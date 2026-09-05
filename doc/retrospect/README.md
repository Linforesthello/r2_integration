# retrospect · 事件记录目录索引

> 定位：`doc/retrospect/` 的**结论速查索引**——「某类问题当时怎么解决的」先查此表，点详情看完整排障/复盘。
> 规则：文件命名 `YYYY-MM-DD_主题.md`（专题探索无日期前缀）；新增事件记录后，在本文登记一行，并同步根 README 文件树。
> **必备结构（2026-09-05 起，见 standards §2.8）**：每篇须含「方法模板节」+「经验点层次标注节」再登记；范本 = [2026-09-05_lowobstacle_fixB_vm_acceptance.md](2026-09-05_lowobstacle_fixB_vm_acceptance.md)
> 本文只承载「一句话结论」；详情一律以各文件为准（standards.md §1.1 单一事实来源）。
> 状态类信息以 [07-handover.md](../07-handover.md)（交接）/ [pending-tasks.md](../pending-tasks.md)（待办）为准。

---

## 索引（按日期）

| 文件 | 一句话结论 |
|:---|:---|
| [2026-07-31_chassis_launch_fix.md](2026-07-31_chassis_launch_fix.md) | chassis.launch.py 路径修复 |
| [2026-07-31_claude_md_import_setup.md](2026-07-31_claude_md_import_setup.md) | 流程模式：Claude 优先读到文档 |
| [2026-07-31_teleop_keyboard_fix.md](2026-07-31_teleop_keyboard_fix.md) | 键盘控制修复全记录（WASD 遥控） |
| [2026-07-31_workspace_check_fix.md](2026-07-31_workspace_check_fix.md) | r2_integration 工作区检查与修复 |
| [2026-08-02_ekf_tf_fusion_fix.md](2026-08-02_ekf_tf_fusion_fix.md) | EKF/TF 融合链路 7 问题全解决（网络迁移/use_sim_time/imu_link/QoS/双发布者/协方差/ekf.yaml） |
| [2026-08-02_vlp16_switch_network.md](2026-08-02_vlp16_switch_network.md) | VLP-16 交换机接入方案（IP 迁移 10.10.3.6→10.18.18.6；NVRAM 重启清 ARP 经验） |
| [2026-08-03_r2_repo_repair.md](2026-08-03_r2_repo_repair.md) | r2_integration 仓库修复全记录 |
| [2026-08-05_chassis_ekf_debug.md](2026-08-05_chassis_ekf_debug.md) | 底盘里程计修复 + EKF 过程噪声 225 值矩阵排障 |
| [2026-08-05_imu_covariance_ekf_nan.md](2026-08-05_imu_covariance_ekf_nan.md) | IMU 协方差病态 → EKF NaN 排障 |
| [2026-08-05_n97_remote_desktop.md](2026-08-05_n97_remote_desktop.md) | N97 远程桌面三方案排障（定型方案见 [n97/n97_remote_desktop.md](../n97/n97_remote_desktop.md)） |
| [2026-08-06_git_ops_lessons.md](2026-08-06_git_ops_lessons.md) | Git 操作教训（reset 误伤 / Co-Authored-By 规则） |
| [2026-08-09_ekf_z_drift_fix.md](2026-08-09_ekf_z_drift_fix.md) | EKF z 漂移修复（two_d_mode + az noise 1e-6，TF z 恒 0） |
| [2026-08-09_map_double_ghost.md](2026-08-09_map_double_ghost.md) | 地图重影排查（留档，根因 = KISS 帧率 3.6Hz，见 08-11） |
| [2026-08-10_vocalinux语音输入.md](2026-08-10_vocalinux语音输入.md) | Vocalinux 本地语音输入调试总结 |
| [2026-08-11_kiss_frame_rate_fix.md](2026-08-11_kiss_frame_rate_fix.md) | KISS 帧率 3.6→9.5Hz（N97 CPU powersave → performance 治理器）→ 建图重影消除 |
| [2026-08-11_r2_bringup_code_review.md](2026-08-11_r2_bringup_code_review.md) | r2_bringup 代码审查 P1~P10 全修复 |
| [2026-08-13_layer_map_3d2d.md](2026-08-13_layer_map_3d2d.md) | 分层 3D→2D 导航层生成（多层对比 + 选层 + seg3 剔除） |
| [2026-08-13_map_chain_investigation.md](2026-08-13_map_chain_investigation.md) | 建图链路排查（重影根因 + z_min 修正 + time 字段之谜） |
| [2026-08-14_vm_vlp16_dds_fix.md](2026-08-14_vm_vlp16_dds_fix.md) | VM 单机 DDS 根因修复（bashrc 跨机配置掐死本机发现 + daemon 缓存） |
| [2026-08-15_clean_bag_rerecord.md](2026-08-15_clean_bag_rerecord.md) | 干净 bag 重录（165547 零空窗）+ filter_person_blobs.py 人形块过滤 → 导航图 map_0815_clean |
| [2026-08-15_kiss_drift_170058.md](2026-08-15_kiss_drift_170058.md) | KISS 长录整程漂移留档（旋转+38 空窗→航向漂 163°），失败样本归档 |
| [2026-08-15_nav2_bringup.md](2026-08-15_nav2_bringup.md) | Nav2 首闭环跑通（D4 复用 + 降额实机 + 7 条排障 + 盲区/footprint 修复） |
| [2026-08-15_r2_sensors_extract.md](2026-08-15_r2_sensors_extract.md) | velodyne 运行物抽包 r2_sensors + g354 补 ament marker（launch/urdf 移出 r2_bringup） |
| [2026-08-15_velodyne_perf_tuning.md](2026-08-15_velodyne_perf_tuning.md) | VLP-16 链路性能调优（供电不足根因 + organize_cloud/max_range；points 7.7→9.4Hz） |
| [2026-08-15_vscode_intellisense_include_fix.md](2026-08-15_vscode_intellisense_include_fix.md) | VS Code 1696 修复（Humble include 双嵌套布局） |
| [2026-08-17_nav2_initialpose_inflation_fix.md](2026-08-17_nav2_initialpose_inflation_fix.md) | 初始位姿诊断 + 膨胀 0.55→0.30 过缝修复（08-17 实车，无碰撞）；全速验证暂缓决策；多次设位姿纪律 |
| [2026-08-18_fast_lio2_deploy.md](2026-08-18_fast_lio2_deploy.md) | FAST-LIO2 VM 侧编译部署验证（官方路径修正「编译地狱」结论；CMake/外参/适配全坑） |
| [2026-08-18_fastlio_laser_map_debug.md](2026-08-18_fastlio_laser_map_debug.md) | FAST-LIO /Laser_map 22MB hz 之谜（QoS 大消息手册源头） |
| [2026-08-23_doc_source_traceback.md](2026-08-23_doc_source_traceback.md) | 文档真实性回溯：roadmap 全篇来源规范化（standards §1.11 落地案例 + 可复用清单） |
| [2026-08-24_fastlio2_verification.md](2026-08-24_fastlio2_verification.md) | FAST-LIO2 N97 实车验证原始数据：旋转左 91.9°/右 −89.4°（<2°）+ 平移 169cm 误差 0.51%/0.58% |
| [2026-08-24_n97_fan_control.md](2026-08-24_n97_fan_control.md) | N97 风扇调速（ACPI 死路→IT8613E force_id=0x8622，sysfs pwm2 即刻调速可撤销；不持久化） |
| [2026-09-03_costmap_far_refresh_closed.md](2026-09-03_costmap_far_refresh_closed.md) | costmap 远距离刷新验证闭环（09-03；relog 触发源） |
| [2026-09-03_doc_engineering.md](2026-09-03_doc_engineering.md) | 文档工程整理复盘（规则化见 [doc-engineering.md](../doc-engineering.md)） |
| [2026-09-04_bags_migration.md](2026-09-04_bags_migration.md) | 数据资产目录跨仓迁移复盘（bags 入仓 09-04；规则化见 doc-engineering §八） |
| [2026-09-04_lowobstacle_breakpoint.md](2026-09-04_lowobstacle_breakpoint.md) | 低物盲区断点定位：relog 三层精分析（断点 = velodyne→scan 转换层） |
| [2026-09-04_experience-layer-decision.md](2026-09-04_experience-layer-decision.md) | 经验四层制（事件/draft/规则/索引）定稿 + 抽取盘点方案 A（阶段收尾即盘点，首个 09-10 A1 收口） |
| [2026-09-05_lowobstacle_fixB_vm_acceptance.md](2026-09-05_lowobstacle_fixB_vm_acceptance.md) | 修法 B VM 验收 PASS（bag 抽帧重发法定型 + 方法模板 ①-⑥ + 经验点 E1-E8 层次标注；sim 回放 known trouble） |

## 专题（无日期前缀）

| 文件 | 一句话结论 |
|:---|:---|
| [vlp16_slam_exploration.md](vlp16_slam_exploration.md) | VLP-16 SLAM 方案探索（slam_toolbox / FAST-LIO2 / KISS-ICP 三方案对比与结论） |

---

## 相关

- 状态交接：[07-handover.md](../07-handover.md)（当前进度/遗留）｜待办索引：[pending-tasks.md](../pending-tasks.md)
- 完整文件树：根 [README](../../README.md)
