# 平台分叉：老车低成本平替 + 新车升级（2026-11-06 决策记录）

> 日期: 2026-11-06
> 任务: 两车架构决策——老车传感器低成本平替、新车结构/传感器升级、共用接口冻结
> 状态: ✅ **用户已拍板（方案层）**，未实施；本文只记录决策与边界，实施细节见 [two-car-architecture.md](../two-car-architecture.md)
> 补充: 2026-11-06 用户定 **B 方案**——实施顺序首期保留 G354（S1/S2），S3 才换 STM32；边界见 §1.3
> 关联: [两车架构与接口](../two-car-architecture.md)（上位文档）｜[explore-plan.md](../minimal-loop2/explore-plan.md)（2D 探索实施稿）｜[07-handover.md](../07-handover.md)（状态交接）｜[pending-tasks.md](../pending-tasks.md)（待办）｜[planning-control-roadmap.md](../roadmaps/planning-control-roadmap.md)（规划控制路线）
> 证据落位: 用户原话见 §四；本机代码/驱动证据见 §二/§十；未实测项均标 `TBD`/`待实测`

---

## 一、决策陈述

### 1.1 总决策

**两车分叉，接口统一，实现分头走：**

1. **老车（R2-OLD，工作代号）**：不再做 3D/大传感器升级（结构上无法进一步升级），改为**低成本平替验证车**——VLP-16 撤下、换 LD06 串口 2D 雷达；G354 换 STM32 + MPU6050；加入已跑通的 Unitree GO-M8010-6 击球机构。软件走 2D：slam_toolbox + Nav2 + explore_lite。
2. **新车（R2-NEW，工作代号）**：在本项目基础上做**结构/传感器升级车**——新底盘运动结构、上层安装、D435 + MID-70（后续可能 MID-360、单点激光测距）；软件走 3D LIO + 视觉 + Nav2。
3. **共用层**：ROS2 话题/坐标系/算法/Nav2/EKF/explore 逻辑与文档规范；**分叉层**：底盘参数、URDF/TF、传感器驱动/launch、地图、标定、每车参数文件。

### 1.2 边界声明（收什么、不收什么）

**收：**

- 老车平替方案与分阶段实施顺序（先单 LD06 跑 explore，再低装/双雷达）。
- 两车共用接口契约（话题、frame、TF 唯一发布者、安全契约）。
- G8010 击球执行器的角色、动作时序、可复用本机栈与 ROS2 封装方向。
- 旧文档的适应性加注（不删不改写历史结论）。

**不收：**

- 不在本次实施任何代码/硬件改动；不创建新的 ROS2 包。
- 不替用户选定 LD06 数量/布置、双雷达融合拓扑、STM32 传输方式、G8010 触发接口、新车算力/传感器最终装法——这些列入 [two-car-architecture.md §十](../two-car-architecture.md#十开放决策待用户定夺) 待定。
- 不把老车的 2D 方案反向套到新车；不把 VLP-16 时代的 1.59m 盲区数字直接搬到 LD06。
- 不删除 VLP-16/KISS/FAST-LIO2 的代码、配置、文档——它们是新车/其他用途的资产。

### 1.3 实施顺序补充（2026-11-06 用户定 B 方案）

**目标形态不变，实施分阶段落地**——老车最终仍是 LD06 2D + STM32 IMU + G8010；但首期不一并换：

| 阶段 | IMU | 雷达 | 执行器 | 说明 |
|:---|:---|:---|:---|:---|
| **S1** | **保留 G354 + 现有 EKF** | 单 LD06 正常高度 | 不装车 | 只换感知源；验收含 EKF 基线对照 |
| **S2** | 保留 G354 | 低装 / 双 LD06 | 台架准备 | 雷达单变量继续 |
| **S3** | 换 STM32 + MPU6050 | 保持 S1/S2 状态 | 台架 | IMU 单变量；与 G354 同路线 A/B |
| **S4** | 保持 S3 | 保持 | 装车 | 执行器最后上车 |

**为什么首期保留 G354**：

1. **单变量原则**：LD06 已改变 `/scan`、TF、SLAM、costmap、Nav2 参数与 explore 输入；G354 + EKF 是已验证的 odom 基线（Phase 1 95%，yaw 方案① 08-12 通过），保留它可把 S1 故障限定在感知侧。
2. **MPU6050 是新增变量**：无磁力计，yaw 漂移、协方差、时间戳都要单独标定；与雷达同时换会让 S1 验收无法归因。
3. **2D 建图依赖 odom 质量**：slam_toolbox 的 `map→odom` 依赖 EKF 的 `odom→base_link`；odom 侧先保持已知良好，地图质量才有可比性。
4. **G8010 是执行器**：台架可并行；装车引入供电/EMI/机械扰动，放在 S4 更干净。
5. **串口冲突**：G354 与 LD06 均占 `/dev/ttyACM*`，S1 起就必须用 udev 固定名；再换 IMU 会多一个串口变量。

> 本节是**顺序补充**，不推翻 §1.1 的目标形态与 §四 的用户原话；S3/S4 的目标不变，只是后置。

---

## 二、背景与输入证据链

### 2.1 当前平台事实

| 事实 | 来源 |
|:---|:---|
| 现役老车 = 四全向轮 + CAN + G354 IMU + VLP-16 + N97；Nav2 降额闭环已跑通 | [07-handover.md](../07-handover.md)、[02-progress.md](../02-progress.md) |
| 低物盲区 1.59m 是 VLP-16 高置 + −15° 环的几何结果，9 月已收手 | [ros2-ops.md §12](../ros2-ops.md)、[survey §三B](../surveys/3d-lidar-2d-navigation-survey.md) |
| 现有 2D 探索方案（slam_toolbox + Nav2 + explore_lite）已梳理，未实机 | [explore-plan.md](../minimal-loop2/explore-plan.md)（2026-11-05） |
| LD06 驱动已在 VM：`~/ldlidar_ros2_ws`，`ldlidar_stl_ros2`，`ld06.launch.py`，230400，`/scan`，`base_laser` | 本机 launch 文件（已读） |
| G8010 本机栈：`~/Lin_workspace/unitree_goM80106` + `~/Lin_workspace/unitree_actuator_sdk`；串口 4Mbaud、FOC、id 0、gear ratio 6.33、位置模式示例 | 本机头文件/示例/文档（已读） |

### 2.2 用户判断（决策输入）

- 老车**结构上无法进一步升级**，但必须做传感器低成本平替（“因为一些原因，必须对老项目当前的 vlp16 搭载四轮全向轮车进行更换传感器”）。
- VLP-16 **彻底换下**，腾空间并挪作他用；雷达换成一个或两个串口雷达。
- IMU 换成 **STM32 + MPU6050 直发 ROS 消息格式**。
- 把之前跑通的 **Unitree G8010 电机及控制**加入老车。
- 新车在本项目基础上升级：底盘运动结构、上层安装方法、传感器选型（D435、MID-70、后续 MID-360、单点激光测距等）。
- 老车先**单 LD06 跑通 explore**，再考虑低处放置与多雷达融合。

### 2.3 为什么现在做这个决策

- 老车平台已到结构上限，继续在 VLP-16/3D 上投入的边际收益低；低成本 2D 平替能保留“可运行、可演示、可面试讲”的资产。
- 新车需要 3D/视觉与新结构，和老车的低成本验证**不是同一条技术路线**；先分叉，避免互相拖。
- 两车共用接口后，算法/文档/经验可以复用，硬件配置各自演进。

---

## 三、选项 × 影响

### 3.1 老车路线

| 选项 | 做法 | 影响 | 结论 |
|:---|:---|:---|:---|
| A. 保留 VLP-16 继续 3D | 老车维持现状，继续 KISS/FAST-LIO2 + 低物精修 | 与“结构无法升级、VLP-16 要挪走”冲突；空间/成本不划算；低物链已收手 | ❌ 不采用 |
| B. **老车 2D 单 LD06（首期）** | 撤 VLP-16，单颗 LD06 正常高度，跑 slam_toolbox + Nav2 + explore | 成本低、链路短、可快速端到端；失去 3D/低物高度维 | ✅ **首期采用** |
| C. **老车双 LD06 低装（二期）** | 两颗 LD06 靠近地面，第二颗做低带/补盲 | 低物覆盖改善；但两个扫描平面不是连续 3D，地面杂波/建图质量需实测 | ✅ **二期再评估** |
| D. 老车退役，只做新车 | 放弃老车 | 与“必须对老车做平替”冲突；丢失现有闭环资产 | ❌ 不采用 |
| E. 老车换 MID-70 等 3D | 用 3D 雷达做老车升级 | 结构/算力/成本都不支持；与新车路线重复 | ❌ 不采用 |

### 3.2 老车 IMU / 执行器

| 选项 | 做法 | 影响 | 结论 |
|:---|:---|:---|:---|
| A. 保留 G354 | 不动 IMU | 最稳，但不符合“低成本平替/把 G354 挪作他用”的方向 | ❌ 不采用 |
| B. **STM32 + MPU6050** | STM32 采 MPU6050，ROS 侧发 `/imu/data` | 成本低、可控；MPU6050 无磁力计，yaw 漂移/协方差/时间戳是新增风险 | ✅ **采用（S3 实施；S1/S2 保留 G354；传输方式待定）** |
| C. G8010 做底盘驱动 | 用 G8010 替代轮毂电机 | 与现有四全向轮 CAN 底盘冲突；G8010 是关节电机，不适合直接做轮驱 | ❌ 不采用 |
| D. **G8010 做击球执行器** | 触发→爆发转角→停→慢回，打排球 | 复用本机成熟栈；新增任务执行器与安全设计 | ✅ **采用** |

### 3.3 新车路线

| 选项 | 做法 | 影响 | 结论 |
|:---|:---|:---|:---|
| A. 老车渐进改 | 在老车结构上继续加传感器 | 结构上限已到；与用户“新车升级”意图不符 | ❌ 不采用 |
| B. **新车平台 + 复用软件** | 新底盘/上层/传感器；复用 ROS2/Nav2/EKF/explore/文档 | 前期投入大；但能承载 3D/视觉与后续 MID-360 | ✅ **采用（方案层）** |
| C. 直接买成品平台 | 放弃自研 | 与项目资产/学习目标不符 | ❌ 不采用 |

### 3.4 G8010 动作时序选项

| 选项 | 做法 | 影响 | 结论 |
|:---|:---|:---|:---|
| A. 速度模式一直转 | `dq` 控制，撞到球后继续转 | 无法精确停位/回位；易过流/机械冲击 | ❌ 不采用 |
| B. **位置模式三段式** | 爆发到击球角 → 保持 → 慢速回 `q0` | 可控、可重复；需要标定角度/步进/kp/kd | ✅ **采用（首版）** |
| C. 力矩/阻抗模式 | 直接给 `tau` 或阻抗 | 控制更“柔”，但台架标定复杂；首版不必要 | ⏸ 备选 |

---

## 四、用户拍板记录（原话）

> 以下为用户 2026-11-06 会话原话（按主题摘录，未改写语义）；完整上下文见会话记录。日期以本文件落盘日为准。

1. **平台分叉与老车平替**
   > “当前项目，vlp16彻底换下，最近在搞的是一辆新车{因为目前的老车结构上无法进一步升级}（但是因为一些原因，必须对老项目当前的vlp16搭载四轮全向轮车进行更换传感器，进行低成本/平替化{比如雷达从vlp16换为一个或两个串口雷达，imu换成stm32+mpu6050直发ros消息格式，这样的组合进行，且需要把之前跑通的宇树g8010电机以及控制加入到老车中}），新车打算在这个项目的基础上进行升级，包括底盘运动结构、上层安装方法、传感器选型（包括d435,mid70后续可能还有mid360,单点激光测距等等传感器）”

2. **老车先单 LD06 跑 explore**
   > “如果只是单独先走一个ld06雷达，跑通explore怎么样，然后再去考虑低处放置以及多雷达融合？全面评价”

3. **顶层文档与决策记录**
   > “1、留下本地决策记录，同时对之前的本地后续方向文档进行适应性修改（A. 先写一份“两车架构与接口”顶层文档：老车平替 + 新车升级 + 共用/分叉清单，再往下拆。）”

4. **G8010 击球动作**
   > “2、go8010涉及到的是根据触发快速爆发转动一定角度，停下，慢速回到初始位置（要打击排球），本机内有成熟的软件栈（ @/home/lin/Lin_workspace/unitree_goM80106 @/home/lin/unitree_actuator_sdk ）”

5. **VLP-16 去向**
   > “撤掉当前安装的车体主雷达（vlp16），换成一款ld06（串口2d单线雷达），腾出空间以及雷达挪作他用，考虑进行布置两颗串口雷达，进行传感器融合，将雷达布置在靠近地平面处，这样也能避免近处盲区（以及被观测物体的高度限制）”

**拍板含义**：

- 老车平替是**必须执行**，不是候选；新车升级是**方案层确定**，细节待定。
- 首期只做单 LD06，双雷达低装是**后续评估项**，不是首期范围。
- G8010 的用途明确为**击球执行器**，动作时序明确为**爆发→停→慢回**。
- VLP-16 不装回老车；去向待定。

---

## 五、成果保留清单（不回滚、不删除）

| 资产 | 处理 |
|:---|:---|
| VLP-16 驱动/launch/URDF/配置/文档 | **保留**，老车不启动；新车或其他用途可复用 |
| KISS-ICP / FAST-LIO2 代码、配置、部署手册、验证数据 | **保留**；3D 主线迁新车，不在老车复活 |
| `nav2_params_low.yaml`（含 `velodyne_low` 低带源、mark-only 结构） | **保留为历史基线**；老车另建参数，不直接改它 |
| 旧地图/bag/分析脚本 | **保留**；老车新地图另存 |
| LD06 驱动 `~/ldlidar_ros2_ws` | **保留并复用**；N97 本机构建 |
| G8010 本机栈 `~/Lin_workspace/unitree_goM80106`、`~/Lin_workspace/unitree_actuator_sdk` | **保留并复用**；新 ROS2 包链接，不复制乱改 |
| 既有文档（07/01/02/03/roadmap/explore 等） | **只增不删**；加平台分叉注记，历史结论保留 |
| `r2.code-workspace`（用户 WIP） | **不动、不 stage** |

---

## 六、状态文档同步清单（收口核对）

> 按 [doc-engineering.md §十一](../doc-engineering.md) 的收口同步核对卡执行；状态只在源文档更新，本文不复制细节。

- [x] 新建上位文档 [two-car-architecture.md](../two-car-architecture.md)
- [x] 新建本决策记录
- [x] 根 [README.md](../../README.md) 文件树增补（two-car + 本记录）
- [x] [standards.md §2.1](../standards.md) 顶层树同步
- [x] [07-handover.md](../07-handover.md) 增补平台分叉状态 + 导航入口
- [x] [pending-tasks.md](../pending-tasks.md) 增补两车任务分组与 VLP-16 条目状态
- [x] [01-plan.md](../01-plan.md) 头部加平台分叉注记（保留五阶段历史基线）
- [x] [02-progress.md](../02-progress.md) 增补两车进度口径
- [x] [03-current_state.md](../03-current_state.md) 近期完成表增补决策行
- [x] [sensor-mount.md](../phase0/sensor-mount.md) 加老车平替注记/待定节
- [x] [explore-plan.md](../minimal-loop2/explore-plan.md) 增补 LD06 平台适配节
- [x] [startup.md](../startup.md) 加两车启动注记
- [x] [planning-control-roadmap.md](../roadmaps/planning-control-roadmap.md) 加平台分叉注记
- [x] [minimal-loop2/plan.md](../minimal-loop2/plan.md) 加平台分叉注记
- [x] [recruitment-learning-plan.md](../roadmaps/recruitment-learning-plan.md) 加一行前提变更注记
- [x] [retrospect/README.md](README.md) 登记本记录
- [x] `python3 scripts/check_doc_links.py`：本次致坏 = 0（1147 条全存在）
- [x] B 方案边界同步：决策记录 §1.3 + [two-car-architecture.md](../two-car-architecture.md) §一/§3.1/§3.2/§3.3/§3.4/§3.6/§八 + [03-current_state.md](../03-current_state.md) + [sensor-mount.md](../phase0/sensor-mount.md) + [startup.md](../startup.md) + [pending-tasks.md](../pending-tasks.md) + [07-handover.md](../07-handover.md)

---

## 七、方法模板节（可复用操作卡）

### 卡① 平台分叉决策卡（先冻接口，再分头实现）

1. 写清两车的**定位差异**（低成本验证 vs 升级平台）与**不做什么**（老车不跑 3D、新车不复制老车）。
2. 列出**共用层**（话题/算法/文档）与**分叉层**（底盘/URDF/驱动/参数/地图/标定）。
3. 先冻结 ROS 接口契约（话题名/类型/frame/QoS/频率/唯一发布者），再谈硬件选型。
4. 每车一份参数/URDF/地图；禁止一份配置两车漂移。
5. 旧文档只加注、不删改；历史结论保留为基线。

### 卡② 传感器平替接口冻结卡

1. 选一个**稳定话题**作为契约（如 `/scan`），不要让 Nav2 直接依赖新驱动私有话题。
2. 新驱动接入后先 `ros2 topic info -v` 核对 QoS、frame、频率，再写参数。
3. 静态 TF 的占位值（如 LD06 launch 的 `z=0.18`）必须实车重标；不要把占位值当定案。
4. 换 IMU 时先检查协方差/时间戳/坐标系，再谈 EKF 调参；协方差全零会重演 NaN。
5. 用 bag 留一份“换前/换后”基线，验收用数据不靠观感。

### 卡③ 单雷达先行、双雷达后置的分阶段验收卡

1. 首期只装一颗 LD06 在正常高度，先跑通 `/scan → slam_toolbox → Nav2 → explore`。
2. 首测场地 ≥5×5m、无低矮障碍、有急停/监护；先端到端，不调低物。
3. 记录基线：`/scan` 频率、地图重影、Goal 成功率、覆盖率、CPU。
4. 二期再低装/加第二颗；对比“单雷达 vs 双雷达/低装”的地图质量与低物可见性，**用同一场地/同一路径**。
5. 双雷达先分开 `/scan` + `/scan_low`（保留几何语义），不要一上来合并成单 scan。

### 卡④ G8010 “爆发—停—慢回”时序卡

1. 上电先发零力矩帧读 `data.q`，记为 `q0`；确认 `merror==0`、温度正常。
2. 输出端目标角 → 电机轴：`q_target = angle_deg * π/180 * gearRatio`，`gearRatio = -queryGearRatio(GO_M8010_6)`；符号实车确认。
3. BURST：从当前 `q` 出发，按 `stepSize` 逐步逼近击球角；`kp/kd` 由台架从小往大调，防 `merror=3` 过流。
4. HOLD：保持击球角 `hold_ms`；监测温度/错误码。
5. RETURN：目标改回 `q0`，用更小 `stepSize`/更低 `kp` 慢速回位；不要直接切 `mode=0` 带载松手。
6. 退出/急停：渐进降 `kp`、升 `kd`，再 `mode=0`；信号处理只设标志，停止指令在主循环后发。
7. 验收：角度重复性、回位误差、单次时序、连续 N 次温升、急停响应；数值台架后回填。

---

## 八、经验点层次标注节

> 去向按四层制：**draft 层** = [analysis-methods.md](../analysis-methods.md)（新经验先完整展开）；**规则层** = [ros2-ops.md](../ros2-ops.md)/[standards.md](../standards.md)/[doc-engineering.md](../doc-engineering.md)；**事件层** = 本文留存。单事件新经验不直写规则层（[doc-engineering.md §十二](../doc-engineering.md)）。

| # | 经验点 | 类型 | 建议去向 |
|:--|:---|:---|:---|
| E1 | 平台分叉先冻接口，再分头实现；共用算法/分叉硬件配置 | 方法 | draft（analysis-methods）→ 成熟后 doc-engineering |
| E2 | 传感器平替保持稳定话题（`/scan`、`/imu/data`），驱动可替换 | 方法 | draft（analysis-methods） |
| E3 | 2D 单线雷达只有单扫描平面；低装减少低物盲区但不等于 3D 覆盖 | 技术认知 | draft（analysis-methods）→ survey 备注 |
| E4 | 双雷达不同高度 = 两个平面，不是连续覆盖；优先分开 `/scan` + `/scan_low` | 技术认知 | draft（analysis-methods） |
| E5 | 换 IMU 先验 yaw 漂移/协方差/时间戳；MPU6050 无磁力计，不能照搬 G354 的 EKF 参数 | 排障前置 | draft → ros2-ops §6（配置失效三查旁边） |
| E6 | G8010 位置模式先读 `q0`、注意输出/转子符号与减速比、`merror=3` 过流 | 操作卡 | draft（analysis-methods）→ 专题文档 |
| E7 | 执行器“爆发—停—慢回”用状态机 + 超时/急停；不要带载直接 `mode=0` | 方法 | draft（analysis-methods） |
| E8 | 旧文档只加注不删改；历史结论保留为基线 | 文档纪律 | 已在 [doc-engineering.md §十](../doc-engineering.md)（不新增） |
| E9 | 平台分叉决策要记录“用户原话 + 选项×影响 + 保留清单”，便于后续翻案/交接 | 决策方法 | 事件层（本文）+ draft 引用 |

---

## 九、遗留 / 待定（转 [pending-tasks.md](../pending-tasks.md) 与上位文档 §十）

| 事项 | 状态 |
|:---|:---|
| LD06 数量/布置（单颗正常/单颗低装/双颗低装/一高一低） | 待用户定夺 |
| 双雷达融合拓扑（分开 `/scan`+`/scan_low` vs 合并） | 待用户定夺 |
| STM32 IMU 传输（micro-ROS vs 串口桥） | 待用户定夺 |
| G8010 触发接口（ROS service vs GPIO）与接口形态（Trigger vs Action） | 待用户定夺 |
| 新车 360° 覆盖（MID-70 + 2D 补盲 / MID-360 / 旋转） | 待用户定夺 |
| 新车算力（N97 / 新工控机 / Jetson） | 待用户定夺 |
| VLP-16 去向 | 待用户定夺 |
| 老车 LD06 安装高度/俯仰、双雷达串口 udev 名 | 实车标定 |
| G8010 击球角/回位速度/kp/kd/限位/供电 | 台架标定 |

---

## 十、来源

> 本文未使用 WebSearch/WebFetch；事实来自用户原话、本机代码/驱动与项目既有文档。未实测项已标 `TBD`/`待实测`。

| 结论 | 来源 |
|:---|:---|
| 老车结构无法进一步升级、必须低成本平替、VLP-16 挪作他用、新车升级方向 | 用户 2026-11-06 原话（§四.1/§四.5） |
| 先单 LD06 跑 explore，再低装/多雷达 | 用户 2026-11-06 原话（§四.2） |
| 两车顶层文档 + 决策记录 + 文档适应性修改 | 用户 2026-11-06 原话（§四.3） |
| G8010 击球动作与本机栈 | 用户 2026-11-06 原话（§四.4） |
| LD06 驱动参数/端口/frame/静态 TF 占位 | 本机 `~/ldlidar_ros2_ws/src/ldlidar_stl_ros2/launch/ld06.launch.py` |
| G8010 串口 4Mbaud、FOC、id 0、gear ratio 6.33、位置模式/停机/过流 | 本机 `~/Lin_workspace/unitree_goM80106/include/serialPort/SerialPort.h`、`include/unitreeMotor/unitreeMotor.h`、`src/locationMode_8010t1.cpp`、`src/doc/locationMode_8010t1.md`、`src/doc/260511.md`；`~/Lin_workspace/unitree_actuator_sdk/README.md` |
| 2D 探索链路与风险 | [explore-plan.md](../minimal-loop2/explore-plan.md)（2026-11-05，未实测） |
| 低物盲区旧几何 | [ros2-ops.md §12](../ros2-ops.md)、[survey §三B](../surveys/3d-lidar-2d-navigation-survey.md) |
| MID-70/D435 装法（纸面） | [sensor-mounting-layout-survey.md](../surveys/sensor-mounting-layout-survey.md)（2026-09-16，未实测） |
| 文档/决策记录规范 | [standards.md §1.14/§2.8](../standards.md)、[doc-engineering.md §十一/§十二](../doc-engineering.md) |

---

## 十一、变更记录

| 日期 | 变更 | 说明 |
|:---|:---|:---|
| 2026-11-06 | 初稿 | 平台分叉决策落盘：老车平替 + 新车升级 + 共用/分叉 + G8010 时序；状态文档同步清单待执行 |
| 2026-11-06 | 实施顺序补充 | 用户定 B 方案：S1/S2 保留 G354 + 现有 EKF；S3 换 STM32；G8010 台架独立、S4 装车；边界同步 two-car/03/sensor-mount/startup/pending/07 |
