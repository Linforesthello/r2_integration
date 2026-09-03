# R2 外设集成 · 全局进度总览

> 最后更新: 2026-08-18
> 内容: 全项目进度一览，每个 Phase 的完成度、依赖关系、下一步

---

## 一、总进度

```
Phase 0 底盘CAN控制 ━━━━━━━━━━━━━━━━━━━━━━━ 100% ✅
Phase 1 IMU+EKF融合 ━━━━━━━━━━━━━━━━○○  95%  ◆ 实车对比验证（08-06）+ yaw 方案①通过（08-12）
Phase 2 VLP16+KISS-ICP ━━━━━━━━━━━━━━━━━━━━ 100% ✅
Phase 3 Nav2导航     ━━━○○○○○○○○  25%  ◆ 首闭环（08-15）+ 降额过缝验证（08-17）；W2 收尾中（到达误差测量/连续导航测试）；全速验证暂缓
Phase 4 视觉AI       ━○○○○○○○○○  0%  ⏳
Phase 5 系统集成     ━○○○○○○○○○  0%  ⏳
                    ─────────────
 总计:              53%
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
| 里程计积分修复（08-06） | ✅ | omega 单位 13.2× + 全向轮积分，见 [chassis_ekf_debug](retrospect/2026-08-05_chassis_ekf_debug.md) |
| 文档 | ✅ | 4 份 .md 同步到 Obsidian |

### Phase 1：IMU + 里程计 EKF 融合 ◆ 85%

| 模块 | 状态 | 备注 |
|:-----|:----:|:------|
| G354 驱动 | ✅ 已完成 | 38 字节 polling + Mahony(Kp=1.0, Ki=0.005) + ZUPT |
| **IMU 轴映射修复** | ✅ 已完成（8-03） | mount_axes 参数 + init/Mahony 两处符号修正；安装定义见 [sensor-mount.md](phase0/sensor-mount.md) |
| G354 静置测试 | ✅ 通过 | yaw 漂移 0.002°/min，132s 仅漂 0.005° |
| 驱动移入工作区 | ✅ 已完成 | `g354_driver/` 在 `r2_integration/` 下 |
| 轮速里程计 | ✅ Phase 0 已就绪 | `/odom_wheels` |
| robot_localization EKF | ✅ **已配置** | `config/ekf.yaml` + `launch/ekf.launch.py` |
| EKF 联调 | ✅ 已跑通（8-03） | IMU 姿态正确跟随车体（左/右转、左/右倾），RViz odom 正常 |
| 对比测试: 纯轮速 vs EKF | ✅ **完成（08-06）** | bag 对比: yaw 偏差 179°→4-14°，方形闭环 1.8m→0.27m（KISS 交叉验证一致） |
| EKF 过程噪声修复（08-06） | ✅ | 225 值矩阵（3.5.4 的 15 值格式加载 bug 致启动 NaN），见 [chassis_ekf_debug](retrospect/2026-08-05_chassis_ekf_debug.md) |

**下一步：z 漂移 slip 场景 +2.5m 跟进（剧烈加减速时数值积累）→ Phase 3 Nav2**

### Phase 2：VLP-16 + KISS-ICP SLAM ✅ 已完成

> 注：现役 VLP-16 + KISS-ICP。FAST-LIO2 曾因 ROS2 分支硬依赖 Livox 编译失败而搁置（探索记录见 [vlp16_slam_exploration.md](retrospect/vlp16_slam_exploration.md)），08-18 起已在 VLP-16 全链路验证通过（感知升级候选）；MID-70 闲置、**计划内**（传感器选型 A/B，见 [planning-control-roadmap.md](roadmaps/planning-control-roadmap.md) §三）

| 模块 | 状态 | 备注 |
|:-----|:----:|:------|
| VLP-16 驱动 | ✅ 已安装 | velodyne_driver，设备 IP 10.18.18.6 |
| G354 IMU | ✅ 已就绪 | 已接入 EKF（见 Phase 1） |
| TF 标定 | ✅ 已完成 | base_footprint→velodyne，z=0.77m（⚠️ 与实述 65cm 冲突，基准待确认，见 [sensor-mount.md](phase0/sensor-mount.md)） |
| KISS-ICP 建图 | ✅ 已跑通 | /velodyne_points → odom |

### Phase 3：VLP16 + Nav2 导航 ⏳

| 模块 | 状态 | 备注 |
|:-----|:----:|:------|
| VLP16 网络配置 | ✅ 已完成 | 设备 IP 10.18.18.6，目标 IP 10.18.18.20（2026-08-02 从 10.10.3.x 迁移） |
| VLP16 ROS2 驱动 | ✅ 已跑通 | |
| KISS-ICP | ✅ 已跑通 | 属于 Phase 2；/velodyne_points → odom |
| slam_toolbox 建图 | ❌ 已否决 | 不适合 VLP-16，见 [vlp16_slam_exploration.md](retrospect/vlp16_slam_exploration.md) |
| Nav2 配置 | ✅ 首闭环（08-15）+ 降额过缝验证（08-17） | AMCL 定位 + MPPI 跟踪 + velocity_smoother；降额参数（0.2/0.15/0.4）实车闭环成功，见 [retrospect 08-15](retrospect/2026-08-15_nav2_bringup.md)；08-17 inflation 0.30 过缝验证通过（无碰撞），见 [retrospect 08-17](retrospect/2026-08-17_nav2_initialpose_inflation_fix.md)；全速验证暂缓 |
| W2 收尾（08-18 起） | 🟡 进行中 | 到达误差测量（方案+脚本见 [w2-operation.md](minimal-loop/w2-operation.md) D7）、连续导航测试（D5-6）、rviz 显示项确认；全速验证**暂缓**（切 nav2_params.yaml 前须先同步其膨胀参数仍 0.55） |

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

