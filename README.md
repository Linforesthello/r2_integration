# R2 全向轮底盘 · 外设集成

> 将 R2 从"串口键盘遥控"升级为"ROS2 自主导航 + 感知 + AI"的完整机器人系统。
>
> 代码在 `~/Lin_workspace/r2_integration/` 下，文档在 `doc/` 中按编号阅读。

---

## 文件树

```
r2_integration/
│
├── README.md                          ← 本文件，入口导航
│
├── doc/                               ← 文档（按阶段组织）
│   ├── standards.md                  文档标准 ← 先看这个
│   ├── 01-plan.md                    五阶段集成方案总纲
│   ├── 02-progress.md                全局进度一览（各Phase完成度）
│   ├── 03-current_state.md           当前完成状态（Phase 0 详细记录）
│   ├── 07-handover.md                状态交接（新会话用）
│   │
│   ├── phase0/                       ← Phase 0 专题
│   │   ├── chassis_definition.md     底盘完整定义（映射/参数/公式）
│   │   ├── completion_report.md      Phase 0 完成记录
│   │   └── debug_log.md              踩坑调试日志
│   │
│   └── phase1/                       ← Phase 1 专题（空，待填充）
│
├── r2_bringup/                        ← ROS2 底盘控制包
│   ├── r2_bringup/chassis_node.py    核心节点
│   ├── launch/chassis.launch.py      启动文件
│   └── config/r2_params.yaml         实车标定参数
│
└── scripts/                           ← 标定工具
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
状态交接:  07-handover.md
```

---

## 当前阶段

```
Phase 0 底盘 ROS2 + CAN 控制  ✅ 100% 完成
Phase 1 IMU + EKF 融合        ◇ 下一个
Phase 2 FAST-LIO2 SLAM        ◇
Phase 3 Nav2 导航              ◇
Phase 4 D435 + Jetson 视觉    ◇
Phase 5 系统集成               ◇
```

---

## 快速启动

```bash
# 1. CAN 总线
sudo ip link set can0 up type can bitrate 1000000

# 2. 启动底盘
source ~/Lin_workspace/r2_integration/r2_bringup/install/setup.bash
ros2 launch r2_bringup chassis.launch.py

# 3. 键盘控制
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```
