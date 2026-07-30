# R2 底盘 ROS2 + CAN 控制 · 调试记录与最终配置

> 完成日期: 2026-07-29
> 目标: ROS2 /cmd_vel → CAN → R2 四全向轮底盘运动
> 状态: ✅ 全部调通，前进后退左移右旋自转正常

---

## 一、最终配置

### CAN ID → 物理位置映射（经标定确认）

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

    Unit#:  0x123=Unit1  0x124=Unit2  0x125=Unit3  0x126=Unit4
    逆时针:   123(FL) → 124(RL) → 125(RR) → 126(FR)
```

### `r2_params.yaml`

```yaml
/**:
  ros__parameters:
    can_channel: 'can0'
    wheel_half_diagonal: 0.33    # R (m)
    ticks_per_rev: 4241           # 编码器 ticks/圈（实测均值）
    wheel_diameter: 0.152         # 轮径 (m)
    speed_scale: 94.5             # 逻辑速度→m/s 系数
    cmd_timeout: 0.5              # /cmd_vel 超时(s)
    odom_publish_rate: 50.0       # odom 发布频率
    max_vx: 0.5                   # 最大前进 (m/s)
    max_vy: 0.3                   # 最大侧移 (m/s)
    max_omega: 0.8                # 最大旋转 (rad/s)
```

### `chassis_node.py` 关键代码

```python
# ── 坐标变换（8 组轮速测试校准）──
# 公式坐标系 ↔ 用户坐标系旋转了 90°
vx = -msg.linear.y    # 用户的左右 → 公式的前后
vy =  msg.linear.x    # 用户的前后 → 公式的左右
```

---

## 二、踩坑记录

### 坑 1：CAN ID → 物理位置映射错误（🔴 严重）

**现象**：前进时车体运动方向完全不对。

**根因**：代码中 `R2_MOTOR_IDS` 数组顺序写错了。把 FR 和 RR 的位置搞混，导致运动学公式输出的速度分配给错误的物理轮子。

**修复**：用 `map_chassis.py` 逐一给每个 CAN ID 发正速度，观察哪个轮子转、在什么位置，确定正确映射：

| CAN ID | 物理位置 | 确定方法 |
|:------:|:--------|:---------|
| 0x123 | 左前 (FL) | 发 speed=+30 观察 |
| 0x126 | 右前 (FR) | 同上 |
| 0x124 | 左后 (RL) | 同上 |
| 0x125 | 右后 (RR) | 同上 |

### 坑 2：运动学坐标系与遥控坐标系差 90°（🔴 严重）

**现象**：发前进命令，车往右走；发左移命令，车往前走。

**根因**：标准全向轮运动学公式的"前方向"定义和 R2 车体的实际前方向差了 90°。这可能是全向轮辊子安装方向与公式假设的不同导致的。

**定位**：用 `calibrate_direction.py` 逐一测试 8 种轮速组合，确定每种组合对应的实际运动方向：

| 测试 | 轮速 (FL FR RL RR) | 实际运动 | 对应关系 |
|:----:|:-------------------|:--------|:---------|
| P1 | +20 +20 -20 -20 | **右移** | 公式 vx+ → 实际 vy- |
| P2 | +20 -20 +20 -20 | **前进** | 公式 vy+ → 实际 vx+ |
| P3 | -20 +20 -20 +20 | **后退** | 公式 vy- → 实际 vx- |
| P4 | -20 -20 +20 +20 | **左移** | 公式 vx- → 实际 vy+ |
| P5 | -20 -20 -20 -20 | **左旋** | 公式 ω+ → 实际 ω+ ✅ |
| P6 | +20 +20 +20 +20 | **右旋** | 公式 ω- → 实际 ω- ✅ |
| P7 | +20 -20 -20 +20 | 不动 | 力抵消 ✅ |
| P8 | -20 +20 +20 -20 | 不动 | 力抵消 ✅ |

**修复**：`_cmd_callback` 中做坐标变换：
```python
kinematics_vx = -user_vy
kinematics_vy =  user_vx
```
里程计正解输出做逆变换：
```python
user_vx = formula_vy
user_vy = -formula_vx
```

### 坑 3：Launch 文件硬编码旧参数（🟡 中等）

**现象**：用 `ros2 launch` 启动时，底盘参数不对。

**根因**：launch 文件里直接写了 `wheel_half_diagonal: 0.15`、`ticks_per_rev: 9000` 等硬编码值，覆盖了 `r2_params.yaml` 里的实车标定值。

**修复**：launch 文件引用 yaml 配置，不再硬编码任何参数。

### 坑 4：ROS2 ament_python 可执行文件路径问题（🟡 中等）

**现象**：`ros2 run r2_bringup chassis_node` 提示 "No executable found"。

**根因**：ament_python 把 entry point 装在 `bin/`，但 ROS2 在某些版本下期望 `lib/<pkg>/`。跟构建系统的交互问题。

**修复**：launch 文件用 `ExecuteProcess(cmd=['python3', node_script])` 直接调用 Python 文件，绕过 libexec 查找机制。

### 坑 5：逆解输出被 int() 截断为 0（🔴 严重）

**现象**：发 `/cmd_vel` 车不动。

**根因**：`omni_inverse()` 输出 m/s 量级的值（如 0.212），直接 `int(0.212) = 0` 送给 CAN，电机收不到有效速度。

**修复**：添加 `speed_scale=94.5` 参数，将 m/s 映射到 CAN 逻辑速度（-100~100）：`logic = int(round(mps * speed_scale))`。

### 坑 6：里程计 MAX_WHEEL_OMEGA 硬编码（🔴 严重）

**现象**：里程计距离错 2.3 倍。

**根因**：代码假设 `speed=100` 对应 300 RPM，实测只有 133 RPM（差 2.3 倍）。

**修复**：删掉硬编码 `MAX_WHEEL_OMEGA=31.4`，改用 `speed_scale` + `m_per_tick` 统一换算。

### 坑 7：ROS2 yaml 参数文件格式错误（🟢 轻微）

**现象**：`ros2 launch` 时报 "Cannot have a value before ros__parameters"。

**根因**：yaml 文件缺少 `/** ros__parameters` 命名空间。

**修复**：参数用 `/** { ros__parameters: {...} }` 包裹。

---

## 三、标定流程（供下次复现）

### 3.1 编码器 ticks/圈 标定

```bash
python3 ~/Lin_workspace/r2_integration/scripts/measure_r2_ticks.py --motor 1 --speed 10
```

操作：在轮子上做标记 → 按 Enter 电机转 → 观察轮子转一圈按 Ctrl+C → 记录 ticks 变化。

对 4 个轮子各做一次，取均值写入 `ticks_per_rev`。

### 3.2 物理位置映射标定

```bash
python3 ~/Lin_workspace/r2_integration/scripts/map_chassis.py
```

操作：架起车 → 轮流给每电机发 speed=+30 → 观察哪个位置轮子转、正转方向 → 输入结果。

输出：确认的 `R2_MOTOR_IDS` 数组。

### 3.3 方向标定

```bash
python3 ~/Lin_workspace/r2_integration/scripts/calibrate_direction.py
```

操作：车放地上 → 逐一测试 8 组轮速组合 → 观察车体实际运动方向 → 输入结果。

输出：vx/vy 坐标变换关系。

---

## 四、文件清单

```
~/Lin_workspace/r2_integration/
├── README.md                              # 五阶段集成方案总纲
├── r2_chassis_definition.md               # 底盘完整定义文档
├── phase0_complete.md                     # Phase 0 完成记录
├── r2_bringup/                            # ROS2 包
│   ├── package.xml / setup.py
│   ├── r2_bringup/
│   │   └── chassis_node.py                # 底盘控制节点
│   ├── launch/
│   │   └── chassis.launch.py
│   └── config/
│       └── r2_params.yaml                 # 实车标定参数
└── scripts/
    ├── measure_r2_ticks.py                # 编码器标定
    ├── map_chassis.py                     # CAN ID → 物理位置映射
    └── calibrate_direction.py             # 运动方向标定
```

---

## 五、启动方法

```bash
# 1. CAN 总线
sudo ip link set can0 up type can bitrate 1000000

# 2. 启动底盘节点
source ~/Lin_workspace/r2_integration/r2_bringup/install/setup.bash
ros2 launch ~/Lin_workspace/r2_integration/r2_bringup/launch/chassis.launch.py

# 3. 键盘控制
ros2 run teleop_twist_keyboard teleop_twist_keyboard

# 4. 查看里程计
ros2 topic echo /odom_wheels
```

---

## 六、版本历史

| 版本 | 日期 | 变更 |
|:----:|:----:|:------|
| v1.0 | 2026-07-29 | Phase 0 完成。全部标定、方向校准、踩坑修复 |
