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
    - 代码围栏/行内代码内的 ](...) 视为示例写法跳过（2026-09-16 加）——规范文档（如 standards §1.5）
      用 `[文本](path/to/file.md)` 做示范时不算坏链；跳过的处数在统计行单独报出，便于核对
"""
import os, re, sys

REPO = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
DOC = os.path.join(REPO, "doc")
SKIP = ("raw_data",)  # 原始留档内部不强制校验
EXTRAS = ("README.md", "CLAUDE.md")  # doc 树之外的补充扫描文件（存在才扫）

LINK_RE = re.compile(r"\]\(([^()\s<>]+)\)")
FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[^\n]*$", re.S | re.M)
INLINE_RE = re.compile(r"`[^`\n]+`")
missing, checked, skipped = [], 0, 0

def mask_code(text):
    """把代码围栏与行内代码替换为等长空白（保留换行）：其中的 ](...) 是示例，非真实链接。"""
    blank = lambda m: re.sub(r"[^\n]", " ", m.group(0))
    return INLINE_RE.sub(blank, FENCE_RE.sub(blank, text))

def check(path):
    global checked, skipped
    with open(path, encoding="utf-8") as f:
        content = f.read()
    masked = mask_code(content)
    skipped += len(LINK_RE.findall(content)) - len(LINK_RE.findall(masked))
    d = os.path.dirname(path)
    for m in LINK_RE.finditer(masked):
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

print(f"共校验 {checked} 条本地链接（另跳过代码跨度内示例写法 {skipped} 处）")
if missing:
    print(f"缺失 {len(missing)} 条：")
    for f, t, ap in missing:
        print(f"  {f}: {t}  ->  {ap}")
    sys.exit(1)
print("全部存在 ✓")
