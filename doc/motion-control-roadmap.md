# R2 运动控制与具身智能路线（2026-08-23 调研）

> 状态：调研结论初稿（2026-08-23 WebSearch 核实）；与 [planning-control-roadmap.md](planning-control-roadmap.md)（规划控制路线）互为姊妹篇——
> 规划控制偏"感知→规划→执行"体系，本文偏"关节协调/上层电机控制/仿真/具身学习"执行层
> 来源 = 官方仓库/论文页 + WebSearch 社区核实，未实测项标注；按 standards §1.11 每条结论可回查
> 关联：[planning-control-roadmap.md](planning-control-roadmap.md)（规划控制路线，§六 RL 增强方向的本体深化）｜[standards.md](standards.md) §1.11（来源留档规范）

---

## 一、能力现状盘点（已有什么）

| 环节 | 现状 | 深度 |
|:---|:---|:---|
| 真机关节执行 | RS00 双关节（CAN CSP ≤0.1° 实测）+ M8010-6（RS485 4Mbps FOC，3 处修复） | ✅ 实机 |
| RL 训练 | Go2 APPO 512 并行 22.8 万轮（UniLab）、G1 FastSAC 2048 并行 1024 万步（MuJoCo）、ONNX 导出一致性验证 | ✅ 仿真训练 |
| 控制理论 | PID 整定（系统辨识 97.75% 实机）、LQR（MATLAB 仿真）、MPC（了解） | 实机/仿真 |
| 底盘执行 | 四舵轮/全向轮运动学、双 CAN 分布式（F407 主控 + 4×F446）、FreeRTOS | ✅ 实机 |
| 固件层 | MCLM 固件 PID 100Hz、堵转保护、CAN 状态上报 | ✅ 实机 |

**与规划控制的定位差**（用户 2026-08-23 确认）：运控方向**少**的是建图算法/重定位方案/整体体系流程（规划控制 roadmap 已覆盖），**多**的是关节间协调、上层电机控制、MoveIt 类仿真、SO-101 跑 HuggingFace VLA、开源主从机械臂与遥操作——本文按此补齐。

---

## 二、运动控制三大方向总览（方向地图）

运动控制（运控）在行业里大体分**三大方向**，各自解决的问题与代表技术不同，但共享同一执行层底座：

| 方向 | 核心问题 | 代表技术栈 | 开源代表 | 与 R2 的衔接 |
|:---|:---|:---|:---|:---|
| **A. 四足/足式运控** | 机体稳定行走（步态/地形/鲁棒）、全身协调 | 模型基（MPC+WBC）vs 强化学习（RL 端到端）双路线；轮足/腿臂复合演进 | OCS2 / legged_gym / Wheel-Legged-Gym | Go2 APPO、G1 FastSAC 训练链路已通（§三） |
| **B. 机械臂操作** | 单/双臂关节协调、力控柔顺、操作学习（模仿/VLA） | MoveIt2 规划仿真 → 遥操作采集 → 模仿学习/VLA 训练 → 真机执行 | MoveIt2 / SO-101+LeRobot / Open X-Embodiment | RS00/M8010-6 真机执行链路已有（§四） |
| **C. 全车协调（移动操作）** | 移动基座+机械臂的**全身协同**（运动中操作、车臂联动、冗余自由度分配） | 全身运动规划（REMANI-Planner 类）+ 全身控制（WBC/RL 混合） | REMANI-Planner / RAMBO / HOVER | R2 底盘+机械臂 = 移动操作平台雏形（§五） |

**通用链路（三方向共享）**：

```
仿真建模(URDF/MoveIt2) → 策略训练(RL/模仿学习/VLA) → 策略部署(ONNX/低层插补)
        ↓                                        ↓
遥操作数据采集(主从) ← 真机执行(CSP/阻抗/协调) ← Sim-to-Real 迁移
```

与规划控制 roadmap §5.1 对应的环节定位：遥操作采集 = 数据入口（类比建图采集），策略训练 = 核心（类比 SLAM/规划），真机执行 = 落点（类比底盘执行），仿真 = 验证手段。

**2025~2026 行业趋势（WebSearch 综述核实，未实测）**：模型基 MPC+WBC、Isaac Lab GPU 级 RL、VLA 基础模型三路正在融合为混合架构（RAMBO、ASAP、UMI-on-Legs 等）——纯模型基或纯 RL 都不是终局，**混合是主流方向**（来源见 §八）。

---

## 三、方向 A：四足机器人运动控制

### 3A.1 范式演进（2015→2025，综述核实）

| 阶段 | 特点 |
|:---|:---|
| 2015-2017 启蒙期 | 液压驱动为主，经典 ZMP/PID 控制，波士顿动力一家独大 |
| 2018-2020 工程突破期 | 电动化替代液压，**MPC+WBC 成为行业主流**，四足商用化落地（宇树从 0 到 1），RL 开始进入 |
| 2021-2023 范式重构期 | 端到端 RL 控制全面爆发，大模型与运控融合，国产厂商进入第一梯队 |
| 2024-2025 普惠成熟期 | 具身智能原生运控体系成熟，**轮腿复合、多模态融合成为标配** |

### 3A.2 模型基路线（MPC + WBC）

- **MPC**（模型预测控制）：在线滚动优化，预测+反馈修正，处理干扰与动态变化；**WBC**（全身控制）：生成全身关节轨迹跟踪规划结果——2018 起行业主流组合
- 开源：ETH RSL 的 [ocs2](https://github.com/leggedrobotics/ocs2)（BSD-3）发布 ANYmal-on-wheels 与 Swiss-Mile 管道；同谱系还有 Crocoddyl / TSID
- 前沿（综述）：载荷感知轨迹优化框架（机器人+负载动力学联合建模，携带 >机体质量 15% 重物越非平坦地形）；全身 MPC（37 主动关节双臂四足，无需 WBC 直接对接关节阻抗，完成拾取重物/避碰/小跑/爬行）

### 3A.3 强化学习路线（R2 已有基础）

- 主流：legged_gym 系（Raibert 初始化、奖励工程、Sim-to-Real 域随机化），训练平台 UniLab / Isaac Lab / MuJoCo；算法 PPO/SAC 系（APPO/FastSAC）
- 2025 前沿（综述）：大规模模仿学习（观察人类运动员视频提取运动逻辑）、端到端（视觉直接映射力矩）、具身大模型（语义指令如"轻声走过去"自动调步态参数）
- 腿臂操作场景：约束 RL 策略仿真训练直接迁移实物（无需微调），成功率 ≥80%，对负载质量/尺寸/材质鲁棒（博士论文页，未实测）

### 3A.4 形态演进总览：点足 → 轮足 → 腿臂复合

| 形态 | 一句话 | 代表 |
|:---|:---|:---|
| 点足（point-foot） | 传统四足，越障强、高速弱 | 宇树 Go1/Go2、A1 |
| 轮足（wheel-legged） | 轮子贴地高速移动 + 腿越障，**"成熟 MPC 谱系与跑酷 RL 的结合"** | Unitree B2-W / Go2-W、ANYmal-wheels、Swiss-Mile（详 3A.5） |
| 腿臂复合（loco-manipulation） | 腿足本体的移动操作，最难任务组合（详 3A.6） | Go2+Z1、Spot+臂、四足+机械臂研究平台 |

### 3A.5 轮足（wheel-legged）详解

**定位**：轮足机器人（wheeled-bipedal / wheel-legged）结合腿的地形适应性与轮的运动效率——2024~2025 行业"普惠成熟期"的标配形态（§3A.1）。

**控制架构（2025 现状，层级化为主流）**：

| 层 | 方法 | 细节（综述核实，未实测） |
|:---|:---|:---|
| 高层规划/力优化 | MPC / NMPC | NMPC 200Hz 平衡+轨迹跟踪（CoM 逆运动学映射关节，轮腿混合步态 5Hz 直接配置在线生成）；DRMPC 用动力学模型（非纯运动学）做跟踪控制，计入力反馈与不可预测交互；StaRide 框架 NMPC 轨迹优化 + LQR 主动悬挂 + 自适应阻抗（乘驾舒适性方向） |
| 低层全身/平衡 | WBC / VMC / LQR | MPC+加权多任务 WBC（WM-WBC，RA-L 2025）层次化优化 + **在线轮位规划**处理非最小相位行为，抗扰强；VMC（虚拟模型控制）在嵌入式平台加速计算（FSDM 全状态动力学模型 + 可微正运动学）；摩擦前馈 LQR 平衡（Stribeck 摩擦模型 PSO 辨识，减振荡） |
| 模态切换 | 点足↔轮足过渡 | 2025 IEEE 综述：**单点切换**（响应快、复杂环境不稳）vs **过渡区间平滑切换**（稳、依赖预定时序与地形耦合）；未来方向 = RL/模仿学习自主学习切换 |
| 学习路线 | RL + sim-to-real | Isaac Gym PPO + HIM 编码器状态表征（策略输出轮速+关节位置，MuJoCo 微调后部署，arXiv 2507.22345）；DTC（Deep Tracking Control）：在线 MPC + 离线学习混合，抗滑/软地面——**与四足 §3A.3 的 RL 资产同源** |

**开源生态**：

| 项目 | 定位 |
|:---|:---|
| [Wheel-Legged-Gym](https://github.com/clearlab-sustech/Wheel-Legged-Gym)（南科大 Clear Lab） | legged_gym 基础上加 VMC、崎岖地形、双足轮腿配置——**足式 RL 研究的事实基地** |
| [awesome-wheeled-legged](https://github.com/XinLang2019/awesome-wheeled-legged) | ~20 个轮足代码仓库整合清单 |
| [upkie](https://github.com/tasts-robots/upkie) | 开源 DIY 平衡轮腿（Python/C++ 双栈，MPC/LQR 基线）——低成本入门首选 |
| Unitree [B2W_example](https://github.com/unitreerobotics/unitree_sdk2_b2w) | Go2-W / B2-W 低级驱动示例 |

**代表硬件与指标**：ANYmal-wheels（4 轮 + 12 腿 DoF，~50kg，轮式最高 ~6m/s）；Swiss-Mile（最高 ~22km/h）；Unitree B2-W；云深处山猫 M20、普渡 D5。轮足切换方案参考指标：最高 5m/s、越障 25cm 台阶、30° 斜坡、**能耗 -25%**。

**工程难点（综述）**：非最小相位行为（轮位需在线规划补偿）、RL 训练耗时 + sim-to-real 迁移未闭合、动态地形与传感器标定。

**与 R2 衔接**：**Go2-W = 宇树官方 Go2 轮足版**（有 B2W_example 驱动示例）——现有 Go2 训练资产可直接平移；训练栈与 UniLab/legged_gym 同源，是"四足进阶"性价比最高的下一步。

### 3A.6 腿臂复合（loco-manipulation）

- IEEE Access 2026 综述提出**"建模-任务-控制"三元组**，给出模型基 WBC / 全身 MPC / RL-IL 的选型决策矩阵（何时用哪种方法）
- **最难任务组合一致指向：接触丰富末端交互 + 非平坦/不确定落脚点 + 感知延迟遮挡**
- 代表工作：全身 MPC（37 主动关节双臂四足，无 WBC 直接对接关节阻抗，拾取/避碰/小跑/爬行）；约束 RL 直接迁移实物（成功率 ≥80%，§3A.3）；RAMBO 的足式形态（§5.3）
- 学术地位：当前足式最活跃方向之一，宇树 G1/H1 已成默认实验平台

### 3A.7 R2 衔接（资产复用）

现有 Go2（UniLab APPO 512 并行）/ G1（MuJoCo FastSAC 2048 并行）训练链路正是方向 A 的落点；进阶路线：行走稳定（已有）→ **轮足切换（Go2-W + Wheel-Legged-Gym，与现有训练栈同源）** → 腿臂复合（§五 全车协调的足式形态）。G1/H1 已是学术界全身学习默认平台，与 §五 的 WBC 方向直接衔接。

---

## 四、方向 B：机械臂与操作

### 4.1 运动规划与仿真（MoveIt2）

| 维度 | 方案 | 状态 |
|:---|:---|:---|
| 框架 | [MoveIt2](https://moveit.ai/)（ROS2 事实标准，Humble 官方支持 2022-06 发布） | ✅ 原生 |
| 规划器 | OMPL（RRTConnect/PRMstar/AITstar 等采样系）/ STOMP / CHOMP / Pilz（PTP/LIN/CIRC 工业模式） | ✅ 内置 |
| IK | KDL（默认）/ TRAC-IK / Pick-IK / BioIK | ✅ 内置 |
| 轨迹优化 | TOTG（默认时间参数化）/ Ruckig（非零初末态抖动平滑） | ✅ |
| 实时伺服 | [moveit_servo](https://github.com/moveit/moveit2)（100Hz 笛卡尔速度控制，奇异规避阈值 17/30） | ✅ |
| 仿真栈 | URDF/Xacro + [ros2_control](https://github.com/ros-controls/ros2_control)（controller_manager：joint_state_broadcaster / forward_position_controller / JointGroupEffortController）+ Gazebo + RViz2 MotionPlanning 插件 | ✅ |
| Python 接口 | MoveGroupInterface（rclpy）/ [pymoveit2](https://github.com/AndrejOrsula/pymoveit2) | ✅ |

> 已知坑（社区实测）：关节越界 → joint_limits.yaml 限位留 5° 余量；MoveIt 规划失败查 SRDF 自碰撞矩阵；Gazebo 机械臂不动查 use_sim_time/控制器加载；笛卡尔路径 computeCartesianPath 返回值 <0.9 = 限位或碰撞。
> SO-100 机械臂已有 [MoveIt2 集成](https://index.ros.org/r/so_arm_100/)（URDF + Gazebo + MoveIt2），可作为 R2 机械臂移植参照。

**R2 落点**：RS00/M8010-6 建 URDF（关节限位/惯性已实测）→ MoveIt2 规划 + RViz2 仿真（真机联调前置）；moveit_servo 与现有 CSP/缓变闭环对接（规划输出 → 现有位置闭环执行）。

### 4.2 遥操作与开源主从机械臂（数据入口）

| 方案 | 硬件 | 成本 | 特点 |
|:---|:---|:---|:---|
| [SO-ARM100 / SO-101](https://github.com/TheRobotStudio/SO-ARM100)（TheRobotStudio + HuggingFace 合作设计） | 6 DOF，STS3215 舵机 ×12（leader+follower 同构），3D 打印 | 双臂套装 ~$232（单臂 ~$123） | **与 LeRobot 深度绑定**；SO-101 改进接线与电机减速比；v0.5.0 统一单臂/双臂支持 |
| [ALOHA / ALOHA-2](https://scite.ai/reports/aloha-2-an-enhanced-low-cost-D1k24zVd)（斯坦福） | ViperX 从臂 ×2 + WidowX 主臂 ×2 + 4 相机，总价 <$2 万 | 高性能 | **关节空间一一映射**（无 IK/无奇异/低延迟，主臂自重滤手抖）；配套 ACT 模仿学习：10 分钟演示数据 → 6 任务 80~90% 成功率 |
| [dora-lerobot](https://github.com/dora-rs/dora-lerobot) | 软件管线（dora 实时遥操作，无摄像头可跑） | — | 数据流编排 |
| slobot（[Genesis 仿真 + SO-ARM100](https://github.com/alexis779/slobot)） | 仿真侧 | — | sim-to-real / real-to-sim 双向 |
| [OpenArm](https://xingyun3d.csdn.net/69f46ef554b52172bc7124f6.html)（Enactic 团队，2026） | 开源 7 DOF 仿人机械臂（双臂系统 $6500） | 中 | 完整硬件设计文件 + ROS2 集成 + Isaac Lab 仿真环境，接触丰富环境设计 |

**主从映射方式取舍**：关节空间一一映射（ALOHA 路线：无 IK、免奇异、延迟低）vs 任务空间 IK 映射（需 IK 求解、有奇异风险）——低成本方案主流走关节空间。

**遥操作采集方式全景（综述，未实测）**：主从（ALOHA/GELLO）、手持式（UMI）、VR/AR（Apple Vision Pro + 逆运动学映射）、动捕全身映射、键盘/3D 鼠标、人机协同（HITL RL）。

**R2 落点**：SO-101 双臂（或 R2 机械臂本体作 follower）→ 主从遥操作 → 录数据 → 训练。ALOHA 硬件成本高，先不上。

### 4.3 VLA / 模仿学习策略（核心训练层）

**框架**：[LeRobot](https://huggingface.co/docs/lerobot/index)（HuggingFace，Apache 2.0，PyTorch 原生）：LeRobotDataset 标准格式（视频+动作/状态，Parquet，HF Hub 流式）+ 策略动物园（ACT / Diffusion Policy / TDMPC2 → Pi0 / SmolVLA 等 VLA）。v0.5.0 新增 Pi0-FAST、Real-Time Chunking（RTC）、PEFT/LoRA 微调。

**VLA 模型对比（2026 现状，WebSearch 核实）**：

| 模型 | 参数 | 动作表示 | 推理 | 显存 | 开源 | 特点 |
|:---|:---|:---|:---|:---|:---|:---|
| [OpenVLA](https://www.roboticscenter.ai/research/vla-models-comparison-2025)（Stanford/Berkeley） | 7B | 离散 action token（RT-2 路线） | 5~6Hz（A100） | ~16GB（INT4 ~4GB） | 完全开源 | 通用基线；离散化有量化误差；双臂不稳 |
| [Pi0](https://www.roboticscenter.ai/research/vla-models-comparison-2025)（Physical Intelligence） | ~3B | **流匹配（flow matching）** | 10~25Hz（最高 50Hz） | ~8GB | 权重部分开放，管线专有 | 跨任务泛化开源最强；OOD 适应性最佳；微调走 pi.ai 商业 |
| [RDT-1B](https://guyuehome.com/wap/detail?id=2051193990079868929)（清华） | 1B | 扩散 Transformer + action chunk | 扩散多步采样慢 | 较高 | 开源 | **双臂原生**设计（46 数据集 >100 万轨迹预训练）；小样本（1~5 演示） |
| [SmolVLA](https://www.roboticscenter.ai/tools/vla-models-comparison)（HuggingFace 2025） | 450M~2B | 流式动作专家 | 20~30Hz（RTX 3090） | 2~6GB | 完全开源 | **消费级 GPU 即可**（Jetson Orin NX 可跑）；LeRobot 一等公民；单任务微调后距 OpenVLA 差 5~10% |

### 4.4 开源数据生态（新增，方向 B 的"弹药库"）

**Open X-Embodiment（OXE，Google DeepMind 主导）**：全球最大开源机器人数据集——100 万+真实轨迹、22 种机器人本体、527 种技能，34 家机构 60 个数据集统一为 RLDS 格式。核心意义：**证明跨本体训练存在正迁移**（RT-X 策略在混合数据上训练优于单本体数据，具身"scaling law"初步验证）；RT-1-X 比专用模型成功率 +50%，RT-2-X 达 RT-2 的 3 倍。Apache 2.0 / CC-BY 双许可。

**数据三级生态（综述）**：

| 层级 | 代表 | 规模 | 格式 |
|:---|:---|:---|:---|
| L1 大规模聚合 | Open X-Embodiment | 100 万+轨迹 / 22 本体 / 527 技能 | RLDS (TFRecord) |
| L2 专项高质量 | LeRobot / DROID | 7.6 万轨迹（DROID：350 小时、564 场景、86 任务） | Parquet+MP4 |
| L3 任务定制 | 自采 | 50~500 条演示/任务 | 各异 |

**LeRobot 2026 工程现状**：数据集格式 Parquet + MP4/AV1 压缩视频（存储降 5~10 倍、加载显著加速），已成为 PyTorch 生态事实标准；内置 SO-100/SO-101、ALOHA 风格硬件支持，低成本"采集→训练→部署"闭环。与 ROS2 互补：LeRobot 管"大脑"（策略/数据集/训练），ROS2 管中间件。

**动作表征共识（社区，未实测）**：参考系以增量/相对位姿为主流；控制空间以笛卡尔（末端 6DoF+夹爪）为主流；动作粒度采用分块 Chunking（16~64 帧）；输出以扩散/流匹配生成为主——Chunking+扩散是主流组合（扩散天然建模多模态分布，避免回归均值"动作平均化"）。

**实践坑（社区，未实测）**：① 预训练子数据集与部署相机配置（分辨率/视角）需尽量匹配；② OXE 中 Fractal 数据占体积主导，需子数据集间平衡采样（否则 60%+ 批次来自单一数据）；③ ~30% OXE episode 语言标注缺失/通用，需过滤或用 LLM 重标注；④ **动作空间归一化是最大工程坑**（各子数据集动作空间不一致，自训练自定义架构需预留 1~2 周）。

**其他开源组件**：openpi（Physical Intelligence 开放基础模型）、NVIDIA GR00T-Dreams / Cosmos（合成轨迹数据，真实+合成"数据飞轮"）。

### 4.5 部署要点（社区共识，未实测）

- **分层架构**：大 VLA 输出低频动作/短轨迹 → 低层控制器插补（与 R2 现有 CSP/缓变闭环天然匹配）
- **data schema 对齐**：相机视角/图像尺寸/语言标注/动作维度/控制频率归一化，不匹配需 action adapter
- 动作表示决定部署：离散 token（OpenVLA）需后处理 + 低层安全过滤；流匹配（Pi0/SmolVLA）连续平滑；扩散（RDT）多峰但慢
- 真机基准（ALOHA Mobile 四任务）：π0 OOD 适应最强、ACT 分布内最稳；低成本硬件上策略性能强依赖任务

**R2 落点**：SmolVLA 起步（消费级 GPU / 可跑 Jetson，与现有计算资源匹配），数据走 LeRobot 标准格式；Pi0 作性能上限参考（vendor lock-in 风险标注）。

---

## 五、方向 C：全车协调（移动操作 mobile manipulation）

> 用户 2026-08-23 点名方向："近年浙大那篇车+机械臂协同动作+规划"——已核实为 FAST Lab（高飞团队）参与的 REMANI-Planner 与 PTDM 两条工作，详见 5.2。

### 5.1 问题定义

移动基座（车）+ 机械臂 = **冗余自由度全身系统**：臂装在移动基座上，规划/控制必须在**一个全身坐标系**里同时处理基座运动与臂运动（车臂同步 vs 停稳操作、运动中末端精度、基座振动耦合、全身碰撞）。核心难点：高维状态空间（基座 3DoF + 臂 6~7DoF）实时求解。

### 5.2 全身运动规划（浙大/STAR 系代表）

| 工作 | 出处 | 核心 | 代码 |
|:---|:---|:---|:---|
| [REMANI-Planner](https://github.com/Robotics-STAR-Lab/REMANI-Planner)（Real-time Whole-body Motion Planning for Mobile MANIpulators） | **ICRA 2024**（STAR Group 南科大 + HITSZ MAS Lab + **ZJU FAST Lab 高飞团队**合作） | 环境自适应搜索 + 时空轨迹优化：按环境复杂度自适应调整搜索维度，全身安全/敏捷/动力学可行性联合优化；MINCO 轨迹表示（借 AutoTrans 框架）；7m×5m 实景房间（桌/架/障碍）实时生成全身轨迹；**C++/GPLv3/ROS Noetic**，UR5 示例可改配置适配自研机器人 | ✅ 开源（[项目页](https://robotics-star.com/REMANI-Planner/)） |
| [PTDM](https://ar5iv.labs.arxiv.org/html/2604.04166)（Primitive-based Truncated Diffusion，高飞团队） | arXiv 2604.04166（2026-04） | 差分驱动移动机械臂轨迹生成：KSE 模块（可微正运动学把边界状态映射为 3D 关键点序列，跨注意力与环境点云融合）→ 离线 K-means 聚类轨迹基元库 → 在线按场景先选基元、扩散去噪从基元偏置分布起步（非纯高斯），DDIM 仅 **2 步采样** → 多项式轨迹优化后处理；**轨迹生成提速约 6 倍**、成功率提升、缓解 mode collapse | ✅ 开源（[nmoma](https://github.com/nmoma/nmoma)）；**局限：仅静态仿真环境，未实机部署** |

### 5.3 全身控制（WBC / RL 混合框架）

| 工作 | 出处 | 核心 | 与 R2 关系 |
|:---|:---|:---|:---|
| [RAMBO](https://arxiv.org/abs/2504.06662)（RL-Augmented Model-Based Whole-Body Control） | RA-L 2025 | **RL+模型基 WBC 混合**：模型基模块解 QP 优化末端接触力（前馈力矩），RL 策略提供反馈修正（补偿建模误差与扰动）——兼具模型基的力矩级精度与 RL 的鲁棒性；**宇树 Go2 实测**：推购物车、端盘子、抱软物体，四足+双足步行模式 | 与用户 Go2 资产直接相关 |
| [HOVER](https://arxiv.org/abs/2410.21229)（Versatile Neural Whole-Body Controller） | NVIDIA R²D² 计划 | 类人 19-DOF **统一神经控制器**：AMASS 人类运动数据训练 oracle 模仿器 → 多模式策略蒸馏成"通才策略"；15+ 控制模式（根速度/关节角/末端跟踪，行走→双臂操作无缝切换） | 类人方向，作为统一全身控制范式参考 |

### 5.4 趋势与难点（综述核实）

- **三路融合**：模型基 MPC+WBC（OCS2/Crocoddyl/TSID）＋ Isaac Lab GPU 级 RL ＋ VLA 基础模型（π0.5/GR00T N1.5/Helix 02）→ 融合为 RAMBO、ASAP、UMI-on-Legs 等混合架构
- **最难任务组合**（IEEE Access 2026 综述一致结论）：接触丰富末端交互 + 非平坦/不确定落脚点 + 感知延迟遮挡
- 腿足强耦合（loco-manipulation）是当前学术界最活跃方向之一，宇树 G1/H1 已成默认实验平台

### 5.5 R2 衔接（分阶段落地）

R2 = 四全向轮底盘 + RS00/M8010-6 机械臂，**正是移动操作平台的物理雏形**：

1. **阶段一（停稳操作）**：底盘停稳 → MoveIt2 规划臂动作 → 执行（现有链路即可，先跑通"车+臂"联合演示）
2. **阶段二（移动中协调）**：底盘慢速移动中臂保持末端姿态（全身协调初阶）；参考 REMANI-Planner 思路做全身轨迹规划（需为 RS00 建全身 URDF + 碰撞体）
3. **阶段三（柔顺/力控）**：阻抗/导纳控制 + 力传感器，接触式任务

> 注意：REMANI-Planner 为 ROS1 Noetic + UR5 示例，迁移到 R2（Humble + 自研臂）是研究级工作量，秋招前按"方向认知 + 论文复现"深度写，不写成果。

---

## 六、跨方向公共设施

### 6.1 多关节协调与上层电机控制

| 方向 | 内容 | R2 基础 |
|:---|:---|:---|
| 阻抗/导纳控制 | 力控机械臂（JointGroupEffortController + 力传感器），柔顺操作 | RS00 运控/CSP 双模式可扩展 |
| 关节协调 | 多电机协同轨迹（同步/插补），现有双关节 + 底盘 4 电机的分布式 CAN 架构可延伸 | 双 CAN 分布式 + 50ms 状态上报 ✅ |
| 双臂/多臂协调 | RDT 双臂原生 / ALOHA 双臂任务（穿扎带 91%、取叉 82%） | SO-101 双臂路线（§4.2） |
| 全身控制（WBC） | 足式 RL 的全身协调（与 Go2/G1 训练衔接）；移动操作全身协调（§五） | UniLab/MuJoCo 训练链路 ✅ |
| 固件层 | PID 100Hz / 堵转保护 / 饱和检测（已有）；上层只需下指令 | MCLM 固件 ✅ |

**R2 落点**：现有固件层不动，上层补"协调层"——MoveIt2 规划输出 → 多关节同步指令 → 现有执行闭环；力控/阻抗作为进阶方向（秋招后）。

### 6.2 Sim-to-Real 与仿真平台

| 平台 | 特点 | R2 现状 |
|:---|:---|:---|
| [Isaac Lab/Gym](https://github.com/isaac-sim/IsaacLab)（NVIDIA） | GPU 并行，RGB-D/LiDAR/IMU 原生传感器，多模态观测（见规划控制 roadmap §6.5） | 规划中（F14/F15/F16） |
| MuJoCo | 现有 G1 训练平台，物理精度好 | ✅ 已用 |
| UniLab | 现有 Go2 训练平台（APPO） | ✅ 已用 |
| [Genesis](https://github.com/Genesis-Embodied-AI/Genesis) | 通用仿真引擎，SO-ARM100 已有集成（slobot） | 探索中 |
| Gazebo + ros2_control | MoveIt2 标准仿真栈（§4.1） | 规划中 |

**R2 落点**：策略训练主平台维持 MuJoCo/UniLab/Isaac Lab（与规划控制 §六共用）；Genesis 作为 SO-101 双臂仿真候选（成本低、集成现成）。

---

## 七、R2 落点与优先级（秋招 2026-09-10 视角）

| 环节 | 现状 | 候选池 | 推荐 | 优先级 |
|:---|:---|:---|:---|:---|
| 机械臂仿真 | 无 | MoveIt2 / 自研 | **MoveIt2**（标准栈 + SO-100 移植参照） | 秋招后 |
| 遥操作数据 | 无 | SO-101 双臂 / ALOHA / 现臂改造 | SO-101（~$232，LeRobot 原生） | 秋招后 |
| 策略层 | RL 训练（足式） | ACT / Diffusion Policy / SmolVLA / Pi0 / RDT | **SmolVLA 起步**（消费级 GPU 可跑） | 秋招后 |
| 关节协调 | 双关节 + 底盘 | 同步插补 / 阻抗 / WBC | 先同步轨迹，后力控 | 秋招后 |
| 仿真平台 | MuJoCo/UniLab | +Isaac Lab / Genesis | Isaac Lab（与规划控制共用） | 探索中 |
| 全车协调 | 车+臂物理雏形 | 停稳操作 → REMANI 类全身规划 → RAMBO 类全身控制 | 阶段一停稳操作演示（现有链路） | 秋招后（阶段二/三研究级） |
| 四足进阶 | Go2/G1 行走训练 | 复杂地形 / 轮足（Wheel-Legged-Gym）/ 腿臂 | 维持 RL 主攻，轮足/腿臂按方向认知写 | 探索中 |

**一句话**：运动控制主线 = **三大方向地图（四足 RL 主攻 / 机械臂 SO-101+LeRobot 数据闭环 / 全车协调 R2 车+臂平台叙事）** + **MoveIt2 仿真前置** + **现有真机执行链路作低层**（规划输出 → CSP/缓变闭环）；力控/全身协调为进阶方向，秋招前全部按"探索中"写，不写成果。

---

## 八、来源（2026-08-23 WebSearch 核实）

**机械臂/策略/仿真（沿用首版）**：
- [SO-ARM100 仓库（TheRobotStudio）](https://github.com/TheRobotStudio/SO-ARM100)｜[LeRobot 官方文档](https://huggingface.co/docs/lerobot/index)｜[LeRobot v0.5.0 发布说明](https://huggingface.co/blog/lerobot-release-v050)（SO-100/SO-101 统一支持、Pi0-FAST、RTC、LoRA）
- [MoveIt2 Humble 官方发布（2022-06）](https://moveit.ai/moveit/ros/humble/2022/06/02/MoveIt-Humble-Release.html)｜[ros2_control 官方仓库](https://github.com/ros-controls/ros2_control)｜[pymoveit2](https://github.com/AndrejOrsula/pymoveit2)
- [SO-100 + MoveIt2 集成（ROS Index）](https://index.ros.org/r/so_arm_100/)
- [ALOHA 2 论文页（低成本双臂遥操作）](https://scite.ai/reports/aloha-2-an-enhanced-low-cost-D1k24zVd)｜[ALOHA 与替代方案总览](https://www.roboticscenter.ai/learn/aloha-robot)
- [VLA 模型对比（SVRC，RT-2/OpenVLA/Pi0/SmolVLA/RoboFlamingo）](https://www.roboticscenter.ai/research/vla-models-comparison-2025)｜[VLA 模型对比 2026（Octo/OpenVLA/Pi0/GR00T/SmolVLA/OpenPI）](https://www.roboticscenter.ai/tools/vla-models-comparison)
- [经典 VLA 模型与动作生成范式（古月居）](https://guyuehome.com/wap/detail?id=2051193990079868929)（含 RDT-1B 双臂设计）
- [dora-lerobot（实时遥操作数据流）](https://github.com/dora-rs/dora-lerobot)｜[slobot（Genesis 仿真 + SO-ARM100）](https://github.com/alexis779/slobot)
- [IsaacLab 官方仓库](https://github.com/isaac-sim/IsaacLab)｜[Genesis 官方仓库](https://github.com/Genesis-Embodied-AI/Genesis)

**开源数据生态（新增）**：
- [Open X-Embodiment 详解（SVRC）](https://my.roboticscenter.ai/blog/open-x-embodiment)｜[OXE 百科条目](https://baike.baidu.com/item/Open%20X-Embodiment/67871162)｜[OXE 统一格式与 RT-X 模型（GitCode）](https://blog.gitcode.com/b72ba013e32fd89e740939103838008f.html)
- [LeRobot 生态综述（Hivebook）](https://hivebook.wiki/wiki/lerobot-hugging-face-s-robotics-ml-library)
- [具身智能"大脑与小脑"：整体架构与小脑运控（CSDN，含 OpenArm/Manipulation 知识体系）](https://xingyun3d.csdn.net/69f46ef554b52172bc7124f6.html)
- [Common Robot Data Infrastructure（香川友志，合成数据趋势）](https://note.com/kagawatomo/n/n4c558a5f5488?hl=en)

**四足方向（新增）**：
- [四足机器人核心研究成果及未来趋势（金刚石机器人）](http://www.jsgszn.com/news/281.html)｜[四足进阶：从稳定行走到自主 Agent](http://jsgszn.com/news/350.html)
- [轮足机器人调研（DMBot）](https://robotics-tutorial.dmbot.cn/05_%E8%BF%90%E5%8A%A8%E6%8E%A7%E5%88%B6/30_%E5%A4%8D%E5%90%88/%E8%B0%83%E7%A0%94/Survey_D1_%E8%BD%AE%E8%B6%B3%E6%9C%BA%E5%99%A8%E4%BA%BA/)
- [Loco-Manipulation With Quadruped Robots 综述（KFUPM）](https://pure.kfupm.edu.sa/en/publications/loco-manipulation-with-quadruped-robots-modeling-task-taxonomy-an/)｜[Gait Planning and Motion Control 综述（CMES/IEEE Access 系）](https://www.sciencedirect.com/org/science/article/pii/S1526149225000943)
- [Optimization and Learning-Based Planning and Control for Quadrupedal Manipulators（UNITesi 博士论文）](https://tesidottorato.depositolegale.it/handle/20.500.14242/193705)（约束 RL 腿臂操作 ≥80% 成功率）
- [Wheel-Legged-Gym 仓库（南科大 Clear Lab）](https://github.com/clearlab-sustech/Wheel-Legged-Gym)｜[upkie（开源平衡轮腿）](https://github.com/tasts-robots/upkie)｜[ocs2（ETH RSL）](https://github.com/leggedrobotics/ocs2)｜[awesome-wheeled-legged 清单](https://github.com/XinLang2019/awesome-wheeled-legged)｜[Unitree B2W_example（Go2-W/B2-W 驱动）](https://github.com/unitreerobotics/unitree_sdk2_b2w)
- [locomotion 十年演进（CSDN DAMO 开发者矩阵）](https://damodev.csdn.net/69a4f90954b52172bc5e761c.html)
- 轮足控制（2025 增补）：[多模态切换运动控制综述（IEEE 11179534，两轮腿机器人）](https://ieeexplore.ieee.org/abstract/document/11179534)｜[Wheeled-bipedal 相关检索（MDPI 45 篇）](https://www.mdpi.com/search?q=wheel-legged+system)｜[动态神经模型预测控制（DRMPC，scite）](https://scite.ai/reports/dynamic-neural-model-based-predictive-control-for-9O5kWaM4)｜[StaRide 车腿协调（Semantic Scholar）](https://www.semanticscholar.org/paper/A-Coordinated-Approach-for-Enhancing-Handling-and-Xu-Xu/0783c6ef463839030b937636214982c8e14c5c71)｜[学习型控制（Isaac Gym PPO + HIM，arXiv 2507.22345）](https://huggingface.co/buckets/huggingchat/papers-content/tree/2507/2507.22345.md?code=true)｜[下一代腿足运控综述（Heliyon）](https://matilda.science/work/c4d64725-c149-4e0b-819c-a45f60ab60d4?l=fr)｜[腿式肢体单元设计建模与控制综述（Cyborg and Bionic Systems 中文转述）](https://www.ebiotrade.com/newsf//2025-8/20250823082842644.htm)

**全车协调（新增，本次核实）**：
- [REMANI-Planner 官方仓库（Robotics-STAR-Lab）](https://github.com/Robotics-STAR-Lab/REMANI-Planner)｜[REMANI-Planner 项目页（ICRA 2024，DOI 10.1109/ICRA57147.2024.10610192）](https://robotics-star.com/REMANI-Planner/)
- [PTDM 论文（arXiv 2604.04166，浙大 FAST Lab）](https://ar5iv.labs.arxiv.org/html/2604.04166)｜[PTDM 代码（nmoma）](https://github.com/nmoma/nmoma)｜[浙大高飞团队新作中文解读（CSDN，6 倍提速）](https://damodev.csdn.net/69e43aab0a2f6a37c5a0d1ff.html)
- [RAMBO 论文（arXiv 2504.06662，RA-L 2025，Go2 实测）](https://arxiv.org/abs/2504.06662)｜[RAMBO 论文页（HuggingFace）](https://huggingface.co/papers/2504.06662)
- [HOVER 论文（arXiv 2410.21229，NVIDIA R²D²）](https://arxiv.org/abs/2410.21229)｜[HOVER 解读：底层控制"瑞士军刀"（CSDN）](https://blog.csdn.net/CyanNoah/article/details/151375310)
- [R²D²：NVIDIA 移动性与全身控制新工作流](https://www.engineering.fyi/article/r-d-advancing-robot-mobility-and-whole-body-control-with-novel-workflows-and-ai-foundation-models-fr)

**未核实项（不写或待核实）**：RSS MoMA 2025 研讨会表述未获直接证据支持（本文不引用）；PTDM 未实机部署（正文已标注）；陈祥驰硕士论文/熊蓉团队 FITEE 视觉伺服等浙大内容链接未在手，未列入。

## 相关

- [planning-control-roadmap.md](planning-control-roadmap.md)（规划控制路线，§六 RL 增强方向 = 本文的上层）
- [standards.md](standards.md) §1.11（调研/选型文档附来源规范）
- [07-handover.md](07-handover.md)（运行状态与参数快照）
- [retrospect/2026-08-23_doc_source_traceback.md](retrospect/2026-08-23_doc_source_traceback.md)（本次调研的来源回溯过程）