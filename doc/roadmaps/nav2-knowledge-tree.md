# Nav2 知识树（R2 实战版）

> 围绕 Nav2 全量知识点树状展开，逐层遍历到叶子；参数均来自 R2 实机配置
> （[nav2_params.yaml](../../r2_bringup/config/nav2_params.yaml)、[nav2.launch.py](../../r2_bringup/launch/nav2.launch.py)），
> 实机现象来自 [retrospect/2026-08-15_nav2_bringup.md](../retrospect/2026-08-15_nav2_bringup.md)。
> 阅读顺序：先看 §0 全景树，再按路径深入。

---

## 0. 全景树（总览，后文逐节展开）

```
Nav2 知识树
├── 1. Nav2 定位与架构
├── 2. 生命周期 Lifecycle
├── 3. TF 坐标变换
├── 4. 定位 AMCL
├── 5. 代价地图 Costmap
├── 6. 全局规划器 Planner
├── 7. 局部控制器 Controller
├── 8. 行为树 BT
├── 9. 路径平滑 Smoothing
├── 10. 速度平滑 VelocitySmoother
├── 11. 地图与文件
├── 12. RViz 工具链
├── 13. 接口与客户端
├── 14. 调参与排障方法论
└── 15. 局限与三维扩展
```

---

## 1. Nav2 定位与架构

```
1. Nav2 定位与架构
 ├── 1.1 定义：ROS2 的导航栈（Navigation Stack）
 ├── 1.2 起源：ROS1 Navigation(1) → ROS2 Navigation2
 ├── 1.3 设计哲学：模块化 / 插件化 / 生命周期化
 ├── 1.4 版本：Humble 对应 Nav2 1.1.20（apt: ros-humble-nav2-*）
 └── 1.5 系统组成（R2 实际节点）
```

- **定义**：Nav2 是 ROS2 的"导航操作系统"——一组协同节点，把"机器人位置 + 地图 + 目标点"变成"底盘速度指令"，并负责过程中的避障、恢复、状态管理
- **起源**：ROS1 的 move_base（Navigation1）在 ROS2 上重写，2019 年起逐步演进，Humble 发行版内置 1.1.20
- **设计哲学**：三大支柱
  - 模块化：规划、控制、恢复都是独立节点，可拆可换
  - 插件化：planner/controller/behavior 都走插件机制（`plugin:` 字段），换算法不用改框架
  - 生命周期化：所有节点受 lifecycle 管理（见 §2），启动/停止可控
- **R2 系统组成**（`ros2 launch r2_bringup nav2.launch.py` 拉起的节点）：

| 节点 | 角色 | 一句话职责 |
|:---|:---|:---|
| map_server | 地图供给 | 读 pgm/yaml → 发布 /map |
| amcl | 定位 | 激光+地图匹配 → 发布 map→odom TF、/amcl_pose |
| planner_server | 全局规划 | 地图上算宏观路径 → 发布 /plan |
| controller_server | 局部控制 | 实时避障跟踪路径 → 发布 /cmd_vel |
| smoother_server | 路径平滑 | 全局路径折线 → 平滑曲线 |
| behavior_server | 恢复行为 | 卡住/撞墙时的自救（spin/backup…） |
| bt_navigator | 任务调度 | 行为树：把上面所有节点按流程串起来 |
| velocity_smoother | 速度安全阀 | 限幅 + 加速度平滑 |
| lifecycle_manager ×2 | 管家 | 按依赖顺序 configure/activate 各节点 |

---

## 2. 生命周期 Lifecycle

```
2. 生命周期
 ├── 2.1 状态机：unconfigured → configuring → inactive → activating → active
 ├── 2.2 状态转换语义（configure=读参数准备；activate=开始干活）
 ├── 2.3 lifecycle_manager：自动按序管理一批节点
 ├── 2.4 CLI 查询/操作：ros2 lifecycle get/set
 └── 2.5 R2 实战：MPPI configure 失败 = model_dt 违例（见 §7.5）
```

- 节点启动不是"立刻干活"，而是先进 `unconfigured`；`configure` 时读参数、建内部结构；`activate` 后才开始发布/订阅干活
- 好处：启动顺序可控（比如先让 map_server 就绪再让 amcl 去订阅）、失败可重试
- R2 的 launch 用 `autostart=true`（`nav2.launch.py`），lifecycle_manager 自动完成 configure→activate
- **R2 实战**：MPPI `model_dt: 0.033` 违例 → configure 报错 → bringup 中断、后续节点全不干活；改 0.04 后正常。**启动日志第一屏就能看到谁 configure 失败**

---

## 3. TF 坐标变换

```
3. TF 坐标变换
 ├── 3.1 概念：坐标系树 + 每帧变换（位置/姿态）
 ├── 3.2 R2 TF 树：map → odom → base_link → velodyne
 ├── 3.3 发布者分工
 │    ├── map→odom：AMCL（低频，定位修正）
 │    ├── odom→base_link：EKF（30Hz，传感器推算）
 │    └── base_link→velodyne：robot_state_publisher（urdf 静态）
 ├── 3.4 为什么两段式（odom 段不跳变 / map 段可跳变）
 ├── 3.5 常见错误
 │    ├── "map frame does not exist" → AMCL 未设初始位姿
 │    ├── "Invalid frame ID" / 时间戳问题
 │    └── 双发布者冲突（R2 曾踩：chassis publish_tf 与 EKF 抢发 odom→base_link）
 └── 3.6 工具：ros2 run tf2_tools view_frames、ros2 tf2_echo
```

- **两段式设计的原因**：odom→base_link 由传感器推算，有漂移但**连续平滑**（控制环路依赖它）；map→odom 由定位给出，可以**跳变**（定位修正）。导航用"map→odom + odom→base_link"串联，位置 = 融合结果
- R2 曾踩的坑：chassis 节点（publish_tf=true）与 EKF 同时发 odom→base_link → TF 双发布者冲突 → 必须 `publish_tf:=false` 让 EKF 统一发

---

## 4. 定位 AMCL

```
4. 定位 AMCL（Adaptive Monte Carlo Localization）
 ├── 4.1 粒子滤波原理（五步循环）
 │    ├── ① 撒粒子：N 个猜想的位姿(x,y,θ)
 │    ├── ② 运动更新：粒子按里程计移动 + 噪声
 │    ├── ③ 观测更新：每帧激光与地图匹配打分（打中墙的粒子得分高）
 │    ├── ④ 重采样：按得分复制淘汰（粒子向真实位置聚集 = 收敛）
 │    └── ⑤ KLD 自适应：粒子数随收敛程度动态增减（R2: 500~2000）
 ├── 4.2 运动模型：OmniMotionModel（全向轮，R2）
 │    └── 对比：DifferentialMotionModel（差速）
 ├── 4.3 观测模型：likelihood_field（似然场）
 │    └── 原理：障碍周围预计算距离场，激光命中点与场匹配打分
 ├── 4.4 初始位姿（rviz 2D Pose Estimate 发布 /initialpose）
 │    └── 为什么必须设：全局定位难，先告诉 AMCL"大约在哪"
 ├── 4.5 关键参数（R2 值）
 │    ├── update_min_d 0.25m / update_min_a 0.2rad → 静止不更新（省算力）
 │    ├── max/min_particles 2000/500
 │    ├── alpha1~5 0.2（运动噪声）
 │    ├── z_hit 0.5 / z_rand 0.5 / sigma_hit 0.2（观测模型权重）
 │    ├── laser_min_range -1（用 scan 自带 range_min，R2 为 0.5m 盲区修复后）
 │    └── save_pose_rate 0.5（周期存位姿）
 ├── 4.6 输出
 │    ├── map→odom TF（设位姿后无条件发）
 │    ├── /amcl_pose（运动时发，update 阈值内不发）
 │    └── /particle_cloud（同上）
 └── 4.7 典型现象/问题
      ├── 静止无粒子 → 设计行为（R2 实测确认）
      ├── 走廊退化：沿廊道方向粒子不收敛（对称环境得分相同）
      ├── 绑架问题：被抱走 → 粒子重定位困难（recovery_alpha 恢复）
      └── 定位错误 → 路径偏移/撞障碍 → 重设初始位姿
```

- **AMCL 的"循环"本质**：每收到一帧激光，粒子群整体"猜"一遍位置，收敛到最像真实位置的地方。地图质量直接决定定位质量——**这就是为什么 08-15 要先修好建图（重影/人形块）再用 Nav2**

---

## 5. 代价地图 Costmap

```
5. 代价地图 Costmap（nav2_costmap_2d）
 ├── 5.1 两张地图
 │    ├── global_costmap：map 系，全图范围，全局规划用
 │    └── local_costmap：odom 系，6×6m 滚动窗（R2 08-15 从 3×3 加大），实时避障用
 ├── 5.2 层机制（Layer）：多层叠加 = 最终代价
 │    ├── static_layer：静态地图（墙等固定障碍）
 │    ├── obstacle_layer：实时激光（2D 投影，global 用）
 │    ├── voxel_layer：实时激光（3D 体素投影，local 用）
 │    │    ├── origin_z / z_resolution 0.05 / z_voxels 16 → 16 层×5cm = 80cm 高
 │    │    └── max_obstacle_height 2.0 / marking 阈值
 │    └── inflation_layer：膨胀（障碍周围代价渐变）
 │         ├── inflation_radius 0.55（影响半径）
 │         └── cost_scaling_factor 3.0（衰减速度）
 ├── 5.3 代价值语义（0~254）
 │    ├── 0 自由 / 50~253 膨胀区（越近障碍越高） / 254 致命障碍 / 255 未知
 │    └── R2 rviz 里看到的"圆圈"= 膨胀区渐变（红=高代价）
 ├── 5.4 footprint：车体外轮廓（决定"车多大、能不能过")
 │    └── R2 08-15 修复：0.62×0.62 → 0.84×0.66（urdf 车体 0.8×0.6 + buffer）
 ├── 5.5 传感器源（observation_sources）
 │    ├── scan 话题 /scan
 │    ├── marking=true / clearing=true（标记 + 清除动态障碍）
 │    ├── obstacle_max_range 8.0 / raytrace_max_range 8.0（R2 08-15 从 5 加大）
 │    └── 数据类型 LaserScan
 ├── 5.6 滚动窗口参数：width/height 6、resolution 0.05、update_frequency 5Hz
 ├── 5.7 其他层（未用）：KeepoutLayer（禁区）、ProhibitionLayer（绕行区）等
 └── 5.8 R2 实战：撞障碍根因 = 盲区 0.9m + 窗口 3×3 + footprint 偏小（三叠加）
      └── 有效避障窗口公式：window/2 − 车长半 − 雷达盲区（修复后 2.1m）
```

- **关键直觉**：planner/controller 不看原始激光，只看"叠加好的代价地图"——所以 **costmap 里看不到的东西，导航一定躲不开**（本次撞击的核心教训）
- 代价值 254（致命）对应 footprint 碰撞：**规划器绝不让 footprint 进入 254 格**；膨胀区则"尽量少走，代价越高越绕"

---

## 6. 全局规划器 Planner

```
6. 全局规划器（planner_server）
 ├── 6.1 插件体系：planner_plugins: ["GridBased"]，可挂多个
 ├── 6.2 NavfnPlanner（R2 当前）
 │    ├── 算法：Dijkstra（use_astar: false）/ A*
 │    ├── 输入：global_costmap（含实时障碍叠加）
 │    ├── 输出：/plan（全局路径点序列）
 │    └── 参数：tolerance 0.5（终点附近可接受偏差）、allow_unknown true
 ├── 6.3 SmacPlanner（替代方案）
 │    ├── SmacPlanner2D：2D 栅格（比 Navfn 更优的搜索）
 │    ├── SmacPlannerHybrid：Hybrid-A*（差速/阿克曼运动学可行路径）
 │    └── SmacPlannerLattice：格栅（多运动基元）
 └── 6.4 参数：expected_planner_frequency 20Hz（频率监控，过低告警）
```

- **为什么全局路径要平滑**：Navfn 走 8 邻域格点，路径是折线 → smoother_server（§9）拉直
- 全向轮不限制转向，Navfn 足够；差速/阿克曼车才需要 Hybrid-A*（路径必须运动学可行）

---

## 7. 局部控制器 Controller

```
7. 局部控制器（controller_server）
 ├── 7.1 插件体系：controller_plugins: ["FollowPath"]
 ├── 7.2 MPPI（Model Predictive Path Integral，R2 当前）
 │    ├── 7.2.1 原理：每帧撒 N 条随机轨迹 → 模型仿真 → 代价打分 → 选最优执行一步
 │    │    ├── 采样：batch_size 2000 条（高斯噪声 vx/vy/wz，std 0.2/0.2/0.4）
 │    │    ├── 仿真：time_steps 48 × model_dt 0.04s ≈ 1.9s 未来
 │    │    ├── 打分：critics 加权求和（见下）
 │    │    └── 执行：只走最优轨迹的第一步，下一帧重来（滚动优化）
 │    ├── 7.2.2 critics 代价函数（R2 全部启用）
 │    │    ├── ConstraintCritic：约束违反（w 4.0）
 │    │    ├── GoalCritic：不朝目标点（w 5.0）
 │    │    ├── GoalAngleCritic：到达时角度不对（w 3.0）
 │    │    ├── PreferForwardCritic：奖励前进（w 5.0）
 │    │    ├── CostCritic：轨迹经过高代价区（w 3.81，critical_cost 300 硬限制）
 │    │    ├── PathAlignCritic：轨迹偏离路径方向（w 14.0，最大权重）
 │    │    ├── PathFollowCritic：轨迹偏离路径（w 5.0）
 │    │    ├── PathAngleCritic：朝向与路径夹角（w 2.0）
 │    │    └── TwirlingCritic：原地打转（w 10.0，全向轮专用）
 │    ├── 7.2.3 运动模型：motion_model: "Omni"（全向：vx/vy/wz 独立）
 │    │    └── 对比：Diff（差速）/ Ackermann（阿克曼）
 │    ├── 7.2.4 速度限制：vx_max 0.2 / vy_max 0.15 / wz_max 0.4（降额版）
 │    ├── 7.2.5 其他参数：temperature 0.3（采样温度）、gamma 0.015、prune_distance 1.7、
 │    │    transform_tolerance 0.1、iteration_count 1、visualize false
 │    └── 7.2.6 R2 实测量化：smoothed 峰值精确钳在限幅（0.200/0.150/0.400）
 ├── 7.3 DWB（备选控制器，nav2_dwb_controller）
 │    ├── 原理：动态窗口法——速度空间采样 → 前向仿真 → 打分
 │    └── 与 MPPI 对比：DWB 采样少（快/简单）、MPPI 随机多轨迹（平滑/可调性好）
 ├── 7.4 检查器
 │    ├── progress_checker：10s 内移动 <0.5m 判定卡住 → 触发恢复行为
 │    └── goal_checker：xy 0.25m / yaw 0.25rad 内判到达
 ├── 7.5 常见问题
 │    ├── "Controller period more then model dt"：model_dt < 1/controller_frequency
 │    │    → R2 0.033 违例 configure 失败（修复 0.04）
 │    ├── controller_frequency 30Hz 与 EKF 30Hz 对齐（R2）
 │    └── CPU 压力：batch_size 2000 每帧采样，N97 需关注
 └── 7.6 输出：/cmd_vel（未经 smoother）
```

- **MPPI 的直觉**：不是"想好一条路跟着走"，而是"每一瞬间撒 2000 条可能性、选最划算的"——所以它能自然绕开临时障碍（costmap 一更新，下帧轨迹就绕）
- **critics 权重就是"性格"**：PathAlign 14 最大 → 车"贴路径走"；想更激进避障就把 CostCritic 调大

---

## 8. 行为树 BT

```
8. 行为树（bt_navigator）
 ├── 8.1 概念
 │    ├── 节点类型
 │    │    ├── Control（序列/选择/并行）：组合逻辑
 │    │    ├── Decorator（重试/限时/条件门）：修饰
 │    │    ├── Action：干活（调 planner/controller 服务）
 │    │    └── Condition：检查（到达了吗/位姿收到了吗）
 │    ├── 黑板（Blackboard）：节点间共享数据
 │    └── XML 定义树结构（nav2_bt_navigator 包内）
 ├── 8.2 navigate_to_pose 流程（R2 用，简化）
 │    ├── WaitForInitialPose（等 2D Pose Estimate）
 │    ├── ComputePathToPose（调 planner_server）
 │    │    └── 失败 → Recovery（恢复行为）
 │    ├── FollowPath（调 controller_server）
 │    │    └── 循环：GoalReached? 没到继续；卡住 → Recovery
 │    └── GoalReached → 报告成功
 ├── 8.3 恢复行为（behavior_server 插件）
 │    ├── spin：原地旋转找路（R2 降额 0.4 rad/s）
 │    ├── backup：后退
 │    ├── drive_on_heading：朝前冲一段
 │    ├── wait：等待
 │    └── assisted_teleop：人辅助操控
 ├── 8.4 自定义：改 XML 树可改整个导航行为（绕行规则/任务编排）
 └── 8.5 R2 参数：plugin_lib_names 列出 40+ 可用节点库
```

- **为什么用行为树**：可组合、可视化（Groot 工具）、改流程不动代码——以后 R2 做"多任务编排"（Phase 5）就是在这层加逻辑

---

## 9. 路径平滑 Smoothing

```
9. 路径平滑（smoother_server）
 ├── 9.1 为什么需要：全局路径是折线，直接跟会"拐直角"
 ├── 9.2 SimpleSmoother（R2）：迭代拉直（max_its 1000、do_refinement）
 └── 9.3 其他：CG Smoother（共轭梯度）、ConstrainedSmoother（约束平滑）
```

---

## 10. 速度平滑 VelocitySmoother

```
10. 速度平滑（velocity_smoother）
 ├── 10.1 作用：控制器输出 → 限幅 + 加速度平滑 → 底盘
 ├── 10.2 限幅：max_velocity [0.2,0.15,0.4] / min_velocity [-0.2,-0.15,-0.4]
 │    └── R2 降额核心：任何情况下速度不超限（实测峰值精确=限幅）
 ├── 10.3 加速度：max_accel [1.0,0.5,1.0] / max_decel（防急刹急起）
 ├── 10.4 反馈模式：feedback "OPEN_LOOP"（不反馈实际速度，R2）
 │    └── 对比 CLOSED_LOOP：用 odom 反馈更平滑但依赖 odom 质量
 ├── 10.5 其他：odom_topic /odometry/filtered、deadband 0、velocity_timeout 1s
 └── 10.6 注意：限幅只管速度，不管规划——超限后果由 planner 兜底
```

---

## 11. 地图与文件

```
11. 地图（map_server / 建图链路）
 ├── 11.1 地图文件格式
 │    ├── .pgm：灰度图（像素值 → 占用概率）
 │    └── .yaml：元数据（分辨率/原点/占用阈值/图像路径）
 ├── 11.2 OccupancyGrid：0=自由 100=占用 -1=未知（话题消息）
 │    └── pgm 灰度 → 占用换算：occupancy_threshold 0.65 / free_threshold 0.25
 ├── 11.3 map_server：configure 时加载文件 → active 后发布 /map（transient_local QoS）
 ├── 11.4 R2 建图链路（Phase 2）
 │    ├── VLP-16 点云 → KISS-ICP 里程计 → 累积点云 → PCD
 │    ├── 3D→2D 分层投影（pcd_to_map.py，选层 z_min 滤地面）
 │    └── map_0815_clean（08-15 清洗版：干净 bag + 人形块过滤）
 └── 11.5 地图与定位的关系：地图质量 = 定位质量的上限
```

---

## 12. RViz 工具链

```
12. RViz 工具链
 ├── 12.1 显示项（Navigation2 组）
 │    ├── Map（/map）｜Global/Local Costmap（代价着色）｜Path（/plan）
 │    ├── Amcl Particle Swarm（/particle_cloud 粒子）
 │    ├── RobotModel（urdf）｜TF｜LaserScan（/scan）
 │    └── Trajectories（/trajectories，MPPI 候选轨迹，默认关）
 ├── 12.2 工具
 │    ├── 2D Pose Estimate（P）：设初始位姿 → /initialpose
 │    └── Navigation2 Goal（G）：发目标 → /goal_pose
 └── 12.3 使用要点：话题灰色=无数据（静止无粒子属正常）；组需展开勾选
```

---

## 13. 接口与客户端

```
13. 接口与客户端
 ├── 13.1 动作 Action：NavigateToPose（goal/feedback/result 三段）
 │    └── 适合"长任务"：可反馈进度、可取消
 ├── 13.2 话题
 │    ├── 输入：/goal_pose、/initialpose、/scan、/odometry/filtered、/tf
 │    └── 输出：/cmd_vel、/cmd_vel_smoothed、/plan、/map、/amcl_pose、/particle_cloud
 ├── 13.3 服务：/clear_entire_costmap、/reinitialize_global_localization 等
 └── 13.4 程序化导航：rclpy 客户端发 goal（未来 R2 自主任务用）
     └── 示例：goal 发布 /goal_pose + 监听 /amcl_pose 判到达
```

---

## 14. 调参与排障方法论

```
14. 调参与排障
 ├── 14.1 调参流程（每次只加一个变量）
 │    ├── 定位 → 代价地图 → 规划 → 控制 → 限速，从外到内
 │    ├── 记录改动前后数据（bag + 截图）
 │    └── 实机降额测试（R2 纪律：速度 20%/力矩 30%）
 ├── 14.2 R2 实机踩过的 7 个坑（详见 retrospect 08-15）
 │    ├── 重复启动 → 同名节点冲突 → lifecycle CLI "Node not found"
 │    ├── pkill "ros2 launch" → 孤儿子进程（精确 pkill 节点名）
 │    ├── topic list 残留 = daemon 缓存（--no-daemon）
 │    ├── rviz DISPLAY（SSH 无图形）
 │    ├── map frame 不存在 = AMCL 未设初始位姿（正常噪音）
 │    ├── AMCL 静止不发布粒子/位姿（update_min_d/a 设计行为）
 │    └── MPPI model_dt 违例 configure 失败
 ├── 14.3 撞障碍排查顺序（本次教训）
 │    ├── 雷达裁剪 min_range → costmap 尺寸 → footprint 一致性
 │    ├── costmap 里看不到的障碍，导航必然躲不开
 │    └── 先查感知链路再怀疑规划
 └── 14.4 常用命令
      ├── ros2 lifecycle get /amcl / ros2 topic hz /scan
      ├── ros2 bag record / ros2 topic echo /cmd_vel
      └── rqt_graph / view_frames
```

---

## 15. 局限与三维扩展

```
15. 局限与三维扩展
 ├── 15.1 Nav2 本质是 2D：平面 (x,y) + 偏航 θ，3 自由度
 │    ├── 地图是 2D 栅格（OccupancyGrid）
 │    ├── 路径是 2D 曲线
 │    └── AMCL 是 2D 粒子
 ├── 15.2 三维感知 ≠ 三维导航
 │    ├── R2 的 VLP-16 是 3D 雷达（点云有 z）
 │    └── 但 3D 点云被投影成 2D 用（voxel_layer 高度过滤、建图 3D→2D 分层）
 ├── 15.3 真 3D 导航的领域与方案
 │    ├── 无人机：PX4/ArduPilot + 3D 规划（RRT*/A* 3D）
 │    ├── 机械臂：MoveIt（位形空间规划）
 │    ├── 水下/空间：专用栈
 │    └── 地面车 3D 能力：3D costmap（实验性）、体素建图（OctoMap）
 ├── 15.4 Nav2 内部的"准 3D"组件
 │    ├── voxel_layer：3D 体素栅格（有 z 信息，投影决策）
 │    ├── KISS-ICP/FAST-LIO2：3D 里程计（位姿含 6 自由度）
 │    └── 3D→2D 投影：高度分层选层生成导航层（R2 08-13 已做）
 └── 15.5 R2 的路线
      ├── 短中期：2D Nav2 为主（全向车地面导航 3 自由度够用）
      ├── 升级感知：LIO（FAST-LIO2）替代 KISS-ICP，解决旋转漂移
      └── 长期：若做越障/爬坡/空中，再引入真 3D 规划栈
```

---

## 附：R2 关键文件索引

| 内容 | 位置 |
|:---|:---|
| Nav2 参数（全速/降额） | [nav2_params.yaml](../../r2_bringup/config/nav2_params.yaml)、[nav2_params_low.yaml](../../r2_bringup/config/nav2_params_low.yaml) |
| Nav2 启动文件 | [nav2.launch.py](../../r2_bringup/launch/nav2.launch.py) |
| RViz 配置 | [nav2.rviz](../../r2_bringup/config/nav2.rviz) |
| 首闭环留档 | [retrospect/2026-08-15_nav2_bringup.md](../retrospect/2026-08-15_nav2_bringup.md) |
| 建图链路 | [retrospect/2026-08-13_layer_map_3d2d.md](../retrospect/2026-08-13_layer_map_3d2d.md) |
| 启动手册 | [minimal-loop/w1-operation.md](../minimal-loop/w1-operation.md) |
