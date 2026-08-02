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

## 方案三：FAST-LIO2（3D LiDAR-Inertial SLAM）🔄

**结论：编译失败**（ROS2 humble 分支代码质量不如预期）。

### 尝试过程

```bash
# 克隆
git clone https://github.com/hku-mars/FAST_LIO.git
git checkout ROS2  # ROS2 分支

# 需要依赖 livox_ros_driver2
git clone --depth 1 https://github.com/Livox-SDK/livox_ros_driver2.git
# 编译失败：缺少 Livox SDK

# 安装 Livox SDK2
git clone --depth 1 https://github.com/Livox-SDK/Livox-SDK2.git
cd build && cmake .. && make -j4 && sudo make install

# livox_ros_driver2 需要 package.xml，官方 fork 缺少
# 改用 Ericsii fork:
git clone --depth 1 -b feature/use-standard-unit \
  https://github.com/Ericsii/livox_ros_driver2.git
```

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

---

## 方案三：KISS-ICP（纯 LiDAR 里程计）✅

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
| **FAST-LIO2** | 3D LIO | 🔴 高 | ❌ 编译地狱 | — |
| **KISS-ICP** | 3D Odom | 🟢 低 | ✅ 马上能用 | **当前** |
| **未来的 FAST-LIO2** | 3D LIO | ⏳ 等完善 | — | 等官方 ROS2 支持 |

## 下一步建议
1. **键盘控制 + 点云采集** — ✅ 已完成（2026-08-02 实车跑通：雷达+KISS-ICP+WASD 键盘，RViz 中 `odom_lidar` 系点云地图随车累积）
2. **雷达闭环运动** — 基于 `/kiss_icp/odometry` 写 waypoint 节点，车自动走距离/转角度/到目标点（P 控制，见 [ekf-verification.md](../phase1/ekf-verification.md) 同期的 r2_bringup 扩展）
3. **IMU 融合** — 接入 G354 IMU，robot_localization EKF 提高定位（Phase 1 实车验证挂起中，清单见 [ekf-verification.md](../phase1/ekf-verification.md)）
4. **换 FAST-LIO** — 等 ROS2 分支稳定后再试，或者用 docker 已有环境
