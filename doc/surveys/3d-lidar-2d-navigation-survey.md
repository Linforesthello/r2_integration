# 单 3D 雷达高置 × 平面导航：低矮障碍感知手段调研清单（2026-09-05）

> 状态：调研清单（2026-09-05 WebSearch 核实，全站链接可回查）；**全部手段均未实测**，
> 标注「未实测」处不可当已验证结论使用（standards §1.11）
> 定位：为「低物盲区修法」提供**社区/工业做法方向池**——复盘 09-04 已裁定修法**后置**
> （09-10 前不实施，阶段二候选），本文是其前置调研，不改变后置决策本身
> 关联：[复盘 09-04 §六-3/§10.4](../retrospect/2026-09-04_lowobstacle_breakpoint.md)（断点与修法候选）、
> [planning-control-roadmap.md](../roadmaps/planning-control-roadmap.md) §三（VLP-16 vs MID-70 传感器线，待用户另行发起迁移/连接）、
> [minimal-loop2/relog-operation.md](../minimal-loop2/relog-operation.md)（重录话题清单，若加低带 scan 需联动）

---

## 一、问题定位：这不是"扫描方式不够"，是"3D→2D 转换层选环"问题

R2 断点（复盘 09-04 钉死）：/velodyne_points **有完整低环数据**（rings 0~4 实测命中 0.3m 矮物），
丢失发生在 velodyne_laserscan 转换层——它只输出**单环**，默认 ring=-1 自动选 VLP-16 的 **ring 8（+1° 上仰）**，
于是 0.3m 矮物在 /scan+costmap 里结构性不可见。

问"社区/工业怎么处理高置单 3D 雷达做平面导航"，实际是问：
**把 3D 点云变回平面避障信息，有哪几种公认做法？** 答案是分层的，远不止"2D scan 一种"：

| 处理层次 | 做法方向 | 一句话 |
|:---|:---|:---|
| ① 转换层 | 点云 → 合成 2D scan | 高度带切片/多环融合，替代"单环抽取" |
| ② 代价地图层 | 点云直接进 costmap | 跳过 scan，obstacle/voxel 层原生吃 PointCloud2 |
| ③ 感知/中间表示 | 点云 → 地面去除/BEV/3D 表示 | 滤波链、3D SLAM 直出 2D、体素表示 |
| ④ 物理/布局 | 传感器侧改变 | 双雷达分工、大垂直 FOV、装位姿态 |
| ⑤ 行为/运行策略 | 不给感知加数据 | 降速/近距策略配合（次要，一笔带过） |

> 本清单即"全部列出"版；对 R2 的具体适配与复盘候选校正见 §三。

---

## 二、手段清单（逐条：做法 / 实现与参数 / 来源案例 / 边界标注）

### ① 转换层：3D 点云 → 合成 2D scan

**1.1 pointcloud_to_laserscan 高度带切片 —— 社区事实标准**
- 做法：订阅完整 PointCloud2，按 `min_height`/`max_height` 高度带滤点 → 每点按**水平距离 + 方位角**投影
  （√(x²+y²)，非斜距）→ 角分箱内**取最近点**，合成 360° 2D scan。
- 关键：它按真实 3D 点先筛后投，物理正确；低环点（VLP-16 −15° 环）落在矮物上的点会真实进入 scan——
  **一条低带切片即可让 0.3m 矮物可见**（官方定位就是"让 3D 设备对 2D 算法表现为激光"）。
- 参数要点：默认高度边界近乎全开（min≈2.2e-308 / max≈1.8e+308，**必须手动收窄**）；
  `angle_min/max` 默认 ±π（360°，勿被某些深度相机教程带偏成 ±π/2）；`range_min/max`；`use_inf`；
  `target_frame`+`transform_tolerance`；**无订阅者时不处理**（省算力）。
- ROS2 现成度：**Humble apt 二进制 `ros-humble-pointcloud-to-laserscan`（v2.0.1，jammy）可用**，零源码改动。
- 边界（官方/社区承认）：高度投影是有损降维——斜坡/台阶场景低切片不可靠；角分箱取最近点会丢纵深遮挡信息。
- 来源：[ros-perception/pointcloud_to_laserscan](https://github.com/ros-perception/pointcloud_to_laserscan)、
  [ROS Index](https://index.ros.org/p/pointcloud_to_laserscan/)、[Kilted API 文档](https://docs.ros.org/en/ros2_packages/kilted/api/pointcloud_to_laserscan/index.html)、
  [Humble apt 包（packages.ros.org）](http://packages.ros.org/ros2-testing/ubuntu/pool/main/r/ros-humble-pointcloud-to-laserscan/)、
  [VLP16 点云转 LaserScan 配置实战（CSDN，Noetic，参数详解）](https://blog.csdn.net/mac99/article/details/153243949)、
  [点云转 2D scan 完整配置避坑（CSDN，360° 覆盖提醒）](https://blog.csdn.net/o1p2q3r/article/details/154226860)

**1.2 双/多切片多 scan（高低带各出一份）**
- 做法：同一节点参数实例两份（或两份点云各跑一个节点）——高带切片管墙/长距（喂 AMCL/全局），
  低带切片管矮物（喂避障）。两者作为 costmap 两个观测源或两个 obstacle 层实例（见 2.3）。
- 案例（工业定式）：Clearpath OutdoorNav 的 3D LiDAR 处理链 = **点云滤波 → 高度带滤波 →
  投影 2D scan → costmap**，环境变量 `PCL_TO_SCAN_MIN_HEIGHT`（例 0.2m）/`PCL_TO_SCAN_MAX_HEIGHT`（例 1.2m）。
- 来源：[Clearpath OutdoorNav Collision Avoidance（costmap inputs）](https://docs.clearpathrobotics.com/docs_outdoornav_user_manual/0.9.0/features/collision_avoidance/)、
  [Clearpath 3D LiDAR 传感器配置文档](https://docs.clearpathrobotics.com/docs/ros2humble/ros/config/yaml/sensors/lidar3d/)

**1.3 velodyne_laserscan 单环抽取 —— R2 现状根因，且社区判定"低环不可靠"**
- 现状：`ring` 参数 −1~31，默认 −1 自动按机型选水平环（VLP-16 → ring 8，HDL-32E → ring 23，HDL-64E → ring 57）。
- **校正事实（2026-09-05 检索新增，影响复盘候选）**：ros-drivers/velodyne issue #192 定论——
  该节点**只有选水平环时才物理准确**；LaserScan 是平面消息，斜环投影成"圆锥扫面"，压平到 z=0 后
  range 与真实 3D 点云对不上（极端环误差最大）；曾有维护者主张**干脆删掉用户选环功能**。
  → 复盘候选里"配低环 ring:=13"（下俯环方案）**社区判物理不可靠**，可降级为"仅演示/验证"用法。
- 来源：[ros-drivers/velodyne issue #192](https://github.com/ros-drivers/velodyne/issues/192)、
  [velodyne_laserscan Kilted 文档](https://docs.ros.org/en/ros2_packages/kilted/api/velodyne_laserscan/)、
  [DeepWiki velodyne_laserscan 章节](https://deepwiki.com/ros-drivers/velodyne/3.3-velodyne_laserscan)、
  [ROS Index velodyne_laserscan](https://index.ros.org/p/velodyne_laserscan/)

**1.4 定制多环/自写转换**
- 做法：自写 points→scan 节点（多环合并、可配置环集），或用 ROS1 系 depthimage_to_laserscan 思路（深度图→scan）同源。
- 实际地位：社区默认不走到这一步——1.1 高度带切片已覆盖"多环合成"需求且免维护；只有特殊环权重/多平面需求才自写。
- 来源（思路先例）：[Autonomous navigation with Velodyne VLP-16（ROS Answers，rtabmap→2D occupancy 全链建议）](https://answers.ros.org/question/367191/)、
  WPI 论文示例（sim VLP-16 → 2D 建图/定位/导航，[digital.wpi.edu](https://digital.wpi.edu/downloads/nv9355467)）

### ② 代价地图层：点云直接进 costmap（跳过 2D scan）

**2.1 Nav2 obstacle layer 原生吃 PointCloud2 —— 官方支持，非 hack**
- 做法：`observation_sources` 里 data_type 用 `"PointCloud2"`，配层级 + 源级
  `min_obstacle_height`/`max_obstacle_height` 高度带 → 层内做 2D 栅格标记 + 水平 raycast 清空。
  层本质仍是 2D（把带内点按 xy 落格），但**带高可设到地面**（min≈0），矮物点即进代价地图。
- 参数：marking/clearing 开关、obstacle_max_range（注意 costmap 尺寸与 range 匹配）、
  observation_persistence、expected_update_rate、combination_method（0 覆盖/1 取大/2 取大不覆盖未知）等。
- 边界（社区）：清空 raycast 假设水平视场，稀疏点云清空效率差；近距/死区 clearing 冲突是经典坑
  （见 2.3）。
- R2 注：/velodyne_points 全环直接喂障碍层低带 = 复盘候选"costmap 改吃 points"的官方路径，
  无需改任何驱动源码。
- 来源：[Nav2 Obstacle Layer 参数文档](https://docs.nav2.org/configuration/packages/costmap-plugins/obstacle.html)、
  [Nav2 障碍层中文镜像（fishros）](https://nav2.fishros.com/doc/configuration/packages/costmap-plugins/obstacle.html)、
  [obstacle_range 默认 2.5m 导致"太近才发现"（navigation2 #4299）](https://github.com/ros-navigation/navigation2/issues/4299)

**2.2 Voxel layer / Spatio-Temporal Voxel Layer（3D 体素层）**
- 做法：voxel/obstacle 层之上再加 z 维栅格（z_resolution/z_voxels/origin_z/unknown_threshold/mark_threshold），
  支持 `publish_voxel_map` 可视化"层实际看到了什么"。
- 现代替代 STVL（ROS2）：OpenVDB 稀疏体素 + **voxel_decay 时间衰减清空**（免 raycast），
  显式支持 VLP-16 沙漏形视场（hFOV 可收窄），宣称稠密相机下 costmap CPU 80~110% → 20~50%。
- 边界：体素层是"重的"一步——community 老经验：点云全量 obstacle 层代价高（数十 ms~数 s 级），
  scan 层便宜；对 R2 的 VLP-16 300k pts/s 需要实测 N97 CPU（未实测）。
- 来源：[STVL 仓库（ROS2）](https://github.com/PythonLidar/spatio_temporal_voxel_layer)、
  [STVL README（VLP-16 沙漏 FOV/decay 参数）](https://raw.githubusercontent.com/ashwinvkNV/spatio_temporal_voxel_layer/refs/heads/ros2/README.md)、
  [nonpersistent_voxel_layer（社区变体）](https://index.ros.org/r/nonpersistent_voxel_layer/)、
  [nonpersistent_voxel_layer Kilted 文档](https://docs.ros.org/en/ros2_packages/kilted/api/nonpersistent_voxel_layer/)、
  [costmap_3d：costmap_2d 的 3D 查询扩展（ROS1 octomap 系，参考）](https://github.com/ros-planning/navigation/commit/09dee054745d3bad393ed7d96fa022c379cd9292)

**2.3 多源/多层组合（高低两个源，互不干扰）**
- 做法：一个 obstacle 层内列多个 `observation_sources`，或 **两个 obstacle_layer 插件实例**
  （`obstacle_layer_low` 吃低带 + `obstacle_layer_high` 吃高带，各配自己的 topic 与高度带）。
- 老坑（ROS Answers 经典结论）：多传感器**不要互相 clear**（长距源会把短距源刚标的障碍清掉）——
  用独立层/独立源各管各的；Nav2 docs 对多源合并语义写得含糊（[docs.nav2.org #851](…)），
  分开层 + combination_method 更可控。
- **AMCL 限制**：只吃单一 scan，不支持多激光源合并——要喂 AMCL 必须先合流
  （laser_assembler ROS2 无维护版；ir_laser_tools 仅 ROS1）。
- 来源：[导航栈多传感器分层（ROS Answers）](https://answers.ros.org/question/190381/)、
  [不同高度两传感器更新 costmap（ROS Answers）](https://answers.ros.org/question/383873/)、
  [Kinect+Hokuyo 混合导航：为什么不转 scan / voxel grid / 分层（ROS Answers）](https://answers.ros.org/question/210426/)、
  [Nav2 能否接两个激光（ROS Answers）](https://answers.ros.org/question/369244/)、
  [docs.nav2.org #851（多源语义未定义）](https://github.com/ros-navigation/docs.nav2.org/issues/851)

### ③ 感知/中间表示级

**3.1 点云滤波链 → 障碍输出（PCL 系，工程标准链）**
- 做法：crop box（xy 近距 + z 高度带）→ 统计/半径离群去除 → 体素降采样 → （可选 RANSAC 去地面）→
  聚类 → 障碍。样例配置：Jackal + VLP-16 的 `/velodyne_points/for_costmap` 即此链（z 带例 0.0~0.4m 去地面/天花板）。
- 来源：[nu_jackal_autonav（西北大学，VLP-16+Jackal 全链）](https://github.com/graberj/nu_jackal_autonav)、
  [Velodyne_3D_LiDAR（voxel→ROI→去离群→RANSAC→DBSCAN 处理链示例）](https://github.com/jinhoyoho/Velodyne_3D_LiDAR)

**3.2 3D SLAM 直出 2D occupancy / 3D 重建切片**
- 做法：rtabmap 等同时维护 3D 点云 + **2D occupancy 栅格**（global costmap 直接用）；
  nvblox（NVIDIA，GPU）3D 重建后对 Nav2 出 **ESDF 2D 切片**——但官方明示切片是**固定高度平面**，
  "仅支持平地为 2D 导航"，矮物/坡面要靠调 esdf_min/max_height 之类参数（例 esdf_min_height=0.2）。
- 边界：nvblox 为 GPU/Jetson 系，对 N97 CPU 现实性低（未实测，标注待评估）。
- 来源：[rtabmap 直出 2D occupancy（ROS Answers）](https://answers.ros.org/question/367191/)、
  [nvblox 斜坡环境与 ESDF 切片讨论（NVIDIA 论坛）](https://forums.developer.nvidia.com/t/isaac-ros-nvblox-how-to-use-in-slope-environment/333413/6)

**3.3 多平面策略（低平面管可通行、高平面管墙）**
- 做法：把感知拆成"低平面可通行性"（curb/矮箱/床沿这类**越不过去**的矮物当墙）+ "高平面墙/长距"，
  与 1.2 双切片呼应，属规划语义层的组织方式。
- 来源（思路先例）：[低成本 ROS 移动机器人（TEB+costmap 局部避障实例，MDPI）](https://www.mdpi.com/1999-5903/18/8/427) 仅为佐证存在性，弱参考

### ④ 物理/传感器布局（工业向；绕开单雷达限制）

**4.1 双雷达高低分工（工业常态）**
- 学术例：清华 2011（水平 + **倾斜**双激光融合，倾斜雷达专司道路边界等低矮障碍 + 角度势场法导航）。
- 产业例：AGV 常用立体布局——**低置 2D 雷达管避障/墙 + 顶部 3D 雷达管立体空间 + 超声波补低矮盲区**
  （厂商宣传文案，仅作布局存在性佐证，性能数字不可当真）；
  AiTEN TP100 双激光融合 ±10mm、富唯双激光+视觉 ±2mm（同为宣传口径）。
- R2 参照：此即 planning-control-roadmap §3.3 方案 b（双雷达）的思想来源，区别是 R2 议题里
  双雷达都高置（全景避障 vs 高密度建图），没有低置雷达——若选"低矮物优先"路线，可衍生
  "顶部 VLP-16 全景 + 低置补盲传感器"变体（传感器布局决策未做）。
- 来源：[双激光雷达融合导航（清华大学，水平+倾斜分工）](https://search.napstic.cn/literature/conference/0720130700026110)、
  [AGV 立体传感器布局与低矮检测（见行智能）](http://www.jxagv.com/news/detail/1337.html)、
  [AiTEN 双雷达硬件（AGV 无人叉车）](https://www.aitenrobot.com/tw/%e6%96%b0%e8%81%9e/agv-unmanned-forklift-hardware)、
  [3D 视觉语义检测低矮物：劳保鞋/扳手（威迈尔，中国 AGV 网）](https://m.chinaagv.com/news/detail/202505/33232.html)、
  [双雷达+视觉融合 ±2mm（联基 AGV，宣传）](https://www.linkagv.com/support/detail/3057.html)

**4.2 大垂直 FOV / 面阵固态雷达（单台覆盖近地）**
- 做法：选垂直视场下缘贴近车体近地的大 FOV 机型（顶置即自带近车一圈下视覆盖），
  或 1° 级角分辨面阵固态雷达（北醒 CE30 类，AGV 低矮识别宣传例）——
  具体机型与规格以官方数据表为准（本次检索未逐机型核实规格数字，标注待核实）。
- R2 参照：planning-control-roadmap §3 已有"VLP-16 vs MID-70"对比（70.4° 圆形视场，朝前装），
  A/B 触发条件已满足未做；4.2 是"换/加传感器"线的同族选项。
- 来源：[Mid-70 规格（roadmap §3.2 已引，不重复）](https://www.livoxtech.com/mid-70/specs)、
  [北醒 CE30 面阵识别低矮障碍（厂商宣传）](http://www.jxagv.com/news/detail/1334.html)

**4.3 装位/姿态调整（降低光带、给下视角）**
- 做法：压低安装高度 / 整体下俯 / 只俯视近区。代价：保 360° 时俯仰破坏环对称；下俯后远距/高物覆盖变差；
  对高置全景需求（R2 现状）是取舍而非解。与 1.3 合并看：**光带几何问题用"选环"修不了（物理不准确），
  只能改安装或改合成方式**。

### ⑤ 行为/运行策略（不给感知加数据，次要）

- 降速/近距慢行扩大反应窗口、footprint 约束、把"已知矮物区"当静态墙标进地图（比赛场地语义先验——
  Robocon 场地固定，静态已知物直接进地图层即可，无需感知重解）。一笔带过，非主线。

---

## 三、对复盘 09-04 修法候选的校正与新增（2026-09-05 新事实）

复盘 §六-3/§10.4 后置候选三条，对照社区清单校正：

| 复盘候选 | 校正后定位 | 依据 |
|:---|:---|:---|
| ① 多环/低环 scan | **保留，但社区标准实现 = pointcloud_to_laserscan 高度带切片**（1.1），零源码改动、apt 现成；"自写多环节点"降级为可选定制 | §二 1.1/1.4 |
| ② costmap 改吃 points | **官方原生正路**：obstacle layer `data_type: PointCloud2` + 高度带（2.1），无需改源码 | §二 2.1 |
| ③ 下俯环（ring:=低环） | **社区判物理不可靠**（1.3，issue #192）——低环 range 与 3D 点云对不上；降级为"仅验证用"，不作为交付形态 | §二 1.3 |
| （新增）④ 高/低双切片进双源/双层 | 社区/工业定式（1.2 + 2.3）：现 /scan 高带管墙与 AMCL 不动，**新增 /scan_low 或 points 低带只管 costmap**，迁移面最小 | §二 1.2/2.3 |
| （新增）⑤ 物理布局（双雷达/换大 FOV/降装高） | 已存在 roadmap §3 传感器议题线（A/B 未做），与本修法正交，不急于本决策 | §二 4.x |

**一句话校正结论**：R2 需要的"让低环数据进 2D 避障信息"在社区是**成熟现成问题**——
主流解法（高度带切片或直接吃 points）**都不需要改任何 velodyne 上游源码**；
唯一需要"改源码"的路线（velodyne_laserscan 多环化）反而是社区里没人做的事（因为单环/多环需求
已被 pointcloud_to_laserscan 覆盖，且 velodyne_laserscan 的设计定位就是单水平环）。

---

## 四、落地前开放点（决策与部署事实，未定）

1. **N97 安装路径**：pointcloud_to_laserscan 走 apt（需 N97 外网，[ros2-ops.md §1](../ros2-ops.md)
   "外网连通性不可想当然"）还是源码 build 进既有工作区——部署路径待定（此调研不实施，仅留档）。
2. **relog 联动**：若日后新增低带 scan 话题，重录话题清单（relog-operation.md）需同步增列。
3. **AMCL 边界**：AMCL 只吃单一 scan（2.3），若低带 scan 用于定位需先合流——R2 现状
   （AMCL 用现有 /scan）无此需求，仅记录防误用。
4. 本文为方向池，**不构成修法决策**；是否把某候选升级实施，沿用复盘后置裁决与 09-10 收口节奏。

---

## 五、来源（2026-09-05 WebSearch 核实）

> 核实方式：WebSearch 两轮 11 查 + 来源页交叉；官方仓库/文档优先（ros-perception、ros-drivers/velodyne、
> docs.nav2.org、Clearpath docs、packages.ros.org），其次 ROS Answers/Stack Exchange 等社区，厂商新闻仅作
> 布局存在性佐证并已标注"宣传"。**所有实现效果类结论均未实测**。

- [pointcloud_to_laserscan（ros-perception 官方仓库）](https://github.com/ros-perception/pointcloud_to_laserscan) ｜ [ROS Index](https://index.ros.org/p/pointcloud_to_laserscan/) ｜ [Kilted API 文档](https://docs.ros.org/en/ros2_packages/kilted/api/pointcloud_to_laserscan/index.html) ｜ [Humble apt 包 2.0.1](http://packages.ros.org/ros2-testing/ubuntu/pool/main/r/ros-humble-pointcloud-to-laserscan/)
- [velodyne_laserscan Kilted 文档（ring −1 自动选环表）](https://docs.ros.org/en/ros2_packages/kilted/api/velodyne_laserscan/) ｜ [DeepWiki velodyne_laserscan](https://deepwiki.com/ros-drivers/velodyne/3.3-velodyne_laserscan) ｜ [ros-drivers/velodyne #192（非水平环物理不准确）](https://github.com/ros-drivers/velodyne/issues/192)
- [Nav2 Obstacle Layer 参数（data_type: PointCloud2 / min·max_obstacle_height）](https://docs.nav2.org/configuration/packages/costmap-plugins/obstacle.html) ｜ [fishros 中文镜像](https://nav2.fishros.com/doc/configuration/packages/costmap-plugins/obstacle.html) ｜ [navigation2 #4299（obstacle_range 近距才标记）](https://github.com/ros-navigation/navigation2/issues/4299) ｜ [docs.nav2.org #851（多源合并语义）](https://github.com/ros-navigation/docs.nav2.org/issues/851)
- [多传感器分层导航（ROS Answers 190381）](https://answers.ros.org/question/190381/) ｜ [不同高度双传感器 costmap（383873）](https://answers.ros.org/question/383873/) ｜ [Kinect+Hokuyo 为什么不转 scan/分层/voxel（210426）](https://answers.ros.org/question/210426/) ｜ [Nav2 接两个激光（369244，AMCL 单源限制）](https://answers.ros.org/question/369244/) ｜ [navigation/Troubleshooting 镜像（TF 高度/quick fix）](https://vectorlinux.osuosl.org/pub/ros/ros_wiki_mirror/navigation(2f)Troubleshooting.html)
- [STVL（ROS2，OpenVDB + decay + VLP-16 沙漏 FOV）](https://github.com/PythonLidar/spatio_temporal_voxel_layer) ｜ [STVL README 原文](https://raw.githubusercontent.com/ashwinvkNV/spatio_temporal_voxel_layer/refs/heads/ros2/README.md) ｜ [nonpersistent_voxel_layer](https://index.ros.org/r/nonpersistent_voxel_layer/) ｜ [costmap_3d（octomap 3D 查询，ROS1 参考）](https://github.com/ros-planning/navigation/commit/09dee054745d3bad393ed7d96fa022c379cd9292)
- [Clearpath OutdoorNav costmap inputs（PCL_TO_SCAN_MIN/MAX_HEIGHT 工业默认）](https://docs.clearpathrobotics.com/docs_outdoornav_user_manual/0.9.0/features/collision_avoidance/) ｜ [Clearpath 3D LiDAR 配置](https://docs.clearpathrobotics.com/docs/ros2humble/ros/config/yaml/sensors/lidar3d/)
- [nu_jackal_autonav（VLP-16+Jackal 点云滤波链实例）](https://github.com/graberj/nu_jackal_autonav) ｜ [Velodyne_3D_LiDAR 处理链](https://github.com/jinhoyoho/Velodyne_3D_LiDAR) ｜ [VLP16 转 LaserScan 配置实战（CSDN）](https://blog.csdn.net/mac99/article/details/153243949) ｜ [点云转 scan 避坑（CSDN）](https://blog.csdn.net/o1p2q3r/article/details/154226860)
- [Autonomous navigation with VLP-16（ROS Answers，rtabmap 2D occupancy）](https://answers.ros.org/question/367191/) ｜ [nvblox 斜坡/ESDF 切片限制（NVIDIA 论坛）](https://forums.developer.nvidia.com/t/isaac-ros-nvblox-how-to-use-in-slope-environment/333413/6) ｜ [WPI 论文（sim VLP-16 2D 导航）](https://digital.wpi.edu/downloads/nv9355467)
- [双激光融合导航（清华 2011，水平+倾斜分工）](https://search.napstic.cn/literature/conference/0720130700026110) ｜ [见行 AGV 低矮避障布局（宣传）](http://www.jxagv.com/news/detail/1337.html) ｜ [AiTEN 双雷达（宣传）](https://www.aitenrobot.com/tw/%e6%96%b0%e8%81%9e/agv-unmanned-forklift-hardware) ｜ [威迈尔 3D 语义低矮检测（宣传）](https://m.chinaagv.com/news/detail/202505/33232.html) ｜ [联基双雷达+视觉（宣传）](https://www.linkagv.com/support/detail/3057.html)

> 厂商新闻来源（见行/AiTEN/威迈尔/联基/北醒）仅佐证"工业上确有低矮检测布局"这一存在性结论，
> 其中性能数字（±mm 精度等）为宣传口径，不可引用。

---

## 相关

- [复盘 09-04（断点证据 + 修法后置裁定）](../retrospect/2026-09-04_lowobstacle_breakpoint.md) ｜ [analysis-methods.md 主题 A5（ring→仰角标定，低环数据的来源）](../analysis-methods.md)
- [planning-control-roadmap.md](../roadmaps/planning-control-roadmap.md) §三（传感器 A/B 线，本清单待其迁移/连接，另行发起）
- [07-handover.md §三/§四](../07-handover.md)（遗留现象与低物待办措辞）
- [ros2-ops.md §1/§2](../ros2-ops.md)（N97 外网/构建同步纪律）
