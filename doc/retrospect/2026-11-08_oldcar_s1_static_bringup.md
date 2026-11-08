# 2026-11-08 老车 S1 静态联调（N97）：LD06 → slam_toolbox → Nav2 → explore_lite

> **日期/环境**：2026-11-08 12:01–12:05，N97（`lin-Default-string`）本机 ROS；用户从 VM 经 SSH 登录，**无图形界面**（全程 `rviz:=false`）。
> **任务**：验证 G1/G2/G3/G4 全链能否起来——LD06 单实例 → 静态 TF 顶替里程计 → slam_toolbox → `nav2_explore.launch.py` → explore_lite。
> 只起不动机器人；**不验安装几何、不验导航质量、不跑底盘/IMU/EKF**。
> **状态**：✅ 链路 PASS（lifecycle 全激活 / TF 树通 / explore 收到 costmap 并发出目标）｜🟡 G8 运行态未验（无 GUI）｜❌ 导航质量未验（规划全败，待定点实验）
> **证据**：[raw_s1_static_bringup_n97_2026-11-08_1201.md](../raw_data/raw_s1_static_bringup_n97_2026-11-08_1201.md)（N97 终端实录，本地不入 git）
> **关联**：[old-car/startup.md](../old-car/startup.md)（启动序列权威）｜[explore-plan.md](../minimal-loop2/explore-plan.md)（探索方案/验收）｜[s1-readiness-gap.md](../old-car/s1-readiness-gap.md)（S1 缺口）｜[two-car-architecture.md](../two-car-architecture.md)

---

## 〇、结论先行

| # | 判据 | 期望 | 实测 | 判定 |
|:--|:---|:---|:---|:---:|
| G1-1 | LD06 出 `/scan` | 驱动启动无报错 | `ldlidar node start is success` / `communication is normal` / `Publish topic message`，baud 230400 实测一致 | ✅ |
| G1-2 | slam_toolbox 建图 | 无 `base_footprint` 报错，产出 `/map` + `map→odom` | `Registering sensor: [Custom Described Lidar]`；`/map` 112×172 @0.05；`map→odom` 持续 10 帧 | ✅ |
| G2-1 | Nav2 探索版全生命周期 | 7 节点 configure→activate 全绿 | `Managed nodes are active`；planner/controller/bt_navigator 均 `active [3]` | ✅ |
| G2-2 | 代价地图接到 `/map` 与 `/scan` | static_layer 订阅 `/map`、obstacle_layer 订阅 `scan` | `Subscribing to the map topic (/map) with transient local durability`；`Subscribed to Topics: scan`；`Resizing costmap to 112 X 172` | ✅ |
| G3 | explore_lite 接入 | 连上 costmap 与 action server 并发出目标 | `Connected to move_base nav2 server`；`/explore_node` 在列；7 次目标下发（6 个不同坐标，`(0.20, 2.96)` 重复一次） | ✅ |
| G4 | 参数文件生效 | 无 `velodyne_low` 低带源 | global 插件仅 static/obstacle/inflation；local 仅 voxel/inflation；订阅话题只有 `scan` | ✅ |
| G8 | rviz 配置可用 | `rviz:=true` 能加载 `nav2.rviz` | **本轮未跑**（SSH 无图形，`rviz:=false`）；仅验到 install 层有文件 | 🟡 未验 |
| — | 规划可用性 | 能为 explore 目标出路径 | **6 个目标全部失败**（`failed to create plan with tolerance 0.50`） | ❌ |
| — | 进程卫生 | 收尾无残留 | `ps aux \| grep -iE "ldlidar\|slam_toolbox\|nav2\|explore\|static_transform"` 空；`ros2 node list` 空 | ✅ |

**一句话**：老车 2D 栈的"数据链"已通（激光→地图→代价地图→探索决策），但"规划链"未通；规划失败原因**尚未定因**，见 §四。

---

## 一、实验条件与取舍

| 项 | 本轮做法 | 原因 |
|:---|:---|:---|
| 底盘 / CAN | **未启动** | N97 无 USB-CAN 适配器（无 `/dev/ttyUSB*`、无 can 接口） |
| IMU / EKF | **未启动** | 同上；本轮只要 TF 树成形 |
| `odom→base_link` | **静态 TF 顶替**：`static_transform_publisher 0 0 0 0 0 0 odom base_link` | 让 slam_toolbox / Nav2 的 TF 链闭合，不引入里程计误差 |
| `map→odom` | slam_toolbox 提供 | 定位置信由激光匹配给出（静止车） |
| 雷达 | 单实例 A 路（`/dev/r2_ld06_a`） | S1 单实例纪律（G16） |
| 图形 | 无 | SSH 会话，`rviz:=false` |
| 场景 | 室内，车静止不动 | 只验链路，不验精度/覆盖率 |

> **注意**：本轮的 `map→odom` 由静止车的单帧/多帧扫描生成，地图只有 5.6 m × 8.6 m 的一小片；**不代表**实车行走时的建图表现。

---

## 二、完整执行序列（命令 + 实际现象）

> 顺序为**推荐启动顺序**；原始终端块顺序不等于时间顺序，时间线以 `[1794…]` 纪元秒为准（见 §二.6）。

### 2.1 终端 1：LD06 雷达（12:01:12）

```bash
source /opt/ros/humble/setup.bash
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch ldlidar_stl_ros2 ld06.launch.py
```

实际现象（节选）：

```text
[INFO] [LD06]: LDLiDAR SDK Pack Version is: v3.0.3
[INFO] [LD06]: <product_name>: LDLiDAR_LD06
[INFO] [LD06]: <topic_name>: scan
[INFO] [LD06]: <frame_id>: base_laser
[INFO] [LD06]: <port_name>: /dev/r2_ld06_a
[INFO] [LD06]: <port_baudrate>: 230400
[INFO] [LD06]: <laser_scan_dir>: Counterclockwise
[INFO] [LD06]: <enable_angle_crop_func>: false
[INFO] [LD06]: <angle_crop_min>: 135.000000
[INFO] [LD06]: <angle_crop_max>: 225.000000
[INFO] [LD06]: ldlidar node start is success
[INFO] [LD06]: ldlidar communication is normal.
[INFO] [LD06]: Publish topic message:ldlidar scan data.
[LDS][INFO][...[Actual BaudRate reported:230400]
[static_transform_publisher-2] translation: ('0.000000', '0.000000', '0.180000')
[static_transform_publisher-2] from 'base_link' to 'base_laser'
```

判读：驱动、串口、发布均正常；launch 内置的 `base_link→base_laser` 静态 TF（z=0.18，**G10 占位值**）同时起来。

### 2.2 终端 2：静态 TF 顶替里程计（12:01:26）

```bash
source /opt/ros/humble/setup.bash
ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 odom base_link
```

实际现象：

```text
[INFO] [static_transform_publisher_...]: Spinning until stopped - publishing transform
translation: ('0.000000', '0.000000', '0.000000')
rotation: ('0.000000', '0.000000', '0.000000', '1.000000')
from 'odom' to 'base_link'
```

### 2.3 终端 3：slam_toolbox 在线建图（12:02:23）

```bash
source /opt/ros/humble/setup.bash
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch slam_toolbox online_async_launch.py \
  slam_params_file:=$HOME/Lin_workspace/r2_integration/install/r2_bringup/share/r2_bringup/config/slam_toolbox_mapping.yaml \
  use_sim_time:=false
```

实际现象：

```text
[INFO] [slam_toolbox]: Node using stack size 40000000
[INFO] [slam_toolbox]: Using solver plugin solver_plugins::CeresSolver
[INFO] [slam_toolbox]: CeresSolver: Using SCHUR_JACOBI preconditioner.
[WARN] [slam_toolbox]: minimum laser range setting (0.0 m) exceeds the capabilities of the used Lidar (0.0 m)
Registering sensor: [Custom Described Lidar]
```

判读：`base_frame: base_link` 生效（无 `base_footprint` 报错）；WARN 见 §四-4。

### 2.4 终端 4：Nav2（探索版，无 map_server/AMCL）（12:03:20）

```bash
source /opt/ros/humble/setup.bash
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch r2_bringup nav2_explore.launch.py rviz:=false
```

实际现象（关键行）：

```text
[planner_server]:   Using plugin "static_layer"
[planner_server]:   Subscribing to the map topic (/map) with transient local durability
[planner_server]:   Using plugin "obstacle_layer"
[planner_server]:   Subscribed to Topics: scan
[planner_server]:   Using plugin "inflation_layer"
[ERROR] [global_costmap.global_costmap]: The configured inflation radius (0.300) is smaller than the
        computed inscribed radius (0.340) of your footprint, ...
[INFO]  [global_costmap.global_costmap]: StaticLayer: Resizing costmap to 112 X 172 at 0.050000 m/pix
[INFO]  [planner_server]: Created global planner plugin GridBased of type nav2_navfn_planner/NavfnPlanner
[controller_server]:   Using plugin "voxel_layer"  /  Subscribed to Topics: scan
[ERROR] [local_costmap.local_costmap]: The configured inflation radius (0.300) is smaller than the
        computed inscribed radius (0.340) ...
[controller_server]: Controller frequency set to 30.0000Hz
[controller_server]: Created controller : FollowPath of type nav2_mppi_controller::MPPIController
[WARN]  [controller_server]: Controller period is less then model dt, consider setting it equal
[lifecycle_manager_navigation]: Managed nodes are active
```

同时确认：`nav2_explore.launch.py` 拉起 7 个进程——planner_server、controller_server、smoother_server、behavior_server、bt_navigator、velocity_smoother、lifecycle_manager_navigation；behavior 插件为 spin / backup / drive_on_heading / assisted_teleop / wait。

### 2.5 终端 5：explore_lite（12:04:31）

```bash
source /opt/ros/humble/setup.bash
source ~/Lin_workspace/r2_integration/install/setup.bash
source ~/Lin_workspace/explore_ws/install/setup.bash
ros2 run explore_lite explore --ros-args \
  --params-file $HOME/Lin_workspace/r2_integration/install/r2_bringup/share/r2_bringup/config/explore_params.yaml
```

实际现象：

```text
[INFO] [explore_node]: Waiting for costmap to become available, topic: /global_costmap/costmap
[INFO] [explore_node]: Waiting to connect to move_base nav2 server
[INFO] [explore_node]: Connected to move_base nav2 server
```

随后 bt_navigator 收到 explore 下发的目标（全部失败，见 §四-1）：

```text
12:04:33  Begin navigating from current location (0.00, 0.00) to (-2.73, -1.62)
12:04:40  ... to (0.17, 2.96)      ← 第 1 个目标失败后 preempt
12:04:47  ... to (0.20, 2.96)
12:04:53  ... to (-0.01, 2.89)
12:05:00  ... to (0.20, 2.96)
12:05:07  ... to (-0.03, 3.16)
12:05:20  ... to (-0.10, 3.08)
```

### 2.6 验证命令与实测输出（全部原语句）

```bash
ros2 run tf2_ros tf2_echo base_link base_laser
ros2 run tf2_ros tf2_echo odom base_link
ros2 run tf2_ros tf2_echo map odom
ros2 topic echo /map --qos-durability transient_local --field info
ros2 lifecycle get /planner_server
ros2 lifecycle get /controller_server
ros2 lifecycle get /bt_navigator
ros2 topic echo /global_costmap/costmap --field info
ros2 param get /explore_node planner_frequency
ros2 node list | grep -i explore
ps aux | grep -iE "ldlidar|slam_toolbox|nav2|explore|static_transform" | grep -v grep
ros2 node list
```

实测：

| 命令 | 输出 | 判读 |
|:---|:---|:---|
| `tf2_echo base_link base_laser` | `Translation: [0.000, 0.000, 0.180]`，四元数单位，连出 5 帧 | ✅ TF 存在 |
| `tf2_echo odom base_link` | 全 0，连出 4 帧 | ✅ 静态顶替生效 |
| `tf2_echo map odom` | 全 0，10 帧时间戳 12:02:35→12:02:45 连续 | ✅ slam_toolbox 在发 |
| `topic echo /map --field info` | `resolution 0.05`，`width 112`，`height 172`，`origin (-4.9262, -3.8332)` | ✅ 地图产出 |
| `lifecycle get /planner_server` 等 ×3 | 均 `active [3]` | ✅ |
| `topic echo /global_costmap/costmap --field info` | 与 `/map` 完全一致（112×172 @0.05，同 origin） | ✅ static_layer 已灌入 |
| `param get /explore_node planner_frequency` | `Double value is: 0.15` | ✅ 参数生效 |
| `node list \| grep explore` | `/explore_node` | ✅ |
| `ps aux …` / `ros2 node list` | 均空 | ✅ 无残留 |

> `map_load_time: sec 0`：slam_toolbox 输出的 map header 时间戳为 0，static layer 正常接收，不影响本轮判定；如需追踪时间一致性再单独核。

### 2.7 时间线（按纪元秒还原）

| 时刻 | 事件 |
|:---|:---|
| 12:01:12 | LD06 启动 |
| 12:01:26 | 静态 TF `odom→base_link` 启动 |
| 12:02:23 | slam_toolbox 启动 |
| 12:03:20 | Nav2 启动 |
| 12:03:23 | `Managed nodes are active` |
| 12:04:31 | explore_lite 启动 |
| 12:04:33 | 首个 goal 下发，开始连续失败 |
| 12:05:24 | explore_lite 停止（`Exploration stopped.`） |
| 12:05:29–12:05:32 | Nav2 / slam_toolbox / TF / LD06 依次 Ctrl-C，均 `process has finished cleanly` |

---

## 三、复现清单（照做即可）

1. 前置：`echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor`（见 [startup.md §一](../old-car/startup.md)）。
2. 确认单实例：`ps aux | grep -i ldlidar | grep -v grep`，应只有一条。
3. 按 §2.1 → 2.5 顺序起五个终端（雷达 → 静态 TF → slam → Nav2 → explore）。
4. 每段起完跑 §2.6 里对应的验证命令，**不要等全部起完再查**（出问题好定位）。
5. 收尾：先停 explore（Ctrl-C）→ 再停 Nav2 → slam → TF → 雷达；最后 `ps` + `ros2 node list` 双查空。

> 本轮**没有**启动底盘 / IMU / EKF；实车独立启动的完整序列见 [old-car/startup.md §三](../old-car/startup.md)。

---

## 四、异常与判读

### 4.1 规划全部失败（未定因，本轮最重要）

现象：

```text
[bt_navigator]: Begin navigating from current location (0.00, 0.00) to (-2.73, -1.62)
[planner_server]: GridBased: failed to create plan with tolerance 0.50.
[planner_server]: Planning algorithm GridBased failed to generate a valid path to (-2.73, -1.62)
```

7 次目标下发（6 个不同坐标）全部失败，每个目标重试 2~4 次；失败后 BT 进入恢复行为（spin / backup / wait），因车不会动，恢复行为全部超时。

**已在日志中证伪的两条常见原因**（对应 navfn 的专用报错串，本轮**未出现**）：

- `The goal sent to the navfn planner is off the global costmap.` —— 未见
- `Cannot create a plan: the robot's start position is off the global costmap.` —— 未见

即：起点（0,0）与目标格本身**都在代价地图范围内**，失败发生在更后面的环节。

**待区分的假设**（本轮证据不足，不下结论）：

| 假设 | 支持现象 | 反证/待查 |
|:---|:---|:---|
| H1 目标格落在障碍/膨胀格（explore 前沿点贴墙） | 4 次 `worldToMap` 报错都出现在 x≈0.2 的贴边目标 | 第一个目标 (-2.73,-1.62) 在内部也失败，无 `worldToMap` 报错 |
| H2 起点与目标之间被隔断（地图小、未知区占比高） | 地图仅 112×172（5.6 m × 8.6 m） | `allow_unknown: true` 理论上可穿未知区 |
| H3 规划时刻的代价地图与后段 echo 到的不是同一份 | `worldToMap` 的 mx 与本轮 echo 的 origin 推算对不上（见 4.2） | 全程只出现一次 `Resizing costmap`，尺寸应未变 |

**定因实验**（尚未执行）：同链路起好后，手工发一个**明显在自由区**的 `NavigateToPose` 目标（如车正前方 0.5 m），看能否出路径；同时 `ros2 topic echo /global_costmap/costmap_raw` 直读目标格与起点格的值（判据见 [ros2-ops.md §11](../ros2-ops.md)）。两者结合可把 H1/H2/H3 拆开。

### 4.2 `worldToMap failed: mx,my: 112,126…145`（与容差搜索的几何吻合）

现象：4 批，每批 20 行，`mx` 恒为 112，`my` 从 126 递增到 145：

```text
[planner_server]: worldToMap failed: mx,my: 112,126, size_x,size_y: 112,172
...
[planner_server]: worldToMap failed: mx,my: 112,145, size_x,size_y: 112,172
```

已核实来源：该字符串在本机 `/opt/ros/humble/lib/libnav2_navfn_planner.so` 中，属 `nav2_navfn_planner::NavfnPlanner::worldToMap`（2026-11-08 `strings` 核对）。

**推导（源码未逐行核对，标注为推断）**：

- 地图实际范围：x ∈ [−4.926, **0.674**]，y ∈ [−3.833, 4.767]（origin + 尺寸 × 0.05）。
- 当批目标为 `(0.20, 2.96)`，其本身 `mx=102, my=135`，**在界内**。
- 配置 `tolerance: 0.5`（[nav2_params_ld06.yaml:329](../../r2_bringup/config/nav2_params_ld06.yaml)）。若容差搜索在 x 方向探到 `goal_x + 0.50 = 0.70`，则 `mx = (0.70 + 4.926)/0.05 = 112.5 → 112 = size_x`，恰好越界一格；`my` 126→145 对应 y ≈ 2.47→3.42，正是 `2.96 ± 0.5` 的窗口。
- 结论（推断）：这 20 行是**容差搜索在目标点容差圆周/方框上撞到地图右边界**产生的噪声，说明目标贴边，而不是"目标本身在界外"。

**影响**：这些 ERROR 会淹没日志，但不等于根因；H1 的验证仍需 4.1 的定点实验。

### 4.3 膨胀半径 < 内切半径（已知副作用）

```text
[ERROR] The configured inflation radius (0.300) is smaller than the computed inscribed radius (0.340)
        of your footprint, it is highly recommended to set inflation radius to be at least as big as ...
```

- 来源：08-17 为过窄缝把 `inflation_radius` 0.55→0.30（[retrospect 08-17](2026-08-17_nav2_initialpose_inflation_fix.md)），footprint 0.84×0.66 m。
- 影响：仅提示，不阻塞启动；碰撞兜底实际靠 MPPI `CostCritic` 的 `consider_footprint: true`（[nav2_params_ld06.yaml:207](../../r2_bringup/config/nav2_params_ld06.yaml)）。
- 处置：本轮不改参数；是否调回 ≥0.34 属参数决策，另议。

### 4.4 slam_toolbox 量程 WARN（措辞可疑）

```text
[WARN] [slam_toolbox]: minimum laser range setting (0.0 m) exceeds the capabilities of the used Lidar (0.0 m)
```

两个值都是 0.0 却判"超出"，属上游在零值边界的措辞/比较写法问题。本轮 `/map` 与 `map→odom` 均正常，**不影响建图**。
待核：`ros2 topic echo /scan --field range_min` / `range_max`（驱动常量报告 25 m，见 [slam_toolbox_mapping.yaml:15](../../r2_bringup/config/slam_toolbox_mapping.yaml) 注记）。

### 4.5 预期内、非故障

| 现象 | 判读 |
|:---|:---|
| `spin failed` / `backup failed`：`Exceeded time allowance` | 车不会动（无底盘），行为必然超时 |
| 反复 `Received request to clear entirely the global_costmap` | BT 恢复行为触发，正常 |
| `Failed to get result for backup in node halt!` + `Goal canceled` | 停止时的取消路径，正常 |
| `Controller period is less then model dt` | `controller_frequency 30`（周期 0.033 s）< `model_dt 0.04`；配置注释已知（[nav2_params_ld06.yaml:157](../../r2_bringup/config/nav2_params_ld06.yaml)），仅 WARN |
| `Parameter controller_server.verbose not found` | Nav2 1.1.20 版本差异提示，无功能影响 |

---

## 五、未验项（本轮边界）

| 项 | 状态 | 说明 |
|:---|:---:|:---|
| G8 rviz 运行态 | 🟡 | SSH 无图形，`rviz:=false`；仅验到 install 层存在 `nav2.rviz` |
| G10 安装几何 | ❌ | `z=0.18` 占位、x/y 无参数写死 0，未量测（见 [startup.md §六](../old-car/startup.md)） |
| 底盘 / IMU / EKF | ❌ | 本轮用静态 TF 顶替，**EKF 链未参与** |
| 导航质量（路径、控制、避障） | ❌ | 规划全败，无路径可跟 |
| 行走建图 / 探索覆盖率 | ❌ | 车静止，地图只有单视角 5.6×8.6 m |
| S1 首跑（整链含底盘） | ❌ | 仍为未完成状态（[s1-readiness-gap.md](../old-car/s1-readiness-gap.md)） |

---

## 六、方法模板（可复用）

### 卡 ①：无硬件条件下的 2D 栈静态联调

1. 不接底盘/IMU，用 `static_transform_publisher 0 0 0 0 0 0 odom base_link` 顶替 `odom→base_link`；
2. 雷达用真实驱动（真数据是链路验证的前提）；
3. 无图形则全程 `rviz:=false`，验证改走命令行（卡 ③）；
4. 该法能验证：TF 树、建图、costmap 灌入、lifecycle、action 连通；
   **不能验证**：里程计/EKF、导航质量、安装几何。

### 卡 ②：逐段启动 + 每段一验证

顺序固定：雷达 → 静态 TF → slam_toolbox → Nav2 → explore_lite。
每段起完立刻跑该段的最小验证（`tf2_echo` / `lifecycle get` / `topic echo --field info`），
失败即停在当前段，不进入下一段——避免"全起完了不知道哪段坏"。

### 卡 ③：无 GUI 的验证三连

```bash
ros2 run tf2_ros tf2_echo <parent> <child>                    # TF 存在性
ros2 lifecycle get /<nav2_node>                               # 生命周期
ros2 topic echo <topic> --field info                          # 大消息用 field，不用 hz
```

大消息（`/map`、`/global_costmap/costmap`）**禁用 `ros2 topic hz`**（best_effort 假阴性，见 [ros2-qos-dds.md](../ros2-qos-dds.md)）；`/map` 还需 `--qos-durability transient_local`。

### 卡 ④：收尾双查

```bash
ps aux | grep -iE "ldlidar|slam_toolbox|nav2|explore|static_transform" | grep -v grep
ros2 node list
```

两条都空才算干净（[ros2-ops.md §10](../ros2-ops.md)）。

### 卡 ⑤：把终端实录还原成时间线

粘贴块顺序 ≠ 执行顺序。用行内 `[1794…]` 纪元秒排序，或对照 `~/.ros/log/<时间戳>/` 目录名，再判断因果。

---

## 七、经验点层次标注

| # | 经验点 | 建议去向 |
|:--|:---|:---|
| E1 | 静态 TF 顶替 `odom→base_link` 可在无底盘时验证 2D 栈全链（TF/建图/costmap/action），但不能验导航质量 | **draft 层**（[analysis-methods.md](../analysis-methods.md)），复用后再抽规则层 |
| E2 | explore 前沿目标贴地图边界时，navfn 的容差搜索会刷 `worldToMap failed`（`mx == size_x`），属噪声，别当根因 | **draft 层** + 本档留存 |
| E3 | 日志里没有 "goal off the global costmap" / "start position off the global costmap" 两条专用串，可直接排除"起终点越界"这一类原因 | **draft 层**（判读法：先用专用报错串做排除） |
| E4 | `inflation_radius 0.30 < inscribed 0.34` 是 08-17 降膨胀的已知副作用，每次 costmap configure 必报 | **事件层留存**（参数决策未变，暂不进规则层） |
| E5 | slam_toolbox 在 `min_laser_range: 0.0` 时打印 "0.0 exceeds 0.0" 的矛盾 WARN，不影响建图 | **事件层留存**（待核实是否上游措辞问题） |
| E6 | 无图形环境下 G8（rviz 配置）只能验到 install 层，验证结论必须写明边界 | **draft 层**（验收边界表述） |
| E7 | 静止车的恢复行为（spin/backup）必然超时，是预期不是故障 | **事件层留存** |
| E8 | 终端实录块顺序不等于时间顺序，时间线要用纪元秒/日志目录名重建 | **规则层候选**（raw_data 留档纪律），先落 draft |

---

## 八、遗留回指

- 规划定因实验（§4.1）→ 待执行，结论回写本档 §四 或另开事件档。
- 未验项见 §五；S1 缺口与待定夺事项以 [s1-readiness-gap.md](../old-car/s1-readiness-gap.md) 为准。
- 启动序列权威仍是 [old-car/startup.md](../old-car/startup.md)；本档只作首次联调证据，不另立命令源。
