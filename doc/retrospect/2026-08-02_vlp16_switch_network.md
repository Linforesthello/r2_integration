# VLP-16 交换机接入方案（2026-08-02）

> 本次方案：雷达经交换机接到 Windows 宿主机，再桥接进 VMware 虚拟机，取代之前的 10.10.3.x 直连方案。
> 注：当前定型拓扑（雷达经交换机直转 N97 enp1s0 10.18.18.20）见 [project_status.md §四](../project_status.md)，本文档为方案演进过程记录。

## 链路拓扑

```
VLP-16 ──RJ45── 交换机（无 VLAN，管理 IP 10.18.18.251，仅管理用勿改）
    ──RJ45── Windows 宿主机有线网口
    ──VMware 桥接── 虚拟机 ens37（静态 10.18.18.30/24）
```

![](vlp16-switch-network-topology.png)

## 网络配置（独立网段，与公司网完全隔离）

| 项 | 值 |
|:---|:---|
| Sensor (Network) IP | 10.18.18.6 / 255.255.255.0 |
| Host (Destination) IP | 10.18.18.30（= 虚拟机 ens37 静态地址，单播直达） |
| Gateway | 10.18.18.1（同网段直发用不到） |
| Data Port / Telemetry | 2368 / 8308 |
| DHCP | Off |

虚拟机网卡：ens33 = 192.168.1.204/24（公司网），ens37 = 10.18.18.30/24（雷达网，静态，网关留空）。

## 关键经验

1. **网页改配置后必须 Save + 重启雷达才生效**（配置写入 NVRAM，重启时应用并重建网络栈，顺带清 ARP 缓存）
2. 换接收端 MAC 后仍收不到包 → 断电重启雷达清 ARP 固化缓存（雷达固化首次连接的接收端 MAC，更换网口/MAC 后必须断电重启才重新学习）
3. VMware 桥接需在虚拟网络编辑器**手动指定桥接到宿主机有线网口**，不要用"自动"（可能桥到无线网卡）
4. 雷达独立网段 10.18.18.x 与公司网 192.168.1.x 隔离，雷达 2368 广播不会骚扰局域网

## 启动方式

```bash
# 终端 1：激光雷达驱动（收 UDP 2368）
ros2 run velodyne_driver velodyne_driver_node --ros-args \
  -p device_ip:=10.18.18.6 \
  -p frame_id:=velodyne \
  -p model:=VLP16

# 终端 2：点云转换（packets → PointCloud2）
ros2 run velodyne_pointcloud velodyne_transform_node --ros-args \
  -p calibration:=/opt/ros/humble/share/velodyne_pointcloud/params/VLP16db.yaml \
  -p model:=VLP16 \
  -p frame_id:=velodyne \
  -p fixed_frame:=velodyne

# 验证
ros2 topic hz /velodyne_points     # 期望 ~10Hz
sudo tcpdump -i ens37 udp port 2368 -n -c 10   # 确认链路通
```

> 完整一键 launch（driver + transform + laserscan）：`/home/lin/.ros/velodyne_n97.launch.py`，注意其中 `device_ip` 需改为 `10.18.18.6`。

## 相关文档

- [vlp16_slam_exploration.md](vlp16_slam_exploration.md) — SLAM 方案对比（KISS-ICP 可用）
- [project_status.md §四](../project_status.md) — 现役网络拓扑
