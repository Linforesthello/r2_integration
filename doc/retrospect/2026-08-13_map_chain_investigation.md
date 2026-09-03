# 建图链路排查：3D→2D 地图质量差 → 重影根因定位与 time 字段之谜（2026-08-13）

> 事件：D4 地图复用验证时发现 3D→2D 地图质量差（重影/旋转偏移/地面脏），用户要求"梳理流程，检查全链路"。
> 结果：地面脏 = z 滤波参数问题（已修）；重影 = 录制期 CPU 争抢（已定位，正式长录验证中）；
> velodyne time 字段之谜 = `timing_offsets` 不是参数（已澄清，假参数已删）。

---

## 一、结论摘要

| 现象 | 根因 | 处置 |
|:-----|:-----|:-----|
| 地图"地面脏"（雾状占用） | pcd_to_map `z_min=0.1` 未滤地面：雷达装高 0.56m，下射环打地面 z≈0~0.3，投影 34431 命中格中 **9668 个（28%）是地面雾格** | 默认 z_min 0.1→**0.3**（脚本+文档已改） |
| 0811 地图重影 | 录制期 CPU 争抢 → KISS 掉帧：0811 录制中 **5.24Hz**（非 9.5Hz）、**102 处 >0.5s 空窗**、max 2.7s、帧间位移 p90 6.4cm/max 65.7cm → 位姿质量差 | 录制纪律：短段（≤3min）+ 只录必要话题 + 关 GUI + 全程盯 hz，见 [w1-operation.md D3b](../minimal-loop/w1-operation.md) |
| velodyne time 字段 100% 填充但参数查不到 | `timing_offsets` 是 RawData **内部成员变量**（发射时间偏移表），**不是 ROS 参数**；time 字段由 unpack 无条件填充 | launch 假参数 `timestamp`/`timing_offsets` 已删；KISS deskew **一直有有效输入**，与重影无关 |
| take3 短段录制无重影 | 录制条件改善（65.9s、只录 3 话题、CPU 争抢小、KISS 7.7Hz） | 结论：**重影与 deskew/时间对齐无关，是录制条件问题**（正式长录验证中） |

---

## 二、排查链（按时间顺序）

### 1. D4 地图复用验证 → 地图质量差

map_server 加载 map_run_0811_1925 + rviz 回显。先后踩坑（已解决）：
- `/map` 收不到：TRANSIENT_LOCAL（latched）+ 单次发布，`ros2 topic hz` 默认 volatile 收不到
- rviz 无 map frame：只跑 map_server 无定位节点，临时 `static_transform_publisher map odom`
- rviz "no map received"：Map display 默认 Volatile，需手动设 **Durability=Transient Local**

### 2. 全链路梳理（bag → 3D ply → 2D pgm）

链路：`bag(/kiss/frame × /kiss/odometry) → build_map.py（抽稀5、最近邻时间对齐、R@pt+t 世界系累积）→ 3D ply → pcd_to_map.py（z 滤波→xy 栅格化→命中≥3=占用）→ pgm+yaml`

### 3. 地面脏实锤（z 滤波参数问题）

- 雷达装高 0.56m，z<0.3 的点 = 下射环地面点
- 0811 地图统计：投影命中 34431 格中 **9668 格（28%）来自地面点**（z<0.3）
- 0.1~1.5 全高度叠合 → 墙厚虚增 + 地面雾
- **修复**：z_min 0.1→0.3，pcd_to_map.py 默认值 + w1-operation.md 副本同步（2026-08-13）

### 4. 0811 重影根因定位（录制期 CPU 争抢）

- stats_map_run.py 统计 0811 bag：KISS **5.24Hz**（应 9.5Hz）、帧间隔 p50=101ms/p90=304ms/**max=2.7s**、
  **102 处 >0.5s 空窗**、帧间位移 p90=6.4cm/max=65.7cm、空窗期间位移中位 13.3× 普通帧
- bag record 写盘（/velodyne_points + /kiss/frame 双 ~6MB/s 点云流）+ KISS 抢 N97 4 核 → KISS 掉帧
- 时间对齐无误差假设已排除（/kiss/frame 与 /kiss/odometry 同帧发布，时间戳差 0ms）
- 录后 0~1Hz 需重启 KISS：热降频滞后或 bag record 进程残留（积压假设被 SensorDataQoS depth=5 推翻）

### 5. take3 短段录制验证（干净）

- 65.9s、只录 3 点云话题、9.6Hz（/velodyne_points 634 帧）/7.7Hz（/kiss 508 帧）
- 出图：墙段最长 **99 格=4.95m**（0811 C 图 81 格=4.05m），无重影 → 干净 ✅

### 6. velodyne time 字段之谜（源码实锤）

- 现象：点云带 time 字段（100% 填充，范围 [-0.0996, +0.0013]），但 `ros2 param get /velodyne_transform_node timing_offsets` → Parameter not set + 启动 WARN "Failed to get parameters: timing_offsets"
- 源码（velodyne ros2 分支，VM `~/kiss_icp_ws/src/velodyne_src`）：
  - [transform.cpp:59-104](../../../kiss_icp_ws/src/velodyne_src/velodyne_pointcloud/src/conversions/transform.cpp#L59-L104)：declare_parameter 仅 9 个（calibration/model/min_range/max_range/view_direction/view_width/fixed_frame/target_frame/organize_cloud），**无 timestamp/timing_offsets**
  - [rawdata.cpp:115](../../../kiss_icp_ws/src/velodyne_src/velodyne_pointcloud/src/lib/rawdata.cpp#L115)：`timing_offsets_` = RawData **内部成员变量**（block/firing 发射时间偏移表），由 setupTimingOffsets* 系列内部计算
  - [rawdata.cpp:329-330](../../../kiss_icp_ws/src/velodyne_src/velodyne_pointcloud/src/lib/rawdata.cpp#L329-L330)：unpack 对每点 `time = timing_offsets_[i][j] + time_diff_start_to_this_packet`，**无条件填充，无参数开关**
- 结论：`timestamp`/`timing_offsets` 均为**未声明假参数**，从未生效；time 字段一直是默认行为 → KISS deskew（Utils.hpp 查 t/timestamp/time 字段）一直有有效输入

### 7. 处置完成

- launch 假参数删除（`~/.ros/velodyne_n97.launch.py`，备份 .bak_20260813）✅
- 重启后验证：fields 长度 6（XYZIRT，time offset=18 datatype=7 float32）✅
- pcd_to_map.py z_min 默认 0.3 ✅

---

## 三、遗留与待办

- [ ] **正式长录**（w1-operation.md D3b 纪律）：验证 take3 结论在长录制/多地形下成立 → 产出正式地图
- [ ] D4 收尾：0811 旧图用 z_min=0.3 重投影重新出图部署 N97（或直接用正式长录新图）
- [ ] 录后 KISS 0~1Hz 现象：热降频滞后 vs 进程残留仍未 100% 定性（正式长录时观察记录）

## 四、关键数据留档

| 指标 | 0811（重影） | take3（干净） |
|:-----|:-----|:-----|
| 时长 | 229.5s（1449 帧） | 65.9s（508 帧） |
| KISS 帧率 | 5.24Hz（max 间隔 2.7s） | 7.7Hz |
| 空窗 >0.5s | 102 处 | 无 |
| 最长连续墙段 | 81 格 = 4.05m | 99 格 = 4.95m |
| 重影 | 有 | 无 |

## 相关

- 手册：[w1-operation.md D3b](../minimal-loop/w1-operation.md)（正式长录纪律）
- 帧率根因：[2026-08-11_kiss_frame_rate_fix.md](2026-08-11_kiss_frame_rate_fix.md)（powersave→performance）
- 重影留档：[2026-08-09_map_double_ghost.md](2026-08-09_map_double_ghost.md)
- 脚本：[pcd_to_map.py](../../bags/analysis/pcd_to_map.py)（z_min 默认 0.3，2026-08-13 修正）
