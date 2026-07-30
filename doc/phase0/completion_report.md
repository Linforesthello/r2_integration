# Phase 0 完成记录 — R2 底盘 CAN 控制

> 完成日期: 2026-07-29
> 目标: ROS2 /cmd_vel → CAN → R2 四全向轮底盘运动

---

## 一、实车参数标定

### 物理参数

| 参数 | 值 | 来源 |
|:-----|:----|:------|
| 车体半对角线 R | 0.33 m | 用户实测 |
| 轮径 | 0.152 m | 用户实测 |
| 编码器 ticks/圈 | 4241 | 实测均值 |

### ticks/圈 实测值

| 电机 | CAN ID | ticks/圈 | 转速 @speed=10 |
|:-----|:-------|:--------:|:--------------:|
| FL (左前) | 0x123 | 4232 | 13.3 RPM |
| FR (右前) | 0x126 | 4222 | 13.3 RPM |
| RL (左后) | 0x124 | 4279 | 13.2 RPM |
| RR (右后) | 0x125 | 4231 | 13.3 RPM |
| **平均** | | **4241** | **13.3 RPM** |

4 轮一致性 CV < 1%，说明编码器硬件一致、标定可靠。

### 速度限幅

| 轴 | 限速值 | 单位 |
|:---|:------|:-----|
| vx (前进) | 0.5 | m/s |
| vy (侧移) | 0.3 | m/s |
| ω (旋转) | 0.8 | rad/s |

---

## 二、产出的文件

```
~/Lin_workspace/r2_integration/
├── doc/01-plan.md                      # 五阶段集成方案
├── r2_bringup/                        # ROS2 包
│   ├── package.xml
│   ├── setup.py
│   ├── r2_bringup/
│   │   ├── __init__.py
│   │   └── chassis_node.py            # 核心：/cmd_vel → CAN + /odom_wheels
│   ├── launch/
│   │   └── chassis.launch.py
│   └── config/
│       └── r2_params.yaml             # 实车参数配置
└── scripts/
    └── measure_r2_ticks.py            # 编码器 ticks/圈 测量工具
```

### chassis_node.py 功能清单

| 功能 | 说明 |
|:-----|:------|
| 运动学逆解 | vx/vy/ω → 4 轮逻辑速度 (从 R2.py 移植) |
| 运动学正解 | 4 轮速度 → vx/vy/ω |
| CAN 命令发送 | 订阅 /cmd_vel → CAN 帧 (0x123~0x126) |
| CAN 状态接收 | 后台线程收 0x323~0x326 状态帧 |
| 里程计积分 | 轮速 → 位置 → /odom_wheels + TF |
| 超时保护 | 0.5s 无 cmd_vel 自动停止 |
| 堵转检测 | 1Hz 诊断 (MOTOR_LOST / STALL) |

---

## 三、运动学公式

```
逆解 (车体速度 → 4 轮速度):

  R = 0.33 (半对角线长)
  INV_SQRT2 = 1/√2

  FL = ( vx + vy) * INV_SQRT2 - R * ω
  FR = ( vx - vy) * INV_SQRT2 - R * ω
  RL = (-vx + vy) * INV_SQRT2 - R * ω
  RR = (-vx - vy) * INV_SQRT2 - R * ω

正解 (4 轮速度 → 车体速度):

  vx    = (FL + FR - RL - RR) / (4 * INV_SQRT2)
  vy    = (FL - FR + RL - RR) / (4 * INV_SQRT2)
  ω     = -(FL + FR + RL + RR) / (4 * R)
```

---

## 四、下一步 (Phase 1 待启动)

- [ ] `robot_localization` EKF 融合 IMU + 轮速里程计
- [ ] G354 IMU 驱动接入
- [ ] 对比 纯轮速 odom vs EKF 精度

## 五、已知问题

1. 里程计 `MAX_WHEEL_OMEGA = 31.4` 是估算值，需要做速度标定才能得到准确的 m/s 数值
2. 4 个电机的 PID 参数是否一致未经确认（会影响直线行驶精度）
