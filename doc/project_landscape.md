# R2 项目全景（与更大系统的关系）

> 生成日期: 2026-08-06
> 职责: 讲清 R2 在 Robocon 系统全景中的位置、项目谱系、依赖的底层
> 现状快照见 [project_status.md](project_status.md)（R2 聚焦）；本文件只讲"关系"

---

## 一、Robocon 系统全景架构

分布式移动机器人系统（长期目标）：

```
ROS2 上位机 (N97 / VM / 树莓派 R1)
   │
   ├── UART / Ethernet
   ▼
通信中枢 MCU（未来下层主控）
   │
   │ CAN 1M
   ▼
STM32 分布式节点（电机控制 ×N）
   │
   ▼
电机 + 编码器 + IMU
```

**R2 的当前位置**（现状实现）：

```
N97 (ROS2 Humble)
   │ CANable2 (USB-CAN, ttyACM0)
   ▼ can0 (1M)
MCLM 电机 ×4（每电机内置 STM32 控制节点，FreeRTOS + PID + 编码器）
   │
   └── 四全向轮底盘
```

> G354 IMU 不走 CAN——经 JLink OB Mini（USB 串口 ttyACM1）直连 N97。

---

## 二、项目谱系：R1 vs R2

| | R1 | R2 |
|:--|:---|:---|
| 底盘类型 | **四舵轮**（转向+驱动，MT6701 转角反馈） | **四全向轮**（MCLM 电机直驱，无转向） |
| 上位机 | 树莓派 4B | N97 Mini PC（Ubuntu 22.04 + Humble） |
| 底层 | STM32 转向/驱动节点 | MCLM 电机控制单元（STM32 内置） |
| 定位 | 早期底盘平台 | 当前主线（集成导航/感知/AI） |
| 参考 | 操作手顺 `STM32_Now/doc/02-deploy/raspi_r1_control.md` | 本仓库 |

> 长期记录（gpt阶段性总结 07-29）中"舵轮运动学"指 R1；R2 全向轮运动学
> 已完成并实车验证（见 [chassis_definition.md](phase0/chassis_definition.md)）。

---

## 三、依赖的底层（STM32 工作区）

`/home/lin/ProjectRequirement/MCU/Lin_STM32/STM32_F103C8T6/STM32_Now/`：

| 模块 | 内容 | 与 R2 的关系 |
|:-----|:-----|:-------------|
| 3_MCLM_t2 | 电机控制单元（FreeRTOS/PID/CAN） | R2 底盘执行层 |
| 3_SteeringArm_t1 | 舵向机械臂 | 并行子项目 |
| 3_Diacifa_t1 | 气动系统（CAN ID 0x141） | Phase 5 接入 R2 |
| 6_MT6701 | 转向编码器 | R1 舵轮用 |

---

## 四、并行子项目

- **四足**（Robocon 交流赛）：资料在 `~/Lin_workspace/260612目前/四足`
- **视觉**：Astra Pro / D435（Phase 4 接入 R2，Jetson 协同规划中）
- **舵轮机械臂**：3_SteeringArm_t1

---

## 五、感知件清单与归属

| 传感器 | 归属 | 状态 |
|:-------|:-----|:-----|
| VLP-16（10.18.18.6，经交换机） | R2 | ✅ 建图/里程计 |
| Epson G354 IMU（JLink OB Mini 直连） | R2 | ✅ 融合 |
| Intel RealSense D435/D430、Astra Pro | 视觉项目 | 待 Phase 4 |
| Livox MID-70 | 闲置、计划内 | 传感器选型 A/B 候选（FAST-LIO 原生适配），见 [planning-control-roadmap.md](planning-control-roadmap.md) §三 |

---

## 六、参考

- 长期脉络（非现状依据，07-29 生成，含较多已过时"待办"）：
  `~/Lin_note/Open-Notes-Library/01-开发日志/个人发展与学习丨20250910/gpt阶段性总结/`
- 项目路线图：[01-plan.md](01-plan.md)
