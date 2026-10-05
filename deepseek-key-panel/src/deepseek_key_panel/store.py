#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地数据文件（INI）
===================

把面板的数据落到磁盘上的一个 INI 文件里，默认位置：

    我的文档\\DeepSeekKeyPanel\\dskp.ini

加密方式用 **Windows DPAPI**（``CryptProtectData``）：密钥由你的 Windows
账户派生，**只有当前这台机器的这个 Windows 用户能解开**。好处是打开面板
就能自动解密，不用输密码；坏处是这个文件拷到别的电脑或别的账户下就是
一堆废数据 —— 这通常正是我们想要的。

可选的「主密码」是在 DPAPI 之上再加一道门：文件本身仍然由 DPAPI 加密，
但必须先用正确的密码通过 PBKDF2 校验，服务才会把明文交出来。这能挡住
「别人趁你没锁屏用你的电脑」这种情况。

文件格式：

    [meta]
    version  = 2
    app      = deepseek-key-panel
    created  = 2026-10-06T12:00:00
    updated  = 2026-10-06T12:34:56
    mode     = dpapi | dpapi+password

    [security]
    iterations = 250000
    salt       =
    verifier   =
    hint       =

    [data]
    payload    = <base64(DPAPI(JSON))>
"""

from __future__ import annotations

import base64
import configparser
import ctypes
import hashlib
import hmac
import io
import json
import os
import sys
import time
from ctypes import wintypes

APP_DIR_NAME = "DeepSeekKeyPanel"
FILE_NAME = "dskp.ini"
PBKDF2_ITERATIONS = 250_000
ENTROPY = b"deepseek-key-panel/v2"      # DPAPI 附加熵，进一步限定用途

IS_WINDOWS = os.name == "nt"

# ---------------------------------------------------------------------------
# 数据文件位置
# ---------------------------------------------------------------------------
def data_dir() -> str:
    """数据目录。可用 DSKP_DATA_DIR 环境变量覆盖（便于做成便携版）。"""
    override = os.environ.get("DSKP_DATA_DIR")
    if override:
        return os.path.abspath(override)
    # 便携模式：exe / 源码旁边可写就放旁边
    base = getattr(sys, "_MEIPASS", None)
    portable = os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv and sys.argv[0] else ""
    if portable and os.path.isdir(portable):
        probe = os.path.join(portable, "dskp-data")
        try:
            os.makedirs(probe, exist_ok=True)
            test = os.path.join(probe, ".w")
            with io.open(test, "w", encoding="utf-8") as fh:
                fh.write("1")
            os.remove(test)
            return probe
        except OSError:
            pass
    # 默认：我的文档
    docs = None
    if IS_WINDOWS:
        try:
            buf = ctypes.create_unicode_buffer(260)
            # CSIDL_PERSONAL = 5
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:
                docs = buf.value
        except Exception:  # noqa: BLE001
            docs = None
    if not docs:
        docs = os.path.join(os.path.expanduser("~"), "Documents")
    return os.path.join(docs, APP_DIR_NAME)


def data_file() -> str:
    return os.path.join(data_dir(), FILE_NAME)


# ---------------------------------------------------------------------------
# Windows DPAPI
# ---------------------------------------------------------------------------
class _BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _make_blob(data: bytes):
    """返回 (BLOB, 保活缓冲)。缓冲必须活到 API 调用结束，否则内存会被回收。"""
    buf = ctypes.create_string_buffer(data, len(data))
    return _BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def _free(blob: _BLOB) -> None:
    if blob.pbData:
        ctypes.windll.kernel32.LocalFree(blob.pbData)


def dpapi_available() -> bool:
    return IS_WINDOWS and hasattr(ctypes, "windll")


def dpapi_protect(data: bytes) -> bytes:
    if not dpapi_available():
        raise RuntimeError("DPAPI 仅在 Windows 上可用")
    src, _keep_src = _make_blob(data)
    ent, _keep_ent = _make_blob(ENTROPY)
    out = _BLOB()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(src), None, ctypes.byref(ent), None, None, 0, ctypes.byref(out))
    if not ok:
        raise OSError(f"CryptProtectData 失败，错误码 {ctypes.GetLastError()}")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        _free(out)


def dpapi_unprotect(data: bytes) -> bytes:
    if not dpapi_available():
        raise RuntimeError("DPAPI 仅在 Windows 上可用")
    src, _keep_src = _make_blob(data)
    ent, _keep_ent = _make_blob(ENTROPY)
    out = _BLOB()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(src), None, ctypes.byref(ent), None, None, 0, ctypes.byref(out))
    if not ok:
        raise OSError("解密失败：文件可能来自另一台电脑或另一个 Windows 账户")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        _free(out)


# ---------------------------------------------------------------------------
# 主密码（可选，DPAPI 之上的一道门）
# ---------------------------------------------------------------------------
def _hash_password(password: str, salt: bytes, iterations: int) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return base64.b64encode(dk).decode("ascii")


def _new_salt() -> bytes:
    return os.urandom(16)


# ---------------------------------------------------------------------------
# 读写
# ---------------------------------------------------------------------------
def _read_ini() -> configparser.ConfigParser | None:
    path = data_file()
    if not os.path.isfile(path):
        return None
    cp = configparser.ConfigParser()
    try:
        cp.read(path, encoding="utf-8")
    except Exception:  # noqa: BLE001
        return None
    return cp


def info() -> dict:
    """返回数据文件的状态（不返回明文）。"""
    path = data_file()
    out = {
        "available": dpapi_available(),
        "path": path,
        "dir": data_dir(),
        "exists": os.path.isfile(path),
        "locked": False,
        "hint": "",
        "mode": "",
        "updated": "",
        "size": 0,
    }
    if out["exists"]:
        try:
            out["size"] = os.path.getsize(path)
        except OSError:
            pass
        cp = _read_ini()
        if cp:
            out["mode"] = cp.get("meta", "mode", fallback="")
            out["updated"] = cp.get("meta", "updated", fallback="")
            out["hint"] = cp.get("security", "hint", fallback="")
            out["locked"] = bool(cp.get("security", "verifier", fallback="").strip())
    return out


def load() -> dict | None:
    """读取并解密。有主密码时返回 None（需要先 unlock）。"""
    cp = _read_ini()
    if not cp:
        return None
    if cp.get("security", "verifier", fallback="").strip():
        return None                                   # 需要密码
    return _decrypt_payload(cp)


def unlock(password: str) -> dict | None:
    """用主密码解锁；密码不对返回 None。"""
    cp = _read_ini()
    if not cp:
        return None
    verifier = cp.get("security", "verifier", fallback="").strip()
    if verifier:
        salt = base64.b64decode(cp.get("security", "salt", fallback=""))
        iters = cp.getint("security", "iterations", fallback=PBKDF2_ITERATIONS)
        if not hmac.compare_digest(_hash_password(password, salt, iters), verifier):
            return None
    return _decrypt_payload(cp)


def verify(password: str) -> bool:
    cp = _read_ini()
    if not cp:
        return False
    verifier = cp.get("security", "verifier", fallback="").strip()
    if not verifier:
        return True
    salt = base64.b64decode(cp.get("security", "salt", fallback=""))
    iters = cp.getint("security", "iterations", fallback=PBKDF2_ITERATIONS)
    return hmac.compare_digest(_hash_password(password, salt, iters), verifier)


def _decrypt_payload(cp: configparser.ConfigParser) -> dict | None:
    raw = cp.get("data", "payload", fallback="").strip()
    if not raw:
        return None
    blob = base64.b64decode(raw)
    plain = dpapi_unprotect(blob)
    return json.loads(plain.decode("utf-8"))


def save(payload: dict, password: str | None = None,
         hint: str | None = None) -> dict:
    """加密并写入。``password`` 为 None 表示保持原有的密码设置不变。"""
    cp = _read_ini() or configparser.ConfigParser()
    for section in ("meta", "security", "data"):
        if not cp.has_section(section):
            cp.add_section(section)

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    if not cp.get("meta", "created", fallback=""):
        cp.set("meta", "created", now)

    # 密码设置：显式传入就以传入的为准，否则沿用文件里已有的
    if password is not None:
        if password:
            salt = _new_salt()
            cp.set("security", "salt", base64.b64encode(salt).decode("ascii"))
            cp.set("security", "verifier",
                   _hash_password(password, salt, PBKDF2_ITERATIONS))
            cp.set("security", "iterations", str(PBKDF2_ITERATIONS))
        else:
            cp.set("security", "salt", "")
            cp.set("security", "verifier", "")
            cp.set("security", "iterations", str(PBKDF2_ITERATIONS))
    if hint is not None:
        cp.set("security", "hint", hint)

    has_pw = bool(cp.get("security", "verifier", fallback="").strip())
    cp.set("meta", "version", "2")
    cp.set("meta", "app", "deepseek-key-panel")
    cp.set("meta", "updated", now)
    cp.set("meta", "mode", "dpapi+password" if has_pw else "dpapi")

    cp.set("data", "payload", base64.b64encode(
        dpapi_protect(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    ).decode("ascii"))

    os.makedirs(data_dir(), exist_ok=True)
    path = data_file()
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as fh:
        cp.write(fh)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return info()


def wipe() -> bool:
    path = data_file()
    if os.path.isfile(path):
        try:
            os.remove(path)
            return True
        except OSError:
            return False
    return False


if __name__ == "__main__":       # 手工排查用
    import pprint
    pprint.pprint(info())
