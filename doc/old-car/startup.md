# R2 老车（R2-OLD）启动手册（LD06 2D 栈）

> 定位：**老车启动序列唯一权威**——LD06 + slam_toolbox + Nav2（+ explore_lite）。
> **两车分文件**：本文只覆盖老车；VLP-16 时代基线（新车参考）见 [startup.md](../startup.md)，该文件保持不动。
> 老车**不得**套用 [startup.md](../startup.md) 的 `velodyne.launch.py` / KISS-ICP / FAST-LIO2 段（VLP-16 已撤下）。
> 职责边界：命令在本文；启动纪律与坑见 [ros2-ops.md §3](../ros2-ops.md)；平台分叉与共用/分叉清单见 [two-car-architecture.md](../two-car-architecture.md)。
>
> ⚠️ **状态：未实测（2026-11-08 建）**——命令取自 G1/G2/G3/G4 配置文件的头注与
> [explore-plan.md](../minimal-loop2/explore-plan.md) 的已定方案，**尚未整链实跑**。
> 首次跑通后回填实测基线并去掉本标注；缺口见 [s1-readiness-gap.md](s1-readiness-gap.md)。

---

## 一、前置（每次开机必做）

```bash
# 前置 0: CPU 性能模式（N97 重启后恢复 powersave；建图/Nav2 都会掉频，见 retrospect/2026-08-11_kiss_frame_rate_fix.md）
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor   # 应输出 performance

# 前置 1（可选）: 风扇固定转速（不持久化，重启后需重跑，完整指令见 retrospect/2026-08-24_n97_fan_control.md）
sudo modprobe it87 force_id=0x8622
echo 1 | sudo tee /sys/class/hwmon/hwmon4/pwm2_enable
echo 200 | sudo tee /sys/class/hwmon/hwmon4/pwm2
```

**环境注记**：N97 bashrc 含跨机 FASTRTPS 配置（10.18.18.x 网段，`r2_bringup/config/dds/`）——
单机话题发现异常先查该环境变量（[ros2-ops.md §1](../ros2-ops.md)）。

**单实例纪律（G16）**：S1 只用**一颗** LD06（A 路）。启动前确认没有第二实例在跑：

```bash
ps aux | grep -i ldlidar | grep -v grep     # 应只有一条；有多条先关掉 B 路实例
ros2 node list | grep -i ld06               # 应只有 /LD06 一个
```

---

## 二、模式选择（三选一）

| 模式 | 终端组合 | 用途 / 依据 |
|:---|:---|:---|
| **实时建图 / 探索** | 0,1,2,3,4,(5),6,7,8 | S1 主目标；slam_toolbox 在线建图 + Nav2 + explore_lite（方案见 [explore-plan.md](../minimal-loop2/explore-plan.md)） |
| **离线导航（已有地图）** | 0,1,2,3,4,(5),7 | map_server + AMCL 定位；`nav2_params_ld06.yaml` 两种模式共用 |
| **底盘独立调试** | 0,2,5 | 不动雷达/IMU，仅 CAN 控制 |

> 终端 7 在两种模式里**互斥**：探索用 `nav2_explore.launch.py`（无 map_server/AMCL），
> 离线导航用 `nav2.launch.py`（含 map_server/AMCL）。**两者不可同时启动**——
> AMCL 与 slam_toolbox 会同时发布 `map→odom`，TF 跳变。

---

## 三、启动序列（分终端）

```bash
# ⚠️ 通用纪律：每个终端先 source 对应工作区；IMU 启动后静止 3s 等校准，校准期不可动；
#    EKF 必须在 IMU 校准完成后启动，重启 IMU 必须同时重启 EKF（否则输出 NaN）

# 终端 0: CAN 总线（CanCmd 工具）
#   从主页面运行 CanCmd → 选择串口设备 → 选择波特率(1M) → 确认
python3 ~/Lin_workspace/command/can_command.py

# 终端 1: LD06 雷达（A 路，/dev/r2_ld06_a，发布 /scan）
#   默认即 S1 配置：port=/dev/r2_ld06_a、topic=scan、frame=base_laser
#   ⚠️ z=0.18 是占位值、x/y 写死 0（launch 无 x/y 参数）——安装几何待实车量测（G10）
#   ⚠️ 改过 package 或首次部署须先 colcon build（launch 加载 install 副本）
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch ldlidar_stl_ros2 ld06.launch.py

# 终端 2: 底盘（EKF 场景必须带 publish_tf:=false，让 EKF 统一发 odom→base_link）
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch r2_bringup chassis.launch.py publish_tf:=false

# 终端 3: IMU（启动后静止 3s 等校准，校准期不可动）
#   mount_axes:=y_front_x_left_z_down 是 R2 的 G354 出厂轴定义（x左/y前/z下），见 phase0/sensor-mount.md
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch g354_imu_driver g354_rviz.launch.py rviz:=false serial_port:=/dev/r2_g354 mount_axes:=y_front_x_left_z_down

# 终端 4: EKF（必须在 IMU 校准完成后启动；重启 IMU 必须同时重启 EKF）
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch r2_bringup ekf.launch.py

# 终端 5（可选）: WASD 键盘遥控
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 run r2_bringup teleop_keyboard

# —— 实时建图 / 探索模式（终端 6 → 7 → 8）——

# 终端 6: slam_toolbox 在线建图
#   ⚠️ 官方 launch 的 use_sim_time 默认 true，实车必须显式传 false（否则无 /clock 卡住）
#   ⚠️ 必须用自己的参数文件：官方母本 base_frame=base_footprint（R2 无该 frame）
#   产出：/map（transient_local）+ map→odom TF
source /opt/ros/humble/setup.bash
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch slam_toolbox online_async_launch.py \
  slam_params_file:=$HOME/Lin_workspace/r2_integration/install/r2_bringup/share/r2_bringup/config/slam_toolbox_mapping.yaml \
  use_sim_time:=false

# 终端 7: Nav2（探索版：无 map_server/AMCL，定位层由 slam_toolbox 提供）
#   默认参数已是老车 LD06 版 nav2_params_ld06.yaml（11-07 起），无需再传 params_file
source /opt/ros/humble/setup.bash
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch r2_bringup nav2_explore.launch.py rviz:=true
#   不要点 "2D Pose Estimate"：AMCL 未启动，map→odom 由 slam_toolbox 提供

# 终端 8: explore_lite（源码工作区，独立于主工作区）
#   ⚠️ 不要用官方 launch：它写死 params.yaml（/map 源）且 use_sim_time 默认 true
#   ⚠️ 段名 explore_node 必须与节点实际名一致，否则参数静默失效
source /opt/ros/humble/setup.bash
source ~/Lin_workspace/r2_integration/install/setup.bash
source ~/Lin_workspace/explore_ws/install/setup.bash
ros2 run explore_lite explore --ros-args \
  --params-file $HOME/Lin_workspace/r2_integration/install/r2_bringup/share/r2_bringup/config/explore_params.yaml

# —— 离线导航模式（终端 7 替代探索版）——
# 需要先有地图（探索结束后保存：ros2 run nav2_map_server map_saver_cli -f $HOME/maps/<名字>）
# source /opt/ros/humble/setup.bash
# source ~/Lin_workspace/r2_integration/install/setup.bash
# ros2 launch r2_bringup nav2.launch.py \
#   map:=$HOME/maps/<地图>.yaml \
#   params_file:=$HOME/Lin_workspace/r2_integration/install/r2_bringup/share/r2_bringup/config/nav2_params_ld06.yaml \
#   rviz:=true
# 之后 rviz 里 2D Pose Estimate 设初始位姿 → Navigation2 Goal 发目标
```

**探索停止/恢复**（异常先停再查，不边跑边改参数）：

```bash
# 暂停（车停）
ros2 topic pub --once /explore/resume std_msgs/msg/Bool "{data: false}"
# 恢复
ros2 topic pub --once /explore/resume std_msgs/msg/Bool "{data: true}"
```

---

## 四、启动后验证基线（老车）

> `/imu/data`、`/odometry/filtered`、`/odom_wheels` 三行**沿用 VLP-16 时代基线**——S1 保留 G354 + 现有 EKF，链路未变。
> `/scan` 为 2026-11-07 N97 实测值。**整链未实跑**，首跑后回填。

| 话题 / 项 | 期望 | 备注 |
|:---|:---|:---|
| `/scan` | ~10 Hz | 11-07 N97 实测 10.00 Hz；beam 452~455/圈、角分辨率 0.793~0.798°；室内有效回波 ≤6.08m（[ld06-dual-lidar P7](ld06-dual-lidar.md)） |
| `/imu/data` | ~100 Hz | G354；沿用基线 |
| `/odometry/filtered` | ~30 Hz | EKF；沿用基线 |
| `/odom_wheels` | ~50 Hz | 轮速；沿用基线 |
| `map→odom` | 持续有变换 | slam_toolbox 发布；**只有它一个发布者** |
| `odom→base_link` | 单一发布者 | chassis 带 `publish_tf:=false` 时由 EKF 发 |
| `base_link→base_laser` | 静态存在 | LD06 launch 内的 static_transform_publisher；**无 velodyne frame** |
| Nav2 生命周期 | `planner_server` / `controller_server` 均 `active` | `ros2 lifecycle get <节点>` |
| `/global_costmap/costmap` | 有数据且含膨胀灰阶 | 大消息话题**不要用 `hz`**（假阴性，见 [ros2-qos-dds.md](../ros2-qos-dds.md)），用 `ros2 topic echo --field info` |

```bash
# TF 链核对（三条都应持续有输出）
ros2 run tf2_ros tf2_echo map odom
ros2 run tf2_ros tf2_echo odom base_link
ros2 run tf2_ros tf2_echo base_link base_laser
```

> **首次联调实录（2026-11-08）**：静态 TF 顶替里程计、无 GUI（SSH）条件下跑通 LD06 → slam_toolbox → Nav2 → explore_lite，
> 逐终端命令、实际输出与判读见 [retrospect/2026-11-08_oldcar_s1_static_bringup.md](../retrospect/2026-11-08_oldcar_s1_static_bringup.md)。
> 该轮**未跑** `/imu/data`、`/odometry/filtered`、`/odom_wheels` 三行（无底盘/IMU），且**规划全败未定因**——首跑对照时留意。

---

## 五、停止与回退

| 目的 | 操作 |
|:---|:---|
| 停探索 | 先 `/explore/resume false` → 再逐终端 Ctrl-C（终端 8 → 7 → 6） |
| 切离线导航 | 关掉终端 8 / 7 / 6，用终端 7 的离线命令（`nav2.launch.py`） |
| 回退到 VLP-16 时代流程 | 老车不适用（VLP-16 已撤）；新车参考 [startup.md](../startup.md) |

> `/explore/resume` 为 `std_msgs/Bool`（[two-car-architecture.md §六](../two-car-architecture.md) 接口表）。

---

## 六、已知未落地 / 风险（首跑前必读）

| 项 | 现状 | 影响 |
|:---|:---|:---|
| **G10 安装几何** | `ld06.launch.py` 的 z=0.18 为占位、x/y 无参数写死 0、0° 朝向未定 | 障碍/地图位置整体偏移；首跑只验链路不验精度。量测时 LD06 的 URDF/TF 一并重写 |
| **G11 量程** | `slam_toolbox max_laser_range: 20.0`（抄自 VLP-16 母本），LD06 室内有效 ≤6.08m | 只影响栅格化/匹配搜索范围，不截断输入；是否调小待实车评估 |
| **G14 供电** | 车体侧 5V 未带载长跑 | 历史掉电根因已定位为接线端子松动；首测仍须监视 |
| **G16 双实例** | N97 曾同时跑 A+B 两路 | 同名节点抢话题；见 §一 单实例纪律 |
| **G19 录包清单** | 老车版见 [explore-plan §3.5](../minimal-loop2/explore-plan.md) | 录包前先 `ros2 topic list` 核实话题存在（[ros2-ops.md §4](../ros2-ops.md)） |
| **整链未实测** | G1/G2/G3 配置均未联跑 | 首跑即本手册的首次验证，出错按上面各终端的注记逐段隔离 |
| **链路联调现状（11-08）** | 已用静态 TF 顶替里程计完成 LD06→slam_toolbox→Nav2→explore_lite 联跑：**链路 PASS**（lifecycle 全激活/TF 通/explore 发目标），**规划全败未定因** | 不含底盘/IMU/EKF 与导航质量；复现清单与证据见 [retrospect 11-08](../retrospect/2026-11-08_oldcar_s1_static_bringup.md) |

---

## 相关文件

- 老车专题：[ld06-dual-lidar.md](ld06-dual-lidar.md)（LD06 执行计划/规格）｜[s1-readiness-gap.md](s1-readiness-gap.md)（S1 缺口清单）｜[two-car-architecture.md](../two-car-architecture.md)（两车接口）
- 方案与判据：[explore-plan.md](../minimal-loop2/explore-plan.md)（探索方案/验收 8 项/覆盖率口径）
- 纪律与坑：[ros2-ops.md](../ros2-ops.md)（启动纪律 §3、bag §4）｜[ros2-qos-dds.md](../ros2-qos-dds.md)（大消息验证）
- 新车/VLP-16 基线：[startup.md](../startup.md)（保持不动，仅作新车参考）
- 首次联调证据：[2026-11-08_oldcar_s1_static_bringup.md](../retrospect/2026-11-08_oldcar_s1_static_bringup.md)（静态 TF 顶替里程计的全链实录 + 复现清单）
