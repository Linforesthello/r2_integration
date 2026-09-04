# R2 集成 · 当前完成状态

> 最后更新: 2026-09-04（状态刷新 + Phase 0 细节指针化）
> 内容: 当前完成状态快照——Phase 进度、近期完成、现役技术状态。
> 交接总览 → [07-handover.md](07-handover.md)；事件详细索引 → [retrospect/README.md](retrospect/README.md)；待办 → [pending-tasks.md](pending-tasks.md)

---

## 〇、2026-08-17 以来近期完成

| 事项 | 详情 |
|:-----|:-----|
| Nav2 降额过缝验证（08-17） | inflation_radius 0.55→0.30（local/global）修复窄缝 costmap 全灰过不去，实车验证**基本无碰撞、能通过过道**，见 [retrospect](retrospect/2026-08-17_nav2_initialpose_inflation_fix.md) |
| 全速验证决策（08-17） | **暂缓，保持降额现状**；切全速版前须先同步其膨胀参数（仍 0.55） |
| 多次设初始位姿诊断（08-17） | map 重叠 = AMCL 锁错位（机制链 + 操作纪律见 [retrospect](retrospect/2026-08-17_nav2_initialpose_inflation_fix.md)） |
| 参数提交（08-17） | nav2_params_low.yaml 膨胀参数改动 commit fc778da |
| FAST-LIO2 实车验证（08-24） | N97 部署 + VLP-16 全链路验证通过：**旋转误差 <2° / 平移 0.5%**（部署手册 [fastlio2-n97-deploy.md](n97/fastlio2-n97-deploy.md)）；08-18 前 ROS2 分支 Livox 硬依赖编译失败已解决，列为 A2 主线 |
| A1 避障首轮 + 重录决策（08-25） | W3 首轮 3 bag 漏录 /velodyne_points 与 costmap 系列 → 按 [ros2-ops.md §9](ros2-ops.md) 判**重录**；Greenwave 方案 B 选定（[greenwave-monitor-deploy.md](n97/greenwave-monitor-deploy.md)） |
| costmap 远刷闭环 + doc 整理（09-03） | costmap 远距离刷新验证闭环（[retrospect 09-03](retrospect/2026-09-03_costmap_far_refresh_closed.md)）；doc 第一层次职能拆分规则化（[retrospect 09-03](retrospect/2026-09-03_doc_engineering.md)） |
| 低物盲区断点 + bags 入仓（09-04） | relog 三层精分析**定位低物盲区断点（待重测）**（[retrospect 09-04](retrospect/2026-09-04_lowobstacle_breakpoint.md)）；bags 数据资产跨仓迁移入仓（[retrospect 09-04](retrospect/2026-09-04_bags_migration.md)） |
| 07-handover 职能拆分（09-04） | 启动命令 → [startup.md](startup.md)（全栈唯一权威）；事件索引 → [retrospect/README.md](retrospect/README.md)；07 瘦身 258→76 行（本文件为拆分后同步刷新） |

---

## 〇、2026-08-05~06 近期完成

| 事项 | 详情 |
|:-----|:-----|
| N97 远程桌面 | TigerVNC 定型（:2 / 5902），NoMachine/RealVNC 弃用，见 [retrospect](retrospect/2026-08-05_n97_remote_desktop.md) |
| VM↔N97 跨机 DDS | FastDDS 固定端口 7410 + 单播 Peer（VMware NAT 不通组播）；VM 可远程跑 rviz2 |
| IMU 协方差修复 | `[base]*9` 填满非对角项致矩阵奇异 → EKF NaN；对角化后实机验证通过，见 [retrospect](retrospect/2026-08-05_imu_covariance_ekf_nan.md) |
| 底盘里程计修复 | omega 单位多除轮半径（放大 13.2×）+ 全向轮积分；bag 对比：yaw 偏差 179°→4-14°，方形闭环 1.8m→0.27m（KISS 交叉验证），见 [retrospect](retrospect/2026-08-05_chassis_ekf_debug.md) |
| EKF 过程噪声 | robot_localization 3.5.4 需 225 值完整矩阵（15 值对角格式加载 bug 致启动 NaN）；z 漂移 85m→亚米级 |
| 数据管理 | bag 仓库统一至 `~/Lin_workspace/r2_integration/bags/`：raw/（12 个 bag 录制）+ maps/（地图产物，08-12 整理分离）+ csv/（全帧导出）+ analysis/（脚本） |
| 规范更新 | standards.md：Co-Authored-By 默认不加（仅显式要求） |

---

## 一、Phase 0：底盘 ROS2 + CAN 控制 ✅ 100%

**状态**：已完成（08-06 里程计修复：omega 单位 13.2× 多除轮半径 + 全向轮积分，闭环 1.8m→0.27m）。

> **技术细节不在本文复制**（防止与权威双份漂移，standards §1.1）：
> - 坐标系/CAN 映射/运动学公式/物理参数/协议 → [phase0/chassis_definition.md](phase0/chassis_definition.md)（唯一权威，本文原 §一 细节 2026-09-04 移入）
> - 传感器安装（IMU/雷达位置朝向，08-24 复测）→ [phase0/sensor-mount.md](phase0/sensor-mount.md)
> - 完成记录 / 踩坑 → [phase0/completion_report.md](phase0/completion_report.md) / [phase0/debug_log.md](phase0/debug_log.md)

---

## 二、Phase 1~5 状态

| Phase | 目标 | 前置 | 状态 |
|:------|:-----|:------|:------|
| **1** | G354 IMU + 轮速 → EKF 融合 | Phase 0 | ✅ 95% 实车验证完成（08-06）；yaw 方案①通过（08-12）；仅剩 slip 剧烈加减速 z 漂移严格复测（[pending-tasks.md §⑤](pending-tasks.md)，非阻塞） |
| **2** | 3D LiDAR SLAM (VLP16 + KISS-ICP) | Phase 0 | ✅ 100% 驱动+里程计+键盘建图全跑通（现役 KISS；FAST-LIO2 已实车验证可替代，见上表 08-24） |
| **3** | VLP16 + Nav2 导航 | Phase 1+2 | ⏳ 25% 首闭环（08-15）+ 降额过缝验证（08-17，无碰撞）；**A1 避障实测进行中**——08-25 首轮 + 09-04 低物盲区断点已定位待重测；全速验证暂缓（08-17 决策）；09-10 收手线见 [recruitment-learning-plan.md §4.1](roadmaps/recruitment-learning-plan.md) |
| **4** | D435 + Jetson YOLO 视觉 | Phase 0 | ⏳ 0% |
| **5** | 气动+异常处理+Robocon编排 | 全部 | ⏳ 0% |

### SLAM 方案探索结论

VLP-16 上尝试了四种 SLAM 方案（探索记录见 `retrospect/vlp16_slam_exploration.md`）：

| 方案 | 类型 | 结论 |
|:----|:-----|:-----|
| **slam_toolbox** | 2D SLAM | ❌ 不适合 VLP-16（16线3D雷达） |
| **Cartographer** | 2D SLAM | ❌ .lua 配置兼容性问题 |
| **FAST-LIO2** | 3D LIO | ⚠️ 早期 ROS2 分支硬依赖 Livox 编译失败（08-18 前）；**08-24 已在 VLP-16 实车验证通过**（旋转 <2°/平移 0.5%，[fastlio2-n97-deploy.md](n97/fastlio2-n97-deploy.md)）——现为 A2 替代主线 |
| **KISS-ICP** | 3D Odom | ✅ 安装简捷，VLP-16 原生支持，已跑通（现役） |

### 当前 VLP-16 工作状态

- [x] VLP-16 驱动（`device_ip:=10.18.18.6`, 目标 IP: `10.18.18.20`，2026-08-02 网段从 10.10.3.x 迁移）
- [x] TF 标定（base_link → velodyne **z=0.655m**，08-24 复测定案：光学中心离地 77~78cm − base_link 12cm；base_footprint 已删，车顶水平安装）— [sensor-mount.md](phase0/sensor-mount.md)
- [x] KISS-ICP 3D 里程计（topic `/velodyne_points` → odom + 注册点云）
- [x] 键盘控制 + 点云采集建图（2026-08-02 实车跑通，RViz 中 `odom_lidar` 系点云地图随车累积）
- [x] IMU 轴映射修复（8-03：mount_axes + init/Mahony 符号修正，见 [sensor-mount.md](phase0/sensor-mount.md)）
- [x] IMU 融合实车验证（G354 EKF，08-06 完成；yaw 方案① 08-12 通过，清单见 [phase1/ekf-verification.md](phase1/ekf-verification.md)）
- [ ] 雷达闭环运动（基于 `/kiss/odometry` 的 waypoint 节点，待做 — [pending-tasks.md §⑤](pending-tasks.md)）
