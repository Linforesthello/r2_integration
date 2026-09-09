# VSCode 工作区建立规范（Claude 会话归属 · 跨项目适用）

> 定位：**独立文档先行**（2026-09-09 用户定调：规范内容先落独立 doc 文件，后续统一盘点抽调入规则层）
> 候选去向：standards 通用层（工作区/会话归属章）——成熟判据 = 在 R2 与 STM32 两处落地均生效
> 适用范围：任何 Claude Code / VS Code 项目的「工作区文件选址 + 会话历史归属」决策
> 调研方式：2026-09-09 本地盘点（无外搜）；与会话哈希规则关联的外部文档 = `~/ProjectRequirement/MCU/Lin_STM32/STM32_F103C8T6/STM32_Now/doc/claude_conversation_migration.md`（跨仓文档，不入链）

---

## 一、背景：为什么需要这份规范（2026-09-09 盘点事实）

| 项 | 现状 | 问题 |
|:--|:--|:--|
| R2 代码仓 | `~/Lin_workspace/r2_integration`（独立 git 仓，根含 CLAUDE.md/doc 树/scripts） | 无 `.vscode/`、无 workspace 文件，VS Code 一直挂在 STM32 工作区里用 |
| Claude 会话 | 81 个 jsonl 全在 STM32_Now-0-Workspace 哈希下 | 其中 **60 个含 r2_integration 内容**（R2 系）错挂——检索/备份/作品集归属混乱 |
| VS Code 工作区 | `robot.code-workspace`（STM32_Now 仓根，settings 为 STM32 工具链专用） | folders 挂载 **Lin_workspace 整目录** + fast_lio_ws + locowiki_ws + 1_Robocon2026_plan + Open-Notes-Library——文件监视/搜索被 build/install/log/bags 污染；settings 对 R2 python/yaml 是噪音 |

根因：**工作区/会话归属没有跟「项目仓」走**——哪个目录先开会话，历史就堆在哪。

---

## 二、规范流程（操作卡）

### ① 单仓项目（默认形态）：仓根 = 工作区根

- VS Code 直接以仓根为文件夹、Claude 会话也在仓根目录发起——**不建 .code-workspace**
- 会话哈希 = 仓路径哈希（如 `~/Lin_workspace/r2_integration` → `-home-lin-Lin-workspace-r2-integration`）
- 仓根放置 CLAUDE.md（项目级指令）时自动被会话加载

### ② 确实需要跨仓协作时，才建多根 `.code-workspace`

判定：单个仓内无法完成、且频率真实的跨仓需求（如代码仓 + 文档镜像库同窗编辑）。

1. **文件放主仓仓根**（入 git 版本化，可复用）；folders 用**相对路径**，首项 `{ "name": "<主仓>", "path": "." }`，其余按需追加
2. **只挂必要仓**：绝不挂整棵生态目录（会拖入 build/install/log/bags/__pycache__）；仅挂真正协作的仓
3. **settings 最小化**：只放跨仓通用的编辑偏好（fontSize、产物目录 exclude）——
   `files.exclude`/`search.exclude` 排除 `build`/`install`/`log`/`**/__pycache__` 类产物；
   工具链配置（arm gcc、clangd、ROS 扩展）放各仓自己的 `.vscode/settings.json`，不得混入跨项目全能工作区
4. 命名 `<项目名>.code-workspace`；文件头 JSON 可带注释（`//`）说明选址理由与会话哈希预期

### ③ 会话哈希：以实测触发为准，不手造目录名

- 规则：路径 `/`→`-`、整体前缀 `-`；**下划线 `_` 处理有版本差异**（早期转 `-`、近期保留）——以磁盘为准
- 多根 workspace 的哈希归属 = VS Code 活动工作区的解析结果，**历史记录中同一形态有两种行为**（05-27 robot.code-workspace = 仓路径哈希；07-25 learnmap.code-workspace = 路径哈希 + `-learnmap-code-workspace` 段）
- **铁律：先在目标工作区触发一次对话（发条消息），再看 `~/.claude/projects/` 实际新出现的目录名**，cp 到那个真实目录
- `~/.claude/projects/` 存在**视觉同名目录**（如 `STM32-F103C8T6` 与 `STM32_F103C8T6` 仅下划线差异）——定位用 `find ~/.claude/projects -maxdepth 1 -type d` 或 Tab 补全，勿手输路径

### ④ 会话迁移

1. 目标目录确认（③ 实测）后：`cp` 源 jsonl → 目标（`file-history/` 全局共享不动）
2. `cmp` 逐文件验证（正在写盘的活动会话除外——建议会话结束后补最终同步）
3. VS Code `Developer: Reload Window` 刷新聊天历史列表验证

### ⑤ 迁移范围决策

- 先迁**最近活跃批**（按 jsonl mtime 排序），不要一上来全量；旧会话留在源，随用随补迁
- 源副本不删（cp 语义），待确认新工作区稳定后再决定清理

---

## 三、执行记录：2026-09-09 R2 落地（方案 B）

**用户定夺**：① 选址 B（`r2.code-workspace` 放 r2_integration 仓根入 git）② 迁移优先最近活跃 ③ 规范先落独立 doc

**产物**：
- `r2.code-workspace`（仓根）：folders = `r2_integration`(".")；settings = fontSize 14 + exclude build/install/log/__pycache__
- 会话迁移：**全量**——源哈希 81 个 jsonl 中 78 个含 r2_integration 内容全部迁至 `-home-lin-Lin-workspace-r2-integration`（VS Code 实测哈希与预期一致；先迁 09-02~09-09 活跃批 24 条，用户 09-09 追加决定全量补迁 54 条 = 78 总）
- 校验：`cmp` 77/79 逐字节一致；差异 2 = 本会话 32a37bbd（迁移时仍写盘，属预期）+ hi 验证会话 915babfb（源无对应，属正常）；目标目录另含 VS Code 自建 `memory/`
- 判据教训：**会话归属判定用全文 grep**（`grep -ql "关键词"`），头部 N 字节抽样会低估（60 → 78 差额 = 头段未含关键词的会话）

**过程中的坑（已成文规则）**：手输源哈希踩到 `STM32-F103C8T6`/`STM32_F103C8T6` 视觉同名目录（见 ③ 铁律）；曾 mkdir 猜测目标目录名——恰与实测一致属侥幸，正式流程一律实测（③）。

---

## 四、待办 / 抽调跟踪

- [x] **本会话（32a37bbd）同步**——09-09 12:27 用户要求已提前执行（cmp 一致）；会话仍写盘中，若需完整归档可会话结束后再同步一次
- [ ] robot.code-workspace 收敛：摘除 R2 生态挂载（Lin_workspace 整目录等），回归 STM32 本职——随 STM32 侧会话整理执行
- [ ] 旧 0-Workspace 哈希内 R2 会话**源副本去留**决策（78 个双份占空间 vs 防误删缓冲）——新工作区稳定使用一段时间后再定
- [ ] **09-10 盘点抽调**：本节规则在 R2/STM32 两处落地后，抽调入 standards 通用层（只增不删追加）
