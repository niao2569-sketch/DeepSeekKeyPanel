#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek Key 面板 · 桌面入口
=============================

把本地服务跑起来，然后开一个**无边框应用窗口**（不是普通浏览器标签页）——
看起来就是个正经桌面程序，没有地址栏、没有书签栏。

关掉窗口程序会自己退出（页面在 ``pagehide`` 时给服务发一个 ``/bye`` 心跳，
服务等几秒确认没有新请求就收摊；按 F5 刷新不会误杀）。

用 ``--no-window`` 可以退回普通浏览器标签页，``--port`` 换端口。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
import webbrowser

from .server import (
    ALLOWED_HOSTS,
    DEFAULT_PORT,
    VERSION,
    Lifecycle,
    bind_server,
    log,
)


def _out(msg: str = "") -> None:
    """打包成无控制台窗口的 exe 时 stdout 可能是 None，这里兜一层。"""
    if sys.stdout is None:
        return
    try:
        print(msg, flush=True)
    except Exception:
        pass


# 常见 Chromium 系浏览器，按顺序找。用 --app 打开就是无边框窗口。
BROWSER_CANDIDATES = (
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"%ProgramFiles%\Vivaldi\Application\vivaldi.exe",
    r"%LOCALAPPDATA%\Programs\Opera\opera.exe",
)


def find_browser() -> str | None:
    for raw in BROWSER_CANDIDATES:
        path = os.path.expandvars(raw)
        if os.path.isfile(path):
            return path
    return None


def open_window(url: str, app_window: bool = True,
                window_size: str = "1480,1020") -> str:
    """打开面板。返回实际用的方式：``app`` / ``tab``。"""
    if app_window and os.name == "nt":
        exe = find_browser()
        if exe:
            try:
                subprocess.Popen(
                    [exe, f"--app={url}", f"--window-size={window_size}",
                     "--no-first-run", "--no-default-browser-check"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    close_fds=True,
                )
                return "app"
            except Exception as exc:  # noqa: BLE001
                log(f"应用窗口启动失败（{exc}），退回普通标签页")
    webbrowser.open(url)
    return "tab"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="deepseek-key-panel",
        description="DeepSeek Key 面板 —— 本地批量查余额、验证可用性、看用量",
    )
    p.add_argument("--port", type=int, default=DEFAULT_PORT,
                   help=f"监听端口（默认 {DEFAULT_PORT}，被占用会自动往后试）")
    p.add_argument("--no-open", action="store_true", help="启动后不自动打开界面")
    p.add_argument("--no-window", action="store_true",
                   help="用普通浏览器标签页打开，而不是无边框应用窗口")
    p.add_argument("--no-exit-on-close", action="store_true",
                   help="关掉界面后不自动退出（默认会自动退出）")
    p.add_argument("--grace", type=float, default=3.0,
                   help="收到关窗信号后等待多少秒再退出（默认 3 秒，刷新页面不会误杀）")
    p.add_argument("--quiet", action="store_true", help="不打印启动横幅")
    p.add_argument("-V", "--version", action="version", version=f"%(prog)s {VERSION}")
    return p


def banner(url: str, how: str, exit_on_close: bool) -> None:
    _out()
    _out("  ╭──────────────────────────────────────────────────╮")
    _out(f"  │   🐋  DeepSeek Key 面板    v{VERSION}                │")
    _out("  ╰──────────────────────────────────────────────────╯")
    _out(f"   界面地址 : {url}")
    _out(f"   打开方式 : {'无边框应用窗口' if how == 'app' else '浏览器标签页'}")
    _out(f"   健康检查 : {url}health")
    _out( "   安全边界 : 仅监听 127.0.0.1；只放行 " + " / ".join(sorted(ALLOWED_HOSTS)))
    _out( "   退出方式 : " + ("关闭窗口自动退出，或按 Ctrl+C" if exit_on_close else "按 Ctrl+C"))
    _out()


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    lifecycle = Lifecycle(
        exit_on_close=not args.no_exit_on_close,
        grace=args.grace,
        expect_connection=not args.no_open,
    )
    server, port = bind_server(args.port, lifecycle)
    url = f"http://127.0.0.1:{port}/"

    how = "tab"
    if not args.no_open:
        how = open_window(url, app_window=not args.no_window)

    if args.quiet:
        _out(url)          # 静默模式只吐地址，方便脚本抓
    else:
        banner(url, how, lifecycle.exit_on_close)

    def on_exit(reason: str):
        if not args.quiet:
            _out(f"\n  {reason}，正在退出…")

    threading.Thread(
        target=lifecycle.monitor,
        kwargs={"on_exit": lambda: (on_exit("界面已关闭"), server.shutdown())},
        daemon=True,
    ).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        on_exit("收到 Ctrl+C")
    finally:
        try:
            server.shutdown()
        except Exception:  # noqa: BLE001
            pass
        server.server_close()

    if not args.quiet:
        _out("  已停止。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
