# R2 集成 · 状态交接

> 最后更新: 2026-08-24
> 当前进度: Phase 0 ✅ 100%｜Phase 1 ✅ 95%（08-12 yaw 方案①通过）｜Phase 2 ✅ 100%｜Phase 3 ⏳ 25%（首闭环 08-15；降额过缝验证 08-17，全速暂缓）
> 下一阶段: Nav2 避障实测 → 长时间稳定性（全速验证暂缓，保持降额现状）
> 基础设施: 08-15 VLP-16 运行物抽包 r2_sensors（launch/r2.urdf 移入，dds 留 r2_bringup，启动命令见 §三）；08-14 两机 git 同步统一；VM 单机跑通 VLP-16（DDS 根因修复，见 §五 8-14）；08-24 N97 风扇可命令行调速（IT8613E + it87 force_id=0x8622，sysfs pwm2，见 §四/§五）
>
> **部署环境**：N97 Mini PC（192.168.1.210，Ubuntu 22.04 + Humble），enp1s0: 10.18.18.20/24
> 开发环境：VM（lin-virtual-machine，192.168.1.204）；VM→N97 SSH 免密可用
> 网络：VLP-16 雷达 IP **10.18.18.6**（2026-08-02 从 10.10.3.6 迁移）

---

## 一、当前进度总览

| Phase | 目标 | 状态 | 说明 |
|:------|:-----|:----:|:-----|
| 0 | 底盘 ROS2 + CAN 控制 | ✅ 100% | 四全向轮，全命令可用 |
| 1 | G354 IMU + 轮速 EKF 融合 | ✅ 95% | 实车验证完成（08-06）；z 漂移修复（08-09）；yaw 偏差方案①实施并验证通过（08-12）；仅剩 slip 剧烈加减速严格复测 |
| 2 | VLP16 + KISS-ICP SLAM | ✅ 100% | 驱动+里程计+键盘建图全跑通（8-02） |
| 3 | VLP16 + Nav2 导航 | ⏳ 25% | D2 重影消除（08-11）；**D4 复用验证 + Nav2 首闭环跑通**（08-15，降额 0.2m/s），见 [retrospect/2026-08-15_nav2_bringup.md](retrospect/2026-08-15_nav2_bringup.md)；**降额过缝验证通过**（08-17，inflation 0.30，无碰撞），见 [retrospect 08-17](retrospect/2026-08-17_nav2_initialpose_inflation_fix.md)；全速验证暂缓，待避障实测 |
| 4 | D435 + Jetson 视觉 | ⏳ 0% | — |
| 5 | 气动+异常+编排 | ⏳ 0% | — |

**8-02 核心成果**：EKF/TF 融合链路 7 个问题全部解决（详见
[retrospect/2026-08-02_ekf_tf_fusion_fix.md](retrospect/2026-08-02_ekf_tf_fusion_fix.md)）。
**8-09 新增**：EKF z 漂移已修复（two_d_mode）；yaw 偏差确认（未解决）；D2 离线建图跑通但重影
（KISS 帧率 3.6Hz，性能瓶颈）。
**8-11 新增**：KISS 帧率根因实锤 = N97 CPU `powersave` 治理器低频；切 `performance` 后帧率恢复
9.5Hz，重录重跑**重影消除**——详见 §五 与 §六。
**8-12 新增**：yaw 偏差方案①（轮速开放 yaw）实施并验证通过（起点 0.00°/峰值 0.07°，含 90°/190°
转弯），见 [ekf-yaw-plan.md](phase1/ekf-yaw-plan.md) 验证结果段；stage_0812_2111 保守留档 bag 地图
对照生成（`bags/stage_0812_map/`）。
**8-17 新增**：降额参数实车验证：inflation_radius 0.55→0.30（local/global）修复窄缝 costmap 全灰过不去，
实测**基本无碰撞、能通过过道**（此前明明有路不通过）；**全速验证暂缓，保持降额现状**（08-17 决策），
见 [retrospect 08-17](retrospect/2026-08-17_nav2_initialpose_inflation_fix.md)。

---

## 二、当前运行状态（2026-08-02 19:21 实测）

### 2.1 运行节点（N97，全套 12 个）

```
ekf_filter_node / g354_imu_node / kiss_icp_node / r2_chassis_node /
r2_teleop_keyboard / robot_state_publisher / static_transform_publisher(base_link→imu_link) /
velodyne_driver_node / velodyne_transform_node / rviz / rqt
（velodyne_laserscan_node 08-15 起停用：/scan 暂无消费者，Nav2 接入时恢复，见 [retrospect 08-15](retrospect/2026-08-15_velodyne_perf_tuning.md)）
```

### 2.2 关键话题与数据表现（实测 hz）

| 话题 | 频率 | 备注 |
|:-----|:-----|:-----|
| /imu/data | ~100Hz（std 0.0025）✅ | G354，稳定 |
| /odometry/filtered | ~30Hz ✅ | EKF 融合输出（08-09 降频 50→30 缓解 CPU） |
| /odom_wheels | ~50Hz（std 0.002）✅ | 轮速里程计 |
| /velodyne_points | ~9.3~9.4Hz ✅（08-15 实测稳定） | 08-15 调优（organize_cloud=false + max_range 40m）后稳定，此前 7.7~8.5Hz，详见 [retrospect 08-15](retrospect/2026-08-15_velodyne_perf_tuning.md) |
| /kiss/odometry | ~9.5Hz ✅（08-11 实测，切 performance 治理器后） | **修复**：08-09 时 3.6Hz（CPU powersave 低频，隔帧处理），详见 §六 |
| /kiss/points 等 | visualize:=true 时发布 | 前缀 **/kiss/**（非 /kiss_icp/） |

### 2.3 数据表现（静止实测）

- EKF 姿态与 IMU 姿态几乎一致（四元数 0.0226/0.0283/0.0172/0.9992）→ 融合正确
- EKF position.z = 0.000000（08-09 two_d_mode 修复后）
- odom→base_link 单一发布者（chassis publish_tf=false）✅

---

## 三、启动命令（N97，按顺序，分终端）

> **前置（每次开机必做）**：切 CPU 性能模式。N97 重启后治理器恢复 `powersave`，
> KISS 会掉回 3.6Hz 重影复现（见 §六）。

```bash
# 前置 0: CPU 性能模式
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
# 检查（应输出 performance）:
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor

# 前置 1（可选）: 风扇固定转速（08-24 起；驱动不持久化，重启后需重跑，完整指令见 [retrospect 08-24](retrospect/2026-08-24_n97_fan_control.md)）
sudo modprobe it87 force_id=0x8622
echo 1 | sudo tee /sys/class/hwmon/hwmon4/pwm2_enable    # 切手动（只需设一次）
echo 200 | sudo tee /sys/class/hwmon/hwmon4/pwm2          # 设转速（0-255），即刻生效
# 恢复自动: echo 2 | sudo tee /sys/class/hwmon/hwmon4/pwm2_enable（重启兜底）
# 查询当前转速: cat /sys/class/hwmon/hwmon4/fan2_input
# 查询当前自动信息: cat /sys/class/hwmon/hwmon4/pwm{1,2,3,4,5}_enable


# 终端 0: CAN 总线
python3 ~/Lin_workspace/command/can_command.py

# 终端 1: 雷达（device_ip 10.18.18.6，600rpm/10Hz）
#   ⚠️ 08-15 起 launch 在 r2_sensors 包：先 git pull + colcon build（launch 加载 install 副本）
ros2 launch r2_sensors velodyne.launch.py

# 终端 2: KISS-ICP（visualize:=true 发 /kiss/points 并带 RViz；false 则无点云话题）
#   ⚠️ Nav2 场景不启动 KISS（08-15 决策：AMCL 定位不需要，省 N97 CPU），跳到终端 7
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

# 终端 6: WASD 键盘遥控（08-11 P3 setup.cfg 修复后 ros2 run 可直接启动，无需 python3 直启）
ros2 run r2_bringup teleop_keyboard
# 或一键（GNOME 终端环境）:
# bash ~/Lin_workspace/r2_integration/scripts/r2_startup.sh

# 终端 7: Nav2 导航（08-15 起；首次实机用降额参数 nav2_params_low，KISS 不启动）
#   ⚠️ 08-17 起参数含 inflation_radius 0.30 修复（窄缝过不去）；初始位姿：启动初期设偏可静止重设 1~2 次（08-25 实车验证有效），导航运行中不要重设（多次设→map 重叠）；每次设完先动一下确认收敛，见 [retrospect 08-17](retrospect/2026-08-17_nav2_initialpose_inflation_fix.md)
#   操作: rviz 出现后 2D Pose Estimate(P) 设初始位姿 → Navigation2 Goal(G) 发目标
#   注意: 设位姿前 planner/costmap 报 "map frame does not exist" 是正常等待噪音；
#         车静止时 AMCL 不发布 /amcl_pose 与粒子（update_min_d/a 阈值设计），动起来才有
n97
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch r2_bringup nav2.launch.py \
  map:=/home/lin/maps/map_0815_clean.yaml \
  params_file:=/home/lin/Lin_workspace/r2_integration/install/r2_bringup/share/r2_bringup/config/nav2_params_low.yaml \
  rviz:=true

或者vmware
ros2 launch r2_bringup nav2.launch.py   map:=/home/lin/Lin_workspace/bags/maps/d4/map_0815_clean.yaml   params_file:=/home/lin/Lin_workspace/r2_integration/install/r2_bringup/share/r2_bringup/config/nav2_params_low.yaml   rviz:=true
```




**IMU 独立看姿态**：`ros2 run rviz2 rviz2` → Fixed Frame 填 `imu_link` →
Add → By display type → Imu（需已装 `ros-humble-rviz-imu-plugin`）→ Topic `/imu/data` → QoS **Reliable**。

---

## 四、关键配置（位置 + 当前值）

| 配置 | 位置 | 当前值 |
|:-----|:-----|:-------|
| EKF 融合 | `r2_bringup/config/ekf.yaml` | frequency 30、two_d_mode: true、az noise 1e-6；odom0_config **yaw=true**（08-12 方案①开放，验证通过，见 [phase1/ekf-yaw-plan.md](phase1/ekf-yaw-plan.md)）⚠️ launch 加载 **install 副本**，改后须 build 或手动同步 |
| 底盘 TF | `chassis.launch.py` | `publish_tf:=false`（EKF 场景），默认 true |
| 静态 TF | `ekf.launch.py` | `base_link→imu_link` 单位变换 |
| KISS-ICP | `~/kiss_icp_ws/src/kiss_icp/config/config.yaml` | max_range 30 / min_range 0.5 / voxel_size 0.2（8-02 调优，备份 .bak_20260802） |
| 雷达驱动 | `r2_sensors velodyne.launch.py` | device_ip 10.18.18.6；08-15 起 launch 覆写 organize_cloud=false、max_range=40m（见 [retrospect 08-15](retrospect/2026-08-15_velodyne_perf_tuning.md)） |
| Nav2 膨胀参数 | `r2_bringup/config/nav2_params_low.yaml` | inflation_radius **0.30** / cost_scaling_factor 3.0（08-17 从 0.55 收窄，修复窄缝过不去，见 [retrospect 08-17](retrospect/2026-08-17_nav2_initialpose_inflation_fix.md)）；⚠️ **全速版 `nav2_params.yaml` 仍是 0.55**，切回前须先同步 |
| 底盘参数 | `r2_bringup/config/r2_params.yaml` | 全实车标定值（speed_scale 94.5 等） |
| N97 风扇（硬件层） | `it87` 驱动 + `/sys/class/hwmon/hwmon4/` | 风扇在 IT8613E **fan2** 通道；调速 `echo 1 > pwm2_enable` + `echo N > pwm2`（0-255），撤销 `echo 2 > pwm2_enable`（重启兜底）；实测 150→2537 / 200→3068 / 255→3534 RPM；**不持久化**，完整指令与速查见 [retrospect 08-24](retrospect/2026-08-24_n97_fan_control.md) 与 [n97info.md](n97info.md) |

---

## 五、历史事件索引（详情见 retrospect）

> 交接只看结论；完整排障/修复记录一律在 retrospect（单一事实来源，见 standards.md）。

| 日期 | 结论 | 详情 |
|:---|:---|:---|
| 08-24 | **FAST-LIO2 N97 部署 + 实车验证全项通过**：IMU Initial Done + /Odometry 跟踪 + 左转 91.9°/右转 −89.4°（误差<2°，KISS 基线 163°）+ 直线平移 169cm 实测误差 0.5%（2D/3D 双口径 0.51%/0.58%，地面不平前提）；外参实测 [0.36,0.035,0.47]；⚠️ 编译必须 `PATH=/usr/bin:$PATH`（cmake 4.4 坑）；TF 桥未做 | [fastlio2-n97-deploy.md](fastlio2-n97-deploy.md)、[retrospect 08-24 验证数据](retrospect/2026-08-24_fastlio2_verification.md) |
| 08-24 | **N97 风扇调速打通**：ACPI thermal/EC 逆向均死路（cur_state 写入曾致停转、撤销无效）→ sensors-detect 找到 IT8613E → 主线 it87 失败 → `force_id=0x8622` 突破；sysfs pwm2 即刻调速可撤销（实测 100→1956~255→3534 RPM）；**暂不持久化** | [retrospect](retrospect/2026-08-24_n97_fan_control.md) |
| 08-17 | 降额参数过缝验证：inflation_radius 0.55→0.30 修复窄缝全灰过不去（实测基本无碰撞、能过过道）；多次设初始位姿致 map 重叠诊断留档；**全速验证暂缓，保持降额现状** | [retrospect](retrospect/2026-08-17_nav2_initialpose_inflation_fix.md) |
| 08-15 | velodyne 抽包 r2_sensors（launch/urdf 移出 r2_bringup，启动命令改为 `ros2 launch r2_sensors velodyne.launch.py`）；g354 补 ament index marker | [retrospect](retrospect/2026-08-15_r2_sensors_extract.md) |
| 08-15 | **干净 bag 重录（165547：9.63Hz 零空窗）+ 人形块过滤工具 filter_person_blobs.py**（空地散点=建图在场的人），清洗版导航图就绪；同日长录 170058 KISS 漂移 163° 按失败样本归档 | [clean_bag](retrospect/2026-08-15_clean_bag_rerecord.md)、[kiss_drift](retrospect/2026-08-15_kiss_drift_170058.md) |
| 08-15 | VLP-16 链路性能调优：points 7.7~8.5 → 9.3~9.4Hz 稳定；根因=雷达供电不足 + 转换节点 CPU（organize_cloud/max_range） | [retrospect](retrospect/2026-08-15_velodyne_perf_tuning.md) |
| 08-15 | 双录对比：长录 170058 KISS 整程漂移（旋转+38 空窗→航向漂 163°、闭环 8.08m、地图 1627 碎片块），不可作建图底图；短录 165547 可用（map_0815_clean） | [retrospect](retrospect/2026-08-15_kiss_drift_170058.md) |
| 08-02 | EKF/TF 融合链路 7 问题全解决（网络迁移/use_sim_time/imu_link/QoS/双发布者/协方差/ekf.yaml） | [retrospect](retrospect/2026-08-02_ekf_tf_fusion_fix.md) |
| 08-03 | G354 IMU 轴定义修复（mount_axes=y_front_x_left_z_down）；启动纪律：IMU 校准后才可起 EKF | [sensor-mount.md](phase0/sensor-mount.md) |
| 08-05 | 底盘里程计修复 + EKF 过程噪声 225 值矩阵排障；IMU 协方差病态→EKF NaN | [chassis_ekf](retrospect/2026-08-05_chassis_ekf_debug.md)、[cov_nan](retrospect/2026-08-05_imu_covariance_ekf_nan.md) |
| 08-09 | EKF z 漂移修复（two_d_mode + az noise 1e-6，TF z 恒 0） | [retrospect](retrospect/2026-08-09_ekf_z_drift_fix.md) |
| 08-11 | KISS 帧率 3.6→9.5Hz（N97 CPU performance 治理器）→ 建图重影消除；r2_bringup 审查 P1~P10 全修复 | [kiss_frame](retrospect/2026-08-11_kiss_frame_rate_fix.md)、[review](retrospect/2026-08-11_r2_bringup_code_review.md) |
| 08-12 | EKF yaw 方案①（odom0_config yaw=true）验证通过：起点 0.00°/峰值 0.07°（含 90°/190° 转弯） | [ekf-yaw-plan.md](phase1/ekf-yaw-plan.md) |
| 08-13 | 分层 3D→2D 导航层生成；建图链路排查（重影根因 + time 字段之谜） | [layer_map](retrospect/2026-08-13_layer_map_3d2d.md)、[map_chain](retrospect/2026-08-13_map_chain_investigation.md) |
| 08-14 | VM 单机跑通 VLP-16（bashrc 跨机 DDS 掐死本机发现 + daemon 缓存）；velodyne 运行物入库 r2_bringup（两机统一，消灭拷贝漂移） | [retrospect](retrospect/2026-08-14_vm_vlp16_dds_fix.md) |

### 遗留现象（算法本底，非故障）

- **KISS-ICP 静止/运动均有毫米~厘米级抖动**：纯激光配准本底（无 IMU 融合）
- **旋转时点云更新滞后，静止后恢复**：旋转运动畸变，deskew 用上一帧匀速外推校不准
- 已调优参数缓解，未根治；**长期方案：换带 IMU 的 LIO（推荐 FAST-LIO2，VLP-16 已原生支持）**

---

## 六、遗留与待办

✅ 已关闭（历史项）：
- Phase 1 EKF 实车验证（08-06 完成）
- z 轴 process noise 漂移（08-09 two_d_mode 修复；回归项见下）
- IMU/雷达坐标基准与雷达高度冲突（08-06 定案 base_joint 0.13 / velodyne_joint 0.56；**08-24 复测更新** base_link 离地 12cm / velodyne_joint 0.655，见 [sensor-mount.md](phase0/sensor-mount.md)）
- 雷达掉帧调查（08-09 bag 实测 9.9Hz 稳定，未复现）
- **KISS 帧率 3.6Hz**（08-11 修复）：CPU `powersave` 低频 → `performance` 后 9.5Hz，
      详见 [retrospect/2026-08-11_kiss_frame_rate_fix.md](retrospect/2026-08-11_kiss_frame_rate_fix.md)
- **D2 重影消除**（08-11 验证通过）：重录重跑地图结构清晰，对比图 `bags/maps/compare_0809_vs_0811_final.png`
- **r2_bringup 代码审查 P1~P10**（08-11 全部实施 + 实车验证，见 §五）
- **VLP-16 转换链路性能**（08-15）：供电不足根因 + organize_cloud/max_range 调优，points 7.7~8.5 → 9.3~9.4Hz 稳定，详见 [retrospect 08-15](retrospect/2026-08-15_velodyne_perf_tuning.md)

待办（按优先级）：
- [x] **performance 持久化**（08-11）：已入启动流程（§三 前置 0 步骤），每次开机手动执行；systemd 固化暂缓
- [x] **D4 地图复用验证**（08-15 完成）：`map_0815_clean` 加载回显一致 + **Nav2 首闭环跑通**（降额 0.2m/s），见 [retrospect/2026-08-15_nav2_bringup.md](retrospect/2026-08-15_nav2_bringup.md)（⚠️ 首测有擦碰，见下条）
- [x] **盲区/footprint 修复复测**（08-17 顺带覆盖）：雷达裁剪 min_range 0.5、local_costmap 6×6、footprint 0.84×0.66（撞障碍根因，见 [retrospect 五-2](retrospect/2026-08-15_nav2_bringup.md)）；08-17 降额实测基本无碰撞（[retrospect 08-17](retrospect/2026-08-17_nav2_initialpose_inflation_fix.md)）
- [ ] **Nav2 全速验证**（**暂缓 08-17，保持降额现状**）：后续切 `nav2_params.yaml`（0.5/0.3/0.8）前须先同步其膨胀参数（仍 0.55）再复测
- [ ] **Nav2 避障实测**：costmap 实时刷新已见（人体移动出膨胀圈），静态/动态障碍绕行 + 恢复行为实测
- [ ] **多次设初始位姿→map 重叠**（诊断 + 操作纪律见 [retrospect 08-17](retrospect/2026-08-17_nav2_initialpose_inflation_fix.md)）：待 N97 确认 AMCL 日志是否 "Ignoring initial pose"（后续点击无效），必要时加 `always_reset_initial_pose: true`；⚠️ 边界（08-25 定）：此问题指**导航运行中**反复设位姿；启动初期设偏后静止重设 1~2 次属正常修正（08-25 实车验证有效，见终端 7 纪律）
- [x] **yaw 偏差**（08-12 完成）：方案①（odom0_config yaw=true）实施并验证通过，见 [phase1/ekf-yaw-plan.md](phase1/ekf-yaw-plan.md)
- [ ] **z 回归项**：slip 场景剧烈加减速 z 漂 +2.5m（08-05 遗留）复测——08-12 转弯/直行全程 z 恒 0（two_d_mode 结构性钳位），仅"剧烈加减速"动作未严格复测
- [ ] VNC 开机自启（N97 重启后远程桌面不丢）
- [x] **FAST-LIO2 N97 部署 + 实车验证**（08-24 完成）：IMU Initial Done + /Odometry 跟踪 + 旋转 90° 误差<2°（KISS 基线 163°/38 空窗）+ **平移 169cm 实测误差 0.5%**（2D/3D 双口径 0.51%/0.58%，地面不平前提）；详见 [fastlio2-n97-deploy.md](fastlio2-n97-deploy.md) 与 [retrospect 08-24](retrospect/2026-08-24_fastlio2_verification.md)（原始数据）。⚠️ **N97 编译 fast_lio_ws 必须 `PATH=/usr/bin:$PATH colcon build`**（`~/.local/bin/cmake` 4.4 不兼容，报 callback_variant_）；extrinsic_T=[0.36,0.035,0.47] 已实测；TF 桥集成未做
- [ ] 可选：VLP-16 rpm 600→1200（20Hz）试验（帧内畸变减半）
- [ ] waypoint 雷达闭环（基于 /kiss/odometry 自主行走）
- [ ] N97 风扇驱动持久化（**08-24 用户决策暂不做**）：开机自动加载 it87（/etc/modprobe.d + /etc/modules-load.d），纯 OS 层不碰固件，删除即恢复出厂，见 [retrospect 08-24](retrospect/2026-08-24_n97_fan_control.md)

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

**资源状态**：VM 与 N97 代码同步基线 = 提交 fc778da（main，08-17，Nav2 膨胀参数 0.30）；
bag 分析副本在 VM `~/Lin_workspace/bags/raw/`（ekf_pure_0809_2013 / ekf_yaw_test_0809 /
map_run_0809_2133 / **map_run_0811_1925** / **ekf_yaw_v2_0812** / **stage_0812_2111** /
**map_run_20260815_165547** 干净包 / **map_run_20260815_170058** KISS 漂移失败样本 /
**nav2_first_loop** 首次闭环 bag，分析脚本 `bags/analysis/analyze_nav2_first_loop.py`）；截图
`bags/rviz_nav2_first_loop.png` / `_2.png`；地图产物
`bags/maps/map_run_0811_1925/`（ply/map.yaml）、`bags/maps/map_0815_clean/`（seg1_clean.ply +
layers_clean + 过滤对比图）与 `bags/maps/d4/`（map.yaml/map_run_0811_1925.pgm +
**map_0815_clean.{pgm,yaml}**，D4 部署副本 → N97 `~/maps/`）；
stage_0812 保守录制对照地图 `bags/stage_0812_map/`（pgm/yaml + raw.ply，对比图
`bags/raw/compare_0811_vs_0812.png`，留档未传 N97）。

---

## 八、相关文档索引

- 排障全记录：`retrospect/2026-08-02_ekf_tf_fusion_fix.md`（7 问题）｜`retrospect/2026-08-09_ekf_z_drift_fix.md`（z 漂移）｜`retrospect/2026-08-09_map_double_ghost.md`（重影留档）｜`retrospect/2026-08-11_kiss_frame_rate_fix.md`（帧率修复）｜`retrospect/2026-08-11_r2_bringup_code_review.md`（代码审查 P1~P10）｜`retrospect/2026-08-14_vm_vlp16_dds_fix.md`（VM 单机 DDS 修复）｜`retrospect/2026-08-15_velodyne_perf_tuning.md`（VLP-16 性能调优+供电根因）｜[08-17 初始位姿诊断+膨胀修复](retrospect/2026-08-17_nav2_initialpose_inflation_fix.md)｜[08-24 N97 风扇调速](retrospect/2026-08-24_n97_fan_control.md)（IT8613E force_id=0x8622 + pwm2，原始命令记录 [n97info.md](n97info.md)）
- 进度看板：`02-progress.md` ｜ 状态快照：`03-current_state.md`
- EKF yaw 预案：`phase1/ekf-yaw-plan.md` ｜ SLAM 方案探索：`retrospect/vlp16_slam_exploration.md`
- W1 建图手册：`minimal-loop/w1-operation.md`（D1~D5，含 D2 执行记录）
- 底盘定义：`phase0/chassis_definition.md` ｜ 键盘控制修复：`retrospect/2026-07-31_teleop_keyboard_fix.md`
