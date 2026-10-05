#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek Key 面板 · 命令行版 (cli.py)
======================================

零依赖，只用 Python 标准库。适合批量查几十上百个 Key、丢进定时任务、或者接进别的脚本。

示例
----
  # 查 keys.txt 里所有 Key 的余额
  python cli.py

  # 从文件读，顺便做 /models 可用性验证，输出 CSV
  python cli.py -f keys.txt --models --format csv --out result.csv

  # 直接给几个 Key，并发 8，超时 10 秒
  python cli.py -k sk-aaa -k sk-bbb -c 8 -t 10

  # 管道用法：只输出能用的 Key，直接喂给别的工具
  python cli.py -f all.txt --quiet --format txt --only ok > usable.txt

  # 余额低于 10 就报警（退出码 3），方便接监控
  python cli.py -f keys.txt --threshold 10 || echo "有 Key 余额不足"

  # 拉官方用量（需要平台登录 Token，Python 直连即可，不用中转）
  python cli.py --usage-token "xxx" --usage-month 2026-10

退出码
------
  0  全部成功
  1  有 Key 查询失败
  2  参数或输入错误
  3  有 Key 余额低于 --threshold（查询本身是成功的）
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

VERSION = "1.1.0"
BALANCE_URL = "https://api.deepseek.com/user/balance"
MODELS_URL = "https://api.deepseek.com/models"
CHAT_URL = "https://api.deepseek.com/chat/completions"
PLATFORM_BASE = "https://platform.deepseek.com/api/v0/usage"

KEY_RE = re.compile(r"(sk-[A-Za-z0-9_\-]{10,}|[A-Za-z0-9_\-]{32,})")
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36")

EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_THRESHOLD = 0, 1, 2, 3


# --------------------------------------------------------------------------
# 终端颜色（Windows 10+ 需要先打开 VT 处理）
# --------------------------------------------------------------------------
def _enable_ansi() -> bool:
    if os.name != "nt":
        return True
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


USE_COLOR = False


def c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


GREEN, RED, YELLOW, DIM, BOLD, BLUE = "32", "31", "33", "2", "1", "36"


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------
# 输入解析（和网页版保持一致的宽松规则）
# --------------------------------------------------------------------------
def parse_keys(text: str) -> list[dict]:
    out: list[dict] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip().strip("\"'") for p in re.split(r"[,\t;|]+", line)]
        parts = [p for p in parts if p]
        key = next((p for p in parts if re.fullmatch(r"sk-[A-Za-z0-9_\-]{10,}", p)), None)
        if not key:
            key = next((p for p in parts if re.fullmatch(r"[A-Za-z0-9_\-]{32,}", p)), None)
        if not key:
            m = KEY_RE.search(line)
            if m:
                key = m.group(1)
        if not key:
            continue
        key = re.sub(r"^Bearer\s+", "", key, flags=re.I).strip()
        name = " ".join(p for p in parts if p != key)[:60]
        out.append({"name": name, "key": key, "auto": not name})
    return out


def read_flexible(path: str) -> list[dict]:
    try:
        with io.open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
            text = fh.read()
    except OSError as exc:
        log(f"[错误] 读不了 {path}：{exc}")
        raise SystemExit(EXIT_USAGE)
    if path.lower().endswith(".json"):
        try:
            data = json.loads(text)
        except ValueError:
            data = None
        if data is not None:
            found: list[dict] = []

            def walk(node):
                if isinstance(node, list):
                    for x in node:
                        walk(x)
                elif isinstance(node, dict):
                    v = next((node.get(k) for k in
                              ("key", "apiKey", "api_key", "token", "sk", "value")
                              if isinstance(node.get(k), str)), None)
                    if v and v.strip():
                        found.append({"name": node.get("name") or node.get("label") or "",
                                      "key": v.strip()})
                    else:
                        for x in node.values():
                            if isinstance(x, (list, dict)):
                                walk(x)
                elif isinstance(node, str):
                    found.append({"name": "", "key": node.strip()})
            walk(data)
            found = [x for x in found if x["key"]]
            if found:
                for x in found:
                    x["auto"] = not x["name"]
                return found
    return parse_keys(text)


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
def http_json(url: str, key: str | None, timeout: float, method: str = "GET",
              body: dict | None = None, extra: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if key:
        req.add_header("Authorization", "Bearer " + key)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", BROWSER_UA)
    if data:
        req.add_header("Content-Type", "application/json")
    for k, v in (extra or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(1 << 20).decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read(1 << 20).decode("utf-8", "replace") if exc.fp else ""
        status = exc.code
    except Exception as exc:  # noqa: BLE001
        return None, None, str(exc)
    try:
        return status, json.loads(raw), None
    except ValueError:
        return status, None, raw[:200]


STATUS_TEXT = {
    "ok": "可用", "low": "余额不足", "invalid": "Key 无效", "ratelimit": "被限流",
    "server": "官方异常", "network": "网络错误", "error": "查询失败",
}
STATUS_MARK = {
    "ok": ("✔", GREEN), "low": ("!", YELLOW), "invalid": ("✘", RED),
    "ratelimit": ("~", YELLOW), "server": ("!", RED), "network": ("!", RED), "error": ("?", RED),
}


def fetch_balance(key: str, timeout: float, retries: int) -> dict:
    last = ""
    for attempt in range(retries + 1):
        status, data, err = http_json(BALANCE_URL, key, timeout)
        if err is not None and status is None:
            last = err
            time.sleep(0.4 * (attempt + 1))
            continue
        out = {"http": status, "requestId": None, "apiMsg": None}
        api_msg = ((data or {}).get("error") or {}).get("message")
        if api_msg:
            out["apiMsg"] = api_msg
            m = re.search(r"request_id:\s*([\w-]+)", api_msg)
            if m:
                out["requestId"] = m.group(1)
        if status == 200 and isinstance((data or {}).get("balance_infos"), list):
            infos = [{"currency": b.get("currency"), "total": b.get("total_balance"),
                      "granted": b.get("granted_balance"), "topped": b.get("topped_up_balance")}
                     for b in data["balance_infos"]]
            out.update(status_key="low" if not data.get("is_available") else "ok",
                       infos=infos, isAvailable=bool(data.get("is_available")))
            return out
        if status == 401:
            out["status_key"] = "invalid"
        elif status == 402:
            out.update(status_key="invalid", apiMsg=api_msg or "余额不足，无法调用（402）")
        elif status == 429:
            out["status_key"] = "ratelimit"
        elif status and status >= 500:
            out["status_key"] = "server"
        else:
            out.update(status_key="error", apiMsg=api_msg or f"HTTP {status}")
        out["infos"] = []
        return out
    return {"status_key": "network", "infos": [], "apiMsg": last or "请求失败"}


def probe_models(key: str, timeout: float) -> dict:
    status, data, err = http_json(MODELS_URL, key, timeout)
    if err is not None and status is None:
        return {"ok": False, "error": err}
    if status != 200:
        msg = ((data or {}).get("error") or {}).get("message") or f"HTTP {status}"
        return {"ok": False, "error": msg}
    models = [m.get("id") for m in (data or {}).get("data", []) if m.get("id")]
    return {"ok": True, "models": models}


def probe_chat(key: str, model: str, timeout: float) -> dict:
    status, data, err = http_json(
        CHAT_URL, key, timeout, method="POST",
        body={"model": model, "messages": [{"role": "user", "content": "ping"}],
              "max_tokens": 1, "stream": False})
    if err is not None and status is None:
        return {"ok": False, "error": err}
    if status != 200:
        msg = ((data or {}).get("error") or {}).get("message") or f"HTTP {status}"
        return {"ok": False, "error": msg}
    return {"ok": True}


def check_one(item: dict, args) -> dict:
    t0 = time.time()
    row = dict(item)
    row.update(fetch_balance(item["key"], args.timeout, args.retries))
    row["ms"] = int((time.time() - t0) * 1000)
    if args.models or args.chat:
        row["live"] = probe_models(item["key"], args.timeout)
        if args.chat and row["live"]["ok"]:
            ch = probe_chat(item["key"], args.chat_model, args.timeout)
            row["live"]["chatOk"] = ch["ok"]
            if not ch["ok"]:
                row["live"]["ok"] = False
                row["live"]["error"] = ch.get("error")
    return row


def fetch_usage(token: str, month: str, timeout: float) -> dict:
    year, mon = month.split("-")
    out: dict = {"month": month}
    for kind in ("amount", "cost"):
        status, data, err = http_json(
            f"{PLATFORM_BASE}/{kind}?month={int(mon)}&year={int(year)}", token, timeout,
            extra={"x-app-version": "1.0.0", "Accept": "*/*"})
        if err is not None and status is None:
            return {"error": err}
        code = (data or {}).get("code")
        if code != 0:
            return {"error": (data or {}).get("msg") or f"code={code}", "code": code}
        out[kind] = (data or {}).get("data", {}).get("biz_data")
    return out


def summarize_usage(raw: dict) -> dict:
    biz_a = raw.get("amount") or {}
    biz_c = raw.get("cost")
    if isinstance(biz_c, list):
        biz_c = biz_c[0] if biz_c else {}
    biz_c = biz_c or {}
    cost_by_model = {m.get("model"): sum(float(e.get("amount") or 0)
                                         for e in m.get("usage", []) if e.get("type") != "REQUEST")
                     for m in biz_c.get("total", [])}
    totals = {"requests": 0, "tokens": 0, "hit": 0, "miss": 0, "resp": 0, "cost": 0.0}
    models = []
    for m in biz_a.get("total", []):
        b = {"requests": 0, "tokens": 0, "hit": 0, "miss": 0, "resp": 0}
        for e in m.get("usage", []):
            amt = int(float(e.get("amount") or 0))
            t = e.get("type")
            if t == "REQUEST":
                b["requests"] = amt
            elif t == "PROMPT_CACHE_HIT_TOKEN":
                b["hit"] = amt; b["tokens"] += amt
            elif t == "PROMPT_CACHE_MISS_TOKEN":
                b["miss"] = amt; b["tokens"] += amt
            elif t == "RESPONSE_TOKEN":
                b["resp"] = amt; b["tokens"] += amt
            else:
                b["tokens"] += amt
        b["model"] = m.get("model")
        b["cost"] = cost_by_model.get(m.get("model"), 0.0)
        models.append(b)
    for k in ("requests", "tokens", "hit", "miss", "resp"):
        totals[k] = sum(m[k] for m in models)
    totals["cost"] = sum(m["cost"] for m in models)
    return {"month": raw.get("month"), "total": totals, "models": models}


# --------------------------------------------------------------------------
# 输出
# --------------------------------------------------------------------------
def dwidth(s: str) -> int:
    """按终端显示宽度算（中日韩全角字符占 2 列）"""
    w = 0
    for ch in str(s):
        w += 2 if (0x1100 <= ord(ch) <= 0x115F or 0x2E80 <= ord(ch) <= 0xA4CF
                   or 0xAC00 <= ord(ch) <= 0xD7A3 or 0xF900 <= ord(ch) <= 0xFAFF
                   or 0xFE30 <= ord(ch) <= 0xFE6F or 0xFF00 <= ord(ch) <= 0xFF60
                   or 0xFFE0 <= ord(ch) <= 0xFFE6 or 0x1F300 <= ord(ch) <= 0x1F9FF) else 1
    return w


def pad(s: str, width: int) -> str:
    s = str(s)
    return s + " " * max(0, width - dwidth(s))


def mask(key: str) -> str:
    return key if len(key) <= 12 else key[:7] + "…" + key[-4:]


def trunc(s: str, maxw: int) -> str:
    """按显示宽度截断，超长加省略号（避免长错误信息把表格撑爆）"""
    s = str(s)
    if dwidth(s) <= maxw:
        return s
    out, w = "", 0
    for ch in s:
        cw = 2 if dwidth(ch) == 2 else 1
        if w + cw > maxw - 1:
            break
        out += ch
        w += cw
    return out + "…"


def balance_str(row: dict) -> str:
    infos = row.get("infos") or []
    if not infos:
        return trunc(row.get("apiMsg") or "—", 38)
    return " / ".join(f"{b['currency']} {b['total']}" for b in infos)


def balance_nums(row: dict) -> list[float]:
    return [float(b["total"]) for b in (row.get("infos") or []) if b.get("total") is not None]


def print_table(rows: list[dict], args) -> None:
    headers = ["名称", "Key", "状态", "余额", "赠送/充值", "耗时"]
    if args.models or args.chat:
        headers.append("实测")
    body = []
    for r in rows:
        st = r.get("status_key", "error")
        mark, colr = STATUS_MARK.get(st, ("?", RED))
        bal = balance_str(r)
        nums = balance_nums(r)
        if args.threshold > 0 and nums and min(nums) < args.threshold:
            bal = c(bal, RED) + c(" ←低于阈值", RED)
        gift = " / ".join(f"{b.get('granted')}|{b.get('topped')}" for b in (r.get("infos") or [])) or "—"
        row = [r.get("name", ""), r["key"] if args.show_key else mask(r["key"]),
               c(f"{mark} {STATUS_TEXT.get(st, st)}", colr),
               bal, gift, f"{r.get('ms', 0)}ms"]
        if args.models or args.chat:
            live = r.get("live")
            if live is None:
                row.append("—")
            elif live["ok"]:
                n = len(live.get("models") or [])
                row.append(c(f"✔ {n} 模型" + (" + 真实调用" if live.get("chatOk") else ""), GREEN))
            else:
                row.append(c("✘ " + trunc(live.get("error"), 26), RED))
        body.append(row)

    widths = [max(dwidth(h), *(dwidth(r[i]) for r in body)) if body else dwidth(h)
              for i, h in enumerate(headers)]
    # 带颜色的单元格宽度会失真，这里用去色后的宽度补齐
    ansi = re.compile(r"\033\[[0-9;]*m")
    def plain(s): return ansi.sub("", str(s))
    widths = [max([dwidth(h)] + [dwidth(plain(r[i])) for r in body]) for i, h in enumerate(headers)]

    print(c("  ".join(pad(h, widths[i]) for i, h in enumerate(headers)), BOLD))
    print(c("  ".join("─" * widths[i] for i in range(len(headers))), DIM))
    for r in body:
        cells = []
        for i, cell in enumerate(r):
            cells.append(pad(cell, widths[i] + dwidth(str(cell)) - dwidth(plain(cell))))
        print("  ".join(cells).rstrip())

    n_ok = sum(1 for r in rows if r.get("status_key") == "ok")
    n_low = sum(1 for r in rows if r.get("status_key") == "low")
    n_bad = len(rows) - n_ok - n_low
    print()
    print(f"  共 {len(rows)} 个：{c(str(n_ok)+' 可用', GREEN)} · "
          f"{c(str(n_low)+' 余额不足', YELLOW)} · {c(str(n_bad)+' 异常', RED)}")
    currencies: dict[str, float] = {}
    for r in rows:
        for b in (r.get("infos") or []):
            try:
                currencies[b["currency"]] = currencies.get(b["currency"], 0.0) + float(b["total"])
            except (TypeError, ValueError):
                pass
    if currencies:
        print("  合计余额：" + " / ".join(f"{k} {v:.2f}" for k, v in currencies.items()))


def rows_to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["名称", "Key", "状态", "is_available", "余额", "赠送", "充值",
                "实测", "可用模型数", "实测错误", "耗时ms", "错误", "request_id"])
    for r in (rows if isinstance(rows, list) else []):
        infos = r.get("infos") or []
        live = r.get("live") or {}
        w.writerow([
            r.get("name", ""), r["key"], STATUS_TEXT.get(r.get("status_key"), ""),
            r.get("isAvailable", ""),
            " / ".join(f"{b['currency']} {b['total']}" for b in infos),
            " / ".join(str(b.get("granted")) for b in infos),
            " / ".join(str(b.get("topped")) for b in infos),
            ("通过" if live.get("ok") else "不通过") if live else "",
            len(live.get("models") or []) if live else "",
            live.get("error", "") if live else "",
            r.get("ms", ""), r.get("apiMsg", "") or "", r.get("requestId", "") or "",
        ])
    return "\ufeff" + buf.getvalue()


def rows_to_json(rows: list[dict], args) -> str:
    payload = {
        "tool": "deepseek-key-panel-cli", "version": VERSION,
        "queriedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "threshold": args.threshold,
        "summary": {
            "total": len(rows),
            "ok": sum(1 for r in rows if r.get("status_key") == "ok"),
            "low": sum(1 for r in rows if r.get("status_key") == "low"),
            "failed": sum(1 for r in rows if r.get("status_key") not in ("ok", "low")),
        },
        "keys": [{
            "name": r.get("name"), "key": r["key"], "status": r.get("status_key"),
            "isAvailable": r.get("isAvailable"), "balances": r.get("infos") or [],
            "live": r.get("live"), "latencyMs": r.get("ms"),
            "error": r.get("apiMsg"), "requestId": r.get("requestId"),
        } for r in rows],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def rows_to_txt(rows: list[dict]) -> str:
    return "\n".join(r["key"] for r in rows) + ("\n" if rows else "")


# --------------------------------------------------------------------------
def main(argv=None) -> int:
    global USE_COLOR
    p = argparse.ArgumentParser(
        prog="cli.py", description="DeepSeek Key 批量查询（余额 / 可用性 / 官方用量）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例见文件头部注释，或 python cli.py -h")

    src = p.add_argument_group("输入（都不给则读 keys.txt）")
    src.add_argument("-f", "--file", action="append", default=[], metavar="PATH",
                     help="从文件读 Key，可多次；支持 txt/csv/json")
    src.add_argument("-k", "--key", action="append", default=[], metavar="SK-XXX",
                     help="直接指定 Key，可多次")
    src.add_argument("--stdin", action="store_true", help="从标准输入读")

    q = p.add_argument_group("查询")
    q.add_argument("-c", "--concurrency", type=int, default=5, help="并发数（默认 5）")
    q.add_argument("-t", "--timeout", type=float, default=20, help="单次超时秒数（默认 20）")
    q.add_argument("--retries", type=int, default=1, help="失败重试次数（默认 1）")
    q.add_argument("--models", action="store_true", help="额外做 GET /models 可用性验证（不花 token）")
    q.add_argument("--chat", action="store_true", help="额外真实调用一次（会产生费用）")
    q.add_argument("--chat-model", default="deepseek-chat", help="真实调用用的模型")
    q.add_argument("--threshold", type=float, default=0,
                   help="余额低于此值时标红并以退出码 3 结束（0 = 关闭）")

    o = p.add_argument_group("输出")
    o.add_argument("--format", choices=["table", "json", "csv", "txt"], default="table")
    o.add_argument("--out", metavar="PATH", help="写入文件（默认输出到标准输出）")
    o.add_argument("--only", choices=["ok", "low", "failed", "all"], default="all",
                   help="只输出某一类结果（txt/json/csv 格式下最有用）")
    o.add_argument("--quiet", action="store_true", help="不打印进度信息")
    o.add_argument("--no-color", action="store_true", help="关闭颜色")
    o.add_argument("--show-key", action="store_true", help="表格里显示完整 Key（默认打码）")

    u = p.add_argument_group("官方用量（可选，Python 直连即可）")
    u.add_argument("--usage-token", metavar="TOKEN", help="DeepSeek 平台网页登录 Token")
    u.add_argument("--usage-month", metavar="YYYY-MM", help="要查询的月份，如 2026-10")

    p.add_argument("-V", "--version", action="version", version=f"cli.py {VERSION}")
    args = p.parse_args(argv)

    USE_COLOR = (not args.no_color) and sys.stdout.isatty() and _enable_ansi()

    # 官方用量是个独立动作
    if args.usage_token or args.usage_month:
        if not (args.usage_token and args.usage_month):
            log("[错误] --usage-token 和 --usage-month 要一起给")
            return EXIT_USAGE
        if not re.fullmatch(r"\d{4}-\d{2}", args.usage_month):
            log("[错误] --usage-month 格式应为 YYYY-MM，例如 2026-10")
            return EXIT_USAGE
        raw = fetch_usage(args.usage_token, args.usage_month, args.timeout)
        if "error" in raw:
            log(f"[错误] 拉取官方用量失败：{raw['error']}")
            return EXIT_FAIL
        summary = summarize_usage(raw)
        if args.format == "json":
            text = json.dumps(summary, ensure_ascii=False, indent=2)
        else:
            t = summary["total"]
            lines = [f"官方用量 · {summary['month']}",
                     f"  请求数 {t['requests']:,}   总 Token {t['tokens']:,}   费用 ¥{t['cost']:.2f}",
                     f"  缓存命中 {t['hit']:,}   未命中 {t['miss']:,}   输出 {t['resp']:,}", ""]
            lines.append(f"  {'模型':<26}{'请求':>8}{'总Token':>14}{'费用':>10}")
            for m in summary["models"]:
                lines.append(f"  {m['model']:<26}{m['requests']:>8,}{m['tokens']:>14,}{m['cost']:>10.2f}")
            text = "\n".join(lines)
        if args.out:
            with io.open(args.out, "w", encoding="utf-8") as fh:
                fh.write(text)
            log(f"[完成] 已写入 {args.out}")
        else:
            print(text)
        return EXIT_OK

    # 收集 Key
    items: list[dict] = []
    for path in args.file:
        items.extend(read_flexible(path))
    for k in args.key:
        items.extend(parse_keys(k))
    if args.stdin:
        items.extend(parse_keys(sys.stdin.read()))
    if not items:
        default = "keys.txt"
        if os.path.isfile(default):
            items = read_flexible(default)
        elif not args.file and not args.key:
            log("[错误] 没有输入。用 -f 文件 / -k Key / --stdin，或把 Key 放进 keys.txt")
            return EXIT_USAGE

    # 去重（保留第一次出现的名字）
    seen: set[str] = set()
    uniq: list[dict] = []
    for it in items:
        if it["key"] in seen:
            continue
        seen.add(it["key"])
        uniq.append(it)
    if not uniq:
        log("[错误] 没解析出任何 Key")
        return EXIT_USAGE

    # 自动编号统一在去重之后分配，避免多个输入源各编各的
    auto_n = 0
    for it in uniq:
        if it.get("auto") or not it.get("name"):
            auto_n += 1
            it["name"] = f"Key-{auto_n}"

    if not args.quiet:
        log(f"[信息] {len(uniq)} 个 Key，并发 {args.concurrency}，超时 {args.timeout}s"
            + ("，含 /models 验证" if args.models else "")
            + ("，含真实调用" if args.chat else ""))

    rows: list[dict] = []
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = {pool.submit(check_one, it, args): it for it in uniq}
        done = 0
        for fut in concurrent.futures.as_completed(futures):
            it = futures[fut]
            try:
                rows.append(fut.result())
            except Exception as exc:  # noqa: BLE001
                rows.append({**it, "status_key": "error", "infos": [], "apiMsg": str(exc), "ms": 0})
            done += 1
            if not args.quiet:
                log(f"\r[进度] {done}/{len(uniq)}…" + " " * 12)
    if not args.quiet:
        log("")

    order = {it["key"]: i for i, it in enumerate(uniq)}
    rows.sort(key=lambda r: order.get(r["key"], 0))

    # 退出码看的是「实际查询到的全部结果」，不受 --only 的输出过滤影响
    all_rows = list(rows)

    if args.only != "all":
        want = {"ok": ("ok",), "low": ("low",),
                "failed": ("invalid", "ratelimit", "server", "network", "error")}[args.only]
        rows = [r for r in rows if r.get("status_key") in want]

    if args.format == "json":
        text = rows_to_json(rows, args)
    elif args.format == "csv":
        text = rows_to_csv(rows)
    elif args.format == "txt":
        text = rows_to_txt(rows)
    else:
        text = None

    if args.out:
        with io.open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text if text is not None else rows_to_csv(rows))
        if not args.quiet:
            log(f"[完成] 已写入 {args.out}（{len(rows)} 行，{time.time()-t0:.1f}s）")
    elif text is not None:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
    else:
        print_table(rows, args)

    all_rows_out = all_rows
    failed = sum(1 for r in all_rows_out if r.get("status_key") not in ("ok", "low"))
    below = sum(1 for r in all_rows_out
                if args.threshold > 0 and balance_nums(r) and min(balance_nums(r)) < args.threshold)
    if failed:
        return EXIT_FAIL
    if below:
        return EXIT_THRESHOLD
    return EXIT_OK


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        log("\n[中断]")
        raise SystemExit(130)
