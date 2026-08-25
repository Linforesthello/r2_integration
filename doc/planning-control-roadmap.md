# R2 规划控制与视觉集成路线（08-18 调研）

> 状态：调研结论定稿（2026-08-18）；§五「全流程替代方案全景」与 §六「RL 增强方向」2026-08-23 补充（WebSearch 核实）；2026-08-23 按 [standards.md §1.11](standards.md) 规范化（补 §3.2 规格来源 / §5.5-5.6 仓库链接 + §6.6 来源小节 + 相关索引）；来源 = 官方仓库/README + WebSearch 社区核实，未实测项标注
> 定位：01-plan 第四章（集成路线图）的补充引用，视觉/规划控制的选型依据
> 关联：[01-plan.md](01-plan.md)｜[fastlio2-n97-deploy.md](fastlio2-n97-deploy.md)（FAST-LIO2 部署）

---

## 一、视觉-雷达标定工具线（hku-mars + 第三方）与集成时机

### 1.1 工具线

| 工具 | 特点 | 限制（对 R2 关键） |
|:---|:---|:---|
| [livox_camera_calib](https://github.com/hku-mars/livox_camera_calib)（hku-mars 官方主推） | targetless 无标定板，场景边缘自动标定，像素级精度，多场景联合更稳；官方示例 Avia + D435i | 核心是"高分辨率点云边缘提取"——**VLP-16 16 线稀疏，边缘质量存疑**；⚠️ ROS1（Kinetic/Melodic） |
| [joint-lidar-camera-calib](https://github.com/hku-mars/joint-lidar-camera-calib)（IROS 2023） | 内参+外参联合标定（平面约束 BA），0.12°/2.44cm，支持机械式 | 需纹理平面场景 + 初始外参（<5°/<0.5m）；⚠️ ROS1 catkin |
| [FAST-Calib](https://github.com/hku-mars/FAST-Calib) | 1s 快速标定，无需初值 | 需定制圆形孔标定板 |
| [direct_visual_lidar_calibration](https://github.com/koide3/direct_visual_lidar_calibration)（koide3，第三方） | 全型号雷达（机械式友好），SLAM 稠密点云 + 视觉配准 | 需相机内参先验（D435 出厂标定自带 ✅） |

### 1.2 关键判断（D435 是 RGB-D）

- D435 内参 + RGB-depth 外参**出厂已标好**，缺的只是 **lidar-camera 外参**
- VLP-16 稀疏点云不是 hku-mars 工具的主场（为高分辨率 Livox 设计）：
  - VLP-16 + D435 标定 → 走 koide3 路线（[direct_visual_lidar_calibration](https://github.com/koide3/direct_visual_lidar_calibration) 机械雷达友好）
  - MID-70 + D435 标定 → [livox_camera_calib](https://github.com/hku-mars/livox_camera_calib) 对口组合（官方示例同类）

### 1.3 集成时机（Phase 4 前置，不阻塞当前主线）

```
Phase 3 收尾（全速验证 + 避障实测）→ FAST-LIO2 决策
        ↓
   [现在不必做] 标定属于 Phase 4（D435+Jetson）前置任务：
   触发条件 = 视觉有明确用途：彩色点云建图（R3LIVE 式演示）/
            目标检测动态避障（Robocon 人形障碍）/ 任务对接
   成本认知：hku-mars 标定工具全 ROS1，N97 是 Humble——
            需容器或 ROS2 移植，不是一个晚上的成本
```

规划控制主线（§二）纯激光即可闭环，**视觉不阻塞它**——这就是"何时集成"的答案：
Phase 3 收尾后、进视觉前，做一次标定专项。

---

## 二、R2 分阶段规划控制方案（离线先验地图 vs 实时建图导航）

### 2.1 两大阵营对比

| 维度 | A. 离线先验地图导航 | B. 实时建图导航（探索） |
|:---|:---|:---|
| 地图 | 录 bag 离线建图 → 存文件 → 加载（KISS 现有 / FAST-LIO2 升级） | 运行中实时建（2D: SLAM Toolbox / 3D: FAST-LIO2 ikd-Tree） |
| 定位 | AMCL 2D（现有闭环）→ 升级 FAST-LIO-Localization 3D 重定位 | 无需独立定位：里程计即地图系（代价：无回环，长距离累积漂移） |
| 规划 | Nav2 全套（全局 NavFn/Smac + 局部 MPPI 现有） | Nav2 + frontier 探索循环 |
| 探索实现 | — | [explore_lite](https://github.com/robo-friends/m-explore-ros2)（ROS2 移植最成熟：前沿检测+黑名单+NavigateToPose 循环，有 RPi5 嵌入式基准）；备选 [frontier_exploration](https://github.com/adrian-soch/frontier_exploration) |
| 适用场景 | 比赛场地已知（**Robocon 主场景 ✅ 当前路线正确**） | 未知/临时场地、场地变更、搜救 |
| 资源成本 | 低（AMCL+Nav2，已跑通） | 高（SLAM+Nav2 同跑；N97 CPU 瓶颈下 3D 方案尤其吃力——[基准论文结论：轻量 2D SLAM 远优于 3D 于嵌入式](https://xplorestaging.ieee.org/document/11365146)） |

### 2.2 R2 分阶段落点

```
Phase 3（当前 25%）: A 阵营收尾 —— 全速验证（先同步膨胀参数 0.55→0.30）→ 避障实测 → 设位姿纪律
Phase 3+（决策点）:   FAST-LIO2 vs KISS 决策 → 若替代：建图质量升级（A 阵营地图源）；FAST-LIO-Localization 定位试验（可选）
Phase 3.5（探索，可插队）: B 阵营轻量版 —— SLAM Toolbox 2D + explore_lite（N97 可承受）；3D 探索（FAST-LIO2 实时地图）仅演示用
Phase 4（视觉）:     lidar-camera 标定 → 彩色点云 → 目标检测动态避障（为 Robocon 人形障碍）
Phase 5（编排）:     waypoint 任务队列（已有待办）+ 气动 + 异常处理
```

### 2.3 Robocon 视角决策

- 比赛场地是规则场地（已知）→ **A 阵营是主力，Phase 3 路线正确，继续收尾**
- B 阵营作为"场地临时变更/未知区"兜底，用 2D 轻量方案即可，不必上 3D 探索
- 视觉标定排 Phase 4 前置，不抢主线时间

---

## 三、传感器选型：VLP-16 vs MID-70（室内三方案对比，实机 A/B 定夺）

### 3.1 核心矛盾（08-18 用户实测反馈）

**VLP-16 16 线稀疏，近距小物体表现非常差**——比赛场地（室内）与实验室（室内）场景下是主要短板。
（原"全景优先 + MID-70 价值被 D435 覆盖"的判断已修正：D435 视场小/5m 内/依赖光照，
**替代不了主雷达的空间密度**——建图/里程计的数据源。）

### 3.2 两雷达特性对比（含易误判点）

| 维度 | VLP-16（现役） | MID-70（闲置） |
|:---|:---|:---|
| FOV | 360° 水平全景（16 线，±15° 垂直） | 70.4° 圆形视场（非全景，朝前安装才可用） |
| 总点率 | 300k/s（总量高，⚠️ **易误判为"更密"**） | 100k/s（总量低，但…） |
| 空间分布 | 集中在 16 条线带，层间 2° 空洞 | 视场内**均匀分布**、无层间空洞 → **有效空间密度远高** |
| 近距小物体 | 1~2 层命中、点稀少（室内柱子/细杆/物料块表现差） | 视场内多点命中（0.2° 级角分辨） |
| FAST-LIO 适配 | PointCloud2 分支（time 字段可用） | **Livox CustomMsg 原生**：每点时间戳、运动畸变处理更好（直击 KISS 旋转漂移痛点） |
| 集成状态 | 驱动/建图/FAST-LIO/Nav2 全跑通 | 无驱动、无集成（livox_ros_driver2 已在 FAST-LIO 工作区装好） |
| 物理成本 | 供电已验证紧张（08-15 供电不足教训） | 供电 + 网口 + 车顶空间 |

> 规格来源（2026-08-23 WebSearch 核实）：[VLP-16 官方数据表（Velodyne 对比表，300k pts/s 单回波 / 360°×±15° / 2° 垂直角分辨）](http://velodynelidar.com/docs/datasheet/LiDAR%20Comparison%20chart_Rev-A_Web.pdf)｜[MID-70 官方规格页（livoxtech.com，70.4° 圆形 FOV / 100k pts/s / 905nm / IP67）](https://www.livoxtech.com/mid-70/specs)；"近距小物体/层间空洞"表现为 08-18 用户实测反馈，非官方规格项

### 3.3 三方案对比（不预设结论，A/B 实测定夺）

| 方案 | 结构 | 优点 | 代价/风险 |
|:---|:---|:---|:---|
| **a. MID-70 换装主雷达** | MID-70 全职责（建图+里程计+避障），VLP-16 拆下 | 建图质量/近距细节最优；FAST-LIO 原生适配（每点时间戳） | 70° 非全景：室内避障需转向弥补；新集成工作量 |
| **b. 双雷达组合** | VLP-16 360° 喂 Nav2 避障 + MID-70 高密度喂 FAST-LIO（**各喂一个消费者，不同时跑两份 SLAM**） | 全景避障 + 高密度建图兼得 | 供电/网口/车顶空间；两链路都要维护；N97 CPU 需实测（两链非并行 SLAM，预估可承受） |
| **c. VLP-16 + D435 补近距** | VLP-16 主雷达 + D435 近距感知（原案） | 零新增雷达成本；D435 已在 Phase 4 计划内 | 近距仅 5m 内/依赖光照；**建图密度短板未解决** |

### 3.4 定夺方法（A/B 实机对比，FAST-LIO2 验证必做环节）

同一段室内场景（场地放柱子/物料块），VLP-16 vs MID-70 分别跑 FAST-LIO2：

1. **建图密度/细节**：同一场景视觉对比 + 点数统计
2. **小物体表现**：Nav2 底图是否检出柱子/物料块
3. **里程计质量**：旋转漂移对比（KISS 163° 教训基线）
4. **避障实测**：2D scan 表现

半天成本，数据定夺方案 a/b/c。触发点 = **FAST-LIO2 实车验证阶段**（见
[fastlio2-n97-deploy.md](fastlio2-n97-deploy.md) §六），不必等"质量不达标"才做。

---

## 四、ROS1/跨版本包 Docker 部署与通信协作

**核心区分：离线批处理 vs 在线融合**——hku-mars 标定工具（livox_camera_calib / joint-lidar-camera-calib /
FAST-Calib）都是**离线批处理**：容器里读 bag、输出 yaml，**无需与宿主机实时通信**，挂载数据卷即可。

| 方案 | 做法 | 适用 |
|:---|:---|:---|
| **离线容器**（首选） | `docker run -v <bag目录>:/data`，容器内跑标定，结果写挂载卷 | hku-mars 标定工具 ✅ |
| **--network=host + ros1_bridge** | 容器复用宿主网络栈；[ros1_bridge](https://github.com/ros2/ros1_bridge)（官方）双向话题/服务桥，`dynamic_bridge` 自动映射 | 在线 ROS1 节点 ↔ 宿主机 ROS2 |
| **现成一体镜像** | [Dsobh/Humble-Noetic](https://github.com/Dsobh/Humble-Noetic)（内置 bridge + conf.yaml 配话题）、[li9i/ros1_humble_bridge_template](https://github.com/li9i/ros1_humble_bridge_template)（自定义消息） | 不想自己搭 |

**坑（社区实测）**：
- [ros1_bridge /rosout 桥在 Humble 损坏](https://github.com/ros2/ros1_bridge/issues/391)（Log 消息无法映射）；不支持 actions；自定义消息需同工作区编译
- 容器间 DDS 走 UDP（共享内存不跨容器）——复用 R2 既有跨机 FASTRTPS 经验（N97↔VM，见 [ros2-ops.md](ros2-ops.md) §1）
- 容器访问硬件（如 D435）需 `--device` 或 `--privileged` 透传 USB

**R2 落地**：标定走"离线容器"（唯一刚需）；在线融合（R3LIVE/LVISAM 等 ROS1）在 N97 CPU 瓶颈下性价比低，
除非 FAST-LIO2 决策后有强动机，否则不引入。

---

## 五、全流程替代方案全景（两大阵营各环节选型）

> 补充时间：2026-08-23（WebSearch 核实）；定位：§二「两大阵营对比」的逐环节展开——每个环节的候选方案、现状与 R2 推荐

### 5.1 流程分解与环节定位

```
A 离线地图导航: 采集(bag) → 离线建图 → 地图后处理 → 定位 → 规划(全局+局部) → 任务编排
B 实时建图导航: 实时SLAM → 探索决策 → 规划(同 Nav2) → 任务编排
              └── 共享: 标定(外参) / 传感器 / 底盘
```

### 5.2 建图算法（A 离线 / B 实时共用一个选型池）

| 算法 | 维度 | 回环 | IMU | ROS2 状态 | 特点 |
|:---|:---:|:---:|:---:|:---|:---|
| SLAM Toolbox | 2D | ✅ 图优化 | 可选 | ✅ 原生 | 轻量、易调试；2025 实测 ATE 0.13m（Cartographer 0.21m）、CPU 70% |
| Cartographer | 2D/3D | ✅ 最强 | ✅ | ⚠️ 社区移植 | 大场景/长廊/仓库强，回环消累积误差，但对参数调优敏感、资源重 |
| KISS-ICP（现役） | 3D | ❌ | ❌ | ✅ 原生 | 纯激光、极简；无 IMU 旋转漂移（R2 163° 教训） |
| FAST-LIO2（候选） | 3D | ❌ | ✅ | ✅ 原生 | LIO 紧耦合，运动预测强、退化场景稳；VLP-16 已原生支持 |
| LIO-SAM | 3D | ✅ 因子图 | ✅ | ⚠️ 社区 | 系统完整、回环强，但重、调参成本高 |
| Point-LIO | 3D | ❌ | ✅ | ✅ | Livox 固态雷达主场 |

**选型逻辑（2025 社区共识）**：接 Nav2 实时导航 → FAST-LIO/KISS 类低延迟连续稳；要全局地图一致性 → LIO-SAM/回环模块；嵌入式 → 2D slam_toolbox 远优于 3D（与 §2.1 引文结论一致）。

**R2 落点**：3D 主线 = KISS → **FAST-LIO2**（接 G354 解决旋转痛点）；B 阵营 2D 探索 = **SLAM Toolbox**。LIO-SAM 的因子图回环是"更远的地图质量升级"，但 N97 上不值。

### 5.3 定位（A 阵营：先验地图下的重定位）

| 方案 | 维度 | 特点 | ROS2 |
|:---|:---:|:---|:---:|
| AMCL（现役） | 2D | 粒子滤波，轻量，已有闭环 | ✅ 原生 |
| SLAM Toolbox localization 模式 | 2D | 复用建图引擎做定位，支持 lifetime map | ✅ 原生 |
| Cartographer localization | 2D/3D | 回环强的定位模式 | ⚠️ 社区 |
| FAST-LIO-Localization | 3D | 点云配准重定位，接 FAST-LIO 工作区（§2.1 已列为升级项） | ✅ |
| NDT/ICP scan matcher | 3D | Autoware 系（ndt_scan_matcher），工程成熟 | ✅ |
| 视觉重定位（ORB-SLAM3 等） | 视觉 | 需要相机先验标定 | ⚠️ |

**R2 落点**：AMCL 现状够用（map_0815_clean 已跑通）；升级路 = FAST-LIO-Localization（若 FAST-LIO2 替代 KISS 后定位一起升 3D）。⚠️ 注意：3D 定位意味着地图底图质量也必须 3D 级——建图升 FAST-LIO2、定位留 AMCL 2D 是可行的过渡态。

### 5.4 规划——"只有 Nav2 吗"

**结论**：Nav2 不是唯一，但它是 ROS2 事实标准，且本身是"可插拔组件框架"——换算法不用换栈。

| 层次 | 可替代选项 |
|:---|:---|
| 框架 | Nav2（✅ 现役）/ move_base（ROS1 前身）/ 完全自研（仅当 Nav2 覆盖不了底盘约束时值得） |
| 全局规划器 | NavFn（现役，A*）/ Smac Planner（Hybrid-A*，支持 omni/差速/阿克曼）/ Theta* / Grid-A* |
| 局部控制器 | MPPI（现役，Nav2 官方指定 TEB/DWB 继任者）/ DWB / Regulated Pure Pursuit / TEB（⚠️ 见下）/ MPC-Local-Planner |
| 恢复行为 | Nav2 Recovery（卡死后退/旋转，内置） |

**关键避坑（已核实）**：TEB 在 ROS2 Humble 处于"官方弃养"——无 apt 二进制、无 humble 分支、作者已停止维护，Nav2 官方明确推荐 MPPI 接任；社区源码移植需手修 cv_bridge/nav2_core 的 Humble API 差异，2025 年仍有大量"换 TEB 后无法导航"求助帖。**R2 结论：别碰 TEB，MPPI 就是正解。**

**全向轮适配**：Nav2 Smac/MPPI 均有 omni 运动模型，四舵轮全向底盘在 Nav2 模型覆盖内——"不换栈"的底气；真要自研，理由只可能是 MPPI 跑不出特定运动学约束（如舵轮转角限制）。

### 5.5 探索（B 阵营独有环节）

| 方案 | 特点 | R2 适配 |
|:---|:---|:---:|
| explore_lite（[m-explore-ros2](https://github.com/robo-friends/m-explore-ros2)，首选） | 前沿检测+黑名单+NavigateToPose 循环；2026-04 仍在更新；源码构建（无二进制包）；参数成熟（potential/orientation/gain 权重） | ✅ 轻量 |
| [frontier_exploration_ros2](https://discourse.openrobotics.org/t/frontier-exploration-ros2-modern-autonomous-exploration-system-for-ros-2/57222/1) | WFD 前沿 + 动态规划优化目标排序；基准：行驶距离 338.6m→263.7m、时间 9:47→7:22（vs m_explore_ros2） | ✅ 备选 |
| [roadmap_explorer](https://github.com/suchetanrs/roadmap-explorer) | 路标式；实测 3520㎡ 大场景；Jetson 上单核 ~10%；会话保存/恢复（探索中断可续）；与 Nav2 端到端集成 | ✅ 效率最优 |
| dynamic-window-frontier | explore_lite 增强版（局部/全局窗口切换） | 可选 |
| rrt_exploration | 非凸/多房间强，计算重 | ❌ N97 |
| [TARE_planner](https://github.com/caochao39/tare_planner)（[RSS 2021 最佳论文](https://www.cmu-exploration.com/tare-planner)，CMU 层级探索） / [ARiADNE-ROS-Planner](https://github.com/marmotlab/ARiADNE-ROS-Planner)（RL 探索） | 工程化强但 ROS2 移植非官方；ARiADNE 2025-08 才出 Humble 版、RL 训练重 | ❌ 过度工程 |

**R2 落点**：先 explore_lite（§2.1 结论不变）；探索效率不够/场地大 → roadmap_explorer 比 frontier_exploration 更值得作第二选择（会话保存对"探索中断继续"实用）。TARE 不上——N97 扛不住，Robocon 也用不上。

### 5.6 标定方案（§一 之外补全的环节）

| 要标定的外参 | 方案 | 状态 |
|:---|:---|:---:|
| 雷达-相机（D435+VLP-16） | livox_camera_calib / joint-lidar-camera-calib / FAST-Calib / [direct_visual_lidar_calibration](https://github.com/koide3/direct_visual_lidar_calibration)（§1.2 已定 koide3 路线） | ✅ 已规划（Phase 4 前置） |
| **雷达-IMU** | [LI-Init](https://github.com/hku-mars/LI-Init)（自动标定）/ 手测初值 | ⚠️ **§一 未覆盖，FAST-LIO2 前置刚需**——VLP-16 与 G354 外参（平移+旋转）直接影响 LIO 精度 |
| 雷达-雷达（§3.3 方案 b） | Autoware 点云标定 / 手工量测 | 仅当方案 b 选中 |
| 相机内参 | D435 出厂已标 | ✅ |
| 底盘里程计/舵轮 | 已有脚本（ticks/圈、speed_scale、MT6701 中位） | ✅ |

> ⚠️ **雷达-IMU 外参标定是比 lidar-camera 更优先的环节**（FAST-LIO2 上线前必做；不做会吃精度亏）。

### 5.7 任务编排（全流程最后一环，Phase 5）

| 方案 | 特点 | R2 |
|:---|:---|:---:|
| Nav2 BT Navigator | 行为树是 ROS2 任务编排事实标准（2025 大量实践）；多航点巡逻 = NavigateThroughPoses / FollowWaypoints（循环+断点续）；Groot2 可视化调试 | ✅ 首选 |
| 自研 waypoint 循环节点 | 简单需求够用（待办"waypoint 雷达闭环"可先这么干） | ✅ 过渡 |
| py_trees / SMACH | BT 的前辈，可读性/复用不如 BT | 可选 |

**R2 落点**：Phase 5 waypoint 队列直接用 Nav2 自带 BT（navigate_through_poses 插件）或包一层自定义 BT 节点，不自己写状态机——Robocon"跑任务序列"环节的正解（巡逻→检测→恢复可挂恢复逻辑）。

### 5.7bis 上层车体控制（MBD 状态机 → 车体部署，2026-08-23 用户规划方向）

> 状态：**规划中，未实测**。与 §5.7 的 BT 任务编排互补——BT 管"任务序列"，状态机管"车体行为/决策层"；
> 秋招（2026-09-10）前优先级低，实车验证后再计入简历（信息池 F12）。

| 环节 | 方案 | 状态 |
|:---|:---|:---|
| 状态机建模 | MATLAB/Simulink Stateflow（MBD 正规流程：建模 → 仿真验证 → 部署车体） | 规划中 |
| 部署路径 | 代码生成（Embedded Coder）→ 车体；或建模验证后手写实现部署 | 未定 |
| 自动驾驶上层框架 | Autoware.universe 等大型框架部署评估 | 未评估（量级/资源成本高，N97 CPU 瓶颈谨慎） |
| 与 Nav2 关系 | 上层输出 goal/行为指令，Nav2 仍是规划执行层 | 不冲突 |

**R2 落点**：先 Phase 3 收尾 + 避障 + 主动探索（explore_lite）出量化；MBD 状态机作为 Phase 5 正规化手段记录，不抢主线。

### 5.7ter 争议点：全向轮底盘运动模式（车头为主 vs 目标点为主）

> 状态：**争议中（2026-08-25 用户提出，未定论）**——有讨论空间，且对后续四舵轮转向底盘
> 的运动学考虑影响更大，先留档待议。R2 当前行为分析基于 08-25 避障实车 bag 数据 + WebSearch 官方资料。

**问题**：全向轮底盘（vx/vy/wz 全自由）存在两种运动策略——

| 模式 | 行为 | 适用 |
|:---|:---|:---|
| **车头为主**（head-aligned） | 车头跟随路径方向缓转，用横向平移（vy）修正位置，少旋转 | R2 推荐方向：雷达盲区最小、可预测、绕障友好（AGV 主流） |
| **目标点为主**（rotate-then-go） | 先转到目标方向再平移 / 到位再对准 | 观感"奇怪"（用户原话：不是车头为准，先变换姿态，甚至斜着过去） |

**R2 现状与机理（08-25 bag 数据 + 官方资料）**：
- 行为：1405 bag 22 段运动中 12 段"旋转为主"；运动中前向最近障碍频繁 0.50m（min_range 下限）——旋转时贴障碍走
- 机理：`motion_model: "Omni"` 下 vx/vy/wz 独立采样，MPPI 只按 cost 最小化选轨迹 → 斜着平移常是最优解；
  ConstraintCritic 对 omni **无任何约束**；朝向相关 critic 权重低（PathAngleCritic w=2.0 / max_angle 1.0rad / GoalAngleCritic 0.5m 内才考虑）→ 车头基本无人管；
  且 holonomic 车可用 vy 满足朝向要求（官方明确），不必旋转
- 实锤：1401 bag 单 goal 全程，前方障碍 1.88m 可见，车 0.22m/s 直冲到 0.85m 才停——感知通、决策晚
  （MPPI 1.92s×0.2m/s≈0.38m 空间前瞻，障碍未入轨迹视野不触发 cost）

**候选方案对比**：

| 方案 | 做法 | 效果 | 代价 |
|:---|:---|:---|:---|
| ① 调权重（倾向推荐） | TwirlingCritic 10→30 + PathAngleCritic w 2→10、max_angle 1.0→0.5 | 旋转变贵→平移修正、车头被引导朝路径方向 | 参数级，实车一趟验证 |
| ② Rotation Shim Controller | 前置控制器先原地转到位再跟踪 | 严格"目标点为主" | 正是用户不想要的模式 |
| ③ motion_model 换 DiffDrive | 禁 vy | 车头必须朝运动方向 | 丢横向能力，窄缝/平移绕障全废 |
| ④ Smac 2D 平滑路径 | 路径圆滑 | 减轻"先转姿态"观感 | 对"斜走"无效 |

**四舵轮底盘延伸考虑（2026-08-25 用户提出，预期待验证）**：后续四舵轮转向底盘（转向电机 + 驱动电机，
非完整约束轮）运动学约束更硬——轮子只能沿自身轴向滚动，横移需所有轮同时转向（蟹行），且转向有机械限位/
转向速率限制。因此"车头为主"在四舵轮上是**结构强制**（类汽车/AGV 路径跟踪：轮转向角跟随路径曲率），
"平移/蟹行"是特殊模式而非默认——运动模式选择策略与全向轮含义完全不同，需单独讨论。

**留档结论**：R2 先按方案① 实车验证（若用户采纳）；四舵轮底盘（MCLM/SteeringArm 项目）运动学留作
专项讨论，本争议点随两项目演进更新。

#### 来源（2026-08-25 WebSearch 核实）

- [PathAngleCritic API 文档](https://api.nav2.org/nav2-humble/html/classmppi_1_1critics_1_1PathAngleCritic.html)（参数/模式含义）
- [path_angle_critic 源码](http://api.nav2.org/nav2-humble/html/path__angle__critic_8cpp_source.html)（mode 0/1/2 行为）
- [MPPI 原地旋转讨论（Turtlebot3，Stack Overflow）](https://robotics.stackexchange.com/questions/114198/in-place-rotation-with-mppi-controller-using-turtlebot3?rq=1)（Rotation Shim 替代方案，未实测）

### 5.8 汇总：R2 全流程决策表

| 环节 | 现状 | 候选池 | 推荐 |
|:---|:---|:---|:---|
| 传感器 | VLP-16 | MID-70 / 双雷达 | 等 FAST-LIO2 实车 A/B（§3.4） |
| 建图(3D) | KISS-ICP | FAST-LIO2 / LIO-SAM / Point-LIO | FAST-LIO2（接 G354） |
| 建图(2D, B 阵营) | — | SLAM Toolbox / Cartographer | SLAM Toolbox（轻量、ATE 更优） |
| 定位 | AMCL | FAST-LIO-Localization / NDT / SLAM-Toolbox-localization | AMCL 过渡 → FAST-LIO-Localization |
| 规划框架 | Nav2 | move_base / 自研 | Nav2（可插拔，不换栈） |
| 局部控制 | MPPI | TEB ❌（弃养）/ DWB / 纯跟踪 | MPPI（Nav2 官方指定） |
| 探索 | — | explore_lite / roadmap_explorer / frontier_exploration_ros2 | explore_lite 起步，效率不够换 roadmap_explorer |
| 标定(雷达-相机) | — | koide3 路线（§1.2 已定） | 不变 |
| 标定(雷达-IMU) | 未规划 | LI-Init | **补为 FAST-LIO2 前置** |
| 任务编排 | 自研待办 | Nav2 BT / py_trees | Nav2 BT（NavigateThroughPoses） |
| 上层车体控制 | — | MBD 状态机（MATLAB/Simulink → 部署）/ 自动驾驶框架 | 规划中（§5.7bis，秋招后优先） |

**一句话**：Nav2 不是"只有它"，但是标准底盘——规划层可插拔、任务层用 BT、建图/定位/探索层各有一个"现状→升级"路径；真正要补的缺口只有两个：**雷达-IMU 外参标定（FAST-LIO2 前置）** 和 **探索效率升级路（explore_lite → roadmap_explorer）**。

### 5.9 来源（2026-08-23 WebSearch 核实）

- [SLAM Toolbox vs Cartographer 仿真到实机对比（2025 预印本）](https://ggnpreprints.authorea.com/doi/full/10.22541/au.175199254.49549720/v1)
- [ROS2 3D LiDAR 选型实战（FAST-LIO/LIO-SAM/Point-LIO/KISS-ICP）](https://blog.csdn.net/pipoa/article/details/162098227)
- [m-explore-ros2 仓库](https://github.com/robo-friends/m-explore-ros2)｜[DeepWiki 参数文档](https://deepwiki.com/robo-friends/m-explore-ros2/1-overview)
- [frontier_exploration_ros2 发布帖（OpenRobotics Discourse）](https://discourse.openrobotics.org/t/frontier-exploration-ros2-modern-autonomous-exploration-system-for-ros-2/57222/1)
- [roadmap_explorer（路标式探索）](https://github.com/suchetanrs/roadmap-explorer)
- [TEB Humble 踩坑记录](https://jishuzhan.net/article/2025430982359318529)｜[TEB 在 Nav2 Humble 失效讨论](https://robotics.stackexchange.com/feeds/question/104822)
- [ARiADNE-ROS-Planner（RL 探索，Humble 2025-08 支持）](https://github.com/marmotlab/ARiADNE-ROS-Planner)
- [TARE_planner（CMU 层级探索，RSS 2021）](https://github.com/caochao39/tare_planner)｜[项目主页](https://www.cmu-exploration.com/tare-planner)
- [ROSCon Spain 2025 RB-Watcher（Nav2 BT 巡逻工作坊）](https://github.com/RobotnikAutomation/roscon2025_rbwatcher_workshop)
- [Nav2 多航点导航 BT 实践（WayWiseR）](https://deepwiki.com/das-rise/WayWiseR/4.1-nav2-integration-(waywiser_nav2))

---

## 六、RL 增强方向（规划控制的 RL 化，2026-08-23 用户规划）

> 状态：方向确认，**实施方式未定**（用户原话："具体怎么实施我还没想好"）。
> 定位：§五 决策表的"RL 增强"延伸，横跨**足式全身控制**与**车构型规划**两层；
> 训练框架 = Isaac Lab/Gym、MuJoCo、UniLab。

### 6.1 足式 RL 扩展（四足/双足全身控制 → 地形适应）

| 能力 | 现状 | 目标 | 训练框架 |
|:---|:---|:---|:---|
| 稳定行走 | Go2 APPO 512 并行 22.8 万轮（UniLab）、G1 FastSAC 2048 并行 1024 万步（MuJoCo） | ✅ 已做 | UniLab / MuJoCo |
| **越障、过地形** | 未做 | 复杂地形适应（跨障/坡面/台阶） | Isaac Lab/Gym、MuJoCo、UniLab |

### 6.2 车构型 RL（底盘/车辆规划层）

| 方向 | 内容 | 与 Nav2 关系 | 状态 |
|:---|:---|:---|:---|
| 局部避障 RL | RL 策略替代/增强 MPPI 局部控制器（端到端或与 costmap 融合） | 可插拔（Nav2 控制器插件） | 方向确认，实施未定 |
| 倒车入库 RL | 精确机动策略（窄位泊车/往返倒库）= 高精度运动规划的 RL 化 | goal 级任务，Nav2 规划层之上/替代 | 方向确认，实施未定 |

### 6.3 实施路径建议（待定夺）

- **足式**：Isaac Lab（GPU 并行）训练 → 与 UniLab/MuJoCo 既有链路对比一致性 → ONNX 部署（链路已通）
- **车构型**：仿真环境选型（Isaac Lab vehicle/car 环境，或自建 gym env 包 Nav2 代价图）→ 训练 → Sim-to-Real（N97 部署，接 R2）

### 6.4 优先级（秋招 2026-09-10 视角）

- 秋招前：现有 RL 素材（Go2/G1/ONNX 一致性）已够支撑"RL 背景"叙事；新方向按"探索中"写，不写成果
- 秋招后：Isaac Lab 车构型 RL 与 R2 实车联动（局部避障策略 vs MPPI 实车对比，数据说话再定）

### 6.5 多传感器融合 RL 观测（D435 + IMU + 里程计 + LiDAR 融合导入训练）

> 2026-08-23 用户设想（"我也没有头绪"），WebSearch 核实结论：**可行，且是 Isaac Lab 多模态标准玩法**。
> 用户原话："RL 这一块好像还支持 D435+IMU+里程计+LiDAR 的融合导入训练"。

**模态支持与 R2 资产对照**：

| 模态 | Isaac Lab 支持 | R2 资产 |
|:---|:---|:---|
| RGB-D 相机（D435） | RTX 照片级渲染（TiledCameraCfg：rgb/depth/fisheye） | D435 SDK 已编译（Phase 4 接入） |
| LiDAR 点云 | RayCasterCfg（2D/3D，多通道 ±180° 等） | VLP-16 实车 ✅ |
| IMU | 加速度/角速度传感器 | G354 实车 ✅（已入 EKF） |
| 里程计 | 机器人状态（位姿/速度，ROS2 /odom） | /odom_wheels + /odometry/filtered ✅ |

**关键坑：混合观测空间（hybrid observation space）**
- 图像/LiDAR 等非向量观测与 proprioception（IMU/里程计/关节）**不能简单 concat**，须分 observation group
  （[IsaacLab issue #768](https://github.com/isaac-sim/IsaacLab/issues/768)）
- RL 库兼容性：RSL-RL **不支持**混合观测；skrl / rl-games 部分支持；SB3 MultiInputPolicy 支持但数据转 CPU 掉性能 → **RL 库选 skrl / rl-games**

**参考实例（可作实现蓝本）**
- 智能轮椅多模态导航（[IEEE](https://ieeexplore.ieee.org/document/11469504)）：2D LiDAR + 4×轮装 IMU + 4×RGB 相机融合编码 → PPO 室内导航 —— **与 R2 车构型最接近**
- 四足巡检机器人（中文期刊，链接待核实）：LiDAR + IMU + RGB + 里程计 + 关节状态经 ROS2 发布 → RL 策略地形行走
- [V550-Ackermann-DRL-Nav2](https://github.com/Jacob-Tan666/V550-Ackermann-DRL-Nav2)：TD3 + 50-bin LiDAR 扇区 + 运动学量（目标距离/方向/速度/转角）→ Nav2 集成（Smac Hybrid-A* + MPPI），含域随机化 Sim-to-Real
- [ros-navigation #4613](https://github.com/orgs/ros-navigation/discussions/4613)：RL local planner 替换 Nav2 内控制器的学术方案——社区建议按 **MPPI/RPP 控制器插件模式**集成

**R2 落点（实施路径建议，待定夺）**
1. **仿真先行**：Isaac Lab 建 R2 数字孪生（URDF + VLP-16 雷达 + D435 + IMU + odom 传感组），观测 = LiDAR 分箱 + 视觉 + proprioception，PPO/skrl 训练局部避障策略
2. **观测复用**：真实侧直接复用 EKF 融合链输出（/odometry/filtered）+ 原始传感器话题，与仿真观测对齐
3. **集成两条路**：a) Nav2 控制器插件（MPPI 插件模式，社区认可路径）b) goal 级独立策略（倒车入库/窄位泊车）
4. **Sim-to-Real**：域随机化（传感器噪声/执行器延迟）→ N97 部署（参照 V550 工作流）

**风险标注（未实测）**：Isaac Lab 训练算力需求待确认（GPU 环境）；RL 导航策略成功率/泛化是开放问题；
观测维度爆炸（图像+点云）训练成本高——起步建议从"LiDAR 分箱 + 运动学量"最小观测做起（V550 模式），再逐步加视觉。

### 6.6 来源（2026-08-23 WebSearch 核实）

- [IsaacLab issue #768（混合观测空间须分 observation group，RSL-RL 不支持）](https://github.com/isaac-sim/IsaacLab/issues/768)
- [智能轮椅多模态导航（IEEE，2D LiDAR + 4×轮装 IMU + 4×RGB 融合 → PPO 室内导航）](https://ieeexplore.ieee.org/document/11469504)
- [V550-Ackermann-DRL-Nav2 仓库（TD3 + 50-bin LiDAR 扇区 + 运动学量 → Nav2 集成，含 Sim-to-Real）](https://github.com/Jacob-Tan666/V550-Ackermann-DRL-Nav2)
- [ros-navigation #4613（RL local planner 替换 Nav2 控制器，社区建议按 MPPI/RPP 插件模式集成）](https://github.com/orgs/ros-navigation/discussions/4613)
- 四足巡检机器人（中文期刊）链接未核实，未列入

---

## 相关

- [01-plan.md](01-plan.md)（集成计划总纲，第四章路线图）｜[fastlio2-n97-deploy.md](fastlio2-n97-deploy.md)（FAST-LIO2 部署手册）
- [standards.md](standards.md) §1.11（调研/选型文档附来源规范——本文格式依据）｜[07-handover.md](07-handover.md)（运行状态与参数快照）
- [ros2-ops.md](ros2-ops.md)（ROS 操作规范）｜[ros2-qos-dds.md](ros2-qos-dds.md)（QoS/DDS 问题手册）
- [retrospect/2026-08-18_fastlio_laser_map_debug.md](retrospect/2026-08-18_fastlio_laser_map_debug.md)（FAST-LIO 排障全记录）
