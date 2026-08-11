# 2026-08-11 KISS 帧率修复：重影根因实锤与消除（performance 治理器）

## 结论速览

**根因**：N97 CPU 频率治理器为 `powersave`（低频 800MHz 附近），KISS-ICP 单帧处理 ~200ms，
10Hz 雷达输入只能隔帧处理 → 输出 3.6Hz → 帧间空窗位姿漂移累积 → 地图重影。

**修复**：切 `performance` 治理器（一行命令，临时生效）→ KISS 恢复 9.5Hz → 重录 bag 重跑 D2 建图，
**地图重影消除，结构清晰**。

## 排查过程（数据实锤，非猜测）

### 1. 用户假设验证（08-11，bag 实测 map_run_0809_2133）

| 假设 | 实测 | 结论 |
|:--|:--|:--|
| 扫描范围太小/点数少 | 每帧 22,042~26,407 点（VLP-16 满量程约 3 万），**接近满点**；77% 点在 5m 内 | ❌ 否决 |
| 车体快速转移 | 指令线速恒 0.24m/s、角速 max 0.48rad/s，**并不快** | ⚠️ 部分（空窗期位移确实大） |
| 多帧图像重叠 | 重影=多帧点云错位重叠，机制对 | ✅ 机制对，但错位源头不是点数/车速 |

### 2. 输入输出频率对比（实锤）

```
/velodyne_points: 9.92 Hz，dt 恒 101ms，无掉帧        ← 输入正常
/kiss/frame:      3.60 Hz，p50=202ms ≈ 2×101ms        ← KISS 隔帧处理
```

p50 恰好是 2 倍输入周期 = **规律性隔帧丢帧**（非偶发卡顿）→ 单帧处理时间 ~200ms → CPU 瓶颈。

### 3. 环境排查（N97 实机）

- CPU: Intel(R) N97（4 核 Alder Lake-N，max 3.6GHz）
- **cpufreq governor = powersave** ← 元凶（CPU 倾向停低频，睿频不积极）
- KISS 参数偏重（算力开销大）：deskew: True / voxel_size 0.2 / max_points_per_voxel 20 / max_range 30

## 修复动作

```bash
# N97，切性能模式（临时，重启恢复 powersave）
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
# 验证
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor   # → performance
```

**未改任何 KISS 参数**。

## 验证（08-11，N97 实测 + bag 重录重跑）

### 帧率对比

| 指标 | 08-09（powersave） | 08-11（performance） |
|:--|:--|:--|
| /kiss/odometry | 3.6 Hz（p50=202ms） | **9.5 Hz**（p50=101ms） |
| /kiss/local_map | 3.6 Hz | 9.4 Hz |

### 重录 bag 对比（map_run_0811_1925，311.7s / 1634 帧）

| 指标 | 08-09 | 08-11 |
|:--|:--|:--|
| 帧间位移 p50 | 4.8 cm | **0.7 cm**（1/7） |
| 帧间位移 p90 | 24.5 cm | **6.4 cm** |
| >0.5s 空窗 | 82 处 / 145s | 102 处 / 311s（占比 6% 残留，见遗留） |
| 累积点 | 258 万（522 帧） | 811 万（1634 帧） |

### 地图质量

- 08-09：48.6×46.6m，中心区域墙线糊成一团**无结构**（多帧错位重叠）
- 08-11：32.5×49.9m，**规则结构清晰**（长直墙/直角/走廊），重影消除
- 对比图：`bags/raw/compare_0809_vs_0811_final.png`（四格：新旧全景 + 中心放大）
- ASCII 放大对比确认：0809 混沌厚块 vs 0811 可辨结构

## 遗留问题

- [ ] **performance 未持久化**：N97 重启恢复 powersave。需 systemd 服务或 udev 规则固化（待办，简单）
- [ ] **长尾空窗残留**：102 处 >0.5s（占比 6%，max 2.7s），帧率中位数已满 10Hz 但仍有偶发停顿
      ——疑录制时磁盘写 bag/其他负载，未排查，对地图影响已不致命
- [ ] D4 地图复用验证（重启后加载地图 rviz 回显）未做

## 相关文件

- 分析脚本（新增）：`bags/analysis/stats_map_run.py`（点数/车速/帧间隔/帧间位移统计）
- 重影留档（承接）：[2026-08-09_map_double_ghost.md](2026-08-09_map_double_ghost.md)
- bag 存档：`bags/raw/map_run_0809_2133`（修复前）/ `map_run_0811_1925`（修复后，2.5GB）
- 地图：`bags/raw/map_run_0811_1925.pgm/.ply/map.yaml`
