# 老车 S1 就绪差距清单（Gap List）

> 日期：2026-11-06
> 定位：老车 S1（单 LD06 + slam_toolbox + Nav2 + explore_lite，5×5m 首测）开工前的**缺口盘点**——
> 只列「缺什么 / 现状证据 / 影响 / 落位」，**方案细节不在此复制**（见 [explore-plan.md](../minimal-loop2/explore-plan.md)）。
> 状态：盘点完成，**未开始实施**；缺口随落地逐项勾销（本文只增不删，销项改状态列）。
> 核实方式：2026-11-06 在 VM 与 N97 做只读核对（`ls` / `grep` / `ros2 pkg list` / `git ls-remote`），
> 每条附证据位置；**未实测项已显式标注**，不把"方案里写了"当成"已经具备"。
> 更新：2026-11-07 补测 LD06 `/scan` 规格与 angle crop（G11 部分销项、§三新增实测行），其余缺口状态不变。
> 相关：[two-car-architecture.md §三](../two-car-architecture.md)（S1 判据）｜[07-handover.md §五](../07-handover.md)（老车接手注意）｜
> [ld06-dual-lidar.md](ld06-dual-lidar.md)（雷达接入执行计划）

---

## 一、S1 边界（先对齐，防摊大）

| 项 | 内容 |
|:---|:---|
| 目标 | 单 LD06（正常高度）+ slam_toolbox 实时建图 + Nav2（去 AMCL/map_server）+ explore_lite 前沿探索 |
| 判据 | `/scan` 稳定；地图无重影；Nav2 Goal 可达；**覆盖率 >80%（5×5m ROI）**；无碰撞；**EKF 输出与 G354 基线一致** |
| 保留 | G354 + 现有 EKF 不动（S3 才换 STM32）；`/odometry/filtered`、`odom→base_link` 契约不变 |
| 不包含 | 低物可见性（S2）、双雷达融合（S2）、全速参数、新场地泛化 |

> 判据原文见 [two-car-architecture.md:107](../two-car-architecture.md#L107)；逐项验收方法见
> [explore-plan.md §四](../minimal-loop2/explore-plan.md)。

---

## 二、缺口清单

### 2.1 软件资产

| ID | 缺口 | 现状证据（2026-11-06 核对） | 影响 | 级别 |
|:---|:---|:---|:---|:---:|
| G1 | `r2_bringup/config/slam_toolbox_mapping.yaml` 不存在 | VM 与 N97 的 `r2_bringup/config/` 均只有 `dds/ ekf.yaml nav2_params_low.yaml nav2_params.yaml r2_params.yaml`；方案给出参数草案（[Step 1.1](../minimal-loop2/explore-plan.md)），**未实测** | 无建图参数，slam_toolbox 只能用官方默认（`base_footprint` + `use_sim_time: true`，R2 会直接不工作） | P0 |
| G2 | `r2_bringup/launch/nav2_explore.launch.py` 不存在 | launch 目录只有 `chassis` / `ekf` / `nav2` 三个 | 无法起"去定位层"的 Nav2 | P0 |
| G3 | `r2_bringup/config/explore_params.yaml` 不存在 | 同上 config 列表；方案给草案（[Step 3.2](../minimal-loop2/explore-plan.md)） | explore_lite 只能吃官方 `params.yaml`（订阅 `/map` 直连，与 Nav2 代价地图链路不匹配） | P0 |
| G4 | **老车专用 Nav2 参数文件缺失**（方案口径冲突） | 现有 `nav2_params_low.yaml` 的 local `voxel_layer` 与 global `obstacle_low_layer` 均订阅 `/velodyne_points`（[L250](../../r2_bringup/config/nav2_params_low.yaml#L250)、[L269](../../r2_bringup/config/nav2_params_low.yaml#L269)、[L322-L324](../../r2_bringup/config/nav2_params_low.yaml#L322-L324)）；老车已无 VLP-16。而 explore-plan [Step 2.1](../minimal-loop2/explore-plan.md) 仍写「两种模式共用同一份参数文件」，与 [07-handover §五-2](../07-handover.md)「必须另建参数；不要直接改历史文件」**直接冲突** | 低带源无输入（是否持续告警未实测）；S1 也不做低物验收，留着纯属噪声 | P0 |
| G5 | explore_lite 源码与构建产物均无 | VM 无 `~/explore_ws`；N97 无 `~/explore_ws`；`ros2 pkg list` 两侧均无 `explore_lite` | 无前沿探索节点 | P0 |
| G6 | 覆盖率统计脚本无 | `bags/analysis/` 下无对应脚本；方案明写「脚本可后续补，本稿先定口径」（[§3.6](../minimal-loop2/explore-plan.md)） | 覆盖率判据（>80%）无法出数，只能目测 | P1 |
| G7 | `/map` 录包 QoS 覆盖文件无 | 仓内 `find` 只命中 `doc/ros2-qos-dds.md`，无 `--qos-profile-overrides-path` 用的 yaml；而方案 §3.5 要求录 `/map`（transient_local） | 首测 bag 可能录不到 `/map`，事后无法复算覆盖率 | P1 |
| G8 | `nav2.rviz` 未被安装到 share（**存量缺陷**） | `setup.py` 只 glob `config/*.yaml` 与 `config/dds/*`（[L15-L16](../../r2_bringup/setup.py#L15-L16)）；源文件 `r2_bringup/config/nav2.rviz` 存在，但 VM/N97 的 `install/.../share/r2_bringup/config/` 均**无该文件**（实测 `ls` 不存在），而 launch 用 `-d <share>/config/nav2.rviz`（[nav2.launch.py:91](../../r2_bringup/launch/nav2.launch.py#L91)） | `rviz:=true` 加载不到配置（具体表现未记录）；explore 若也要 RViz 会先撞这条 | P1 |
| G9 | `explore.rviz` / `explore_all.launch.py`（可选） | 方案 [§六](../minimal-loop2/explore-plan.md) 列为可选 | 仅影响操作便捷性 | P2 |

### 2.2 参数与几何

| ID | 缺口 | 现状证据 | 影响 | 级别 |
|:---|:---|:---|:---|:---:|
| G10 | LD06 实车安装几何未回填 | `ld06.launch.py` 默认 `z=0.18`（标注占位）、`yaw/pitch/roll=0`（[L37-L43](../../ldlidar_stl_ros2/launch/ld06.launch.py#L37-L43)）；方案要求实车量测后替换，勿沿用 0.18 | 静态 TF 与真实安装不符 → 障碍投影/地图尺度偏 | P1 |
| G11 | LD06 量程与 `slam max_laser_range: 20.0` 未对齐 | 方案 [Step 1.1](../minimal-loop2/explore-plan.md) 的 20.0 抄自 VLP-16 母本；驱动消息里 `range_max=25`（[demo.cpp:167](../../ldlidar_stl_ros2/src/demo.cpp#L167)）只是**消息字段**，不是传感器规格；LD06 实际量程本仓未落档。**2026-11-07 补测**：0.02/25 均为驱动常量，室内有效回波最大 6.08 m；**空旷场地量程/地面杂波仍未测**（[ld06-dual-lidar P7](ld06-dual-lidar.md)） | 远端边界行为不确定（截断/噪点） | P2 |
| G12 | 首测用哪颗雷达未指定 | A/B 两颗均已在 N97 跑通（[ld06-dual-lidar P6](ld06-dual-lidar.md)），S1 只需一颗 | 选错端口 → 启动即错 | P2 |

### 2.3 硬件与现场

| ID | 缺口 | 现状证据 | 影响 | 级别 |
|:---|:---|:---|:---|:---:|
| G13 | 实车安装未做 | 执行计划 [§六-3](ld06-dual-lidar.md) 仍写"待实车实测后回填（z / 俯仰 / 前后位置）"；方案 §十 亦要求"实车量安装高度后改 TF" | 没有 S1 的物理前提 | P0 |
| G14 | 车体侧 5V 供电/接头未带载实测 | 用户 2026-11-06 决定暂不做长跑（"一直在供电没问题"）；历史掉电根因 = 接线端子松动（[ld06-dual-lidar §五](ld06-dual-lidar.md)） | 首跑中途掉电 = 数据作废 | P1 |
| G15 | 5×5m 场地 / 急停 / 监护未排 | 方案 [Step 0 清单](../minimal-loop2/explore-plan.md) 要求 | 无法开跑 | P0 |
| G16 | N97 当前跑的是**双实例**（A+B） | 2026-11-06 19:21 实测 `/ld06_a`、`/ld06_b` 双节点在跑；S1 是单雷达 | 双实例同名话题冲突/资源占用 | P0 |

### 2.4 验证与数据

| ID | 缺口 | 现状证据 | 影响 | 级别 |
|:---|:---|:---|:---|:---:|
| G17 | "EKF 输出与基线一致"**没有量化阈值** | 现有基线：[startup §4.2](../startup.md)（`/odometry/filtered ~30Hz`）、[§4.3](../startup.md)（静止四元数 0.0226/0.0283/0.0172/0.9992、`z=0`、`odom→base_link` 单发布者）；S1 判据只写"一致" | 验收时无法判合格/不合格，易变成"看着差不多" | P1 |
| G18 | 复测场景未排 | [standards §1.15](../standards.md) 要求单场景 PASS 后至少换起点/换场地复测一次；方案 §四 亦注明 | 首跑 PASS 不等于收口 | P1 |
| G19 | 首测 bag 话题清单未按老车改 | 方案 §3.5 清单仍含 VLP-16 语境（"`/velodyne_points` 体积大，先不录"），老车该话题根本不存在 | 录包清单需重列，否则易漏 `/scan` 之外的探索证据 | P2 |

### 2.5 文档与流程

| ID | 缺口 | 现状证据 | 影响 | 级别 |
|:---|:---|:---|:---|:---:|
| G20 | 老车启动序列未落地 | [startup.md](../startup.md) 仍是 VLP-16 基线（仅加 11-06 注记："老车启动命令待 S1 落地后替换"） | 实车手顺无权威来源，靠临场拼 | P1 |
| G21 | README 快速启动仍是 VLP-16 | [README.md](../../README.md) 「快速启动」段为 velodyne/chassis/ekf | 新会话/交接易误用 | P2 |
| G22 | explore 方案仍是"拟稿（未实测）"且与老车前提有冲突 | [explore-plan.md](../minimal-loop2/explore-plan.md) 头部状态为「方案拟稿（未实测）」；§二 §三 为 VLP-16 口径，§十 只做增补不重写 → 冲突点即 G4 | 照方案执行会踩 G4 | P1 |
| G23 | 新参数文件命名与继承范围未定 | 07-handover 要求"另建、不改历史文件"，但没定文件名/是否继承 low 版的膨胀 0.30、速度降额 | 落地时临时命名，后续引用分裂 | P2 |

---

## 三、已完成前置（别重复补）

| 项 | 状态 | 证据 |
|:---|:---|:---|
| udev 四路固定名（N97） | ✅ | `/dev/r2_g354` / `r2_can` / `r2_ld06_a` / `r2_ld06_b` 均核到 serial（[ld06-dual-lidar §P3](ld06-dual-lidar.md)） |
| LD06 双实例 10Hz | ✅ | 2026-11-06 19:21 N97 实测 `10.000` / `10.002 Hz`，frame/Publisher 均正确（[P6-3](ld06-dual-lidar.md)） |
| slam_toolbox 已装 | ✅ | VM 与 N97 `ros2 pkg list` 均有 `slam_toolbox`；官方母本 `mapper_params_online_async.yaml` 在位 |
| N97 能拉 GitHub | ✅ | `git ls-remote m-explore-ros2` 返回 `326cf8a`（与方案引用的 commit 一致），exit 0 |
| N97 构建环境 | ✅ | `cmake 3.22.1` 仅在 `/usr/bin`（无 pip cmake 抢占），磁盘余量 54G |
| N97 仓库版本 | ✅ | 已在 `1e4accb`（本次文档批次已同步） |
| LD06 launch 参数化 | ✅ | 9 参数（node/topic/frame/port/baud/z/yaw/pitch/roll），可单实例起 |
| 新 yaml/launch 自动安装 | ✅ | `setup.py` glob `config/*.yaml` + `launch/*.launch.py`，新增文件不必改 setup（`.rviz` 例外，见 G8） |
| LD06 `/scan` 规格与 crop 实测 | ✅ | 2026-11-07 N97：beam 455/452/454、角分辨率 0.793~0.798°、10 Hz；crop 90° 掩盖实测通过（[P7](ld06-dual-lidar.md)） |

---

## 四、级别定义与阻塞关系

| 级别 | 含义 |
|:---|:---|
| **P0** | 不解决就无法首跑（缺文件/缺硬件前提/环境冲突） |
| **P1** | 能跑，但验收结论不可信或事后无法复算 |
| **P2** | 收尾、可选、或仅影响操作体验 |

**依赖链**：G1/G2/G3 + G4 → 才能起"建图 + 导航 + 探索"链路；G5 为探索节点；G16 → 起链路前必须停掉多余实例；
G13 → G10 的前提；G15 现场就位 → 首跑；首跑后 G6/G7/G17 → 才能判"覆盖率"和"EKF 一致"；G18 复测 → 才谈收口。

---

## 五、建议实施顺序（依赖顺序，不含排期）

1. **定物理前提**：G13（装雷达）→ G10（量高度/俯仰回填 TF）→ G12（选 A/B）
2. **落软件资产**：G4（老车参数文件，先定名 G23）→ G1 → G2 → G3（可在 VM 写、VM 只做静态检查）
3. **建 explore_ws**：G5（N97 本机构建，VM 可另建一份做配置检查；构建产物不能互搬）
4. **补跑后数据链**：G6（覆盖率脚本）、G7（QoS 覆盖文件）、G17（EKF 对照阈值）
5. **现场首跑**：G16（停第二颗）→ G15（场地/急停）→ 按 explore-plan Step 0~3 分终端起
6. **收口**：G18 复测 → G20/G21 启动文档落地 → G8/G9 视需要

> 顺序原则：**先把"能起链路"和"能判合格"两件事分开做**——链路先端到端跑通，再加数据判据，
> 不在首跑当天同时调参数和算覆盖率。

---

## 六、待用户定夺

| # | 事项 | 选项 | 影响 |
|:--|:---|:---|:---|
| 1 | G4 新参数文件命名 | `nav2_params_ld06.yaml` / `nav2_params_oldcar.yaml` / 其他 | 决定后续文档引用名；不影响功能 |
| 2 | G4 继承范围 | 只删低带源（其余照抄 low 版）/ 同时调膨胀与速度 | 只删源 = 变量最少，推荐作为首跑起点 |
| 3 | G10 安装几何由谁测、何时 | 你实车量测后给我数值 / 先按占位值跑 | 占位值会让障碍位置偏，首跑仍可端到端 |
| 4 | G12 首跑用哪颗 | A（`r2_ld06_a`）/ B | 两颗均验证过，任选 |
| 5 | G8 是否本轮修 | 修 `setup.py` 加 `config/*.rviz` / 暂不修（rviz 另开） | 修了 `rviz:=true` 才有意义 |
| 6 | G17 EKF 对照阈值 | 由我按现有基线提一版供你定 / 你直接给 | 不定阈值 = 验收判不了 |

> 双雷达拓扑（S2）、低物兜底（L4）等 S1 之外的事项不在此列，见 [pending-tasks §⓪](../pending-tasks.md) 与
> [explore-plan §七](../minimal-loop2/explore-plan.md)。

---

## 七、本次盘点的边界与来源

- **已核实**：上表所有"现状证据"均来自 2026-11-06 的实机/仓库只读核对（文件存在性、grep 行号、
  `ros2 pkg list`、`git ls-remote`）；行号以当日文件为准。
- **未做**：explore_lite 实际构建/运行、Nav2 在 LD06 下的行为、覆盖率脚本实现、rviz 缺配置的实际表现——
  均标为未实测，不当作结论。
- **方案本身未做正确性评审**：本文只判"方案要的东西有没有"，不判"方案参数值对不对"；
  参数值以首跑实测回填 explore-plan。
