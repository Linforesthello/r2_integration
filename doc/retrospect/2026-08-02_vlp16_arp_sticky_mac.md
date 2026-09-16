# VLP-16 雷达 ARP 固化（Sticky Cache）踩坑记录（2026-08-02）

> 日期：2026-08-02（**迁移前 10.10.3.x 网络时代**，见下方时代标注）
> 状态：✅ 已解决（专用 IP 隔离方案定型并沿用至 08-02 交换机迁移）
> 来源：**迁回档**——原文为 Obsidian 镜像层独有文件（`R2_Integration/vlp16同目标ip锁定MAC导致lidar data不更新问题.md`），
> 2026-09-16 按 [obsidian-sync.md §4-3](../obsidian-sync.md)「真独有 → 迁回权威源」迁入本仓（一文一事一档），镜像副本随删
> 关联：[2026-08-02_vlp16_switch_network.md](2026-08-02_vlp16_switch_network.md)（同日交换机迁移，其 §关键经验第 2 条为本问题的 2 行摘要）、
> [2026-08-14_vm_vlp16_dds_fix.md](2026-08-14_vm_vlp16_dds_fix.md)（后续 DDS 层网络问题）

> ⚠️ **时代标注（迁回时加注，原文保留）**：本文正文中的 IP（`10.10.3.x`）为 **08-02 交换机迁移前**的直连方案；
> 现役网段为 **10.18.18.x**（雷达 10.18.18.6 → N97 enp1s0 10.18.18.20），见 [sensor-mount.md](../phase0/sensor-mount.md) /
> [07-handover.md §头部](../07-handover.md)。**机制部分（ARP 固化行为）与 IP 无关，仍然有效**。
> 文末一键 launch 段亦为当时形态，现役为 [r2_sensors/launch/velodyne.launch.py](../../r2_sensors/launch/velodyne.launch.py)。

---

## 一、症状

tcpdump/Wireshark 能看到雷达 `10.10.3.6` 发来的 UDP 数据包，但：

- `nc -u -l 2368` 收不到
- `velodyne_driver` poll() timeout
- `UdpInDatagrams` 不涨（或涨极少）
- 但雷达的状态数据（8308 端口）可能正常
- 没有防火墙拦截，路由正确

## 二、排查过程

```bash
# 确认包到了本机
sudo tcpdump -i enp1s0 host 10.10.3.6 -e -n -c 5
```

关键看**目的 MAC 地址**——如果 2368 端口的包发往一个**不存在的 MAC**（例如 VMware 虚拟机 `00:0c:29:XX:XX:XX`），
而本机网卡 MAC 是另一个（如 `e4:3a:6e:86:7e:42`），就是这个问题。

**8308 端口的包 MAC 正确 ≠ 2368 的包 MAC 正确。**

## 三、根因

**VLP-16 的固件在 2368 端口（激光数据流）上是单向推送，ARP 表是 NVRAM 固化的，不会标准老化。**

| 端口 | 方向 | ARP 行为 |
|:---|:---|:---|
| **2368**（激光数据） | 雷达 → PC 单向 | **第一次 ARP 解析后写死，不重新请求，不老化** |
| **8308**（遥测/诊断） | 双向（PC 主动请求，雷达应答） | 相对正常，双向通信刷新 MAC |

### 典型触发场景

```
时间线：
① 笔记本 VMware 虚拟机（10.10.3.30, MAC=00:0c:29:81:2e:ef）连雷达调试
② 雷达学到：10.10.3.30 = 00:0c:29:81:2e:ef，写死到 NVRAM
③ 换 N97 MiniPC（IP 也设 10.10.3.30, MAC=e4:3a:6e:86:7e:42）直连雷达
④ 雷达：10.10.3.30 = 00:0c:29:81:2e:ef（管你换了谁），包全发给不存在 MAC
⑤ N97 网卡硬件层看到 MAC 不匹配，丢弃 → 应用层收不到
⑥ tcpdump 混杂模式能看到包（不经过 MAC 过滤），造成"能看到但收不到"的错觉
```

## 四、修复方法（三选一）

### 方法 A ✅ 推荐：专用 IP 隔离

给 N97 的雷达网口加一个**雷达从未见过的 IP**，然后改雷达目标 IP：

```bash
# N97 上加辅助 IP
sudo ip addr add 10.10.3.20/24 dev enp1s0

# 浏览器访问雷达 Web 界面 http://10.10.3.6
# Network → Destination IP → 改为 10.10.3.20
# Save → Reboot Radar

# 启动驱动
ros2 run velodyne_driver velodyne_driver_node --ros-args \
  -p device_ip:=10.10.3.6 \
  -p frame_id:=velodyne \
  -p model:=VLP16
```

### 方法 B：ARP 广播（不一定有效）

```bash
sudo apt install arping  # 如果没装
sudo arping -U -I enp1s0 -c 5 10.10.3.30  # 广播真实 MAC
```

VLP 固件可能不响应 Gratuitous ARP，所以不一定有效。

### 方法 C：断电清空雷达缓存

雷达断电再上电，ARP 缓存清空；N97 先 ping 雷达重建正确 ARP 映射。
但 VLP 的 NVRAM 固化**不一定**被断电清除（对比：[08-02 交换机档](2026-08-02_vlp16_switch_network.md) 记录"断电重启雷达清 ARP 固化缓存"在同日另一场景有效）。

## 五、验证方法

```bash
# 确认 2368 包的目的 MAC 是否为本机网卡
sudo tcpdump -i enp1s0 host 10.10.3.6 -e -n -c 5

# 期望输出：2368 的 MAC 是 e4:3a:6e:86:7e:42（本机），而不是 00:0c:29:XX:XX:XX
```

## 六、最佳实践

1. **为 Velodyne 雷达分配一个专用的 IP 地址**（如 `10.10.3.20`），不与主机日常 IP（如 `10.10.3.30`）共用
2. 一旦设好目标 IP，**不要在不同机器上重复使用同一个 IP 来接雷达**
3. 换电脑时，要么换新 IP，要么进雷达 Web 界面重置网络配置
4. 建议 N97 的雷达网口保留两个 IP：
   ```
   10.10.3.30/24  → 日常管理/其他设备
   10.10.3.20/24  → 专供 VLP-16
   ```

## 七、附：用户踩坑语料原文（迁回时如实保留）

> VLP-16 会记住同一个目标 IP 下的网卡 MAC。查了半天，是 Host (Destination) IP 没改，直接换设备导致网卡不一致，应用层过不去。
>
> **正常时：** 2368 和 8308 两个端口的包，目的 MAC 都是 N97 的 `e4:3a:6e:86:7e:42`
> **异常时：** 2368 包的 MAC 是 VMware 虚拟机 `00:0c:29:81:2e:ef`
>
> 1206 字节包 = 激光数据（雷达单向发给设备）
> 512 字节包 = 双向通信数据
>
> **单向的数据流（2368）不更新 MAC，双向的（8308）ping 一下就更新了。单向的不更新。**

### 7.1 NetworkManager autoconnect 陷阱（同批排查发现）

> 找到原因了！`connection.autoconnect: 否`——这个配置不会在开机时自动连接，所以重启后 IP 就跑掉了。

```bash
# 发现：nmcli 配置的静态 IP 重启后丢了
# 排查：
nmcli conn show enp1s0 | grep connection.autoconnect
# → connection.autoconnect: 否（默认值，重启后配置不生效！）

# 修复：允许开机自连
sudo nmcli conn mod "enp1s0" connection.autoconnect yes

# 确认配置写进去了
nmcli conn show enp1s0 | grep connection.autoconnect
# → connection.autoconnect: 是

# 重启验证
sudo reboot
ip addr show enp1s0 | grep inet
# → inet 10.10.3.20/24 brd 10.10.3.255 scope global noprefixroute enp1s0 ✅
```

### 7.2 当时的一键启动（ROS2 launch，形态已过时，**加注保留**）

> 文件位置：`/home/lin/.ros/velodyne_n97.launch.py`（driver + transform + laserscan 三节点合并 + OnProcessExit 联动 Shutdown）。
> **现役形态**见 [r2_sensors/launch/velodyne.launch.py](../../r2_sensors/launch/velodyne.launch.py)（08-15 抽包，参数在 launch 内 override）；
> 下述代码的 `device_ip` 为旧网段值（10.10.3.6），**保留原文作历史留档，勿直接沿用**。

```python
import os
import ament_index_python.packages
import launch
import launch_ros.actions


def generate_launch_description():
    driver_share = ament_index_python.packages.get_package_share_directory('velodyne_driver')
    driver_params = os.path.join(driver_share, 'config', 'VLP16-velodyne_driver_node-params.yaml')
    velodyne_driver_node = launch_ros.actions.Node(
        package='velodyne_driver',
        executable='velodyne_driver_node',
        output='both',
        parameters=[driver_params, {'device_ip': '10.10.3.6', 'frame_id': 'velodyne'}])

    convert_share = ament_index_python.packages.get_package_share_directory('velodyne_pointcloud')
    convert_params_file = os.path.join(convert_share, 'config', 'VLP16-velodyne_transform_node-params.yaml')
    with open(convert_params_file, 'r') as f:
        import yaml
        convert_params = yaml.safe_load(f)['velodyne_transform_node']['ros__parameters']
    convert_params['calibration'] = os.path.join(convert_share, 'params', 'VLP16db.yaml')
    convert_params['frame_id'] = 'velodyne'
    velodyne_transform_node = launch_ros.actions.Node(
        package='velodyne_pointcloud',
        executable='velodyne_transform_node',
        output='both',
        parameters=[convert_params])

    laserscan_share = ament_index_python.packages.get_package_share_directory('velodyne_laserscan')
    laserscan_params = os.path.join(laserscan_share, 'config', 'default-velodyne_laserscan_node-params.yaml')
    velodyne_laserscan_node = launch_ros.actions.Node(
        package='velodyne_laserscan',
        executable='velodyne_laserscan_node',
        output='both',
        parameters=[laserscan_params])

    return launch.LaunchDescription([
        velodyne_driver_node,
        velodyne_transform_node,
        velodyne_laserscan_node,
        launch.actions.RegisterEventHandler(
            event_handler=launch.event_handlers.OnProcessExit(
                target_action=velodyne_driver_node,
                on_exit=[launch.actions.EmitEvent(event=launch.events.Shutdown())]),
        ),
    ])
```

传输与使用（原文）：

```bash
# 从开发机（VMware）SCP 到 N97
scp /home/lin/.ros/velodyne_n97.launch.py lin@<N97_IP>:/home/lin/.ros/

# N97 上一键启动
ros2 launch /home/lin/.ros/velodyne_n97.launch.py
```

包含三个节点：`velodyne_driver_node`（收 UDP） + `velodyne_transform_node`（转点云） + `velodyne_laserscan_node`（2D LaserScan）。
两次测试均正常，无 poll() timeout。

## 八、参考（迁回保留）

- VLP-16 Web 界面：`http://10.10.3.6`（旧网段；现役 `http://10.18.18.6`）
- 默认端口：**2368（激光数据）/ 8308（遥测诊断）**
- **默认出厂目标 IP：`192.168.1.201:2368`**（换机/重置后的兜底线索）

## 九、方法模板（可复用操作卡）

① **判"能看到包但应用收不到"**：`sudo tcpdump -i <iface> host <雷达IP> -e -n -c 5`，**先看目的 MAC**——
若 2368 的目的 MAC ≠ 本机网卡 MAC → 命中本问题；
② **判新旧缓存差异**：对比 2368（单向）与 8308（双向）两个端口的包 MAC——单向错、双向对 = ARP 固化特征；
③ **首选修复**：给接收机加**雷达从未见过的辅助 IP** + Web 改雷达 Destination IP（方法 A），比反复清缓存可靠；
④ **预防**：雷达专用 IP 不与他机复用；`nmcli conn show <iface> | grep autoconnect` 确认开机自连。

## 十、经验点层次标注（供盘点抽取）

| # | 经验点 | 建议去向 |
|:--|:---|:---|
| E1 | 雷达/设备 ARP **NVRAM 固化**：首次解析的接收端 MAC 写死、不老化——换设备/网口后必须让雷达重新学习 | **draft 层**（网络诊断域，待复用 2+ 次）→ 规则层候选 ros2-ops §7 排障纪律 |
| E2 | **单向推送端口不老化、双向端口刷新**——可用于快速区分"ARP 固化"与"链路断" | 同上 |
| E3 | `tcpdump` 混杂模式可看到目的 MAC 非本机的包 → 造成"能看到但收不到"错觉，**必须看 `-e` 的 MAC 列** | 同上 |
| E4 | 根治优于绕过：**专用 IP 隔离**（方法 A）> 清缓存（方法 C，NVRAM 不一定清得掉） | 同上 |
| E5 | NetworkManager `connection.autoconnect` 默认**否** → nmcli 静态 IP 重启即丢 | 同上（可与 E1~E4 合并为一组抽取） |

---

## 相关

- [2026-08-02_vlp16_switch_network.md](2026-08-02_vlp16_switch_network.md)（同日交换机迁移方案；本文为其"关键经验第 2 条"的完整展开）
- [2026-08-14_vm_vlp16_dds_fix.md](2026-08-14_vm_vlp16_dds_fix.md)（DDS 层网络问题，与本问题分层不同）
- [sensor-mount.md](../phase0/sensor-mount.md)、[07-handover.md](../07-handover.md)（现役网络拓扑）
