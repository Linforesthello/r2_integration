# Greenwave Monitor 部署手册（N97）

> 日期：2026-08-25
> 用途：R2 全栈话题自主化监测——多话题 hz + 预期频率管理 + Diagnostics 上报，替代手动 `ros2 topic hz` 逐条盯（2026-08-25 用户选定方案 B，背景见 [07-handover.md §六 待办](07-handover.md)）
> 执行机：N97（192.168.1.210）；关联：[relog-operation.md](minimal-loop2/relog-operation.md)（重录操作卡，录制时用本监测盯盘）
> 来源 = [官方仓库 README](https://github.com/NVIDIA-ISAAC-ROS/greenwave_monitor)（2026-08-25 WebSearch 核实）+ [Open Robotics Discourse 介绍帖](https://discourse.openrobotics.org/t/nvidias-greenwave-monitor-a-tool-for-high-performance-topic-monitoring-and-diagnostics/50477)；launch 参数名等细节标注「待 N97 以 clone 后 README 为准」

---

## 1. 是什么

- NVIDIA ISAAC 团队开源的 ROS2 话题监测节点：类 `ros2 topic hz` 的 C++ 高性能版（订阅任意话题，动态解析消息类型，提取 header 时间戳，无 header 用接收时间）
- 发布 `diagnostic_msgs/DiagnosticArray`（每秒）→ 可接 rqt_robot_monitor 等 Diagnostics 可视化
- ncurses 终端面板：实时显示各话题频率/latency/抖动/状态（OK / ERROR / STALE）
- 服务方式运行时管理：`/greenwave_monitor/set_expected_frequency`（设预期频率+容差）、`/greenwave_monitor/manage_topic`（增删话题）
- **无 Isaac ROS 依赖**，独立包；官方测试覆盖 Humble（Ubuntu 22.04）

## 2. N97 安装步骤

```bash
# 2.1 独立工作区（不混入 r2_integration——第三方工具与业务包隔离）
mkdir -p ~/greenwave_ws/src && cd ~/greenwave_ws/src
git clone https://github.com/NVIDIA-ISAAC-ROS/greenwave_monitor.git

# 2.2 编译（⚠️ 沿用 FAST-LIO 教训：PATH 前置 /usr/bin 绕过 ~/.local/bin/cmake 4.4 坑，
#     见 07-handover §五 08-24；greenwave 是 C++ 包，同坑预防）
source /opt/ros/humble/setup.bash
PATH=/usr/bin:$PATH colcon build --packages-up-to greenwave_monitor
# 预期：greenwave_monitor 与 greenwave_monitor_interfaces 两个包 build 成功，无报错
source install/setup.bash
```

## 3. 配置与启动

### 3.1 一键启动监测（终端独立跑）

```bash
ros2 launch greenwave_monitor hz.launch.py \
  gw_monitored_topics:='["/imu/data", "/odom_wheels", "/odometry/filtered", "/velodyne_points", "/scan", "/cmd_vel_smoothed", "/local_costmap/costmap_raw", "/global_costmap/costmap"]'
```

### 3.2 预期频率表（来自 2026-08-25 健康检查实测，见 [raw_data](raw_data/raw_imu_hz_ekf_update_rate_2026-08-25_1919.txt)）

> ⚠️ **关键经验（08-25 实测教训）：预期频率设「实测正常值」，不设标称值**。
> 例：IMU 标称 100Hz 但实测稳定 94Hz——设 100 则永久 ERROR（狼来了，报警信号贬值）；
> 设 94 则 94→OK，真掉链（50Hz/节点死）→ 红色/STALE。**预期值的作用是把"正常"定在实测上。**
> 同理 /cmd_vel_smoothed 无 nav 指令不发布，设预期会永久红——按需留 N/A。

| 话题 | 预期 Hz | 容差 | 实测（08-25） | 备注 |
|:---|:---|:---|:---|:---|
| /imu/data | 100 | ±10% | 93.8 | G354 标称 |
| /odom_wheels | 50 | ±5% | 50.00 | odom_publish_rate |
| /odometry/filtered | 30 | ±5% | 30.00 | ekf.yaml frequency |
| /velodyne_points | 9.5 | ±15% | 9.5~9.7 | 抖动 0.1~0.2s，容差放宽 |
| /scan | 10 | ±10% | 9.9 | |
| /cmd_vel_smoothed | 20 | ±50% | 无 nav 指令不发布 | **事件型，无指令时 STALE 属正常** |
| /local_costmap/costmap_raw | 2 | ±50% | 待重录实测 | publish 2.0Hz |
| /global_costmap/costmap | 2 | ±50% | 待重录实测 | publish 2.0Hz |

预期频率可在 launch 参数或运行时用服务设置：

```bash
ros2 service call /greenwave_monitor/set_expected_frequency greenwave_monitor_interfaces/srv/SetExpectedFrequency \
  "{topic_name: '/imu/data', expected_hz: 100.0, tolerance_percent: 10.0, clear_expected: false, add_topic_if_missing: true}"
```

> 参数名/服务字段以 N97 clone 后 `cat ~/greenwave_ws/src/greenwave_monitor/README.md` 为准（待验证标注）。

### 3.3 终端面板

```bash
ros2 run greenwave_monitor ncurses_dashboard
# 预期：ncurses 界面，每行一个话题：频率/latency/状态；掉链话题状态转 ERROR/STALE
```

## 4. 可视化（可选进阶）

```bash
sudo apt install ros-humble-rqt-robot-monitor
rqt --standalone RobotMonitor
```

> 注意：rqt_robot_monitor 默认订阅 `/diagnostics_agg`（需 diagnostic_aggregator 聚合）；greenwave 发布 `/diagnostics`。直接用法待 N97 验证（改订阅话题或加 aggregator），不阻塞终端面板方案。

## 5. 与重录衔接（核心用法）

重录（relog-operation.md）时新开一个终端跑 §3.1 监测：

- 录制全程盯 8 话题状态，**任一话题 ERROR/STALE 立即喊停录制排查**，杜绝"录完才发现掉链"
- 场景流程 ②③④⑤ 每步放好障碍后，确认 `/local_costmap/costmap_raw` 仍存活（防止成本图节点挂掉而不自知）
- 录完对照监测面板记录各话题平均 hz，与 §3.2 表核对后结束

## 6. 待 N97 验证项

- [ ] launch 参数确切名（`gw_monitored_topics` 拼写与格式）与预期频率参数名
- [ ] /diagnostics 话题名与 rqt_robot_monitor 订阅适配
- [ ] 大消息话题（/velodyne_points）订阅 QoS 是否兼容（reliable 发布方；hz 假阴性教训见 [ros2-qos-dds.md](ros2-qos-dds.md)）
- [ ] 无 nav 指令时 /cmd_vel_smoothed 是否长期 STALE 刷屏（预期行为确认）

## 7. 来源（2026-08-25 WebSearch 核实）

- [官方仓库 README](https://github.com/NVIDIA-ISAAC-ROS/greenwave_monitor) — 安装命令/参数/服务/dashboard 用法
- [Open Robotics Discourse 介绍帖](https://discourse.openrobotics.org/t/nvidias-greenwave-monitor-a-tool-for-high-performance-topic-monitoring-and-diagnostics/50477) — 设计动机与能力说明
- 未实测项已标注「待验证」；GitHub raw README 本机 WebFetch 被网络策略挡（2026-08-25），细节以 N97 clone 后 README 为准

## 8. VM 部署验证记录（2026-08-25）

- 部署机：VM（lin-virtual-machine，Ubuntu + ROS2 Humble）
- 结果：clone + `colcon build` 成功（cmake 3.22，无 N97 的 4.4 坑）；`ros2 run greenwave_monitor ncurses_dashboard --demo` 面板正常
- fixture 实测：demo 3 话题 OK —— /image_topic 30.00Hz/0.38ms、/imu_topic 99.99Hz/0.13ms、/string_topic 972.73Hz；19 话题列表 + Add/Remove + 状态栏正常
- 观察：未设预期频率的话题显示 N/A（不统计）——印证 §3.2 预期频率表是监测发光的必需配置
- 遗留：未实测 demo 报警转换（设错误预期频率 → ERROR → 恢复）；N97 真机部署待做
