# R2 集成 · 状态交接

> 最后更新: 2026-08-02（全面彻查后）
> 当前进度: Phase 0 ✅ 100%｜Phase 1 EKF 配置完成，实车验证挂起｜Phase 2 ✅ 驱动+里程计+键盘建图全跑通
> 下一阶段: Phase 1 EKF 实车验证（清单见 [ekf-verification.md](phase1/ekf-verification.md)）→ Phase 3 Nav2；另评估 FAST-LIO2 替代 KISS-ICP
>
> **部署环境**：N97 Mini PC（192.168.1.210，Ubuntu 22.04 + Humble），enp1s0: 10.18.18.20/24
> 开发环境：VM（lin-virtual-machine，192.168.1.204）；VM→N97 SSH 免密可用
> 网络：VLP-16 雷达 IP **10.18.18.6**（2026-08-02 从 10.10.3.6 迁移）

---

## 一、当前进度总览

| Phase | 目标 | 状态 | 说明 |
|:------|:-----|:----:|:-----|
| 0 | 底盘 ROS2 + CAN 控制 | ✅ 100% | 四全向轮，全命令可用 |
| 1 | G354 IMU + 轮速 EKF 融合 | ◆ 30% | 配置/修复全部完成，**实车验证挂起** |
| 2 | VLP16 + KISS-ICP SLAM | ✅ 100% | 驱动+里程计+键盘建图全跑通（8-02） |
| 3 | VLP16 + Nav2 导航 | ⏳ 0% | — |
| 4 | D435 + Jetson 视觉 | ⏳ 0% | — |
| 5 | 气动+异常+编排 | ⏳ 0% | — |

**8-02 核心成果**：EKF/TF 融合链路 7 个问题全部解决（详见
[retrospect/2026-08-02_ekf_tf_fusion_fix.md](retrospect/2026-08-02_ekf_tf_fusion_fix.md)），
当前全套系统稳定运行；KISS-ICP 参数已调优（抖动/旋转性能为纯激光算法本底）。

---

## 二、当前运行状态（2026-08-02 19:21 实测）

### 2.1 运行节点（N97，全套 12 个）

```
ekf_filter_node / g354_imu_node / kiss_icp_node / r2_chassis_node /
r2_teleop_keyboard / robot_state_publisher / static_transform_publisher(base_link→imu_link) /
velodyne_driver_node / velodyne_transform_node / velodyne_laserscan_node / rviz / rqt
```

### 2.2 关键话题与数据表现（实测 hz）

| 话题 | 频率 | 备注 |
|:-----|:-----|:-----|
| /imu/data | ~100Hz（std 0.0025）✅ | G354，稳定 |
| /odometry/filtered | ~50Hz（std 0.002）✅ | EKF 融合输出，稳定 |
| /odom_wheels | ~50Hz（std 0.002）✅ | 轮速里程计 |
| /velodyne_points | ~10Hz（std 0.089）⚠️ | 600rpm，**掉帧明显**（0.094~0.409s） |
| /kiss/odometry | ~10Hz（std 0.050）⚠️ | 跟随雷达帧率，配准耗时波动 |
| /kiss/points 等 | visualize:=true 时发布 | 前缀 **/kiss/**（非 /kiss_icp/） |

### 2.3 数据表现（静止实测）

- EKF 姿态与 IMU 姿态几乎一致（四元数 0.0226/0.0283/0.0172/0.9992）→ 融合正确
- EKF position.z = -0.185m（process noise 漂移，无观测，2D 导航无影响）
- odom→base_link 单一发布者（chassis publish_tf=false）✅

---

## 三、启动命令（N97，按顺序，分终端）

```bash
# 终端 0: CAN 总线
python3 ~/Lin_workspace/command/can_command.py

# 终端 1: 雷达（device_ip 10.18.18.6，600rpm/10Hz）
ros2 launch ~/.ros/velodyne_n97.launch.py

# 终端 2: KISS-ICP（visualize:=true 发 /kiss/points 并带 RViz；false 则无点云话题）
source ~/kiss_icp_ws/install/setup.bash
ros2 launch kiss_icp odometry.launch.py \
  topic:=/velodyne_points base_frame:=velodyne \
  use_sim_time:=false visualize:=true   # ⚠️ use_sim_time 必须显式 false

# 终端 3: 底盘（publish_tf:=false 让 EKF 发 TF；独立使用可不带）
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch r2_bringup chassis.launch.py publish_tf:=false

# 终端 4: IMU（启动后静止 3s 等校准，校准期不可动）
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch g354_imu_driver g354_rviz.launch.py rviz:=false serial_port:=/dev/ttyACM1

# 终端 5: EKF（必须在 IMU 校准完成后启动；重启 IMU 必须同时重启 EKF）
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch r2_bringup ekf.launch.py

# 终端 6: WASD 键盘遥控（python3 直启，绕开本环境 libexec 布局问题）
python3 ~/Lin_workspace/r2_integration/r2_bringup/r2_bringup/teleop_keyboard.py
# 或一键（GNOME 终端环境）:
# bash ~/Lin_workspace/r2_integration/scripts/r2_startup.sh
```

**IMU 独立看姿态**：`ros2 run rviz2 rviz2` → Fixed Frame 填 `imu_link` →
Add → By display type → Imu（需已装 `ros-humble-rviz-imu-plugin`）→ Topic `/imu/data` → QoS **Reliable**。

---

## 四、关键配置（位置 + 当前值）

| 配置 | 位置 | 当前值 |
|:-----|:-----|:-------|
| EKF 融合 | `r2_bringup/config/ekf.yaml` | 15 值完整配置；轮速给 x/y/vx/vy，IMU 给 yaw/角速度 |
| 底盘 TF | `chassis.launch.py` | `publish_tf:=false`（EKF 场景），默认 true |
| 静态 TF | `ekf.launch.py` | `base_link→imu_link` 单位变换 |
| KISS-ICP | `~/kiss_icp_ws/src/kiss_icp/config/config.yaml` | max_range 30 / min_range 0.5 / voxel_size 0.2（8-02 调优，备份 .bak_20260802） |
| 雷达驱动 | `~/.ros/velodyne_n97.launch.py` | device_ip 10.18.18.6（备份 .bak_20260802） |
| 底盘参数 | `r2_bringup/config/r2_params.yaml` | 全实车标定值（speed_scale 94.5 等） |

---

## 五、本次联调结果与现象（2026-08-02）

### 已解决（7 问题，详见 retrospect 文档）

| 问题 | 根因 | 修复 |
|:-----|:-----|:-----|
| 网络迁移 10.10.3.x→10.18.18.x | 规划调整 | device_ip 同步更新 |
| KISS-ICP 里程计不走 | launch 默认 use_sim_time=true | 显式 false |
| imu_link 标红 | TF 树无 imu_link | ekf.launch.py 加 static TF |
| /imu/data 灰色 | N97 未装 rviz_imu_plugin + QoS | 装插件 + QoS Reliable |
| 点云/IMU 震动"打架" | odom→base_link 双发布者 | chassis 加 publish_tf 参数 |
| chassis 启动崩溃 | 协方差 int 非 float | 0→0.0 |
| EKF yaw 大跳 + z 漂 12m | N97 ekf.yaml 坏配置（6 值 vs 15 值） | 同步正确配置 |

### 遗留现象（算法本底，非故障）

- **KISS-ICP 静止/运动均有毫米~厘米级抖动**：纯激光配准本底（无 IMU 融合）
- **旋转时点云更新滞后，静止后恢复**：旋转运动畸变，deskew 用上一帧匀速外推校不准
- 已调优参数缓解，未根治；**长期方案：换带 IMU 的 LIO（推荐 FAST-LIO2，VLP-16 已原生支持）**

---

## 六、遗留与待办

- [ ] **Phase 1 EKF 实车验证**（静态 3min/直线 5m/旋转/矩形闭环）— 清单与判合格标准见 [ekf-verification.md](phase1/ekf-verification.md)
- [ ] **FAST-LIO2 评估**（Ericsiii ROS2 fork，VLP-16 原生支持，接 G354 解决旋转痛点）— VM 先编译验证
- [ ] **git 提交**：VM 工作区积压大量未提交改动（代码修复+文档），分支 master
- [ ] 雷达掉帧调查（/velodyne_points std 0.089s，600rpm 下帧间隔不稳）
- [ ] 可选：VLP-16 rpm 600→1200（20Hz）试验（帧内畸变减半，需重启雷达驱动）
- [ ] waypoint 雷达闭环（基于 /kiss/odometry 自主行走）
- [ ] z 轴 process noise 漂移（3D 场景再处理）

---

## 七、阶段性总结（Phase 0 → 2）

**已完成的能力**：
- 底盘：ROS2 + CAN 全向轮控制、里程计、TF、键盘遥控（WASD 一键一状态）
- 感知：VLP-16 驱动 + KISS-ICP 3D 里程计 + 实时点云建图（车在点云地图中移动 ✅）
- 融合：G354 IMU + 轮速 → EKF 融合链路完整可用（/odometry/filtered 稳定 50Hz）

**关键结论**：
1. KISS-ICP 适合建图/演示，旋转性能和精度受纯激光本质限制——后续自主导航建议换 LIO
2. EKF 融合是底盘导航的基础（yaw 来自 IMU，位置来自轮速），实车验证是收尾前必须项
3. 本阶段 7 个问题的共性教训：跨机器同步必须全覆盖（含配置）、第三方 launch 默认值必须实测、配置不合法可能不报错

**资源状态**：VM 与 N97 代码已同步（r2_bringup 全套 + ekf.yaml + kiss config），
文档 9 份已同步 Obsidian 镜像。N97 磁盘 25%，负载 4.2（全套运行中正常）。

---

## 八、相关文档索引

- 排障全记录：`retrospect/2026-08-02_ekf_tf_fusion_fix.md`（7 问题：现象/命令/根因/解决/验证）
- 进度看板：`02-progress.md` ｜ 状态快照：`03-current_state.md`
- EKF 验证清单：`phase1/ekf-verification.md` ｜ SLAM 方案探索：`retrospect/vlp16_slam_exploration.md`
- 底盘定义：`phase0/chassis_definition.md` ｜ 键盘控制修复：`retrospect/2026-07-31_teleop_keyboard_fix.md`
