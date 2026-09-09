# 低物链日期实证修正 + 坏链接批量修复 · 双仓闭环复盘

> 日期：2026-09-08 ~ 2026-09-09 ｜ 任务：① 09-07/09-08 日期归属实证与全批修正 ② doc 全量链接校验与 29 条修复
> 状态：✅ 双仓已闭环（r2 `d6055c5` / `1455d4e` ↔ Obsidian `f2dfc17` / `fb516f1`，commit body 互引 hash）
> 关联互指：[09-03 文档工程复盘](2026-09-03_doc_engineering.md)（规则化源头）｜[obsidian-sync.md](../obsidian-sync.md)（镜像规范，本次追加 §2.3 / §4.0）｜[doc-engineering.md](../doc-engineering.md)（§四 追加同型聚合）｜[analysis-methods.md](../analysis-methods.md)（主题 C = 会话日期核验法）
> 证据落位：session transcripts `~/.claude/projects/*/*.jsonl`（timestamp 为 UTC，换算 +8h）；bag `metadata.yaml` 的 `starting_time`；校验器全量输出 `/tmp/chk_links_full.txt`（43 条）与 `/tmp/chk_after.txt`（16/14 条）

---

## 一、结论先行

1. **日期实证**：低物链全部实际工作在 **09-08**——session transcript 按北京时间日统计：09-07 **零活动**，09-08 10:02~21:35 密集活动；bag `starting_time.nanoseconds_since_epoch: 1788833996504237069` = 09-08 10:19:56 +08 交叉印证。文档被 commit `c379842`（09-08 21:28）批量改名时**误写 09-07**（文档内日期与实际 commit 时间错位，09-07 无任何证据支撑）。
2. **修正批（r2 `d6055c5`，28 文件 39+/39-）**：`git restore` 还原改名时误做的 content 改写 → `git mv` 保史改名 → sed 修正文件内日期 → **引用方同步**（README / 07-handover / pending-tasks / retrospect README / surveys / roadmaps）→ **未追踪磁盘资产**（bag 目录、raw_data 文件）单独 mv + 内层 metadata/db3 路径 sed → Obsidian 镜像 `f2dfc17`（diff 0 差异）。
3. **链接批（r2 `1455d4e`，8 文件 25+/25-）**：全量校验 737 条 → 43 坏链 → 三桶分类呈报 → 用户**分三批准**修复（A 22 + B 3 + C 扩展名 2 + 同型深错补批 2 = **29 条**）→ 验收 43→14，剩余全为保留类（格式示例 10 + 复盘叙述 3 + 跨仓引用 1），本次改动致坏 = 0 → Obsidian 镜像 `fb516f1`。
4. 两处操作事故均当场纠正：sed 复合命令"未终止"报错（拆分简化重跑）；镜像 cp **多源平铺**把 4 文件错放到镜像 doc/ 根（rm 错放副本 + 按子目录重新覆盖，见经验点 2）。

---

## 二、过程明细

### 批 1 · 日期实证与修正（09-08 深夜 ~ 09-09 凌晨）

| 步 | 动作 | 验收/产物 |
|:--|:--|:--|
| 1 | 用户怀疑 09-08 工作量真实性 → session transcript 按北京日统计消息量 | 09-07 零活动 / 09-08 有活动 → 工作属实 |
| 2 | bag metadata 交叉验证 | `1788833996504237069` = 09-08 10:19:56 +08（盒子 bag 录制日） |
| 3 | commit 时间线核对 | `180077c`（09-08 12:06 config）→ `c379842`（09-08 21:28 误改批）→ `5fd655b`（09-08 21:35） |
| 4 | git 资产修正：restore → git mv → sed 文件内日期/链接 | 6 文档改名 + 1 rig 目录改名 + 14 件内部引用 sed |
| 5 | 引用方 sed 同步（README/07-handover/pending-tasks/retrospect README/surveys/roadmaps） | grep 09-07 残留 = 0 |
| 6 | 磁盘未追踪资产：bag 3 目录 + raw_data 2 文件 mv；内层 metadata.yaml `relative_file_paths` sed | bag 可重放、文件头日期正确 |
| 7 | commit + push → Obsidian 镜像 diff → 覆盖 → 0 差异 → commit + push | `d6055c5` ↔ `f2dfc17` |

### 批 2 · 链接全量校验与修复（09-09）

| 步 | 动作 | 验收/产物 |
|:--|:--|:--|
| 1 | `check_doc_links.py` 全量 | 737 条，缺失 43 |
| 2 | 三桶分类呈报（① 格式示例 ② 既有坏链 ③ 本次致坏）+ D 类待确认 | 用户批准 A(22)+B(3)+C 扩展名(2) |
| 3 | 修复 A/B/C：sed `../r2_bringup`→`../../`、kiss_icp_ws 3→4 级、`phase0/`→`../phase0/`、`.md`→`.txt` | 43→16 |
| 4 | 用户补批同型深错 2 条（ekf-yaw-plan `../`、crashbox `../../../bags`，归 D 未入首批） | 43→14 |
| 5 | 逐路径 add + commit + push → 镜像同步（cp 平铺事故纠正后 0 差异）→ commit + push | `1455d4e` ↔ `fb516f1` |

---

## 三、方法模板节

### ① 会话日期实证卡（"某天到底有没有做这件事"）

1. 找出相关 session transcript：`~/.claude/projects/*/*.jsonl`（按目录名对项目）
2. 逐行取 `timestamp` 字段，**UTC +8h** 换算北京时间，按北京日分组统计消息量（user/assistant 均计）
3. 空日 = 无活动铁证；再取 commit 时间（`git log --format=%ai`）交叉核对文档日期 vs 提交日期
4. 需落具体物证时用 bag `metadata.yaml` 的 `starting_time.nanoseconds_since_epoch`（转 epoch 工具换算 +8）
5. 判定：文档日期与提交/会话实证不符 → 文档日期为笔误，按实证日期修正

### ② 错批日期全量修正卡（git 资产 + 磁盘资产分开走）

1. 先 `git restore` 还原改名过程中误做的内容改写（恢复 HEAD 正确内容）
2. `git mv` 改文件名（保历史）；改动未追踪文件用 `mv`
3. sed 修正文件内日期字符串；再修**引用方**（README/handover/pending-tasks/索引/专题文档）——引用方常被漏
4. **未追踪资产单独处理**：bag 目录、raw_data 文件 mv 改名；bag 内层 `metadata.yaml` 的 `relative_file_paths` 一并 sed（否则 bag 不可重放）
5. grep 旧日期残留 = 0 → commit（body 说明实证依据）→ 镜像同步

### ③ 坏链三桶分类 + 同型聚合卡

1. 跑校验器取全量缺失清单（机器枚举）
2. **先按错误类型聚合再分桶**：深度错（`../` 级数不足）、扩展名错、跨仓引用、叙述/示例——同型合并成一组呈批，避免同型散落多文件导致分批补批
3. 每批给出文件×条数清单 + 修复前后对比；用户批准后执行，逐路径 `git add`
4. 验收：本次致坏 = 0，剩余按 ① 格式示例 / ② 既有坏链留档 / 跨仓引用分桶说明（详情规则见 [doc-engineering.md §四](../doc-engineering.md)）

---

## 四、经验点层次标注

| # | 经验点（含教训） | 建议去向 | 实落 |
|:--|:--|:--|:--:|
| E1 | **同型坏链按错误类型聚合呈批**，勿按文件位置散类——首批 A/B/C 漏 2 条同型深错致补批 | 规则层 doc-engineering §四 | ✅ 已追加 |
| E2 | **cp 多源平铺丢目录结构**：`cp f1 f2 f3 $DIR/` 全部进根目录，跨子目录同步必须逐目录 cp 或 rsync | 规则层 obsidian-sync §2 | ✅ 已追加 |
| E3 | **镜像"独有文件"先查上一步操作**：4 个假独有 = 自己 30 秒前 cp 错放，比完整调查流程（重命名/过时排查）先看时间戳与权威源对应子目录一致性 | 规则层 obsidian-sync §4 | ✅ 已追加 |
| E4 | **session transcript 日期核验法**（UTC→+8h 按日统计 + bag metadata 交叉）——客观核验"哪天做了什么事"，可推广到任何"工作真实性/日期错位"争议 | draft analysis-methods 主题 C | ✅ 已追加 |
| E5 | **git 状态快照会过时**：会话快照显示 fix_base 实际在 main，push 报"源引用无匹配"——push 前先 `git branch --show-current` | 事件层留存 | 本篇 |
| E6 | 未追踪资产（bag/raw_data）修正必须与 git 资产分开走、单独 sed 内层路径 | 规则层已有（doc-engineering §八）复用 | 本篇实例 |
| E7 | 批处理先 `git diff` 检视 + 逐路径 add；镜像 cp 事故被 diff -rq 立即暴露并纠正 | 规则层已有（doc-engineering §三/§六）复用 | 本篇实例 |

---

## 五、遗留

- 链接校验剩余 14 条全为保留类；唯一可后续收尾项：n97 `raspi_r1_control.md` 跨仓引用（真实文件在 STM32_Now `doc/02-deploy/`）——决定删除或改指向时处理
- 本篇不含状态类变更，07-handover / pending-tasks 无需更新
