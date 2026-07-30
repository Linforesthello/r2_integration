# R2 全向轮底盘 · 外设集成与系统闭环

> 将 R2 从"串口键盘遥控"升级为"ROS2 自主导航 + 感知 + AI决策"的完整机器人系统。
>
> **定位**：基于你现有资产（G354 驱动、VLP16+KISS-ICP、IMU-odom 融合、视觉检测、CAN 协议）的系统集成实施方案。
>
> **范围**：只覆盖 NUC/Jetson 侧的 ROS2 集成，不涉及 STM32 固件修改（固件已定型）。

---

## 目录

- [第一章 底盘定义](#第一章-底盘定义)
- [第二章 现有资产全景图](#第二章-现有资产全景图)
- [第三章 系统架构总览](#第三章-系统架构总览)
- [第四章 集成路线图总览](#第四章-集成路线图总览)
- [第五章 Phase 0：底盘 ROS2 + CAN 控制](#第五章-phase-0底盘-ros2--can-控制)
- [第六章 Phase 1：IMU + 里程计 EKF 融合](#第六章-phase-1imu--里程计-ekf-融合)
- [第七章 Phase 2：MID70 + G354 → FAST-LIO2 SLAM](#第七章-phase-2mid70--g354--fast-lio2-slam)
- [第八章 Phase 3：VLP16 + Nav2 导航](#第八章-phase-3vlp16--nav2-导航)
- [第九章 Phase 4：D435 + Jetson 视觉 AI](#第九章-phase-4d435--jetson-视觉-ai)
- [第十章 Phase 5：系统集成与硬化](#第十章-phase-5系统集成与硬化)
- [附录](#附录)

---

## 第一章 底盘定义

### 1.1 R2 是什么

| 属性 | 值 |
|:-----|:----|
| **构型** | 四全向轮底盘（区别于 R1 的四舵轮底盘） |
| **电机数** | 4 个（每轮一个，无转向电机） |
| **CAN 命令 ID** | 0x123 (FL), 0x124 (FR), 0x125 (RL), 0x126 (RR) |
| **CAN 状态 ID** | 0x323 (FL), 0x324 (FR), 0x325 (RL), 0x326 (RR) |
| **车体布置** | 正方形，轮轴指向中心，90° 辊子全向轮 |
| **运动学模型** | 四全向轮标准模型（见 1.2） |
| **固件** | `3_MCLM_t2` — PID 闭环、CAN 状态上报、堵转保护（已定型不改） |

### 1.2 运动学公式

已由 `control/R2.py` 实测验证：

```
逆解（车体速度 → 4 轮速度）:

    已知参数:
      R = 车体中心到轮子的半对角线长 (m)
      INV_SQRT2 = 1/√2

    FL = ( vx + vy) · INV_SQRT2 - R · ω
    FR = ( vx - vy) · INV_SQRT2 - R · ω
    RL = (-vx + vy) · INV_SQRT2 - R · ω
    RR = (-vx - vy) · INV_SQRT2 - R · ω

    其中 vx(右为正), vy(前为正), ω(逆时针为正)

正解（4 轮速度 → 车体速度）:

    逆解公式的代数反推（见 Phase 0 代码）
```

### 1.3 CAN 协议

命令帧（NUC → MCLM，8 字节）：

| Byte | 字段 | 类型 | 说明 |
|:----:|:-----|:----:|------|
| 0 | cmd | uint8 | `0x11` = SET_SPEED, `0x08` = STOP |
| 1 | speed | int8 | -100~+100 |
| 2~7 | reserved | — | 填充 `0x00` |

状态帧（MCLM → NUC，每 50ms 主动上报，8 字节）：

| Byte | 字段 | 类型 | 说明 |
|:----:|:-----|:----:|------|
| 0~1 | current_speed | int16 LE | 当前实际速度 |
| 2~3 | accumulated_ticks | uint16 LE | 编码器累计脉冲 |
| 4~5 | pwm_output | int16 LE | PWM 输出值 |
| 6 | target_speed | int8 | 目标速度 |
| 7 | flags | uint8 | bit0=STALL, bit1=SATURATED |

---

## 第二章 现有资产全景图

> 在开始任何工作前，先搞清楚"已经有什么"和"缺什么"。这里分成三个层次：**可复用资产**、**待集成资产**、**尚未涉及领域**。

### 2.1 可复用资产（可直接用，不需要再开发）

```
层 1 — 嵌入式固件（STM32 侧，已定型）
├── 3_MCLM_t2           — 电机 PID 闭环、CAN 状态上报、堵转保护
├── 3_Diacifa_t1        — 气动系统（气泵+电磁阀），CAN ID 0x141/0x341
├── 3_SteeringArm_t1    — 舵机机械臂（如 R2 需要）
└── 5_ChassisController_t1 — UART↔CAN 网关（当前未用于 R2，架构参考）

层 2 — ROS2 驱动（Linux 侧，已完成）
├── g354_test/          — G354 IMU 完整 ROS2 驱动
│   ├── imu_node.py     — 串口解析 + 互补滤波 + /imu/data 发布
│   ├── test_g354.py    — 原始数据解析验证
│   ├── launch/         — 一键启动
│   └── config/         — Rviz 可视化配置
│
├── vlp16_slam_ws/      — VLP16 + KISS-ICP SLAM
│   └── install/kiss_icp/ — 已编译通过
│
├── imu_odom_ws/        — IMU+里程计融合节点
│   └── imu_odometry_node.py — 订阅 IMU → /odom + TF
│
└── librealsense/       — RealSense SDK 源码编译

层 3 — 应用工具（Python 脚本，已完成）
├── control/R2.py       — R2 键盘遥控 + 全向轮运动学
├── command/can_command.py — CAN 命令工具
├── command/chassis_control.py — 底盘控制脚本
└── command/dashboard.py — 状态面板

层 4 — 视觉检测
└── vision/good/dynamic_ball_tracker_node.py — HSV 球体检测 + 3D 坐标
```

### 2.2 待集成资产（已部分完成，需要接入系统）

| 资产 | 已做到 | 还缺什么 |
|:-----|:-------|:---------|
| G354 驱动 | 独立的 ROS2 驱动，发布 `/imu/data` | 未接入 FAST-LIO2，未接入 EKF |
| IMU-odom 节点 | 简单积分模型（yaw=∫gyro, x=∫v·cos(yaw)) | 不是正式 EKF，未用加速度计修正 |
| VLP16 + KISS-ICP | 已编译，配置文件就绪 | 未实车测试（PoE 网络配置） |
| R2 底盘控制 | ✅ **ROS2 + CAN 已完成** | 运动学校准、方向标定、里程计均通过 |
| 视觉球体检测 | 独立运行，输出 3D 坐标 | 未接到导航/控制上 |
| D435 | SDK 编译 | 未装 ROS2 驱动 |
| MID70 | 物理设备就位 | 未装 livox_ros_driver2 |
| Jetson Nano | YOLO 部署经验 | 未配 ROS2，未与 NUC 通信 |

### 2.3 尚未涉及领域

- FAST-LIO2 SLAM（MID70 + IMU 紧耦合）— 核心出活点
- `robot_localization` EKF 正式配置
- Nav2 导航堆栈的完整部署
- NUC ↔ Jetson 跨版本 ROS2 通信
- 气动系统从 ROS2 层控制
- 行为树/状态机任务编排

### 2.4 差距总结

```
当前状态：
  传感器驱动 ◇◇◇◇◇ 独立运行，不互通
  底盘控制   ◆◆◆◆◆ ✅ ROS2 + CAN 已跑通
  SLAM       ◇◇◇◇◇ 部分编译，未实车
  导航       ◇◇◇◇◇ 未开始
  视觉 AI    ◇◇◇◇◇ 独立运行，未接入控制

目标状态：
  传感器驱动 ←→ EKF ←→ SLAM ←→ Nav2 ←→ 底盘 CAN ←→ 电机
                                      ↑
                                   视觉 AI (Jetson)
```

**核心矛盾**：你已有大量独立运行的模块，缺的不是"开发"而是"连线"。

---

## 第三章 系统架构总览

### 3.1 硬件拓扑

```
                        NUC N100 (ROS2 Humble)
  ┌──────────────────────────────────────────────────────────────────┐
  │                                                                  │
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
  │  │ G354 IMU │  │ MID70    │  │ VLP16    │  │ D435i            │ │
  │  │ USB串口   │  │ USB 3.0  │  │ 以太网    │  │ USB 3.0         │ │
  │  │ /imu/data│  │ /livox/  │  │ /velodyne│  │ /camera/color+   │ │
  │  │         │  │ lidar    │  │ /points  │  │ depth            │ │
  │  └────┬────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘ │
  │       │            │             │                   │          │
  │       └─────┬──────┴──────┬──────┘                   │          │
  │             │             │                          │          │
  │       ┌─────▼─────┐  ┌───▼────┐              ┌──────▼──────┐   │
  │       │ EKF 融合  │  │ SLAM   │              │ 视觉预处理  │   │
  │       │ robot_    │  │ FAST-  │              │ (压缩转发)   │   │
  │       │localization│  │ LIO2   │              │             │   │
  │       └─────┬─────┘  └───┬────┘              └──────┬──────┘   │
  │             │             │                          │          │
  │             └──────┬──────┘                          │          │
  │                    │                                 │          │
  │              ┌─────▼──────┐                          │          │
  │              │    Nav2    │←─── /detections ─────────┘          │
  │              │  导航规划  │                                     │
  │              └─────┬──────┘                                     │
  │                    │ /cmd_vel                                    │
  │              ┌─────▼──────┐                                     │
  │              │chassis_can │                                     │
  │              │ _node.py   │  ←── ROS2 → CAN 桥                  │
  │              │(运动学逆解) │                                     │
  │              └─────┬──────┘                                     │
  └────────────────────┼────────────────────────────────────────────┘
                       │ USB
                  ┌────┴─────┐
                  │ CANable  │ 1Mbps
                  └────┬─────┘
                       │ CAN Bus (0x123~0x126)
            ┌──────────┼──────────┐
            ▼          ▼          ▼
       MCLM #1    MCLM #2    MCLM #3/4
       (FL 0x123) (FR 0x124) (RL 0x125 / RR 0x126)

    Jetson Nano B01 (ROS2 Foxy)
  ┌────────────────────────────────────┐
  │  ┌──────────────────────────────┐  │
  │  │ YOLO / TensorRT 推理         │  │
  │  │ ← /camera/color (from NUC)  │  │
  │  │ → /detections (to NUC)      │  │
  │  └──────────────────────────────┘  │
  │  注意: Foxy ≠ Humble，跨版本 DDS  │
  └────────────────────────────────────┘
```

### 3.2 数据流设计

```
流向 A：运动控制（实时性要求最高）
  ROS2 /cmd_vel
    → chassis_can_node (运动学逆解)
      → CAN Bus (命令帧 0x123~0x126)
        → MCLM_t2 (PID 100Hz)
          → 电机 → 编码器
            → CAN Bus (状态帧 0x323~0x326)
              → chassis_can_node (正解 → /odom_wheels)

流向 B：状态估计（融合 IMU + 轮速）
  /odom_wheels + /imu/data
    → robot_localization EKF
      → /odometry/filtered

流向 C：SLAM 建图（LiDAR + IMU）
  /livox/lidar + /imu/data
    → FAST-LIO2
      → 三维点云地图 + /Odometry

流向 D：导航规划
  /odometry/filtered + 地图
    → Nav2
      → /cmd_vel (闭环回流向 A)

流向 E：视觉 AI（非实时，事件驱动）
  D435 RGB → NUC → /camera/color/compressed → Jetson
    → YOLO TensorRT → /detections → NUC
      → 目标 3D 坐标 → Nav2 goal → 流向 D → 流向 A
```

### 3.3 关键设计决策

| 决策 | 选择 | 理由 |
|:-----|:-----|:------|
| IMU 分配 | G354 → FAST-LIO2 + EKF；D435i IMU → 视觉 VIO（可选） | G354 精度高，做主要融合；D435i 的 IMU 只是辅助 |
| CAN 还是串口 | CAN（通过 CANable） | MCLM 固件用 CAN，串口是旧方案 |
| R2 用 ChassisController 吗 | **不用**。NUC 直连 CAN | ChassisController 是为 R1 舵轮设计的网关。R2 全向轮运动学简单，NUC 直接算更高效 |
| Jetson 角色 | **纯 AI 推理协处理器**，不参与控制环路 | 控制环路要求实时性，不能经过 Jetson |
| ROS2 跨版本 | NUC Humble ↔ Jetson Foxy 通过 DDS | 物理上同一网段，DDS 自动发现 |

---

## 第四章 集成路线图总览

### 4.1 Phase 依赖关系

```
Phase 0: 底盘 CAN 控制 ──────────────── 前提，所有 Phase 的实车测试基础
       │
       ├──→ Phase 1: IMU+odom EKF ──→ Phase 3: Nav2 导航
       │                                    ↑
       └──→ Phase 2: FAST-LIO2 SLAM ───────┘
                │
                └──→ Phase 4: D435+Jetson ──→ Phase 5: 系统集成

可并行：
  Phase 1 (EKF 配置，纯软件) 和 Phase 2 (FAST-LIO2 编译) 可同时进行
  VLP16 网络配置 (Phase 3 的一部分) 可提早开始
  Jetson 环境搭建 (Phase 4 的一部分) 可提早开始
```

### 4.2 每个 Phase 的定位

| Phase | 定位 | 难度 | 依赖 | 实车可测 |
|:-----|:-----|:----:|:----:|:--------:|
| **0** | **基石** — ROS2 + CAN 控制 ✅ | ✅ 已完成 | 无 | ✅ 实车验证通过 |
| **1** | **精度** — 让里程计不漂 | ⭐⭐ | Phase 0 | ✅ 需要车动 |
| **2** | **出活** — SLAM 建图，核心能力 | ⭐⭐⭐⭐ | Phase 0+1 | ✅ 需要车动 |
| **3** | **自主** — 导航到目标点 | ⭐⭐⭐ | Phase 1+2 | ✅ 需要车动 |
| **4** | **感知** — AI 视觉接入 | ⭐⭐⭐ | Phase 0 | ✅ 静态可测 |
| **5** | **可靠** — 异常处理+编排 | ⭐⭐ | 全部 | ✅ 需要全系统 |

### 4.3 时序建议（并行策略）

```
时间线         Phase 0     Phase 1     Phase 2     Phase 3     Phase 4     Phase 5
─────────────────────────────────────────────────────────────────────────────
第1~3天        ████████     ← 已完成
第4~7天        ████████    ████████
第8~14天                  ████████   ████████    [VLP16网配]
第15~21天                              ████████   ████████
第22~28天                                          ████████   ████████   [Jetson搭环]
第29~35天                                                     ████████   [异常处理]
第36~42天                                                                ████████
```

**关键并行路径**：
- VLP16 网络配置（Phase 3 的步骤 3.1）**不受任何 Phase 依赖**，第 1 天就可以开始搞
- Jetson 的 ROS2 环境搭建（Phase 4 的步骤 4.2）也**不受其他 Phase 依赖**，可以在等 FAST-LIO2 编译时抽空做
- Phase 1（EKF 配置）和 Phase 2（FAST-LIO2 编译）**互不依赖**，可以同时做

### 4.4 风险预警

| 风险 | 发生在 | 概率 | 影响 | 缓解措施 |
|:-----|:-------|:----:|:----:|:---------|
| VLP16 网络不通（PoE/静态IP） | Phase 3 | 🔴 高 | 卡住 | 提前开始网络配置，准备好 PoE 交换机/注入器 |
| FAST-LIO2 编译依赖冲突（PCL/Eigen 版本） | Phase 2 | 🟡 中 | 1~3天 | 先编译 livox_ros_driver2，确认 ROS2 Humble 环境正常 |
| G354 IMU 驱动与 FAST-LIO2 的 IMU topic 不匹配 | Phase 2 | 🟡 中 | 1天 | 通过 remap 或修改 laserMapping.cpp |
| Jetson ROS2 Foxy 与 NUC Humble DDS 通信失败 | Phase 4 | 🟡 中 | 1~2天 | 先用 `ros2 topic pub/test` 跨版本验证 |
| D435 USB 带宽不足（与 MID70 抢 USB） | Phase 4 | 🟢 低 | — | D435 用 USB3，MID70 也用 USB3，N100 通常有多个 USB3 口 |
| 全向轮里程计标定不准（R 值、ticks/rev） | Phase 0 | 🟢 低 | 半天 | 用卷尺实测，走直线验证后校准 |

---

## 第五章 Phase 0：底盘 ROS2 + CAN 控制（✅ 已完成）

### 5.1 定位

**这是所有工作的前提**。没有 Phase 0，后面每个 Phase 都只能在"发仿真 topic"层面验证，没法让 R2 真正动起来验证。

### 5.2 完成状态

```
当前状态: → 目标状态 ✅
  control/R2.py 串口键盘遥控
  → R2 底盘 ROS2 + CAN 控制已跑通
  → /cmd_vel → CAN → 4 轮运动正常
  → /odom_wheels + TF 已发布
  → 运动学正解/逆解 + 坐标变换已校准
```

**核心产出：**
- `r2_bringup/` ROS2 包（chassis_node + launch + config）
- 标定脚本（measure_r2_ticks / map_chassis / calibrate_direction）
- 完整踩坑记录见 [[当前项目文档/R2_Integration/phase0_debug_log.md]]

### 5.3 步骤总览（已执行完毕，留存参考）

以下步骤已按顺序执行完成，供后续复现或重新搭建时参考：

#### 0.1 确认 CAN 总线通信（0.5 天）

```bash
# 启动 CAN
sudo ip link set can0 up type can bitrate 1000000

# 验证状态帧（应有 4 路 0x323~0x326，每 50ms 一帧）
candump can0

# 逐一验证每个电机
## 测试 0x123 (FL)
cansend can0 123#113C000000000000  # speed=60
cansend can0 123#1100000000000000  # stop
## 同样测 0x124 (FR)、0x125 (RL)、0x126 (RR)
```

**风险点**：确认 wheel 安装方向与运动学公式的符号一致。用 `cansend` 单独发正速度，看轮子实际转向。

#### 0.2 创建 R2 专用 CAN 控制包（0.5 天）

```
r2_bringup/
├── r2_bringup/
│   ├── chassis_node.py    # /cmd_vel → CAN + 状态帧 → /odom_wheels
│   └── __init__.py
├── launch/
│   ├── chassis.launch.py  # CAN 启动 + 底盘节点
│   └── r2_bringup.launch.py  # 全系统启动入口
├── config/
│   ├── can_params.yaml    # CAN 接口参数
│   └── r2_params.yaml     # R2 物理参数（R, ticks/rev, 轮径...）
├── setup.py
└── package.xml
```

#### 0.3 核心代码：`chassis_node.py` 的运动学部分

从你的 `control/R2.py` 移植运动学公式（已验证正确），改为 CAN 输出：

```python
# 文件: r2_bringup/r2_bringup/chassis_node.py

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import math
import can

INV_SQRT2 = 1.0 / math.sqrt(2)
R2_MOTOR_IDS = [0x123, 0x124, 0x125, 0x126]  # FL, FR, RL, RR

class R2ChassisNode(Node):
    def __init__(self):
        super().__init__('r2_chassis_node')
        
        # 参数
        self.declare_parameter('wheel_half_diagonal', 0.15)  # R (m)
        self.declare_parameter('can_channel', 'can0')
        self.R = self.get_parameter('wheel_half_diagonal').value
        
        # CAN 接口
        self.can_bus = can.interface.Bus(
            channel=self.get_parameter('can_channel').value,
            bustype='socketcan')
        
        # 订阅 /cmd_vel
        self.create_subscription(Twist, '/cmd_vel', self.cmd_callback, 10)
        
        # 发布 /odom_wheels（纯轮速里程计）
        self.odom_pub = self.create_publisher(Odometry, '/odom_wheels', 10)
        
    def omni_inverse(self, vx, vy, omega):
        """R2 四全向轮逆解"""
        R = self.R
        return [
            ( vx + vy) * INV_SQRT2 - R * omega,   # FL
            ( vx - vy) * INV_SQRT2 - R * omega,   # FR
            (-vx + vy) * INV_SQRT2 - R * omega,   # RL
            (-vx - vy) * INV_SQRT2 - R * omega,   # RR
        ]
    
    def cmd_callback(self, msg):
        vx = msg.linear.x
        vy = msg.linear.y
        omega = msg.angular.z
        
        speeds = self.omni_inverse(vx, vy, omega)
        
        for can_id, speed in zip(R2_MOTOR_IDS, speeds):
            speed_norm = int(max(-100, min(100, speed)))
            # CAN 命令帧: [0x11, speed, 0,0,0,0,0,0]
            self.can_bus.send(can.Message(
                arbitration_id=can_id,
                data=bytes([0x11, speed_norm & 0xFF, 0,0,0,0,0,0]),
                is_extended_id=False))
```

#### 0.4 正解 + 里程计发布（与 0.3 同步实现）

从 0x323~0x326 状态帧提取轮速 → 正解 → 车体速度 → 积分 → 里程计。

#### 0.5 验证标准

```
运动验证：
  □ ros2 topic pub /cmd_vel "linear: {x: 0.3}"   → R2 前进 1m，停下
  □ ros2 topic pub /cmd_vel "linear: {y: 0.3}"   → R2 左移 1m，停下
  □ ros2 topic pub /cmd_vel "angular: {z: 0.5}"  → R2 自转 360°，停下
  □ 组合运动（前进+左转）流畅无卡顿

里程计验证：
  □ ros2 topic echo /odom_wheels 有数据
  □ 推车前进 1m → odom x ≈ 1.0m（误差 < 10%）
  □ Rviz 中 chassis 模型随实际运动移动

CAN 验证：
  □ 4 个状态帧都稳定收到（连续 1 分钟无丢失）
  □ candump 无错误帧
```

---

## 第六章 Phase 1：IMU + 里程计 EKF 融合

### 6.1 定位

纯轮速里程计（Phase 0 产物）存在固有缺陷：轮子打滑、地面不平、轮胎磨损都会导致积分误差累积。IMU 可以提供加速度和角速度参考，修正这些误差。

**为什么要先做 EKF 再做 SLAM**：FAST-LIO2 需要好的初始位姿估计。EKF 融合后的 odom 质量直接影响 SLAM 的收敛速度和鲁棒性。

### 6.2 当前状态 → 目标

```
当前：
  - G354 驱动独立运行，发 /imu/data（已完成）
  - 里程计独立运行，发 /odom_wheels（Phase 0 产物）
  - 没有任何融合

目标：
  /odom_wheels + /imu/data → robot_localization EKF → /odometry/filtered
  静止时位置不漂，转弯时 yaw 准确，长距离误差 < 5%
```

### 6.3 步骤

#### 1.1 确认 G354 驱动正常（0.5 天）

```bash
# 启动 G354（从 Lin_workspace）
python3 ~/Lin_workspace/g354_test/g354_imu_node.py

# 另一个终端验证
ros2 topic echo /imu/data
# 检查：
#   静止时: angular_velocity ≈ (0,0,0), linear_acceleration.z ≈ 9.8
#   旋转时: 对应的 gyro 轴读数变化
#   温控: temperature 应稳定（G354 内部温补）
```

**如果你上次测试后改过接线或换过 NUC**，需要确认串口设备名：
```bash
ls -l /dev/ttyACM*  # 或 /dev/ttyUSB*
# 如果设备名变了，修改 imu_node.py 或通过参数传入
```

#### 1.2 安装 robot_localization（0.5 天）

```bash
sudo apt install ros-humble-robot-localization
```

#### 1.3 编写 EKF 配置文件

```yaml
# config/ekf.yaml
# robot_localization EKF 配置 — R2 底盘
# 
# 融合策略：
#   - /odom_wheels 提供 x, y, vx, vy 的轮速估计
#   - /imu/data 提供 roll, pitch, yaw, wx, wy, wz 的 IMU 估计
#   - IMU 的加速度计用于修正俯仰/横滚，陀螺仪用于修正偏航

ekf_filter_node:
  ros__parameters:
    frequency: 50.0
    
    # ── 轮速里程计输入 ──
    odom0: /odom_wheels
    odom0_config: [true, true, false,    # x, y, z
                   false, false, true,   # roll, pitch, yaw（只用 yaw）
                   true, true, false,    # vx, vy, vz
                   false, false, false,  # vroll, vpitch, vyaw
                   false, false, false]  # ax, ay, az
    odom0_differential: false
    
    # ── IMU 输入 ──
    imu0: /imu/data
    imu0_config: [false, false, false,   # x, y, z
                  true, true, true,      # roll, pitch, yaw
                  false, false, false,   # vx, vy, vz
                  true, true, true,      # vroll, vpitch, vyaw
                  true, true, true]      # ax, ay, az
    imu0_differential: false
    
    # ── 坐标系 ──
    map_frame: map
    odom_frame: odom
    base_link_frame: base_link
    world_frame: odom
```

#### 1.4 写 launch 文件启动 EKF

```python
# launch/ekf.launch.py
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_filter_node',
            parameters=['config/ekf.yaml'],
        ),
    ])
```

#### 1.5 验证标准

```
静态测试：
  □ 把 R2 放在地面不动
  □ /odometry/filtered 的 x, y 变化 < 1cm/min
  □ yaw 波动 < 0.5°/min
  □ 对比: 纯轮速 odom 静止时不变，EKF 也不变（正确）

动态测试：
  □ 推车走 5m 直线，停车测位置误差 < 3%
  □ 原地旋转 360°, yaw 误差 < 5°
  □ 走 2m×2m 方形轨迹，回到起点闭合误差 < 20cm
```

---

## 第七章 Phase 2：MID70 + G354 → FAST-LIO2 SLAM

### 7.1 定位

**这是整个系统的核心出活点**。FAST-LIO2 是 LiDAR-IMU 紧耦合 SLAM，利用 MID70 的非重复扫描特性和 G354 的高频 IMU，实现实时三维建图与定位。

### 7.2 当前状态 → 目标

```
当前：
  - G354 驱动就绪（输出 /imu/data）
  - MID70 物理设备就位
  - FAST-LIO2 源码确定

目标：
  MID70 + G354 → FAST-LIO2 → 实时三维点云地图 + /Odometry
  拿着 R2 在房间走一圈，Rviz 建出可辨识的地图
```

### 7.3 步骤

#### 2.1 编译 livox_ros_driver2（1 天）

```bash
cd ~
mkdir -p mid70_ws/src
cd mid70_ws/src
git clone https://github.com/Livox-SDK/livox_ros_driver2.git
cd ..
colcon build --packages-select livox_ros_driver2
source install/setup.bash

# 验证：查看 MID70 点云
ros2 launch livox_ros_driver2 rviz_MID70.launch.py
```

**可能遇到的问题**：
- `livox_ros_driver2` 某些版本与 Humble 不完全兼容，可能需要 checkout 特定分支
- CMake 版本要求 ≥ 3.16（Ubuntu 22.04 默认 3.22，没问题）

#### 2.2 编译 FAST-LIO2（1 天）

```bash
cd ~/mid70_ws/src
git clone https://github.com/hku-mars/FAST-LIO2.git
cd ..
colcon build --packages-select fast_lio
```

**关键改动**：FAST-LIO2 默认 IMU topic 是 `/livox/imu`，需要改为你的 `/imu/data`（G354）。

```bash
# 方案一：在 launch 文件中 remap
# 修改 FAST-LIO2/launch/mapping_avia.launch.py，在 Node 参数中添加：
# remappings=[('/livox/imu', '/imu/data')]

# 方案二（更可靠）：修改源码
# 编辑 FAST-LIO2/src/laserMapping.cpp，找到：
#   imuSub = nh.subscribe<sensor_msgs::Imu>("/livox/imu", ...)
# 改为：
#   imuSub = nh.subscribe<sensor_msgs::Imu>("/imu/data", ...)
```

#### 2.3 外参标定（半天）

测量 MID70 和 G354 在 R2 上的安装位置：

```yaml
# FAST-LIO2/config/avia.yaml 中的关键参数
# 注意: FAST-LIO2 使用 livox_avia 的配置作为 MID70 的模板

extrinsic_T: [0.0, 0.0, 0.0]  # LiDAR→IMU 平移 (m)
# 根据实测修改。比如 MID70 在 G354 前方 5cm：
# extrinsic_T: [0.05, 0.0, 0.0]

extrinsic_R: [1, 0, 0,  # LiDAR→IMU 旋转矩阵
              0, 1, 0,  # 如果两者安装方向一致，就是单位阵
              0, 0, 1]
```

**初始估算方法**：
- 卷尺测量物理偏移，填入 `extrinsic_T`
- 如果 IMU 和 LiDAR 的安装朝向一致，`extrinsic_R` 用单位阵
- FAST-LIO2 在运行时会在线精化外参，初始估算不必精确到毫米

#### 2.4 组合启动（半天）

```bash
# 终端1: MID70 驱动
ros2 launch livox_ros_driver2 msg_MID70.launch.py

# 终端2: G354 IMU
python3 ~/Lin_workspace/g354_test/g354_imu_node.py

# 终端3: FAST-LIO2
ros2 launch fast_lio mapping_avia.launch.py

# 终端4: Rviz（查看点云+定位）
rviz2 -d ~/mid70_ws/src/FAST-LIO2/config/avia.rviz
```

#### 2.5 实车建图测试（半天）

1. 手持/遥控 R2 在房间走一圈（5m×5m 即可）
2. 观察 Rviz 中点云地图的构建
3. 回到起点，检查点云闭合情况
4. 如果建图质量差，调整参数或检查外参

#### 2.6 验证标准

```
□ Rviz 中看到实时三维点云地图，房间轮廓可辨识
□ FAST-LIO2 输出的 /Odometry 话题频率 ≥ 10Hz
□ 走 10m 路径回到起点，点云闭合误差 < 10cm
□ 快速旋转时点云不严重畸变（IMU 补偿正常）
□ 导出地图用于后续 Nav2 导航
```

---

## 第八章 Phase 3：VLP16 + Nav2 导航

### 8.1 定位

在 Phase 2 已建图的基础上，让 R2 实现自主导航。VLP16 提供 360° 环境感知用于避障，FAST-LIO2 提供定位。

### 8.2 当前状态 → 目标

```
当前：
  - KISS-ICP（VLP16 的 LiDAR-only SLAM）已编译
  - FAST-LIO2 建图（Phase 2）已就绪
  - 无导航能力

目标：
  Rviz 2D Nav Goal → R2 自动规划路径 → 行驶到目标 → 避障
```

### 8.3 步骤

#### 3.1 VLP16 网络配置（可在任何时间提前开始）

这是最容易被卡住的一步，建议尽早开始。

```bash
# VLP16 默认出厂配置：
#   IP: 192.168.1.201
#   数据端口: 2368
#   配置端口: 串口 115200 8N1

# NUC 以太网口配置
sudo ip addr add 192.168.1.100/24 dev eth0
sudo ip link set eth0 up

# 验证连接
ping 192.168.1.201

# 如果 ping 不通：
#   1. 检查 PoE 供电（PoE 注入器或 PoE 交换机）
#   2. 检查网线直连还是通过交换机
#   3. 用 Wireshark 抓包确认是否有 UDP 数据发出
#      sudo tcpdump -i eth0 port 2368
#   4. VLP16 配置口（UART 115200）可以修改网络参数
```

**硬件准备清单**：
- [ ] PoE 注入器（或 PoE 交换机）—— VLP16 必须 PoE 供电
- [ ] 以太网线 —— 至少 CAT5e
- [ ] （可选）USB 转串口模块 —— 如果要用 UART 改 VLP16 配置

#### 3.2 安装 VLP16 ROS2 驱动

```bash
# 方法一：apt 安装（如果可用）
sudo apt install ros-humble-velodyne

# 方法二：源码编译
cd ~
git clone https://github.com/ros-drivers/velodyne.git
# 注意 checkout 对应 humble 的分支
cd velodyne
colcon build
```

#### 3.3 两种导航方案对比

| 方案 | SLAM | 地图类型 | 优点 | 缺点 | 推荐 |
|:-----|:------|:---------|:-----|:-----|:----:|
| **A：SLAM Toolbox** | KISS-ICP 测距 + 2D 投影 | 2D 占用网格 | 简单直接，Nav2 原生支持 | 只支持 2D 导航 | **推荐优先** |
| **B：FAST-LIO2 → octomap** | FAST-LIO2 | 3D 八叉树 | 支持 3D 导航 | 配置复杂 | 后续升级 |

方案 A 步骤：
```bash
# 1. 点云 → 2D 激光扫描
ros2 run pointcloud_to_laserscan pointcloud_to_laserscan_node \
  cloud_in:=/velodyne/points \
  scan:=/scan

# 2. 2D SLAM 建图
ros2 launch slam_toolbox online_async.launch.py

# 3. 保存地图
ros2 run nav2_map_server map_saver_cli -f ~/maps/r2_map
```

#### 3.4 Nav2 导航启动

```bash
# 完整启动导航（地图由 slam_toolbox 提供）
ros2 launch nav2_bringup bringup_launch.py \
  use_sim_time:=false \
  autostart:=true
```

#### 3.5 Nav2 参数调优

Nav2 默认参数是针对差速底盘的，全向轮需要调整：

```yaml
# config/nav2_params.yaml（关键改动）
controller_server:
  ros__parameters:
    # 全向轮底盘
    odom_frame_id: odom
    
DWBLocalPlanner:
  enable_rotate: true  # 全向轮允许原地旋转
  
local_costmap:
  # 全向轮 footprint
  footprint: "[[0.2, 0.2], [0.2, -0.2], [-0.2, -0.2], [-0.2, 0.2]]"
```

#### 3.6 验证标准

```
□ Rviz 中可设置 2D Nav Goal
□ R2 自动规划路径并开始移动
□ 行驶到目标点后自动停止
□ 路径上有障碍时绕行
□ 连续导航 10 次成功率 > 80%
```

---

## 第九章 Phase 4：D435 + Jetson 视觉 AI

### 9.1 定位

为 R2 增加视觉感知能力。D435 提供 RGB-D 数据，Jetson 做 AI 推理，结果反哺导航。

### 9.2 当前状态 → 目标

```
当前：
  - librealsense SDK 已编译
  - Jetson Nano YOLO 部署经验
  - 已有 HSV 球体检测（vision/good/）
  - 但三者相互独立，没有形成链路

目标：
  D435 → RGB → Jetson YOLO → 目标检测 → NUC Nav2 → 导航到目标
```

### 9.3 步骤

#### 4.1 D435 驱动安装（半天）

```bash
# 安装 realsense2_camera
sudo apt install ros-humble-realsense2-camera

# 启动（带参数）
ros2 launch realsense2_camera rs_launch.py \
  depth_module.profile:=640x480x30 \
  rgb_camera.color_profile:=640x480x30 \
  enable_imu:=false \
  align_depth.enable:=true

# 验证
ros2 topic hz /camera/color/image_raw  # ~30Hz
ros2 topic hz /camera/depth/image_raw   # ~30Hz
```

#### 4.2 Jetson 环境搭建（可与 4.1 并行）

```bash
# Jetson Nano (Ubuntu 18.04) 安装 ROS2 Foxy
# 注意：18.04 最高只支持到 Foxy

# 确认 NUC ↔ Jetson 网络互通
# 推荐：以太网直连，静态 IP
# NUC:    192.168.2.100/24
# Jetson: 192.168.2.101/24

# 跨版本 ROS2 测试
# NUC:    ros2 topic pub /test std_msgs/String "data: hello"
# Jetson: ros2 topic echo /test  # 应能收到
```

#### 4.3 YOLO 推理节点（Jetson 侧，1 天）

```python
# NUC → Jetson 的图像转发已经在 NUC 侧用 compressed 格式降低带宽
# Jetson 侧订阅 /camera/color/compressed

class JetsonYoloNode(Node):
    def __init__(self):
        # 订阅压缩图像（来自 NUC）
        self.sub = self.create_subscription(
            CompressedImage, '/camera/color/compressed',
            self.detect_cb, 10)
        # 发布检测结果
        self.pub = self.create_publisher(
            Detection2DArray, '/detections', 10)
        # 加载 TensorRT 引擎（你已有的经验）
        self.net = cv2.dnn.readNetFromTensorRT('model.trt')
    
    def detect_cb(self, msg):
        # cv2 解码 → YOLO 推理 → 检测框
        # → 发布 Detection2DArray
        pass
```

#### 4.4 视觉导航集成（NUC 侧，1 天）

```python
# NUC 订阅 /detections → 目标 3D 坐标 → Nav2 goal

def on_detection(self, msg):
    for det in msg.detections:
        # 1. 取检测框中心像素坐标 (u, v)
        # 2. 读深度图对应像素值
        depth = self.depth_image[v, u]
        
        # 3. 像素坐标 → 相机坐标系 3D 点
        x_cam = (u - cx) * depth / fx
        y_cam = (v - cy) * depth / fy
        z_cam = depth
        
        # 4. 相机坐标 → 车体坐标（通过 TF: camera_link → base_link）
        # 5. 车体坐标 → world 坐标（通过 TF: base_link → odom）
        # 6. 发布 Nav2 导航目标
```

#### 4.5 验证标准

```
□ D435 RGB 和 Depth 在 Rviz 中可视化
□ Jetson 收到图像并返回检测结果
□ 检测到目标后，3D 坐标估算偏差 < 20%（3m 内）
□ R2 能自动导航到目标附近（1m 范围内）
```

---

## 第十章 Phase 5：系统集成与硬化

### 10.1 定位

当所有感知、控制、导航模块都能独立工作后，最后一步是把它们拧成一套可靠的比赛系统。

### 10.2 需要集成的子系统

```
Phase 0  → 底盘 CAN 控制            ┐
Phase 1  → EKF 状态估计              │
Phase 2  → FAST-LIO2 SLAM           ├─ 运动控制核心
Phase 3  → Nav2 导航                 │
Phase 4  → 视觉 AI                  ┘
          └ 3_Diacifa_t1（气动系统） ── 执行机构
```

### 10.3 步骤

#### 5.1 统一启动架构

把所有子系统组织到统一的 launch 文件中：

```python
# launch/r2_complete.launch.py
# 按依赖顺序启动所有节点

def generate_launch_description():
    return LaunchDescription([
        # 底层驱动
        Node(package='r2_bringup', exec='chassis_node'),
        Node(package='g354_imu_driver', exec='g354_imu_node'),
        
        # 传感器
        Node(package='livox_ros_driver2', exec='livox_ros_driver2_node'),
        Node(package='realsense2_camera', exec='realsense2_camera_node'),
        
        # 融合
        Node(package='robot_localization', exec='ekf_node'),
        
        # SLAM
        Node(package='fast_lio', exec='fast_lio_mapping'),
        
        # 导航
        Node(package='nav2_bringup', exec='bringup_launch.py'),
        
        # 视觉（通过条件变量控制是否启动）
        # Node(package='vision', exec='detection_node'),
    ])
```

#### 5.2 气动系统接入 ROS2

`3_Diacifa_t1`（CAN ID 0x141/0x341）已经是独立 MCU，NUC 需要能发命令：

```python
class PneumaticNode(Node):
    """气动控制系统 ROS2 节点"""
    
    def __init__(self):
        self.can_bus = can.interface.Bus(channel='can0', bustype='socketcan')
        self.create_service(SetPneumatic, '/pneumatic/set', self.set_cb)
    
    def set_cb(self, req, res):
        """CAN 命令格式: [pump1_pwm, pump2_pwm, valve1, valve2, 0,0,0,0]"""
        data = bytes([req.pump1_pwm, req.pump2_pwm, 
                      int(req.valve1), int(req.valve2),
                      0, 0, 0, 0])
        self.can_bus.send(can.Message(
            arbitration_id=0x141, data=data, is_extended_id=False))
        res.success = True
        return res
```

#### 5.3 异常处理（实现 chassis_model.md 的 EVENT 设计）

chassis_model.md 第 4.2 节定义了 EVENT 上报机制。在 Phase 0~5 的基础上实现：

```python
# 在每个节点中集成异常检测
class R2ChassisNode(Node):
    def __init__(self):
        self.event_pub = self.create_publisher(String, '/events', 10)
        self.last_status_time = {}  # CAN ID → 上次收到时间
    
    def check_anomalies(self):
        now = self.get_clock().now()
        for can_id in R2_MOTOR_IDS:
            dt = (now - self.last_status_time[can_id]).nanoseconds * 1e-9
            if dt > 0.2:  # 超过 200ms 未收到状态帧
                self.publish_event('MOTOR_LOST', f'motor 0x{can_id:x} lost')
        
        # 堵转检测
        if speed == 0 and pwm > 90 and target_speed != 0:
            self.publish_event('STALL', f'motor 0x{can_id:x} stalled')
```

**需要实现的 EVENT 类型**（来自 chassis_model.md）：

| 事件 | 检测条件 | 动作 |
|:-----|:---------|:-----|
| STALL | target≠0, PWM>90%, actual=0, >2s | 自动切断电机 |
| MOTOR_LOST | 超过 200ms 未收到状态帧 | 发布警告 |
| ESTOP | 收到急停命令或手动触发 | 全车急停 |
| QUEUE_DROP | CAN 发送队列丢帧 | 发布诊断 |

#### 5.4 Robocon 任务编排

行为树示例（使用 BehaviorTree.CPP）：

```
Root
├── Sequence: "主任务"
│   ├── WaitForStart     ← 等待开始信号（串口/CAN/按键）
│   ├── NavigateToZone   ← Nav2 导航到目标区域
│   ├── DetectTarget     ← 视觉检测目标（等待 /detections）
│   ├── ApproachTarget   ← 靠近目标到 0.5m
│   ├── Actuate          ← 触发气动/机械臂
│   └── ReturnToStart    ← 返回起点
└── Fallback: "异常处理"
    ├── EStopMonitor     ← 随时监听急停信号
    └── BatteryMonitor   ← 监听低电量
```

### 10.4 验证标准

```
系统验证：
  □ 一键启动所有节点（launch 文件成功加载）
  □ 所有传感器话题都有数据（ros2 topic list）
  □ 发布 /cmd_vel 能控制 R2 运动
  □ Rviz 中可视化所有传感器数据
  
可靠性验证：
  □ 连续运行 30 分钟无崩溃
  □ 拔掉某个传感器后系统降级运行
  □ 急停信号 50ms 内触发
  
比赛验证：
  □ 完整任务流程跑通（出发→导航→检测→执行→返回）
  □ 重复 5 次成功率 ≥ 80%
```

---

## 附录

### A. 命令速查表

```bash
# ─── CAN ───
sudo ip link set can0 up type can bitrate 1000000     # 启动 CAN
candump can0                                           # 监听所有 CAN 帧
cansniffer can0                                        # CAN 数据嗅探

# ─── G354 ───
python3 ~/Lin_workspace/g354_test/g354_imu_node.py    # 启动 IMU 驱动
rviz2 -d ~/Lin_workspace/g354_test/config/g354_imu.rviz  # 可视化

# ─── MID70 ───
ros2 launch livox_ros_driver2 msg_MID70.launch.py     # 启动 MID70 驱动

# ─── VLP16 ───
sudo ip addr add 192.168.1.100/24 dev eth0             # 配置 IP
ros2 launch velodyne_driver velodyne_driver_node.py   # 启动 VLP16 驱动

# ─── D435 ───
ros2 launch realsense2_camera rs_launch.py             # 启动 D435

# ─── R2 底盘 ───
ros2 topic pub /cmd_vel geometry_msgs/Twist \
  "{linear: {x: 0.2, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
```

### B. 关键文件索引

```
~/Lin_workspace/
├── g354_test/                       # G354 IMU 驱动（已完成）
│   ├── g354_imu_driver/imu_node.py  #   ROS2 驱动节点
│   ├── test_g354.py                 #   原始数据验证
│   ├── launch/g354_rviz.launch.py   #   一键启动
│   └── config/g354_imu.rviz         #   Rviz 配置
│
├── vlp16_slam_ws/                   # VLP16 SLAM（已编译）
│   └── install/kiss_icp/            #   KISS-ICP SLAM
│
├── imu_odom_ws/                     # IMU+里程计融合（已完成）
│   └── imu_odometry_node.py         #   基础 odom 节点
│
├── control/
│   ├── R2.py                        # R2 键盘遥控（运动学已验证）
│   └── speed_calc.py                # 速度换算
│
├── command/                         # CAN 工具集
│   ├── can_command.py               # CAN 命令工具
│   ├── chassis_control.py           # 底盘控制
│   └── dashboard.py                 # 状态面板
│
├── vision/good/                     # 视觉检测
│   └── dynamic_ball_tracker_node.py # 球体检测+3D坐标
│
├── librealsense/                    # RealSense SDK（已编译）
│
├── r2_integration/                  # ← 当前文档所在
│   └── README.md                    #   本文件
│
└── STM32_Now/                       # 嵌入式固件（已定型）
    └── doc/01-arch/chassis_model.md # 底盘构型设计文档

~/mid70_ws/                          # MID70 + FAST-LIO2（待搭建）
├── src/
│   ├── livox_ros_driver2/           # MID70 驱动
│   └── FAST-LIO2/                   # LiDAR-IMU SLAM
└── ...
```

### C. 术语对照

| 缩写 | 全称 | 说明 |
|:-----|:-----|:------|
| MCLM | Motor Control Low Machine | 电机控制器固件项目 |
| ChassisController | 底盘控制器 | UART↔CAN 网关（当前未用于 R2） |
| Diacifa | 气动系统 | 气泵+电磁阀控制 |
| FAST-LIO2 | Fast LiDAR-Inertial Odometry | LiDAR-IMU 紧耦合 SLAM |
| KISS-ICP | Keep It Simple, ICP | LiDAR-only SLAM（用于 VLP16） |
| EKF | Extended Kalman Filter | IMU+轮速融合 |
| Nav2 | ROS2 Navigation Stack | 自主导航堆栈 |
