# VLP-16 SLAM 方案探索记录

> R2 底盘 + VLP-16 + N97 MiniPC ROS2 Humble

## 硬件环境

| 项目 | 内容 |
|------|------|
| 雷达 | VLP-16，IP: 10.18.18.6，目标 IP: 10.18.18.20 |
| 主机 | N97 MiniPC (x86), enp1s0: 10.18.18.20/24 |
| 系统 | Ubuntu 22.04, ROS2 Humble |
| IMU | G354（未接入 FAST-LIO 流程） |

> **网络变更记录（2026-08-02）**：原网段 10.10.3.x（雷达 10.10.3.6 / N97 10.10.3.20）
> 整体迁移至 10.18.18.x（雷达 10.18.18.6 / N97 10.18.18.20）。
> 雷达 IP 在 VMware 中通过 VLP-16 Web 配置页修改，`velodyne_n97.launch.py` 中
> `device_ip` 需同步更新为 10.18.18.6（否则驱动与雷达的交互通道断开，日志持续告警）。

---

## 方案一：slam_toolbox（2D SLAM）🚫

**结论：不适用。** VLP-16 是 16 线 3D 雷达，slam_toolbox 用 2D LaserScan（只取了其中一条环），浪费了 15/16 的数据。

### 尝试过程

```bash
# 手动配置参数启动
ros2 run slam_toolbox async_slam_toolbox_node --ros-args \
  --params-file ~/.ros/slam/slam_toolbox.yaml

ros2 run slam_toolbox sync_slam_toolbox_node --ros-args \
  --params-file ~/.ros/slam/slam_toolbox.yaml

# 用系统 launch 文件
ros2 launch slam_toolbox online_sync_launch.py \
  base_frame:=base_footprint \
  odom_frame:=odom \
  map_frame:=map \
  scan_topic:=/scan \
  mode:=mapping
```

### 卡点
1. **tf2 message filter queue full** — slam_toolbox 内部的消息过滤队列阻塞，所有帧都被丢弃
2. 增加 `transform_tolerance`、`transform_timeout` 无效
3. 消息类型是 `LaserScan`（单线），VLP-16 的全点云能力被浪费

### 结论
即使绕开 queue full，2D SLAM 对 VLP-16 也不是正确方案。

---

## 方案二：Cartographer（2D/3D SLAM）🔄

**结论：配置格式与 humble 版本兼容问题，放弃。**

### 尝试过程

```bash
sudo apt install ros-humble-cartographer ros-humble-cartographer-ros
```

创建 `.lua` 配置文件 `~/.ros/slam/cartographer_2d.lua`：

```lua
include "map_builder.lua"
include "trajectory_builder.lua"

options = {
  map_builder = MAP_BUILDER,
  trajectory_builder = TRAJECTORY_BUILDER,
  map_frame = "map",
  tracking_frame = "velodyne",
  published_frame = "velodyne",
  odometry_frame = "odom",
  provide_odometry_frame = true,
  ...
}

MAP_BUILDER.use_trajectory_builder_2d = true
TRAJECTORY_BUILDER_2D.min_range = 0.3
TRAJECTORY_BUILDER_2D.max_range = 25.
```

启动：
```bash
ros2 run cartographer_ros cartographer_node \
  -configuration_directory ~/.ros/slam/ \
  -configuration_basename cartographer_2d.lua
```

### 卡点

| 问题 | 原因 |
|------|------|
| `Key 'resolution' was used the wrong number of times` | `TRAJECTORY_BUILDER_2D.submaps.resolution` 和默认 `map_builder.lua` 中的 resolution 冲突 |
| `Key 'odom_frame' not in dictionary` | `lua_parameter_dictionary.cc` 检查失败，配置作用域问题 |

### 结论
Cartographer 的 `.lua` 配置格式复杂，与 humble 版本的默认配置存在兼容性问题。2D 模式对 VLP-16 也不是最优选择。放弃。

---

## 方案三：FAST-LIO2（3D LiDAR-Inertial SLAM）✅（08-18 复核修正）

**结论（08-18 修正）：编译通过 ✅**——官方路径两步即可，无需裁剪；
08-02 的"编译失败"是裁剪路线失败，见 [2026-08-18_fast_lio2_deploy.md](2026-08-18_fast_lio2_deploy.md)（全流程/三坎/修正对照）。

### 尝试过程

**2026-08-02 尝试（未走通，未运行验证即转向）**：安装 Livox-SDK2 后误判"官方 fork 缺
package.xml"（实为双版本设计，需 `cp package_ROS2.xml package.xml`），转用 Ericsii fork，
并在 FAST_LIO 源码上尝试裁剪 livox 依赖（卡点见下）——**Ericsii fork 本身从未编译运行过**，
裁剪路线未走通即放弃，转向官方路径。

**正确路径（2026-08-18 验证 ✅，官方路线）**：

```bash
# 1. clone FAST_LIO（ROS2 分支，--recursive 带 ikd-Tree 子模块）
git clone --branch ROS2 --recursive https://github.com/hku-mars/FAST_LIO.git ~/fast_lio_ws/src/FAST_LIO

# 2. 安装 Livox-SDK2（livox_ros_driver2 编译依赖；build 目录需先 mkdir）
git clone --depth 1 https://github.com/Livox-SDK/Livox-SDK2.git ~/Livox-SDK2
cd ~/Livox-SDK2 && mkdir build && cd build && cmake .. && make -j4 && sudo make install

# 3. clone 官方 livox_ros_driver2 + 生成 package.xml（关键一步）
cd ~/fast_lio_ws/src
git clone --depth 1 https://github.com/Livox-SDK/livox_ros_driver2.git
cd livox_ros_driver2
cp package_ROS2.xml package.xml
cp -rf launch_ROS2/ launch/

# 4. 编译（DISTRO_ROS=humble 参数必带，见下方卡点表）
cd ~/fast_lio_ws && source /opt/ros/humble/setup.bash
colcon build --symlink-install --cmake-args -DROS_EDITION=ROS2 -DDISTRO_ROS=humble
```

分步说明与三坎排障详见 [2026-08-18_fast_lio2_deploy.md](2026-08-18_fast_lio2_deploy.md)。

### 卡点

| 问题 | 原因 |
|------|------|
| `find_package(livox_ros_driver2 REQUIRED)` | 硬依赖，用 QUIET 绕过 |
| `ament_target_dependencies` 引用了 livox_ros_driver2 | 需要从依赖列表删除 |
| `#include <livox_ros_driver2/msg/custom_msg.hpp>` | preprocess.h 和 laserMapping.cpp 中硬引用 |
| `livox_pcl_cbk` 未声明 | 在 class 作用域中找不到自由函数 |
| 多头文件生成路径问题 | include 路径嵌套了两层 livox_ros_driver2 |
| preprocess.cpp 中 livox 引用 | 散落在多个文件中，裁不干净 |

### 结论
FAST-LIO2 的 ROS2 humble 分支原生强依赖 Livox 雷达，对 VLP-16 虽然 config 目录中有 `velodyne.yaml`，但源码硬编码了 Livox 消息类型和回调。要裁剪几乎等于重写。放弃。

> **2026-08-18 复核修正（重要）**：上述"放弃"结论是**误判**——08-02 卡的是"裁剪绕开 Livox"路线；官方"装依赖满足编译"路线只需两步：
> 1. `cp package_ROS2.xml package.xml`（官方仓库**双版本设计**，非"缺 package.xml"；README 2.2 / build.sh 机制）
> 2. `colcon build --cmake-args -DROS_EDITION=ROS2 -DDISTRO_ROS=humble`（CMakeLists 按 `DISTRO_ROS` 分流，humble 需该参数走现代 typesupport API）
>
> 且 velodyne 走 `~/fast_lio_ws/src/FAST_LIO/src/laserMapping.cpp` L921 标准 PointCloud2 else 分支，
> livox 仅是编译期依赖（提供 CustomMsg 消息定义）。全流程/三坎/修正对照见 [2026-08-18_fast_lio2_deploy.md](2026-08-18_fast_lio2_deploy.md)。

---

## 方案四：KISS-ICP（纯 LiDAR 里程计）✅

**结论：可用。** 安装简捷，VLP-16 原生支持，输出 odom 和注册点云。

### 安装
```bash
# C++ ROS2 包（需要 CMake >= 3.24）
pip3 install cmake --upgrade   # 升级 cmake 到 4.4.0
git clone https://github.com/PRBonn/kiss-icp.git ~/kiss-icp
mkdir -p ~/kiss_icp_ws/src
cp -r ~/kiss-icp/ros ~/kiss_icp_ws/src/kiss_icp

cd ~/kiss_icp_ws
colcon build --symlink-install --packages-select kiss_icp \
  --cmake-args -DCMAKE_BUILD_TYPE=Release

# 也可用纯 Python 版本（备选）
pip3 install kiss-icp
```
（Python 版无 ROS2 节点，只能编程使用）

### 启动
```bash
# 终端 1：雷达
ros2 launch ~/.ros/velodyne_n97.launch.py

# 终端 2：KISS-ICP
source ~/kiss_icp_ws/install/setup.bash
ros2 launch kiss_icp odometry.launch.py \
  topic:=/velodyne_points \
  use_sim_time:=false \ # ⚠️ 必须显式设 false！launch 默认 true，实车无 /clock 时里程计不走
  visualize:=false \    # SSH 无 GUI 时设 false，本地显示器可设 true 自动开 RViz
  base_frame:=velodyne
```

### 输出话题

| 话题 | 类型 | 说明 |
|------|------|------|
| `/kiss_icp/odometry` | Odometry | 里程计数据 |
| `/kiss_icp/points` | PointCloud2 | 注册后的全局点云 |
| `/kiss_icp/deskewed_points` | PointCloud2 | 去畸变的当前帧 |

### 坐标系
- **base_frame**: `velodyne`（配置参数）
- **odom_frame**: `odom_lidar`（默认）
- **Fixed Frame（RVIZ）**: `odom_lidar`

### 已知限制
- 不发布 `/map` 话题（不是 full SLAM）
- 无回环检测，长距离会有漂移
- 需配合 IMU 或底盘 odom 做 EKF 融合以提升精度

---

## 方案对比总结

| 方案 | 类型 | 难度 | 效果 | 推荐 |
|------|------|------|------|------|
| **slam_toolbox** | 2D SLAM | 低 | ❌ 不适合 VLP-16 | — |
| **Cartographer** | 2D SLAM | 中 | ❌ 配置兼容性问题 | — |
| **FAST-LIO2** | 3D LIO | 🟢 中 | ✅ 编译+VM 重放验证（08-18）；实车链路待验证 | 候选池 |
| **KISS-ICP** | 3D Odom | 🟢 低 | ✅ 马上能用 | **当前** |

## 下一步建议
1. **键盘控制 + 点云采集** — ✅ 已完成（2026-08-02 实车跑通：雷达+KISS-ICP+WASD 键盘，RViz 中 `odom_lidar` 系点云地图随车累积）
2. **雷达闭环运动** — 基于 `/kiss_icp/odometry` 写 waypoint 节点，车自动走距离/转角度/到目标点（P 控制，见 [ekf-verification.md](../phase1/ekf-verification.md) 同期的 r2_bringup 扩展）
3. **IMU 融合** — 接入 G354 IMU，robot_localization EKF 提高定位（Phase 1 实车验证挂起中，清单见 [ekf-verification.md](../phase1/ekf-verification.md)）
4. **FAST-LIO2 部署** — 编译已通 + VM bag 重放链路验证完成（08-18，含 /Laser_map 1Hz 验证，见 [2026-08-18_fast_lio2_deploy.md](2026-08-18_fast_lio2_deploy.md)）；实车链路验证待做（重放源 stage_0812_2111 含 `/imu/data` + `/velodyne_points`，无需新录）
