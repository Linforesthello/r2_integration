# R2 启动手册（全栈启动序列唯一权威）

> 定位：R2 全套机器人栈启动命令与顺序的**唯一权威**（两机通用，差异已标注）。三种运行模式按需选一。
> 职责边界：命令在此维护；启动纪律/坑在 [ros2-ops.md §3](ros2-ops.md)；部署细节在 `n97/` 各手册。
> 引用方：07-handover（交接）｜README（快速启动）｜w1/w2/w3/execution/relog（执行卡）——启动一律以本文为准。
> 相关：[07-handover.md](07-handover.md)（状态交接）｜[fastlio2-n97-deploy.md](n97/fastlio2-n97-deploy.md)（FAST-LIO 部署/排障）｜[greenwave-monitor-deploy.md](n97/greenwave-monitor-deploy.md)（话题监测替代手动 hz）｜[sensor-mount.md](phase0/sensor-mount.md)（传感器安装/轴定义）

---

## 一、前置（每次开机必做）

```bash
# 前置 0: CPU 性能模式（N97 重启后治理器恢复 powersave，KISS 会掉回 3.6Hz 重影复现，见 retrospect/2026-08-11_kiss_frame_rate_fix.md）
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
# 检查（应输出 performance）:
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor

# 前置 1（可选）: 风扇固定转速（08-24 起；驱动不持久化，重启后需重跑，完整指令见 retrospect/2026-08-24_n97_fan_control.md）
sudo modprobe it87 force_id=0x8622
echo 1 | sudo tee /sys/class/hwmon/hwmon4/pwm2_enable    # 切手动（只需设一次）
echo 200 | sudo tee /sys/class/hwmon/hwmon4/pwm2          # 设转速（0-255），即刻生效
# 恢复自动: echo 2 | sudo tee /sys/class/hwmon/hwmon4/pwm2_enable（重启兜底）
# 查询当前转速: cat /sys/class/hwmon/hwmon4/fan2_input
```

**环境注记**：N97 bashrc 含跨机 FASTRTPS 配置（10.18.18.x 网段，`r2_bringup/config/dds/`）——单机跑话题发现异常先查该环境变量（见 [ros2-ops.md §1](ros2-ops.md)）。

---

## 二、模式选择（三选一 + 独立调试）

| 模式 | 终端组合 | 用途 / 依据 |
|:---|:---|:---|
| **建图（KISS）** | 1, 2, 3, 4, 5, 6 | 键盘建图/里程计演示；流程见 [minimal-loop/w1-operation.md](minimal-loop/w1-operation.md) |
| **导航（Nav2）** | 1, 3, 4, 5, 6, 7 | Nav2 自主导航；**KISS 不启动**（08-15 决策：AMCL 定位不需要，省 N97 CPU） |
| **FAST-LIO 实验** | 1, 4, 8 | FAST-LIO2 建图/里程计对比（替代 KISS+EKF 链路）；部署/外参/排障见 [fastlio2-n97-deploy.md](n97/fastlio2-n97-deploy.md) |
| **底盘独立调试** | 3, 6 | 不动雷达/IMU，仅 CAN 控制 |

> 08-15 起 `/scan` 暂无消费者，velodyne_laserscan_node 停用（见 retrospect/2026-08-15_velodyne_perf_tuning.md）；Nav2 接入 scan 时恢复。

---

## 三、启动序列（分终端，模式按 §二 组合）

```bash
# ⚠️ 通用纪律: 每个终端先 source 对应工作区；IMU 启动后静止 3s 等校准，校准期不可动；
#    EKF 必须在 IMU 校准完成后启动，重启 IMU 必须同时重启 EKF（否则输出 NaN）

# 终端 0: CAN 总线（使用 CanCmd 工具）
#   从主页面运行 CanCmd → 选择串口设备 → 选择波特率(1M) → 确认
python3 ~/Lin_workspace/command/can_command.py

# 终端 1: 雷达（device_ip 10.18.18.6，600rpm/10Hz）
#   ⚠️ 08-15 起 launch 在 r2_sensors 包：先 git pull + colcon build（launch 加载 install 副本）
ros2 launch r2_sensors velodyne.launch.py

# 终端 2: KISS-ICP —— 仅建图模式（visualize:=true 发 /kiss/points 并带 RViz；false 则无点云话题）
#   ⚠️ 必须先 source kiss_icp_ws（独立工作区）；建图前实机确认 /kiss/frame 是否依赖 visualize
source ~/kiss_icp_ws/install/setup.bash
ros2 launch kiss_icp odometry.launch.py \
  topic:=/velodyne_points base_frame:=velodyne \
  use_sim_time:=false visualize:=true   # ⚠️ use_sim_time 必须显式 false

# 终端 3: 底盘（EKF 场景必须带 publish_tf:=false 让 EKF 统一发 TF；独立使用可不带）
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch r2_bringup chassis.launch.py publish_tf:=false

# 终端 4: IMU（启动后静止 3s 等校准，校准期不可动）
#   mount_axes:=y_front_x_left_z_down 是 R2 的 G354 出厂轴定义（x左/y前/z下），见 phase0/sensor-mount.md
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch g354_imu_driver g354_rviz.launch.py rviz:=false serial_port:=/dev/ttyACM1 mount_axes:=y_front_x_left_z_down

# 终端 5: EKF（必须在 IMU 校准完成后启动；重启 IMU 必须同时重启 EKF）
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch r2_bringup ekf.launch.py

# 终端 6: WASD 键盘遥控（08-11 P3 setup.cfg 修复后 ros2 run 可直接启动）
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 run r2_bringup teleop_keyboard
# 或一键（GNOME 终端环境）: bash ~/Lin_workspace/r2_integration/scripts/r2_startup.sh

# 终端 7: Nav2 导航 —— 仅导航模式（首次实机用降额参数 nav2_params_low）
#   ⚠️ 08-17 起参数含 inflation_radius 0.30 修复（窄缝过不去）；全速版 nav2_params.yaml 仍是 0.55，切回前须先同步
#   ⚠️ 初始位姿纪律: 启动初期设偏可静止重设 1~2 次（08-25 实车验证有效）；导航运行中不要重设（多次设→map 重叠）；
#      每次设完先动一下确认收敛（见 retrospect/2026-08-17_nav2_initialpose_inflation_fix.md）
#   操作: rviz 出现后 2D Pose Estimate(P) 设初始位姿 → Navigation2 Goal(G) 发目标
#   注意: 设位姿前 planner/costmap 报 "map frame does not exist" 是正常等待噪音；
#         车静止时 AMCL 不发布 /amcl_pose 与粒子（update_min_d/a 阈值设计），动起来才有
source ~/Lin_workspace/r2_integration/install/setup.bash
# —— N97（地图在 ~/maps/ 部署副本）:
ros2 launch r2_bringup nav2.launch.py \
  map:=/home/lin/maps/map_0815_clean.yaml \
  params_file:=/home/lin/Lin_workspace/r2_integration/install/r2_bringup/share/r2_bringup/config/nav2_params_low.yaml \
  rviz:=true
# —— VM（分析副本地图，bag 目录内）:
ros2 launch r2_bringup nav2.launch.py \
  map:=/home/lin/Lin_workspace/r2_integration/bags/maps/d4/map_0815_clean.yaml \
  params_file:=/home/lin/Lin_workspace/r2_integration/install/r2_bringup/share/r2_bringup/config/nav2_params_low.yaml \
  rviz:=true

# 终端 8: FAST-LIO2 —— 仅 FAST-LIO 实验模式（08-24 实车验证通过；替代 KISS/EKF）
#   ⚠️ 完整部署/外参/验收/排障见 n97/fastlio2-n97-deploy.md §六；IMU 启动纪律同 R2（校准后才可起）
#   ⚠️ N97 编译 fast_lio_ws 必须 PATH=/usr/bin:$PATH colcon build（~/.local/bin/cmake 4.4 坑）；map_en 保持 false
cd ~/fast_lio_ws && source install/setup.bash
ros2 launch fast_lio mapping.launch.py config_file:=velodyne.yaml rviz:=false
# 里程计查看: ros2 topic echo /Odometry --field pose.pose（大消息话题勿用 hz，见 ros2-qos-dds.md）
# 录制对比: ros2 bag record /imu/data /velodyne_points /Odometry /path /tf
```

---

## 四、启动后验证基线（2026-08-02 实测，部分行已更新至 08-15；待下次实车刷新）

> 用途：启动后对着核各话题 hz 是否达标；长期用 [greenwave-monitor-deploy.md](n97/greenwave-monitor-deploy.md) 自动化监测（多话题 hz + 预期频率表，替代手动 `ros2 topic hz`）。

### 4.1 节点构成（N97 全套，随模式增减）

```
ekf_filter_node / g354_imu_node / kiss_icp_node(建图模式) / r2_chassis_node /
r2_teleop_keyboard / robot_state_publisher / static_transform_publisher(base_link→imu_link) /
velodyne_driver_node / velodyne_transform_node / rviz / rqt
（velodyne_laserscan_node 08-15 起停用：/scan 暂无消费者，Nav2 接入时恢复）
```

### 4.2 话题频率基线（实测）

| 话题 | 频率 | 备注 |
|:-----|:-----|:-----|
| /imu/data | ~100Hz（std 0.0025）✅ | G354，稳定 |
| /odometry/filtered | ~30Hz ✅ | EKF 融合输出（08-09 降频 50→30 缓解 CPU） |
| /odom_wheels | ~50Hz（std 0.002）✅ | 轮速里程计 |
| /velodyne_points | ~9.3~9.4Hz ✅（08-15 实测稳定） | 08-15 调优（organize_cloud=false + max_range 40m）后稳定，此前 7.7~8.5Hz |
| /kiss/odometry | ~9.5Hz ✅（08-11 实测，切 performance 治理器后） | 修复前 3.6Hz（CPU powersave 低频，隔帧处理） |
| /kiss/points 等 | visualize:=true 时发布 | 前缀 **/kiss/**（非 /kiss_icp/） |
| /Odometry（FAST-LIO） | 8Hz+（雷达 10Hz 帧率） | 08-24 实车验证；IMU Initial Done 后才发布 |

### 4.3 数据表现核对点（静止实测）

- EKF 姿态与 IMU 姿态几乎一致（四元数 0.0226/0.0283/0.0172/0.9992）→ 融合正确
- EKF position.z = 0.000000（08-09 two_d_mode 修复后）
- odom→base_link 单一发布者（chassis publish_tf:=false）✅

---

## 五、IMU 独立看姿态

```bash
ros2 run rviz2 rviz2   # Fixed Frame 填 imu_link
# Add → By display type → Imu（需已装 ros-humble-rviz-imu-plugin）→ Topic /imu/data → QoS Reliable
```

---

## 相关文件

- 交接总览：[07-handover.md](07-handover.md)｜入口导航：README「快速启动」（6 终端简版）
- 模式手册：[w1-operation.md](minimal-loop/w1-operation.md)（建图全流程）｜[w2-operation.md](minimal-loop/w2-operation.md)（Nav2 闭环）｜[fastlio2-n97-deploy.md](n97/fastlio2-n97-deploy.md)（FAST-LIO）
- 纪律与坑：[ros2-ops.md](ros2-ops.md)（启动纪律 §3）｜[ros2-qos-dds.md](ros2-qos-dds.md)（大消息验证）
