#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek Key 面板 · 本地服务
=============================

这个模块只负责两件事，不掺和界面：

1. 把面板页面通过 ``http://127.0.0.1:PORT`` 提供出去 —— 页面就有了正常的 http 源，
   不再受 ``file://`` 的各种限制。
2. 转发发往 DeepSeek 的请求，绕开浏览器同源策略，并顺带解锁「官方用量接口」
   （``platform.deepseek.com/api/v0/usage/*`` —— 它没有任何 CORS 响应头，
   还要求自定义请求头，浏览器里无论怎么调都会被拦）。

安全设计
--------
* 只监听 ``127.0.0.1``，局域网和外网都访问不到。
* 只允许转发到 ``api.deepseek.com`` / ``platform.deepseek.com`` 两个白名单域名。
* 不转发 Cookie，不回传 Set-Cookie，不透传 Referer / Origin。
* 不记录、不落盘任何 Authorization / API Key；日志里只有方法、域名、路径、状态码。
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from . import store as store_mod          # 作为包导入
except ImportError:                            # 直接跑 server.py 时
    import store as store_mod                  # type: ignore[no-redef]

VERSION = "1.1.0"

# 允许转发的目标域名白名单（必须是 https）
ALLOWED_HOSTS = {"api.deepseek.com", "platform.deepseek.com"}

# 允许从浏览器透传给上游的请求头（小写）。其余一律丢弃。
FORWARD_HEADERS = ("authorization", "accept", "content-type", "x-app-version")

# 上游看到的是一个正常浏览器 UA，避免被风控 / 网关拒绝
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)

UPSTREAM_TIMEOUT = 25          # 秒
MAX_BODY = 8 * 1024 * 1024     # 单次请求 / 响应体积上限
DEFAULT_PORT = 8787
PORT_TRIES = 12

PANEL_FILENAME = "index.html"


def web_dir() -> str:
    """面板静态文件所在目录。

    打包成单文件 exe 后，资源会被解到 ``sys._MEIPASS``；直接跑源码时就在包目录下。
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, "web")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


def log(msg: str) -> None:
    """打印日志。打包成无控制台窗口的 exe 时 stdout 是 None，这里要兜住。"""
    if sys.stdout is None:
        return
    try:
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# 生命周期：支持「关掉窗口就自动退出」
# ---------------------------------------------------------------------------
class Lifecycle:
    """跟踪页面活动，决定服务何时该退出。

    页面在 ``pagehide`` 时给 ``/bye`` 发一个 beacon。收到后等 ``grace`` 秒：

    * 这期间**没有任何新请求** → 认定窗口真的关了，退出进程。
    * 期间来了新请求（比如用户只是按了 F5） → 取消退出，什么都不做。

    这样既能让双击启动的程序「关窗即退」，又不会因为一次刷新就自杀。
    """

    def __init__(self, exit_on_close: bool = True, grace: float = 3.0,
                 expect_connection: bool = False, connect_timeout: float = 120.0):
        self._lock = threading.Lock()
        self.last_activity = time.time()
        self.bye_at: float | None = None
        self.exit_on_close = exit_on_close
        self.grace = grace
        self.stop_event = threading.Event()
        self.ever_connected = False
        self.started = time.time()
        # 启动时开了窗口，却迟迟没有任何页面连上来 —— 说明启动失败了。
        # 对无控制台窗口的 exe 来说这是唯一能自我了断的信号，否则会变成看不见的僵尸进程。
        self.expect_connection = expect_connection
        self.connect_timeout = connect_timeout

    def touch(self) -> None:
        with self._lock:
            self.last_activity = time.time()
            self.ever_connected = True
            if self.bye_at is not None and self.last_activity > self.bye_at:
                self.bye_at = None          # 有新活动，撤销退出

    def say_bye(self) -> None:
        with self._lock:
            self.bye_at = time.time()

    def request_stop(self) -> None:
        self.stop_event.set()

    def monitor(self, on_exit=None) -> None:
        """后台线程：判断该不该退出。"""
        while not self.stop_event.wait(0.5):
            if (self.expect_connection and not self.ever_connected
                    and (time.time() - self.started) > self.connect_timeout):
                if on_exit:
                    on_exit(f"{int(self.connect_timeout)} 秒内没有界面连上来")
                self.stop_event.set()
                return
            if not self.exit_on_close:
                continue
            with self._lock:
                bye = self.bye_at
                last = self.last_activity
            if bye is not None and last <= bye and (time.time() - bye) >= self.grace:
                if on_exit:
                    on_exit()
                self.stop_event.set()
                return


# ---------------------------------------------------------------------------
# HTTP 处理
# ---------------------------------------------------------------------------
class PanelHandler(BaseHTTPRequestHandler):
    server_version = "DeepSeekKeyPanel/" + VERSION
    protocol_version = "HTTP/1.1"

    # ---------- 基础工具 ----------

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Headers",
            "authorization, content-type, accept, x-app-version",
        )
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Max-Age", "600")

    def _respond(self, code: int, body: bytes,
                 ctype: str = "application/json; charset=utf-8") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        if self.command != "HEAD" and body:
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _json(self, code: int, obj: dict) -> None:
        self._respond(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def log_message(self, fmt, *args):  # 覆盖默认实现，避免把 URL 里的东西写进日志
        pass

    # ---------- 路由 ----------

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self._cors()
        self.end_headers()

    def do_HEAD(self):  # noqa: N802
        self.do_GET()

    def do_GET(self):  # noqa: N802
        self._route(b"")

    def do_PUT(self):  # noqa: N802
        self._read_body_then_route()

    def do_DELETE(self):  # noqa: N802
        self._route(b"")

    def _read_body_then_route(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > MAX_BODY:
            self._json(413, {"error": "request_too_large"})
            return
        self._route(self.rfile.read(length) if length > 0 else b"")

    def do_POST(self):  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > MAX_BODY:
            self._json(413, {"error": "request_too_large"})
            return
        body = self.rfile.read(length) if length > 0 else b""
        self._route(body)

    def _route(self, body: bytes) -> None:
        life: Lifecycle = getattr(self.server, "lifecycle", None)
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path.rstrip("/") or "/"

        # 生命周期相关的路由不参与「活动」判定，否则 /bye 会把自己取消掉
        if path == "/bye":
            if life:
                life.say_bye()
            self._respond(204, b"")
            return

        if path == "/shutdown":
            if life:
                life.request_stop()
            self._json(200, {"ok": True, "message": "服务正在退出"})
            return

        if life:
            life.touch()

        if path == "/health":
            self._json(200, {
                "ok": True,
                "service": "deepseek-key-panel",
                "version": VERSION,
                "allowed_hosts": sorted(ALLOWED_HOSTS),
                "panel": PANEL_FILENAME,
            })
            return

        if path == "/proxy":
            params = urllib.parse.parse_qs(parsed.query)
            target = (params.get("url") or [""])[0]
            if not target:
                self._json(400, {"error": "missing_url",
                                 "hint": "/proxy?url=<URL 编码后的 https 目标地址>"})
                return
            self._proxy(target, body)
            return

        if path == "/store":
            self._store(body)
            return

        if path in ("/", "/index.html", "/panel", "/panel.html"):
            self._serve_panel()
            return

        self._json(404, {"error": "not_found", "path": path})

    # ---------- 本地数据文件（INI + Windows DPAPI） ----------

    def _store(self, body: bytes) -> None:
        try:
            if self.command == "GET":
                st = store_mod.info()
                st["data"] = None if st["locked"] else store_mod.load()
                self._json(200, st)
                return

            if self.command == "PUT":
                payload = json.loads(body.decode("utf-8")) if body else {}
                st = store_mod.save(payload if isinstance(payload, dict) else {})
                log("STORE saved -> %s" % st["path"])
                self._json(200, st)
                return

            if self.command == "DELETE":
                ok = store_mod.wipe()
                self._json(200, {"ok": ok, **store_mod.info()})
                return

            if self.command == "POST":
                req = json.loads(body.decode("utf-8")) if body else {}
                action = req.get("action")

                if action == "unlock":
                    data = store_mod.unlock(str(req.get("password") or ""))
                    if data is None:
                        self._json(403, {"error": "bad_password"})
                    else:
                        self._json(200, {"ok": True, "data": data})
                    return

                if action == "setpassword":
                    st = store_mod.save(req.get("data") or {},
                                        password=str(req.get("password") or ""),
                                        hint=str(req.get("hint") or ""))
                    self._json(200, st)
                    return

                if action == "verify":
                    self._json(200, {"ok": store_mod.verify(str(req.get("password") or ""))})
                    return

                self._json(400, {"error": "unknown_action", "action": action})
                return

            self._json(405, {"error": "method_not_allowed"})
        except Exception as exc:  # noqa: BLE001
            log("STORE-ERROR %s" % exc)
            self._json(500, {"error": "store_error", "detail": str(exc)})

    # ---------- 静态页面 ----------

    def _serve_panel(self) -> None:
        panel_path = os.path.join(web_dir(), PANEL_FILENAME)
        if not os.path.isfile(panel_path):
            self._respond(
                500,
                ("<h1>找不到面板文件</h1><p>期望位置：<code>%s</code></p>"
                 % panel_path).encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return
        with open(panel_path, "rb") as fh:
            data = fh.read()
        self._respond(200, data, "text/html; charset=utf-8")

    # ---------- 代理 ----------

    def _proxy(self, target: str, body: bytes) -> None:
        try:
            parts = urllib.parse.urlsplit(target)
        except ValueError:
            self._json(400, {"error": "bad_url"})
            return

        host = (parts.hostname or "").lower()
        if parts.scheme != "https" or host not in ALLOWED_HOSTS:
            log("BLOCKED %s %s" % (self.command, host or "?"))
            self._json(403, {"error": "host_not_allowed", "host": host,
                             "allowed": sorted(ALLOWED_HOSTS)})
            return

        if len(body) > MAX_BODY:
            self._json(413, {"error": "request_too_large"})
            return

        req = urllib.request.Request(target, data=body if body else None, method=self.command)
        for name in FORWARD_HEADERS:
            value = self.headers.get(name)
            if value:
                req.add_header(name, value)
        # 始终覆盖 UA，且不转发 Cookie / Referer / Origin
        req.add_header("User-Agent", BROWSER_UA)
        if not req.get_header("Accept"):
            req.add_header("Accept", "application/json, */*")

        started = time.time()
        try:
            with urllib.request.urlopen(req, timeout=UPSTREAM_TIMEOUT) as resp:
                data = resp.read(MAX_BODY)
                ctype = resp.headers.get("Content-Type") or "application/json; charset=utf-8"
                code = resp.status
        except urllib.error.HTTPError as exc:  # 4xx/5xx 也是正常业务响应，原样回传
            data = exc.read(MAX_BODY) if exc.fp else b""
            ctype = (exc.headers.get("Content-Type") if exc.headers else None) or \
                "application/json; charset=utf-8"
            code = exc.code
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            log("UPSTREAM-FAIL %s %s -> %s" % (self.command, host, reason))
            self._json(502, {"error": "upstream_unreachable", "detail": str(reason),
                             "hint": "检查本机网络 / 代理 / 防火墙是否能访问 " + host})
            return
        except (socket.timeout, TimeoutError):
            self._json(504, {"error": "upstream_timeout",
                             "detail": "超过 %ds 未响应" % UPSTREAM_TIMEOUT})
            return
        except Exception as exc:  # noqa: BLE001 - 兜底，避免线程崩掉
            log("PROXY-ERROR %s" % exc)
            self._json(500, {"error": "proxy_error", "detail": str(exc)})
            return

        log("%s %s%s -> %s (%dms, %dB)" % (
            self.command, host, parts.path, code,
            int((time.time() - started) * 1000), len(data)))
        self._respond(code, data, ctype)


class PanelServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    lifecycle: Lifecycle


def bind_server(preferred_port: int, lifecycle: Lifecycle | None = None):
    """在 127.0.0.1 上依次尝试端口，返回 ``(server, port)``。"""
    last_error = None
    for offset in range(PORT_TRIES):
        port = preferred_port + offset
        try:
            server = PanelServer(("127.0.0.1", port), PanelHandler)
            server.lifecycle = lifecycle or Lifecycle()
            return server, port
        except OSError as exc:
            last_error = exc
            continue
    raise SystemExit(
        f"端口 {preferred_port}-{preferred_port + PORT_TRIES - 1} 全部被占用：{last_error}")
