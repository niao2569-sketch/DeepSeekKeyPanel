#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
打包成免安装程序
================

    python build.py                # 单文件 exe（推荐分发用，像个正经桌面程序）
    python build.py --console      # 保留控制台窗口，方便看日志 / 排错
    python build.py --onedir       # 输出文件夹（启动更快，也不会被杀软误报解包行为）
    python build.py --all          # 两个都出：单文件 exe + 便携版 zip
    python build.py --no-clean     # 保留 build/ 中间产物

产物在 ``dist/`` 下。

> **为什么还要 onedir？** 单文件 exe 每次启动都要把自己解包到 ``%TEMP%``，
> 这既慢一点，也容易被杀毒软件启发式误报。便携版不需要解包，是稳妥的备选。

依赖 PyInstaller。没装的话：
    python -m pip install pyinstaller
或者用仓库自带的 ``.tools/fetch_wheels.py``（不走 pip，直接解包 wheel 放进 .pytools/）。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP_NAME = "DeepSeekKeyPanel"
ENTRY = os.path.join(HERE, "run_panel.py")
WEB_DIR = os.path.join(HERE, "src", "deepseek_key_panel", "web")
ICON = os.path.join(HERE, "assets", "icon.ico")
LOCAL_TOOLS = os.path.join(HERE, ".pytools")
DIST = os.path.join(HERE, "dist")


def ensure_pyinstaller() -> None:
    """优先用仓库内 .pytools 里的 PyInstaller，其次用系统装的。"""
    if os.path.isdir(LOCAL_TOOLS):
        sys.path.insert(0, LOCAL_TOOLS)
    try:
        import PyInstaller  # noqa: F401, PLC0415
    except ImportError:
        print("[错误] 没找到 PyInstaller。两种装法都行：")
        print("       python -m pip install pyinstaller")
        print("       python .tools/fetch_wheels.py      # 不走 pip 的备选方案")
        raise SystemExit(2)


def check_sources() -> bool:
    if not os.path.isfile(ENTRY):
        print(f"[错误] 找不到入口脚本 {ENTRY}")
        return False
    if not os.path.isdir(WEB_DIR):
        print(f"[错误] 找不到面板目录 {WEB_DIR}")
        return False
    return True


def run_pyinstaller(name: str, onedir: bool, console: bool, icon: bool,
                    clean: bool) -> int:
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean" if clean else "--nocheck",
        "--onedir" if onedir else "--onefile",
        "--name", name,
        # 把包目录加进搜索路径
        "--paths", os.path.join(HERE, "src"),
        # 面板页面作为数据文件打进去，运行时从 sys._MEIPASS 取
        "--add-data", f"{WEB_DIR}{os.pathsep}web",
        "--hidden-import", "deepseek_key_panel",
        # server.py 里的 store 是 try/except 相对导入，显式声明避免被静态分析漏掉
        "--hidden-import", "deepseek_key_panel.store",
    ]
    cmd += ["--console"] if console else ["--noconsole"]
    if icon and os.path.isfile(ICON):
        cmd.append(f"--icon={ICON}")
    cmd.append(ENTRY)

    print("  " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    env = dict(os.environ)
    if os.path.isdir(LOCAL_TOOLS):
        env["PYTHONPATH"] = LOCAL_TOOLS + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.call(cmd, cwd=HERE, env=env)


def cleanup_intermediates(name: str) -> None:
    for junk in ("build", f"{name}.spec"):
        p = os.path.join(HERE, junk)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
        elif os.path.isfile(p):
            try:
                os.remove(p)
            except OSError:
                pass


def report(name: str, onedir: bool) -> None:
    exe = os.path.join(DIST, name, name + ".exe") if onedir else \
        os.path.join(DIST, name + (".exe" if os.name == "nt" else ""))
    if os.path.isfile(exe):
        size = os.path.getsize(exe) / 1024 / 1024
        print(f"  [完成] {exe}  ({size:.1f} MB)")
        print("         双击即可运行，目标机器不需要装 Python。")
    else:
        print(f"  [完成] 产物在 {DIST}")


def build(args) -> int:
    ensure_pyinstaller()
    if not check_sources():
        return 2

    os.makedirs(DIST, exist_ok=True)

    if args.all:
        targets = [(args.name, False), (args.name + "-portable", True)]
    else:
        targets = [(args.name, bool(args.onedir))]

    for name, onedir in targets:
        kind = "文件夹（便携版）" if onedir else "单文件"
        print(f"\n=== 构建 {name} · {kind} ===")
        rc = run_pyinstaller(name, onedir, args.console, not args.no_icon, not args.no_clean)
        if rc != 0:
            print(f"\n[失败] PyInstaller 退出码 {rc}")
            return rc
        report(name, onedir)
        if not args.no_clean:
            cleanup_intermediates(name)

    if args.all and os.name == "nt":
        src = os.path.join(DIST, args.name + "-portable")
        if os.path.isdir(src):
            print("\n=== 打包便携版 zip ===")
            archive = shutil.make_archive(
                os.path.join(DIST, args.name + "-portable"), "zip", src)
            print(f"  [完成] {archive}  "
                  f"({os.path.getsize(archive) / 1024 / 1024:.1f} MB)")
            print("         解压后双击里面的 exe 即可，无需安装。")

    print()
    print("提示：单文件版每次启动会把自己解包到 %TEMP%，个别杀毒软件会误报；")
    print("      遇到这种情况改用便携版（--onedir / --all 产出的 zip）。")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="把 DeepSeek Key 面板打包成免安装程序")
    p.add_argument("--name", default=APP_NAME, help=f"产物名（默认 {APP_NAME}）")
    p.add_argument("--console", action="store_true", help="保留控制台窗口（默认无窗口）")
    p.add_argument("--onedir", action="store_true",
                   help="输出文件夹而非单文件（启动更快，不易被杀软误报）")
    p.add_argument("--all", action="store_true",
                   help="同时产出单文件 exe 和便携版 zip")
    p.add_argument("--no-icon", action="store_true", help="不使用图标")
    p.add_argument("--no-clean", action="store_true", help="保留 build/ 中间产物")
    args = p.parse_args()
    if args.all and args.onedir:
        print("[提示] --all 已包含 --onedir，忽略后者")
    return build(args)


if __name__ == "__main__":
    raise SystemExit(main())
