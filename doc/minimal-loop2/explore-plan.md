# Explore 式导航升级 · 实施梳理（工作稿）

> 日期: 2026-11-05
> 状态: **方案拟稿（未实测）**——参数/命令待 N97 实机首跑校正；本文件随进展直接改，不追求一次定稿
> 定位: Phase 3.5 / minimal-loop2 B2「explore_lite 探索」分支的实施梳理——把当前「离线先验地图 + AMCL」升级为「实时建图 + 前沿探索 + Nav2」的轻量 B 阵营方案
> 关联: [规划控制路线 §2.1/§2.2/§5.5](../roadmaps/planning-control-roadmap.md)（A/B 阵营与选型结论）｜[minimal-loop2/plan.md](plan.md)（B2 判据）｜[execution.md](execution.md)（验收口径）｜[07-handover.md](../07-handover.md)（当前主线，explore 不抢 A1/A2）
> 原则: **不改现有 `nav2.launch.py` / `nav2_params_low.yaml`**——新增 explore 专用 launch/config，两种模式并存、可回退；首跑按「一次只加一个变量」分终端推进
>
> **2026-11-06 平台适配注记**：老车已撤 VLP-16，改 LD06 串口 2D 雷达；本文的 VLP-16/`velodyne_low` 前提按
> §十 替换，**2D 探索骨架（slam_toolbox + Nav2 + explore_lite）不变**。两车架构见 [two-car-architecture.md](../two-car-architecture.md)。
>
> **2026-11-07 进展**：Step 3.1 构建通过 + [冒烟实测](#312-冒烟实测2026-11-07-n97无-nav2-环境)（节点名 / 参数读取 / `return_to_init` 三项已钉死），
> 官方 launch 的两处陷阱实锤——见 [§3.1.1](#311-实测记录2026-11-07-n97) 与 [§3.3](#33-启动终端-d)。
> Step 1（`slam_toolbox_mapping.yaml`）、Step 2（`nav2_explore.launch.py`）、Step 3.2（`explore_params.yaml`）
> 的配置文件与 launch **已全部落文件，但均未实测**——slam_toolbox / Nav2 / explore 三者从未联合起过。
>
> **2026-11-07 晚订正**：§3.1.2 关于 `return_to_init`「不存在」与 7 参数「未声明」的结论**已被推翻**
> ——干净复测证明二者都存在且可取，原观测是构造期阻塞导致的假阴性（见 §3.1.3）。

---

## 一、现状与目标

### 1.1 现状（A 阵营：离线地图 + AMCL）

| 环节 | 现役实现 | 关键点 |
|:---|:---|:---|
| 地图 | `map_0815_clean.yaml` 离线文件 | `map_server` 加载，`/map` 为 transient_local |
| 定位 | AMCL（`nav2_amcl`，OmniMotionModel） | 发布 `map→odom`；RViz 先 2D Pose Estimate |
| 里程计 | EKF `/odometry/filtered` | 发布 `odom→base_link`；Nav2 侧 `/odom` remap 到它 |
| 感知 | VLP-16 → `/scan` + `/velodyne_points` | 导航模式不跑 KISS；`/scan` 来自 `velodyne_laserscan` |
| 规划控制 | Nav2（NavFn + MPPI + velocity_smoother） | 降额参数 `nav2_params_low.yaml` |
| 启动 | `nav2.launch.py` | map_server + AMCL + 导航节点 + 两个 lifecycle manager |

> 现状细节以 [nav2.launch.py](../../r2_bringup/launch/nav2.launch.py)、[nav2_params_low.yaml](../../r2_bringup/config/nav2_params_low.yaml)、[startup.md](../startup.md) 为准，本文不复制参数表。

### 1.2 目标（B 阵营轻量版：实时建图 + 前沿探索）

| 环节 | Explore 模式 | 与现状的差异 |
|:---|:---|:---|
| 地图 | `slam_toolbox`（`online_async`）实时 `/map` | 去掉 `map_server` 与地图文件 |
| 定位 | `slam_toolbox` 发布 `map→odom` | 去掉 AMCL；不再需要 2D Pose Estimate |
| 探索 | `explore_lite` 前沿检测 → `NavigateToPose` | 新增；Nav2 只负责“怎么去” |
| 规划控制 | 复用现有 Nav2 栈 | 不改 `nav2_params_low.yaml` |
| 启动 | `slam_toolbox` + `nav2_explore.launch.py` + `explore_lite` | 新增 explore 专用 launch；首跑分终端 |

**一句话链路**：`/scan` → `slam_toolbox` → `map→odom` + `/map` → Nav2 代价地图 → `explore_lite` 选前沿 → `NavigateToPose` → Nav2 规划控制 → `/cmd_vel`。

### 1.3 边界与旧结论对齐（重要，防误读）

- **本方案是 2D 探索层，不是 3D 主 SLAM**。[vlp16_slam_exploration.md](../retrospect/vlp16_slam_exploration.md) 的结论「slam_toolbox 不适合 VLP-16」指的是**把 slam_toolbox 当 3D 主 SLAM**：它只吃单环 2D `LaserScan`，浪费 VLP-16 其余 15 环。这里刻意只用它的 **2D 导航/探索层**：`/scan` 本来就是 `velodyne_laserscan` 抽的单环扫描，够 Nav2 做 2D 代价地图与前沿检测；3D 主线仍是 KISS-ICP / FAST-LIO2（A2），两者不冲突。
- **N97 算力边界**：explore 模式只跑 `slam_toolbox` 2D + Nav2，不叠 KISS/FAST-LIO2；3D 实时探索（FAST-LIO2 地图 + 3D 前沿）只作演示，不进本方案。
- **低物盲区不因 explore 消失**：VLP-16 对 0.35m 箱的几何盲区 1.59m（[survey §三B](../surveys/3d-lidar-2d-navigation-survey.md)）仍在。explore 首测场地先避开低物；低物绕行仍靠 `nav2_params_low.yaml` 的 low 带源与人工急停兜底。
- **不改变当前主线**：A1 避障收口 / A2 FAST-LIO2 仍是主线；本文件是 B2 余力项的实施梳理，何时启动由用户定（见 §七）。

---

## 二、目标架构

### 2.1 数据流

```text
[VLP-16] → velodyne_driver → /velodyne_points ─┬→ velodyne_transform → /velodyne_points
                                                └→ velodyne_laserscan → /scan
[G354]  → /imu/data ─┐
[底盘]  → /odom_wheels ┴→ EKF → /odometry/filtered + TF odom→base_link

/scan + TF ─→ slam_toolbox（online_async）
                ├→ TF map→odom
                └→ /map（OccupancyGrid, transient_local）
                        └→ Nav2 global_costmap static_layer

/scan + /velodyne_points ─→ Nav2 local/global obstacle layers
/global_costmap/costmap ─→ explore_lite（前沿检测）
                             └→ NavigateToPose → bt_navigator
Nav2 planner/controller → /cmd_vel → 底盘
```

### 2.2 TF 归属（唯一发布者）

| TF | 发布者 | 说明 |
|:---|:---|:---|
| `map→odom` | `slam_toolbox` | **AMCL 必须不启动**；两者同发会跳变 |
| `odom→base_link` | EKF（`ekf.launch.py`） | 不变 |
| `base_link→velodyne` | `robot_state_publisher`（`r2_sensors/velodyne.launch.py`） | 不变 |
| `base_link→imu_link` | G354 驱动/URDF | 不变 |

> 启动 explore 前先 `ros2 node list | grep -E "amcl|map_server"`，有残留先停——这是最常见的“地图/位姿乱跳”根因。

### 2.3 两种模式对照

| 功能 | 离线模式（现役） | Explore 模式（本方案） |
|:---|:---|:---|
| 地图来源 | 文件（`map_0815_clean.yaml`） | `slam_toolbox` 实时 `/map` |
| `map→odom` | AMCL | `slam_toolbox` |
| 初始位姿 | RViz 2D Pose Estimate | 不需要（slam_toolbox 从原点起图） |
| 探索 | 无 | `explore_lite` |
| 启动文件 | `nav2.launch.py` | `nav2_explore.launch.py` + 外部 `slam_toolbox` / `explore_lite` |
| 地图保存 | 已有文件 | 探索结束后 `map_saver_cli` 保存，可回灌离线模式 |

---

## 三、落地步骤

### Step 0 前置检查（首跑前一次）

**机器**：实车 = N97（192.168.1.210）；VM 只做配置检查/离线试跑，**不要用 VM 的 install 状态解释 N97 行为**（[ros2-ops.md §1](../ros2-ops.md)）。

```bash
# 0.1 机器与网络确认
hostname
ip -4 addr show | grep -E "192.168.1.210|10.18.18.20"

# 0.2 包检查
ros2 pkg list | grep -E "slam_toolbox|nav2_map_server|explore_lite"
# - slam_toolbox 缺失：sudo apt install ros-humble-slam-toolbox
# - explore_lite 无 apt 二进制，走 Step 3 源码构建

# 0.3 传感器/EKF 已起时的最小前置
ros2 topic hz /scan
ros2 topic hz /odometry/filtered
ros2 run tf2_ros tf2_echo odom base_link
ros2 run tf2_ros tf2_echo base_link velodyne

# 0.4 确认没有 AMCL/map_server 残留
ros2 node list | grep -E "amcl|map_server" || echo "OK: no AMCL/map_server"
```

**检查清单**：

- [ ] N97 CPU governor = `performance`（每次开机；否则 slam/Nav2 都可能掉帧，[ros2-ops.md §3](../ros2-ops.md)）
- [ ] 雷达 `/scan` 持续有数据；`/odometry/filtered` 正常；TF 链 `odom→base_link→velodyne` 完整
- [ ] 无 AMCL/map_server 在跑
- [ ] `r2.code-workspace` 等用户 WIP 不动；提交前 `git status` 确认
- [ ] 首测场地 ≥5×5m、无低矮障碍、有急停/监护人员

> 大消息话题（`/velodyne_points`）不要用 `ros2 topic hz` 判链路，按 [ros2-qos-dds.md](../ros2-qos-dds.md) 用 `echo header.stamp` 或 bag metadata。

---

### Step 1 实时建图：slam_toolbox

#### 1.1 新增配置 `r2_bringup/config/slam_toolbox_mapping.yaml`

以官方 `mapper_params_online_async.yaml` 为母本**整份复制**，只改下表几项（其余保持官方默认，减少变量）：

```yaml
slam_toolbox:
  ros__parameters:
    odom_frame: odom
    map_frame: map
    base_frame: base_link          # 官方默认 base_footprint；R2 已删 base_footprint，必须改
    scan_topic: /scan
    mode: mapping
    use_sim_time: false
    resolution: 0.05
    max_laser_range: 20.0
    map_update_interval: 2.0       # 官方 5.0 偏慢，探索时前沿更新滞后
    transform_publish_period: 0.05 # 官方 0.02（50Hz）没必要，20Hz 足够
    minimum_time_interval: 0.5     # 2Hz 处理 scan，省 N97 CPU
    minimum_travel_distance: 0.5
    minimum_travel_heading: 0.5
    enable_interactive_mode: false # 关掉 RViz 交互标记，防误拖地图
    use_scan_matching: true
    do_loop_closing: true
```

**改动理由**：

| 参数 | 值 | 理由 |
|:---|:---|:---|
| `base_frame` | `base_link` | R2 的 TF 树没有 `base_footprint`；保持官方默认会报 “base_footprint does not exist” 或直接不发布 `map→odom` |
| `use_sim_time` | `false` | 官方 launch 默认 `true`，实车必须关；否则 TF 时间戳对不上 |
| `map_update_interval` | `2.0` | 默认 5s 地图刷新太慢，explore_lite 的前沿会滞后 |
| `transform_publish_period` | `0.05` | `map→odom` 20Hz 足够；50Hz 白耗 CPU |
| `minimum_time_interval` | `0.5` | `/scan` 约 10Hz，2Hz 建图足够，N97 省算力 |
| `enable_interactive_mode` | `false` | 避免 RViz 里误拖地图/位姿 |

> 新增配置后必须 `colcon build --packages-select r2_bringup`（launch 加载 install 副本，[ros2-ops.md §2](../ros2-ops.md)）。

#### 1.2 启动（终端 B）

```bash
source /opt/ros/humble/setup.bash
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch slam_toolbox online_async_launch.py \
  slam_params_file:=$HOME/Lin_workspace/r2_integration/install/r2_bringup/share/r2_bringup/config/slam_toolbox_mapping.yaml \
  use_sim_time:=false
```

> 不要用官方 launch 的默认参数文件（`base_footprint` + `use_sim_time:=true`）。

#### 1.3 验证

```bash
ros2 node list | grep slam_toolbox
ros2 topic info /map -v            # 看发布端 QoS 是否 transient_local、订阅端数量
ros2 run tf2_ros tf2_echo map odom # 应持续有变换
ros2 topic echo /map --qos-durability transient_local --field info
```

RViz（先只开 Map + LaserScan + TF）：

- Map display 的 **Durability 设为 Transient Local**，否则看不到 `/map`（[ros2-qos-dds.md §二](../ros2-qos-dds.md)）。
- 键盘遥控缓慢走一小段，地图应随车扩展；墙段连续、无明显重影。
- 若 `tf2_echo map odom` 报 “Invalid frame ID map”：slam_toolbox 还没初始化——先确认 `/scan` 有数据、`odom→base_link` 存在。

#### 1.4 保存地图（可选，探索结束后做）

```bash
ros2 run nav2_map_server map_saver_cli -f $HOME/maps/explore_map_$(date +%m%d_%H%M)
```

> 保存的是 2D 占据栅格，可直接回灌离线模式（`nav2.launch.py map:=...`）。探索中途保存会得到不完整地图，等无前沿后再存。

---

### Step 2 Nav2 接实时地图：去 AMCL / map_server

#### 2.1 新增 `r2_bringup/launch/nav2_explore.launch.py`

以现有 [nav2.launch.py](../../r2_bringup/launch/nav2.launch.py) 为母本复制，做三处删改：

| 改动 | 内容 |
|:---|:---|
| 删除 | `map` 参数、`RewrittenYaml` 的 `yaml_filename` 注入、`map_server`、`amcl`、`lifecycle_manager_localization` |
| 保留 | `planner_server`、`controller_server`、`smoother_server`、`behavior_server`、`bt_navigator`、`velocity_smoother`、`lifecycle_manager_navigation` |
| 默认参数 | ~~`params_file` 默认改为 `nav2_params_low.yaml`（**安全默认**；现有 `nav2.launch.py` 默认是全速版，explore 不沿用这个默认）~~ → **2026-11-07 G4 定夺后改为 `nav2_params_ld06.yaml`**（low 版含 `velodyne_low` 低带源，老车无 `/velodyne_points`；LD06 版 = low 版只删低带源，膨胀与降额速度不动） |

保留原有 remap：

```python
remappings = [('/odom', '/odometry/filtered'),
              ('/tf', 'tf'),
              ('/tf_static', 'tf_static')]
```

> 不启动 `map_server`/`amcl`，所以参数文件里这两段参数不会被使用，**不需要删配置**；
> ~~两种模式共用同一份参数文件~~ → **2026-11-07 订正**：老车导航模式与 explore 模式**共用 `nav2_params_ld06.yaml`**
> （G4 定夺：按硬件外设命名），`nav2_params_low.yaml` 保留作 VLP-16 历史基线/新车参考，不再作老车默认。

#### 2.2 启动（终端 C）

```bash
source /opt/ros/humble/setup.bash
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch r2_bringup nav2_explore.launch.py \
  params_file:=$HOME/Lin_workspace/r2_integration/install/r2_bringup/share/r2_bringup/config/nav2_params_ld06.yaml \
  rviz:=true
# 注：默认值已是 nav2_params_ld06.yaml（11-07），此参数可省略；
#     原示例用 nav2_params_low.yaml，老车无 /velodyne_points，会持续报低带源缺失。
```

#### 2.3 验证

```bash
ros2 lifecycle get /planner_server       # 应为 active
ros2 lifecycle get /controller_server    # 应为 active
ros2 topic echo /global_costmap/costmap --qos-durability transient_local --field info
ros2 topic echo /global_costmap/costmap_updates --field info
```

RViz 检查：

- **不要再点 2D Pose Estimate**；slam_toolbox 已提供 `map→odom`。
- 手动发一个 Nav2 Goal 到已建图的自由区，车应能规划/到达；到达后取消，确认 `/cmd_vel` 正常。
- 全局代价地图应随 `/map` 增长；若一直空白，按 §五 的风险表逐项查。

> 现有配置已具备探索所需的三项：`global_costmap.track_unknown_space: true`、`planner_server.allow_unknown: true`、`static_layer.map_subscribe_transient_local: True`（[nav2_params_low.yaml](../../r2_bringup/config/nav2_params_low.yaml)）。这是前沿目标能进未知区的关键，不要改。

---

### Step 3 前沿探索：explore_lite

#### 3.1 源码构建（官方无 apt 二进制）

在 **N97** 上建独立工作区（不塞进 `r2_integration`，避免嵌套仓/构建污染）：

```bash
mkdir -p ~/Lin_workspace/explore_ws/src
cd ~/Lin_workspace/explore_ws/src
git clone https://github.com/robo-friends/m-explore-ros2.git

cd ~/Lin_workspace/explore_ws
source /opt/ros/humble/setup.bash
colcon build --packages-up-to explore_lite
source install/setup.bash
ros2 pkg executables explore_lite     # 应看到 explore_lite explore
```

注意：

- 实际包名 `explore_lite`，**可执行文件是 `explore`**（不是 `explore_lite`）；节点默认名 `explore_node`。
- `explore_lite_msgs` 会被依赖一起构建；`--packages-up-to explore_lite` 足够。
- N97 若遇 pip 安装的 cmake 抢占 PATH，用 `PATH=/usr/bin:$PATH colcon build ...`（[ros2-ops.md §2](../ros2-ops.md)）。
- VM 可另建一份做配置检查；实车运行必须在 N97 本机构建。

##### 3.1.1 实测记录（2026-11-07 N97）

上述命令在 N97 一次跑通，实测数据：

| 项 | 实测 |
|:---|:---|
| 落位 | `~/Lin_workspace/explore_ws/src/m-explore-ros2`（独立工作区，未嵌套 r2_integration） |
| 版本 | `326cf8a (HEAD -> main, origin/main, origin/HEAD)` —— 与本文引用一致，clone 后无需 checkout |
| 构建 | `explore_lite_msgs` 4.99s + `explore_lite` 18.3s，`Summary: 2 packages finished [23.7s]` |
| stderr | **只有警告，无 error**：`cmake_minimum_required` 版本弃用 + `Policy CMP0148`（Humble `rosidl_generator_py` 在较新 CMake 下的策略提示）——上游代码卫生问题，不影响产物 |
| 验证 | `ros2 pkg executables explore_lite` → `explore_lite explore`；`install/explore_lite/lib/explore_lite/explore` 在位 |
| 参数文件 | 已随包安装：`install/explore_lite/share/explore_lite/config/params_costmap.yaml` 与 `params.yaml` |
| launch | 已安装：`install/explore_lite/share/explore_lite/launch/explore.launch.py` |

**两点实测补充**（方案原文未涉及）：

1. **`map_merge` 在 src 里但不构建**。仓库含 `explore` / `explore_lite_msgs` / `map_merge` 三个包，`--packages-up-to explore_lite` 只编前两个。
   → **后续在 `explore_ws` 里一律带 `--packages-up-to explore_lite`**，裸跑 `colcon build` 会把 `map_merge` 一起编（依赖更多，易报错）。
2. **安装路径按包名分层**：`install/<包名>/share/<包名>/config/`，不是按源码目录名（`explore/`）。
   查产物用 `find ~/Lin_workspace/explore_ws/install/explore_lite/share -type f`。

> 原始终端输出（含完整 CMake 警告与 `tree`）留档 `doc/raw_data/raw_explore_build_n97_2026-11-07_1240.txt`（本地，不入 git）。

##### 3.1.2 冒烟实测（2026-11-07 N97，无 Nav2 环境）

目标：在起 Nav2/slam_toolbox 之前，先钉死**节点名**与**参数是否真被读取**两件事。

```bash
# 终端 1：加 timeout 让它自己退，不留孤儿进程
source /opt/ros/humble/setup.bash && source ~/Lin_workspace/explore_ws/install/setup.bash && \
  timeout 30 ros2 run explore_lite explore --ros-args \
  --params-file /home/lin/Lin_workspace/explore_ws/install/explore_lite/share/explore_lite/config/params_costmap.yaml

# 终端 2：30 秒内执行
source /opt/ros/humble/setup.bash; ros2 node list; \
  ros2 param get /explore_node costmap_topic; ros2 param list /explore_node
```

| 结论 | 实测证据 | 影响 |
|:---|:---|:---|
| ✅ 节点默认名 = `explore_node` | `ros2 node list` → `/explore_node` | §3.2 参数段名正确，无需 remap |
| ✅ 参数被正确读取 | 日志 `Waiting for costmap to become available, topic: /global_costmap/costmap`；`param get` 同值 | 参数文件路径 + 解析链正常 |
| ✅ `use_sim_time` 可覆盖 | 出现在 `param list` 声明列表 | 实车 `false` 生效 |
| ✅ `return_to_init` **不存在** | 不在 `param list` 中 | 参数文件里保持注释，写入会报未声明 |
| ⚠️ 另 7 项**未声明** | `visualize` / `planner_frequency` / `progress_timeout` / `potential_scale` / `orientation_scale` / `gain_scale` / `min_frontier_size` 均不在 `param list` | 代码用 `get_parameter_or` 读取、未 declare。**值未必没生效**（启动无 `not declared` 报错），但 `param get` 查不到 → **调这些参数只能看运行期日志/行为，不能用 param get 验证** |
| ℹ️ 退出时 abort | `timeout` 发 SIGTERM 时 `failed to create guard condition ... rcl_shutdown() was called` | 功能期 30s 正常；**是否 SIGTERM 特有、Ctrl-C 是否复现，未测** |

> 终端 1 全程只有「等 costmap」一条日志——**这是预期**：没起 Nav2 与 slam_toolbox，节点拿不到输入。
> 冒烟只回答「能起来 / 名字对 / 参数读得进」，不覆盖任何运行时行为。
>
> 原始输出留档 `doc/raw_data/raw_explore_smoke_n97_2026-11-07_1253.txt`（本地，不入 git）。
>
> ⚠️ **订正**：本表第 4、5 行（`return_to_init` 不存在 / 7 项未声明）已被 §3.1.3 的干净复测推翻，
> 以 §3.1.3 为准。

##### 3.1.3 P1 复核：return_to_init 与 7 参数的结论订正（2026-11-07 晚，N97）

> 按 [doc-engineering §十](../doc-engineering.md) 翻案留痕：§3.1.2 原文保留不动，此处另立修正块 + 互指。
> 原始数据 `doc/raw_data/raw_explore_p1_retest_n97_2026-11-07_2010.txt`（本地，不入 git）。

**触发**：另一 session 核对上游 `326cf8a` 源码，指出 `explore.cpp:65-72` 是 `declare_parameter`
8 项（含 `return_to_init`），与 §3.1.2 的「不存在 / 未声明」矛盾。

**实测定论**（N97，同一进程内 A/B 对照）：

| 阶段 | 条件 | `param list` 结果 |
|:---|:---|:---|
| A | 只起节点（无 Nav2） | 9 项：costmap 侧 4 + `use_sim_time` + qos_overrides×4 —— **复现 §3.1.2 的观测** |
| B | 补 costmap + 静态 TF + 假 `NavigateToPose` action server | 17 项：**8 项全部出现** |

B 腿取证（与 `params_costmap.yaml` 一致）：

```text
ros2 param get /explore_node return_to_init     → Boolean value is: False
ros2 param get /explore_node planner_frequency  → Double value is: 0.15
ros2 param get /explore_node visualize          → Boolean value is: True
ros2 param get /explore_node potential_scale    → Double value is: 3.0
```

**订正内容**：

| 原结论（§3.1.2） | 实测事实 |
|:---|:---|
| `return_to_init` 不存在 | **存在**：`explore.cpp:72` declare，默认 `false`，`param get` 可取 |
| 7 项未声明、代码用 `get_parameter_or` 读取 | **已声明**：`explore.cpp:65-71` `declare_parameter`，`param get` 可取 |

**假阴性根因**（比"参数不存在"重要得多）——构造期三段串行阻塞，参数声明被挡在后段：

| 阻塞点 | 位置 | 等待对象 |
|:---:|:---|:---|
| ① | `costmap_client.cpp:89` | `/global_costmap/costmap` 首帧 |
| ② | `costmap_client.cpp` TF 段 | `map → base_link` |
| ③ | `explore.cpp:112` | `/navigate_to_pose` action server（**无超时**） |

①② 在 `Costmap2DClient` 构造函数内（它是 `Explore` 的成员、先于构造函数体执行）→
`explore.cpp:65-72` 的 8 个 declare 不执行；③ 在 declare 之后，但节点不 spin → 参数服务不响应。

> **运维含义**：explore_lite **不能在"只有雷达"的裸环境下用 `param list` 验参数**——
> 必须给齐 costmap + TF + action server。首跑时这三者由 slam_toolbox + Nav2 提供，属正常路径；
> 只有孤立冒烟才需要伪造。复测命令见原始数据第六节。
> 另一坑：`ros2 topic pub --once` 在 DDS 发现完成前会丢消息（volatile），对已在等待的订阅者要用 `-r 1` 连续发。

#### 3.2 参数文件 `r2_bringup/config/explore_params.yaml`

以官方 `explore/config/params_costmap.yaml` 为母本（**不要用 `params.yaml`**——后者订阅 `/map` 直连，不经过 Nav2 代价地图），改/补如下：

```yaml
explore_node:
  ros__parameters:
    robot_base_frame: base_link
    costmap_topic: /global_costmap/costmap
    costmap_updates_topic: /global_costmap/costmap_updates
    visualize: true
    planner_frequency: 0.15
    progress_timeout: 30.0
    potential_scale: 3.0
    orientation_scale: 0.0
    gain_scale: 1.0
    transform_tolerance: 0.3
    min_frontier_size: 0.5
    return_to_init: false
    use_sim_time: false
```

| 参数 | 初值 | 说明 |
|:---|:---|:---|
| `robot_base_frame` | `base_link` | 官方两套参数都已是 `base_link`，与 R2 一致 |
| `costmap_topic` | `/global_costmap/costmap` | 用 Nav2 全局代价地图做前沿检测；它含未知区 + 膨胀代价 |
| `costmap_updates_topic` | `/global_costmap/costmap_updates` | 增量更新；Nav2 默认发布 |
| `planner_frequency` | `0.15` | 约 6.7s 重规划一次；太低反应慢，太高刷屏 |
| `progress_timeout` | `30.0` | 30s 无进展弃目标；R2 低速 0.2m/s 若频繁超时调到 60.0 |
| `min_frontier_size` | `0.5` | 小于 0.5m 的前沿忽略，防抖动 |
| `return_to_init` | `false` | 首测不自动回起点；需要时改 `true` |
| `use_sim_time` | `false` | 实车必须关；官方 launch 默认 `true` |

> 新增配置后 `colcon build --packages-select r2_bringup`。

#### 3.3 启动（终端 D）

```bash
source /opt/ros/humble/setup.bash
source ~/Lin_workspace/r2_integration/install/setup.bash
source ~/Lin_workspace/explore_ws/install/setup.bash
ros2 run explore_lite explore --ros-args \
  --params-file $HOME/Lin_workspace/r2_integration/install/r2_bringup/share/r2_bringup/config/explore_params.yaml
```

> **不要直接 `ros2 launch explore_lite explore.launch.py`**：官方 launch 固定加载 `params.yaml`（`/map` 源）且 `use_sim_time` 默认 `true`，与 R2 的 Nav2 代价地图链路不匹配。若要用 launch，需另建包装 launch 覆盖参数文件与 `use_sim_time`。
>
> **2026-11-07 实测确认（`326cf8a`）**：官方 launch **未暴露 `params_file` 参数**——`config` 是硬编码的
> `os.path.join(get_package_share_directory("explore_lite"), "config", "params.yaml")`，不接受 `LaunchConfiguration`。
> 所以「命令行传 `params_file:=...` 覆盖」这条路**走不通**，只剩三条：
> ① `ros2 run explore_lite explore --ros-args --params-file <我们的.yaml>`（本文采用）；
> ② 自写包装 launch（= Step 2.1 的 `nav2_explore.launch.py` 顺带承担）；
> ③ 覆盖 `install/.../config/params.yaml`——**不采用**，rebuild 即丢且不可版本管理。
>
> 另记：`use_sim_time` 官方 launch 用 `DeclareLaunchArgument` 暴露（默认 `true`），可传 `use_sim_time:=false` 覆盖；
> 走 `ros2 run` 时该参数默认 `false`，天然正确。

#### 3.4 运行观察与停止/恢复

RViz 增加 `MarkerArray` 订阅 `explore/frontiers`，可看到候选前沿与当前目标。

```bash
# 暂停探索（车停）
ros2 topic pub --once /explore/resume std_msgs/msg/Bool "{data: false}"

# 恢复探索
ros2 topic pub --once /explore/resume std_msgs/msg/Bool "{data: true}"
```

预期日志：

- 有前沿：周期性发送 `NavigateToPose`，Nav2 规划并移动；
- 无前沿：`No frontiers found, stopping.` 或 `All frontiers traversed/tried out, stopping.`；
- 反复放弃同一目标：看 `progress_timeout` / 目标是否被代价地图判为不可达。

#### 3.5 首测方案（5×5m，先端到端）

1. 场地清空，起点放角落，车头朝开阔方向；一人持急停，一人观察 RViz。
2. 启动顺序：传感器 → EKF → slam_toolbox（Step 1）→ Nav2（Step 2）→ explore_lite（Step 3）。
3. 观察 3 件事：地图是否持续扩展、`explore_lite` 是否发目标、车是否按低速参数移动。
4. 出现异常先 `/explore/resume false` 停车，再查日志/代价地图，不要边跑边改参数。
5. 录包（按 [ros2-ops.md §4](../ros2-ops.md) 先核实话题存在）：

```bash
ros2 bag record -o ~/Lin_workspace/r2_integration/bags/raw/explore_$(date +%m%d_%H%M) \
  /scan /map /global_costmap/costmap /global_costmap/costmap_updates \
  /odometry/filtered /cmd_vel /tf /tf_static /explore/frontiers
```

> `/velodyne_points` 体积大，首测先不录；需要分析低物/点云时再加。`/map` 是 transient_local，录包 QoS 覆盖方法见 [ros2-ops.md §4](../ros2-ops.md)。

#### 3.6 覆盖率验收口径（5×5m）

探索结束后保存最终地图，在 ROI（5×5m 场地边界内）统计：

```text
coverage = ROI 内已知栅格数 / ROI 总栅格数
已知栅格 = 栅格值 >= 0（0=自由，100=占据；-1=未知）
判据：coverage > 80%
```

- ROI 在测试前用场地边界钉死，不要探索完再“挑一块好看的区域”。
- 墙外/场地外不计入 ROI；若地图边缘含墙外未知区，按实际场地裁剪。
- 结果与 bag/最终地图一起留档；脚本可后续补，本稿先定口径。

---

### Step 4 模式切换与回退

| 目的 | 启动 | 停止 |
|:---|:---|:---|
| 离线导航（现役） | 传感器/EKF → `nav2.launch.py map:=...` | Ctrl-C |
| Explore | 传感器/EKF → `slam_toolbox` → `nav2_explore.launch.py` → `explore_lite` | 先 `/explore/resume false`，再逐终端 Ctrl-C |
| Explore 地图回灌离线 | 保存 `explore_map_*.yaml` → `nav2.launch.py map:=...` | 同离线 |

**回退保证**：本方案只新增文件，不改 `nav2.launch.py` / `nav2_params_low.yaml` / `velodyne.launch.py` / `ekf.launch.py`；explore 跑不通时按上表切回离线模式即可，不需要回滚代码。

> 两种模式**不要同时启动**：AMCL 与 slam_toolbox 会同时发布 `map→odom`，TF 直接跳变。

---

## 四、验收清单

| # | 项 | 判据 | 方法 |
|:--|:---|:---|:---|
| 1 | TF 链 | `map→odom→base_link→velodyne` 连续、无跳变 | `tf2_echo`；RViz TF |
| 2 | 实时地图 | 地图随车扩展；墙段连续、无明显重影 | RViz；保存地图目检 |
| 3 | Nav2 接图 | 生命周期节点全 active；手动 Goal 可达 | `lifecycle get`；RViz Goal |
| 4 | 前沿探索 | `explore_lite` 持续发目标，不反复放弃同一前沿 | 日志；`explore/frontiers` |
| 5 | 覆盖率 | 5×5m ROI 已知栅格 >80% | 最终 `/map` 统计（§3.6） |
| 6 | 安全 | 首测无碰撞；急停有效；降额参数 | 现场 |
| 7 | 停止/恢复 | `/explore/resume false/true` 行为正确 | 话题发布 + 观察 |
| 8 | N97 负载 | `/scan` 不掉帧；Nav2 节点不掉线；无持续满载 | `top`/`htop` + `ros2 topic hz /scan` |

> 判据措辞按 [standards.md §1.15](../standards.md)：单场景 PASS ≠ 场景闭环；首测通过后至少补一次“换起点/换场地”复测，再谈收口。

---

## 五、风险与坑

| 风险 | 现象 | 处理 |
|:---|:---|:---|
| AMCL 与 slam_toolbox 同发 `map→odom` | 地图/位姿乱跳 | 启 explore 前 `ros2 node list` 确认无 AMCL/map_server |
| `base_frame` 仍是 `base_footprint` | slam_toolbox 不发布 `map→odom` / 报 TF 不存在 | 配置改 `base_link`；R2 已删 `base_footprint` |
| `use_sim_time` 为 true | TF 时间戳对不上、地图不动 | 启动显式 `use_sim_time:=false` |
| launch 加载 install 旧副本 | 新配置不生效 | 新增 config/launch 后 `colcon build --packages-select r2_bringup` |
| 全局代价地图收不到 `/map` | costmap 空白、前沿检测无输入 | 查 `/map` 是否 transient_local；`map_subscribe_transient_local: True` |
| `track_unknown_space` / `allow_unknown` 关闭 | 规划器拒绝前沿目标 | 保持现有 `true`；不要为 explore 改这两项 |
| `costmap_topic` 指错 | explore_lite 无前沿、日志空 | 用 `/global_costmap/costmap`；`ros2 topic info -v` 核对 |
| `progress_timeout` 太短 | 低速下频繁放弃目标 | 0.2m/s 场景先 30s，频繁超时改 60s |
| 低物盲区 1.59m | 探索中撞矮箱 | 首测场地避开低物；保留 low 带源；人工急停兜底；L4 行为层另议 |
| N97 CPU 吃紧 | `/scan` 掉帧、Nav2 掉线 | 不叠 KISS/FAST-LIO2；`map_update_interval` 2.0、`minimum_time_interval` 0.5；实测再降 |
| 动态行人/反光 | 前沿抖动、目标反复切换 | `min_frontier_size` 0.5；必要时停 explore 人工处理 |
| 地图保存过早 | 地图不完整 | 等“无前沿”日志后再 `map_saver_cli` |
| `explore_lite` 无 apt 包 | `ros2 run` 找不到 | 按 Step 3 源码构建；包名 `explore_lite`、可执行 `explore` |
| 官方 launch 默认 `use_sim_time:=true` | 实车不动 | 用 `ros2 run` + 自己的参数文件，或包装 launch 覆盖 |
| RViz Map 不显示 | 以为没建图 | Map display Durability 改 Transient Local |

---

## 六、文件改动清单

| 文件 | 类型 | 作用 |
|:---|:---|:---|
| `doc/minimal-loop2/explore-plan.md` | 新增（本文） | 实施梳理工作稿 |
| `r2_bringup/config/slam_toolbox_mapping.yaml` | 新增 | slam_toolbox 2D 建图参数 |
| `r2_bringup/launch/nav2_explore.launch.py` | 新增 | 去 map_server/AMCL 的 Nav2 启动 |
| `r2_bringup/config/explore_params.yaml` | 新增 | explore_lite 参数（Nav2 costmap 源） |
| `r2_bringup/config/explore.rviz` | 可选 | explore 专用 RViz（Map/代价地图/前沿 Marker） |
| `r2_bringup/launch/explore_all.launch.py` | 可选（稳定后） | 一条命令组合 slam_toolbox + Nav2 + explore |
| `~/Lin_workspace/explore_ws/src/m-explore-ros2` | 仓库外 | 官方源码，N97 本机构建 |

**不改**：`nav2.launch.py`、`nav2_params_low.yaml`、`velodyne.launch.py`、`ekf.launch.py`。

> `r2_bringup/setup.py` 已用 glob 安装 `config/*.yaml` 与 `launch/*.launch.py`，新增文件不需要改 setup.py。

---

## 七、待定事项（需用户定夺）

| 事项 | 选项 | 影响 |
|:---|:---|:---|
| 启动时机 | A1/A2 主线之后 / B2 余力窗口 / 插队 | 插队会打断当前主线；B2 原计划为 1~2 天演示级 |
| 验收场地 | 5×5m 演示场 / 实际比赛场地 | 场地越大，覆盖率与 `progress_timeout`/`min_frontier_size` 越要重调 |
| 是否自动回起点 | `return_to_init: false`（首测）/ `true` | `true` 会在无前沿后自动返航，需确认返航路径安全 |
| 低物兜底 | 仅靠现有 low 带源 + 人工急停 / 加 L4 限速停车 | L4 属行为层改动，不在本方案范围；盲区 1.59m 仍在 |
| 构建位置 | 仅 N97 / VM+N97 各一份 | 仅 N97 最省事；VM 可用于离线试跑但构建产物不能直接搬 |
| 组合 launch | 首跑分终端 / 稳定后再做 `explore_all.launch.py` | 分终端便于定位；组合 launch 少终端但排障面变大 |

> 本文默认假设：**2D 轻量探索**（slam_toolbox + explore_lite），不采用 3D 实时探索；若改 3D，架构与算力边界需另写一稿。

---

## 八、来源（2026-11-05 核实）

> 核实方式：官方仓库 shallow clone（`m-explore-ros2` commit `326cf8a`）+ 本机 Humble 安装文件；**未在 N97 实机运行，所有运行时行为标“未实测”**。
>
> **2026-11-07 增量核实**：`explore_lite` 已在 N97 实机构建（clone `326cf8a` → `colcon build --packages-up-to explore_lite` 成功）。
> 此次实测**只覆盖构建与安装产物**（包名/可执行名/参数文件落位/launch 内容），**运行时行为（无前沿日志、目标发送、
> 与 Nav2 的交互）仍未实测**。构建实录见 §3.1.1，原始输出 `doc/raw_data/raw_explore_build_n97_2026-11-07_1240.txt`（本地，不入 git）。

| 结论 | 来源 |
|:---|:---|
| `explore_lite` 包名/可执行 `explore`/节点名 `explore_node`；`NavigateToPose`；`/explore/resume`；`params_costmap.yaml` 订阅 `/global_costmap/costmap` | [m-explore-ros2 官方仓库](https://github.com/robo-friends/m-explore-ros2)（README + `explore/config/params*.yaml` + `explore/src/explore.cpp` + `explore/launch/explore.launch.py`） |
| `slam_toolbox` Humble 参数默认值（`base_footprint`、`use_sim_time`、`map_update_interval` 等） | 本机 `/opt/ros/humble/share/slam_toolbox/config/mapper_params_online_async.yaml` + `/opt/ros/humble/share/slam_toolbox/launch/online_async_launch.py`；[slam_toolbox 官方仓库](https://github.com/SteveMacenski/slam_toolbox) |
| Nav2 静态层 transient_local、`allow_unknown`、`track_unknown_space` | 本机 [nav2_params_low.yaml](../../r2_bringup/config/nav2_params_low.yaml)；[Nav2 官方文档](https://docs.nav2.org/) |
| 2D 探索选型（Phase 3.5，N97 可承受；3D 仅演示） | [规划控制路线 §2.1/§2.2/§5.5](../roadmaps/planning-control-roadmap.md)（已按 standards §1.11 带来源） |
| slam_toolbox 不适合 VLP-16 3D 主 SLAM 的旧结论 | [vlp16_slam_exploration.md](../retrospect/vlp16_slam_exploration.md)（本文 §1.3 区分 2D 探索层与 3D 主 SLAM） |
| 低物盲区 1.59m 几何边界 | [3d-lidar-2d-navigation-survey.md §三B](../surveys/3d-lidar-2d-navigation-survey.md) |
| 构建/启动/bag/QoS 操作纪律 | [ros2-ops.md](../ros2-ops.md)｜[ros2-qos-dds.md](../ros2-qos-dds.md) |

**未实测项**（首跑后回填）：`map_update_interval`/`transform_publish_period` 在 N97 的实际负载；`progress_timeout` 在 0.2m/s 下是否够用；`explore_lite` 与 R2 全向底盘的转向/倒车行为；5×5m 覆盖率能否 >80%。

---

## 九、变更记录

| 日期 | 变更 | 说明 |
|:---|:---|:---|
| 2026-11-05 | 初稿 | 方案梳理（未实测）；explore_lite 参数按官方 `params_costmap.yaml` 母本；明确不改现有 Nav2 launch/config |
| 2026-11-06 | 平台适配 | 老车撤 VLP-16 换 LD06；增 §十 平台适配（扫描源/TF/低带源/验收），探索骨架不变 |
| 2026-11-07 | Step 3.1 实测落地 | explore_lite 在 N97 构建通过（clone `326cf8a`、2 包 23.7s、仅 CMake 弃用警告）；增 §3.1.1 实测记录（含 `map_merge` 不构建提醒、安装路径按包名分层）；§3.3 补「官方 launch 无 `params_file` 参数」实测结论。**Step 1 / Step 2 / Step 3.2 仍未实测** |
| 2026-11-07 | 节点冒烟 + 三个配置文件落地 | 增 §3.1.2 冒烟实测（节点名 `explore_node`、参数读取正常、`return_to_init` 不存在、7 项未声明参数不可用 `param get` 验证）；新增 `slam_toolbox_mapping.yaml`（Step 1）、`nav2_explore.launch.py`（Step 2）、`explore_params.yaml`（Step 3.2）。**三份配置均未实测运行** |
| 2026-11-07 | P1 复核订正 | N97 干净复测（同进程 A/B）：`return_to_init` 与 7 参数**实为 `declare_parameter` 已声明**，上一行「不存在/未声明」作废；根因 = 构造期三段串行阻塞（costmap → TF → action server）。增 §3.1.3；`explore_params.yaml` 放开 `return_to_init` |

---

## 十、平台适配：VLP-16 → LD06（2026-11-06 增补）

> 上位决策：[two-car-architecture.md](../two-car-architecture.md)｜[决策记录](../retrospect/2026-11-06_platform_split_old_retrofit.md)。
> 本节只说明「本文哪些前提变了」，不重写上文步骤；首期按单 LD06 执行。

### 10.1 变化清单

| 本文原前提 | 老车新前提 | 处理 |
|:---|:---|:---|
| `/scan` 来自 `velodyne_laserscan`（VLP-16） | `/scan` 来自 LD06 驱动（`ldlidar_stl_ros2`，230400，`/dev/r2_ld06_a` udev 固定名） | 启动 LD06 launch；先 `ros2 topic info -v /scan` 核对 QoS/frame/频率 |
| `base_link→velodyne`（z=0.655） | `base_link→base_laser`（LD06 launch 的 z=0.18 是**占位值**） | 实车量安装高度后改静态 TF；不要沿用 0.655/0.18 |
| `nav2_params_low.yaml` 的 `velodyne_low` 低带源 | 老车无 `/velodyne_points` | 老车另建参数：首期先跑无低带源的 2D explore；二期用 `/scan_low` 或按 §十.2 处理。**2026-11-07 已落地**：`nav2_params_ld06.yaml`（只删低带源，G4） |
| 低物盲区 1.59m（VLP-16 几何） | 换雷达后几何全变 | 旧数字不适用；首测避开低物；低物验收另立 |
| `slam_toolbox` + Nav2 + explore_lite | 不变 | 继续用本文 Step 1~3；`base_frame` 仍 `base_link` |

### 10.2 双雷达拓扑（二期，待用户定夺）

| 方案 | 做法 | 影响 |
|:---|:---|:---|
| A. 分开 `/scan` + `/scan_low` | 一颗喂 slam_toolbox/Nav2，一颗只喂低带障碍层 | 保留几何语义；建图平面不被低平面污染；需要两套 TF/参数 |
| B. 合并单 `/scan` | 两颗按角度合并成一条 LaserScan | Nav2 简单；不同高度的点混在一个平面，建图/避障可能失真 |
| C. 单颗低装 | 只装一颗在低高度 | 低物覆盖改善；建图平面低、地面杂波多；无冗余 |

> 首期**不预选**；S1 单 LD06 跑出基线后，再按上位文档 §十 决策。本文 Step 1~3 的参数只需把雷达源换掉，不改探索逻辑。

### 10.3 Step 0 前置检查（替换原 0.3/0.4 的雷达部分）

```bash
# LD06 设备与驱动
ls -l /dev/r2_ld06_a 2>/dev/null   # udev 固定名优先；没有则先确认实际端口
ros2 launch ldlidar_stl_ros2 ld06.launch.py          # 端口/frame 按实车改
ros2 topic info -v /scan                             # 看 QoS、frame_id、发布者
ros2 topic hz /scan                                  # 预期 ~10Hz（2026-11-07 N97 实测 10.00Hz）
ros2 run tf2_ros tf2_echo base_link base_laser       # 静态 TF 是否按实车高度

# 仍要确认
ros2 topic hz /odometry/filtered
ros2 run tf2_ros tf2_echo odom base_link
ros2 node list | grep -E "amcl|map_server" || echo "OK: no AMCL/map_server"
```

**新增检查**：

- [ ] LD06 串口权限（`dialout` 组）与设备名稳定；两颗雷达不互换。
- [ ] `frame_id` 与静态 TF 一致（`base_laser`）；不要同时保留 VLP-16 的 `base_link→velodyne`。
- [ ] LD06 的 `range_min/range_max`、角度裁剪与场地匹配；低装时先测地面回波。
  **2026-11-07 已测**：消息 `0.02/25 m` 为驱动常量（非传感器规格），室内有效回波 ≤6.08 m；
  crop 90° 掩盖实测通过（详见 [ld06-dual-lidar.md P7](../old-car/ld06-dual-lidar.md)）——地面杂波/低装仍待实车。
- [ ] 首测场地无低矮障碍（低物验收放 S2）。

### 10.4 验收口径调整

- 本文 §四 的 8 项验收仍适用；第 8 项 N97 负载改为「LD06 `/scan` 不掉帧 + Nav2 节点不掉线」。
- 覆盖率口径不变（5×5m ROI >80%），但**地图质量**要加一条：墙段连续、无地面杂波造成的假墙。
- 低物可见性**不在 S1 验收**；S2 另立判据（目标高度/距离/是否进 costmap）。
- 单场景 PASS ≠ 场景闭环（[standards §1.15](../standards.md)）：S1 通过后至少换起点/换场地复测一次。

### 10.5 风险增补

| 风险 | 现象 | 处理 |
|:---|:---|:---|
| LD06 端口漂移/两颗互换 | 启动报错或数据错车 | udev 固定名；launch 用符号链接；启动前 `ls -l` |
| 低装地面杂波 | costmap 假障碍、地图脏 | 调高度/俯仰；角度裁剪；先静态测；必要时地面过滤 |
| 双雷达互扰 | 偶发噪点/丢帧 | 同开/单开对比；错开/遮挡；必要时分时 |
| 旧参数残留 `velodyne_low` | 启动报找不到源/低带层空 | 老车用 `nav2_params_ld06.yaml`（11-07 已建）；不要直接改历史 `nav2_params_low.yaml` |
| 静态 TF 沿用占位 0.18 | 地图尺度/障碍位置偏 | 实车量测后改 launch/URDF；用 `tf2_echo` 核对 |

### 10.6 来源（本节）

- LD06 驱动参数/端口/frame/占位 TF：本机 `~/ldlidar_ros2_ws/src/ldlidar_stl_ros2/launch/ld06.launch.py`（已读）。
- 平台分叉与首期单雷达：用户 2026-11-06 决策，见 [决策记录](../retrospect/2026-11-06_platform_split_old_retrofit.md)。
- 2D 探索链路/参数：本文 §一~§九（2026-11-05，未实测）。
- 未实测项：LD06 实际频率/量程/地面杂波、双雷达互扰、低装建图质量——S1/S2 实车回填。
- **2026-11-07 补测**：频率 10 Hz、beam 数/角分辨率、angle crop 掩盖已实测（[ld06-dual-lidar.md P7](../old-car/ld06-dual-lidar.md)）；
  剩余未实测 = 空旷场地量程、地面杂波、双雷达互扰、低装建图质量。
