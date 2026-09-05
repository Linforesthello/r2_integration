# R2 集成 · 状态交接

> 最后更新: 2026-09-05（低物盲区修法 B VM 验收 PASS 状态刷新）
> 当前进度: Phase 0 ✅ 100%｜Phase 1 ✅ 95%（08-12 yaw 方案①通过）｜Phase 2 ✅ 100%（KISS 建图）｜Phase 3 ⏳ 25%（Nav2 首闭环 08-15 + 降额过缝 08-17；A1 避障实测进行中，低物盲区断点定位 09-04 → 修法 B VM 验收 PASS 09-05，实车验证待 N97 检查单）
> 下一阶段: A1 避障收口（判据 5/5）→ A2 FAST-LIO2 落地（排期与 09-10 收手线见 [recruitment-learning-plan.md §4.1](roadmaps/recruitment-learning-plan.md)）
> 基础设施: 08-14 两机 git 同步统一（push→pull）；08-15 VLP-16 运行物抽包 r2_sensors；08-24 N97 风扇可命令行调速；09-04 bags 数据资产入仓
>
> **部署环境**：实车 = N97 Mini PC（192.168.1.210，Ubuntu 22.04 + Humble，enp1s0: 10.18.18.20/24）；开发 = VM（lin-virtual-machine，192.168.1.204，VM→N97 SSH 免密）
> **网络**：VLP-16 雷达 IP **10.18.18.6**（2026-08-02 从 10.10.3.6 迁移）

---

## 一、当前进度总览

| Phase | 目标 | 状态 | 说明 |
|:------|:-----|:----:|:-----|
| 0 | 底盘 ROS2 + CAN 控制 | ✅ 100% | 四全向轮，全命令可用；定义见 [chassis_definition.md](phase0/chassis_definition.md) |
| 1 | G354 IMU + 轮速 EKF 融合 | ✅ 95% | 实车验证完成（08-06）+ yaw 方案①通过（08-12）；仅剩 slip 剧烈加减速严格复测（见 §四） |
| 2 | VLP16 + KISS-ICP SLAM | ✅ 100% | 驱动 + 3D 里程计 + 键盘建图跑通；FAST-LIO2 已验证可作替代（08-24） |
| 3 | VLP16 + Nav2 导航 | ⏳ 25% | 首闭环 08-15、降额过缝 08-17（inflation 0.30）；A1 避障：08-25 首轮 + 低物盲区断点定位（09-04）+ 修法 B VM 验收 PASS（09-05，实车验证待 N97 检查单），全速验证暂缓保持降额 |
| 4/5 | 视觉 / 气动+编排 | ⏳ 0% | — |

> 各阶段验证细节、事件结论见 [retrospect/README.md](retrospect/README.md)（事件索引）；进度百分比看板见 [02-progress.md](02-progress.md)。

---

## 二、系统定义与文档导航（交接快速索引）

| 要找什么 | 去哪 |
|:---|:---|
| 底盘定义（坐标系/CAN 映射/运动学/参数） | [phase0/chassis_definition.md](phase0/chassis_definition.md)（唯一权威） |
| 传感器安装/朝向/轴定义（IMU/VLP-16，含 08-24 复测） | [phase0/sensor-mount.md](phase0/sensor-mount.md) |
| **启动命令（全栈唯一权威，按模式选终端）** | **[doc/startup.md](startup.md)** |
| FAST-LIO2 部署/外参/启动/排障 | [n97/fastlio2-n97-deploy.md](n97/fastlio2-n97-deploy.md) |
| N97 运维（部署清单/风扇/VNC/监测） | [n97/](n97/) 各手册 |
| 近期待办入口 | [pending-tasks.md](pending-tasks.md)（每条一句话 + 源文档） |
| 排障/事件结论速查 | [retrospect/README.md](retrospect/README.md) |
| 实验数据资产（bag/地图清单） | [bags/README.md](../bags/README.md) |
| 文档/操作规范 | [standards.md](standards.md) ｜ [ros2-ops.md](ros2-ops.md) ｜ [doc-engineering.md](doc-engineering.md) |

**新会话阅读路线**：本文件（状态）→ 按任务进 §二 对应文档；先看规范则从 [README](../README.md) 起。

---

## 三、关键认知与纪律

**已完成能力（Phase 0→2 基线）**：底盘 ROS2+CAN 全向轮控制/里程计/TF/键盘遥控；VLP-16 驱动 + KISS-ICP 3D 里程计建图；G354 IMU + 轮速 EKF 融合链路（/odometry/filtered）；FAST-LIO2 实车验证（08-24，旋转误差 <2° / 平移 0.5%）。N97 单机跑全套是性能瓶颈——CPU 余量优先于功能扩展。

**遗留现象（算法本底，非故障）**：
- KISS-ICP 静止/运动均有毫米~厘米级抖动：纯激光配准本底（无 IMU 融合）
- 旋转时点云更新滞后，静止后恢复：旋转运动畸变，deskew 外推校不准
- 长期方案 = FAST-LIO2（已验证）；Nav2 场景仍 AMCL 定位不跑 LIO（08-15 决策）

**实机纪律（启动/操作，命令见 startup.md）**：
1. 每次开机切 CPU performance（powersave 掉到 3.6Hz → 建图重影）；IMU 静止 3s 校准后才可起 EKF，重启 IMU 须同时重启 EKF
2. Nav2 初始位姿：启动初期设偏可静止重设 1~2 次（08-25 验证有效）；**运行中不要重设**（多次设 → map 重叠）；设完先动一下确认收敛
3. 首次实机/新参数一律降额（速度 20%/力矩 30%），上电前检查清单，失控先拍急停（[ros2-ops.md §8](ros2-ops.md)）
4. 改配置后必须 build 或同步 install 副本再重启（launch 加载 install 副本，[ros2-ops.md §2](ros2-ops.md)）

**配置警示**：Nav2 降额版 `nav2_params_low.yaml` 膨胀 0.30 + **09-05 增 velodyne_low 低带源**（local voxel_layer，[0,0.40] odom 系，修法 B）；**全速版 `nav2_params.yaml` 仍是 0.55 且无低带源**，切回前须先同步两项（膨胀 0.55→0.30 见 [retrospect 08-17](retrospect/2026-08-17_nav2_initialpose_inflation_fix.md)，低带源见 [retrospect 09-05](retrospect/2026-09-05_lowobstacle_fixB_vm_acceptance.md)）；N97 风扇调速**不持久化**，重启后需手动 modprobe（[retrospect 08-24](retrospect/2026-08-24_n97_fan_control.md)）。

---

## 四、交接级遗留（交接视角；全量待办入口见 [pending-tasks.md](pending-tasks.md)）

- [ ] **低物盲区修法 B 实车验证**（VM 已 PASS 09-05）：N97 检查单 = install 副本同步（colcon build）→ 启动验证 → publish_voxel_map → 带顶 0.40 评估 — [retrospect 09-05](retrospect/2026-09-05_lowobstacle_fixB_vm_acceptance.md)
- [ ] **Nav2 全速验证**（暂缓 08-17，保持降额现状）：切 `nav2_params.yaml` 前先同步膨胀 0.55→0.30 **及 velodyne_low 低带源块**再复测
- [ ] **AMCL 多次设初始位姿 → map 重叠**（边界：仅指导航运行中反复设）：待 N97 确认日志 "Ignoring initial pose"，必要时加 `always_reset_initial_pose: true` — [retrospect 08-17](retrospect/2026-08-17_nav2_initialpose_inflation_fix.md)
- [ ] **z 回归项**：slip 剧烈加减速 z 漂 +2.5m（08-05 遗留）严格复测 — [retrospect 08-05](retrospect/2026-08-05_chassis_ekf_debug.md)
- [ ] **VNC 开机自启**（N97 重启后远程桌面不丢）— [n97_remote_desktop.md](n97/n97_remote_desktop.md)
- [ ] **FAST-LIO2 TF 桥集成**（静态桥 camera_init↔odom + body→base_link；方案已定 08-18）— [fastlio2-n97-deploy.md §五](n97/fastlio2-n97-deploy.md)
- [ ] 可选：VLP-16 rpm 600→1200（20Hz）帧内畸变试验 ｜ waypoint 雷达闭环（基于 /kiss/odometry 自主行走）
