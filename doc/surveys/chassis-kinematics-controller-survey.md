# 底盘运动学 × Nav2 控制器选型调研（2026-09-06）

> 核实：2026-09-06 WebSearch（docs.nav2.org 官方 + navigation2 GitHub + 4WS 社区/工业案例）；
> R2 配置事实来自本地 nav2_params_low.yaml。未实测项一律标注。
> 关联：[navigation-behavior-safety-survey.md](navigation-behavior-safety-survey.md)（Q1/Q2/Q5 行为线）、
> [phase0/chassis_definition.md](../phase0/chassis_definition.md)（R2 全向轮运动学唯一权威）、
> [motion-control-roadmap.md §三](../roadmaps/motion-control-roadmap.md)（传感器/底盘线）

---

## 〇、三种底盘的运动学本质（先钉死自由度）

| 底盘 | 瞬时速度空间 | 完整约束 | Nav2 侧模型 | 备注 |
|:--|:--|:--|:--|:--|
| 全向轮（R2，四轮独立驱动+辊子） | **SE(2) 全空间**（vx,vy,wz 任意） | Holonomic | AMCL `OmniMotionModel` + MPPI `motion_model: "Omni"` | R2 已正确配置 |
| 阿克曼（前轮转向） | 非完整：只有 (v, δ, θ) 约束空间；vy≡0、最小转弯半径 | Non-holonomic | MPPI `AckermannMotionModel`（+min_turning_r）；规划需 hybrid 系 planner（Smac Hybrid-A*/lattice） | 无法横移/原地转 |
| 四舵轮 4WIS4WID / swerve（R1 类） | **SE(2) 全空间**（每轮转角+轮速，可任意方向平移/旋转） | Holonomic | 同 Omni 模型 + 底层 IK（body cmd_vel → 轮转角/轮速） | 瞬时运动学与全向轮**等价**；差异在执行器约束（转向速率/同步）与打滑特性 |

> 关键：**全向轮与 4WS/swerve 在规划层的"可行驶空间"完全一致（都是 3DOF holonomic）**——
> 区别只在"怎么把 (vx,vy,wz) 变成轮子动作"（IK）与轮系物理特性（辊子打滑 vs 转向电机响应）。
> 因此 Nav2 对两者的**规划与控制接口相同**（Omni 模型即可），无需专用"舵轮模型"才能导航
> （community 已有大量 4WS+Nav2+Omni 集成，见 §四来源）。

---

## 一、Q3：R2 全向轮"先转身再倒车"的行为病

### 1.1 现象
目标在车体后斜方时，车不是直接平移/斜退到位，而是：先转身 → （倒车/前进）→ 再转身 → 到位后转到目标姿态。

### 1.2 机制（本地配置 + nav2 官方语义）
- R2 配置已正确使用全向模型：AMCL `OmniMotionModel`、MPPI `motion_model: "Omni"`（vx/vy/wz 三维采样，
  [官方模型清单](https://docs.nav2.org/configuration/packages/configuring-mppic.html)）——
  **运动学模型没有选错**。
- 病根在 **critics 的"前进偏好"**：`PreferForwardCritic`（cost_weight 5.0）惩罚 vx<0（倒退），
  + `GoalAngleCritic`/`PathAngleCritic` 要求姿态对准 → 对"目标在后斜方"的 omni 车：
  - 直平移方案（vx<0 或 vy 横移）被 PreferForward 压分
  - "转身 180° → 前进 → 到位再转回"方案得分更高 → S 形低效路径（观感 = 先转身再倒车/绕行）
- 即：**不是控制器选型问题，是"全向车的无姿态依赖移动能力"没有被 critic 表达**——critic 默认按
  类车（diff/ackermann 心理）设计，倒退与横移被当作"应避免"。

### 1.3 约束/修改选项

| 选项 | 做法 | 效果与取舍 |
|:--|:--|:--|
| a. 降/关 PreferForwardCritic | 权重 5.0→0~2 或 `threshold_to_consider` 调大 | 允许倒退/横移直行 → 斜退直接到位；代价 = 偶发"倒着走"观感（对全向轮安全无虞） |
| b. 目标姿态松弛 | GoalAngle `threshold_to_consider` 调大 / 权重降 | 减少"到位后还要转一次"的段 |
| c. 接受 S 形 | 认为是全向车对"倒着走"的心理规避，功能无害 | 零改动，时间略多 |
| d. 全局路径引导 | planner 输出带朝向路径（NavFn 无朝向 → 换 lattice/hybrid planner 或 use_path_orientations） | 让"直退段"预先出现在全局路径里，controller 跟随即可 |

> 推荐：先试 **a+b**（VM 参数 → N97 实测斜退行为对比），这是纯参数、可逆、一变量。

### 1.4 换阿克曼会更好吗？——**不会（对这个需求而言）**
- 阿克曼非完整：不能横移、不能原地转，转弯有最小半径 → 在"斜退/窄地/原地调整"场景**严格更差**；
  R2 全向能力是底盘资产，换阿克曼模型 = 主动放弃自由度。
- 何时该换：若业务/展示要求"类车轨迹"（Robocon 搬运动线、公路叙事）或底盘本身是阿克曼（R3?）。
  换模型代价：MPPI `motion_model: "Ackermann"` + `min_turning_r` + planner 换 hybrid 系 +
  AMCL 换 DiffMotionModel——成套改动。

---

## 二、Q4：舵轮（4WIS/swerve）底盘的底层控制规划

### 2.1 架构结论（先给答案）
1. **规划/控制层：直接用 Omni 模型即可**（MPPI `motion_model: "Omni"` / AMCL Omni），
   与全向轮共用同一套 Nav2 流程——不需要 nav2 官方提供"舵轮模型"（不存在也不需要，见 §〇）。
2. **底层执行：body (vx,vy,wz) → 每轮转向角 δ_i + 轮速 v_i 的逆运动学（IK）**放固件/驱动层
   （R1 四舵轮固件已有该能力与标定，见 STM32 仓 steering-calibration 记忆）或独立 ROS 节点。
3. 舵轮特有的工程点在**执行约束**：转向角速度上限、四轮转向同步/防扫掠（拐向时轮子转角要协调）、
   模式切换（crab 横行 / pivot 原地转 / 普通转向）——这些在 IK/固件层管，不进规划层。

### 2.2 MPPI 对舵轮的支持现状（2026-09-06 核实）
- 官方内置模型只有 3 种：**DiffDrive / Omni（默认，holonomic）/ Ackermann**（[motion_models.xml](https://github.com/ros-navigation/navigation2/blob/main/nav2_mppi_controller/motion_models.xml)）——
  **没有"舵轮/4WS/swerve 专用"模型**（Humble~rolling 均无）。
- 但社区/工业已证明 **Omni 模型 + 4WS = 现成正路**：
  - IEEE 2026 农业 4WS 整车：Hybrid-A* 全局 + MPPI 局部 + Nav2 全套（opposite-phase steering，
    [IEEE 11626756](https://ieeexplore.ieee.org/document/11626756)）
  - Open Robotics discourse：4WIS 独立转向车 + Nav2 + ros2_control，body Twist → IK → 转向角位置控制
    + 轮速速度控制（[discourse 34587](https://discourse.openrobotics.org/t/four-wheel-independent-steering-robot-using-nav2-and-ros2-control/34587)）
- **更精细的进阶存在**（非必需）：MPPI-H（Hybrid Swerve MPPI，IROS 2024，
  [arXiv:2409.08648](https://arxiv.org/abs/2409.08648)，开源 mppi_swerve_drive_ros）——
  采样空间在"body 3D 速度"与"轮对 4D 空间"间切换（论文：MPPI-H 99% 成功率 vs 3D 76%）。

### 2.3 若要自实现舵轮专用 MPPI 模型（真需要时）
nav2 MPPI 的运动模型是 **pluginlib 插件**，自定义 = 四步（官方插件机制，
[motion_models.xml](https://github.com/ros-navigation/navigation2/blob/main/nav2_mppi_controller/motion_models.xml) 注册示例）：

```
① 继承 mppi::MotionModel 基类，实现虚方法:
   initialize() / setConstraints() / predict()（输入控制量→车体速度推进）
   applyConstraints()（对控制序列施加硬约束：如转向角速率/轮速极限）
   isHolonomic() → true（4WS 是 holonomic）
② 在自己的 ROS 包里声明 pluginlib 插件（XML + 类注册宏）
③ 编译安装到 NAV2 PLUGIN 路径，YAML: motion_model: "你的模型名"
④ 需要额外自由度（如直接采样轮对转角）则同时自定义噪声生成/约束critic——复杂度显著上升，
   只在"Omni 层忽略的转向约束导致实机问题"时才值得（先实测 Omni+IK 是否够用）
```

> 务实的路径：**先 Omni 模型 + 底层 IK（R1 已具备），实车验证；只有出现"转向速率约束导致的
> 轨迹不可执行/打滑"实测问题，再考虑 MPPI-H 或自实现模型**。不做前置重造。

### 2.4 R1（四舵轮）接入 Nav2 的前置清单（未来线）
1. 底盘驱动层暴露 ROS 接口：收 `geometry_msgs/Twist`（body vx/vy/wz），固件 IK → 四轮（R1 已有 cmd 层，
   补 vy/wz→斜行/自转模式映射）
2. 里程计：轮速×转角合成 odom（车体系积分，参考 R2 chassis_definition 全向式，换舵轮合成公式）→ /odom + tf
3. 传感器：2D 扫描源（R1 需配雷达/或复用低物线结论）+ AMCL（OmniMotionModel）
4. 参数：直接复用 R2 的 nav2_params_low 全家桶（footprint 换 R1 尺寸、降额起步）
> R1 线排期在秋招后（[motion-control-roadmap.md](../roadmaps/motion-control-roadmap.md)），本文只留接口结论。

---

## 来源（2026-09-06 WebSearch 核实）

- [Nav2 Configuring MPPI（motion_model 三种 + 参数）](https://docs.nav2.org/configuration/packages/configuring-mppic.html)
- [nav2_mppi_controller motion_models.xml（插件注册/基类 mppi::MotionModel）](https://github.com/ros-navigation/navigation2/blob/main/nav2_mppi_controller/motion_models.xml)
- [DiffDriveMotionModel 类参考（predict/applyConstraints/isHolonomic 虚方法）](https://api.nav2.org/nav2-rolling/html/classmppi_1_1DiffDriveMotionModel.html)
- [IEEE 2026：4WS 农业车 opposite-phase + Hybrid-A* + MPPI + Nav2](https://ieeexplore.ieee.org/document/11626756)
- [Open Robotics discourse：4WIS + Nav2 + ros2_control（IK + 转向/轮速分离控制）](https://discourse.openrobotics.org/t/four-wheel-independent-steering-robot-using-nav2-and-ros2-control/34587)
- [MPPI-H（Hybrid Swerve MPPI，IROS 2024，3D/4D 采样切换）](https://arxiv.org/abs/2409.08648)
- [ROS Answers：4WS retrofit 指南（ros2_control 可选/Twist 驱动/odom 反馈）](https://answers.ros.org/question/414246/)

> 未实测标注：1.3 各选项（a/b）效果、MPPI-H 收益、4WS IK 细节均为方案层，待 R2/R1 实车验证。
