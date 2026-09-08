# R2 导航行为病 × 安全设计调研（2026-09-06）

> 核实：2026-09-06 WebSearch（docs.nav2.org 官方 + GitHub navigation2 源码/issue 为主）+ 本地 R2 配置/数据交叉；
> §1.3/§1.4-c 结论由 navigation2 **humble 分支源码逐行核实**（2026-09-06，链接见来源）。
> 未实测项一律标注；nav2 版本口径 = Humble（R2 实机）为主，rolling/Jazzy 文档仅佐证。
> 关联：[retrospect 09-06 §11](../retrospect/2026-09-06_lowobstacle_fixB_crashbox.md)（L1-L4 分层）、
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

### 1.3 为什么灰格会降速（源级核实 09-06：候选 ① 对 R2 不成立）

**先钉死"灰在哪张图"**：R2 仅 global_costmap 显式 `track_unknown_space: true`
（[nav2_params_low.yaml](../../r2_bringup/config/nav2_params_low.yaml)）；local_costmap 未配 →
nav2 该参数默认 **false**（[costmap_2d_ros.cpp L97](https://github.com/ros-navigation/navigation2/blob/humble/nav2_costmap_2d/src/costmap_2d_ros.cpp#L97)），
未观测格 default_value = FREE(0)（[obstacle_layer.cpp L112](https://github.com/ros-navigation/navigation2/blob/humble/nav2_costmap_2d/plugins/obstacle_layer.cpp#L112)）
→ **local（MPPI 消费图）无灰格**；灰只存在于 global（static 未覆盖 + 未 ray 到 + 更新节流 0.64Hz）。

**全局 planner 对灰格的精确语义**（[navfn.cpp setCostmap L246-291](https://github.com/ros-navigation/navigation2/blob/humble/nav2_navfn_planner/src/navfn.cpp#L246-L291)）：
`allow_unknown: true`（R2 显式配；[navfn_planner.cpp L88](https://github.com/ros-navigation/navigation2/blob/humble/nav2_navfn_planner/src/navfn_planner.cpp#L88) 默认即 true）
→ unknown 格映射为 **COST_OBS−1（可通行、全场最高代价）**；`false` → 当障碍。
即灰格 = **"尽量避开、绕无可绕才穿"的高代价可通行格**，不是"当 free"。

**MPPI CostCritic 对 unknown(255) 的源级公式**（[cost_critic.cpp humble](https://github.com/ros-navigation/navigation2/blob/humble/nav2_mppi_controller/src/critics/cost_critic.cpp)）：
- score() L153-169：中心点格值 ≥ INSCRIBED_INFLATED_OBSTACLE(253) → 每格 +`critical_cost_`(300)，
  否则 +格值(1~252)——255 ≥ 253 必然落 300 分支 → **图里有灰格则每落灰轨迹点 +300 罚分**（与
  inscribed 近撞同档）；free(<1) 跳过不累计。
- inCollision() L188-212：`NO_INFORMATION → return is_tracking_unknown ? false : true`——R2 local
  tracking=false → **255 判死**；而 local 里 255 只可能来自**出图**（costAtPose worldToMap 失败→255，
  足迹轮廓出界 → [FootprintCollisionChecker](https://github.com/ros-navigation/navigation2/blob/humble/nav2_costmap_2d/src/footprint_collision_checker.cpp#L36-L44) 判 LETHAL）→ **local 窗边 = 虚拟墙**（R2 horizon
  0.4m ≪ 半宽 3m，正常不触发）。
- isTrackingUnknown consult 出处：该分支在 [PR #4174](https://github.com/ros-navigation/navigation2/pull/4174)
  （"45% performance improvement in MPPI"）重构**前后均存在**——PR 仅将其 inline 化 + 缓存
  `is_tracking_unknown_` 成员；另在 findPathCosts 对 unknown 上的路径点 consult tracking
  （tracking=true 时灰上路径点保持有效、路径跟随不断点；注：critic 查询的是 local costmap，
  R2 local 无灰 → 该分支少见触发）。

**结论：候选 ①（灰格被 CostCritic 记入成本 → 压分 → 降速）对 R2 不成立**——local 无灰格，
该罚分分支正常行驶不触发。降速候选收敛为：
a. **global 路径绕灰**（灰 = COST_OBS−1 高代价 → Dijkstra 绕行 → 路径更长/更弯，MPPI 跟弯路径
转弯段自然降速——与 Q2 同源）；b. **global 更新节流 0.64Hz** 滞后（§1.2），path 与 costmap 反复不一致；
c. 反向说明：R2 现状 = local"未观测即 free"的激进默认（见 1.4-c' 保守化选项）。
主导项判定仍须录包实测：录岔路行进段，对齐 path 曲率 / cmd_vel / global costmap 时间戳三者。
- 相邻排除（官方提醒）：**local costmap 太小会人为 cap 速度**（prediction horizon = time_steps×model_dt×vx
  超出 costmap 视野时，[configuring-mppic](https://docs.nav2.org/configuration/packages/configuring-mppic.html)）——
  R2 local 6×6m：horizon 48×0.04×0.2≈0.4m ≪ 3m，此项不构成限制（仅记录排除）。

### 1.4 修法选项（按"改动面 × 收益"）

| 选项 | 做法 | 取舍/风险 |
|:--|:--|:--|
| a. 接受 + 行为 | 岔路前减速探测是 nav2 保守默认（安全）；"边走边清"= 探路模式 | 零改动；时间成本留规划余量 |
| b. 预扫 | 全向车可**原地自旋扫描**把岔路先 free 化再走（行为层/操作层） | 简单可靠；占用时间，需操作习惯 |
| c. 调 MPPI unknown 成本 | 源级核实（09-06）：**不存在 unknown 专用参数**——CostCritic 无；obstacle 层无 `unknown_cost_value`（humble 源码只有 `track_unknown_space` 决定 default 值，[obstacle_layer.cpp L73/L112](https://github.com/ros-navigation/navigation2/blob/humble/nav2_costmap_2d/plugins/obstacle_layer.cpp#L73-L112)）；255≥253 罚分硬编码走 `critical_cost_`（与 inscribed 判罚耦合） | 无专用旋钮；全局动 critical_cost_ 牵连近撞判罚——不推荐 |
| d. global 提速 | 深究 global 0.64Hz 节流（update 耗时/大图裁剪），让 global free 跟上 | 独立问题线，见 retrospect §10 观察项 |
| e. 关 track_unknown | global `track_unknown_space: false`（unknown 即 free） | ❌ 语义破坏：膨胀层无 unknown 边界、AMCL 无关但 planner 更激进——不推荐 |
| c'. 给 local 开 track_unknown | local `track_unknown_space: true` → 未观测变灰 → MPPI 侧 +300/格罚分与出图判死全部生效（保守探入，替代现状"未观测=free"的激进默认） | 源级推演的可行保守化手段，**未实测**：行为全面变保守、inflation 与灰交互未知——须先实测"岔路慢"主导项再决定 |

> 结论：灰格（global）= 全局路径"高代价可通行格"的正常表达（NavFn 绕灰语义），local 无灰格；
> 嫌慢/嫌绕走 b（预扫）最稳；现状 local"未观测=free"是激进默认（Q2 盲区撞车结构同源），
> 保守化方向 = c' 而非 c。

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

## 来源（2026-09-06 WebSearch + humble 源码核实）

**WebSearch 核实**：

- [Nav2 Environmental Representation（unknown/free/occupied/inflated）](https://docs.nav2.org/rolling/getting_started/navigation_concepts/environmental_representation/)
- [Configuring MPPI（官方参数 + 视野/costmap 尺寸提醒）](https://docs.nav2.org/configuration/packages/configuring-mppic.html)
- [nav2_mppi_controller motion_models.xml（GitHub）](https://github.com/ros-navigation/navigation2/blob/main/nav2_mppi_controller/motion_models.xml)
- [CostCritic 类文档（jazzy：is_tracking_unknown 等）](http://docs.ros.org/en/jazzy/p/nav2_mppi_controller/generated/classmppi_1_1critics_1_1CostCritic.html)
- [Issue #5668 非圆足迹后部近碰漏罚讨论](https://github.com/ros-navigation/navigation2/issues/5668)
- [Robotics SE：track_unknown_space / allow_unknown 实践](https://robotics.stackexchange.com/questions/107594)
- [Smac 2D planner 配置（allow_unknown）](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/planners_plugins/smac/smac_2d/configuring_smac_2d/)

**humble 分支源码逐行核实（§1.3/§1.4-c 结论依据）**：

- [cost_critic.cpp（score L121-181 / inCollision L188-212 / costAtPose）](https://github.com/ros-navigation/navigation2/blob/humble/nav2_mppi_controller/src/critics/cost_critic.cpp)
- [footprint_collision_checker.cpp（足迹轮廓逐格检查 / 出界判 LETHAL）](https://github.com/ros-navigation/navigation2/blob/humble/nav2_costmap_2d/src/footprint_collision_checker.cpp)
- [costmap_2d_ros.cpp L97（track_unknown_space 默认 false）](https://github.com/ros-navigation/navigation2/blob/humble/nav2_costmap_2d/src/costmap_2d_ros.cpp#L97)
- [obstacle_layer.cpp L73-116（track_unknown_space → default_value NO_INFORMATION/FREE）](https://github.com/ros-navigation/navigation2/blob/humble/nav2_costmap_2d/plugins/obstacle_layer.cpp#L73-L116)
- [navfn.cpp L246-291（unknown 格 → allow_unknown ? COST_OBS−1 : 障碍）](https://github.com/ros-navigation/navigation2/blob/humble/nav2_navfn_planner/src/navfn.cpp#L246-L291)
- [navfn_planner.cpp L88（allow_unknown 默认 true）](https://github.com/ros-navigation/navigation2/blob/humble/nav2_navfn_planner/src/navfn_planner.cpp#L88)
- [PR #4174 "45% performance improvement in MPPI"（isTrackingUnknown consult 重构前后均存在）](https://github.com/ros-navigation/navigation2/pull/4174)

> 未实测标注：Q1.3 降速主导项（a 绕行 vs b 节流）为候选收敛，判定留录包实测；Q2 数量级（0.11m 超界）
> 为几何估算待实测；c'（local 开 track_unknown）为源级推演未实测；IMU 阈值待撞箱 bag 验证。
