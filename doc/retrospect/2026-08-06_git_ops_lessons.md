# Git 操作教训（2026-08-06 本地留档）

> 日期: 2026-08-06
> 场景: N97→VM 同步提交时执行 `git reset --hard` 误伤未提交修改
> 状态: 本地留档，未提交 git

---

## 经过

N97 提交底盘修复（ff205c9）后同步 VM：因本地 HEAD 与远端历史分叉
（内容相同、哈希不同），执行 `git reset --hard origin/main`。
执行前未检查 `git status`，**工作区 `doc/standards.md` 有未提交的规则修改，
被 reset 直接冲掉**。最终靠 Obsidian 镜像副本（8-06 12:50 的更新版本）
恢复了丢失内容。

## 教训

### 1. `git reset --hard` 前必须先 stash（或确认工作区干净）

- 执行任何 `reset --hard` / `checkout --` 前，先 `git status` 确认无未提交修改
- 有修改时：`git stash` → reset → `git stash pop`
- 本次靠 Obsidian 镜像侥幸恢复，镜像没有的话修改就真丢了

### 2. Co-Authored-By 默认不加（standards.md 新规则，2026-08-06）

- AI 辅助的提交**默认不加** `Co-Authored-By` 标记
- 仅在显式要求时添加（如"本次提交带 Co-Authored-By"）
- 原因：该标记会把 AI 计入 GitHub 贡献者列表，署名与否应由提交者本人决定
- 已对 ff205c9 执行 amend 去掉（force push 改写）

## 关联

- standards.md 的规则修改仍在 VM 工作区未提交（` M doc/standards.md`），待提交
