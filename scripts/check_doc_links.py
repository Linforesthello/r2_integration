#!/usr/bin/env python3
"""链接完整性校验器：遍历仓库 doc 树 + 根 README + CLAUDE.md，校验所有本地相对链接目标存在。

用法:
    python3 scripts/check_doc_links.py [repo路径]   # 默认扫描 <repo>/doc/**, <repo>/README.md, <repo>/CLAUDE.md

定位:
    文档工程验收闸门（见 doc/doc-engineering.md §四）。移动/重写文档后跑一遍，
    缺失清单做三桶分类: 格式示例 / 既有坏链 / 本次改动致坏(必须清零)。

规则:
    - 跳过 raw_data/（原始留档内部不强制校验）
    - 目标可为 .md/.png/.patch/.txt/目录等; 不存在即报（含 repo 外越界路径——归入"既有坏链"桶人工分类）
    - 纯外部(http/mailto/锚点)跳过
"""
import os, re, sys

REPO = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
DOC = os.path.join(REPO, "doc")
SKIP = ("raw_data",)  # 原始留档内部不强制校验
EXTRAS = ("README.md", "CLAUDE.md")  # doc 树之外的补充扫描文件（存在才扫）

LINK_RE = re.compile(r"\]\(([^()\s<>]+)\)")
missing, checked = [], 0

def check(path):
    global checked
    with open(path, encoding="utf-8") as f:
        content = f.read()
    d = os.path.dirname(path)
    for m in LINK_RE.finditer(content):
        t = m.group(1)
        tp = t.split("#", 1)[0]
        if not tp or tp.startswith(("http://", "https://", "mailto:", "ftp://", "//", "tel:")):
            continue
        ap = os.path.abspath(os.path.normpath(os.path.join(d, tp)))
        checked += 1
        if not os.path.exists(ap):
            missing.append((os.path.relpath(path, REPO), t, ap))

if os.path.isdir(DOC):
    for root, dirs, files in os.walk(DOC):
        dirs[:] = [x for x in dirs if x not in SKIP]
        for fn in files:
            if fn.lower().endswith(".md"):
                check(os.path.join(root, fn))
else:
    print(f"未找到 doc 目录: {DOC}"); sys.exit(2)
for extra in EXTRAS:
    p = os.path.join(REPO, extra)
    if os.path.exists(p):
        check(p)

print(f"共校验 {checked} 条本地链接")
if missing:
    print(f"缺失 {len(missing)} 条：")
    for f, t, ap in missing:
        print(f"  {f}: {t}  ->  {ap}")
    sys.exit(1)
print("全部存在 ✓")
