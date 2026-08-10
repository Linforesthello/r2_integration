# R2 集成 · 状态交接

> 最后更新: 2026-08-10
> 当前进度: Phase 0 ✅ 100%｜Phase 1 ✅ 85%（08-09 z 漂移修复；yaw 偏差预案未实施）｜Phase 2 ✅ 100%｜Phase 3 ⏳ D2 建图跑通但重影
> 下一阶段: KISS 帧率调参 → 重录建图 → Nav2
>
> **部署环境**：N97 Mini PC（192.168.1.210，Ubuntu 22.04 + Humble），enp1s0: 10.18.18.20/24
> 开发环境：VM（lin-virtual-machine，192.168.1.204）；VM→N97 SSH 免密可用
> 网络：VLP-16 雷达 IP **10.18.18.6**（2026-08-02 从 10.10.3.6 迁移）

---

## 一、当前进度总览

| Phase | 目标 | 状态 | 说明 |
|:------|:-----|:----:|:-----|
| 0 | 底盘 ROS2 + CAN 控制 | ✅ 100% | 四全向轮，全命令可用 |
| 1 | G354 IMU + 轮速 EKF 融合 | ✅ 85% | 实车验证完成（08-06）；z 漂移修复（08-09）；yaw 偏差预案未实施 |
| 2 | VLP16 + KISS-ICP SLAM | ✅ 100% | 驱动+里程计+键盘建图全跑通（8-02） |
| 3 | VLP16 + Nav2 导航 | ⏳ 0% | D2 离线建图已跑通但重影（KISS 帧率 3.6Hz），见 [retrospect/2026-08-09_map_double_ghost.md](retrospect/2026-08-09_map_double_ghost.md) |
| 4 | D435 + Jetson 视觉 | ⏳ 0% | — |
| 5 | 气动+异常+编排 | ⏳ 0% | — |

**8-02 核心成果**：EKF/TF 融合链路 7 个问题全部解决（详见
[retrospect/2026-08-02_ekf_tf_fusion_fix.md](retrospect/2026-08-02_ekf_tf_fusion_fix.md)）。
**8-09 新增**：EKF z 漂移已修复（two_d_mode）；yaw 偏差确认（未解决）；D2 离线建图跑通但重影
（KISS 帧率 3.6Hz，性能瓶颈）——详见 §五 与 §六。

---

## 二、当前运行状态（2026-08-02 19:21 实测）

### 2.1 运行节点（N97，全套 12 个）

```
ekf_filter_node / g354_imu_node / kiss_icp_node / r2_chassis_node /
r2_teleop_keyboard / robot_state_publisher / static_transform_publisher(base_link→imu_link) /
velodyne_driver_node / velodyne_transform_node / velodyne_laserscan_node / rviz / rqt
```

### 2.2 关键话题与数据表现（实测 hz）

| 话题 | 频率 | 备注 |
|:-----|:-----|:-----|
| /imu/data | ~100Hz（std 0.0025）✅ | G354，稳定 |
| /odometry/filtered | ~30Hz ✅ | EKF 融合输出（08-09 降频 50→30 缓解 CPU） |
| /odom_wheels | ~50Hz（std 0.002）✅ | 轮速里程计 |
| /velodyne_points | ~9.9Hz ✅（08-09 bag 实测，max 间隔 0.121s） | 08-02 的掉帧现象**未复现**，此项关闭 |
| /kiss/odometry | ~3.6Hz ⚠️（08-09 bag 实测） | **雷达 10Hz 输入吞掉 64%**：p50 0.19s / p90 0.6s / max 1.95s，纯处理瓶颈（详见 §六） |
| /kiss/points 等 | visualize:=true 时发布 | 前缀 **/kiss/**（非 /kiss_icp/） |

### 2.3 数据表现（静止实测）

- EKF 姿态与 IMU 姿态几乎一致（四元数 0.0226/0.0283/0.0172/0.9992）→ 融合正确
- EKF position.z = 0.000000（08-09 two_d_mode 修复后）
- odom→base_link 单一发布者（chassis publish_tf=false）✅

---

## 三、启动命令（N97，按顺序，分终端）

```bash
# 终端 0: CAN 总线
python3 ~/Lin_workspace/command/can_command.py

# 终端 1: 雷达（device_ip 10.18.18.6，600rpm/10Hz）
ros2 launch ~/.ros/velodyne_n97.launch.py

# 终端 2: KISS-ICP（visualize:=true 发 /kiss/points 并带 RViz；false 则无点云话题）
source ~/kiss_icp_ws/install/setup.bash
ros2 launch kiss_icp odometry.launch.py \
  topic:=/velodyne_points base_frame:=velodyne \
  use_sim_time:=false visualize:=true   # ⚠️ use_sim_time 必须显式 false

# 终端 3: 底盘（publish_tf:=false 让 EKF 发 TF；独立使用可不带）
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch r2_bringup chassis.launch.py publish_tf:=false

# 终端 4: IMU（启动后静止 3s 等校准，校准期不可动）
#   mount_axes:=y_front_x_left_z_down 是 R2 的 G354 出厂轴定义（x左/y前/z下），见 doc/phase0/sensor-mount.md
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch g354_imu_driver g354_rviz.launch.py rviz:=false serial_port:=/dev/ttyACM1 mount_axes:=y_front_x_left_z_down

# 终端 5: EKF（必须在 IMU 校准完成后启动；重启 IMU 必须同时重启 EKF）
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch r2_bringup ekf.launch.py

# 终端 6: WASD 键盘遥控（python3 直启，绕开本环境 libexec 布局问题）
python3 ~/Lin_workspace/r2_integration/r2_bringup/r2_bringup/teleop_keyboard.py
# 或一键（GNOME 终端环境）:
# bash ~/Lin_workspace/r2_integration/scripts/r2_startup.sh
```

**IMU 独立看姿态**：`ros2 run rviz2 rviz2` → Fixed Frame 填 `imu_link` →
Add → By display type → Imu（需已装 `ros-humble-rviz-imu-plugin`）→ Topic `/imu/data` → QoS **Reliable**。

---

## 四、关键配置（位置 + 当前值）

| 配置 | 位置 | 当前值 |
|:-----|:-----|:-------|
| EKF 融合 | `r2_bringup/config/ekf.yaml` | frequency 30、two_d_mode: true、az noise 1e-6；odom0_config **yaw=false**（yaw 偏差根因，预案 [phase1/ekf-yaw-plan.md](phase1/ekf-yaw-plan.md)）⚠️ launch 加载 **install 副本**，改后须 build 或手动同步 |
| 底盘 TF | `chassis.launch.py` | `publish_tf:=false`（EKF 场景），默认 true |
| 静态 TF | `ekf.launch.py` | `base_link→imu_link` 单位变换 |
| KISS-ICP | `~/kiss_icp_ws/src/kiss_icp/config/config.yaml` | max_range 30 / min_range 0.5 / voxel_size 0.2（8-02 调优，备份 .bak_20260802） |
| 雷达驱动 | `~/.ros/velodyne_n97.launch.py` | device_ip 10.18.18.6（备份 .bak_20260802） |
| 底盘参数 | `r2_bringup/config/r2_params.yaml` | 全实车标定值（speed_scale 94.5 等） |

---

## 五、本次联调结果与现象（2026-08-02）

### 已解决（7 问题，详见 retrospect 文档）

| 问题 | 根因 | 修复 |
|:-----|:-----|:-----|
| 网络迁移 10.10.3.x→10.18.18.x | 规划调整 | device_ip 同步更新 |
| KISS-ICP 里程计不走 | launch 默认 use_sim_time=true | 显式 false |
| imu_link 标红 | TF 树无 imu_link | ekf.launch.py 加 static TF |
| /imu/data 灰色 | N97 未装 rviz_imu_plugin + QoS | 装插件 + QoS Reliable |
| 点云/IMU 震动"打架" | odom→base_link 双发布者 | chassis 加 publish_tf 参数 |
| chassis 启动崩溃 | 协方差 int 非 float | 0→0.0 |
| EKF yaw 大跳 + z 漂 12m | N97 ekf.yaml 坏配置（6 值 vs 15 值） | 同步正确配置 |

### 8-03 新增：IMU 轴定义修复（✅ 已完成）

G354 **出厂轴定义为 x 左/y 前/z 下**（模块正放安装），与驱动假设的标准朝向不符 →
EKF 姿态错乱（"轴指向天空"、动一下姿态大翻转）。驱动修复三处（[imu_node.py](../../g354_driver/g354_imu_driver/imu_node.py)）：

1. +`mount_axes` 参数与轴映射（`y_front_x_left_z_down`）
2. `init_from_accelerometer` w 方向符号 bug（被 z 朝下双负抵消掩盖）
3. Mahony a/v 符号约定不一致 → 翻转伪稳定点（"过肩摔"）

实车验证：左转/右转/左倾/右倾全部正确，RViz odom→base_link 姿态正常。
安装定义见 [phase0/sensor-mount.md](phase0/sensor-mount.md)。
**启动纪律**：IMU 校准完成（Init quat）后才可启动 EKF；EKF 在 IMU 校准前启动会输出 NaN。

### 8-09 新增：z 漂移修复 ✅ / yaw 偏差 ⚠️ / 地图重影 ⚠️

- **z 漂移修复 ✅**：15 维 EKF 中无测量约束的 z/vz/az 受姿态-速度耦合 + 积压放大 → 漂 55.7m；
  `two_d_mode: true` + az noise 1e-6 修复，TF z 恒 0、30Hz 正常。详见
  [retrospect/2026-08-09_ekf_z_drift_fix.md](retrospect/2026-08-09_ekf_z_drift_fix.md)
- **yaw 偏差 ⚠️（未解决）**：filtered yaw = IMU 纯积分（f-i 恒 0.1°），起点偏置随机 6~10°、运动峰值 ±14°；
  预案（方案①轮速开放 yaw）已写好未实施，见 [phase1/ekf-yaw-plan.md](phase1/ekf-yaw-plan.md)
- **地图重影 ⚠️（未解决）**：D2 离线建图链路跑通但产出严重重影；根因 KISS 帧率 3.6Hz（§二）
  帧间 0.5~0.7s 空窗漂移 + 20-29m 远点放大。详见
  [retrospect/2026-08-09_map_double_ghost.md](retrospect/2026-08-09_map_double_ghost.md)

### 遗留现象（算法本底，非故障）

- **KISS-ICP 静止/运动均有毫米~厘米级抖动**：纯激光配准本底（无 IMU 融合）
- **旋转时点云更新滞后，静止后恢复**：旋转运动畸变，deskew 用上一帧匀速外推校不准
- 已调优参数缓解，未根治；**长期方案：换带 IMU 的 LIO（推荐 FAST-LIO2，VLP-16 已原生支持）**

---

## 六、遗留与待办

✅ 已关闭（历史项）：
- Phase 1 EKF 实车验证（08-06 完成）
- z 轴 process noise 漂移（08-09 two_d_mode 修复；回归项见下）
- IMU/雷达坐标基准与雷达高度冲突（08-06 定案 base_joint 0.13 / velodyne_joint 0.56）
- 雷达掉帧调查（08-09 bag 实测 9.9Hz 稳定，未复现）

待办（按优先级）：
- [ ] **KISS 帧率 3.6Hz**（08-09 暴露，主线）：CPU 瓶颈（N97 4 核低功耗 + 全套节点），
      KISS 本地图越积越稠密配准变慢（[社区佐证 issue #152](https://github.com/PRBonn/kiss-icp/issues/152)）。
      作者推荐调参：**max_range 30→15~20m**（主要参数，代价=丢远墙特征）、**voxel_size 0.2→0.25/0.3**；
      采集时 N97 不开 rviz2。改后重录复测
- [ ] **D2 重影消除**：帧率解决后重录重验；验收指标待定量化（轮廓清晰度 + 闭环误差）
- [ ] **yaw 偏差**：实施预案方案①（odom0_config yaw=false→true），验证标准见 [phase1/ekf-yaw-plan.md](phase1/ekf-yaw-plan.md)
- [ ] **z 回归项**：slip 场景剧烈加减速 z 漂 +2.5m（08-05 遗留）在 two_d_mode 下复测
- [ ] 同步收尾：最新提交 857d57a，**N97 待 `git pull`**（08-10 网络不通，恢复后补）
- [ ] VNC 开机自启（N97 重启后远程桌面不丢）
- [ ] FAST-LIO2 评估（长期，VLP-16 原生支持，接 G354 解决旋转痛点）— VM 先编译验证
- [ ] 可选：VLP-16 rpm 600→1200（20Hz）试验（帧内畸变减半）
- [ ] waypoint 雷达闭环（基于 /kiss/odometry 自主行走）

---

## 七、阶段性总结（Phase 0 → 2）

**已完成的能力**：
- 底盘：ROS2 + CAN 全向轮控制、里程计、TF、键盘遥控（WASD 一键一状态）
- 感知：VLP-16 驱动 + KISS-ICP 3D 里程计 + 实时点云建图（车在点云地图中移动 ✅）
- 融合：G354 IMU + 轮速 → EKF 融合链路完整可用（/odometry/filtered 稳定 50Hz）

**关键结论**：
1. KISS-ICP 适合建图/演示，旋转性能和精度受纯激光本质限制——后续自主导航建议换 LIO
2. EKF 融合是底盘导航的基础（yaw 来自 IMU，位置来自轮速）
3. 本阶段 7 个问题的共性教训：跨机器同步必须全覆盖（含配置）、第三方 launch 默认值必须实测、配置不合法可能不报错
4. **N97 单机跑全套是性能瓶颈**：EKF 降频 + KISS 吞帧同源，CPU 余量优先于功能扩展

**资源状态**：VM 与 N97 代码同步基线 = 提交 857d57a（N97 待 pull）；
bag 分析副本在 VM `~/Lin_workspace/bags/raw/`（ekf_pure_0809_2013 / ekf_yaw_test_0809 / map_run_0809_2133）。

---

## 八、相关文档索引

- 排障全记录：`retrospect/2026-08-02_ekf_tf_fusion_fix.md`（7 问题）｜`retrospect/2026-08-09_ekf_z_drift_fix.md`（z 漂移）｜`retrospect/2026-08-09_map_double_ghost.md`（重影）
- 进度看板：`02-progress.md` ｜ 状态快照：`03-current_state.md`
- EKF yaw 预案：`phase1/ekf-yaw-plan.md` ｜ SLAM 方案探索：`retrospect/vlp16_slam_exploration.md`
- W1 建图手册：`minimal-loop/w1-operation.md`（D1~D5，含 D2 执行记录）
- 底盘定义：`phase0/chassis_definition.md` ｜ 键盘控制修复：`retrospect/2026-07-31_teleop_keyboard_fix.md`
