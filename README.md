# R2 全向轮底盘 · 外设集成

> 将 R2 从"串口键盘遥控"升级为"ROS2 自主导航 + 感知 + AI"的完整机器人系统。
>
---
> 代码在 `~/Lin_workspace/r2_integration/` 下，文档在 `doc/` 中按阶段组织。
>
> **部署环境**：开发在 VMware 虚拟机，实车部署在 **N97 Mini PC**（192.168.1.210，Ubuntu 22.04 + ROS2 Humble）。
> 两环境 ROS2 包一致，区别在于 CAN 硬件接口和串口设备路径。

---

## 文件树

```
r2_integration/
│
├── README.md                          ← 本文件，入口导航
│
├── doc/                               ← 文档（按阶段组织）
│   ├── standards.md                  文档标准 ← 先看这个
│   ├── obsidian-tags.md              Obsidian 标签体系习惯
│   ├── ros2-ops.md                   ROS/ROS2 操作规范（构建/启动/录包/分析）
│   ├── obsidian-sync.md              Obsidian 镜像同步规范（全局适用）
│   ├── 01-plan.md                    五阶段集成方案总纲
│   ├── minimal-loop/                  最小闭环计划（plan.md）+ W1操作手册（w1-operation.md）+ Nav2 bringup（nav2-bringup.md）+ 审计数据
│   ├── 02-deploy-checklist.md        N97 部署清单
│   ├── 02-progress.md                全局进度一览（各Phase完成度）
│   ├── project_status.md              全项目现状总结（08-06）
│   ├── project_landscape.md            项目全景（R2在更大系统中的位置）
│   ├── 03-current_state.md           当前完成状态
│   ├── 07-handover.md                状态交接（新会话用）
│   │
│   ├── phase0/                       ← Phase 0 专题
│   │   ├── chassis_definition.md     底盘完整定义（映射/参数/公式）
│   │   ├── sensor-mount.md            传感器安装定义（IMU/雷达位置朝向）
│   │   ├── completion_report.md      Phase 0 完成记录
│   │   └── debug_log.md              踩坑调试日志
│   │
│   ├── phase1/                       ← Phase 1 专题
│   │   ├── g354-wiring.md            G354 IMU 接线/配置
│   │   ├── ekf-verification.md       EKF 实车验证清单（测试方法+判合格标准）
│   │   ├── ekf-yaw-plan.md           EKF yaw 融合预案（08-12 方案①已实施验证）
│   │   └── 2026-08-04_ekf-verification-result.md  EKF 验证结果记录
│   │
│   └── retrospect/                   ← 事件记录（按日期排序）
│       ├── 2026-08-15_nav2_bringup.md             Nav2 首闭环跑通（D4 验证 + 降额实机 + 7 条排障 + 盲区/footprint 修复）
│       ├── 2026-08-15_kiss_drift_170058.md          KISS 长录整程漂移留档（旋转+空窗→航向漂163°，双录对比）
│       ├── 2026-08-15_r2_sensors_extract.md       velodyne 抽包 r2_sensors + g354 marker 补全（全流程/坑/决策/经验）
│       ├── 2026-08-15_clean_bag_rerecord.md       干净 bag 重录 + 人形块过滤（清洗版导航图 map_0815_clean）
│       ├── 2026-08-15_velodyne_perf_tuning.md     VLP-16 链路性能调优（供电不足根因 + organize_cloud/max_range）
│       ├── 2026-08-15_vscode_intellisense_include_fix.md  VS Code 1696 修复（Humble include 双嵌套布局）
│       ├── 2026-08-14_vm_vlp16_dds_fix.md         VM 单机 DDS 根因修复（bashrc 跨机配置 + daemon 缓存）
│       ├── 2026-08-13_layer_map_3d2d.md           分层3D→2D导航层生成（多层对比+选层+seg3剔除）
│       ├── 2026-08-13_map_chain_investigation.md 建图链路排查（重影根因+z_min修正+time字段之谜）
│       ├── 2026-08-11_kiss_frame_rate_fix.md      KISS 帧率修复（3.6→9.5Hz，重影根因）
│       ├── 2026-08-11_r2_bringup_code_review.md   r2_bringup 代码审查
│       ├── 2026-08-10_vocalinux语音输入.md        Vocalinux 本地语音输入调试总结
│       ├── 2026-08-09_ekf_z_drift_fix.md          EKF z 漂移修复（two_d_mode 钳位）
│       ├── 2026-08-09_map_double_ghost.md         地图重影排查
│       ├── 2026-08-06_git_ops_lessons.md          Git 操作教训（reset 误伤/Co-Authored-By 规则）
│       ├── 2026-08-05_chassis_ekf_debug.md        底盘里程计修复+EKF过程噪声225值矩阵排障
│       ├── 2026-08-05_imu_covariance_ekf_nan.md   IMU 协方差病态→EKF NaN 排障
│       ├── 2026-08-05_n97_remote_desktop.md       N97 远程桌面三方案排障（NoMachine/RealVNC/TigerVNC）
│       ├── 2026-08-03_r2_repo_repair.md           r2_integration 仓库修复全记录
│       ├── 2026-08-02_vlp16_switch_network.md     VLP-16 交换机接入方案（+vlp16-switch-network-topology.png）
│       ├── 2026-08-02_ekf_tf_fusion_fix.md        EKF/TF 融合排障全记录（7 问题）
│       ├── 2026-07-31_chassis_launch_fix.md       chassis.launch.py 路径修复
│       ├── 2026-07-31_claude_md_import_setup.md   流程模式：Claude 优先读到文档
│       ├── 2026-07-31_teleop_keyboard_fix.md      键盘控制修复全记录（WASD 遥控）
│       ├── 2026-07-31_workspace_check_fix.md      r2_integration 工作区检查与修复
│       └── vlp16_slam_exploration.md              VLP-16 SLAM 方案探索
│
├── r2_bringup/                        ← ROS2 底盘控制包
│   ├── r2_bringup/chassis_node.py    核心节点
│   ├── launch/chassis.launch.py      底盘启动文件
│   ├── launch/ekf.launch.py          EKF 融合启动文件
│   ├── launch/nav2.launch.py         Nav2 启动文件（map_server+amcl+MPPI 全栈）
│   ├── config/r2_params.yaml         实车标定参数
│   ├── config/ekf.yaml               EKF 融合配置
│   ├── config/nav2_params.yaml       Nav2 参数（全速版）
│   ├── config/nav2_params_low.yaml   Nav2 参数（降额版，首次实机用）
│   ├── config/nav2.rviz              Nav2 RViz 配置
│   └── config/dds/                   DDS 跨机配置（fastdds_peer_n97/wellknown + README）
│
├── r2_sensors/                        ← ROS2 传感器外设包（包名 r2_sensors，08-15 从 r2_bringup 抽出）
│   ├── README.md                     包说明（话题/参数/启动）
│   ├── launch/velodyne.launch.py     VLP-16 雷达启动（driver+transform+laserscan+TF，两机通用）
│   └── config/r2.urdf                base_link→velodyne TF（z=0.56m，08-06 定案）
│
├── g354_driver/                       ← ROS2 IMU 驱动包（包名 g354_imu_driver）
│   ├── README.md                     包说明（话题/参数/启动）
│   ├── g354_imu_driver/imu_node.py   核心节点（Mahony + ZUPT）
│   ├── launch/g354_rviz.launch.py    启动文件（rviz:=false 可只开节点）
│   ├── config/g354_imu.rviz          RViz2 配置
│   ├── doc/                           G354 专题文档（completion-report/debug-log/observation-methods/test-flow）
│   └── scripts/                       测试脚本
│
└── scripts/                           ← 标定工具
    ├── r2_startup.sh                 CAN + 底盘 + IMU + EKF 一键启动
    ├── measure_r2_ticks.py           编码器 ticks/圈 测量
    ├── map_chassis.py                CAN ID → 物理位置映射
    └── calibrate_direction.py        运动方向标定（8组测试）
```

---

## 阅读顺序

```
先看规范:  standards.md — 了解文档结构和管理方式
首次阅读:  01-plan.md → 02-progress.md → 03-current_state.md
技术参考:  phase0/chassis_definition.md
调参回溯:  phase0/debug_log.md
踩坑记录:  retrospect/（修复与探索事件记录，按日期排序）
状态交接:  07-handover.md
```

---

## 当前阶段

```
Phase 0 底盘 ROS2 + CAN 控制            ✅ 100% 完成（含 08-06 里程计修复）
Phase 1 G354 IMU + EKF 融合             ✅ 95% 实车验证完成（08-06）；yaw 方案①验证通过（08-12）
Phase 2 3D LiDAR SLAM (VLP16+KISS-ICP)  ✅ 驱动 + 3D 里程计已跑通
Phase 3 VLP16 + Nav2 导航              ⏳ 10%（08-15 首闭环跑通，降额参数；盲区/footprint 修复待复测）
Phase 4 D435 + Jetson 视觉             ⏳
Phase 5 气动 + 异常处理 + Robocon 编排   ⏳
```

（详细状态见 `doc/03-current_state.md`）

---

## 部署环境

```
开发时（VMware 虚拟机）
├──  CAN 总线: slcan 转串口 (USB-CAN 适配器) → CanCmd 工具配置
├──  IMU/G354: 需 USB 透传或模拟
└──  LiDAR:    无硬件直连，代码准备

部署时（N97 Mini PC / 192.168.1.210）
├──  CAN 总线: slcan 转串口 (USB-CAN 适配器) → CanCmd 工具配置
├──  IMU/G354: ttyACM1（JLink OB Mini 串口直连）
├──  LiDAR:    VLP-16 经交换机转接（设备 IP 10.18.18.6）
├──  视觉:     D435 USB 直连（可选 Jetson 协同）
└──  OS:       Ubuntu 22.04 + ROS2 Humble
```

---

## 快速启动

```bash
# 0. 工作区编译
cd ~/Lin_workspace/r2_integration
source /opt/ros/humble/setup.bash
colcon build

# 1. CAN 总线（使用 CanCmd 工具）
#    从主页面运行 CanCmd → 选择串口设备 → 选择波特率(1M) → 确认
python3 ~/Lin_workspace/command/can_command.py

# 2. 启动底盘（在终端 1 运行；EKF 场景必须带 publish_tf:=false 让 EKF 统一发 TF，独立使用可不带）
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch r2_bringup chassis.launch.py publish_tf:=false

# 3. 启动 IMU（在终端 2 运行；保持静止 3s 等校准完成）
#    mount_axes:=y_front_x_left_z_down 是 R2 的 G354 出厂轴定义（x左/y前/z下），见 doc/phase0/sensor-mount.md
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch g354_imu_driver g354_rviz.launch.py rviz:=false serial_port:=/dev/ttyACM1 mount_axes:=y_front_x_left_z_down

# 4. 启动 EKF 融合（在终端 3 运行；⚠️ 必须在 IMU 校准完成后启动，重启 IMU 须同时重启 EKF）
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch r2_bringup ekf.launch.py

# 5. 键盘遥控（终端 4；08-11 P3 setup.cfg 修复后 ros2 run 可直启）
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 run r2_bringup teleop_keyboard

# 6. Nav2 自主导航（终端 5，08-15 起；KISS 不启动；首次实机用降额参数）
#    启动后 rviz 里先 2D Pose Estimate(P) 设初始位姿 → Navigation2 Goal(G) 发目标
#    ⚠️ 设位姿前 planner 报 "map frame does not exist" 是正常等待噪音；车静止时 AMCL 不发布粒子/位姿
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch r2_bringup nav2.launch.py \
  map:=/home/lin/maps/map_0815_clean.yaml \
  params_file:=~/Lin_workspace/r2_integration/install/r2_bringup/share/r2_bringup/config/nav2_params_low.yaml \
  rviz:=true

# 观看融合里程计
ros2 topic echo /odometry/filtered
```

> 一键启动（需图形界面 + gnome-terminal）:
> `bash ~/Lin_workspace/r2_integration/scripts/r2_startup.sh`
>
> ⚠️ **建图/导航完整启动**（performance governor → CAN → 雷达 → KISS-ICP → 底盘 → IMU → EKF → 遥控，
> 含 N97 跨机 DDS 的 FASTRTPS 环境变量）见 [w1-operation.md §1.1](doc/minimal-loop/w1-operation.md)。
>
> 注: console_script 入口经 08-11 setup.cfg 修复后已可 `ros2 run` 直启（teleop_keyboard 等）。

