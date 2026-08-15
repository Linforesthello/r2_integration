# r2_sensors · VLP-16 雷达外设包

> R2 的 VLP-16 激光雷达 ROS2 启动包（08-15 从 r2_bringup 抽出，两机通用）。
> 驱动 + 点云转换 + 2D LaserScan（Nav2 用）+ 静态 TF 一条链路，单一 launch 启动。

## 启动

```bash
ros2 launch r2_sensors velodyne.launch.py              # 默认 device_ip 10.18.18.6
ros2 launch r2_sensors velodyne.launch.py device_ip:=10.18.18.6
```

## 节点与话题

| 节点 | 来源包 | 输出话题 | 说明 |
|:-----|:------|:---------|:-----|
| velodyne_driver_node | velodyne_driver | /velodyne_packets | UDP 收包 |
| velodyne_transform_node | velodyne_pointcloud | /velodyne_points | 点云转换；organize_cloud=false、max_range 40m、**min_range 0.5m**（08-15 盲区修复，原 0.9） |
| velodyne_laserscan_node | velodyne_laserscan | **/scan** | 2D LaserScan（08-15 恢复：Nav2 AMCL/costmap 订阅），frame_id=velodyne |
| robot_state_publisher | robot_state_publisher | /tf_static | base_link→velodyne（config/r2.urdf，z=0.56m） |

## 关键参数

- `device_ip`：雷达 IP（默认 10.18.18.6）
- transform 层裁剪：`max_range 40` / `min_range 0.5`（VLP-16 规格最小测距；盲区修复见 [retrospect 08-15](../doc/retrospect/2026-08-15_nav2_bringup.md)）

## 关联

- 建图链路：KISS-ICP 订阅 /velodyne_points（Nav2 场景不启动 KISS）
- 导航链路：Nav2 订阅 /scan（AMCL 定位 + costmap 感知）
- 性能调优记录：[retrospect 08-15](../doc/retrospect/2026-08-15_velodyne_perf_tuning.md)（供电根因 + organize/max_range）
