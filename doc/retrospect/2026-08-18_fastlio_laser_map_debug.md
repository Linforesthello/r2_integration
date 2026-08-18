# 2026-08-18 FAST-LIO /Laser_map 无发布排障全记录

> 事件：VM 验证 FAST-LIO2 链路时 `/Laser_map` 0 条，配置→参数→源码→诊断日志逐段隔离，最终 1Hz 闭环
> 关联：[2026-08-18_fast_lio2_deploy.md](2026-08-18_fast_lio2_deploy.md)（部署验证结论，本文是排障细节全记录）
> 机器：VM（lin-virtual-machine）
> 涉及源码：`~/fast_lio_ws/src/FAST_LIO/src/laserMapping.cpp`（FAST_LIO ROS2 分支）、
> `/opt/ros/humble/lib/python3.10/site-packages/ros2topic/verb/{hz,echo}.py`

---

## 一、现象

bag 重放（`stage_0812_2111`，231s 含 90°/190° 转弯）验证 FAST-LIO2 链路时，话题记录结果
（bag `fastlio_0818_replay_1`，169s）：

| 话题 | 条数 | 判定 |
|:---|:---|:---|
| /Odometry | 1403 | ✅ 8.2Hz |
| /path | 140 | ✅ 0.87Hz（path_en 已开） |
| /cloud_registered_body | 1403 | ✅ 8.2Hz |
| /tf | 7697 | ✅ 45Hz |
| **/Laser_map** | **0** | ❌ 无发布 |

---

## 二、排查时间线（指令 → 结果 → 判断）

### 阶段 1：源码定位（初始）

读 laserMapping.cpp 三个关键点：

| 位置 | 内容 | 含义 |
|:---|:---|:---|
| L1076 | `// if (map_pub_en) publish_map(pubLaserCloudMap_);` | **主循环的发布调用被注释** |
| L1110-1113 | `map_publish_callback()` 内 `if (map_pub_en) publish_map(...)` | 唯一入口 = 1s 定时器 |
| L839 | `get_parameter_or<bool>("publish.map_en", map_pub_en, false)` | **参数键名是 `publish.map_en`** |

**判断**：yaml publish 段无 `map_en` 参数 → 默认 false → 0 条。修法：yaml 加 `map_en: true` + 重启。

### 阶段 2：第一次加参（错键名试错 ❌）

我凭变量名 `map_pub_en` 直接 sed 加 `map_pub_en: true`——**未核对 L839 的键名**。
用户重启验证（`replay_2`，114s）：`/Laser_map` 仍 0 条。

**复盘**：`get_parameter_or` 按键名 `publish.map_en` 查 → 找不到 → 取默认 false。**键名错 = 参数等于没加**。
教训：参数键名以源码 `get_parameter_or` 为准，不凭变量名或印象。

### 阶段 3：社区核实键名（正确键名 ✅）

用户质疑后 WebSearch 核实：

- [CSDN：FAST-LIO2 velodyne.yaml 配置解析](https://blog.csdn.net/m0_55260921/article/details/151315696)
- [gitcode：FAST-LIO 地图发布解析](https://blog.gitcode.com/a51a0a3502bc18a6feab2dcb36dca1da.html)

键名确为 `map_en`（与 L839 源码一致）。用户 sed 改 `map_en: true` → 重启 → **用户报"还是没有"**
（`hz_3`，18:45）→ 排查方向被带偏（见阶段 5/6 复盘）。

### 阶段 4："参数未生效"疑点排查

- 用户问：改 yaml 是否要重新编译 → **不需要**（symlink-install 模式 install 是符号链接指向源码），
  但**必须重启节点**（参数启动时一次性读取）
- 用户确认"之前都是停掉并重启的" → 排除重启假设
- yaml 解析验证 `publish.map_en: True` → 参数文件正确
- **矛盾点**：参数对 + 重启过 + 仍"没有" → 需更深定位

### 阶段 5：诊断日志（逐段隔离，决定性）

在 `map_publish_callback` 加诊断日志并重编译（`colcon build --packages-select fast_lio --symlink-install`，~1min）：

```cpp
RCLCPP_INFO(this->get_logger(), "[diag] map_pub_cb: en=%d wait_pub_size=%zu",
            (int)map_pub_en, pcl_wait_pub->points.size());
```

用户实测输出：

```
[diag] map_pub_cb: en=1 wait_pub_size=87571
[diag] map_pub_cb: en=1 wait_pub_size=93401
[diag] map_pub_cb: en=1 wait_pub_size=99238
[diag] map_pub_cb: en=1 wait_pub_size=105077
```

三个事实：**en=1（参数确已加载）→ 每秒触发（timer 正常）→ 地图持续累积（publish_map 执行中）**。
**判断**：执行侧全通，`publish_map` 必然执行到最后的 `publish()`。问题只可能在"发布→接收"或"验证手段"。

### 阶段 6：接收侧验证（echo 成功 ✅）

```bash
ros2 param get /laser_mapping publish.map_en     # → True
ros2 topic echo /Laser_map --once                # → 467,651 点，frame_id camera_init
ros2 topic echo /Laser_map --once                # → 624,151 点（持续累积）
```

**链路已通！** 阶段 3 的"还是没有"实为验证手段误判（hz 收不到，见阶段 7）。

### 阶段 7：hz 之谜（工具对比，源码实锤）

现象：`ros2 topic hz /Laser_map` 一直等、无输出、Ctrl-C 不即时。

查 Humble ros2topic 源码：

| 文件:行 | 事实 |
|:---|:---|
| hz.py L278 | 订阅 QoS **写死 `qos_profile_sensor_data`（best_effort）**，无参数可改 |
| hz.py L223-224 | 收到**第一条消息不打印**（节流），间隔 ≥1s 的第二条才打印 |
| hz.py L282-283 | `rclpy.spin_once` 单线程循环，每条大消息 Python 处理 1~2s |
| laserMapping.cpp L933 | 发布者 `create_publisher("/Laser_map", 20)` = **reliable + KEEP_LAST 20 + 22MB/帧** |
| echo.py L41 | 默认同为 sensor_data（best_effort），但 `--once` 收一条即退；且有 `--qos-reliability` 可改 |

机制推断：best_effort 订阅 22MB 分片大消息（FastDDS 拆 ~350 片、无重传），回环下部分帧可凑齐
（echo 命中），但 hz 单线程 + 大消息处理慢 + 首条不打印 → 感知"一直等"；Ctrl-C 不即时 = 卡在
大消息处理/等待中。**DDS 层确切机制（缺片丢弃 vs 处理慢）未完全定位，不影响使用。**

### 阶段 8：最终闭环（1Hz 实锤 ✅）

```bash
ros2 topic echo /Laser_map --qos-reliability reliable --field header.stamp
```

输出（节选）：`sec: 1786540289 → 290 → 291 → 292 → 293 → 294`，间隔 ~1.008s = **1Hz 定时器实锤**。

---

## 三、时间线对照表（bag metadata 证据）

| bag | 时间 | 当时配置 | /Laser_map 条数 | 判定 |
|:---|:---|:---|:---|:---|
| replay_1 | 18:33 | path_en true（无 map_en） | 0 | 默认 false，符合预期 |
| replay_2 | 18:41 | 错键名 `map_pub_en` | 0 | 键名错 = 参数没加 |
| replay_3 | 18:45 | **`map_en: true`** | **96**（95.7s / 1Hz） | **当时已通！** |

**决定性结论：replay_3 的 96 条证明——改对键名后链路即通，"还是没有"是 hz 假阴性。**

---

## 四、方法复盘（为什么这样排）

1. **先读源码定键名和入口，再动手改**（L839 键名 + L1076 注释 + L1110 定时器入口）；错键名那次
   正是跳过了"核实键名"直接凭变量名猜测
2. **验证手段先行（本次最大教训）**："参数对不对"用 `ros2 param get`（1 秒）直接问，
   不该靠 hz 间接判定；大消息话题频率用 `echo --field header.stamp` 轻量验证。
   若阶段 3 直接 param get + echo，可省掉阶段 4~5 的约 1 小时
3. **逐段隔离**：配置（yaml 解析）→ 参数（param get）→ 执行（diag 日志）→ 发布（echo）→
   频率（stamp），每段一个验证动作，问题在哪段一目了然
4. **bag metadata 是免费排障证据**：message_count 对比直接钉死"当时到底有没有"，
   事后复盘不受记忆影响

---

## 五、经验沉淀（复用清单）

1. **yaml 参数键名以源码 `get_parameter_or` 为准**，不凭变量名/印象（`map_pub_en` ≠ `publish.map_en`）
2. **参数启动时一次性读取**：改 yaml 必须重启节点；symlink-install 模式无需重新编译
3. **`ros2 topic hz` 只适用于轻量话题（<1MB）**：订阅 QoS 写死 best_effort，大消息收不到/假阴性；
   大消息话题验证频率用 `echo --field header.stamp` 或 bag metadata 的 message_count
4. **/Laser_map 消息巨大**：22.4MB/帧（62 万点 × 48B），1Hz = 22MB/s 持续带宽且随建图增长 →
   实车日常 `map_en: false`，需要建图快照再开；验证录制勿长时间开启（bag 巨大，
   replay_3 仅 95.7s 即 1.5G）

---

## 六、成果物清单

位置：`~/Lin_workspace/bags/raw/`

| 文件 | 大小 | 说明 |
|:---|:---|:---|
| fastlio_0818_replay_1 | 373M | 169s，Laser_map 0 条（排障前基线） |
| fastlio_0818_replay_2 | 248M | 114s，错键名期，Laser_map 0 条 |
| fastlio_0818_replay_3 | 1.5G | 95.7s，**Laser_map 96 条**（22MB×96 的带宽直接体现） |
| fastlio_0818_hz.log | 1.0K | 初始频率记录 |
| fastlio_0818_hz_1.log | 3.6K | path_en 后全话题频率（Odometry 8.2Hz / path 0.87Hz / cloud_registered_body 8.2Hz） |
| fastlio_0818_hz_2.log | 3.5K | 错键名期 |
| fastlio_0818_hz_3.log | 3.4K | map_en 后（hz 假阴性，Laser_map 段空） |

最终验证 bag（含 Laser_map 的干净版）：未录制，需要时补录。

---

## 七、收尾与遗留

**收尾（08-18 完成 ✅）**：

- laserMapping.cpp 的 diag 日志删除 + 重编译（`colcon build --packages-select fast_lio --symlink-install`）
- 重启节点复验：日志**不再出现 `[diag] map_pub_cb`**（代码还原成功）
- `ros2 topic echo /Laser_map --qos-reliability reliable --field header.stamp` 复验仍逐秒推进（1Hz 正常）

**遗留**：

- 含 Laser_map 的最终干净 bag 未录制，需要时补录

---

## 八、hz 之谜定论（社区核实 + 源码，08-18）

**现象**：hz 一直等无输出；echo 默认（同为 best_effort）能收到完整帧；
echo `--qos-reliability reliable` 稳定逐秒输出。

**机制（源码 + 社区多来源拼齐）**：

1. hz 订阅 QoS 写死 `qos_profile_sensor_data`（best_effort），无参数可改
   （[ros2/ros2cli#719](https://github.com/ros2/ros2cli/issues/719) 待办至今未合）
2. 22MB 消息 ≈ 350 个 UDP 分片，发布者 1s 内 burst 发完；接收端 socket buffer（默认 ~212KB）
   瞬间灌满溢出丢片
3. best_effort 无重传 → 缺片 → **整条消息丢弃** → hz 结构性收不到（非随机丢包，持续循环）
4. echo --once 同为 best_effort，靠概率命中完整帧（两次成功）；reliable 模式 ACK/NACK
   重传补齐 → 稳定逐秒收到
5. hz 还会创建第二路 DataReader 逼发布者发副本流加剧负载
   （arXiv ros2probe：BEST_EFFORT 饱和链路丢包 38.5%）

**社区证据源**（同款案例）：

- [CSDN 排障](https://blog.csdn.net/qq_39167050/article/details/143145263)：大点云话题 hz 不稳定，
  `echo --qos-reliability reliable` 后正常；点云降到 <1 万点/帧后 hz 恢复 → 消息大小问题而非发布者
- [rosbag2#1152](https://github.com/ros2/rosbag2/issues/1152)：370 条 PointCloud2 中 hz 只收到 ~320
- [ros2cli#843](https://github.com/ros2/ros2cli/issues/843)：hz 远差于匹配 QoS 的 C++ 订阅者
- [Stereolabs 论坛](https://community.stereolabs.com/t/frequency-differences-between-recieved-and-published-images/11465)：分片丢一片整条作废

**通用排查四步法**（工具匹配 → QoS 检查 → 分层定位 → 证据优先）：见
[ros2-qos-dds.md](../ros2-qos-dds.md)（QoS/DDS 专题，全局文档，单一事实来源）。
