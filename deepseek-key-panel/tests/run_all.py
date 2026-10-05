#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一把梭跑完所有自检。CI 和本地开发都用它。

    python tests/run_all.py

包含：
  1. Python 语法编译（app / server / cli / run_panel / build）
  2. 抽出面板内联 JS，做结构检查
  3. JS 语法检查（``node --check``，没装 node 就跳过）
  4. id 交叉检查（JS 引用的每个 #id 是否真实存在）
  5. 纯逻辑断言（``node tests/test_logic.js``）
  6. CLI 冒烟测试（--help / --version / 参数校验退出码）
"""

from __future__ import annotations

import io
import json
import os
import py_compile
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
PANEL = os.path.join(SRC, "deepseek_key_panel", "web", "index.html")
CHECK_JS = os.path.join(HERE, "_panel_check.js")

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results: list[tuple[str, str, str]] = []


def record(name: str, state: str, detail: str = "") -> None:
    results.append((name, state, detail))
    mark = {"PASS": "  ok  ", "FAIL": " FAIL ", "SKIP": " skip "}[state]
    print(f"[{mark}] {name}" + (f"  — {detail}" if detail else ""))


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", **kw)


# ---------------------------------------------------------------- 1. 编译
def step_compile() -> None:
    targets = ["run_panel.py", "build.py"]
    targets += [os.path.join("src", "deepseek_key_panel", f)
                for f in ("__init__.py", "__main__.py", "app.py", "server.py", "cli.py")]
    targets += [os.path.join("tests", f)
                for f in ("extract_js.py", "check_ids.py", "probe_endpoints.py")]
    bad = []
    for rel in targets:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            bad.append(f"{rel}(缺失)")
            continue
        try:
            py_compile.compile(path, cfile=os.path.join(HERE, "_pyc.tmp"), doraise=True)
        except py_compile.PyCompileError as exc:
            bad.append(f"{rel}({str(exc).splitlines()[-1][:70]})")
    if bad:
        record("Python 语法编译", FAIL, "; ".join(bad))
    else:
        record("Python 语法编译", PASS, f"{len(targets)} 个文件")


# ------------------------------------------------------- 2. 抽 JS + 结构检查
def step_extract() -> bool:
    if not os.path.isfile(PANEL):
        record("抽出面板 JS", FAIL, f"找不到 {PANEL}")
        return False
    r = run([sys.executable, os.path.join(HERE, "extract_js.py")], cwd=HERE)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0 or not os.path.isfile(CHECK_JS):
        record("抽出面板 JS", FAIL, out.strip()[-200:])
        return False
    fails = [ln for ln in out.splitlines() if "FAIL" in ln]
    if fails:
        record("面板结构检查", FAIL, "; ".join(f.strip() for f in fails))
    else:
        record("面板结构检查", PASS, "HTML 完整 / 无外部资源 / 端点齐全")
    return True


# ------------------------------------------------------------ 3. JS 语法
def step_node_check() -> None:
    node = shutil.which("node")
    if not node:
        record("JS 语法检查", SKIP, "PATH 里没有 node")
        return
    r = run([node, "--check", CHECK_JS])
    if r.returncode == 0:
        record("JS 语法检查", PASS)
    else:
        record("JS 语法检查", FAIL, (r.stderr or "").strip()[:200])


# --------------------------------------------------------------- 4. id 检查
def step_ids() -> None:
    r = run([sys.executable, os.path.join(HERE, "check_ids.py")], cwd=HERE)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode == 0:
        n = next((ln.split(":")[-1].strip() for ln in out.splitlines()
                  if "JS 中引用的 id" in ln), "?")
        record("id 交叉检查", PASS, f"{n} 个引用全部命中")
    else:
        # 只在 "!!" 之后找缺失项。否则会把「声明了但没被引用」的提示行
        # 也当成错误报出来（这些是正常的，比如只用于 CSS 的锚点）。
        seg = out.split("!!", 1)[-1] if "!!" in out else out
        bad = [ln.strip() for ln in seg.splitlines() if ln.strip().startswith("#")]
        record("id 交叉检查", FAIL, "; ".join(bad)[:200] or "存在引用不到的 id")


# ------------------------------------------------------------- 5. 逻辑断言
def step_logic() -> None:
    node = shutil.which("node")
    if not node:
        record("纯逻辑断言", SKIP, "PATH 里没有 node")
        return
    r = run([node, os.path.join(HERE, "test_logic.js")], cwd=HERE)
    out = (r.stdout or "") + (r.stderr or "")
    summary = next((ln.strip() for ln in out.splitlines() if "通过" in ln and "失败" in ln), "")
    if r.returncode == 0:
        record("纯逻辑断言", PASS, summary)
    else:
        bad = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("✗")]
        record("纯逻辑断言", FAIL, " | ".join(bad)[:220] or summary)


# --------------------------------------------------- 6. 桌面入口真起一次服务
def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def step_server() -> None:
    """真的把 app 起起来，打 /health 和 /，再让它自己退。

    这一步专门防「参数名写错、启动即崩」这类问题 ——
    打包成 --noconsole 的 exe 之后，这种崩溃是完全看不见的。
    """
    env = dict(os.environ, PYTHONPATH=SRC, PYTHONIOENCODING="utf-8")
    port = _free_port()
    # 注意不要加 --no-exit-on-close：下面要验证 /bye 能不能让服务自己退。
    # --no-open 已经保证不会有人在测试期间发 /bye，所以不会提前退出。
    proc = subprocess.Popen(
        [sys.executable, "-m", "deepseek_key_panel.app",
         "--no-open", "--port", str(port), "--quiet"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        up = False
        for _ in range(48):
            time.sleep(0.25)
            if proc.poll() is not None:
                record("启动即崩（桌面入口）", FAIL,
                       f"进程启动后立刻退出，退出码 {proc.returncode}")
                return
            try:
                with urllib.request.urlopen(base + "/health", timeout=2) as r:
                    if json.load(r).get("ok"):
                        up = True
                        break
            except Exception:  # noqa: BLE001
                continue
        if not up:
            record("桌面入口起服务", FAIL, "10 秒内 /health 没起来")
            return
        record("桌面入口起服务", PASS, f"127.0.0.1:{port} /health 正常")

        with urllib.request.urlopen(base + "/", timeout=5) as r:
            body = r.read()
        local = io.open(PANEL, "rb").read()
        if body == local:
            record("面板投递一致性", PASS, f"{len(body)} 字节")
        else:
            record("面板投递一致性", FAIL, f"服务端 {len(body)} vs 源文件 {len(local)}")

        # 关窗心跳要能真的让服务退出
        try:
            req = urllib.request.Request(base + "/bye", method="POST", data=b"")
            urllib.request.urlopen(req, timeout=5).read()
        except Exception:  # noqa: BLE001
            pass
        for _ in range(24):
            time.sleep(0.25)
            if proc.poll() is not None:
                record("关窗自动退出", PASS, "收到 /bye 后进程自行结束")
                return
        record("关窗自动退出", FAIL, "发了 /bye 但进程没退")
    finally:
        if proc.poll() is None:
            proc.kill()
        try:
            proc.wait(timeout=5)
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------- 6.5 本地数据文件
def step_store() -> None:
    r = run([sys.executable, os.path.join(HERE, "test_store.py")], cwd=HERE)
    out = (r.stdout or "") + (r.stderr or "")
    summary = next((ln.strip() for ln in out.splitlines() if "通过" in ln and "失败" in ln), "")
    if r.returncode == 0:
        record("本地数据文件 (INI+DPAPI)", PASS, summary)
    else:
        bad = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("✗")]
        record("本地数据文件 (INI+DPAPI)", FAIL, " | ".join(bad)[:200] or summary)

    r = run([sys.executable, os.path.join(HERE, "test_store_http.py")], cwd=HERE)
    out = (r.stdout or "") + (r.stderr or "")
    summary = next((ln.strip() for ln in out.splitlines() if "通过" in ln and "失败" in ln), "")
    if r.returncode == 0:
        record("数据文件 HTTP 接口", PASS, summary)
    else:
        bad = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("✗")]
        record("数据文件 HTTP 接口", FAIL, " | ".join(bad)[:200] or summary)


# --------------------------------------------------------------- 7. 语言覆盖
def step_i18n() -> None:
    r = run([sys.executable, os.path.join(HERE, "check_i18n.py")], cwd=HERE)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode == 0:
        n = "?"
        for ln in out.splitlines():
            if "ZH2EN" in ln:
                n = ln.split(":")[-1].strip()
        record("中英双语覆盖", PASS, f"ZH2EN {n} 条映射，标记无遗漏")
    else:
        bad = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("FAIL")]
        record("中英双语覆盖", FAIL, "; ".join(bad)[:200])


# --------------------------------------------------------------- 8. CLI 冒烟
def step_cli() -> None:
    env = dict(os.environ, PYTHONPATH=SRC, PYTHONIOENCODING="utf-8")
    exe = [sys.executable, "-m", "deepseek_key_panel.cli"]

    r = run(exe + ["--version"], env=env)
    if r.returncode != 0 or "1." not in (r.stdout or ""):
        record("CLI --version", FAIL, (r.stderr or "").strip()[:120])
    else:
        record("CLI --version", PASS, (r.stdout or "").strip())

    r = run(exe + ["--help"], env=env)
    record("CLI --help", PASS if r.returncode == 0 else FAIL)

    r = run(exe + ["--usage-token", "x"], env=env)
    record("CLI 参数校验退出码", PASS if r.returncode == 2 else FAIL,
           f"exit={r.returncode}（期望 2）")


def cleanup() -> None:
    for junk in ("_panel_check.js", "_pyc.tmp", "__pycache__"):
        p = os.path.join(HERE, junk)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
        elif os.path.isfile(p):
            try:
                os.remove(p)
            except OSError:
                pass


def main() -> int:
    print("DeepSeek Key 面板 · 自检")
    print("=" * 52)
    print()
    step_compile()
    ok = step_extract()
    step_node_check()
    if ok:
        step_ids()
    step_logic()
    step_i18n()
    step_store()
    step_server()
    step_cli()

    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    n_skip = sum(1 for _, s, _ in results if s == SKIP)
    print()
    print("=" * 52)
    print(f"  {len(results)} 项检查：{len(results)-n_fail-n_skip} 通过"
          + (f"，{n_skip} 跳过" if n_skip else "")
          + (f"，{n_fail} 失败" if n_fail else ""))
    if n_skip:
        print("  （跳过的是需要 node 的检查；装了 Node.js 就能全跑）")
    print("=" * 52)
    cleanup()
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
