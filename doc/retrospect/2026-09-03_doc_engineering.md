# 文档工程：doc/ 第一层次整理复盘（2026-09-03）

> 事件：r2_integration doc/ 顶层 23 个散件 → 分层文件夹；全部待办汇总为入口索引文档。
> 定位：可复用的「文档工程」方法论记录（分层整理 / 链接修复 / 完整性校验 / 镜像同步 / 协作授权）。
> 相关：本次结构变更是当前状态（git 历史可查），本文只留**手法与教训**。

---

## 一、背景与目标

doc/ 顶层散落 23 个文件（部署手册、路线图、过时状态档混在一起），无文件夹划分。
用户指令两条：
1. **第一层次整理**：划分文件夹（顶层收敛，规范 + 阅读主线留顶层）
2. **待办汇总**：全库待办梳理为一份索引文档，每条 = 一句话 + 源文档入口（不展开）

批准过程：AskUserQuestion 三项决策（方案 A 顶层收敛 / 过时档归档保留 / 本轮同步 Obsidian 镜像），
每项给出影响，由用户定夺后再执行（决策边界三原则）。

## 二、目标结构与移动清单

顶层保留 10 件（规范 5：standards/ros2-ops/ros2-qos-dds/obsidian-sync/obsidian-tags；阅读主线 4：
01-plan/02-progress/03-current_state/07-handover；新索引 1：pending-tasks.md），其余入文件夹：

| 新文件夹 | 内容 | 件数 |
|:---|:---|:---|
| `n97/` | N97 部署/运维手册（02-deploy-checklist、n97_remote_desktop、n97info、fastlio2-n97-deploy、greenwave-monitor-deploy、velodyne_r2.patch） | 6 |
| `roadmaps/` | 路线/学习计划（planning-control、motion-control、recruitment-learning-plan ×2、nav2-knowledge-tree） | 5 |
| `archive/` | 过时状态档（project_status、project_landscape，文件头加「已过时」横幅） | 2 |
| `raw_data/` | raw_实操路线_2026-09-02_2139.md 归位（未跟踪，不入 git） | 1 |

前置探索（动刀前 3 份盘点）：
- 交叉引用爆点地图：**约 200 处 doc 内相对链接，零代码/配置依赖**（scripts/ROS2 包无引用）→ 风险收敛在文档层
- 3 件漏登记文件（nav2-knowledge-tree 孤儿、review 稿、greenwave）→ 补进 README 树
- minimal-loop(史) vs minimal-loop2(现行) = 先后关系非重复 → 第一层次不合并

## 三、链接修复方法论（核心经验）

**移动文件的链接按目标分类处理**：
- 指向 doc 树内的相对链接 → 按新目录重算深度
- 指向 doc 树外**真实存在**的仓库路径（`../r2_bringup/…`）→ 也要加深前缀（`../../r2_bringup/…`），
  早期版本误当「外部链接」跳过，致 nav2-knowledge-tree 6 处移动后失效（校验器抓出）
- 指向 doc 树外**虚构/跨项目**路径（`../../../Lin_workspace/…` 双 Lin_workspace、`raspi_r1_control.md`）→ 保持原样（既有问题不放大）
- Obsidian `[[wikilinks]]` 按 basename 解析 → 不动

**未移动文件的引用方** → 仅当解析目标不存在且 basename 命中移动登记表才重写（防过度改写，
v1 曾把合法外部链 `../../../Lin_workspace/bags/README.md` 误改 → git checkout 恢复 + 收紧规则重跑）。

**漏网类型（校验器抓出）**：裸**目录**链接 `[retrospect/](retrospect/)` 随移动失效——
正则脚本对文件目标重写，目录目标漏掉 1 处（project_status）。

**校验器**：遍历 doc 全树 + 根 README 解析 `](target)`，相对文件目录解析目标，报告缺失；
缺失分类三桶（格式示例 / 既有坏链 / 移动致坏）——**移动致坏必须清零**，其余两桶留档不动
（最小干预，防止把文档史改花）。

## 四、权威树同步契约（维护契约 §1.7 落地）

唯一文件树权威 = 根 README；standards §2.1/§2.2 为第二处结构声明。两处 + 引用方全部同步后，
链接受影响面 = doc 内 + 根 README + CLAUDE.md 的 @导入（方案 A 不动顶层 5 规范 → @导入不受影响）。

**教训**：01-plan.md 内嵌文件树是早期**历史快照**（缺文件远早于本次）——「树」类内容只追权威两处，
历史快照标注不追（01-plan 树留原样，避免把老文档改成假当代）。

## 五、协作纪律（本次执行的边界）

- 用户未提交 WIP（minimal-loop2 ×3、retrospect 09-03、raw ×2）全程隔离：add 逐个路径，**不用 `git add -A/-u`**
- 移动用 `git mv`（保历史）：**git mv 已把 rename 写进 index**，后续内容修改只 add 新路径即可补 stage
- 分 3 批 commit（结构移动 / 引用更新+索引 / 复盘文档），**不自动 commit/push**——由用户逐批/整批授权

## 六、Obsidian 镜像同步（obsidian-sync.md §2 实测流程）

1. `diff -rq` 盘点：镜像侧独有 = 13 个旧顶层位置文件（调查确认为**重命名迁移**，非真独有）
2. 镜像侧：rm 旧位 → rsync 单向全量（排除 raw_data）→ raw_data 单独补 2 件
3. `diff -rq` 验证 **0 差异**（raw_data 含用户在库惯例，一并同步）

## 七、量化结果

| 指标 | 值 |
|:---|:---|
| git mv | 14 件（13 跟踪 + 1 未跟踪归位） |
| 链接重写 | 移动文件内部 ~60 处 + 引用方 ~40 处 + 漏网修复 2 处 |
| 完整性校验 | 480 条，移动致坏清零；残留 41 条 = 既有问题（格式示例 + 历史文档旧深度） |
| 旧路径 grep | 残留仅用户 WIP 纯文本提及 + 历史快照树，均未动 |
| 待办汇总 | ~50 条去重 → 6 分组入口索引 |
| 镜像 | diff -rq 0 差异 |

## 相关

- 结构变更本身：README 文件树（当前状态，权威）｜[standards.md §2.1](../../standards.md)
- 待办索引：[pending-tasks.md](../../pending-tasks.md)
- 文档规范：[standards.md](../../standards.md)（§1.7 维护契约 / §1.12 只增不删 / §2.5 树放置）
