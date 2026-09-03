# 2026-08-18 FAST-LIO2 部署验证（VM）

> 事件：08-18 在 VM（lin-virtual-machine）完成 FAST-LIO2 全流程编译部署，修正 08-02 "编译地狱"结论
> 关联：[vlp16_slam_exploration.md](vlp16_slam_exploration.md)（08-02 方案探索，FAST-LIO2 结论已由本文修正）
> 机器：VM（lin-virtual-machine）开发验证；N97 实车部署待后续（见文末待办）

---

## 一、背景与目标

- 08-02 探索结论："FAST-LIO2 ROS2 humble 分支硬依赖 Livox、裁剪几乎等于重写、放弃"（见 vlp16_slam_exploration.md 方案三）
- 08-18 复核动机：01-plan §8.4 候选池将 FAST-LIO2 列为算法候选（解决 KISS-ICP 旋转漂移痛点），需确认部署可行性
- **目标（时间盒 1~2 晚）**：VM 上编译通过 + 启动不崩 + bag 重放链路通；IMU 实数据（G354）留实车阶段

## 二、结论速览

**官方路径完整可行，两步即可编译通过，无需任何源码裁剪**：

1. `cp package_ROS2.xml package.xml`（官方仓库双版本设计）
2. `colcon build --cmake-args -DROS_EDITION=ROS2 -DDISTRO_ROS=humble`

08-02 的"放弃"结论是走"裁剪绕开 Livox"路线的失败，官方"装依赖满足编译"路线当时未走通验证。

---

## 三、环境与源码

| 项 | 值 |
|:---|:---|
| 机器 | VM lin-virtual-machine，Ubuntu 22.04，ROS2 Humble |
| 工作区 | `~/fast_lio_ws/`（独立 colcon 工作区，第三方算法不混入 Lin_workspace，同 kiss_icp_ws 习惯） |
| FAST_LIO | `hku-mars/FAST_LIO` **ROS2 分支**（维护者 Ericsiii；`--recursive` 带 ikd-Tree 子模块 e2e3f4e） |
| livox_ros_driver2 | `Livox-SDK/livox_ros_driver2` **官方 master**（FAST_LIO README L78 首选） |
| Livox-SDK2 | `Livox-SDK/Livox-SDK2`，sudo make install 装系统 |

## 四、安装全流程（真实命令记录）

### 4.1 clone

```bash
git clone --branch ROS2 --recursive https://github.com/hku-mars/FAST_LIO.git ~/fast_lio_ws/src/FAST_LIO
```

### 4.2 Livox-SDK2（livox_ros_driver2 编译依赖）

```bash
git clone --depth 1 https://github.com/Livox-SDK/Livox-SDK2.git ~/Livox-SDK2
cd ~/Livox-SDK2 && mkdir build && cd build   # ⚠️ build 目录需自建（官方 README 2.2 流程）
cmake .. && make -j4 && sudo make install
```

产物（实测确认）：
- `/usr/local/lib/liblivox_lidar_sdk_static.a` + `liblivox_lidar_sdk_shared.so`
- `/usr/local/include/livox_lidar_def.h` / `livox_lidar_api.h` / `livox_lidar_cfg.h`

### 4.3 livox_ros_driver2（官方 master，含双版本 package 机制）

```bash
cd ~/fast_lio_ws/src
git clone --depth 1 https://github.com/Livox-SDK/livox_ros_driver2.git
cd livox_ros_driver2
cp package_ROS2.xml package.xml   # 关键：colcon/ament 只认 package.xml（官方 build.sh 同款动作）
cp -rf launch_ROS2/ launch/       # build.sh 同款动作（CMakeLists 对 launch 引用弱，保险起见）
```

### 4.4 编译

```bash
cd ~/fast_lio_ws && source /opt/ros/humble/setup.bash
colcon build --symlink-install --cmake-args -DROS_EDITION=ROS2 -DDISTRO_ROS=humble
```

结果（实测输出摘要）：`Summary: 2 packages finished`——livox_ros_driver2 14.0s、fast_lio 1min 12s；全部告警无害
（boost bind 弃用 / PCL_ROOT CMP0074 / fast_lio 未用 DISTRO_ROS、ROS_EDITION 变量）。

---

## 五、三个坎（根因 + 解法，供排障复用）

| # | 报错现象 | 根因 | 解法 |
|:--|:---|:---|:---|
| 1 | `Could not find a package configuration file provided by "livox_ros_driver2"` | FAST_LIO 的 `find_package(livox_ros_driver2 REQUIRED)` 硬依赖，驱动未装 | 装 Livox-SDK2 + clone livox_ros_driver2 进工作区（§四） |
| 2 | `File .../livox_ros_driver2/package.xml does not exist` + `Packages installing interfaces must include <member_of_group>rosidl_interface_packages</member_of_group>` | 官方仓库**双版本设计**：`package_ROS1.xml`/`package_ROS2.xml` 需复制为 `package.xml` 才能被 colcon 识别（README 2.2 节 + build.sh 机制）；08-02 误判为"官方缺 package.xml" | `cp package_ROS2.xml package.xml` |
| 3 | `LIVOX_INTERFACES_INCLUDE_DIRECTORIES` NOTFOUND | CMakeLists（约 L290）按 `DISTRO_ROS` 变量分流：`humble`/`jazzy` 走 `rosidl_get_typesupport_target()` 现代 API；否则走旧式字符串 target 名 + `get_target_property`（foxy 用）。直接 colcon build 不带该变量 → 进 else 分支 → target 不存在 → NOTFOUND | colcon build 加 `--cmake-args -DROS_EDITION=ROS2 -DDISTRO_ROS=humble`（官方 build.sh 同款参数；fast_lio 收到未用变量，无害） |

> 教训：08-02 卡点记录表（find_package 硬依赖 / ament_target_dependencies / 头文件硬引用 / livox_pcl_cbk 未声明等）全部是**裁剪路线**下的症状；走官方装依赖路线后无一出现。

---

## 六、关键认知修正（vs 08-02 记录）

| 08-02 记录 | 08-18 实锤 |
|:---|:---|
| "官方 fork 缺 package.xml" | 双版本设计：`cp package_ROS2.xml package.xml` 即得 |
| "humble 分支硬依赖 Livox 雷达，源码硬编码 Livox 消息类型和回调，裁剪几乎等于重写" | **无需裁剪**：`~/fast_lio_ws/src/FAST_LIO/src/laserMapping.cpp` L921 `if (lidar_type == AVIA){livox 订阅} else {PointCloud2 订阅}`——velodyne 走标准 `sensor_msgs/PointCloud2` 完整分支；livox 仅是**编译期依赖**（提供 `CustomMsg.msg` 消息定义，laserMapping/preprocess include 它），运行时不用 |
| "等官方 ROS2 支持" | 官方 master 现即可编译（08-18 实测） |

## 七、官方仓库 vs Ericsii fork（为何回归官方）

- FAST_LIO README：L78 **首选官方** `Livox-SDK/livox_ros_driver2`；L80 备选 Ericsii fork（"You can also use the one I modified"）
- 08-02 因误判"官方缺 package.xml"改用 Ericsii fork；08-18 复核官方双版本机制后**回归官方 master**，编译一次通过
- 官方 master 的 `CustomMsg.msg` 与 FAST_LIO ROS2 兼容（Ericsii 的 use-standard-unit 分支差异非必需）；对 velodyne 场景两者等效（只提供消息定义）

## 八、velodyne.yaml 适配清单（下一步，VM 侧可先改）

`config/velodyne.yaml` 当前为 HDL-32E 默认值，按 VLP-16 实车需调整：

| 项 | 当前默认 | 应改 | 说明 |
|:---|:---|:---|:---|
| `scan_line` | 32 | **16** | VLP-16 是 16 线，32 会解析错乱 |
| `extrinsic_T` | [0, 0, 0.28] | 按实车量 | IMU→LiDAR 平移，须实测 G354 与 VLP-16 安装关系 |
| `det_range` | 100 | 40 | 与 08-15 雷达驱动 max_range 40m 一致 |
| `lidar_type` | 2 | 2 ✅ | velodyne |
| `lid_topic` | /velodyne_points | ✅ | 与 R2 一致 |
| `imu_topic` | /imu/data | ✅ | 与 G354 一致 |
| `scan_rate` | 10 | ✅ | 600rpm |
| `timestamp_unit` | 2 (us) | 先不动 | velodyne 驱动 time 字段为微秒，实车验证 |

## 九、VM 验证结果（08-18 晚 ✅ 全通过）

**验收三件套：编译 ✅ → 启动不崩 ✅ → bag 重放链路通 ✅**

### 9.1 启动验证（第 1 步）

```bash
ros2 launch fast_lio mapping.launch.py config_file:=velodyne.yaml rviz:=false
```

实测：`p_pre->lidar_type 2`（velodyne 分支确认）→ `Node init finished`；节点名 `/laser_mapping`；
订阅 `/imu/data` + `/velodyne_points`、发布 `/Odometry` `/path` `/Laser_map` `/cloud_registered*` `/tf` 全部就绪。

### 9.2 bag 重放链路验证（第 2~3 步）

**数据源（现成，无需 N97 新录）**：`~/Lin_workspace/r2_integration/bags/raw/stage_0812_2111`（231s，08-12 yaw 验证
保守录制，含 90°/190° 转弯，话题 `/imu/data` + `/velodyne_points` 与 velodyne.yaml 完全匹配）。
> 修正：08-18 早前"现有 bag 均未录 IMU"的说法错误——实测 7 个 bag 含 `/imu/data`，
> 其中 stage_0812_2111 / map_run_0809_2133 同时含雷达（后者 146s 可作备份）。

```bash
# 终端 1（先起，重放场景）
ros2 launch fast_lio mapping.launch.py config_file:=velodyne.yaml rviz:=false use_sim_time:=true
# 终端 2
ros2 bag play ~/Lin_workspace/r2_integration/bags/raw/stage_0812_2111 --clock
# 终端 3
ros2 topic hz /Odometry
```

| 检查项 | 实测 | 判定 |
|:---|:---|:---|
| IMU 接入 | `IMU Initial Done`（无同步告警） | ✅ |
| 建图启动 | `Initialize the map kdtree` | ✅ |
| /Odometry 频率 | 8.2~8.7Hz 持续（bag 雷达 10Hz） | ✅ |
| pose 运动 | 起点 (-0.03,-0.01) → (3.78,1.00) yaw≈83°（对应 bag 90° 转弯段，位移 3.9m） | ✅ 真实跟踪 |
| 致命告警 | 仅启动初期 2 条 `No point, skip this scan!`（随后消失）；无 `Failed to find match for field 'time'` | ✅ |

注记：`path_en: true` 后 `/path` 0.87Hz（轨迹点逐帧累积）；z 漂移 0.14m/3.9m 位移，
纯 LIO 无外部约束的正常量级，实车对比 KISS 后再评价。

### 9.3 /Laser_map 全局地图发布验证（map_en 排障链）

> 完整排障档案（阶段指令/结果/试错/工具对比/成果物）见
> [2026-08-18_fastlio_laser_map_debug.md](2026-08-18_fastlio_laser_map_debug.md)；
> 此处仅留结论。关键复盘：改对键名后链路即通（replay_3 96 条为证），当时"还是没有"
> 是 `ros2 topic hz` 对 22MB 大消息的假阴性。

`/Laser_map` 是**全量累积地图快照**（非增量）：1s 定时器 `map_publish_callback` 触发
`publish_map`，每次发布累积到当前的全部点。

**排障链（0 条 → 1Hz 闭环）**：

| 阶段 | 现象 | 结论 |
|:---|:---|:---|
| 初始 | /Laser_map 0 条 | yaml publish 段缺 `map_en` 参数 → 默认 false；且主循环 `publish_map` 调用被注释（laserMapping.cpp L1076），唯一入口是 1s 定时器（L1110） |
| 加 `map_en: true` | echo 收到完整帧 | 参数生效（param get = True）；diag 日志 `en=1` + 地图逐秒累积（87571→105077 点）；stamp 逐秒推进 |

**已验证数据（08-18）**：
- `ros2 param get /laser_mapping publish.map_en` → True
- `echo /Laser_map --once`：width 467,651 → 624,151 点（持续累积），frame_id `camera_init`
- `echo --field header.stamp`：sec 逐秒推进（289→294），间隔 ~1.008s = 1Hz 定时器实锤

**收尾（08-18 ✅）**：diag 日志已删除还原（重启后无 `[diag]` 输出），echo stamp 复验仍正常
——最终态：配置 ✅ 参数 ✅ 定时器 ✅ 发布 ✅ 接收 ✅

**踩坑与经验**：
- 键名是 `publish.map_en`（laserMapping.cpp L839 `get_parameter_or<bool>("publish.map_en", ...)`），不是 `map_pub_en`
- **`ros2 topic hz` 对 /Laser_map 不可用**：hz 订阅 QoS 写死 best_effort（`qos_profile_sensor_data`，无参数可改）+
  22MB 大消息 Python 单线程处理慢 → 一直等无输出、Ctrl-C 不即时；验证频率用 `echo --field header.stamp`（轻量，不刷 22MB）
- **消息巨大**：row_step ≈ 22.4MB/帧（62 万点 × 48B），1Hz = 22MB/s 持续带宽且随建图增长 →
  实车日常 `map_en: false`，需要建图快照再开；验证录制勿长时间开启（bag 巨大）

### 9.4 velodyne.yaml 已适配（VM 侧）

`scan_line 32→16`、`blind 2.0→0.5`、`det_range 100→40`（与 R2 雷达裁剪/驱动一致）；
`lid_topic`/`imu_topic` 与 R2 一致零改名；`pcd_save_en` 验证时关（防 231s 全帧大文件），需用时开。

---

## 十、待办（后续）

- [x] ~~VM 启动验证~~（08-18 ✅，见 §9）
- [x] ~~N97 录 30s 短 bag~~（不需要：stage_0812_2111 现成可用，见 §9.2）
- [ ] N97 实车部署：**完整检查清单见 [fastlio2-n97-deploy.md](../n97/fastlio2-n97-deploy.md)**
      （依赖全量安装 / 外参量测 / 运行纪律 / 验证流程 / 决策）
- [ ] 决策：FAST-LIO2 vs KISS-ICP+EKF（01-plan §8.4 候选池）——Nav2 侧 AMCL 定位不依赖 FAST-LIO，
      价值主要在**建图质量/里程计精度**（旋转漂移痛点）；实车对比后定（对比方法见部署手册 §六）
