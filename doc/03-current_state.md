# R2 集成 · 当前完成状态

> 最后更新: 2026-11-07（§〇 增 explore_lite 构建落地条目 + LD06 `/scan` 规格 + crop 实测条目；11-06 平台分叉口径不变；上文 Phase 状态为 VLP-16 时代基线）
> 内容: 当前完成状态快照——Phase 进度、近期完成、现役技术状态。
> 交接总览 → [07-handover.md](07-handover.md)；事件详细索引 → [retrospect/README.md](retrospect/README.md)；待办 → [pending-tasks.md](pending-tasks.md)

---

## 〇、2026-08-17 以来近期完成

| 事项 | 详情 |
|:-----|:-----|
| **S1 三份配置落文件（11-07）** | G1 `r2_bringup/config/slam_toolbox_mapping.yaml`（官方 `mapper_params_online_async.yaml` 整份复制 + 6 项改动：`base_frame→base_link`、`use_sim_time:false`、`map_update_interval:2.0`、`transform_publish_period:0.05`、`enable_interactive_mode:false`）；G2 `r2_bringup/launch/nav2_explore.launch.py`（删 map_server/AMCL，默认降额参数）；G3 `r2_bringup/config/explore_params.yaml`（global_costmap 源，冒烟确认节点名/参数读取正常、`return_to_init` 不存在）。**三者均未实测运行**，G4（老车 Nav2 参数文件）未动 — [explore-plan §3.1.2/§3.2](minimal-loop2/explore-plan.md)、[s1-readiness-gap](old-car/s1-readiness-gap.md)。**11-07 晚复核订正**：`return_to_init` 与 7 参数**并非未声明**（干净复测 `param get` 可取），原冒烟结论作废，根因 = 构造期三段串行阻塞 → [explore-plan §3.1.3](minimal-loop2/explore-plan.md) |
| **explore_lite 构建落地（11-07）** | N97 独立工作区 `~/Lin_workspace/explore_ws`：clone `326cf8a`（= 方案引用版本）+ `colcon build --packages-up-to explore_lite` 成功（`explore_lite_msgs` 4.99s / `explore_lite` 18.3s，仅 CMake 弃用警告）；`ros2 pkg executables explore_lite` = `explore_lite explore`。**G5 销项**。连带实测：`map_merge` 在 src 但不随 `--packages-up-to explore_lite` 构建（后续勿裸跑 `colcon build`）；官方 launch **写死 `params.yaml`（`/map` 源）、`use_sim_time` 默认 `true`、且未暴露 `params_file` 参数** → 只能用 `ros2 run` 或自写 launch。详见 [explore-plan §3.1.1](minimal-loop2/explore-plan.md) |
| **LD06 /scan 规格 + crop 实测（11-07）** | N97 实测：beam 452~455/圈、角分辨率 0.793~0.798°、10.00 Hz；range 0.02/25 为驱动常量（室内有效回波 ≤6.08m）；crop 只 NaN 掩盖，参数用**原始雷达角**，因 `laser_scan_dir=true` 发布角 = 360°−原始角（非对称用例钉死）。N97 重启后 udev 四路固定名仍正确。探针 [probe_laserscan.py](../scripts/probe_laserscan.py)，详见 [ld06-dual-lidar P7](old-car/ld06-dual-lidar.md) |
| **GitHub 访问根因定位 + 纠错（11-07）** | 此前「VM/N97 `git ls-remote` 均超时、原因未定位」**不成立**——根因是代理（Clash 类 TUN，`Meta 198.18.0.1/30` + fake-ip `198.18.x.x`）**未开**，非网络故障。开启后两机 `curl https://github.com` = 200（1.4~2.2s）、`git ls-remote` 均 exit=0（三次同机对照实测）。副产物：gitee 走该代理 3 次中 2 次 `SSL routines::unexpected eof`（http=000）→ **镜像路线不采用**；两机本地均无 explore_lite（`dpkg`/`find` 空）。方法经验入 [analysis-methods 主题 L](analysis-methods.md)，口径纠正见 [07-handover §五](07-handover.md) |
| **平台分叉决策（11-06）** | 老车结构无法进一步升级 → **低成本平替**：VLP-16 撤下换 LD06 串口 2D（首期单颗，二期低装/双颗）、G354 后续换 STM32+MPU6050（S3 实施）、加入 GO-M8010-6 击球机构；软件走 2D slam_toolbox + Nav2 + explore_lite。新车在本项目基础上做底盘/上层/传感器升级（D435、MID-70、后续 MID-360、单点激光），走 3D LIO + 视觉。两车共用接口/分叉清单见 [two-car-architecture.md](two-car-architecture.md)，决策记录见 [retrospect 11-06](retrospect/2026-11-06_platform_split_old_retrofit.md)。**实施顺序（B 方案）**：S1/S2 保留 G354 + 现有 EKF，S3 才换 STM32；G8010 台架独立，S4 装车 |
| Nav2 降额过缝验证（08-17） | inflation_radius 0.55→0.30（local/global）修复窄缝 costmap 全灰过不去，实车验证**基本无碰撞、能通过过道**，见 [retrospect](retrospect/2026-08-17_nav2_initialpose_inflation_fix.md) |
| 全速验证决策（08-17） | **暂缓，保持降额现状**；切全速版前须先同步其膨胀参数（仍 0.55） |
| 多次设初始位姿诊断（08-17） | map 重叠 = AMCL 锁错位（机制链 + 操作纪律见 [retrospect](retrospect/2026-08-17_nav2_initialpose_inflation_fix.md)） |
| 参数提交（08-17） | nav2_params_low.yaml 膨胀参数改动 commit fc778da |
| FAST-LIO2 实车验证（08-24） | N97 部署 + VLP-16 全链路验证通过：**旋转误差 <2° / 平移 0.5%**（部署手册 [fastlio2-n97-deploy.md](n97/fastlio2-n97-deploy.md)）；08-18 前 ROS2 分支 Livox 硬依赖编译失败已解决，列为 A2 主线 |
| A1 避障首轮 + 重录决策（08-25） | W3 首轮 3 bag 漏录 /velodyne_points 与 costmap 系列 → 按 [ros2-ops.md §9](ros2-ops.md) 判**重录**；Greenwave 方案 B 选定（[greenwave-monitor-deploy.md](n97/greenwave-monitor-deploy.md)） |
| costmap 远刷闭环 + doc 整理（09-03） | costmap 远距离刷新验证闭环（[retrospect 09-03](retrospect/2026-09-03_costmap_far_refresh_closed.md)）；doc 第一层次职能拆分规则化（[retrospect 09-03](retrospect/2026-09-03_doc_engineering.md)） |
| 低物盲区断点 + bags 入仓（09-04） | relog 三层精分析**定位低物盲区断点**（→ 09-05 修法 B 验收，见下行；[retrospect 09-04](retrospect/2026-09-04_lowobstacle_breakpoint.md)）；bags 数据资产跨仓迁移入仓（[retrospect 09-04](retrospect/2026-09-04_bags_migration.md)） |
| 07-handover 职能拆分（09-04） | 启动命令 → [startup.md](startup.md)（全栈唯一权威）；事件索引 → [retrospect/README.md](retrospect/README.md)；07 瘦身 258→76 行（本文件为拆分后同步刷新） |
| 低物盲区修法 B VM 验收 PASS（09-05） | local voxel_layer 增 velodyne_low 低带源 [0, 0.40]（[nav2_params_low.yaml](../r2_bringup/config/nav2_params_low.yaml)，commit 7b746ef）；**bag 抽帧重发法验收**：W1/W2 判据 254 格命中、89 帧证据（scan 同方位开阔排除旧源）；剩余 = N97 实车检查单 — [retrospect 09-05](retrospect/2026-09-05_lowobstacle_fixB_vm_acceptance.md) |
| retrospect 必备两节规则化（09-05） | [standards.md](standards.md) §1.14/§2.8：复盘/结案/排障长记录**必备 方法模板节 + 经验点层次标注节**（范本 = 09-05 档）；四层制决策档同步 — [retrospect 09-05](retrospect/2026-09-05_lowobstacle_fixB_vm_acceptance.md) |
| 低物实车撞箱实锤（09-06） | 实车撞箱验证：local 254 / global 无 = **global 结构性没源实锤**（修法 A 未生效期；[retrospect 09-06](retrospect/2026-09-06_lowobstacle_fixB_crashbox.md)） |
| 低物链收手定论（09-08） | 纯净三录 ring 几何律：低物盲区边界 **1.59m 实锤**（[ringlaw 09-08](retrospect/2026-09-08_lowobstacle_ringlaw_cleandata.md)）；VM A/B 验收 PASS（反转重放：OLD 归零 vs NEW 保留，[AB 验收 09-08](retrospect/2026-09-08_lowobstacle_fixB_ab_acceptance.md)）；实车第一次接近停障有效 + **二次失效根因实锤** = 新 goal 触发 global 整层清空、抹保留 mark、盲区不可再生（[secondfail 09-08](retrospect/2026-09-08_lowobstacle_secondfail_clearevent.md)）；**用户 09-08 定论收手**：机制精修停投、180077c mark-only 保留不回滚、主线转 3D 规控（[pivot 09-08](retrospect/2026-09-08_lowobstacle_pivot_decision.md)）— A1 判据 5/5 不变，09-10 收手线见 [recruitment-learning-plan.md §4.1](roadmaps/recruitment-learning-plan.md) |
| 传感器加装装法定档（09-16） | MID-70 装 VLP-16 **下方**（离地 0.55~0.65m、前倾 15~20°）+ D435 夹两雷达之间（**视觉导航栈用，不检测低物**）；拟走双雷达组合（roadmap 方案 b）。几何评价（纸面，未实测）：0.35m 箱盲区 **1.59m → 0.14~0.25m**；**近距贴地 <0.46m 无感知覆盖 → 归 L4 行为层兜底**；待办 = 实车安装结构核算（三层叠装/供电/网口）+ 外参标定（含 MID-70 倾角旋转）— [survey](surveys/sensor-mounting-layout-survey.md) |

---

## 〇（早期 08-05~06）、近期完成

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
| **3** | VLP16 + Nav2 导航 | Phase 1+2 | ⏳ 25% 首闭环（08-15）+ 降额过缝验证（08-17，无碰撞）；**A1 避障实测进行中**——08-25 首轮 + 低物链收手（09-04 断点定位 → 09-05 VM 验收 PASS → 09-06 撞箱实锤 → 09-08 实车有效 + 二次失效根因实锤 → **收手定论**，详见上表 §〇）；全速验证暂缓（08-17 决策）；09-10 收手线见 [recruitment-learning-plan.md §4.1](roadmaps/recruitment-learning-plan.md) |
| **4** | D435 + Jetson YOLO 视觉 | Phase 0 | ⏳ 0%；**传感器加装装法已定档（09-16，MID-70 下挂 VLP-16 下方 + D435 夹层，视觉导航栈定位，见 §〇）** |
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
