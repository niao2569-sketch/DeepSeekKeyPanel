#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地数据文件的 HTTP 层测试。

直接在进程内起服务（不 fork 子进程），用 urllib 打真实的 HTTP 请求。
这样能覆盖「面板通过 /store 存取数据」这条完整链路。
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import threading
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

PASS = FAIL = 0


def ok(label: str, cond: bool, extra: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}" + (f"  — {extra}" if extra else ""))


def call(base: str, path: str, method: str = "GET", payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except ValueError:
            return e.code, {"raw": body}


def main() -> int:
    tmp = os.path.join(HERE, ".tmp-store-http")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    os.environ["DSKP_DATA_DIR"] = tmp

    from deepseek_key_panel import server  # noqa: PLC0415
    from deepseek_key_panel import store   # noqa: PLC0415

    if not store.dpapi_available():
        print("非 Windows 平台，跳过 HTTP 层测试")
        return 0

    srv, _ = server.bind_server(0)
    port = srv.server_address[1]
    base = f"http://127.0.0.1:{port}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    print("本地数据文件 HTTP 层测试")
    print("=" * 52)
    try:
        print("\n[1] 初始状态")
        st, body = call(base, "/store")
        ok("GET /store 返回 200", st == 200, str(st))
        ok("available = true", body.get("available") is True)
        ok("exists = false", body.get("exists") is False)
        ok("data = null", body.get("data") is None)
        ok("返回了文件路径", bool(body.get("path")))

        print("\n[2] PUT 写入")
        payload = {"keys": [{"name": "主力号", "key": "sk-http-secret-9999"}],
                   "platformToken": "tok-http", "history": {"a": [{"t": 1, "v": 2.5}]},
                   "usage": {"total": {"tokens": 42}}}
        st, body = call(base, "/store", "PUT", payload)
        ok("PUT /store 返回 200", st == 200, str(body)[:120])
        ok("响应里 exists = true", body.get("exists") is True)

        print("\n[3] 文件落盘且已加密")
        path = store.data_file()
        ok("INI 文件已生成", os.path.isfile(path))
        raw = io.open(path, encoding="utf-8").read()
        ok("含 [meta] / [security] / [data] 三段",
           all(f"[{s}]" in raw for s in ("meta", "security", "data")))
        ok("不含明文 Key", "sk-http-secret-9999" not in raw)
        ok("不含明文 Token", "tok-http" not in raw)

        print("\n[4] 重新 GET：自动解密")
        st, body = call(base, "/store")
        ok("GET /store 返回 200", st == 200)
        ok("locked = false（无需密码）", body.get("locked") is False)
        ok("data 已自动解密", body.get("data") is not None)
        ok("内容与写入一致", body.get("data") == payload)
        ok("中文没乱码", (body.get("data") or {}).get("keys", [{}])[0].get("name") == "主力号")

        print("\n[5] 设主密码后会被锁定")
        st, body = call(base, "/store", "POST",
                        {"action": "setpassword", "password": "pw123456",
                         "hint": "提示语", "data": payload})
        ok("setpassword 返回 200", st == 200, str(body)[:120])
        st, body = call(base, "/store")
        ok("locked = true", body.get("locked") is True)
        ok("锁定后不再返回 data", body.get("data") is None)
        ok("提示语被保存", body.get("hint") == "提示语")

        print("\n[6] 解锁")
        st, body = call(base, "/store", "POST", {"action": "unlock", "password": "错的"})
        ok("错误密码返回 403", st == 403, str(st))
        st, body = call(base, "/store", "POST", {"action": "unlock", "password": "pw123456"})
        ok("正确密码返回 200", st == 200)
        ok("解锁后拿到数据", body.get("data") == payload)

        print("\n[7] 删除")
        st, body = call(base, "/store", "DELETE")
        ok("DELETE 返回 200", st == 200)
        ok("ok = true", body.get("ok") is True)
        ok("文件已删除", not os.path.isfile(store.data_file()))

        print("\n[8] 未知 action 被拒绝")
        st, body = call(base, "/store", "POST", {"action": "nonsense"})
        ok("返回 400", st == 400, str(st))
    finally:
        srv.shutdown()
        srv.server_close()
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print("=" * 52)
    print(f"  {PASS} 通过，{FAIL} 失败")
    print("=" * 52)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
