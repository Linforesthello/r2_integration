# FAST-LIO2 N97 实车部署手册

> 状态：✅ N97 已部署并实车验证通过（2026-08-24；旋转 90° 误差 <2°，对比 KISS 基线 163°）
> VM 侧验证记录：[2026-08-18_fast_lio2_deploy.md](retrospect/2026-08-18_fast_lio2_deploy.md)
> 目标：N97 实车跑通 FAST-LIO2，对比 EKF 里程计，为「FAST-LIO2 vs KISS-ICP+EKF」决策提供数据
> 关联：[vlp16_slam_exploration.md](retrospect/vlp16_slam_exploration.md)（方案对比）｜
> [2026-08-18_fastlio_laser_map_debug.md](retrospect/2026-08-18_fastlio_laser_map_debug.md)（排障经验）｜
> [ros2-qos-dds.md](ros2-qos-dds.md)（大消息验证方法）

---

## 一、部署顺序（总览）

```
1. 依赖安装（Livox-SDK2 + livox_ros_driver2）     §二
2. 编译 FAST_LIO（工作区 + 编译参数）              §二
3. velodyne.yaml 适配（R2 参数 + 外参量测）        §三
4. 实车链路验证（独立跑，不接 R2 TF 树）           §四/§六
5. 数据对比 → 决策（替代 KISS？）                 §六
6. （可选）TF 桥集成 R2                           §五
```

---

## 二、依赖与构建（N97 全量装，不是只拷源码）

**N97 没装过任何 Livox 依赖——最容易漏的环节。**

```bash
# 1. Livox-SDK2（livox_ros_driver2 编译依赖；build 目录需自建）
git clone --depth 1 https://github.com/Livox-SDK/Livox-SDK2.git ~/Livox-SDK2
cd ~/Livox-SDK2 && mkdir build && cd build
cmake .. && make -j4 && sudo make install

# 2. 官方 livox_ros_driver2（双版本设计，需生成 package.xml）
cd ~/fast_lio_ws/src
git clone --depth 1 https://github.com/Livox-SDK/livox_ros_driver2.git
cd livox_ros_driver2
cp package_ROS2.xml package.xml
cp -rf launch_ROS2/ launch/

# 3. FAST_LIO（ROS2 分支，--recursive 带 ikd-Tree 子模块）
git clone --branch ROS2 --recursive https://github.com/hku-mars/FAST_LIO.git ~/fast_lio_ws/src/FAST_LIO

# 4. 编译（⚠️ DISTRO_ROS 参数必带，漏了 LIVOX_INTERFACES NOTFOUND）
cd ~/fast_lio_ws && source /opt/ros/humble/setup.bash
colcon build --symlink-install --cmake-args -DROS_EDITION=ROS2 -DDISTRO_ROS=humble
```

| 注意点 | 说明 |
|:---|:---|
| 工作区独立 | 按 kiss_icp_ws 习惯用 `~/fast_lio_ws`，不混入 Lin_workspace |
| symlink-install | install 副本是符号链接：改 yaml 无需重编译，但**必须重启节点**（参数一次性读取） |
| velodyne.yaml 同步 | R2 适配 patch 留档 `doc/velodyne_r2.patch`，N97 `git apply`（git push → pull → apply） |
| **CMake 版本（N97 坑）** | N97 `~/.local/bin/cmake` 是 **4.4**（pip 装的，PATH 优先），与 fast_lio 的 CMakeLists 不兼容 → 编译报 `rclcpp callback_variant_ invalid field`（rclcpp 头文件正常，纯 CMake 版本差异）；**必须 `PATH=/usr/bin:$PATH colcon build`** 用 apt 3.22（08-24 实测：3.22 一次通过） |
| N97 编译时长 | VM 实测 fast_lio 1min12s，N97 约 1min22s，耐心等待 |

---

## 三、配置适配（外参是最大坑）

### 3.1 外参量测（部署前必做；官方方法有三层）

> 官方定义：`extrinsic_T`/`extrinsic_R` 是 **LiDAR 在 IMU body 系中的位姿**（FAST_LIO README L137-139；
> 不是 base_link 到雷达的 0.655m，08-24 定案）。三层官方方法（2026-08-18 核实）：

| 方法 | 说明 | R2 采用 |
|:---|:---|:---|
| **① 手动量测**（官方 README 默认路径 "found in the official manual"） | 尺子量平移 + 按安装方向推导旋转 | ✅ **已做（08-24 实车量测）**：`extrinsic_T = [0.36, 0.035, 0.47]`（x/y = G354(-36,-3.5)cm → VLP16(0,0)cm 位置差；z = 高差实测 47cm = G354 距地 30cm → VLP-16 距地 77cm）；`extrinsic_R` = **单位阵**——G354 数据已被 mount_axes 映射到车体系（sensor-mount.md 3.1"旋转为 0"），VLP-16 正装同为车体系朝向，无需旋转对齐 |
| **② 在线估计**（FAST-LIO 原生 `mapping.extrinsic_est_en`，laserMapping.cpp L831，默认 **true**） | 初始化阶段 IEKF 在线估计外参；官方 README 建议外参已知时设 false（更准/省算/防发散） | ✅ 保持 true：填好量测初值后让在线估计精化（前提：启动后激励运动充分） |
| **③ LI-Init**（官方推荐初始化工具，IROS 2022，[hku-mars/LiDAR_IMU_Init](https://github.com/hku-mars/LiDAR_IMU_Init)，README L108 官方指向；[项目主页](https://liuqian62.github.io/projects/li-init/)） | 同时标定 **外参 R+T + 时间偏移 + 重力 + IMU bias**；无需标定板/特定环境/初值；**支持 Velodyne 机械雷达**（Hesai/Velodyne/Ouster + Livox）；流程：静止 5s+ → 三维旋转+平移激励（自动检测充分度并指导）→ 输出 `Initialization_result.txt` → 自动切换进入 FAST-LIO；机械雷达配置 `cut_frame_num × orig_odom_freq = 30`、`mean_acc_norm = 9.805` | ⏸ 后续可选：⚠️ **官方版是 ROS1**（catkin_make/roslaunch），N97 为 Humble ROS2，需容器/移植评估；外参同装只需标一次，时间偏移视同步机制（如雷达断电重启）决定是否重标 |

**R2 结论**：① 量测填初值 + ② 保持 `extrinsic_est_en: true` 在线精化 = 两条官方路结合，先不动 LI-Init。
时间偏移 `time_offset_lidar_to_imu`（laserMapping.cpp L812）保持 0，实车若初始化失败/里程计跳变，第一个查它与时间单位。

### 3.2 时间戳

- `timestamp_unit: 2`（us）标注"先不动"——实车若初始化失败/里程计跳变，**第一个查时间单位与同步**（time_sync_en 保持 false，依赖各节点时钟）

### 3.3 发布开关（实车纪律）

| 开关 | 实车值 | 原因 |
|:---|:---|:---|
| `map_en` | **false（保持默认）** | 22MB/帧全量地图，1Hz=22MB/s 带宽且随建图增长；需要建图快照再改 true + 重启 |
| `pcd_save_en` | false | 验证期防大文件（全帧 pcd 可能内存崩溃） |
| `path_en` | true | 轨迹可视化 |

---

## 四、实车运行环境（N97 特殊性）

1. **performance governor 前置**（每次开机必做）：`echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor`
2. **CPU 是瓶颈**：N97 跑 KISS 9.5Hz 已紧张（此前 3.6Hz 重影教训）。FAST-LIO 用于**建图/里程计对比场景，替代 KISS**，不要两者同时跑；Nav2 场景仍 AMCL 定位，不跑 LIO
3. **DDS 环境**：N97 bashrc 有跨机 FASTRTPS 配置（10.18.18.x 网段）——单机跑注意话题发现（跨机配置会掐死本机发现，见 ros2-ops.md §1）
4. **启动顺序**：CAN → 雷达 → 底盘 → IMU（静止 3s 校准）→ **FAST-LIO 替代 EKF 场景**；IMU 重启纪律同 R2（G354 校准完成后才可起消费节点）
5. **IMU 话题共享**：FAST-LIO 订阅 /imu/data 与 EKF 可并存（广播），但对比场景只需 FAST-LIO 一条链路

---

## 五、TF 集成方案（验证期不接，集成期静态桥；方案已定 08-18）

**frame 语义（官方确认）**：FAST-LIO frame_id **写死** `camera_init`（odom 系）/`body`（IMU 系），
无 base_frame 参数（KISS-ICP 有；laserMapping.cpp L630-631 源码实测）；仅发布一对动态 TF
`camera_init→body`。维护者官方语义（[Issue #130](https://github.com/hku-mars/FAST_LIO/issues/130)）：
`map → camera_init → body` ≡ `map → odom → base_link`。

**三种社区做法**：

| 方案 | 做法 | 适用 |
|:---|:---|:---|
| **静态 TF 桥**（推荐，零改码） | 静态发布 `camera_init↔odom`（桥接）+ `body→base_link`（传感器→底盘外参）；⚠️ 必须走 `/tf_static`，transient 会中途断树 | 验证/集成阶段 |
| **源码改名** | laserMapping.cpp 里 `camera_init→odom`、`body→base_link` 直接替换 | 单机 hack，写死不通用 |
| **专用桥节点**（生产级） | 如 [Lidar_nav2_ws](https://github.com/Ikunio/Lidar_nav2_ws) 把 `/Odometry` 统一转成 Nav2 标准 `odom→base_footprint` TF | Nav2 长期集成 |

**R2 落地**：
1. **验证阶段不接 R2 TF 树**：FAST-LIO 独立链路，rviz 固定系选 `camera_init`（先做对比数据，现状不变）
2. **集成期**（对比决策后）：两个静态 TF 桥——`body(G354) → base_link`（量 G354 相对底盘中心）+ `camera_init → odom`；Nav2 的 `map→odom` 仍归 AMCL，R2 现有 TF 体系不动
3. 社区案例佐证：[sentry_navigation](https://github.com/BJHYZJ/sentry_navigation)（agilex+MID360+FAST-LIO2+move_base）TF 树即 `map→camera_init→body→body_foot(静态)`；[FAST-LIO-Localization](https://github.com/hku-mars/FAST_LIO_LOCALIZATION)（官方地图复用重定位：FAST-LIO 高频里程计 + 低频全局 ICP 消除累积误差）为未来弃 AMCL 的 3D 定位正路

---

## 六、验证流程（验收指标）

```bash
# 终端 1：雷达（同 R2 现有）
ros2 launch r2_sensors velodyne.launch.py

# 终端 2：IMU（mount_axes 同 R2）
ros2 launch g354_imu_driver g354_rviz.launch.py rviz:=false serial_port:=/dev/ttyACM1 mount_axes:=y_front_x_left_z_down

# 终端 3：FAST-LIO
cd ~/fast_lio_ws && source install/setup.bash
ros2 launch fast_lio mapping.launch.py config_file:=velodyne.yaml rviz:=false

# 终端 4：录制 + 对比（⚠️ 大消息话题勿用 hz 验证）
ros2 bag record /imu/data /velodyne_points /Odometry /path /tf
ros2 topic echo /Odometry --field pose.pose   # FAST-LIO 里程计
ros2 topic echo /odometry/filtered --field pose.pose   # EKF（若对比场景同跑）
```

**验收标准**：

| 项 | 指标 | 08-24 N97 实车结果 |
|:---|:---|:---|
| IMU 接入 | `IMU Initial Done`，无同步告警 | ✅ |
| /Odometry | 连续 8Hz+（雷达 10Hz），pose 随推车移动 | ✅ 连续发布；推车/转弯 pose 真实跟踪 |
| 平移漂移 | 直线段位移误差 vs 尺子实测（目标 <5%） | ✅ 前进 169cm（尺子，沿地面量）→ FAST-LIO 位移（起点/终点各取多帧均值，Δx 1.6985m / Δy 0.0206m / Δz +0.0638m）。⚠️ 场地地面不平（车真爬坡/过坎），z 变化 +6.4cm 为真实地形响应非漂移（FAST-LIO 3D 里程计，与 EKF two_d_mode 锁 z 的 2D 设计不冲突）；故双口径对比：**2D 平面 169.86cm（+0.86cm ≈ 0.51%）/ 3D 空间 169.98cm（+0.98cm ≈ 0.58%）**，均 <5% 达标；yaw 变化 ~3.4°（含地面不平真实偏转，非纯累积）。原始数据见 [2026-08-24_fastlio2_verification.md](retrospect/2026-08-24_fastlio2_verification.md) |
| 旋转漂移 | 90° 转弯后 yaw 误差（对比 KISS 基线 163°/38 空窗教训） | ✅ 左转 91.9°（误差 1.9°）/ 右转 −89.4°（误差 0.6°），z 稳定 ±4cm |
| 对比结论 | FAST-LIO2 vs KISS-ICP+EKF：建图质量/旋转表现 → 决策 | 旋转表现远优于 KISS（163°→<2°），决策建议见 §六 后 |

**安全前置**：首次实车推车/慢速，降额参数，失控先拍急停。

---

## 七、排障经验迁移（VM 已验证，直接可用）

1. **大消息话题不用 `ros2 topic hz`**（QoS 写死 best_effort，22MB 结构性假阴性"一直等"）；用 `echo --field header.stamp` 或 bag metadata 的 message_count
2. **yaml 键名以源码为准**：`publish.map_en` ≠ `map_pub_en`（get_parameter_or 按名查，键名错 = 参数等于没加）
3. **参数一次性读取**：改 yaml 必须重启节点
4. **bag 体积**：22MB/s 话题别长时间录（95.7s ≈ 1.5G）
5. **诊断日志逐段隔离**：配置→参数（param get）→执行（日志）→发布（echo），每段一个验证动作

---

## 八、检查清单（部署时勾选）

- [x] N97 装 Livox-SDK2 + livox_ros_driver2（§二）——08-24 ✅（含旧版 SDK 头文件不匹配坑：`kLivoxLidarDoubleEchoData` 未声明 → 重装新版解决）
- [x] FAST_LIO 编译通过（DISTRO_ROS=humble 参数）——08-24 ✅（CMake 4.4 坑见 §二）
- [x] velodyne.yaml 同步 R2 适配 + `map_en: false`——08-24 ✅（`doc/velodyne_r2.patch` git apply）
- [x] **extrinsic_T / extrinsic_R 实车量测填值**——08-24 ✅（`[0.36, 0.035, 0.47]` + 单位阵，`extrinsic_est_en: true`）
- [x] performance governor + 启动顺序就绪（§四）——08-24 ✅
- [x] 独立链路跑通：IMU Initial Done + /Odometry 8Hz+——08-24 ✅
- [x] 对比数据采集（平移/旋转误差）→ 决策——旋转 ✅（<2°）+ 平移 ✅（169cm 实测误差 0.5%）；**决策建议：旋转表现远优于 KISS（163°→<2°），FAST-LIO2 可作为建图/里程计替代，Nav2 场景仍 AMCL**
- [ ] TF 桥集成（验证对比后做，方案见 §五）——未做

---

## 相关

- VM 部署验证：[2026-08-18_fast_lio2_deploy.md](retrospect/2026-08-18_fast_lio2_deploy.md)
- 排障全记录：[2026-08-18_fastlio_laser_map_debug.md](retrospect/2026-08-18_fastlio_laser_map_debug.md)
- QoS/DDS 手册：[ros2-qos-dds.md](ros2-qos-dds.md)
- 方案对比：[vlp16_slam_exploration.md](retrospect/vlp16_slam_exploration.md)