# 双雷达（LD06 ×2）兼容调研 —— 老车 S2 层面

> **日期**：2026-11-18
> **任务**：在 S1 单 LD06 链路基础上，核对老车 S2「双 LD06（一高一低）」与现有驱动 / launch / TF / SLAM / Nav2 / explore 栈的兼容性，列出拓扑选项、风险与待实测项。
> **状态**：调研完成；**未实测项逐条标注**，不把“机制支持”写成“已验证”。
> **范围**：老车 R2-OLD，LD06 ×2；不含新车 VLP-16/MID-70 双雷达线（见 [planning-control-roadmap.md](../roadmaps/planning-control-roadmap.md) §3.3）与机械结构设计。
> **核实方式**：本地知识库优先（`doc/old-car`、`doc/surveys`、`retrospect`、仓内 launch/config 代码）；**本次未新增 WebSearch/WebFetch**，外部结论沿用 2026-11-07 [exploration-prior-map-survey](exploration-prior-map-survey.md) 已核实链接（📘/🌐），未重新外搜。
> **关联**：[ld06-dual-lidar.md](../old-car/ld06-dual-lidar.md) ｜ [s1-readiness-gap.md](../old-car/s1-readiness-gap.md) ｜ [old-car/startup.md](../old-car/startup.md) ｜ [two-car-architecture.md](../two-car-architecture.md) ｜ [explore-plan.md](../minimal-loop2/explore-plan.md) ｜ [exploration-prior-map-survey.md](exploration-prior-map-survey.md)
> **证据等级**：✅ 本地/实机实测 ｜ 📘 官方源码/文档 ｜ 🌐 论文/社区 ｜ 🧠 工程推理（未实测，不作结论用）

---

## 〇、结论先行

**1）总体判断**：现有 S1 栈在**分开话题拓扑**下与第二颗 LD06 兼容——驱动多实例、udev、TF、话题隔离已经实测；Nav2 costmap 多观测源有现成模板；explore_lite 只读 global costmap，不需要改代码。**改动集中在配置层**（launch 覆盖 + Nav2 低带层 + 第二颗几何/udev），不需要改现有包源码。

**2）但有四个前提必须先处理：**

| # | 前提 | 影响 | 现状 |
|:--|:---|:---|:---|
| 1 | **S2 的低物价值目标要先定义** | 第一颗 LD06 扫描平面离地 **0.16 m**（z=0.040 + base_link 0.12）；0.35 m 箱体跨 0–0.35 m，**该平面本身就能与箱体相交**。若 S2 验收仍用 0.35 m 箱，单雷达已能看见，低装收益无法体现；S2 主要增量是 **<0.16 m 目标** | 🧠 纸面几何；未实测 |
| 2 | **双实例 + 过滤链尚未复测** | 11-06 双实例测试早于 11-08 过滤链；11-08 全链为单实例。过滤节点名写死 `scan_to_scan_filter_chain`，双实例会同名 | ✅ 单实例过滤已验证；双实例组合 ❌ 未测 |
| 3 | **SLAM 单 scan 是拓扑分水岭** | `slam_toolbox_mapping.yaml` 只有 `scan_topic: /scan`；合并第二颗需外部合并包，且无硬件同步 | ✅ 配置事实；合并方案 ❌ 未实测 |
| 4 | **低装地面杂波可能复发 G24 零前沿** | 低雷达地面回波/假 lethal 会把自由区切碎，重演 55 连通域 → `No frontiers found` | 🧠 风险推理；未实测 |

**3）拓扑选项不替你选**：分开 `/scan` + `/scan_low`、合并单 `/scan`、混合（合并只喂 costmap）、单颗低装，四者的影响见 §四；本地既有倾向是分开（[exploration-prior-map-survey O2](exploration-prior-map-survey.md)、[平台分叉卡③](../retrospect/2026-11-06_platform_split_old_retrofit.md#L215)）。

---

## 一、范围、方法与证据等级

### 1.1 调研边界

| 维度 | 覆盖 | 不覆盖 |
|:---|:---|:---|
| 平台 | 老车 LD06 ×2（一高一低或同高） | 新车 VLP-16/MID-70 双雷达线、机械结构/供电选型 |
| 层面 | 驱动多实例、launch、TF、时间同步、SLAM、Nav2 costmap、explore、算力、互扰、几何、验收 | 具体控制算法调参、新场地泛化 |
| 数据 | 本仓既有实测/配置/代码 | 本次新增实车实验（未做） |

### 1.2 方法

- 本地：逐份读 `doc/old-car/` 三份、`doc/surveys/` 双雷达相关段、[two-car-architecture.md](../two-car-architecture.md) §三/§十、[explore-plan.md](../minimal-loop2/explore-plan.md) §十、相关 retrospect。
- 代码：读 [ld06.launch.py](../../ldlidar_stl_ros2/launch/ld06.launch.py)、[ld06_scan_filter.yaml](../../ldlidar_stl_ros2/config/ld06_scan_filter.yaml)、[nav2_params_ld06.yaml](../../r2_bringup/config/nav2_params_ld06.yaml)、[nav2_params_low.yaml](../../r2_bringup/config/nav2_params_low.yaml)（legacy 低带层模板）、[slam_toolbox_mapping.yaml](../../r2_bringup/config/slam_toolbox_mapping.yaml)、[explore_params.yaml](../../r2_bringup/config/explore_params.yaml)。
- 外部：本次**未新增检索**；`ira_laser_tools` 官方/社区分支、LD06 无同步引脚等结论沿用 2026-11-07 survey 的已核实链接（§八）。

### 1.3 证据等级

- ✅：本仓实机/VM 实测、原始日志、既有 bag 分析结论，可直接引用。
- 📘：官方源码/README/产品文档，版本与日期已核。
- 🌐：论文/社区/第三方，作者自报或未复现，引用保留限定语。
- 🧠：基于事实的工程推理，**不是实测结论**；落地前需验证。

---

## 二、现状基线（回指，不复制细节）

> 本节只列与双雷达兼容判断直接相关的基线；完整执行记录/验收见各源文档。

| 基线项 | 状态 | 证据 |
|:---|:---:|:---|
| 双实例并发 10 Hz | ✅ | N97 `/scan_a` 10.000 Hz、`/scan_b` 10.002 Hz（2026-11-06）+ 重启复验（11-07）— [ld06-dual-lidar P2/P3/P6](../old-car/ld06-dual-lidar.md#L136) |
| 数据隔离/无混流 | ✅ | 遮挡 A 不影响 B、反向同样；两路各 1 Publisher — [同上 P2](../old-car/ld06-dual-lidar.md#L136) |
| udev 固定名 | ✅ | VM/N97 四路；第二颗已有 `/dev/r2_ld06_b` — [同上 P3](../old-car/ld06-dual-lidar.md#L190) |
| `/scan` 规格 | ✅ | 10 Hz、452–455 beam/圈、0.793–0.798°、crop 机制 — [同上 P7](../old-car/ld06-dual-lidar.md#L275) |
| 第一颗安装几何 | ✅ | x=0.275 / y=0.290 / z=0.040 / yaw=−1.5708；yaw 实物复核 — [sensor-mount §6.1](../phase0/sensor-mount.md) |
| 自车回波过滤 | ✅ 单实例 | `scan_raw → scan_to_scan_filter_chain → scan`；车体多边形 — [sensor-mount §6.1.2](../phase0/sensor-mount.md)、[filter yaml](../../ldlidar_stl_ros2/config/ld06_scan_filter.yaml) |
| S1 全链导航 | ✅ | 2026-11-08 39/39 目标成功 — [retrospect 11-08](../retrospect/2026-11-08_oldcar_s1_fullchain_pass.md) |
| S1 未收口项 | ❌ | explore 复测/覆盖率/N97 负载/急停/EKF 基线/换场地 — [s1-readiness-gap §八](../old-car/s1-readiness-gap.md#L194) |

---

## 三、分层兼容核对

### 3.1 总览

| 层面 | 结论 | 依据/缺口 |
|:---|:---:|:---|
| 驱动/多实例 | ✅ 已验证 | 双实例 10 Hz；数据隔离；udev |
| 串口/供电 | 🟡 串口已验证；双雷达带载未测 | G14 单雷达 25 min；P6-4 待测 |
| TF/frame | ✅ 机制支持 | 每实例独立 static TF |
| 话题/QoS | ✅ 独立话题 | RELIABLE/VOLATILE；过滤输出需显式命名 |
| 自车过滤 | 🟢 可复用，需按装位复测 | polygon 在 `base_link` |
| launch 硬化 | 🟡 3 处写死 | filter 节点名 / crop / 配置路径 |
| 时间同步 | ❌ 无硬件同步 | LD06 无 PPS/触发 |
| SLAM | ⚠️ 单 scan 输入 | `scan_topic` 单一 |
| Nav2 costmap | 🟢 多源模板存在 | legacy `velodyne_low` 层 |
| explore | ✅ 间接兼容 | 只读 global costmap |
| 算力/带宽 | 🟡 预期轻，未测 | 2×4.5k 点/s vs VLP-16 ~300k |
| 光学互扰 | 🟡 仅 VM 初筛 | P5 无量化 |
| 几何/低物价值 | ❌ 第二颗未量测；目标高度未定义 | 见 §五-1 |
| 验收 | ❌ 指标未量化 | S2 判据定性 |

图例：✅ 已验证 ｜ 🟢 机制支持、配置即可 ｜ 🟡 需实测或需设计 ｜ ❌ 结构约束或缺失。

### 3.2 驱动 / 实例层

- ✅ **双实例已验证**：两颗 LD06 同时跑、话题/frame 独立、各 1 Publisher；udev 按 J-Link serial 固定（[P2/P3](../old-car/ld06-dual-lidar.md#L136)）。
- ✅ **第二颗硬件已在手**：LD06-B serial `000063728647` → `/dev/r2_ld06_b`；S2 不需要新增采购/udev（可选加 `r2_ld06_low` 别名）。
- ⚠️ **双实例 + 过滤链未复测**：11-06 双实例测试无过滤节点；11-08 过滤链加入后只跑单实例。过滤节点名写死 `scan_to_scan_filter_chain`（[launch:113](../../ldlidar_stl_ros2/launch/ld06.launch.py#L113)），双实例会起两个同名节点；话题已按实例重映射，数据通路应隔离，但 `ros2 node list`/`param`/诊断指向不确定；若第二颗需要不同过滤参数，当前 launch 无法区分。
- ⚠️ **`topic_name` 与 `filtered_topic_name` 都要覆盖**：raw 默认 `scan_raw`、filtered 默认 `scan`；双实例漏改任一都会双发布。现有文档只强调 filtered 一项。
- ⚠️ **crop 参数写死**：`enable_angle_crop_func=False`、`angle_crop_min/max=135/225`（[launch:88-91](../../ldlidar_stl_ros2/launch/ld06.launch.py#L88-L91)）；低装若需角度屏蔽，须改 launch 或在 filter chain 加 `LaserScanAngularBoundsFilter`。
- ⚠️ 驱动主循环不 spin 参数服务，`ros2 param set` 不可用；过滤/几何参数只能启动时定（[README_R2](../../ldlidar_stl_ros2/README_R2.md)）。
- 同型号 LD06 ×2 已验证；若未来混用 LD19/STL27L，`product_name` 目前写死在 launch（[launch:83](../../ldlidar_stl_ros2/launch/ld06.launch.py#L83)），需另参数化——S2 不涉及。

### 3.3 TF / frame

- ✅ 每实例一个 `base_link → <frame>` 静态 TF，节点名随 frame 派生（`base_link_to_<frame>_ld06`），不重名；`base_link` 多子帧无冲突。
- 🟡 **命名未冻结**：双实例测试用 `/scan_a`+`laser_a`、`/scan_b`+`laser_b`；S2 文档写 `/scan_low`+`laser_low`。写 Nav2/launch 配置前需先冻结一套，否则下游引用分裂。建议（仅陈列，不替选）：若一高一低，用 `/scan`+`base_laser`（高）与 `/scan_low`+`laser_low`（低）语义最清晰；若同高，用 `/scan_a/b`。
- 🟡 第二颗几何 x/y/z/yaw/pitch/roll 未量测；低装 pitch/roll 不能沿用 G10 的“按 0 处理”（见 §3.9）。

### 3.4 时间同步

- ❌ **结构约束**：LD06/LD19 只有 UART + PWM + 5V/GND，没有 PPS/触发/同步引脚；多台各自自由旋转，无法相位锁定（📘/🌐，沿用 [exploration-prior-map-survey §5.1](exploration-prior-map-survey.md#L425-L428)）。
- **分开话题**：不需要同步——每条 scan 按自己的 stamp + 静态 TF 独立进 costmap/SLAM；这是分开拓扑的核心兼容优势。
- **合并单帧**：必须接受 0–100 ms 时间差与运动畸变；旋转时两个平面的点会在时间上错位。合并节点通常按最后到达的消息/固定频率输出，进一步引入陈旧数据——未实测。

### 3.5 SLAM

- ✅ 现状：[slam_toolbox_mapping.yaml](../../r2_bringup/config/slam_toolbox_mapping.yaml#L37) 只有 `scan_topic: /scan`；ROS2 slam_toolbox 按单 scan 输入组织，当前配置未见多 scan 输入参数。
- **方案 A（分开）**：高雷达 `/scan` → slam_toolbox + Nav2；低雷达 `/scan_low` → Nav2 低带层。**SLAM 配置零改动，地图质量不受第二颗影响**。
- **方案 B（合并）**：需引入合并节点，把两路转成一条 `/scan` 再喂 SLAM。风险：
  - 无硬件同步 → 时间差/运动畸变（§3.4）；
  - 不同高度混叠 → 低平面地面杂波/假墙进入 `/map`，直接冲击 S2“地图质量不显著下降”判据；
  - LD06 逐帧 beam 数 452–455、`angle_increment` 逐帧变化 → 合并节点需重采样，不能假设固定 360 线；
  - `angle_min=0` / `angle_max=360` 方向重复 → 合并需处理重复角；
  - 过滤后的 NaN、QoS、消息 stamp 语义需逐项验证。
  - 本地调研已核实：`ira_laser_tools` 官方仅 ROS1，Humble 只有社区 fork（[nakai-omer humble 分支](https://github.com/nakai-omer/ira_laser_tools/tree/humble)），无官方二进制，需源码构建，**本项目未实测**（[survey](exploration-prior-map-survey.md#L425-L428)）。
- **方案 B'（混合）**：合并只用于 costmap，SLAM 仍吃高雷达 `/scan`——保护地图质量，但仍需合并节点与时间差验证。

### 3.6 Nav2 / costmap

- ✅ **多源机制已验证**：legacy [nav2_params_low.yaml](../../r2_bringup/config/nav2_params_low.yaml#L250) 的 local `voxel_layer` 有 `observation_sources: "scan velodyne_low"`，global 另有独立 `obstacle_low_layer`（[L319-L332](../../r2_bringup/config/nav2_params_low.yaml#L319-L332)）——这是第二颗 scan 接入 costmap 的现成模板。
- 当前 [nav2_params_ld06.yaml](../../r2_bringup/config/nav2_params_ld06.yaml#L265) 已删低带源/低带层（[L292](../../r2_bringup/config/nav2_params_ld06.yaml#L292)）；S2 需重新加回，**纯配置改动**。
- **必须加到 global**，不能只加 local：09-06 撞箱实锤 local 254 / global 无 → planner 不避障（[retrospect 09-06](../retrospect/2026-09-06_lowobstacle_fixB_crashbox.md)）。
- **层设计选项**（待实测定夺）：
  - 与高 scan 同层 → 09-06 教训：高 scan 的 raytrace clear 会清掉低带 mark，**不建议**；
  - 独立层 + `marking: true / clearing: false`（legacy 模板）→ 保守，但物移走后 mark 残留到 costmap 重置；
  - 独立层 + `clearing: true` → 低雷达自清，但需验证 09-08 的 **global 整层 ClearEntirely** 事件与自身 raytrace 语义（[retrospect 09-08 secondfail](../retrospect/2026-09-08_lowobstacle_secondfail_clearevent.md)）。
- **LaserScan 高度语义**：scan 平面就是其安装高度；`min/max_obstacle_height` 只需覆盖该平面，**不要照抄 PointCloud2 的 0–0.40 m 高度带**。
- Humble 的 `observation_sources` 用空格分隔字符串（list 型会在 configure 报类型错，见 legacy 文件注释）。
- **地面杂波**：低装 + 微小 pitch 就会引入地面回波；可在 filter chain 加 range/angular filter，或在 costmap 用 `obstacle_min_range` 拒绝近距回波——但后者可能误伤真实近距低物，需实测定。

### 3.7 explore_lite

- ✅ 间接兼容：[explore_params.yaml](../../r2_bringup/config/explore_params.yaml#L40) 只读 `costmap_topic: /global_costmap/costmap`，不直接订阅 scan；第二颗雷达通过 global costmap 影响前沿/规划，**无代码改动**。
- 低物进入 global costmap 后，explore 会把它当障碍避开——正是 S2 想要的效果。
- ⚠️ **最大应用层风险**：低装雷达的地面杂波/假 lethal 会把自由区切碎 → 重演 G24「55 个连通域 → `No frontiers found`」（[retrospect 11-08 chain rerun](../retrospect/2026-11-08_oldcar_s1_chain_rerun_selfocclusion.md)）。自车多边形过滤只管车体内，地面回波在车体外仍需额外过滤（range/angular filter 或调平）。

### 3.8 算力 / 带宽

- 🧠 2×~4.5k 点/s ≈ 9k 点/s，远低于 VLP-16 的 ~300k 点/s；两个 filter 节点 + 一个额外 costmap 源，预期很轻。
- 但 S1 第 8 项 N97 负载基线**未采**（[s1-readiness-gap §八](../old-car/s1-readiness-gap.md#L194)）；S2 应同窗口采 `/scan`、`/scan_low` hz + CPU + 节点存活。
- USB 侧：两个 J-Link 12 Mbps / 230400 baud 已并发验证；瓶颈在供电不在带宽。

### 3.9 光学互扰 / 几何

- **互扰**：P5 仅 VM 同高度初筛、无量化数据（[P5](../old-car/ld06-dual-lidar.md#L244)）；低装不同高度可能降低互扰，但不能假设为零；实车需 A 单开 / B 单开 / 双开三组对比（ranges 分布、鬼影簇、丢帧）。
- **第二颗几何**：x/y/z/yaw/pitch/roll 未量测。低装 **pitch 是关键**：水平 2D 扫描在高度 h、下俯 θ 时，地面命中距离 `d = h / tanθ`（h=0.10 m：1°→5.7 m，2°→2.9 m，5°→1.1 m；🧠 纸面几何，公式同 [ros2-ops §12.1](../ros2-ops.md)）。G10 的 pitch/roll 按 0 处理，低装不能沿用。
- **自车过滤复用**：`LaserScanPolygonFilter` 的 polygon 在 `base_link`、车体相对 → 同一车上的任意雷达可复用同一份配置（低雷达的自车回波也落在车体矩形内）。但当前 polygon x[−0.45,+0.40]/y±0.34 与 footprint ±0.42/±0.33 **未完全对齐**（[filter yaml 注](../../ldlidar_stl_ros2/config/ld06_scan_filter.yaml#L32-L35)），第二颗装位不同可能暴露新的自车回波区（保险杠/支架），需按装位复测。
- **S2 低物价值前提**：第一颗扫描平面离地 **0.16 m**（z=0.040 + base_link 0.12）；0.35 m 箱体跨 0–0.35 m → 该平面本身能与箱体相交，**单雷达已能看见 0.35 m 箱**（过滤多边形外、量程内）。S2 低装的增量主要是 **<0.16 m 目标**（地面线缆、10 cm 块等）。若验收仍用 0.35 m 箱，低装收益无法体现——S2 判据必须先定义目标高度（🧠 纸面几何，未实测）。

### 3.10 验收

- S2 判据（[two-car §3.4](../two-car-architecture.md#L108)）：低物可见；SLAM 地图质量不显著下降；地面杂波可控；双串口不掉线。
- 目前全是定性描述，**缺量化阈值**：目标高度/距离、地图质量指标、杂波率、掉线时长、互扰指标均未定。
- S1 未收口 → S2 的同场地/同路径 A/B 基线还没有；按 [standards §1.15](../standards.md)，单场景 PASS ≠ 场景闭环。

---

## 四、拓扑选项与影响

| 方案 | 数据流 | 对现有栈的改动 | 兼容性 | 主要风险 |
|:---|:---|:---|:---:|:---|
| **A 分开** | 高 `/scan` → slam_toolbox + Nav2；低 `/scan_low` → Nav2 低带层 | launch 覆盖 + Nav2 参数 + udev/几何；**无代码改动** | 最高 | 低带层设计、地面杂波 |
| **B 合并** | merger → `/scan` → 现有栈 | 新增合并包/配置；现有包不改 | 中 | 无同步、高度混叠、beam 数变化、外部包未实测 |
| **B' 混合** | merger → `/scan_merged` → costmap；高 `/scan` → SLAM | 新增 merger + costmap 参数 | 中 | 同 B，但 SLAM 不受污染 |
| **C 单颗低装** | 单颗低雷达 → `/scan` → 现有栈 | 只改几何 | 高（但无第二颗） | 建图平面低、地面杂波、无冗余 |

> 本地既有倾向是 **A**（[survey O2](exploration-prior-map-survey.md)、[平台分叉卡③](../retrospect/2026-11-06_platform_split_old_retrofit.md#L215)）；本节只陈列影响，不替你做决定。

---

## 五、关键发现（相对现有文档新增/需注意）

1. **S2 的低物价值前提要重新定义**：第一颗 16 cm 平面已能与 0.35 m 箱相交；S2 增量主要是 <0.16 m 目标。验收目标高度必须先定，否则低装收益无法体现（🧠）。
2. **双实例 + 过滤链未复测**：11-06 双实例测试无过滤节点；11-08 加过滤后只跑单实例。双实例下两个 `scan_to_scan_filter_chain` 同名，是新的未验证点。
3. **launch 有三处写死**：filter 节点名、crop 参数、过滤配置路径——分开拓扑“配置即可”成立，但若第二颗需要不同过滤/角度屏蔽，要先做 launch 硬化。
4. **过滤 polygon 可复用但不能盲用**：`base_link` 系车体多边形对任意车载雷达通用；但当前 polygon 与 footprint 未完全对齐，第二颗装位可能漏过滤。
5. **slam_toolbox 单 scan**：这是“分开 vs 合并”的结构分水岭；分开方案对 SLAM 零改动，合并方案要引入外部包并承担时间/高度/元数据风险。
6. **Nav2 低带层有现成模板**：legacy `obstacle_low_layer` 可直接改写为 `scan_low` 源；当前 LD06 参数已删掉该层，S2 是“重新加回”而非从零设计。
7. **合并方案的元数据坑**：LD06 逐帧 beam 数 452–455、`angle_increment` 逐帧变化、`angle_min=0/angle_max=360` 方向重复——合并节点必须重采样/处理重复角，不能假设固定 360 线。
8. **低装 pitch 比高装敏感得多**：`d = h/tanθ`，10 cm 高度下 1° 下俯就在 5.7 m 处打地；低装必须实测/调平 pitch、roll，不能沿用 G10 的“按 0 处理”。
9. **G24 失败模式可能复发**：低装雷达的地面杂波若进入 global costmap，会把自由区切碎，重演 explore 零前沿。
10. **文档一致性提示（已修）**：[ld06-dual-lidar P1 参数表](../old-car/ld06-dual-lidar.md#L108-L120) 原把 `topic_name` 默认写成 `scan`，当前 launch 实际是 `scan_raw`；本文落地时已一并修正，并补 `filtered_topic_name` 行。

---

## 六、待实测 / 待量化清单

| # | 项 | 方法 | 判据/产出 | 状态 |
|:--|:---|:---|:---|:---:|
| 1 | 第二颗安装几何 | 同 G10 方法量 x/y/z/yaw/pitch/roll；箱体复核 yaw | 数值回填 launch；pitch/roll 实测 | ❌ |
| 2 | 低装自车遮挡 | 单开低雷达，统计车体矩形内回波数 | 漏过滤点 = 0 或已知可接受 | ❌ |
| 3 | 地面杂波 | 静止空场地，记录不同 pitch 下近距回波 | 杂波距离/数量 vs `d=h/tanθ` 对账 | ❌ |
| 4 | 双雷达互扰 | A 单开/B 单开/双开各 60 s，三组 ranges 分布对比 | 无系统性鬼影/整体偏移/频繁丢帧 | ❌（仅 VM 初筛） |
| 5 | 双雷达供电 | 两路 5V 带载测 PSV，≥30 min | 4.5–5.5 V，无掉电/重连 | ❌（单雷达 25 min） |
| 6 | Nav2 低带层 | 0.1 m 目标放在 0.3/0.5/1.0/2.0 m，读 global/local `costmap_raw` | 目标格 254，planner 绕行 | ❌ |
| 7 | explore 复测 | S2 链路上跑 explore_lite | 无 `No frontiers found`，自由区连通 | ❌ |
| 8 | N97 负载 | 双 scan hz + CPU + 节点存活 | 与 S1 基线对比 | ❌ |
| 9 | SLAM 质量 | 同场地/同路径 S1 vs S2 对比 | 墙段连续、无地面假墙 | ❌ |
| 10 | 验收阈值 | 目标高度/距离、地图指标、杂波率、掉线时长 | 用户定夺后写进 S2 判据 | ❌ |
| 11 | 双实例 + 过滤链 | 两颗同时起，检查 node list/话题/频率 | 无双发布、节点名/参数可区分 | ❌ |
| 12 | 合并拓扑（如选） | 源码构建 `ira_laser_tools` Humble fork 或替代包 | 时间差/重采样/QoS/NaN 逐项验证 | ❌ |

---

## 七、未实测与待核实

| 项 | 状态 | 说明 |
|:---|:---:|:---|
| 第二颗 LD06 安装几何 | ❌ 未测 | x/y/z/yaw/pitch/roll 全部待量 |
| 双实例 + 过滤链 | ❌ 未测 | 11-06 双实例早于 11-08 过滤链 |
| 低装地面杂波 | ❌ 未测 | 仅纸面公式 `d=h/tanθ` |
| 双雷达带载供电 | ❌ 未测 | 单雷达 25 min；P6-4 仍开口 |
| 双雷达互扰量化 | ❌ 未测 | P5 仅初筛、无三组分布 |
| N97 双 scan 负载 | ❌ 未测 | S1 第 8 项也未采 |
| Nav2 低带层行为 | ❌ 未测 | 有 legacy 模板，但 LD06 `scan_low` 未配 |
| explore + 低带层 | ❌ 未测 | 依赖上项 |
| 合并拓扑 | ❌ 未测 | `ira_laser_tools` Humble fork 未构建 |
| S2 验收阈值 | ❌ 未定 | 目标高度/地图指标/杂波率/掉线时长 |
| 16 cm 平面看见 0.35 m 箱 | 🧠 纸面几何 | 未实车验证；过滤多边形外、量程内前提 |
| 低装 pitch 对地面回波的影响 | 🧠 纸面几何 | 未实车验证 |

---

## 八、来源（2026-11-18 核实方式）

### 8.1 本地文档/实测（✅）

- [ld06-dual-lidar.md](../old-car/ld06-dual-lidar.md) — 双实例/udev/规格/互扰初筛
- [s1-readiness-gap.md](../old-car/s1-readiness-gap.md) — S1 缺口与 §八 剩余验收
- [old-car/startup.md](../old-car/startup.md) — 老车启动序列（终端 0–8）
- [two-car-architecture.md](../two-car-architecture.md) — S2 定义、TF 契约、开放决策
- [explore-plan.md](../minimal-loop2/explore-plan.md) — 探索方案/§十双雷达拓扑（2026-11-18 迁出至本文）
- [exploration-prior-map-survey.md](exploration-prior-map-survey.md) — 2D/3D 方案、多雷达同步、`ira_laser_tools` 现状
- [sensor-mount.md §6.1](../phase0/sensor-mount.md) — 第一颗几何/过滤/装位
- [retrospect 2026-11-06_ld06_vm_bringup_smoke.md](../retrospect/2026-11-06_ld06_vm_bringup_smoke.md) — 双实例冒烟
- [retrospect 2026-11-08_oldcar_s1_fullchain_pass.md](../retrospect/2026-11-08_oldcar_s1_fullchain_pass.md) — 39/39 全链
- [retrospect 2026-11-08_oldcar_s1_chain_rerun_selfocclusion.md](../retrospect/2026-11-08_oldcar_s1_chain_rerun_selfocclusion.md) — G24 零前沿根因
- [retrospect 2026-09-06_lowobstacle_fixB_crashbox.md](../retrospect/2026-09-06_lowobstacle_fixB_crashbox.md) — local/global 分层教训
- [retrospect 2026-09-08_lowobstacle_secondfail_clearevent.md](../retrospect/2026-09-08_lowobstacle_secondfail_clearevent.md) — global 整层 clear 事件

### 8.2 仓内代码/配置（📘）

- [ld06.launch.py](../../ldlidar_stl_ros2/launch/ld06.launch.py) — 12 个 launch 参数、过滤节点、crop 写死
- [ld06_scan_filter.yaml](../../ldlidar_stl_ros2/config/ld06_scan_filter.yaml) — `base_link` 多边形/padding/修订记录
- [nav2_params_ld06.yaml](../../r2_bringup/config/nav2_params_ld06.yaml) — 当前单 scan 源、低带层已删
- [nav2_params_low.yaml](../../r2_bringup/config/nav2_params_low.yaml) — legacy 多源/`obstacle_low_layer` 模板
- [slam_toolbox_mapping.yaml](../../r2_bringup/config/slam_toolbox_mapping.yaml) — `scan_topic: /scan`
- [explore_params.yaml](../../r2_bringup/config/explore_params.yaml) — `costmap_topic` 配置

### 8.3 外部来源（📘/🌐，沿用 2026-11-07 survey，未重新外搜）

- [ldlidar_stl_ros2 上游仓库](https://github.com/ldrobotSensorTeam/ldlidar_stl_ros2) — LD06 驱动/协议
- [m-explore-ros2（explore_lite）](https://github.com/robo-friends/m-explore-ros2) — 探索节点
- [ira_laser_tools Humble 分支](https://github.com/nakai-omer/ira_laser_tools/tree/humble) — 社区 fork，无官方二进制
- [LD06 无硬件同步结论](exploration-prior-map-survey.md#L425-L428) — 本地 survey 已核实的 UART/PWM/5V 引脚事实

> 本次未新增 WebSearch/WebFetch；如需对合并工具/最新 ROS2 替代方案做外网核实，按 [standards §1.13](../standards.md) 另存轻量档或更新本文。

---

## 九、变更记录

| 日期 | 变更 | 说明 |
|:---|:---|:---|
| 2026-11-18 | 初稿 | 基于 2026-11-09 前的 S1/S2 文档与仓内代码核对；未新增外搜/实测 |

---

## 相关

- 老车执行：[ld06-dual-lidar.md](../old-car/ld06-dual-lidar.md) ｜ [s1-readiness-gap.md](../old-car/s1-readiness-gap.md) ｜ [old-car/startup.md](../old-car/startup.md)
- 架构/方案：[two-car-architecture.md](../two-car-architecture.md) ｜ [explore-plan.md](../minimal-loop2/explore-plan.md) ｜ [exploration-prior-map-survey.md](exploration-prior-map-survey.md)
- 规范：[standards.md](../standards.md)（§1.11 来源、§1.13 留档、§1.15 验收）｜ [ros2-ops.md](../ros2-ops.md)（§12 感知覆盖判据）
