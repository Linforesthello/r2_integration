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
│   ├── 01-plan.md                    五阶段集成方案总纲
│   ├── 02-deploy-checklist.md        N97 部署清单
│   ├── 02-progress.md                全局进度一览（各Phase完成度）
│   ├── 03-current_state.md           当前完成状态
│   ├── 07-handover.md                状态交接（新会话用）
│   │
│   ├── phase0/                       ← Phase 0 专题
│   │   ├── chassis_definition.md     底盘完整定义（映射/参数/公式）
│   │   ├── completion_report.md      Phase 0 完成记录
│   │   └── debug_log.md              踩坑调试日志
│   │
│   ├── phase1/                       ← Phase 1 专题
│   │   ├── g354-wiring.md            G354 IMU 接线/配置
│   │   └── ekf-verification.md       EKF 实车验证清单（测试方法+判合格标准）
│   │
│   └── retrospect/                   ← 事件记录（按日期排序）
│       ├── 2026-08-02_ekf_tf_fusion_fix.md    EKF/TF 融合排障全记录（7 问题）
│       ├── 2026-07-31_chassis_launch_fix.md   chassis.launch.py 路径修复
│       └── vlp16_slam_exploration.md          VLP-16 SLAM 方案探索
│
├── r2_bringup/                        ← ROS2 底盘控制包
│   ├── r2_bringup/chassis_node.py    核心节点
│   ├── launch/chassis.launch.py      底盘启动文件
│   ├── launch/ekf.launch.py          EKF 融合启动文件
│   ├── config/r2_params.yaml         实车标定参数
│   └── config/ekf.yaml               EKF 融合配置
│
├── g354_driver/                       ← ROS2 IMU 驱动包（包名 g354_imu_driver）
│   ├── g354_imu_driver/imu_node.py   核心节点（Mahony + ZUPT）
│   ├── launch/g354_rviz.launch.py    启动文件（rviz:=false 可只开节点）
│   ├── config/g354_imu.rviz          RViz2 配置
│   ├── doc/                           G354 专题文档
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
Phase 0 底盘 ROS2 + CAN 控制            ✅ 100% 完成
Phase 1 G354 IMU + EKF 融合            ⏳ 进行中（IMU 驱动完成，EKF 联调中）
Phase 2 3D LiDAR SLAM (VLP16+KISS-ICP)  ✅ 驱动 + 3D 里程计已跑通
Phase 3 VLP16 + Nav2 导航              ⏳
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
├──  LiDAR:    VLP-16 以太网直连（设备 IP 10.18.18.6）
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

# 2. 启动底盘（在终端 1 运行）
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch r2_bringup chassis.launch.py

# 3. 启动 IMU（在终端 2 运行）
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch g354_imu_driver g354_rviz.launch.py rviz:=false   # 有显示器可去掉 rviz:=false

# 4. 启动 EKF 融合（在终端 3 运行）
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch r2_bringup ekf.launch.py

# 观看融合里程计
ros2 topic echo /odometry/filtered
```

> 一键启动（需图形界面 + gnome-terminal）:
> `bash ~/Lin_workspace/r2_integration/scripts/r2_startup.sh`
>
> 注意: 本机 colcon 会把 console_script 装在 `bin/`（而非标准 `lib/<pkg>/`），
> `ros2 run` 无法找到入口脚本，请一律使用 `ros2 launch` 启动。

