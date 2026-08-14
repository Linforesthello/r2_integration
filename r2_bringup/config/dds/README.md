# DDS 配置（FastDDS 固定端口方案）

> 权威源在本目录（git 管理）。机器本地旧副本（`~/fastdds_wellknown.xml`、
> `~/Lin_workspace/fastdds_peer_n97.xml`）为历史拷贝，改动以本目录为准。

## 背景

VMware NAT/桥接不转发组播 → 跨机（VM↔N97）发现走**固定单播端口 7410**。
配套踩坑记录：[retrospect/2026-08-14_vm_vlp16_dds_fix.md](../../../doc/retrospect/2026-08-14_vm_vlp16_dds_fix.md)

## 文件说明

| 文件 | 用途 | 用在哪台机器 | 副作用 |
|:--|:--|:--|:--|
| `fastdds_peer_n97.xml` | initialPeers 单播直连 N97 7410（跨机发现） | VM 跨机时 export | ⚠️ 只向 N97 发现，**本机节点互相看不见**，单机跑必须 unset |
| `fastdds_wellknown.xml` | 监听 7410 单播（供 VM 单播发现） | N97 每个 ROS 终端 export | 无（本机靠默认组播发现，物理网卡组播正常） |

## 用法

```bash
# VM 单机跑（默认，bashrc 已注释跨机配置）：
#   什么都不用 export，走默认 DDS 发现

# VM 跨机（VM 节点 ↔ N97 节点）：
export FASTRTPS_DEFAULT_PROFILES_FILE=~/Lin_workspace/r2_integration/r2_bringup/config/dds/fastdds_peer_n97.xml

# N97（每个 ROS 终端都要）：
export FASTRTPS_DEFAULT_PROFILES_FILE=~/Lin_workspace/r2_integration/r2_bringup/config/dds/fastdds_wellknown.xml
```

## 排障

- `ros2 topic list` 只剩 `/parameter_events /rosout` → 环境/daemon 问题：
  `ros2 daemon stop` 后重查，或确认没误带 peer 配置
- 改环境后 CLI 仍查不到但 rviz2 正常 → daemon 缓存，`ros2 daemon stop`
