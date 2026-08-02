# R2 外设集成 · 全局进度总览

> 最后更新: 2026-07-31
> 内容: 全项目进度一览，每个 Phase 的完成度、依赖关系、下一步

---

## 一、总进度

```
Phase 0 底盘CAN控制 ━━━━━━━━━━━━━━━━━━━━━━━ 100% ✅
Phase 1 IMU+EKF融合 ━━━━━○○○○○○○  30%  ◆ 进行中
Phase 2 VLP16+KISS-ICP ━━━━━━━━━━━━━━━━━━━━ 100% ✅
Phase 3 Nav2导航     ━○○○○○○○○○  0%  ⏳
Phase 4 视觉AI       ━○○○○○○○○○  0%  ⏳
Phase 5 系统集成     ━○○○○○○○○○  0%  ⏳
                    ─────────────
 总计:              38%
```

---

## 二、Phase 详情

### Phase 0：底盘 ROS2 + CAN 控制 ✅ 100%

| 模块 | 状态 | 备注 |
|:-----|:----:|:------|
| CAN 总线通信确认 | ✅ | 4 路状态帧稳定接收 |
| r2_bringup ROS2 包 | ✅ | chassis_node + launch + config |
| 运动学逆解/正解 | ✅ | 公式从 R2.py 移植，已验证 |
| CAN ID → 物理位置映射 | ✅ | map_chassis.py 实测确认 |
| 坐标变换校准 | ✅ | calibrate_direction.py 8 组测试 |
| 编码器 ticks/圈标定 | ✅ | 均值 4241 |
| 里程计 /odom_wheels | ✅ | + TF (odom → base_link) |
| 超时保护 + 诊断 | ✅ | 0.5s 无指令自动停止 |
| 参数配置 (yaml) | ✅ | 全实车标定值 |
| 文档 | ✅ | 4 份 .md 同步到 Obsidian |

### Phase 1：IMU + 里程计 EKF 融合 ◆ 30%

| 模块 | 状态 | 备注 |
|:-----|:----:|:------|
| G354 驱动 | ✅ 已完成 | 38 字节 polling + Mahony(Kp=1.0, Ki=0.005) + ZUPT |
| G354 静置测试 | ✅ 通过 | yaw 漂移 0.002°/min，132s 仅漂 0.005° |
| 驱动移入工作区 | ✅ 已完成 | `g354_driver/` 在 `r2_integration/` 下 |
| 轮速里程计 | ✅ Phase 0 已就绪 | `/odom_wheels` |
| robot_localization EKF | ✅ **已配置** | `config/ekf.yaml` + `launch/ekf.launch.py` |
| 对比测试: 纯轮速 vs EKF | ◇ **待实车验证** | 需底盘 + IMU + EKF 同时运行 |

**下一步：实车验证 EKF 融合效果**

### Phase 2：VLP-16 + KISS-ICP SLAM ✅ 已完成

> 注：FAST-LIO2 / MID70 方案已弃用（FAST-LIO2 ROS2 分支硬依赖 Livox 编译失败），详见 [vlp16_slam_exploration.md](retrospect/vlp16_slam_exploration.md)

| 模块 | 状态 | 备注 |
|:-----|:----:|:------|
| VLP-16 驱动 | ✅ 已安装 | velodyne_driver，设备 IP 10.18.18.6 |
| G354 IMU | ✅ 已就绪 | 已接入 EKF（见 Phase 1） |
| TF 标定 | ✅ 已完成 | base_footprint→velodyne，z=0.77m |
| KISS-ICP 建图 | ✅ 已跑通 | /velodyne_points → odom |

### Phase 3：VLP16 + Nav2 导航 ⏳

| 模块 | 状态 | 备注 |
|:-----|:----:|:------|
| VLP16 网络配置 | ✅ 已完成 | 设备 IP 10.18.18.6，目标 IP 10.18.18.20（2026-08-02 从 10.10.3.x 迁移） |
| VLP16 ROS2 驱动 | ✅ 已跑通 | |
| KISS-ICP | ✅ 已跑通 | 属于 Phase 2；/velodyne_points → odom |
| slam_toolbox 建图 | ❌ 已否决 | 不适合 VLP-16，见 [vlp16_slam_exploration.md](retrospect/vlp16_slam_exploration.md) |
| Nav2 配置 | ◇ | Phase 3 核心待办 |

### Phase 4：D435 + Jetson 视觉 AI ⏳

| 模块 | 状态 | 备注 |
|:-----|:----:|:------|
| D435 驱动 | ◇ | `realsense2_camera` |
| Jetson ROS2 环境 | ◇ | Foxy 与 N97 Humble 互通 |
| YOLO 推理节点 | ◇ | 已有部署经验 |
| 视觉→导航集成 | ◇ | |

### Phase 5：系统集成与硬化 ⏳

| 模块 | 状态 | 备注 |
|:-----|:----:|:------|
| 气动系统接入 | ◇ | 外部引用（STM32_Now 工作区）：/home/lin/ProjectRequirement/MCU/Lin_STM32/STM32_F103C8T6/STM32_Now/3_Diacifa_t1，CAN ID 0x141 |
| EVENT 异常上报 | ◇ | 设计待实现 |
| 行为树/状态机 | ◇ | |
| 全系统启动 launch | ◇ | |

---

## 三、依赖关系图

```
Phase 0 底盘CAN控制  ──────────────── 已完成
       │
       ├──→ Phase 1: IMU+odom EKF  ←── 下一步
       │              │
       │              └──→ Phase 3: Nav2 导航
       │
       └──→ Phase 2: VLP16 + KISS-ICP SLAM
                              │
                              └──→ Phase 3 (地图来源)
                                     │
                                     └──→ Phase 5 系统集成
                                              ↑
                                      Phase 4 视觉AI (独立,可并行)
```

---

## 四、建议优先级

```
现在──────→ 短期 ──────→ 中期 ──────→ 长期
│           │            │            │
▼           ▼            ▼            ▼
Phase 0  Phase 1    Phase 2+3    Phase 4+5
已完成    IMU+EKF    SLAM+导航    视觉AI+集成
          (1~2周)    (2~3周)      (2~3周)
```

---

## 五、风险跟踪

| 风险 | 阶段 | 可能性 | 缓解 |
|:-----|:----:|:------:|:-----|
| VLP16 网络配置 | Phase 2 | 🟡 中 | ✅ 已解决：设备 IP 10.18.18.6，目标 IP 10.18.18.20（2026-08-02 从 10.10.3.x 迁移） |
| Jetson/N97 跨版本通信 | Phase 4 | 🟡 中 | 先用简单话题验证 |

