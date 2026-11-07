# 自主探索 × 离线先验导航 · 方案调研与文档核验

> **日期**：2026-11-07
> **任务**：核对"自主探索 / 离线先验"两条线的文档与路线正确性；梳理社区用得最多、与本项目最匹配的方案；结合现有硬件外设做可行性评估。
> **状态**：调研完成（结论可回查；**未实测项逐条标注**，不写成已验证）。
> **平台范围**：老车 R2-OLD（LD06 2D 线）+ 新车 R2-NEW（MID-70 / MID-360 / D435 3D 线）+ 硬件可行性。
> **核实方式**：本地知识库优先（`doc/`、LocoWiki、既有 retrospect/survey）→ 缺口处 WebSearch/WebFetch 官方仓库、官方文档、论文与社区帖（2026-11-07）。
> **关联**：[two-car-architecture.md](../two-car-architecture.md) ｜ [planning-control-roadmap.md](../roadmaps/planning-control-roadmap.md) ｜ [explore-plan.md](../minimal-loop2/explore-plan.md) ｜ [s1-readiness-gap.md](../old-car/s1-readiness-gap.md) ｜ [ld06-dual-lidar.md](../old-car/ld06-dual-lidar.md) ｜ [3d-lidar-2d-navigation-survey.md](3d-lidar-2d-navigation-survey.md)
> **证据等级**：✅ 本地/实机实测 ｜ 📘 官方源码或官方文档核实 ｜ 🌐 论文/社区核实 ｜ 🧠 工程推理（未实测，不得当结论用）

---

## 〇、结论先行

**1）文档与路线总体正确，但有 3 处必须修正、2 处需补条件：**

| 编号 | 问题 | 等级 | 处置 |
|:---|:---|:---:|:---|
| P1 | [explore-plan.md §3.1.2](../minimal-loop2/explore-plan.md) 与 [explore_params.yaml](../../r2_bringup/config/explore_params.yaml) 称 `return_to_init` "不存在"、另外 7 个参数"未声明"——**与上游源码和 README 矛盾** | 中 | ✅ **2026-11-07 20:10 干净复测已确认**：上游正确、本地文档错误；文档已修正——见 §2.3 末「复测结果」 |
| P2 | `nav2_params_low.yaml` 的 local/global 两层仍订阅 `/velodyne_points`（G4）；老车已撤 VLP-16 | 高 | S1 首跑前另建老车参数文件，**不要改历史文件** |
| P3 | roadmap §5.5 对 `roadmap_explorer` 漏记关键约束：**仅 Humble 实测、FastDDS 工作不佳、推荐 CycloneDDS、10% 是 Jetson Xavier 不是 Nano** | 中 | 在 roadmap 追加条件注（只增不删） |
| P4 | `slam_toolbox_mapping.yaml` 的 `max_laser_range: 20.0` 抄自 VLP-16；LD06 室内有效回波实测仅 6.08 m | 中 | 空旷场地量程实测后对齐，勿把驱动常量 25 当规格 |
| P5 | `nav2.rviz` 未安装到 share（G8）、`/map` 录包 QoS override 文件缺失（G7） | 低 | S1 首跑前的工程项，不阻塞方案判断 |

**2）"用得最多"（社区/生态事实标准）：**

- **2D 自主探索**：`explore_lite`（m-explore-ros2）——Nav2 生态里引用最广、教程最多的轻量前沿探索器。
- **2D SLAM**：`slam_toolbox`——ROS 2 Humble 下最常用的 2D 建图/定位包，与 Nav2 原生配套。
- **2D 先验定位**：`map_server` + `AMCL`——Nav2 官方默认的已知地图定位链路。
- **3D LIO**：`FAST-LIO2`——Livox 生态与开源社区的事实标准之一（R2 已于 08-24 在 VLP-16 上实车验证）。
- **3D 探索研究**：`TARE`——RSS 2021 最佳论文 + 最佳系统论文，CMU/DARPA SubT 使用；但**只有 ROS1 官方实现**。

**3）"最适合 R2"（工程判断，🧠）：**

- **老车 S1**：`LD06 → slam_toolbox → Nav2 → explore_lite`。现有三份配置方向正确，缺的是 G4 参数文件 + 实车安装几何 + 首跑。
- **老车 S2**：双 LD06 **优先独立 `/scan` + `/scan_low`**，不合并成单帧——LD06 无硬件同步，合并会引入时间/高度语义混杂（§5.1）。
- **新车**：**MID-70 的 70.4° 圆视场不适合 360° 前沿探索**；探索正解是 MID-360（360°×59°）。MID-70 适合前向稠密建图/避障。先验导航用 `FAST-LIO2 + 先验 PCD 定位`，再投影 2D 供 Nav2。
- **VLP-16**：360°×30°，若新车在 MID-360 到位前需要探索，它比 MID-70 更合适；去向仍待用户定夺（§六 O7）。
- **N97**：4C/4T、12W，老车 2D 栈可行；**不要同时叠 3D SLAM + Nav2 + 探索**。
- **Jetson Nano**：JetPack 4 / Ubuntu 18.04 / 无原生 Humble，只适合做纯 AI 推理协处理器，**不建议做新车主算力**。

**4）路线判断**：A 阵营（离线先验）与 B 阵营（实时探索）的划分正确；Robocon 主场景走 A、未知/变更场地走 B 的决策正确。B 阵营的 2D 轻量链路（SLAM Toolbox + explore_lite）与 N97 算力匹配。**两条线不能同时跑**（`map→odom` 单发布者约束），`nav2_explore.launch.py` 已正确移除 AMCL/map_server。

---

## 一、范围、方法与证据等级

### 1.1 调研边界

| 维度 | 覆盖 | 不覆盖 |
|:---|:---|:---|
| 平台 | 老车 LD06 2D 线；新车 MID-70/MID-360/D435 3D 线 | 机械结构设计、电源详细选型、底盘运动学 |
| 探索 | 2D 前沿探索、3D 前沿/体素探索、学习型方法（仅点名） | 多机器人协同探索的深入实现 |
| 先验 | 2D 地图 + AMCL；slam_toolbox localization；3D PCD + ICP 定位；3D→2D 投影 | 高精地图（HD Map）、语义地图、V2X |
| 硬件 | 现有/已规划外设的可行性与瓶颈 | 采购报价、供应商交期 |

### 1.2 检索路径（关键查询，2026-11-07）

- 本地：`grep/rg` 全 `doc/`；重点读 `explore-plan.md`、`s1-readiness-gap.md`、`ld06-dual-lidar.md`、`planning-control-roadmap.md §2/§5.5`、`two-car-architecture.md §6/§10`、LocoWiki §U4.7。
- 网络（缺口补网）：`explore_lite return_to_init`、`frontier_exploration_ros2 benchmark`、`roadmap_explorer CycloneDDS FastDDS`、`TARE RSS 2021`、`FAST-LIO localization ROS2 Humble`、`LD06 multiple lidar synchronization`、`MID-70 MID-360 FOV`、`Jetson Nano JetPack EOL`、`pointcloud to grid ROS2 Humble`。
- 原则：官方仓库/源码 > 官方文档 > 论文/社区；**同一结论至少一个可回查链接**；未实测项标 🧠 或"未实测"。

### 1.3 证据等级说明

- ✅：本仓实机/VM 实测、原始日志、既有 bag 分析结论（可直接引用）。
- 📘：官方源码、官方 README、官方产品页/文档（版本与日期已核）。
- 🌐：论文、社区帖子、第三方对比（**作者自报或未复现**，引用时保留限定语）。
- 🧠：基于上述事实的工程推理，**不是实测结论**；落地前需验证。

---

## 二、文档与路线正确性核验

### 2.1 文档代际与权威性

2026-11-06 平台分叉后，文档分为"VLP-16 历史基线"与"老车/新车现役"两套。核验时先认代际，避免拿旧结论判新平台。

| 文档 | 定位 | 核验判断 |
|:---|:---|:---|
| [01-plan.md](../01-plan.md) | VLP-16 时代五阶段总纲 | 历史基线；头部已注 11-06 分叉。**不作为老车现状**，路线思想仍可参考 |
| [02-progress.md](../02-progress.md) / [07-handover.md](../07-handover.md) | 状态板/交接 | Phase 0~3 百分比是 VLP-16 基线；§六/S1 快照才是老车口径。已注 |
| [planning-control-roadmap.md](../roadmaps/planning-control-roadmap.md) | 规划控制路线 | §2.1 A/B 阵营判断正确；§5.5 探索选型需补条件（P3） |
| [two-car-architecture.md](../two-car-architecture.md) | 两车架构/接口/TF/待定 | **现役上位文档**；§6 话题/TF 契约、§10 待定项与本次调研一致 |
| [old-car/ld06-dual-lidar.md](../old-car/ld06-dual-lidar.md) | S1/S2 执行 | 现役；P7 已实测 `/scan` 规格与 crop 行为 |
| [old-car/s1-readiness-gap.md](../old-car/s1-readiness-gap.md) | S1 缺口清单（23 项） | 现役；G4/G8/G10/G11/G13 等直接约束首跑 |
| [minimal-loop2/explore-plan.md](../minimal-loop2/explore-plan.md) | 2D 探索执行稿 | 主体链路正确；**§3.1.2 参数声明结论错误（P1）**；§十与 07-handover 的参数文件口径冲突（P2 关联） |
| [surveys/3d-lidar-2d-navigation-survey.md](3d-lidar-2d-navigation-survey.md) | 低物感知数值权威 | 09-06 实车更新；1.59 m 盲区等数值以它为准 |
| [ros2-ops.md](../ros2-ops.md) | 操作规范 | §12 感知覆盖判据、§11 costmap 读数判据可直接复用 |

**结论**：文档代际标注基本到位；真正会误导执行的是 P1（参数声明）与 P2（老车参数文件）。

### 2.2 路线正确性判断

**A 阵营：离线先验（已知地图 + 定位 + Nav2）**

- 适用：Robocon 场地固定、可提前建图；比赛时环境大体不变。
- 标准链路：`slam_toolbox` 建图 → `map_saver` → `map_server` + `AMCL` → Nav2 规划/控制。
- 判断：**正确**。这是移动机器人已知地图导航的主流做法，也是 Nav2 官方默认组合。
- 边界：场地变更、临时障碍、地图老化会直接降低定位/规划质量；需要地图更新策略与 costmap 动态层兜底。

**B 阵营：实时探索（未知/变更场地）**

- 适用：场地未知、或 A 的地图失效时的兜底。
- 标准链路：`/scan` → `slam_toolbox`（`online_async`，发布 `/map` 与 `map→odom`）→ Nav2 `global_costmap` → `explore_lite` 前沿检测 → `NavigateToPose` → Nav2 → `/cmd_vel`。
- 判断：**正确**，且是 2D 轻量探索的标准组合。
- 关键前提（已核）：
  - `global_costmap.track_unknown_space: true`（[nav2_params_low.yaml:295](../../r2_bringup/config/nav2_params_low.yaml#L295)）——否则未知区不进入代价地图，前沿检测不到。
  - `nav2_explore.launch.py` 已移除 `map_server`/`amcl`/`lifecycle_manager_localization`，由 `slam_toolbox` 单独发布 `map→odom`——**正确**，避免 TF 双发布者。
  - `use_sim_time: false`（实车）与 `slam_toolbox` 一致。
- 边界：`explore_lite` 是贪心前沿选择，不保证全局最优；场地大/房间多时可能来回折返（§3）。

**两阵营的互斥性**

- `map→odom` 只能有一个发布者：AMCL 或 slam_toolbox，**不能同时**。
- 切换模式必须整栈重启（或至少确保旧定位节点退出），不能只改参数。

### 2.3 P1：`return_to_init` / 7 参数"未声明"结论错误

**本地文档的原始结论**（三处一致）：

- [explore-plan.md:334](../minimal-loop2/explore-plan.md#L334)：`return_to_init` **不存在**，不在 `param list` 中。
- [explore-plan.md:335](../minimal-loop2/explore-plan.md#L335)：另 7 项**未声明**，代码用 `get_parameter_or` 读取。
- [explore_params.yaml:24/46](../../r2_bringup/config/explore_params.yaml#L24)：确认不存在，保持注释。

**上游证据链（📘，commit `326cf8a`，即 N97 构建所用版本）：**

[explore/src/explore.cpp#L65-L72](https://github.com/robo-friends/m-explore-ros2/blob/326cf8a/explore/src/explore.cpp#L65-L72)：

```cpp
this->declare_parameter<float>("planner_frequency", 1.0);
this->declare_parameter<float>("progress_timeout", 30.0);
this->declare_parameter<bool>("visualize", false);
this->declare_parameter<float>("potential_scale", 1e-3);
this->declare_parameter<float>("orientation_scale", 0.0);
this->declare_parameter<float>("gain_scale", 1.0);
this->declare_parameter<float>("min_frontier_size", 0.5);
this->declare_parameter<bool>("return_to_init", false);
```

同文件 L81-88 用 `get_parameter` 读取上述 8 项。README 也明确写有 `return_to_init`（"Set to True to make the robot return to its starting pose after exploration finishes"）。

**本地冒烟输出（✅，但异常）：** [raw_explore_smoke_n97_2026-11-07_1253.txt](../raw_data/raw_explore_smoke_n97_2026-11-07_1253.txt) 中 `ros2 param list /explore_node` 只列出 `costmap_topic`、`costmap_updates_topic`、`qos_overrides.*`、`robot_base_frame`、`transform_tolerance`、`use_sim_time`——正好是 `costmap_client.cpp` 侧的参数，**缺 `explore.cpp` 的 8 项**。

**如何解释这个矛盾（假设，未证实）：**

1. **同名残留节点**：`ros2 node list` 按名字去重，看不到两个 `/explore_node`；`ros2 param list /explore_node` 可能问到旧的同名进程。旧进程若来自更早的构建，就只有 5 个参数。
2. **overlay/install 顺序**：`ros2 run explore_lite explore` 命中了另一个工作区或旧 install 的 `explore_lite`，不是 `326cf8a` 的构建。
3. **daemon 缓存/抓取不完整**：`ros2 daemon` 缓存了旧的图/参数信息，或命令在节点初始化窗口内执行。

**影响评估：**

- 当前 `explore_params.yaml` 把 `return_to_init` 注释掉，源码默认 `false`，**首跑行为不受影响**。
- 但文档说"写入会报未声明"是**错误指导**：用户若想开自动返航，会被文档吓退；同时"7 项参数不能用 `param get` 验证"也是错的——`declare_parameter` 后 `param get` 应可见。
- 真正需要修的是**文档与复测结论**，不是运行配置。

**干净复测步骤（建议由用户在 N97 执行；AI 不代跑）：**

```bash
# 1. 清残留：确认没有别的 explore 进程
pgrep -af "explore_lite|/explore" || echo "no explore process"
# 2. 清 daemon 缓存
ros2 daemon stop
# 3. 只 source 目标工作区（避免 overlay 串台）
source /opt/ros/humble/setup.bash
source ~/Lin_workspace/explore_ws/install/setup.bash
# 4. 起节点（保持前台，另开终端查询）
ros2 run explore_lite explore --ros-args \
  --params-file ~/Lin_workspace/explore_ws/install/explore_lite/share/explore_lite/config/params_costmap.yaml
# 5. 另开终端查
ros2 node list
ros2 param list /explore_node
ros2 param get /explore_node return_to_init
ros2 param get /explore_node planner_frequency
```

**判据**：`param list` 出现 `return_to_init`、`planner_frequency`、`visualize` 等 8 项，且 `param get` 返回值与 YAML 一致 → 文档结论必须改；若仍只有 5 项，再查 `ros2 run -p explore_lite` 解析到哪个 install 路径与进程 PID。

> 处置纪律：**先复测，后改文档**；改 `explore-plan.md` / `explore_params.yaml` 前按"只增不删"给用户过目。

#### 复测结果（2026-11-07 20:10，N97，已完成）

> 本节为事后追加；上方 P1 判定与复测步骤保留原样（翻案留痕）。原始数据
> `doc/raw_data/raw_explore_p1_retest_n97_2026-11-07_2010.txt`（本地，不入 git）。

**裁定：`explore.cpp:65-72` 的 8 项 `declare_parameter` 属实，本文件 P1 判定成立；
本地文档的「不存在 / 未声明」结论错误，已修正。**

**关键修正**：上方给出的复测步骤**不足以得到正确结论**——只起节点时它仍会输出同样的 5 项，
会被误读成"上游不成立"。实测发现节点构造有三段串行阻塞：

| 阻塞点 | 位置 | 等待对象 | 无此项时 |
|:---:|:---|:---|:---|
| ① | `costmap_client.cpp:89` | `/global_costmap/costmap` 首帧 | 8 个 declare 不执行 |
| ② | `costmap_client.cpp` TF 段 | `map → base_link` | 同上 |
| ③ | `explore.cpp:112` | `/navigate_to_pose` action server（无超时） | declare 已执行但不 spin，参数服务不响应 |

**正确复测姿势**（A/B 同进程对照）：起节点 → 查一次（A 腿）→ 发 costmap（用 `-r 1` 连续发；
`--once` 会因 DDS 发现未完成丢消息）→ 发静态 TF `map→base_link` → 起假 `NavigateToPose`
action server → 再查（B 腿）。

| 腿 | `param list` |
|:---|:---|
| A（仅节点） | 9 项：costmap 侧 4 + `use_sim_time` + qos_overrides×4 |
| B（补齐三件套） | 17 项：上述 9 + `return_to_init` / `planner_frequency` / `visualize` / `potential_scale` / `orientation_scale` / `gain_scale` / `min_frontier_size` / `progress_timeout` |

B 腿 `param get`：`return_to_init=False`、`planner_frequency=0.15`、`visualize=True`、`potential_scale=3.0`。

**连带结论**：explore_lite 在"只有雷达"的裸环境下**无法**用 `param list` 验参数；
首跑须起齐 slam_toolbox + Nav2 后再验。

### 2.4 P2：老车参数文件与 `/velodyne_points` 冲突（G4）

**事实**（✅ 本地配置）：

- local costmap：`observation_sources: "scan velodyne_low"`（[nav2_params_low.yaml:250](../../r2_bringup/config/nav2_params_low.yaml#L250)），`velodyne_low.topic: /velodyne_points`（[L268-L269](../../r2_bringup/config/nav2_params_low.yaml#L268-L269)）。
- global costmap：独立 `obstacle_low_layer`，同样订阅 `/velodyne_points`（[L322-L324](../../r2_bringup/config/nav2_params_low.yaml#L322-L324)）。
- 老车 VLP-16 已撤，`/velodyne_points` 无发布者。

**影响：**

- ObstacleLayer 会等待/告警；低带 mark 源实际为空，低物避障能力与 VLP-16 时代不等价。
- 若直接拿 `nav2_params_low.yaml` 跑 S1，local/global 的预期行为与配置注释不符，排障时容易误判为"explore_lite 不工作"。

**口径冲突：**

- [explore-plan.md §十](../minimal-loop2/explore-plan.md) 写"两种模式共用同一份参数文件"。
- [07-handover.md §五](../07-handover.md) 写"老车 `nav2_params_low.yaml` 里的 `velodyne_low` 源不可用，必须另建参数；不要直接改历史文件"。
- **后者与 G4 一致，应作为现行口径**；前者需要修正或加注。

**处置：** 新建老车专用参数（建议名 `nav2_params_ld06.yaml` 或 `nav2_params_oldcar.yaml`），保留 `scan` 源，移除/替换 `velodyne_low`；`nav2_params_low.yaml` 作为 VLP-16 历史文件不动。命名与放置位置待用户定（G23）。

### 2.5 P3：roadmap §5.5 的条件缺失

| roadmap 原表述 | 核验结果 | 需要补的条件 |
|:---|:---|:---|
| explore_lite "2026-04 仍在更新" | ✅ 最新 commit 2026-06-01（#51），2026-04-08 有 Humble 相关更新 | 可更新为"2026-06 仍在维护"；仍无二进制，需源码构建 |
| frontier_exploration_ros2 "338.6m→263.7m、9:47→7:22" | ✅ 与仓库 benchmark 表一致（DP 变体 263.72 m/442 s vs m_explore 338.61 m/587 s） | **作者自报、Gazebo 仿真、TurtleBot3 Waffle Pi**；非 R2 实测 |
| roadmap_explorer "实测 3520㎡；Jetson 上单核 ~10%" | ✅ README 原文：3,520 sq.m；**Jetson Xavier** 单核 ~10%，全局重定位时 20-25% | 补"Xavier 不是 Nano"；补"**仅 Humble 实测**"；补"**FastDDS 目前工作不佳（README 原文），推荐 CycloneDDS**" |
| TARE "RSS 2021 最佳论文" | ✅ 同时获 **Best Paper + Best System Paper**；官方仓库为 ROS1 Melodic/Noetic | 补"ROS2 移植非官方"；"N97 扛不住"是推断，未实测 |
| dynamic-window-frontier / rrt_exploration | ⚠️ 未找到可回查的维护中 ROS2 包 | 标"来源缺失/未核实"，不作为选型依据 |

**最关键的一条**：roadmap 把 `roadmap_explorer` 列为"探索效率不够时的第二选择"，但 R2 跨机 DDS 现用 FastDDS（`r2_bringup/config/dds/fastdds_peer_n97.xml`）。README 明确说"does not work well with FastDDS"、"recommended to use CycloneDDS"。**采用它意味着切换 DDS 栈**，这不是一个"换个包"级别的决策。roadmap 的排序应加此条件，或把 `frontier_exploration_ros2` 提为"未声明 DDS 约束（未实测）"的第二选择。

### 2.6 P4：LD06 量程与 `max_laser_range: 20.0`

- [slam_toolbox_mapping.yaml](../../r2_bringup/config/slam_toolbox_mapping.yaml) 的 `max_laser_range: 20.0` 抄自 VLP-16 母本。
- LD06 驱动消息 `range_max=25.0` 是**驱动常量**，不是传感器规格（[ld06-dual-lidar.md P7](../old-car/ld06-dual-lidar.md)）。
- N97 室内实测有效回波最大 **5.94~6.08 m**（3 帧，室内环境限制）；空旷场地量程仍待测。
- 影响：20.0 会把远端噪点/稀疏回波纳入 scan matching，可能导致地图毛刺或假障碍。
- 处置：空旷场地实测后，把 `max_laser_range` 设为"实测有效量程 + 余量"（🧠 建议 8~12 m，待实测）；当前先标"待调"。

### 2.7 其他已登记缺口（不重复展开）

- G8：`nav2.rviz` 未被 `setup.py` 安装到 share，`rviz:=true` 加载不到配置。
- G7：`ros2 bag record` 录 `/map` 需 `--qos-profile-overrides-path`（transient_local），override yaml 尚未建。
- G10/G13：LD06 安装几何（z/x/y/pitch/yaw）未实车量测，`z=0.18` 是占位。
- G14：N97 供电长跑未测（历史 18m36s 掉电已定位为接线端子松动，非驱动问题）。
- G17：S1 的 EKF 基线对照没有量化阈值。
- G21：README 快速启动仍是 VLP-16/EKF 版本，老车应走 LD06 + slam_toolbox。

### 2.8 核验结论

- **路线正确**：A/B 两阵营、2D 探索链路、`map→odom` 单发布者、`track_unknown_space` 前提均成立。
- **文档需修**：P1（参数声明）是事实错误；P2（老车参数文件）是执行阻塞；P3（roadmap 条件）是选型误导风险；P4（量程）是参数待调。
- **不要动历史文件**：`nav2_params_low.yaml`、`01-plan.md` 的 VLP-16 基线保留；老车走新参数/新文档，符合"只增不删"。

---

## 三、自主探索方案全景

### 3.1 分类

| 类别 | 代表 | 适用 |
|:---|:---|:---|
| 2D 前沿探索（贪心） | explore_lite / m-explore-ros2 | 2D 激光、室内、轻量算力 |
| 2D 前沿探索（全局排序） | frontier_exploration_ros2、roadmap_explorer | 2D 激光、场地较大、追求效率 |
| 3D 前沿/体素探索 | TARE、FUEL、GBP、NBVP | 3D 激光、无人机/腿足/复杂 3D 环境 |
| 学习型探索 | ARiADNE 等 | 研究；训练/部署成本高 |
| 混合（3D 感知→2D 探索） | 3D 点云投影 + explore_lite | 地面机器人、Nav2 2D 规划 |

### 3.2 2D 方案对比

| 方案 | 方法 | 维护/生态（2026-11-07） | Humble | 算力/依赖 | 传感器假设 | 对 R2 的适配 | 来源 |
|:---|:---|:---|:---:|:---|:---|:---|:---|
| **explore_lite**（m-explore-ros2） | 前沿检测 + 黑名单 + `NavigateToPose` 循环；贪心选择 | 活跃；最新 commit 2026-06-01；**无二进制，源码构建** | ✅ | 轻量；C++；依赖 Nav2 costmap | 2D `/scan` 或 costmap；需未知区 | **老车 S1 首选**；配置已在位，未联跑 | [repo](https://github.com/robo-friends/m-explore-ros2) ｜ [源码 326cf8a](https://github.com/robo-friends/m-explore-ros2/blob/326cf8a/explore/src/explore.cpp#L65-L72) |
| **frontier_exploration_ros2** | WFD 前沿 + MRTSP 排序 + 有界视野 DP；遮挡感知预抢占 | Apache-2.0；Humble + Jazzy；C++ 核心库 + Nav2 | ✅ | 中；C++；Nav2 | 2D 栅格；TurtleBot3 调参 | **未声明 DDS 约束（未实测）的第二选择**；但仿真 benchmark、未在 R2 实测 | [repo](https://github.com/mertgulerx/frontier_exploration_ros2) |
| **roadmap_explorer** | 路标图 + TSP 全局排序；会话保存/恢复；Nav2 端到端 | Humble 实测；Jazzy 未测；**FastDDS 工作不佳，推荐 CycloneDDS** | ✅（仅 Humble） | 中；C++；Jetson Xavier 单核 ~10% | 2D/3D 地图；Nav2 | **效率最优但需换 DDS 栈**；不适合当前 FastDDS 基线直接替换 | [repo](https://github.com/suchetanrs/roadmap-explorer) |
| nav2_wavefront_frontier_exploration（nav2_wfd） | 波前前沿检测 + Nav2 waypoint follower | 小项目；社区使用面小 | ✅ | 轻量 | 2D 栅格 | 可作教学/备选；不作为主线 | [repo](https://github.com/seanreg/nav2_wavefront_frontier_exploration) |
| rrt_exploration | RRT 前沿/多房间 | ROS1 起源为主；ROS2 分支零散 | ⚠️ | 较重 | 2D 激光 | N97 不优先；不纳入选型 | 来源缺失，未核实 |
| dynamic-window-frontier | explore_lite 的局部/全局窗口增强 | 研究代码；未见维护中 ROS2 包 | ⚠️ | 中 | 2D | 暂不纳入 | 来源缺失，未核实 |

**"用得最多"的判断依据（🌐/🧠）**：explore_lite 是 Nav2 教程、TurtleBot 示例、比赛仓库中出现频率最高的 2D 探索器；ROS Index 无二进制反而说明大家普遍源码构建。`frontier_exploration_ros2` 与 `roadmap_explorer` 是 2025-2026 的新一代效率方案，社区规模明显更小，未形成"事实标准"。

### 3.3 3D 方案对比

| 方案 | 方法 | 平台/ROS | 优势 | 对 R2 的适配 | 来源 |
|:---|:---|:---|:---|:---|:---|
| **TARE** | 层级（局部稠密 + 全局稀疏）+ TSP；地面车辆 | ROS1 Melodic/Noetic；OR-Tools；官方无 ROS2 | RSS 2021 双奖；DARPA SubT；3D 复杂环境效率高 | **研究/演示可用，工程集成成本高**；N97 算力不足（🧠） | [repo](https://github.com/caochao39/tare_planner) ｜ [项目页](https://www.cmu-exploration.com/tare-planner) |
| FUEL / GBP / NBVP | 体素/图搜索/下一最佳视点 | 多为 ROS1；无人机/腿足 | 3D 信息增益规划 | 地面 2D 场景不需要；移植成本高 | TARE 论文对比（🌐） |
| ARiADNE | 强化学习探索 | 仓库有 Humble 版本（roadmap 称 2025-08，未独立核实） | 学习型策略 | 训练/部署重；不建议 S1 | [repo](https://github.com/marmotlab/ARiADNE-ROS-Planner) |
| **3D→2D + explore_lite** | 3D 点云投影为 2D 栅格/costmap，复用 2D 探索 | ROS2 Humble | 工程简单、与 Nav2 一致、可复用现有经验 | **新车过渡期最务实**；丢失 3D 结构信息 | [pointcloud_to_grid](https://github.com/jkk-research/pointcloud_to_grid) ｜ [navmap_tools](https://docs.ros.org/en/humble/p/navmap_tools/navmap_tools.map2d_from_pcd.html) |

**关键判断**：3D 探索的收益建立在 **360° 视场** 上。MID-70 的 70.4° 圆视场做前沿探索会反复"看不到身后"，不是算法能补的（🧠，几何约束）。新车探索要么上 MID-360，要么先用 VLP-16 过渡，要么只做"3D 建图 + 2D 探索"的降级方案。

### 3.4 "用得最多" vs "最适合"

| 问题 | 答案 |
|:---|:---|
| 2D 探索用得最多 | **explore_lite**（教程/示例/比赛仓库覆盖最广） |
| 2D 探索最适合老车 S1 | **explore_lite**（轻量、Nav2 直连、配置已在位） |
| 2D 探索效率更高 | frontier_exploration_ros2（无 DDS 约束）；roadmap_explorer（需 CycloneDDS） |
| 3D 探索研究标准 | **TARE**（但 ROS1；ROS2 需移植） |
| 新车最务实 | **MID-360 + 3D 感知 → 2D 探索**，或 TARE ROS2 移植（工作量大） |
| 新车只有 MID-70 时 | **不做 360° 探索**；MID-70 用于前向建图/避障，探索等 MID-360 或 VLP-16 |

---

## 四、离线先验导航方案全景

### 4.1 2D 先验链路（老车）

**建图 → 保存 → 运行：**

```text
LD06 /scan
  → slam_toolbox (online_async, mode: mapping)
  → /map (transient_local) + map→odom
  → map_saver_cli -f <name>   # 生成 .pgm + .yaml
  → [比赛/复用] map_server + AMCL + Nav2
```

**关键配置/约束：**

- `slam_toolbox`：`base_frame: base_link`、`scan_topic: /scan`、`mode: mapping`、`resolution: 0.05`、`transform_publish_period: 0.05`、`map_update_interval: 2.0`。现有 [slam_toolbox_mapping.yaml](../../r2_bringup/config/slam_toolbox_mapping.yaml) 方向正确。
- `map_server`：`/map` 为 **transient_local**；`rviz2` 的 Map display 需手动设 Durability = Transient Local，`ros2 topic hz` 默认 best_effort 会"一直等"（工具限制，非链路断）。
- `AMCL`：四全向轮用 `nav2_amcl::OmniMotionModel`；启动后先 `2D Pose Estimate` 设初始位姿；**运行中不要反复重设**（08-17 教训：多次设 → map 重叠）。
- 地图质量：0.05 m 分辨率、未知区保留、动态障碍不入图；多段建图合并需 IoU 门槛（本仓 [ros2-ops §5.1](../ros2-ops.md) 已有方法）。

**AMCL vs slam_toolbox localization mode：**

| 维度 | AMCL + map_server | slam_toolbox localization |
|:---|:---|:---|
| 地图形式 | `.pgm` + `.yaml` 栅格 | `.posegraph` + `.data` 位姿图 |
| 定位原理 | 粒子滤波 + 激光观测模型 | 扫描匹配 + 位姿图 |
| 优点 | 成熟、Nav2 默认、对地图直观 | 无需栅格化；可增量更新；适合 lifelong |
| 缺点 | 地图更新需重建；粒子数/参数需调 | 依赖较好里程计；参数/地图质量要求高 |
| 适用 | **老车 S1/A 阵营首选** | 地图需长期维护、或想复用建图位姿图时 |
| 注意 | 与 slam_toolbox **不能同时**发布 `map→odom` | 同上 |

**Keepout / 禁区：** Nav2 `costmap_filters` 的 `KeepoutFilter` 可在不修改地图的情况下禁止进入区域（比赛场边界、危险区）。Humble 可用；本项目未实测（🧠/未实测）。

### 4.2 3D 先验链路（新车）

**建图 → 先验 PCD → 定位 → 2D 规划：**

```text
MID-70 / MID-360 / VLP-16
  → FAST-LIO2 (livox_ros_driver2, CustomMsg)
  → 先验点云地图 .pcd（pcd_save_en）
  → 在线：FAST-LIO2 + 先验地图 ICP 定位
  → 输出 odom / map→odom（按实现）
  → 3D 点云 → 2D costmap（height band / pointcloud_to_grid）
  → Nav2 (SE2) 规划控制
```

**3D 定位候选（📘，均未在 R2 实测）：**

| 方案 | ROS2/Humble | 方法 | 备注 | 来源 |
|:---|:---:|:---|:---|:---|
| **FAST_LIO_LOCALIZATION_ROS2** | ✅ Galactic+，Humble 测试 | FAST-LIO + 先验 PCD 的 ICP 定位 + TF/odom 融合 | 与 FAST-LIO2 同源，迁移成本低；依赖 Open3D/PCL | [repo](https://github.com/myeongw002/FAST_LIO_LOCALIZATION_ROS2) |
| **LIO-Localization** | ✅ Humble | ScanLock：先验点云内 ICP 定位 | 工作区式仓库；文档较少 | [repo](https://github.com/wdc3iii/LIO-Localization) |
| NDT（Autoware 系） | ✅（Autoware） | NDT scan matching | 工业界常用、鲁棒；但引入 Autoware 依赖，重 | [Autoware](https://github.com/autowarefoundation/autoware_universe)（未实测） |
| 2D 投影 + AMCL | ✅ | 3D PCD → `.pgm` → map_server + AMCL | 复用老车 2D 经验；丢失 3D 结构 | [navmap_tools](https://docs.ros.org/en/humble/p/navmap_tools/navmap_tools.map2d_from_pcd.html) |

**3D→2D 工具（📘，未实测）：**

- `pointcloud_to_grid`（jkk-research，ROS2 分支）：实时 `PointCloud2` → `OccupancyGrid`（按高度/强度），发布 `height_grid`/`intensity_grid`。
- `pointcloud_to_grid_ros2`（wvu-robotics）：Python 轻量版，README 称 Humble 测试。
- `navmap_tools`：离线 `.pcd` → `.pgm` + `.yaml`，直接给 `map_server`。
- 自研高度带投影：与老车低带源同思路，控制最细，但需自己维护。

**关键约束：**

- FAST-LIO2 对 Livox 设备通常走 `livox_ros_driver2` 的 `CustomMsg`；MID-70 支持，但**需确认驱动/固件与 FAST-LIO2 的 `lid_type` 配置**（未实测）。
- 3D 先验地图的坐标系（`camera_init`/`map`/`odom`）必须与 Nav2 `map` 对齐；外参（尤其 MID-70 倾角）必须进 TF。
- 先验 PCD 体积大，加载与 ICP 对 N97 内存/CPU 有压力；新车算力未定（§5）。

### 4.3 "用得最多" vs "最适合"

| 问题 | 答案 |
|:---|:---|
| 2D 先验用得最多 | **map_server + AMCL**（Nav2 官方默认） |
| 2D 先验最适合老车 | **map_server + AMCL**；需要长期维护地图时再评估 slam_toolbox localization |
| 3D 先验用得最多（开源） | **FAST-LIO2 + ICP 先验定位**（Livox 生态常见组合） |
| 3D 先验工业界 | NDT（Autoware）为主流之一 |
| 新车最务实 | FAST-LIO2 建图 + `FAST_LIO_LOCALIZATION_ROS2`/`LIO-Localization` + 2D costmap + Nav2 |

### 4.4 工程约束清单

1. **`map→odom` 单发布者**：AMCL、slam_toolbox、3D 定位节点三者只能选一。
2. **`/map` QoS**：transient_local；录包用 `--qos-profile-overrides-path`，rviz 手动设 Durability。
3. **初始位姿纪律**：启动初期可重设 1~2 次；运行中不要反复设；设完先动一下确认收敛。
4. **地图时效**：场地变更后先更新地图，不要靠 costmap 硬扛；否则 AMCL 定位漂移会被误判为"导航算法问题"。
5. **`use_sim_time`**：实车一律 `false`；bag 回放另说。
6. **算力**：3D 先验定位 + Nav2 + 感知在 N97 上很可能超预算；新车需单独选算力平台。

---

## 五、硬件可行性

### 5.1 老车（LD06 2D 线）

**LD06 实测规格（✅ N97，2026-11-07）：**

| 项 | 实测值 | 说明 |
|:---|:---|:---|
| 帧率 | 10 Hz | `scan_time` 99.97~100.02 ms |
| beam 数/圈 | 452~455 | 逐帧变化 |
| 角分辨率 | 0.793~0.798° | 驱动按 `360/(beam_size−1)` 反推 |
| 点率 | ~4.5k 点/s | 452~455 × 10 Hz |
| NaN | 80~85/圈（~18%） | 无回波 bin |
| range_min/max（消息） | 0.02 / 25.0 m | **25 是驱动常量，不是规格** |
| 室内有效回波 | 5.94~6.08 m | 室内限制；空旷场地待测 |

**多雷达同步（📘/🌐）：**

- LD06/LD19 只有 UART（TX 输出）+ PWM（电机调速）+ 5V/GND；**没有 PPS/触发/同步引脚**。
- 多台雷达各自自由旋转，无法相位锁定；只能"各自时间戳 + TF 融合"。
- 结论：**双 LD06 不存在硬件同步**；合并 scan 时要接受时间差与运动畸变。

**双雷达拓扑（S2）：**

| 方案 | 做法 | 优点 | 缺点 | 判断 |
|:---|:---|:---|:---|:---|
| A：独立话题 | `/scan` + `/scan_low`，各自 frame（`laser_a`/`laser_b` 或 `base_laser`/`laser_low`），costmap 分层订阅 | 保留高度语义；各层独立 clear/mark；排障清晰 | 需两套 costmap 源配置 | **优先**（与 two-car §6.1 契约一致） |
| B：合并单帧 | `ira_laser_tools` 的 `laserscan_multi_merger`（社区 Humble 分支） | 下游只订一个 `/scan`；老 2D 算法兼容 | 时间不同步、高度混叠；QoS/`destination_frame` 坑；无官方二进制 | 备选；未实测 |

> `ira_laser_tools` 官方仓库只有 ROS1；Humble 支持在社区 fork（[nakai-omer humble 分支](https://github.com/nakai-omer/ira_laser_tools/tree/humble)），无官方包，需源码构建（📘/🌐）。

**N97 算力（📘 Intel ARK；本地 [n97info.md](../n97/n97info.md) 只记录型号/风扇）：** Intel N97，4C/4T，12W TDP，6MB cache，最高 3.6 GHz。2D SLAM + Nav2 + explore_lite 可行；不要再叠 3D LIO/3D 探索。

### 5.2 新车（3D 线）

| 传感器 | 关键规格 | 对探索的意义 | 对先验导航的意义 | 来源 |
|:---|:---|:---|:---|:---|
| **MID-70** | 70.4° 圆视场；100k 点/s；90 m@10%；905 nm；8 W；100 Mbps Ethernet；无内置 IMU | **非 360°，前沿探索会反复丢身后**；适合前向稠密建图/避障 | 可建前向 PCD；需外部 IMU（G354/其他） | [Livox MID-70](https://www.livoxtech.com/mid-70) |
| **MID-360** | 360°×59°（-7°~52°）；200k 点/s；40 m@10%；内置 IMU 200 Hz；265 g | **探索正解**：360° 覆盖 + 内置 IMU | 建图/定位均合适 | [Livox MID-360](https://www.livoxtech.com/mid-360) |
| **D435** | 深度 FOV 87°×58°；理想 0.3~3 m；2 m 处 <2%；USB-C | 视觉导航/检测；**不解决低物/360° 覆盖** | 可做视觉里程计/检测，不作主定位 | [RealSense D435](https://www.realsenseai.com/products/stereo-depth-camera-d435/) |
| **VLP-16** | 360°×30°；16 线；100 m；~300k 点/s；8 W；Ethernet；830 g | **比 MID-70 更适合 360° 探索**；但重、旧 | 已用于 FAST-LIO2 实车验证（08-24） | [Velodyne datasheet](http://velodynelidar.com/docs/datasheet/63-9286_Rev-F_Puck%20LITE_Spec%20Sheet_Web.pdf) |
| **Jetson Nano B01** | JetPack 4 / Ubuntu 18.04；无原生 Humble | 可做 YOLO 推理协处理器 | **不建议做主算力**（EOL、ROS2 版本旧） | [01-plan.md](../01-plan.md)（本地规划）；[JetPack](https://developer.nvidia.com/embedded/jetpack) |

**新车算力判断（🧠）**：3D LIO（FAST-LIO2）+ Nav2 + 3D 探索（TARE 类）在 N97 的 4C/4T 上大概率不足；新车应单独选 8 核以上 x86 或 Orin NX/AGX 级平台。**未实测，仅作预算提示**。

### 5.3 硬件-方案匹配矩阵

| 平台/阶段 | 感知 | 探索 | 先验导航 | 算力判断 | 结论 |
|:---|:---|:---|:---|:---|:---|
| **老车 S1** | LD06 ×1 | slam_toolbox + explore_lite | 建图后 map_server + AMCL | N97 足够 | ✅ 链路成立；缺 G4 参数 + 安装几何 + 首跑 |
| **老车 S2** | LD06 ×2（低装） | explore_lite（分层 costmap） | 2D 地图 + AMCL | N97 足够 | ⚠️ 几何/标定/双源配置是关键；不建议合并单帧 |
| **新车 phase 1** | MID-70（+D435） | 不做 360° 探索；可做前向建图/避障 | FAST-LIO2 + 先验 PCD 定位 | 待定（N97 偏紧） | ⚠️ MID-70 FOV 是硬约束；探索等 MID-360 |
| **新车 phase 2** | MID-360（+D435） | TARE ROS2 移植，或 3D→2D + explore_lite | FAST-LIO2 + 先验 PCD 定位 | 需新算力平台 | ✅ 传感器匹配；软件集成是主要工作量 |
| **VLP-16 备用** | VLP-16 | 可作新车探索过渡（360°×30°） | FAST-LIO2 已验证 | N97 可跑 LIO，但重 | ⚠️ 去向待定（O7） |

### 5.4 关键硬件约束

- **2D 低物几何**：低装 LD06 的高度/俯仰决定盲区；用 [ros2-ops §12.1](../ros2-ops.md) 的 `d = Δh / tan|θ|` 先算再装，装完实测对账（偏差 <1 cm）。
- **多雷达时间同步**：LD06 无硬件同步；Livox 设备是否支持 PTP/时间同步需按型号确认（未核实，勿假设）。
- **外参**：MID-70 前倾 15~20° 必须进 TF/标定（09-16 survey 已定装法，待实车结构核算）；D435 与雷达的相对位姿同样要标。
- **供电/网络**：MID-70/MID-360 是以太网 + 独立供电；N97 网口/交换机端口/供电余量需核算（two-car §10 待定）。
- **DDS**：跨机 FastDDS 配置已存在；若采用 roadmap_explorer 需切 CycloneDDS，影响全栈，不是局部替换。

---

## 六、选项与影响（交用户定夺）

> 以下只列选项与影响，**不替用户选**；推荐标记仅在明确征求时给出（全局"决策边界"）。

| 编号 | 选项 | 内容 | 影响/代价 | 前置 |
|:---|:---|:---|:---|:---|
| **O1** | 老车 S1 先跑通 explore_lite | 修 G4 参数 → 量安装几何 → 起 slam_toolbox + nav2_explore + explore | 打通 2D 探索最小闭环；后续 S2/新车都复用 | G4、G10/G13、G7/G8 |
| **O2** | 老车 S2 双 LD06 拓扑 | A 独立 `/scan`+`/scan_low`；B 合并单帧 | A 语义清晰、配置多；B 下游简单、时间不同步 | 双雷达安装/标定 |
| **O3** | 新车探索传感器 | ① MID-360 首期；② MID-70 + 2D 补盲；③ VLP-16 过渡 | ① 最匹配、需采购；② FOV 仍不足；③ 零采购、重量/旧平台 | 预算、结构、算力 |
| **O4** | 新车先验定位 | ① FAST_LIO_LOCALIZATION_ROS2；② LIO-Localization；③ NDT/Autoware；④ 3D→2D + AMCL | ① 同源迁移低；② 轻但文档少；③ 工业鲁棒但重；④ 复用 2D 经验、丢 3D | 先验 PCD、外参、算力 |
| **O5** | 新车 3D 探索 | ① TARE ROS2 移植；② 3D→2D + explore_lite；③ 自研 frontier | ① 效果最好、工作量最大；② 务实、能力降级；③ 可控、周期长 | 算力、MID-360、SLAM |
| **O6** | Jetson Nano 去留 | ① 保留做 YOLO 协处理器；② 退役换 Orin | ① 零成本、ROS2 Foxy 旧；② 新算力、成本 | 视觉任务时间表 |
| **O7** | VLP-16 去向 | ① 新车探索过渡；② 其他项目/备用；③ 出售 | ① 零采购、360° 可用；② 闲置；③ 回血 | 用户定夺（two-car §10） |
| **O8** | 文档修正批次 | ① 只改 P1；② P1+P2+P3+P4 一起；③ 先只记录不改 | ① 最小；② 一次闭环；③ 保留现状、风险留存 | 用户授权（只增不删） |

---

## 七、未实测项与待核实

| 项 | 状态 | 说明 |
|:---|:---:|:---|
| explore_lite 8 参数声明 | ✅ 已复测确认 | 2026-11-07 20:10 N97 同进程 A/B：补 costmap+TF+action server 后 8 项全部出现（`param get` 可取）；原冒烟系构造期阻塞假阴性，见 §2.3 末 |
| explore_lite 在 S1 全链路联跑 | ❌ 未跑 | slam_toolbox + Nav2 + explore 三件套从未一起启动 |
| 双 LD06 合并/分层实际效果 | ❌ 未测 | 无硬件同步；合并方案未实测 |
| LD06 空旷场地量程/地面杂波 | ❌ 未测 | 室内仅 6.08 m；`max_laser_range` 待调 |
| MID-70 + FAST-LIO2 在 R2 的精度/算力 | ❌ 未测 | 新车平台未定 |
| MID-360 实机 | ❌ 未购/未测 | 探索正解，但需采购与结构 |
| FAST-LIO 先验定位（ICP）在 R2 | ❌ 未测 | 候选仓库均未在本项目验证 |
| 3D→2D 投影工具 | ❌ 未测 | pointcloud_to_grid/navmap_tools 未在 R2 跑 |
| roadmap_explorer FastDDS 失效形态 | ❌ 未复现 | README 只说"works not well"，未给具体报错 |
| frontier_exploration_ros2 在 R2 | ❌ 未测 | 作者仿真 benchmark，未独立复现 |
| Jetson Nano 跑 Humble/Docker | ❌ 未测 | 仅作协处理器规划；不建议主算力 |
| N97 3D LIO + Nav2 + 探索并行 | ❌ 未测 | 算力判断为推理 |
| KeepoutFilter / costmap filters | ❌ 未测 | Humble 可用，未在本项目配置 |

---

## 八、来源（2026-11-07 核实方式）

### 8.1 本地文档/实测（✅）

- [explore-plan.md](../minimal-loop2/explore-plan.md) — 2D 探索执行稿（含待修正的 §3.1.2）
- [s1-readiness-gap.md](../old-car/s1-readiness-gap.md) — S1 23 项缺口
- [ld06-dual-lidar.md](../old-car/ld06-dual-lidar.md) — LD06 规格/crop/双实例实测
- [two-car-architecture.md](../two-car-architecture.md) — 两车接口/TF/待定
- [planning-control-roadmap.md](../roadmaps/planning-control-roadmap.md) — §2.1/§5.5
- [07-handover.md](../07-handover.md) — 平台分叉与老车口径
- [ros2-ops.md](../ros2-ops.md) — §12 感知覆盖判据、§5.1 点云分析
- [3d-lidar-2d-navigation-survey.md](3d-lidar-2d-navigation-survey.md) — 低物感知数值权威
- [raw_explore_smoke_n97_2026-11-07_1253.txt](../raw_data/raw_explore_smoke_n97_2026-11-07_1253.txt) — 冒烟原始输出
- [explore_params.yaml](../../r2_bringup/config/explore_params.yaml) / [nav2_params_low.yaml](../../r2_bringup/config/nav2_params_low.yaml) / [slam_toolbox_mapping.yaml](../../r2_bringup/config/slam_toolbox_mapping.yaml) — 现役配置

### 8.2 官方仓库/源码（📘）

- [m-explore-ros2（explore_lite）](https://github.com/robo-friends/m-explore-ros2) — 最新 commit 2026-06-01；无二进制
- [explore.cpp @326cf8a](https://github.com/robo-friends/m-explore-ros2/blob/326cf8a/explore/src/explore.cpp#L65-L72) — 8 参数 `declare_parameter`
- [frontier_exploration_ros2](https://github.com/mertgulerx/frontier_exploration_ros2) — Apache-2.0；Humble+Jazzy；仿真 benchmark
- [roadmap-explorer](https://github.com/suchetanrs/roadmap-explorer) — Humble only；FastDDS 工作不佳；CycloneDDS 推荐；Xavier 10%
- [TARE planner](https://github.com/caochao39/tare_planner) — ROS1 Melodic/Noetic
- [slam_toolbox](https://github.com/SteveMacenski/slam_toolbox)
- [Nav2 文档](https://docs.nav2.org/) ｜ [AMCL](https://docs.nav2.org/configuration/packages/configuring-amcl.html) ｜ [Map Server](https://docs.nav2.org/configuration/packages/configuring-map-server.html)
- [FAST_LIO](https://github.com/hku-mars/FAST_LIO) ｜ [livox_ros_driver2](https://github.com/Livox-SDK/livox_ros_driver2)
- [FAST_LIO_LOCALIZATION_ROS2](https://github.com/myeongw002/FAST_LIO_LOCALIZATION_ROS2) — Humble 测试
- [LIO-Localization](https://github.com/wdc3iii/LIO-Localization) — Humble；ScanLock ICP
- [pointcloud_to_grid](https://github.com/jkk-research/pointcloud_to_grid) ｜ [pointcloud_to_grid_ros2](https://github.com/wvu-robotics/pointcloud_to_grid_ros2)
- [navmap_tools map2d_from_pcd（Humble）](https://docs.ros.org/en/humble/p/navmap_tools/navmap_tools.map2d_from_pcd.html)
- [ldlidar_stl_ros2（LD06 驱动）](https://github.com/ldrobotSensorTeam/ldlidar_stl_ros2)
- [ira_laser_tools Humble 社区分支](https://github.com/nakai-omer/ira_laser_tools/tree/humble) — 无官方二进制

### 8.3 官方产品/规格（📘）

- [Livox MID-70](https://www.livoxtech.com/mid-70) — 70.4° 圆视场；100k pts/s；90 m@10%；8 W；无 IMU
- [Livox MID-360](https://www.livoxtech.com/mid-360) — 360°×59°；200k pts/s；40 m@10%；内置 IMU 200 Hz
- [Intel RealSense D435](https://www.realsenseai.com/products/stereo-depth-camera-d435/) — 87°×58°；0.3~3 m；2 m <2%
- [Velodyne VLP-16 datasheet](http://velodynelidar.com/docs/datasheet/63-9286_Rev-F_Puck%20LITE_Spec%20Sheet_Web.pdf) — 360°×30°；16 线；100 m；~300k pts/s
- [LD19 datasheet](https://botland.com.pl/img/art/inne/21991_Karta%20katalogowa.pdf) — UART TX + PWM，无同步引脚
- [Intel Processor N97（ARK，SKU 233090）](https://www.intel.com/content/www/us/en/products/sku/233090/intel-processor-n97-6m-cache-up-to-3-60-ghz/specifications.html) — 4C/4T，12W TDP，最高 3.6 GHz
- [NVIDIA JetPack](https://developer.nvidia.com/embedded/jetpack) — JetPack 4 / Ubuntu 18.04 世代
- [ROS REP 2000](https://ros.org/reps/rep-2000.html) — Humble EOL 2027-05

### 8.4 论文/社区（🌐）

- [TARE 项目页（CMU）](https://www.cmu-exploration.com/tare-planner) — RSS 2021 Best Paper + Best System Paper
- [ARiADNE-ROS-Planner](https://github.com/marmotlab/ARiADNE-ROS-Planner) — RL 探索（Humble 支持状态未独立核实）
- [frontier_exploration_ros2 发布帖](https://discourse.openrobotics.org/t/frontier-exploration-ros2-modern-autonomous-exploration-system-for-ros-2/57222/1) — 作者介绍/benchmark
- [LD06 多雷达融合社区讨论（CSDN 等）](https://wenku.csdn.net/column/1op7x9rcyp) — 软件融合/独立话题的常见做法（二手来源，仅作旁证）

---

## 附录 A：P1 证据摘录

**本地（错误结论）：**

```text
explore-plan.md:334  | ✅ `return_to_init` 不存在 | 不在 `param list` 中 | ...
explore-plan.md:335  | ⚠️ 另 7 项未声明 | ... 代码用 `get_parameter_or` 读取、未 declare ...
explore_params.yaml:24 | ✅ `return_to_init` 不在声明列表中 → 确认不存在，已注释，勿写入
```

**上游（正确事实，326cf8a）：**

```cpp
// explore/src/explore.cpp L65-L72
this->declare_parameter<float>("planner_frequency", 1.0);
this->declare_parameter<float>("progress_timeout", 30.0);
this->declare_parameter<bool>("visualize", false);
this->declare_parameter<float>("potential_scale", 1e-3);
this->declare_parameter<float>("orientation_scale", 0.0);
this->declare_parameter<float>("gain_scale", 1.0);
this->declare_parameter<float>("min_frontier_size", 0.5);
this->declare_parameter<bool>("return_to_init", false);
```

**判定**：本地文档结论错误；冒烟输出异常需按 §2.3 复测。**在复测完成前，不改运行配置**（`return_to_init` 保持注释不影响首跑）。

---

## 附录 B：与既有 survey 的分工

- 本文：**探索/先验两条线的方案与路线核验**（问题导向）。
- [3d-lidar-2d-navigation-survey.md](3d-lidar-2d-navigation-survey.md)：低矮障碍感知的**数值与几何**（1.59 m 盲区等），本文引用不复制。
- [sensor-mounting-layout-survey.md](sensor-mounting-layout-survey.md)：MID-70/D435 的**安装位置与倾角评价**，本文不重复。
- [navigation-behavior-safety-survey.md](navigation-behavior-safety-survey.md)：导航行为病/安全设计，本文只引用其结论方向。
