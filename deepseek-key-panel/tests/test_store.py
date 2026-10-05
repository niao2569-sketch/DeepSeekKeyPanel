#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地数据文件（INI + DPAPI）测试。

用临时目录作为数据目录，不碰真实的「我的文档」。
DPAPI 仅在 Windows 上可用；其他平台会自动跳过加密相关的断言。
"""

from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

PASS = FAIL = SKIP = 0


def ok(label: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}")


def skip(label: str, why: str) -> None:
    global SKIP
    SKIP += 1
    print(f"  - {label}（跳过：{why}）")


def main() -> int:
    # 用仓库内的临时目录：既不碰真实的「我的文档」，
    # 也不会因为写到系统 %TEMP% 而被沙箱/权限拦掉
    tmp = os.path.join(HERE, ".tmp-store")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    os.environ["DSKP_DATA_DIR"] = tmp
    try:
        from deepseek_key_panel import store
    except ImportError as exc:
        print("!! 无法导入 store 模块:", exc)
        return 1

    print("本地数据文件测试")
    print("=" * 52)
    print(f"数据目录: {store.data_dir()}")
    print()

    print("[1] 路径与状态")
    ok("数据文件位于数据目录下", store.data_file().startswith(tmp))
    ok("文件名是 .ini", store.data_file().endswith(".ini"))
    info = store.info()
    ok("初始状态：文件不存在", info["exists"] is False)
    ok("info() 报告了路径", bool(info["path"]))

    if not store.dpapi_available():
        skip("DPAPI 加解密", "非 Windows 平台")
        print()
        print("=" * 52)
        print(f"  {PASS} 通过，{FAIL} 失败，{SKIP} 跳过")
        return 1 if FAIL else 0

    print()
    print("[2] DPAPI 往返")
    blob = store.dpapi_protect(b"hello-world")
    ok("密文与明文不同", blob != b"hello-world")
    ok("密文不含明文痕迹", b"hello-world" not in blob)
    ok("能解回原文", store.dpapi_unprotect(blob) == b"hello-world")

    tampered = bytearray(blob)
    tampered[-1] ^= 0xFF
    try:
        store.dpapi_unprotect(bytes(tampered))
        ok("密文被篡改会被拒绝", False)
    except OSError:
        ok("密文被篡改会被拒绝", True)

    print()
    print("[3] 保存 / 读取往返（无密码，自动解密）")
    payload = {"keys": [{"name": "主力号", "key": "sk-secret-0001"}],
               "usage": {"total": {"tokens": 12345}},
               "platformToken": "tok-abc",
               "history": {"a": [{"t": 1, "v": 2.5}]}}
    st = store.save(payload)
    ok("save() 返回 exists=True", st["exists"] is True)
    ok("文件确实生成了", os.path.isfile(store.data_file()))
    ok("模式是 dpapi", st["mode"] == "dpapi")

    raw = io.open(store.data_file(), encoding="utf-8").read()
    ok("文件里有 [data] 段", "[data]" in raw)
    ok("文件里没有明文 Key", "sk-secret-0001" not in raw)
    ok("文件里没有明文 Token", "tok-abc" not in raw)

    back = store.load()
    ok("load() 无需密码即可解密", back is not None)
    ok("内容完全一致", back == payload)
    ok("中文没有乱码", back["keys"][0]["name"] == "主力号")

    print()
    print("[4] 覆盖写入")
    payload2 = dict(payload, platformToken="tok-xyz")
    store.save(payload2)
    ok("第二次写入后读回的是新内容", store.load()["platformToken"] == "tok-xyz")

    print()
    print("[5] 主密码（DPAPI 之上的一道门）")
    store.save(payload, password="s3cret-pw", hint="常用的那个")
    info = store.info()
    ok("状态为已锁定", info["locked"] is True)
    ok("模式标记为 dpapi+password", info["mode"] == "dpapi+password")
    ok("提示被保存", info["hint"] == "常用的那个")
    ok("锁定状态下 load() 不返回数据", store.load() is None)

    ok("错误密码解不开", store.unlock("wrong-pw") is None)
    got = store.unlock("s3cret-pw")
    ok("正确密码能解开", got == payload)
    ok("verify() 对正确密码返回 True", store.verify("s3cret-pw") is True)
    ok("verify() 对错误密码返回 False", store.verify("nope") is False)

    print()
    print("[6] INI 结构")
    import configparser
    cp = configparser.ConfigParser()
    cp.read(store.data_file(), encoding="utf-8")
    for sec in ("meta", "security", "data"):
        ok(f"有 [{sec}] 段", cp.has_section(sec))
    ok("meta.app 正确", cp.get("meta", "app") == "deepseek-key-panel")
    ok("记录了 created 时间", bool(cp.get("meta", "created")))
    ok("记录了 updated 时间", bool(cp.get("meta", "updated")))
    ok("迭代次数不少于 200000", cp.getint("security", "iterations") >= 200000)
    ok("payload 是 base64", len(cp.get("data", "payload")) > 100)

    print()
    print("[7] 删除")
    ok("wipe() 返回 True", store.wipe() is True)
    ok("文件已删除", not os.path.isfile(store.data_file()))
    ok("删除后 info() 显示不存在", store.info()["exists"] is False)

    shutil.rmtree(tmp, ignore_errors=True)
    print()
    print("=" * 52)
    print(f"  {PASS} 通过，{FAIL} 失败" + (f"，{SKIP} 跳过" if SKIP else ""))
    print("=" * 52)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
