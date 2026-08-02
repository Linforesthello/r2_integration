# R2 集成 · 当前完成状态

> 最后更新: 2026-07-31
> 内容: 截至今日已完成的所有工作的详细记录

---

## 一、Phase 0：底盘 ROS2 + CAN 控制 ✅

### 1.1 最终确认的映射

```
        前 (vx⁺)
     FL(0x123)    FR(0x126)
         ╲   ↑   ╱
          ╲  ↑  ╱
     左 ←───中───→ 右
          ╱     ╲
         ╱       ╲
     RL(0x124)    RR(0x125)
        后

Unit: 0x123=Unit1  0x124=Unit2  0x125=Unit3  0x126=Unit4
CCW:  0x123(FL) → 0x124(RL) → 0x125(RR) → 0x126(FR)
```

### 1.2 ROS2 包: `r2_bringup`

| 文件 | 说明 |
|:-----|:------|
| `r2_bringup/chassis_node.py` | 核心节点: /cmd_vel → CAN + /odom_wheels |
| `launch/chassis.launch.py` | 启动文件, 引用 yaml 参数 |
| `config/r2_params.yaml` | 实车标定参数 |

### 1.3 标定脚本

| 脚本 | 用途 | 用法 |
|:-----|:-----|:------|
| `scripts/measure_r2_ticks.py` | 编码器 ticks/圈 | `--motor 1 --speed 10` |
| `scripts/map_chassis.py` | CAN ID → 物理位置 | 交互式 |
| `scripts/calibrate_direction.py` | 运动方向标定 | 交互式，8 组测试 |

### 1.4 实车标定参数

```yaml
wheel_half_diagonal: 0.33    # R (m)
ticks_per_rev: 4241           # 均值 FL=4232 FR=4222 RL=4279 RR=4231
wheel_diameter: 0.152         # 轮径 (m)
speed_scale: 94.5             # 逻辑速度→m/s
m_per_tick: 0.000113          # 0.113 mm/tick
max_vx: 0.5                   # 限速 (m/s)
max_vy: 0.3
max_omega: 0.8
```

### 1.5 坐标变换（8 组实测确定）

```python
# _cmd_callback 中:
kin_vx = -user_vy
kin_vy =  user_vx

# _compute_chassis_speed 中(逆变换):
user_vx = formula_vy
user_vy = -formula_vx
```

### 1.6 已实现功能

- [x] /cmd_vel → CAN 命令 (0x123~0x126)
- [x] 四全向轮运动学逆解/正解
- [x] CAN 状态帧接收 (0x323~0x326)
- [x] 里程计 /odom_wheels
- [x] TF (odom → base_link)
- [x] cmd_vel 超时自动停止 (0.5s)
- [x] 电机健康检测 (1Hz)
- [x] 独立 CAN 测试模式 (`--test`)

---

## 二、Phase 1~5 状态

| Phase | 目标 | 前置 | 状态 |
|:------|:-----|:------|:------|
| **1** | G354 IMU + 轮速 → EKF 融合 | Phase 0 | ⏳ IMU 驱动完成，EKF 联调中 |
| **2** | 3D LiDAR SLAM (VLP16 + KISS-ICP) | Phase 0 | ✅ 驱动+里程计+键盘建图全跑通 |
| **3** | VLP16 + Nav2 导航 | Phase 1+2 | ⏳ |
| **4** | D435 + Jetson YOLO 视觉 | Phase 0 | ⏳ |
| **5** | 气动+异常处理+Robocon编排 | 全部 | ⏳ |

### SLAM 方案探索结论

VLP-16 上尝试了四种 SLAM 方案（详见 `retrospect/vlp16_slam_exploration.md`）：

| 方案 | 类型 | 结论 |
|:----|:-----|:-----|
| **slam_toolbox** | 2D SLAM | ❌ 不适合 VLP-16（16线3D雷达） |
| **Cartographer** | 2D SLAM | ❌ .lua 配置兼容性问题 |
| **FAST-LIO2** | 3D LIO | ❌ ROS2 分支硬依赖 Livox，编译失败 |
| **KISS-ICP** | 3D Odom | ✅ 安装简捷，VLP-16 原生支持，已跑通 |

### 当前 VLP-16 工作状态

- [x] VLP-16 驱动（`device_ip:=10.18.18.6`, 目标 IP: `10.18.18.20`，2026-08-02 网段从 10.10.3.x 迁移）
- [x] TF 标定（`base_footprint → velodyne`, z=0.77m, 车顶水平安装）
- [x] KISS-ICP 3D 里程计（topic `/velodyne_points` → odom + 注册点云）
- [x] 键盘控制 + 点云采集建图（2026-08-02 实车跑通，RViz 中 `odom_lidar` 系点云地图随车累积）
- [ ] IMU 融合（G354 EKF，实车验证挂起中，见 [phase1/ekf-verification.md](phase1/ekf-verification.md)）
- [ ] 雷达闭环运动（基于 `/kiss_icp/odometry` 的 waypoint 节点，待做）

---

## 三、相关文件

完整项目结构见 `README.md`。本阶段文件：

- `phase0/chassis_definition.md` — 底盘定义（映射/参数/公式）
- `phase0/completion_report.md` — Phase 0 完成记录
- `phase0/debug_log.md` — 踩坑日志
