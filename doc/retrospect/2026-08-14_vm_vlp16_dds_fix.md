# 2026-08-14 VM 单机跑 VLP-16：DDS 发现根因与修复

## 结论速览

**根因**：VM `~/.bashrc` 持久化了跨机 DDS 配置
`FASTRTPS_DEFAULT_PROFILES_FILE=~/Lin_workspace/fastdds_peer_n97.xml`（initialPeers 只单播直连
N97 192.168.1.210:7410）→ VM 上所有 ROS2 节点只向 N97 发起发现，**本机节点之间互相发现不了**
→ `ros2 topic list` 只剩 `/parameter_events /rosout`（velodyne 节点一切正常，UDP 收包独立于 DDS）。

**修复**：注释 `.bashrc` 该行，单机走默认 DDS 发现 → 话题全通、点云输出。
**次要坑**：ros2 daemon 常驻进程缓存旧环境，改环境后须 `ros2 daemon stop` 重查。

## 现象链

| 现象 | 结论 |
|:--|:--|
| launch 正常启动，驱动无 `poll() timeout`（数据在进） | 雷达数据流 OK（UDP 与 DDS 无关） |
| `ros2 topic list` 只剩 `/parameter_events /rosout`，`node list` 空 | **本机 DDS 发现失败** |
| rviz2 能看到点云 | 节点本身正常（rviz2 是新环境独立进程） |

## 排查过程

### 1. 链路验证（✅ 通过）

- 雷达**直连 VMware 宿主机**（本次拓扑变更：08-02 定型是经交换机；直连未复现 ARP 固化问题）
- ens37 = 10.18.18.40/24，路由正确，ARP 表 10.18.18.6 REACHABLE

### 2. 排除项（按时间顺序）

| 假设 | 排除方式 | 结论 |
|:--|:--|:--|
| 驱动没装/没 source | `ros2 pkg list` 有 velodyne 全套；apt 2.5.1 与 N97 同版本同构建 | ❌ |
| 源码工作区未编译 | `~/kiss_icp_ws/src/velodyne_src` 存在但从未 build；apt 版可直接用 | ❌（非本次根因，见遗留） |
| transform 无 Azimuth Cache 不发点云 | N97 同款 apt 包 + 同配置能出 9.9Hz；WARN 无害 | ❌ |
| N97 用了不同驱动 | SSH N97：同为 apt 2.5.1 | ❌ |
| daemon 缓存 | `--no-daemon` 查询仍空 | ❌（是次要坑，见 §4） |
| wellknown 配置未生效 | `/proc/<pid>/environ` 确认已加载 | ❌（配置语义问题，见 §3） |

### 3. 实锤：bashrc 跨机 DDS 配置掐死本机发现

- VM `.bashrc`（2026-08-05 配置）：
  `export FASTRTPS_DEFAULT_PROFILES_FILE=/home/lin/Lin_workspace/fastdds_peer_n97.xml`
- 该文件 = `initialPeersList` 只指向 `192.168.1.210:7410`（N97）→ 本机节点互不可见
- N97 侧用 `fastdds_wellknown.xml`（metatrafficUnicastLocatorList 0.0.0.0:7410，**监听**固定端口），
  本机靠默认组播发现（物理网卡组播正常），7410 供 VM 单播直连——注释原话"供 VM 单播发现"
- 尝试「VM 也用 wellknown」**不通**：metatrafficUnicastLocatorList 只改监听端口，
  SPDP 发送仍走默认组播 239.255.0.1:7400，VMware 组播不可靠 → 监听 7410 收不到任何 SPDP
- **修复动作**：`unset FASTRTPS_DEFAULT_PROFILES_FILE` → 话题全通 ✅
- **根治**：注释 `.bashrc` 该行（留说明注释）；跨机时手动 export（见 w1-operation.md）

### 4. 次要坑：ros2 daemon 缓存旧环境

- 症状：改完环境后 `ros2 topic list` 仍空，但 **rviz2 能看到点云**
- 原因：ros2 daemon 常驻进程（旧环境启动）缓存了 discovery 状态，CLI 默认走 daemon
- 处理：`ros2 daemon stop`（下次 CLI 命令自动拉起新 daemon）或 `ros2 topic list --no-daemon`

## 验证数据

```
/velodyne_packets   9.914 Hz  std 0.0008   ✅ 驱动收包稳定
/velodyne_points    6.371 Hz  max 0.5s    ⚠️ 有输出，VM 性能抖动（低于 N97 9.9Hz）
/scan               已有                  ✅ laserscan
```

## 遗留与相关

- **VM 点云 6.4Hz 抖动**：transform 为 CPU 密集节点，VMware 性能所限；不影响功能验证
- **两机 launch 已分叉**：N97 版 `~/.ros/velodyne_n97.launch.py` 多 robot_state_publisher
  （发 base_link→velodyne TF，读 `~/.ros/r2_description/r2.urdf`，z=0.56m 定案 08-06）；
  已复制到 VM：`~/.ros/velodyne_n97.from_n97.launch.py` + `~/.ros/r2_description/`
- **源码工作区**：`~/kiss_icp_ws/src/velodyne_src`（ros2 分支）从未编译，与 apt 2.5.1 同源；
  不需要 colcon；除非要改 velodyne 代码
- 相关：w1-operation.md §1.1（N97 启动含跨机 DDS export）、vlp16-network-topology（08-02 网络定型）
