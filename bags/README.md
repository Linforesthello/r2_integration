# R2 bag 仓库

> 统一存放与分析 R2 底盘/IMU/EKF/KISS-ICP 建图测试数据。
> **采集在 N97** `~/Lin_workspace/r2_integration/bags/`（录制输出），VM 此目录为分析副本（含 raw/maps 完整拷贝）。
> 2026-09-04 起由独立目录并入 r2_integration 仓；raw/ 与 maps/ 不入 git
> （r2 仓 `.gitignore` 白名单：仅 analysis/csv/README/png 入库）。
> 整理日期：2026-08-12（raw/ 只留 bag 数据，地图产物全部归位 maps/）；2026-09-04（迁入 r2 仓）

## 目录

| 路径 | 内容 |
|:-----|:-----|
| `raw/` | bag 原始录制（db3 + metadata.yaml），07-30 ~ 09-03 全系列（底盘/EKF/建图/Nav2/W3/relog）；本表清单截至 08-13，此后新增 bag 见相应 retrospect（08-15 起） |
| `maps/` | 地图产物（pgm/yaml/ply/preview/对比图），按 bag 分子目录 |
| `csv/` | 底盘测试全帧分析导出（t, 轮速x/y/yaw, IMU yaw, 偏差） |
| `analysis/` | 分析脚本（官方 rosbag2_py） |

## bag 清单 — 底盘测试（07-30 ~ 08-06）

| bag | 日期 | 代码版本 | 测试内容 | 备注 |
|:----|:-----|:---------|:---------|:-----|
| r2_turn_test.bag | 07-30 | 修复前 | 转弯 | yaw 偏差最大 179° |
| r2_square_test.bag | 07-30 | 修复前 | 方形闭环 | 闭环误差 1.80m |
| r2_slip_test.bag | 07-30 | 修复前 | 直线滑移 | 闭环误差 5.74m |
| imu_zupt_test.bag | 07-30 | — | IMU ZUPT 测试 | VM 侧副本 |
| imu_test | 08-03 | — | IMU ZUPT 测试 | 08-03 新增测试 |
| r2_turn_test_after | 08-06 | 修复后 | 转弯 | yaw 偏差 4-14°，KISS 交叉验证一致 |
| r2_square_test_after | 08-06 | 修复后 | 方形闭环 | 闭环 0.27m（KISS 0.24m） |
| r2_slip_test_after | 08-06 | 修复后 | 直线滑移 | 闭环 1.08m（KISS 0.44m） |

## bag 清单 — EKF 与建图（08-08 ~ 08-12）

| bag | 日期 | 内容 | 备注 |
|:----|:-----|:-----|:-----|
| sys_audit_0808_2036 | 08-08 | 系统基线审计 | 132.5s，见 `doc/minimal-loop/0audit.md` |
| map_run_0808_2107 | 08-08 | 建图尝试 | 产物 v2 |
| map_run_0808_2132 | 08-08 | 建图尝试 | 产物 map2d/map_corridor/v3 多版迭代 |
| ekf_pure_0809_2013 | 08-09 | EKF 纯融合测试 | |
| ekf_yaw_test_0809 | 08-09 | EKF yaw 测试 | |
| map_run_0809_2133 | 08-09 | 建图（重影 bug 版本） | 修复前，见 `doc/retrospect/2026-08-09_map_double_ghost.md` |
| map_run_0811_1925 | 08-11 | KISS 帧率修复后重录 | 311.7s / 1634 帧，地图即 D4 地图 |
| stage_0812_2111 | 08-12 | 建图（新采集） | 产物 stage_0812_map（用途待核实） |
| map_take3 | 08-13 | 短段录制验证（65.9s，只录 3 点云话题） | 无重影，墙段 99 格=4.95m；验证性录制 |
| map_final_0813_1727_seg1 | 08-13 | 正式长录 seg1（直行段，35.7s） | 0 空窗，KISS 7.9Hz |
| map_final_0813_1728_seg2 | 08-13 | 正式长录 seg2（原地转 85°×2，33.9s） | 0 空窗；**原地转漂移 10-18cm 验证**（纯激光旋转退化） |
| map_final_0813_1807_seg3 | 08-13 | 正式长录 seg3（前进+左转90+右转90+回正，41.1s） | 0 空窗；**带平移约束转弯漂移 <10cm 验证通过**，正式地图候选 |

## maps/ 地图产物

| 路径 | 内容 |
|:-----|:-----|
| `maps/d4/` | D4 地图（map_run_0811_1925.pgm + map.yaml），部署副本 → N97 `~/maps/` |
| `maps/map_final_0813/` | **正式地图候选（map.pgm=seg2 版 + map.yaml，z_min 0.3 出图）+ 分段产物（seg1/seg2/seg3 的 ply/pgm/preview）**，部署副本 → N97 `~/maps/` |
| `maps/stage_0812/` | 08-12 建图产物（pgm/yaml/raw.ply） |
| `maps/map_run_0808_2107/` | 0808 建图尝试产物（map v2 系列） |
| `maps/map_run_0808_2132/` | 0808 建图尝试产物（map2d / map_corridor / v3 系列） |
| `maps/map_run_0809_2133/` | 0809 重影版本图产物 |
| `maps/map_run_0811_1925/` | 0811 图产物（ply / preview / map.yaml；pgm 见 `maps/d4/`） |
| `maps/stage_0812_map.pgm/.preview` | 与 `maps/stage_0812/` 内文件重复（归位保留，未去重） |
| `maps/compare_*.png` | 0809 vs 0811、0811 vs 0812 地图对比图 |
| `maps/map_final_0813/compare_*.png` | 0813 分段对比（seg1直行 vs seg2原地转；**seg2原地转 vs seg3前进转弯**） |
| `maps/*/layers/` | 各 bag 分层 3D→2D 重生成（layer_map.py 同参数：机体带 [0.10,0.90)，推荐层 [0.50,0.90)，导航层 cum_100_900，三态版可直接 map_server 加载）——0813 seg1/2/3 与 0808/0809/0811/0812 全部 8 组已生成（2026-08-13） |

## 分析结果摘要（2026-08-06，底盘）

| 指标 | 修复前 | 修复后 |
|:-----|:-------|:-------|
| 轮速 yaw vs IMU 最大偏差 | 179°（乱跳） | 7-20°（滑移残余） |
| 方形闭环位移差 | 1.80m | 0.27m |
| EKF z 漂移 | 85m（小时级） | 亚米级（slip 场景 +2.5m 待跟进） |

详见 `doc/retrospect/2026-08-05_chassis_ekf_debug.md`。

## 使用

```bash
# 分析脚本用法（VM，需 source /opt/ros/humble/setup.bash）
# 底盘数据全帧分析
python3 analysis/analyze_bags.py raw/2026-07-30_r2_chassis_before/r2_turn_test.bag raw/2026-08-06_r2_chassis_after/r2_turn_test_after
# 建图 bag 统计（点数/车速/帧间隔，重影根因分析）
python3 analysis/stats_map_run.py raw/map_run_0809_2133
# 点云累积建图（输出到 maps/）
python3 analysis/build_map.py raw/map_run_0811_1925 maps/map_run_0811_1925/map_raw.ply
```