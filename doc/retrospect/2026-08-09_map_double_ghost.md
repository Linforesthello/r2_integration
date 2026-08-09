# 2026-08-09 地图严重重影留档（D2 阶段性总结 + 未解决问题清单）

## 现象

D2 离线建图（build_map.py → pcd_to_map.py）产出地图**严重重影**，不可用；
但流程本身已跑通（bag → 累积点云 → 占用网格 → PGM），作为阶段性成果留档。

## 数据（bag: `map_run_0809_2133`，N97 采集，1.1GB / 146.8s / 9 话题）

| 项 | 值 |
|:--|:--|
| 轨迹（KISS） | 523 帧，5.5 × 8.3 m 绕场，贯穿全程（0~145.3s） |
| 累积点云 | 2,583,600 点（522 帧，抽稀 5） |
| 占用网格 | 971×931 格 @ 0.05m，二值 0/100 |
| 地图范围 | 47 × 49 m —— **符合大场地**（用户本次扩大了活动范围） |
| 雷达视距 | 原始 kiss/frame 每帧水平视距 23.1~29.2m（p50=23.1m，522/522 帧有 >15m 远点） |

## 根因链（重影来源）

1. **KISS-ICP 帧率严重不足**：523 帧 / 145.3s ≈ **3.6Hz**（正常应跟随 velodyne 10Hz），
   82 处帧间隔 >0.5s（最大 0.7s）
2. 帧间 0.5~0.7s 的空窗期里程计漂移无约束累积 → 相邻帧点云相对错位 → **重影**
3. **大场地 + 远视距（20-29m）放大错位**：同一位姿误差下，远点偏移 = 误差 × 距离，远墙重影最严重
4. 性能瓶颈与 EKF `Failed to meet update rate` **同源**（N97 单机跑雷达+KISS+IMU+EKF+底盘，CPU 吃紧）

## 未解决问题清单

### 新问题（本次暴露）
- [ ] **KISS 帧率 3.6Hz 根因**：CPU 瓶颈 vs KISS 参数（deskew/体素/匹配策略）？未排查
- [ ] **重影消除**：帧率解决后重录重验；验收指标 = 轮廓清晰度 + 闭环误差（待定量化）
- [ ] KISS-ICP `visualize:=true` 才发布 /kiss/frame 的依赖（手册 D1b 已标注，仍未实机确认）

### 老问题（遗留，与本次无关）
- [ ] **yaw 偏差**（ekf_yaw_test_0809 实测）：filtered yaw = IMU 纯积分（f-i 恒 0.1°），
      起点偏置随机 6~10°，运动中峰值 ±14°；预案见 [phase1/ekf-yaw-plan.md](../phase1/ekf-yaw-plan.md)（方案①轮速开放 yaw，未实施）
- [ ] **N97 性能余量**：EKF 已降频 30Hz 缓解（update rate 警告消除），但 KISS 仍受限——长期需评估
      降点云分辨率/降频率/或异构分工（KISS 移到更强的机器）
- [ ] EKF z 漂移：已修复（two_d_mode），见 [2026-08-09_ekf_z_drift_fix.md](2026-08-09_ekf_z_drift_fix.md)，回归项

## 阶段性成果（保留价值）

- D1b/D2 离线建图链路（build_map.py + pcd_to_map.py）**首次全程跑通**：采集 → 传回 → 离线累积 → 网格
- 采集规范有效：9 话题齐（含 /kiss/frame、/imu/data、/cmd_vel）
- 大场地（20m+ 视距）下数据行为符合预期（轨迹 8m、地图 48m 由视距决定）

## 相关文件

- `bags/analysis/build_map.py`、`bags/analysis/pcd_to_map.py`（D2 脚本）
- `doc/minimal-loop/w1-operation.md`（D2 流程定义）
- bag 存档：`Lin_workspace/bags/raw/map_run_0809_2133`（VM 分析副本）
