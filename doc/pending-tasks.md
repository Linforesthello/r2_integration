# R2 近期待办汇总（入口索引）

> 建档：2026-09-03 ｜ 关联：[07-handover.md](07-handover.md) §六（交接核心待办摘要）、[02-progress.md](02-progress.md)（进度看板）
>
> **本文只做入口汇总**：每条 = 一句话待办 + 指向承载详情/状态的源文档链接，不展开细节。
> 状态变化时改源文档，并顺手更新/删除本文对应行；以源文档为唯一事实来源（standards.md §1.1）。
> 分组：① 当前主线（阶段一线 1/线 2）→ ② 运维 → ③ 遗留收尾 → ④ 远期池。

## ① 当前主线 · R2 导航（阶段一 线 1）

> 权威排期与收手纪律见 [recruitment-learning-plan.md §4.1](roadmaps/recruitment-learning-plan.md)；**09-10 = R2 补数收手线**（判据未满即记录缺口收手，不拖期）。

- 参数盘点：N97 侧代码与 08-25 基线一致性核对（nav2 参数/urdf/launch）+ 四问题处置全景核对 — [recruitment-learning-plan.md §4.1 步骤 0](roadmaps/recruitment-learning-plan.md)
- 全话题重录（静置/高箱三段式 + 三层断点判定；补 /velodyne_points 与 costmap 系列）— [relog-operation.md](minimal-loop2/relog-operation.md)；前置：/scan 需在跑（velodyne_laserscan 恢复）
- 静态绕行 ×3（与 08-25 基线同参数，不新增变量）— [recruitment-learning-plan.md §4.1](roadmaps/recruitment-learning-plan.md)
- 动态人横穿 ≥2 + 恢复行为 ≥1 + 综合演练 3 连 → A1 判据 5/5（08-25 仅跑一天未满）— [execution.md A1 卡](minimal-loop2/execution.md)
- 到达误差 <0.5m 测量（analyze_nav2_goal_error.py）+ 无碰撞 + rviz 显示项确认 + 复盘留档 — [w2-operation.md D7](minimal-loop/w2-operation.md)
- A1 达标后同日加跑：运动模式「方案①」改前/改后对比（受 09-10 收手线约束）— [planning-control-roadmap.md §5.7ter](roadmaps/planning-control-roadmap.md)、[costmap_experiment.md §五](minimal-loop2/costmap_experiment.md)
- 排一个 N97 实车窗口日期，把实操路线 ①~⑤ 倒排成小时级操作卡（引用既有执行卡，不新建文档）— [raw_实操路线_2026-09-02_2139.md 后记](raw_data/raw_实操路线_2026-09-02_2139.md)

## ② 求职/学习线（阶段一 线 2，exit 清单 09-30）

> 全部条目以 [recruitment-learning-plan.md §4.2/§4.4](roadmaps/recruitment-learning-plan.md) 为权威。

- 双版简历 v2（素材清单卡 6 项逐勾）；08-23 版可先投，不阻塞 — §4.2
- 作品集项目页 ×2 + 单项目 5 分钟深挖稿（R2 导航闭环 / FAST-LIO2 二选一等素材库决定）— §4.2
- 双线投递启动（岗位信息来源池维护）；每场面试 24h 内复盘回写信息池 — §4.2
- 阶段一 exit（09-30）：简历 v2 / 投递推进 / A1 收口 / 项目页 / 素材入库 / 面试复盘六项齐 — §4.4
- 附项：车体健康检查清单执行状态确认（参数核对 + hz 基线表）— [recruitment-learning-plan-review.md §3.5](roadmaps/recruitment-learning-plan-review.md)

## ③ FAST-LIO2（A2 主线，正式开工入阶段二）

> 决策点与操作卡见 [execution.md A2 卡](minimal-loop2/execution.md)；部署手册 [fastlio2-n97-deploy.md](n97/fastlio2-n97-deploy.md)。

- TF 桥集成：静态 `/tf_static` 桥 camera_init↔odom + body→base_link（用途/双父处理/外参 (-0.36,-0.035,+0.185) 三决策点）— [execution.md A2](minimal-loop2/execution.md)、[fastlio2-n97-deploy.md §五/§八](n97/fastlio2-n97-deploy.md)
- 建图源切换：KISS → FAST-LIO2 重建图（map_en 开关 + 服务保存 + z_min 抬高 ~0.1 判据）— [execution.md A2 判据](minimal-loop2/execution.md)、[relog-operation.md](minimal-loop2/relog-operation.md)
- 可选：LI-Init 自动标定（官方 ROS1，需容器/移植评估；外参已手测不阻塞）— [fastlio2-n97-deploy.md §3.1](n97/fastlio2-n97-deploy.md)
- 远期：FAST-LIO-Localization 3D 重定位（弃 AMCL 正路，未排期）— [fastlio2-n97-deploy.md §五](n97/fastlio2-n97-deploy.md)

## ④ N97 运维 / 工具链

- TigerVNC 开机自启（systemd 用户/系统单元方案已写，未落地）— [n97_remote_desktop.md §4](n97/n97_remote_desktop.md)
- NoMachine（/usr/NX:4000）待 VNC 稳定后卸载；`/tmp/.X11-unix/X1` 历史占用来源未查明 — [n97_remote_desktop.md §4](n97/n97_remote_desktop.md)
- Greenwave Monitor：N97 真机部署（VM 已验证）+ §6 四项待验证（launch 参数名/QoS 兼容/STALE 行为）— [greenwave-monitor-deploy.md](n97/greenwave-monitor-deploy.md)
- N97 风扇 it87 驱动持久化 — **08-24 用户决策暂不做**，重启后需手动 modprobe + pwm — [n97info.md](n97/n97info.md)
- performance 治理器 systemd 固化 — 暂缓，已入每次开机手动流程 — [07-handover.md §三 前置 0](07-handover.md)

## ⑤ 排障/技术遗留（非主线，随手收）

- **z 漂移回归项**：slip 场景剧烈加减速 z 漂 +2.5m 严格复测 — [07-handover.md §六](07-handover.md)、[02-progress.md](02-progress.md)
- **AMCL 多次设初始位姿 → map 重叠**：待 N97 确认日志是否 "Ignoring initial pose"，必要时 `always_reset_initial_pose: true`（注意边界：仅指导航运行中反复设位姿）— [retrospect 08-17](retrospect/2026-08-17_nav2_initialpose_inflation_fix.md)、[07-handover.md §六](07-handover.md)
- **costmap 实验收尾**：修 pub_simple_scan.py 退出 1（查 /tmp/pub_dist.log）；远距离 2/3/4/5m mark 重测（判据未满）；N97 侧 lifecycle 激活态 + 远端实测 — [costmap_experiment.md §四/§五](minimal-loop2/costmap_experiment.md)
- **W2 收尾核对**：D5-6 连续导航（≥5 goal 含 90° 转角）+ D7 验收项是否已随 A1 覆盖 — [w2-operation.md](minimal-loop/w2-operation.md)
- **waypoint 雷达闭环**：基于 /kiss/odometry 的自主行走节点（待做）— [07-handover.md §六](07-handover.md)
- 全速版 Nav2 验证 — **暂缓（08-17 决策）**；切回前须先同步 nav2_params.yaml 膨胀 0.55→0.30 — [07-handover.md §六](07-handover.md)
- 可选：VLP-16 rpm 600→1200（20Hz）帧内畸变试验 — [07-handover.md §六](07-handover.md)
- 可选：VLP-16 vs MID-70 实机 A/B（触发条件已满足，未做）— [planning-control-roadmap.md §3.4](roadmaps/planning-control-roadmap.md)
- 可选：MPPI batch 调优（视 N97 CPU 实测）— [nav2-bringup.md](minimal-loop/nav2-bringup.md)
- 遗留现象（算法本底非故障）：KISS 抖动/旋转点云滞后 → 长期方案已由 FAST-LIO2 承接 — [07-handover.md §五](07-handover.md)

## ⑥ 远期池（阶段二+ / 计划态，仅入口备查，不排期）

- A2 建图源切换重建图 + 方案①对比（若线 1 收手前未加跑）→ 阶段二主交付 RL 局部避障 v1（Isaac Lab + R2 实车 A/B vs MPPI）— [recruitment-learning-plan.md §5.1](roadmaps/recruitment-learning-plan.md)
- 运动线：Go2 地形扩展（SO-101/机械臂明确不做）— [recruitment-learning-plan.md §5.1](roadmaps/recruitment-learning-plan.md)、[motion-control-roadmap.md §七](roadmaps/motion-control-roadmap.md)
- LocoWiki 两轮扫读 + 复现 1~2 开源项目；里程碑：10 底 A2+RL 首数据 / 11 底复现 1 / 12 底题库骨架 — [recruitment-learning-plan.md §5.2](roadmaps/recruitment-learning-plan.md)
- 全向轮运动模式方案①运动学专项（未定论，秋招后处理）— [planning-control-roadmap.md §5.7ter](roadmaps/planning-control-roadmap.md)
- Phase 4 D435+Jetson 视觉（0%）与 Phase 5 气动+异常+编排（0%）— [02-progress.md](02-progress.md)
- MBD 状态机（MATLAB/Simulink 部署路径未定，秋招后优先）；探索效率升级路 explore_lite — [planning-control-roadmap.md §5.7bis/§5.8](roadmaps/planning-control-roadmap.md)
- STM32/MCLM 技术栈 LocoWiki「翻译层」整理（低优先级）— [planning-control-roadmap.md §6.8](roadmaps/planning-control-roadmap.md)
