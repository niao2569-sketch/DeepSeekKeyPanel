"""交叉检查：JS 里引用的每个 #id / getElementById 是否都真实存在于 HTML 中。
   这类拼写错误在浏览器里只会静默失效，靠肉眼很难发现。"""
import io, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PANEL = os.path.join(ROOT, "src", "deepseek_key_panel", "web", "index.html")
html = io.open(PANEL, encoding="utf-8").read()

script = max(re.findall(r"<script>(.*?)</script>", html, re.S), key=len)
markup = html.replace(script, "")

declared = set(re.findall(r'\bid\s*=\s*"([^"]+)"', markup))
# 运行时由 innerHTML 动态插入的元素，id 也写在 JS 的模板字符串里
declared_dynamic = set(re.findall(r'\bid\s*=\s*"([A-Za-z0-9_\-]+)"', script))
referenced = set(re.findall(r'\$\("#([A-Za-z0-9_\-]+)"\)', script))
referenced |= set(re.findall(r'getElementById\(\s*["\']([A-Za-z0-9_\-]+)["\']', script))

# 动态拼接的 id 模板（形如 #tab-xxx）单独说明
dynamic_ok = {"tab-keys", "tab-usage", "tab-settings"}

missing = sorted(r for r in referenced
                 if r not in declared and r not in declared_dynamic and r not in dynamic_ok)
unused = sorted(d for d in declared if d not in referenced
                and not d.startswith("tab-")
                and d not in ("dskp-theme",))

print("HTML 中静态声明的 id    :", len(declared))
print("JS 模板里动态生成的 id  :", len(declared_dynamic), "->", sorted(declared_dynamic))
print("JS 中引用的 id          :", len(referenced))
print()
if missing:
    print("!! 引用了不存在的 id（会静默失效）:")
    for m in missing:
        print("   #" + m)
else:
    print("OK  所有 JS 引用的 id 都能找到（静态标记或 JS 模板生成）")

print()
if unused:
    print("提示：声明了但 JS 未直接引用的 id（可能只用于 CSS/锚点，正常）:")
    for u in unused:
        print("   #" + u)

# 再检查一遍所有 bind("#xxx") 的目标
binds = re.findall(r'bind\("#([A-Za-z0-9_\-]+)"', script)
bad_binds = [b for b in binds if b not in declared]
print()
print("bind() 绑定目标:", len(binds), "个")
if bad_binds:
    print("!! 绑定了不存在的元素:", bad_binds)
    sys.exit(1)
print("OK  所有 bind() 目标都存在")

# 检查 data-copy 指向的锚点
copies = re.findall(r'data-copy="#([A-Za-z0-9_\-]+)"', markup)
bad_copy = [c for c in copies if c not in declared]
print()
print("data-copy 目标:", copies)
if bad_copy:
    print("!! data-copy 指向不存在的 id:", bad_copy)
    sys.exit(1)
print("OK  data-copy 目标都存在")
sys.exit(1 if missing else 0)
