# EKF 实车验证清单

> 最后更新: 2026-07-31
> 目的: 实车对比「纯轮速 /odom_wheels」vs「EKF 融合 /odometry/filtered」，判定 Phase 1 收尾
> 前置: Phase 0 底盘控制 ✅、G354 驱动 ✅（接线见 [g354-wiring.md](g354-wiring.md)）、EKF 配置 ✅（[ekf.yaml](../../r2_bringup/config/ekf.yaml)）

---

## 一、配置核对结论（2026-07-31，已核实代码）

| 核对项 | 配置 | 状态 |
|:------|:-----|:----:|
| 输入 topic `/odom_wheels` | chassis_node 发布，50Hz | ✅ |
| 输入 topic `/imu/data` | imu_node 发布，100Hz | ✅ |
| frame: `odom` / `base_link` | 与 chassis 一致 | ✅ |
| IMU frame: `imu_link` | **缺 `base_link→imu_link` 静态 TF** | 🔴 待修 |
| TF 发布者 | chassis 与 EKF 都发 `odom→base_link` | 🔴 待修 |
| `/odom_wheels` 协方差 | 消息未填（全零），EKF 会拒收 | 🔴 待修 |
| IMU 协方差 | 姿态/角速度/加速度均已填 | ✅ |
| 频率 / 队列 | EKF 50Hz，queue 10 | ✅ |
| `ekf.launch.py` docstring | 声称 `ekf_only:=false` 启动全部，实际没实现 | 🟡 顺手修 |

**修复项都完成前不要出车**（否则 TF 抖动 / 轮速路不参与融合，验证结果不可信）。

---

## 二、前置修复（✅ 已全部落地 2026-07-31）

### 2.1 消除 TF 冲突（P0）✅

`chassis_node.py` 发布 `odom→base_link`（`_publish_odom` 末尾），EKF 默认也发布同名 TF。

**已落地**：chassis_node 加 `publish_tf` 参数（默认 true，不影响单独使用），
EKF 场景下启动时传 `publish_tf:=false`，由 EKF 统一发布 `odom→base_link`。

- [x] `r2_bringup/r2_bringup/chassis_node.py`：声明参数 + TF 广播加开关
- [x] `r2_bringup/launch/chassis.launch.py`：声明并透传参数
- [x] `scripts/r2_startup.sh`：底盘终端加 `publish_tf:=false`

### 2.2 补 `base_link→imu_link` 静态 TF（P0）✅

EKF 需要 IMU frame 在 TF 树中可达。IMU 与 base_link 重合同向（单位变换）。

**已落地**：`ekf.launch.py` 内新增 `static_transform_publisher`
（`0 0 0 0 0 0 base_link imu_link`）。

### 2.3 给 `/odom_wheels` 补协方差（P0）✅

`chassis_node.py` 的 `_publish_odom` 中给 `odom.pose.covariance` 和
`odom.twist.covariance` 赋值（全零会被 robot_localization 丢弃并告警）。

**已落地**：初值 pose=1e-3（x/y）、twist=1e-2（vx/vy），yaw 相关填 0
（`ekf.yaml` 中 yaw 不融合）。按实测调整，量级参考 `m_per_tick=0.000113`。

### 2.4 修 docstring（P2）✅

**已落地**：`ekf.launch.py` 顶部的 `ekf_only:=false` 描述已改为
「三合一启动见 [scripts/r2_startup.sh](../../scripts/r2_startup.sh)」。

---

## 三、出车准备

### 3.1 前置确认

- [ ] 地面平整、场地空旷（建议 ≥ 4m × 4m），四轮离地测试已完成过
- [ ] CAN 适配器在 `/dev/ttyACM0`，G354 在 `/dev/ttyACM1`
- [ ] 修复 2.1~2.4 已落地并 `colcon build` 成功
- [ ] 记录起点地面标记（贴纸/粉笔十字）

### 3.2 启动顺序（N97 上）

```bash
# 终端 0: CAN 总线
python3 ~/Lin_workspace/command/can_command.py

# 终端 1: 底盘（publish_tf:=false 让 EKF 发 TF）
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch r2_bringup chassis.launch.py publish_tf:=false

# 终端 2: IMU
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch g354_imu_driver g354_rviz.launch.py rviz:=false serial_port:=/dev/ttyACM1

# 终端 3: EKF（修复后含 static TF）
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch r2_bringup ekf.launch.py

# 终端 4: 数据录制
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 bag record /odom_wheels /odometry/filtered /imu/data /cmd_vel
```

> 修复完成后 r2_startup.sh 会自动带 `publish_tf:=false`，也可直接用它启动。

### 3.3 启动后冒烟检查（每项都应通过）

- [ ] `ros2 topic hz /odom_wheels` ≈ 50Hz，`/imu/data` ≈ 100Hz，`/odometry/filtered` ≈ 50Hz
- [ ] `ros2 topic echo /odometry/filtered --once` 正常出数
- [ ] `ros2 run tf2_ros tf2_echo odom base_link` 输出稳定、无跳变
- [ ] `ros2 run tf2_ros tf2_echo base_link imu_link` 有输出（静态变换）
- [ ] EKF 日志无报错；无 "Could not obtain transform" / "Covariance is zero" 反复刷屏

---

## 四、验证步骤与判合格标准

> 每步先停稳 5s 再操作；两个里程计用 `tf2_echo` 或录包后对比。
> 手机/量具记录实测真值。

### 4.1 静态漂移测试（3 min）

| 操作 | 记录 |
|:-----|:-----|
| 车停稳，静置 3 分钟不动 | 期间 yaw 变化量（读 `/odometry/filtered`） |

**合格**：`|Δyaw| ≤ 0.1°/min`（G354 静置实测 0.002°/min，融合后不应更差）
**记录**：纯轮速 vs EKF 各自的 Δyaw，确认 EKF 明显优于纯轮速。

### 4.2 直线测试（5 m）

| 操作 | 记录 |
|:-----|:-----|
| 遥控/键盘发固定 vx（建议 0.3 m/s），直线走 5 m（贴纸标记） | 终点两路里程计 x、y；实测距离 |

**合格**：
- 距离误差 ≤ 3%（5 m 误差 ≤ 0.15 m）
- 终点横向偏移 ≤ 0.1 m
- EKF 与纯轮速距离读数差异 ≤ 0.05 m（此时融合值应以轮速为准）

> 若两者都偏差 > 3%：大概率是 `speed_scale` 不准，回头做速度标定
> （handover 中的可选项，`scripts/measure_r2_ticks.py`）。

### 4.3 原地旋转测试（90° / 360°）

| 操作 | 记录 |
|:-----|:-----|
| 原地转 90°（量角器/手机罗盘校），停稳读 yaw；再转 360° | 两路 yaw 读数；IMU yaw 单读 |

**合格**：
- 转 90°：yaw 误差 ≤ 2°
- 转 360°：yaw 误差 ≤ 5°
- 旋转停止后 10s，yaw 保持稳定（无回弹/缓慢漂移）
- **重点**：纯轮速在此步表现应差于 EKF（打滑），正是融合的意义所在

### 4.4 矩形闭环测试（2 m × 2 m）

| 操作 | 记录 |
|:-----|:-----|
| 沿 2 m × 2 m 矩形走一圈（每边直行 + 角上原地转 90°），回起点 | 终点两路 (x, y) 读数 vs 实测回位偏差 |

**合格**：闭环位置误差 ≤ 0.3 m（总路程 8 m 的 ~4%），且 EKF 优于纯轮速。

### 4.5 综合判定

| 判定 | 条件 |
|:-----|:-----|
| ✅ Phase 1 收尾 | 4.1~4.4 全部合格 |
| ◇ 部分通过 | 4.1/4.3 通过但 4.2 距离偏差 > 3% → 先做速度标定再复测 |
| ❌ 未通过 | EKF 不如纯轮速或日志异常 → 回查修复项，记录现象到 debug_log |

---

## 五、验证后收尾

- [ ] 把 4.1~4.4 实测数据（表格）回填本节，或录入 [03-current_state.md](../../doc/03-current_state.md)
- [ ] 更新 [02-progress.md](../../doc/02-progress.md)：Phase 1 → 100% ✅
- [ ] 踩坑记录写入 `debug_log.md`（本目录新建，如未存在）
- [ ] 同步 Obsidian 镜像（cp 覆盖）

---

## 六、遗留问题

- 速度标定（`speed_scale`）可选做，若 4.2 距离偏差大则必须做
- EKF 的 yaw 完全依赖 IMU（无磁力计），长时间运行时漂移风险 → 动态过程靠 ZUPT 兜底
- IMU 重启后 yaw 重置为 0：重启 IMU 时需同时重启 EKF，保证 yaw 对齐
