# 数据资产目录跨仓迁移：bags 入 r2_integration 全流程复盘（2026-09-04）

> 事件：用户决策「bags 不再分属 Lin_workspace 父仓，整个目录移入 r2_integration 随项目提交」——
> 约 20G 数据目录（19G raw + 616M maps + analysis/csv/README）跨仓迁移 + 白名单入库 + 全库路径重定向 + 双仓提交。
> 定位：可复用的「数据资产目录跨仓迁移」方法论记录（盘点 → 转移 → 白名单 → 路径批量 → 链接分类 → 校验 → 双仓批次）。
> 规则化版本见 [doc-engineering.md §八](../doc-engineering.md)（2026-09-04 增补）。
> 关联：[2026-09-03_doc_engineering.md](2026-09-03_doc_engineering.md)（doc 分层整理复盘，同手法族）。

---

## 一、背景与方案决策

- 背景：bags（R2 实验数据：N97 采集 raw + VM 分析副本）长期独立于 `~/Lin_workspace/bags`（父仓 Lin_workspace 管辖），
  与 R2 代码/文档（r2_integration 嵌套仓）分属两仓。用户 09-03 决策：「整个 bag 文件夹放到 r2 区域内，
  后续直接一起提交，不再分到 Lin_workspace 这个仓库」
- 方案（AskUserQuestion 两项批准）：① 删除重复内容 + r2_eKF_test.bag（唯一文件）入 raw/；
  ② 接受**白名单 .gitignore**（raw 19G / maps 616M 不入库本地保留，仅 analysis/csv/README/截图约 2M 资产进 git）
- 关键语义：**这是嵌套仓之间的目录搬家**——r2_integration 是 Lin_workspace 的子仓。父仓删跟踪（git rm --cached）+ 子仓新增

## 二、执行链条（含试错）

| 步 | 动作 | 试错 / 关键点 |
|:--|:---|:---|
| 1 | 盘点 ~30 bag/日志，归类 raw 19G / maps 616M / analysis 400K / csv 1.2M | — |
| 2 | 重复清理：3 个旧 .bag（07-30 底盘测试）在**新旧位置都出现** | **目录格式 bag 坑**：`*_0.db3` 分片 + metadata.yaml 的**目录**不是文件——`rm` 报 "Is a directory"，且**嵌套脚本里 set -e 未中止后续步骤**，最终把旧目录整个搬进新仓 → 出现 `bags/bags/` 嵌套。修复：`diff -rq` 内容验证 3 个重复项后 `rm -rf` 旧位，`mv` 上移嵌套内容 + rmdir，`du/ls` 复验 |
| 3 | 父仓 `git rm --cached -r bags/` | 15 个跟踪文件解除（25316 行），删除**待提交**（不 commit） |
| 4 | 整目录 `mv` 入 r2_integration/bags/ | 结构验证：README/.gitignore/analysis/csv/maps/raw/2 png |
| 5 | r2 仓 .gitignore：`bags/` 整忽略 → **白名单** `bags/*` + `!bags/README.md` `!bags/.gitignore` `!bags/analysis/` `!bags/csv/` `!bags/*.png` | 验证三连：`git status --untracked-files=all` 展开白名单可见项 + `git check-ignore` 确认 raw/maps **深度忽略**（目录被忽略后其内一切无法用 `!` 解除——恰好不需要） |
| 6 | 路径批量重定向：**23 文档 46 处** `Lin_workspace/bags/` → `Lin_workspace/r2_integration/bags/`（sed，排除 raw_data 历史原件） | 纯文本路径一次过 |
| 7 | **md 链接形态单独处理**（sed 文本路径覆盖不到的正确性层）： | 三类：① map-verify-flow 5 处 `../../../Lin_workspace/...` = **跨仓虚构链**（迁移后 bags 入仓 → 重写为仓内 `../../bags/`）；② nav2_bringup `../../../bags/` = **迁移前合法外部链**（指向仓外真实位置）→ 迁移后失效 = 移动致坏 → `../../bags/`；③ map_chain 以链接语法写 `~/Lin_workspace/...`（方括号文本 + 圆括号目标）→ **校验器按相对解析、不展开 ~**（历史遗留坏链）→ 仓内链 |
| 8 | analysis 脚本内硬编码路径同步（`*.py` sed） | **区分留档与活引用**：脚本 `.py` 是活引用（不入库即失效）→ 更新；`*_out.txt` 是历史日志内容 → 如实留档不动 |
| 9 | README 树登记 bags 段 + bags/README.md 头部更新（采集/副本同路径 + 入仓标注） | — |
| 10 | **校验器验收**：502 条 → bags 相关缺失 5→0，总 46→39（残留 = 全既有桶：格式示例 + 历史旧链） | 「机器枚举 + 人工分桶」闭环 |
| 11 | 双仓 4 笔提交 + push | 见 §四 |

## 三、关键教训（按杀伤力排序）

1. **目录格式 rosbag ≠ 文件，批量迁移脚本必须逐层验结构**：`rm` 报 "Is a directory" 后脚本仍继续
   （set -e 未中止嵌套子命令），错误被带入最终结构（bags/bags 嵌套）。教训：**结构变更每步验证，
   出错先回滚该步再重跑**（对应 doc-engineering §二-5「恢复 + 收紧规则重跑」的通用化）
2. **文本路径批量 ≠ 链接修复完成**：sed 只处理了行内文本；**md 链接形态**（方括号文本 + 圆括号目标的写法）三类
   各自语义不同（仓内/仓外真实/虚构 + `~/` 写法），靠校验器逐条判定后才完整。迁移后 grep 纯文本
   残留 = 0 不代表链接层正确——**校验器是唯一验收闸门**
3. **Bash 裸 git 命令的 cwd 陷阱（AI 操作层）**：工具工作目录可能停在会话启动目录而非最近 cd 的仓
   （本会话 push 前检查曾把 STM32_Now 仓误当 r2_integration 输出，一度误判「提交落错仓」）。
   教训：**多仓操作一律 `git -C <路径>`，裸 git 不信任**；落仓核验用 `git cat-file -t <hash>` 或
   `git -C <仓> log` 双向确认
4. **白名单 gitignore 的可验证性**：`git status --untracked-files=all` 展开 + `git check-ignore` 打点
   （raw/maps 深度忽略、白名单件可见）——不靠肉眼读规则
5. **留档 vs 活引用二分**：日志输出 txt（历史记录，如实留档，路径旧就旧）与脚本 py（可执行，路径须活）
   在批量替换时分开处理；同理 raw_data 原件不参与 sed（历史原文）
6. **嵌套仓迁移的提交顺序**：父仓删除先行（fa88c91）→ 子仓资产 + 配套（5c539e2）→ 路径统一（ffd6397）
   → 收尾文档（d9fe5de）；commit body 双仓互引 hash，`git log --grep` 可双向对账

## 四、量化结果

| 指标 | 值 |
|:---|:---|
| 迁移体量 | raw 19G + maps 616M 本地保留（不入 git）；入 git 轻量资产 ~2M（bags 39 件 + .gitignore + README 树） |
| 重复清理 | 3 个目录格式旧 bag（diff 内容验证）+ r2_eKF_test.bag 入 raw/ |
| 文档路径重定向 | 23 文件 46 处 + md 链接形态修正 7 个目标（5+1+1） |
| 脚本路径同步 | analysis/*.py 全部（txt 日志留档不动） |
| 校验器 | 502 条，bags 相关缺失 0（5→0），总缺失 46→39（残留全既有桶，未触碰） |
| 提交 | 父仓 fa88c91（15 删，25316 行）+ r2 5c539e2（41 增，29792 行）/ ffd6397（17 文档 42/42）/ d9fe5de（8 件收尾） |

## 五、状态与后续

- 双仓已 push；Obsidian 镜像同步 0 差异（09-04）
- N97 对齐：两仓 git pull（raw 录制目录同路径，无数据搬运）
- 关联后续：低物断点收尾同批提交（见 [2026-09-04_lowobstacle_breakpoint.md](2026-09-04_lowobstacle_breakpoint.md)）；
  规则化落 doc-engineering §八

## 相关文件

- 规则化：**[doc-engineering.md §八](../doc-engineering.md)**（数据目录跨仓迁移，2026-09-04 增补）
- 同手法族：**[2026-09-03_doc_engineering.md](2026-09-03_doc_engineering.md)**（doc 分层整理方法论）
- 提交溯源：父仓 `fa88c91` ↔ r2 `5c539e2`/`ffd6397`/`d9fe5de`（互引 hash）
