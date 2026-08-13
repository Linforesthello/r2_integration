# Obsidian 镜像同步规范

> 范围：工作区文档 ↔ Obsidian 库镜像的同步规则与处理流程（全局适用）。
> 关联：[standards.md](standards.md)（文档规范）、[ros2-ops.md](ros2-ops.md)（ROS/ROS2 操作规范）、[obsidian-tags.md](obsidian-tags.md)（标签体系）。

## 1. 镜像关系

- 权威源：`~/Lin_workspace/r2_integration/doc/`（只在此处修改）
- 镜像：`~/Lin_note/Open-Notes-Library/01-开发日志/✨总/当前项目文档/R2_Integration/doc/`
- 镜像 = 权威源内容的普通文件复制（非链接）；Obsidian 侧可做标签增强（标签只加镜像侧）

## 2. 同步流程

1. 先 `diff -rq` 对比权威源 vs 镜像，向用户展示差异（镜像侧可能有独有内容）
2. 确认无独有内容后，单向 `cp` 覆盖 + `diff -q`/`diff -rq` 验证 0 差异

## 3. 误覆盖恢复

- Obsidian 库本身是 git 仓库：`git -C ~/Lin_note/Open-Notes-Library checkout -- <路径>` 可恢复
- 教训（2026-08-13）：未先对比就 cp 覆盖被用户叫停，靠库内 git 恢复

## 4. 镜像独有文件处理（先调查，再删/迁）

独有 ≠ 真独有，处理前按顺序调查（2026-08-13 教训）：

1. **是否重命名迁移**：`diff` 对比权威源其他位置同名/相似文件
   （例：镜像 `g354-completion.md` 与 `g354_driver/doc/completion-report.md` diff 完全一致 = 重命名迁移）
2. **是否过时旧快照**：被权威源更新版本取代
   （例：镜像 `ekf-config.yaml` yaw=false 过时，被 `r2_bringup/config/ekf.yaml` yaw=true 取代）
3. **是否真独有**：权威源无对应内容 → **迁回权威源**（retrospect 用日期前缀命名）后再删镜像，知识不丢、只落唯一事实来源

**案例（2026-08-13）**：4 个独有文件 → 3 删（2 重命名迁移 + 1 过时快照）+ 1 迁回
（`vlp16_switch_network.md` → `retrospect/2026-08-02_vlp16_switch_network.md`，含 NVRAM 重启清 ARP 经验）

## 5. 图片迁移

- Obsidian 嵌入 `![[Pasted image xxx.png]]`（库附件引用）→ 权威源用**图片文件**（kebab-case 名，放文档同目录）+ 标准 markdown 相对路径 `![](file.png)`
- 原附件保留在 Obsidian `Attachments/` 不动

## 6. 现状（2026-08-13）

- 镜像与权威源 `diff -rq` = **0 差异、0 独有**，已完全对齐
- 旧"已知 Obsidian 侧独有文件"清单（`ekf-config.yaml`、`g354-completion.md`、`g354-debug-log.md`、`vlp16_switch_network.md` 等）已全部清零

---

## 相关

- 文档规范：[standards.md](standards.md) ｜ Obsidian 标签：[obsidian-tags.md](obsidian-tags.md) ｜ ROS 操作：[ros2-ops.md](ros2-ops.md)
