# ROS2 QoS 与 DDS 问题手册（全局）

> 范围：跨项目通用的 QoS/DDS 坑、排查方法、大消息工程注意事项（全局文档，单一事实来源）
> 关联：[ros2-ops.md](ros2-ops.md)（ROS/ROS2 操作规范）｜案例：[2026-08-18_fastlio_laser_map_debug.md](retrospect/2026-08-18_fastlio_laser_map_debug.md)（/Laser_map 22MB hz 之谜全记录）
> 来源：08-18 FAST-LIO 排障（实测）+ 社区核实；**未在本项目实测的调优项均标注"待验证"**

---

## 一、QoS 四要素与兼容矩阵

| 维度 | 取值 | 说明 |
|:---|:---|:---|
| reliability | reliable / best_effort | 可靠重传 vs 尽力而为（丢片即弃） |
| durability | volatile / transient_local | volatile 不保留历史；transient_local 新订阅者能收到旧数据 |
| history | keep_last / keep_all | 只留 N 条 vs 全留 |
| depth | 队列深度 | keep_last 的 N |

**reliability 兼容矩阵**（发布者 × 订阅者）：

| 发布 \ 订阅 | reliable | best_effort |
|:---|:---|:---|
| reliable | ✅ 最稳 | ⚠️ 兼容但有损（大消息丢帧） |
| best_effort | ❌ 不兼容，收不到 | ✅ 有损 |

> **大消息（>1MB，点云/图像等）务必双向 reliable**，靠 ACK/NACK 重传补齐分片。

---

## 二、CLI 工具默认行为（源码实锤）

| 工具 | 默认 QoS | 可否改 | 大消息适用 |
|:---|:---|:---|:---|
| `ros2 topic hz` | **写死 best_effort**（qos_profile_sensor_data） | ❌ 无参数（[ros2cli#719](https://github.com/ros2/ros2cli/issues/719)，待办未合） | ❌ 假阴性"一直等" |
| `ros2 topic echo` | sensor_data（best_effort） | ✅ `--qos-reliability reliable` / `--qos-profile` / `--field` | ✅ 但全量输出刷屏 |
| `ros2 topic info --verbose` | — | — | 看发布/订阅两端实际 QoS 是否匹配 |
| `ros2 topic bw` | — | — | 字节流量监测（丢帧时的旁证） |

**大消息话题验证频率的正确姿势**：

```bash
ros2 topic echo <topic> --qos-reliability reliable --field header.stamp   # 轻量，只打印时间戳
```

或 `ros2 bag record` 后查 metadata.yaml 的 `message_count`（免费、确凿、可回溯）。

---

## 三、高频坑

1. **hz 大消息假阴性**：22MB 消息 ≈ 350 个 UDP 分片 burst，接收端 socket buffer（默认 ~212KB）
   溢出丢片，best_effort 无重传 → 缺片整条丢弃 → 持续"一直等"（结构性丢失，非随机）；
   hz 自身还会多开一路 DataReader 加剧负载（[ros2probe](https://arxiv.org/html/2606.10746v1#4)：
   BEST_EFFORT 饱和链路丢包 38.5%）
2. **reliable 发布 + best_effort 订阅**：连接能建立，但大消息实际收不全——工具显示"没有"会误导
   排障方向（08-18 教训：hz 假阴性带偏方向 1 小时，见案例文档）
3. **参数启动时一次性读取**：改 yaml 后必须重启节点（symlink-install 可免编译，但参数不重读）
4. **`ros2 topic hz` 首条消息不打印**（节流逻辑），要等第二条才出数——短时采样叠加假阴性

---

## 四、排查四步法（大消息话题无响应）

| 步骤 | 动作 | 判定 |
|:---|:---|:---|
| ① 工具匹配 | 大消息话题不用 hz；改用 echo stamp / bag record + metadata / rviz | hz 无输出 ≈ 工具限制，**先别怀疑链路** |
| ② QoS 检查 | `ros2 topic info <topic> --verbose` | 发布 reliable + 订阅 best_effort = 有损；大消息一律 reliable 订阅 |
| ③ 分层定位 | 参数层 `param get` → 执行层节点日志 → 传输层 `topic bw` → 接收层 echo/record 交叉 | 每层一个验证动作，哪层断查哪层 |
| ④ 证据优先 | bag metadata 的 message_count 钉死"当时到底有没有" | 不靠记忆/单工具下结论 |

> 教训（08-18）：跳过 ① 直接进 ③，hz 假阴性带偏方向 1 小时；"参数对不对"这类问题
> `ros2 param get` 1 秒直接问，别绕。

---

## 五、大消息工程注意事项

- **带宽量级**：22MB/帧 × 1Hz ≈ 22MB/s 持续（且随地图增长更甚）——实车/低带宽场景按需开关
  发布（FAST-LIO `/Laser_map` 即此例：日常 `map_en: false`，需要建图快照再开）
- **bag 体积**：22MB/s 录制 100s ≈ 2.2GB（实测 replay_3 仅 95.7s 即 1.5G）；录制时长与话题
  选择按此规划
- **DDS 调优方向（社区方案，本项目未验证）**：
  - FastRTPS：shared memory `segment_size`（例 128MB），经 XML +
    `FASTRTPS_DEFAULT_PROFILES_FILE` 注入
  - CycloneDDS：`SocketReceiveBufferSize`（例 10MB）+ 内核 `sysctl net.core.rmem_max`
  - 反直觉：MTU 调大（8900）实测变差（[Robotics SE](https://robotics.stackexchange.com/questions/116992/reliable-ethernet-transmission-of-large-ros2-messages-with-cyclonedds-between-mu)）——调优必须实测

---

## 六、R2 项目已实测 QoS 记录

| 话题 | 发布者 QoS | 备注 |
|:---|:---|:---|
| `/Laser_map`（FAST-LIO） | reliable, KEEP_LAST 20（laserMapping.cpp L933） | 22MB/帧全量累积地图；日常关 map_en |
| hz / echo 工具 | 见 §二 | — |

其他话题 QoS 未逐一核验，需要时以 `ros2 topic info --verbose` 实测为准。

---

## 相关

- 案例全记录：[retrospect/2026-08-18_fastlio_laser_map_debug.md](retrospect/2026-08-18_fastlio_laser_map_debug.md)
- 操作规范：[ros2-ops.md](ros2-ops.md)