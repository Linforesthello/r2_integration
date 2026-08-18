# R2 Nav2 首闭环跑通：D4 地图复用验证 + 降额参数实机验证

> 日期：2026-08-15
> 主题：R2 全向轮底盘 Nav2（AMCL + MPPI）首次实机自主导航闭环——从"键盘遥控"到"点到哪走到哪"。
> 结论：**D4 地图复用验证通过，首个 goal 闭环成功（降额 0.2/0.15/0.4 m/s、rad/s），全程无碰撞。**

## 一、目标与前置决策

- 目标：用 08-15 清洗版地图 `map_0815_clean` 直接接入 Nav2，完成 D4 地图复用验证 + 首个自主导航闭环
- 决策 1：**Nav2 测试期间不跑 KISS-ICP**（AMCL 定位不需要，省 N97 CPU）
- 决策 2：**首次实机降额速度**（安全前置纪律）：限幅降到底盘上限 40~50%（0.5/0.3/0.8 → 0.2/0.15/0.4）

## 二、VM 侧改动（git 提交 097b330 等）

| 改动 | 内容 |
|:---|:---|
| `r2_sensors/launch/velodyne.launch.py` | 恢复 velodyne_laserscan 节点（`/scan`，frame_id 显式 `velodyne`），Nav2 的 AMCL/costmap 均订阅 /scan |
| `r2_bringup/config/nav2_params_low.yaml` | 新建降额参数（复制 nav2_params.yaml，限幅 0.2/0.15/0.4 + spin 降速） |
| `r2_bringup/config/nav2_params.yaml` | **model_dt 0.033 → 0.04**：必须 ≥ 1/controller_frequency(30Hz)，否则 MPPI configure 报错 "Controller period more then model dt" 导致 lifecycle bringup 中断 |

## 三、N97 侧 bringup 排障时间线（每坑一条）

1. **重复启动冲突**：先后多次启动 nav2.launch.py → 5 个 ros2 launch 进程、多个同名节点（amcl×N）→ DDS graph 混乱，lifecycle CLI 报 "Node not found"。清理后重跑
2. **pkill "ros2 launch" 误杀全栈 + 孤儿进程**：该模式只匹配 launch 主进程，子节点（robot_state_publisher、velodyne_*、ekf_node 等，命令行不含 "ros2 launch"）成孤儿继续发布话题。**纪律：杀进程用精确节点名**（pkill -f 节点可执行名）；chassis/imu 可 SIGTERM，其余需 -9
3. **topic list 残留假象**：进程死后 topic list 仍显示话题 = ros2 daemon 缓存。用 `ros2 daemon stop` + `ros2 topic list --no-daemon` 确认真实状态
4. **rviz DISPLAY**：SSH 会话无图形 → N97 桌面终端里跑 Nav2（gdm3 display :1）
5. **地图不显示 / "map frame does not exist"（本会话最大困惑点）**：根因链 = AMCL 未收到初始位姿 → 不发 map→odom TF → map frame 不存在 → planner/costmap 持续报错。**该报错是"等待 2D Pose Estimate"的正常噪音，不是故障**。设位姿后 map frame 立即出现、地图回显、报错停止
6. **AMCL 静止不发布 /amcl_pose 与 /particle_cloud**：Nav2 AMCL 设计行为——`update_min_d: 0.25`/`update_min_a: 0.2` 阈值内不更新粒子滤波（省算力），车动起来才发布（bag 实测运动时有 64 帧 amcl_pose/63 帧粒子）。静止时误以为"AMCL 挂了"，实为正常
7. **particle_cloud 显示**：rviz 配置已含 "Amcl Particle Swarm"（nav2_rviz_plugins/ParticleCloud，/particle_cloud）——未显示主因是第 6 条（静止无数据），车动后出现

## 四、验证结果（bag `nav2_first_loop` 量化，脚本 [analyze_nav2_first_loop.py](../../../bags/analysis/analyze_nav2_first_loop.py)）

| 指标 | 数值 | 结论 |
|:---|:---|:---|
| 速度峰值（/cmd_vel_smoothed） | vx 0.200 / vy 0.150 / wz 0.400 | **精确钳在降额限幅**，velocity_smoother 生效 ✅ |
| 平均速度（非零指令） | ~0.109 / 0.085 / 0.199 | 限幅一半以下，低速安全 ✅ |
| MPPI 原始指令峰值（/cmd_vel） | 0.206 / 0.153 / 0.403 | 略超限幅，被 smoother 钳制 ✅ |
| 运动轨迹 | 累计路程 8.37 m，直线位移 0.48 m | **不到 10 次 goal**：走一段直线 → 转一小圈 → 绕圈返回 → 折线回到原点附近（用户口述） |
| AMCL 定位帧 | 64 帧 / 221s | 运动时持续更新 ✅ |
| 规划 | /plan 70 次 | 多 goal + 局部重规划 |
| 粒子收敛 | 中心随车移动 (0.24,-0.13)→(0.65,0.13)；σy 0.36→0.26 收缩有限 | 走廊环境退化（沿廊道方向模糊，AMCL 已知特性），未影响导航成功 |
| 到达判定 | 车停稳于目标点（用户目检，误差未测量） | 闭环成功 ✅ |
| 碰撞 | **有擦碰（用户报告）** | 根因分析见下节，已修复参数待复测 |

留档资产：bag `~/Lin_workspace/bags/raw/nav2_first_loop/`（32.7 MiB，10 话题）、截图 `bags/rviz_nav2_first_loop.png`/`_2.png`。

## 五、实测发现的问题与修复（08-15 当晚复盘）

### 问题 1：rviz 里粒子/路径看不到

- **粒子**：rviz2 添加话题时 `/particle_cloud` 灰色 = 当时无发布者/无数据。运行时车一动就有数据（bag 录到 63 帧）；静止时 AMCL 不发布（见 §三-6）。**非故障**
- **绿色路径（/plan）**：rviz 配置 "Global Planner 组 → Path" 项已 enabled；用户未展开组或路径线太细未注意；MPPI 轨迹（/trajectories）显示项默认 `Enabled: false`。下次运行时在 rviz 左侧 "Navigation 2" 组逐项勾选确认
- **结论**：显示问题，不影响功能；运行中排查

### 问题 2：近距离障碍扫不到 + 撞击擦碰（根因链实锤）

**根因（三处叠加，均已定位并修复参数）**：

| 根因 | 位置 | 影响 | 修复 |
|:---|:---|:---|:---|
| 雷达裁剪盲区 0.9m | velodyne_transform_node `min_range: 0.9`（出厂默认） | 车头前方 0.4~0.9m 障碍对 /scan **不可见** | launch 覆写 `min_range: 0.5`（VLP-16 规格最小测距） |
| local_costmap 太小 3×3m | nav2_params `local_costmap` | 车前有效避障窗口 = 3/2 − 0.4(车长半) − 0.9(盲区) = **仅 0.2m** | width/height 3 → 6（窗口 1.1 → 2.6m） |
| footprint 与车体不符 | 0.62×0.62 vs urdf 车体 0.8×0.6 | x 向（前后）建模短 0.18m，车头车尾超出模型 | footprint → 0.84×0.66（urdf + 0.02 buffer） |

**关联**：costmap obstacle_max_range/raytrace 5.0 → 8.0（感知范围匹配新 local 尺寸）。
**结论**：非"过度依赖全局地图"——是实时感知盲区 + 局部地图过小 + footprint 错配三叠加；参数已修（git 提交见下），**待下次实机复测**。

### 遗留：到达误差未精确测量（/goal_pose 未入 bag，下次录制加入）

## 六、经验

- **Nav2 启动后先设 2D Pose Estimate 再谈"地图不显示/报错"**——map frame 依赖 AMCL 初始位姿，位姿是第一步不是最后一步
- AMCL 静止不发布位姿/粒子是设计行为，判断 AMCL 是否工作看 lifecycle 状态 + 动起来后的发布
- 杀进程用精确模式，别用宽泛 pkill；topic list 带 daemon 缓存，"查真相"用 --no-daemon
- MPPI `model_dt` 与 `controller_frequency` 存在硬约束（model_dt ≥ 1/freq）
- 全向底盘 + Nav2 参数链路（OmniMotionModel + Omni 运动模型 + velocity_smoother 三处限幅）一次跑通，无方向性返工
- **撞障碍先查三件套：雷达裁剪 min_range、local_costmap 尺寸、footprint 与 urdf 一致**——实时感知盲区往往被全局地图"记忆"掩盖，出事故时先怀疑感知链路再怀疑规划

## 七、后续

- [x] **盲区/footprint 修复复测**（08-17 降额实测顺带覆盖：基本无碰撞；inflation_radius 0.55→0.30 同时修复窄缝过不去，见 [retrospect 08-17](2026-08-17_nav2_initialpose_inflation_fix.md)）
- [ ] Nav2 全速验证：切 `nav2_params.yaml`（0.5/0.3/0.8）复测（⚠️ 08-17 决策暂缓，保持降额现状）
- [ ] 避障实测：costmap 实时刷新已见（人体移动出膨胀圈），静态/动态障碍绕行 + 恢复行为实测
- [ ] 到达误差精确测量（goal 位姿 vs 实际停位，bag 录制加 /goal_pose）
- [ ] rviz 显示项确认：Global Planner→Path、Controller→Trajectories（默认关）、Amcl Particle Swarm 运行中勾选
- [ ] 长时间稳定性 / 走廊定位退化对策（换 FAST-LIO2 或 AMCL 参数调优）
- [ ] MPPI batch_size 2000 视 N97 CPU 实测调优
