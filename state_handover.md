# R2 集成 · Phase 0 状态交接

> 2026-07-29 完成。下阶段目标: Phase 1 (IMU+里程计 EKF 融合)

---

## 已完成的 Phase 0

R2 四全向轮底盘 ROS2 + CAN 控制已跑通。

### CAN ID → 物理位置

| CAN ID | Unit | 位置 | MCLM Group |
|:------:|:----:|:----:|:----------:|
| 0x123 | Unit1 | 左前 (FL) | GROUP=2 |
| 0x126 | Unit4 | 右前 (FR) | GROUP=1 |
| 0x124 | Unit2 | 左后 (RL) | GROUP=2 |
| 0x125 | Unit3 | 右后 (RR) | GROUP=1 |

### 物理参数（`r2_params.yaml`）

```yaml
wheel_half_diagonal: 0.33    # R (m)
ticks_per_rev: 4241           # 实测均值
wheel_diameter: 0.152         # 轮径 (m)
speed_scale: 94.5             # 逻辑速度→m/s 系数
m_per_tick: 0.000113          # 每 tick = 0.113mm
```

### 关键修复：坐标变换

用 `scripts/calibrate_direction.py` 实测 8 组轮速组合确定：

```python
# 用户遥控器坐标系 → 运动学公式坐标系相差 90°
kinematics_vx = -user_vy    # 用户的左右 → 公式的前后
kinematics_vy =  user_vx    # 用户的前后 → 公式的左右
# omega 方向正确，无需变换

# 里程计正解输出做逆变换:
user_vx = formula_vy
user_vy = -formula_vx
```

### 踩过的坑（7 个）

| # | 问题 | 修复 |
|:--|:-----|:------|
| 1 | CAN ID → 物理位置映射错 | `map_chassis.py` 逐个确认 |
| 2 | 坐标系差 90° | 上述坐标变换 |
| 3 | launch 硬编码旧参数 | 引用 yaml |
| 4 | ament_python libexec 问题 | `ExecuteProcess` 直接调 python |
| 5 | 逆解输出被 int() 截断为 0 | 加 `speed_scale` 映射 |
| 6 | MAX_WHEEL_OMEGA 硬编码 | 用 `m_per_tick` + `speed_scale` 统一 |
| 7 | ROS2 yaml 缺命名空间 | 加 `/** ros__parameters` |

### 文件位置

```
代码:   ~/Lin_workspace/r2_integration/r2_bringup/
启动:   ros2 launch r2_bringup chassis.launch.py
标定:   ~/Lin_workspace/r2_integration/scripts/
文档:   ~/Lin_workspace/r2_integration/*.md
Ob:     01-开发日志/✨总/当前项目文档/R2_Integration/
```

---

## 下一步：Phase 1（IMU + 里程计 EKF）

**目标**: G354 IMU + 轮速里程计 → `robot_localization` EKF → 精确 /odometry/filtered

**已完成基础**:
- G354 驱动就绪: `~/Lin_workspace/g354_test/g354_imu_driver/imu_node.py`
  - 发布 `/imu/data` (sensor_msgs/Imu)
  - 互补滤波姿态 (roll/pitch/yaw)
- 轮速里程计就绪: `chassis_node.py` 发布 `/odom_wheels`

**需要做的**:
1. 安装 `ros-humble-robot-localization`
2. 编写 `config/ekf.yaml`（融合 /odom_wheels + /imu/data）
3. 启动 EKF → 对比纯轮速 vs EKF 精度
4. 可选：做一次速度标定（发固定速度，实测距离→校准 speed_scale）

**已知 G354 问题**:
- 串口可能是 `/dev/ttyACM0` 或 `/dev/ttyUSB0`，确认设备名
- 上次测试时温控正常
