# R2 导航行为病 × 安全设计调研（2026-09-06）

> 核实：2026-09-06 WebSearch（docs.nav2.org 官方 + GitHub navigation2 源码/issue 为主）+ 本地 R2 配置/数据交叉。
> 未实测项一律标注；nav2 版本口径 = Humble（R2 实机）为主，rolling/Jazzy 文档仅佐证。
> 关联：[retrospect 09-06 §11](retrospect/2026-09-06_lowobstacle_fixB_crashbox.md)（L1-L4 分层）、
> [chassis-kinematics-controller-survey.md](chassis-kinematics-controller-survey.md)（Q3/Q4 运动学线）、
> [3d-lidar-2d-navigation-survey.md](3d-lidar-2d-navigation-survey.md)（低物感知线）

---

## 一、Q1：灰格（unknown）大且清除慢 → 边走边清、速度降

### 1.1 现象定义（用户）
- 遇到新地段（岔路）、甚至**前方已扫描过的空白地带**，costmap 出现大面积灰格；车能走但速度低，
  前进中"边走边清"灰格。

### 1.2 机制核实（nav2 官方语义）
- 灰格 = **unknown（未观测）格**，来自 `track_unknown_space: true`（R2 global/local 均 true）。
  costmap 四态：unknown / free / occupied / inflated（[Nav2 环境表示文档](https://docs.nav2.org/rolling/getting_started/navigation_concepts/environmental_representation/)）。
- unknown 的**清除只能靠观察源 raytrace clear**：obstacle 层 `clearing: True` 把
  sensor→命中点（≤`raytrace_max_range`，R2=8m）路径格置 free（[案例配置](https://robotics.stackexchange.com/questions/107594)）。
  未覆盖区（车后、>8m、地图外、sensor 盲区）→ 保持 unknown。
- 岔路/新地段灰格大 = **static map（map_0815_clean）未覆盖该处**（无 static free）+
  车未驶近（sensor ray 没到）→ 整片 unknown；驶入后 ray 逐步 free 化 = 用户所见"边走边清"。
- "前方已扫描过的空白也灰"最可能口径：**global costmap 远处**（>raytrace 8m 或 global obstacle
  update 节流 0.64Hz 落后于车）——R2 global 大图 update 已实测节流（见 retrospect 09-06 §10）。

### 1.3 为什么灰格会降速（候选机制，精确公式未源码钉死）
- 全局 planner（NavFn/GridBased）**传统把 unknown 当 free**（能走 ✓ 用户"车正常在走"）。
- local MPPI 侧：CostCritic 感知 `is_tracking_unknown`（[jazzy 类文档](http://docs.ros.org/en/jazzy/p/nav2_mppi_controller/generated/classmppi_1_1critics_1_1CostCritic.html)）、
  path 成本计算会 consult `isTrackingUnknown()`（[PR #4174](https://github.com/ros-navigation/navigation2/pull/4174)）。
  候选 = ① unknown 区格被 CostCritic 记入成本 → 穿过灰区的轨迹被压分 → 优选"少进灰"轨迹 → 观感减速；
  ② 或减速实为 MPPI 轨迹被 costmap 变化频繁打回。
  **候选 ① 的精确公式本次未在官方文档钉死 → 标注"待源码核实或实测"**（验证法：录一段岔路灰区行进，
  对比 local master costmap 灰格比例 vs MPPI 输出 vx 曲线）。
- 官方提醒相邻点：**local costmap 太小会人为 cap 速度**（prediction horizon = time_steps×model_dt×vx
  超出 costmap 视野时，[configuring-mppic](https://docs.nav2.org/configuration/packages/configuring-mppic.html)）——
  R2 local 6×6m：horizon 48×0.04×0.2≈0.4m ≪ 3m，此项不构成限制（仅记录排除）。

### 1.4 修法选项（按"改动面 × 收益"）

| 选项 | 做法 | 取舍/风险 |
|:--|:--|:--|
| a. 接受 + 行为 | 岔路前减速探测是 nav2 保守默认（安全）；"边走边清"= 探路模式 | 零改动；时间成本留规划余量 |
| b. 预扫 | 全向车可**原地自旋扫描**把岔路先 free 化再走（行为层/操作层） | 简单可靠；占用时间，需操作习惯 |
| c. 调 MPPI unknown 成本 | 待源码核实参数存在性（候选：CostCritic 或 obstacle 层 `unknown_cost_value`） | 激进=快速但盲；不推荐默认激进 |
| d. global 提速 | 深究 global 0.64Hz 节流（update 耗时/大图裁剪），让 global free 跟上 | 独立问题线，见 retrospect §10 观察项 |
| e. 关 track_unknown | global `track_unknown_space: false`（unknown 即 free） | ❌ 语义破坏：膨胀层无 unknown 边界、AMCL 无关但 planner 更激进——不推荐 |

> 结论：灰格 = 安全语义的正常表达；嫌慢走 b（预扫）最稳，激进调参（c/e）风险大于收益。

## 二、Q2：转弯处绕行范围不够，经常撞

### 2.1 机制核实
- **非圆足迹旋转扫掠**：R2 footprint 0.84×0.66（矩形）旋转半径 = √(0.42²+0.33²) ≈ **0.53m** >
  静态半长 0.42m。inflation_radius 0.30（08-17 为过窄缝调小，[retrospect 08-17](../retrospect/2026-08-17_nav2_initialpose_inflation_fix.md)）
  的膨胀余量只按静态姿态留 → **旋转到 45° 时角点外扩 0.53−0.42≈0.11m 超出膨胀边界**（数量级参考，精确碰撞判据看下条）。
- **MPPI 足迹检查**：CostCritic `consider_footprint: true`（R2）→ 轨迹逐姿态（含 θ）足迹级检查，
  理论上已覆盖旋转扫掠；但社区明确 issue：
  [#5668 非圆机器人窄处后部近碰漏罚](https://github.com/ros-navigation/navigation2/issues/5668)——
  点成本为主、足迹检查阈值后才全检，rear/near-miss 段可漏。
- **更主要的撞弯归因 = 障碍不在图上**：弯道内侧/转角低物若处于低物盲区（L1/L2 感知线，见
  [3d-lidar-2d-navigation-survey](3d-lidar-2d-navigation-survey.md)）或 unknown 灰区，costmap 无 mark →
  任何 critic 都无从拦——**与 Q1 灰格、低物链同源**。

### 2.2 修法选项

| 选项 | 做法 | 取舍 |
|:--|:--|:--|
| a. inflation ≥ 旋转半径 | 局部关键弯道评估 inflation 0.30→0.45+（0.53 附近） | 08-17 窄缝矛盾复现风险 → 只给**转弯段**留余量需要 footprint padding 类机制（nav2 无直接参数）或接受全局调大后重测窄缝 |
| b. 转弯降速 | MPPI/costmap 对高曲率路径段限速（wz 大 → vx 上限降） | 留出反应时间；实现 = 调 critic 或 costmap filter（官方 speed restriction 区） |
| c. 感知补齐 | 低物进图（近距 mark-only 层/盲区锥策略，见低物线）+ 灰区处理 | 治本；就是 09-06 开放项 |
| d. 窄处/弯道分开配 | 弯道场景换 inflation 配置/参数组 | nav2 运行时改参可行（dynamic reconfigure），流程复杂 |

> 结论：撞弯 = 「margin 结构性不足（旋转扫掠 vs 0.30 膨胀）」+「障碍不在图上」双因；优先补感知（c）
> 与转弯限速（b），inflation 全局调大有窄缝副作用需成套重测。

## 三、Q5：安全措施规划（含 IMU 震动检测）

### 3.1 分层安全架构（R2 现状 + 缺口）

| 层 | 机制 | R2 现状 | 缺口 |
|:--|:--|:--|:--|
| L0 电气/机械 | 物理急停 | ✅ 有 | — |
| L1 固件 watchdog | 指令超时/看门狗 | 底盘层有（未核实细节） | — |
| L2 运动一致性 | 期望 cmd_vel vs odom 实际偏差（打滑/被推/卡死） | ❌ 无 | 新增 watchdog 节点：|Δv| 超限 N ms → 停车 |
| L3 碰撞/冲击检测 | IMU 瞬态强震动（撞箱/撞墙时刻加速度尖峰） | ❌ 无 | 新增：imu/data 加速度瞬态检测 → E-stop 话题 → 底盘/行为层响应 |
| L4 nav2 recovery | behavior server（spin/backup/stop） | ✅ 启用 | 撞后"恢复 vs 停等人工"策略未定义 |
| L5 行为兜底 | 低物盲区锥限速/停车（感知失败 fallback） | ❌ 无 | retrospect 09-06 §11 建议项 |

### 3.2 IMU 震动检测设计（L3）
- 信号：`/imu/data` linear_acceleration（G354 已入栈，~85Hz）；特征 = 窗口内 |a| 尖峰
  （如 >1.5~2.0g）或加速度能量突变 → 疑似碰撞/撞击。
- 判据参数化：阈值 + 去抖窗口 + 与 cmd_vel/odom 联合（避免误报：颠簸路 vs 真撞）。
- 反馈链路：检测节点 → 发布 `/safety/estop`（std_msgs/Bool）→ ①底盘节点直停（最低延迟）
  ②nav2 收到后可走 recovery 或保持停车等人确认。
- **可行性验证（本地可做，推荐）**：手头撞箱 bag（`box_lowband_20260906_101449/_102944`）内
  撞箱瞬间的 imu 特征直接统计——1 小时内可出"撞箱加速度尖峰"证据，定阈值。
- 参考框架：nav2 无内置碰撞检测（behavior 只有 recovery），工业做法多为自研 watchdog 或
  safety controller（Autoware 有 collision 检测节点可参考其思路，未实测不引用细节）。

### 3.3 建议实施顺序（安全线）
1. L2 运动一致性 watchdog（简单、收益高：防打滑漂移）
2. L3 IMU 冲击检测（用撞箱 bag 定阈值后加）
3. L5 低物盲区锥兜底（与 A1 验收口径绑定，见 lowobstacle 线）
4. L4 恢复策略定义（撞后自动 backup+重规划 vs 停等人工——实车安全优先：停等人工）

---

## 来源（2026-09-06 WebSearch 核实）

- [Nav2 Environmental Representation（unknown/free/occupied/inflated）](https://docs.nav2.org/rolling/getting_started/navigation_concepts/environmental_representation/)
- [Configuring MPPI（官方参数 + 视野/costmap 尺寸提醒）](https://docs.nav2.org/configuration/packages/configuring-mppic.html)
- [nav2_mppi_controller motion_models.xml（GitHub）](https://github.com/ros-navigation/navigation2/blob/main/nav2_mppi_controller/motion_models.xml)
- [CostCritic 类文档（jazzy：is_tracking_unknown 等）](http://docs.ros.org/en/jazzy/p/nav2_mppi_controller/generated/classmppi_1_1critics_1_1CostCritic.html)
- [cost_critic.cpp 源码（rolling）](https://api.nav2.org/nav2-rolling/html/cost__critic_8cpp_source.html)
- [PR #4174 MPPI 45% 性能优化（isTrackingUnknown consult）](https://github.com/ros-navigation/navigation2/pull/4174)
- [Issue #5668 非圆足迹后部近碰漏罚讨论](https://github.com/ros-navigation/navigation2/issues/5668)
- [Robotics SE：track_unknown_space / allow_unknown 实践](https://robotics.stackexchange.com/questions/107594)
- [Smac 2D planner 配置（allow_unknown）](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/planners_plugins/smac/smac_2d/configuring_smac_2d/)

> 未实测标注：Q1.3 候选①（unknown→MPPI 成本）精确公式；Q2 数量级（0.11m 超界）为几何估算待实测；
> IMU 阈值待撞箱 bag 验证。
