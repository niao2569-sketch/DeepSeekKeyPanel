import io, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PANEL = os.path.join(ROOT, "src", "deepseek_key_panel", "web", "index.html")
html = io.open(PANEL, encoding="utf-8").read()

# 提取最后一个 <script> ... </script>
blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
print("script blocks:", len(blocks))
js = max(blocks, key=len)
io.open(os.path.join(HERE, "_panel_check.js"), "w", encoding="utf-8").write(js)

# 粗查结构
checks = {
    "html 结尾完整": html.rstrip().endswith("</html>"),
    # 只看真正会发起网络加载的标签；<a href> 是超链接，不算外部依赖
    "无外部资源加载": not re.search(
        r"<(script|link|img|iframe|video|audio|source|embed|object)\b[^>]*\b(src|href)\s*=\s*[\"']https?://",
        html, re.I),
    "有 canvas 余额图": 'id="chart-balance"' in html,
    "有用量输出容器": 'id="usage-out"' in html,
    "balance 接口地址": "https://api.deepseek.com/user/balance" in js,
    "models 接口地址": "https://api.deepseek.com/models" in js,
    "usage amount 地址": "https://platform.deepseek.com/api/v0/usage" in js,
    "中转 proxy 拼装": "/proxy?url=" in js,
    "桌面模式退出按钮": 'id="btn-quit"' in html,
    "关窗心跳 /bye": 'sendBeacon("/bye")' in js,
}
for k, v in checks.items():
    print(("  OK  " if v else "  FAIL") + "  " + k)

# 括号配对粗检
for a, b, name in (("{", "}", "花括号"), ("(", ")", "圆括号"), ("[", "]", "方括号")):
    print(f"  {name}: {js.count(a)} 开 / {js.count(b)} 闭  {'OK' if js.count(a)==js.count(b) else 'MISMATCH'}")
print("js bytes:", len(js))
