#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
国际化校验
==========

三件事：

1. ``I18N.zh`` 和 ``I18N.en`` 的键集合必须完全一致 —— 否则切到英文会露出中文键名
2. ``ZH2EN`` 里的每个中文键都必须真的出现在面板标记里 —— 防止改了文案后映射表悄悄失效
3. 面板标记里所有中文文本节点都应该在 ``ZH2EN`` 里 —— 也就是"有没有漏翻"

第 3 项允许通过 ``_ALLOW_MISSING`` 显式豁免，豁免列表本身也会被检查是否过期。
"""

from __future__ import annotations

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PANEL = os.path.join(ROOT, "src", "deepseek_key_panel", "web", "index.html")

# 不打算翻译的（品牌名、代码示例、纯符号、语言选择器本身）
_ALLOW_MISSING = {
    "中文", "DeepSeek", "API Key", "Key", "CSV", "JSON", "Token", "Topics",
    "sk-abc…wxyz", "AES-GCM-256", "PBKDF2-SHA256", "sessionStorage",
    "api.deepseek.com", "platform.deepseek.com", "启动面板.cmd",
    "python run_panel.py", "userToken", "deepseek-chat", "GET /models",
    '[{"name":"主力","key":"sk-..."}]',   # 文档里的 JSON 示例，属于数据不是文案
}


def load_panel():
    html = io.open(PANEL, encoding="utf-8").read()
    script = max(re.findall(r"<script>(.*?)</script>", html, re.S), key=len)
    markup = html.replace(script, "")
    # 样式和注释里也有中文，但它们不是待翻译的界面文本
    markup = re.sub(r"<style>.*?</style>", " ", markup, flags=re.S)
    markup = re.sub(r"<!--.*?-->", " ", markup, flags=re.S)
    return html, script, markup


def parse_dict(script: str, name: str) -> dict:
    """从 JS 里抠出名为 name 的对象字面量的键值对。

    兼容两种写法：``const X = { ... }`` 和 ``X: { ... }``。
    """
    m = re.search(r"\b" + name + r"\s*[:=]\s*\{", script)
    if not m:
        return {}
    i = m.end() - 1
    depth, j = 0, i
    while j < len(script):
        if script[j] == "{":
            depth += 1
        elif script[j] == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    body = script[i + 1:j]
    out = {}
    for km in re.finditer(r'"((?:[^"\\]|\\.)*)"\s*:\s*"((?:[^"\\]|\\.)*)"', body):
        out[km.group(1)] = km.group(2)
    return out


def parse_zh2en(script: str) -> dict:
    return parse_dict(script, "ZH2EN")


def is_cjk(s: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", s))


def main() -> int:
    _, script, markup = load_panel()
    zh = parse_dict(script, "zh")
    en = parse_dict(script, "en")
    z2e = parse_zh2en(script)

    problems = []
    print(f"I18N.zh 词条 : {len(zh)}")
    print(f"I18N.en 词条 : {len(en)}")
    print(f"ZH2EN  映射  : {len(z2e)}")
    print()

    # ---- 1. 键一致性 ----
    only_zh = sorted(set(zh) - set(en))
    only_en = sorted(set(en) - set(zh))
    if only_zh:
        problems.append(("zh 有但 en 缺失", only_zh))
    if only_en:
        problems.append(("en 有但 zh 缺失", only_en))
    if not only_zh and not only_en:
        print("  ok   zh / en 键集合一致")

    # ---- 2. ZH2EN 的键必须真的在面板里（静态标记或 JS 动态生成的 HTML 都算） ----
    stale = [k for k in z2e if k not in markup and k not in script]
    if stale:
        problems.append(("ZH2EN 里的键已不在面板中（改了文案没同步）", stale))
    else:
        print("  ok   ZH2EN 的每个键都能在面板里找到")

    # ---- 3. 标记里的中文是否都覆盖了 ----
    text = re.sub(r"<[^>]+>", "\n", markup)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    candidates = []
    for line in text.splitlines():
        s = line.strip()
        if not s or not is_cjk(s):
            continue
        # <code> 里的片段和纯符号行跳过
        if s in _ALLOW_MISSING or s in z2e:
            continue
        if s.startswith(("/*", "*", "//")):
            continue
        candidates.append(s)
    # 去重保序
    seen, missing = set(), []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            missing.append(c)
    if missing:
        problems.append((f"标记里有 {len(missing)} 处中文没有英文映射", missing))
    else:
        print("  ok   标记里的中文全部有英文映射")

    # ---- 4. 语言开关本身必须是可见的、两个选项都在 ----
    # 曾经踩过的坑：语言开关的按钮用了 data-lang，而 applyLangToDom 会把
    # 「非当前语言」的 [data-lang] 元素 display:none —— 结果中文模式下
    # EN 按钮被自己人藏了起来。
    seg = re.search(r'<div class="seg" id="lang-seg".*?</div>', markup, re.S)
    if not seg:
        problems.append(("找不到语言开关 #lang-seg", []))
    else:
        block = seg.group(0)
        opts = re.findall(r'data-setlang="([a-z]{2})"', block)
        if sorted(opts) != ["en", "zh"]:
            problems.append((f"语言开关的选项不对（应为 zh+en，实际 {opts}）", []))
        else:
            print("  ok   语言开关同时有 zh / en 两个选项")
        if "data-lang=" in block:
            problems.append(("语言开关用了 data-lang（会被语言区块逻辑隐藏，应改用 data-setlang）", []))
    hiding = re.findall(r"\[(data-only-lang)\]", script)
    if "data-lang" in re.findall(r'\$\$\("\[([a-z\-]+)\]"\)', script):
        problems.append(("applyLangToDom 里仍在用 [data-lang] 选择器，会和语言开关撞名", []))

    # ---- 5. 豁免列表是否过期 ----
    fresh_exempt = [k for k in _ALLOW_MISSING if k in markup]
    unused_exempt = sorted(_ALLOW_MISSING - set(fresh_exempt))
    if unused_exempt:
        print(f"  提示 _ALLOW_MISSING 里有 {len(unused_exempt)} 项已不在标记中：{unused_exempt[:6]}")

    print()
    if problems:
        for title, items in problems:
            print(f"FAIL  {title}")
            limit = len(items) if os.environ.get("I18N_ALL") else 25
            for it in items[:limit]:
                print(f"        {it}")
            if len(items) > limit:
                print(f"        …还有 {len(items)-limit} 项（I18N_ALL=1 可看全部）")
        return 1
    print("i18n 校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
