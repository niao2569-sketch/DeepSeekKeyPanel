"""校验 docs/intro.md 的结构：About 字段长度、中英段落是否成对。"""
import io
import re

t = io.open("docs/intro.md", encoding="utf-8").read()
F = chr(96) * 3

blocks = re.findall(re.escape(F) + r"text\r?\n(.*?)" + re.escape(F), t, re.S)
about = [b.strip() for b in blocks if "导入 DeepSeek" in b]
if about:
    a = about[0]
    print(f"GitHub About 长度: {len(a)} / 350 ->", "OK" if len(a) <= 350 else "超出！")
    print("-" * 56)
    print(a)
    print("-" * 56)
else:
    print("!! 没找到 About 段")

print()
zh, en = t.count("**中文**"), t.count("**English**")
print(f"中文段 {zh} 个 / 英文段 {en} 个 ->", "成对" if zh == en else "!! 数量不一致")
print("小节数:", len(re.findall(r"^## \d+\.", t, re.M)))
print("文件字符数:", len(t))

# 关键词覆盖检查：新版功能有没有写进去
must = ["DPAPI", "dskp.ini", "中英双语", "可用性实测", "MIT"]
missing = [k for k in must if k not in t]
print("关键词覆盖:", "全部命中" if not missing else f"缺少 {missing}")
