# R2 外设集成 · 全局进度总览

> 最后更新: 2026-11-08（**老车 S1 全链实车首跑 PASS**：底盘 + IMU + EKF + slam_toolbox + Nav2 全链起身，**39 个目标 39 成功 / 0 失败**（真实 EKF 里程计，跳过 explore_lite）— [retrospect 全链首跑](retrospect/2026-11-08_oldcar_s1_fullchain_pass.md)；上文 Phase 进度仍为 VLP-16 时代基线。11-07 记录保留：§六 增 S1 进度快照：LD06 `/scan` 规格/crop 实测完成；**同日纠错：explore_lite 的"网络阻塞"不成立，根因是代理 TUN 未开**；**同日晚 explore_lite 已在 N97 构建成功（`326cf8a`），软件依赖转 🟢**；仅安装几何未实测。11-06 平台分叉口径不变；上文 Phase 进度为 VLP-16 时代基线）
> 内容: 全项目进度一览，每个 Phase 的完成度、依赖关系、下一步

---

## 一、总进度

```
Phase 0 底盘CAN控制 ━━━━━━━━━━━━━━━━━━━━━━━ 100% ✅
Phase 1 IMU+EKF融合 ━━━━━━━━━━━━━━━━○○  95%  ◆ 实车对比验证（08-06）+ yaw 方案①通过（08-12）
Phase 2 VLP16+KISS-ICP ━━━━━━━━━━━━━━━━━━━━ 100% ✅
Phase 3 Nav2导航     ━━━○○○○○○○○  25%  ◆ 首闭环（08-15）+ 降额过缝验证（08-17）；A1 避障实测进行中（08-25 首轮 + 低物链：断点定位 09-04 → 修法 B VM 验收 09-05 → 撞箱实锤 09-06 → 实车有效 + 二次失效根因实锤 + 收手定论转 3D 09-08）；全速验证暂缓
Phase 4 视觉AI       ━○○○○○○○○○  0%  ⏳
Phase 5 系统集成     ━○○○○○○○○○  0%  ⏳
                    ─────────────
 总计:              53%
```

---

## 二、Phase 详情

### Phase 0：底盘 ROS2 + CAN 控制 ✅ 100%

| 模块 | 状态 | 备注 |
|:-----|:----:|:------|
| CAN 总线通信确认 | ✅ | 4 路状态帧稳定接收 |
| r2_bringup ROS2 包 | ✅ | chassis_node + launch + config |
| 运动学逆解/正解 | ✅ | 公式从 R2.py 移植，已验证 |
| CAN ID → 物理位置映射 | ✅ | map_chassis.py 实测确认 |
| 坐标变换校准 | ✅ | calibrate_direction.py 8 组测试 |
| 编码器 ticks/圈标定 | ✅ | 均值 4241 |
| 里程计 /odom_wheels | ✅ | + TF (odom → base_link) |
| 超时保护 + 诊断 | ✅ | 0.5s 无指令自动停止 |
| 参数配置 (yaml) | ✅ | 全实车标定值 |
| 里程计积分修复（08-06） | ✅ | omega 单位 13.2× + 全向轮积分，见 [chassis_ekf_debug](retrospect/2026-08-05_chassis_ekf_debug.md) |
| 文档 | ✅ | 4 份 .md 同步到 Obsidian |

### Phase 1：IMU + 里程计 EKF 融合 ◆ 95%

| 模块 | 状态 | 备注 |
|:-----|:----:|:------|
| G354 驱动 | ✅ 已完成 | 38 字节 polling + Mahony(Kp=1.0, Ki=0.005) + ZUPT |
| **IMU 轴映射修复** | ✅ 已完成（8-03） | mount_axes 参数 + init/Mahony 两处符号修正；安装定义见 [sensor-mount.md](phase0/sensor-mount.md) |
| G354 静置测试 | ✅ 通过 | yaw 漂移 0.002°/min，132s 仅漂 0.005° |
| 驱动移入工作区 | ✅ 已完成 | `g354_driver/` 在 `r2_integration/` 下 |
| 轮速里程计 | ✅ Phase 0 已就绪 | `/odom_wheels` |
| robot_localization EKF | ✅ **已配置** | `config/ekf.yaml` + `launch/ekf.launch.py` |
| EKF 联调 | ✅ 已跑通（8-03） | IMU 姿态正确跟随车体（左/右转、左/右倾），RViz odom 正常 |
| 对比测试: 纯轮速 vs EKF | ✅ **完成（08-06）** | bag 对比: yaw 偏差 179°→4-14°，方形闭环 1.8m→0.27m（KISS 交叉验证一致） |
| EKF 过程噪声修复（08-06） | ✅ | 225 值矩阵（3.5.4 的 15 值格式加载 bug 致启动 NaN），见 [chassis_ekf_debug](retrospect/2026-08-05_chassis_ekf_debug.md) |

**下一步：slip 场景 z 漂移严格复测（08-05 遗留，[pending-tasks.md §⑤](pending-tasks.md)）——不再阻塞 Nav2（08-15 首闭环已跑）**

### Phase 2：VLP-16 + KISS-ICP SLAM ✅ 已完成

> 注：现役 VLP-16 + KISS-ICP。FAST-LIO2 曾因 ROS2 分支硬依赖 Livox 编译失败而搁置（探索记录见 [vlp16_slam_exploration.md](retrospect/vlp16_slam_exploration.md)），**08-24 已在 VLP-16 实车验证通过**（旋转误差 <2° / 平移 0.5%，部署手册 [fastlio2-n97-deploy.md](n97/fastlio2-n97-deploy.md)）——A2 主线（见 [07-handover.md](07-handover.md) 下一阶段）；MID-70 闲置、**计划内**（传感器选型 A/B，见 [planning-control-roadmap.md §3.4](roadmaps/planning-control-roadmap.md)）

| 模块 | 状态 | 备注 |
|:-----|:----:|:------|
| VLP-16 驱动 | ✅ 已安装 | velodyne_driver，设备 IP 10.18.18.6 |
| G354 IMU | ✅ 已就绪 | 已接入 EKF（见 Phase 1） |
| TF 标定 | ✅ 已完成（08-24 复测定案） | base_link→velodyne **z=0.655m**（光学中心离地 77~78cm − base_link 12cm；base_footprint 已删，65/77cm 冲突解决），见 [sensor-mount.md](phase0/sensor-mount.md) |
| KISS-ICP 建图 | ✅ 已跑通 | /velodyne_points → odom |

### Phase 3：VLP16 + Nav2 导航 ⏳

| 模块 | 状态 | 备注 |
|:-----|:----:|:------|
| VLP16 网络配置 | ✅ 已完成 | 设备 IP 10.18.18.6，目标 IP 10.18.18.20（2026-08-02 从 10.10.3.x 迁移） |
| VLP16 ROS2 驱动 | ✅ 已跑通 | |
| KISS-ICP | ✅ 已跑通 | 属于 Phase 2；/velodyne_points → odom |
| slam_toolbox 建图 | ❌ 已否决 | 不适合 VLP-16，见 [vlp16_slam_exploration.md](retrospect/vlp16_slam_exploration.md) |
| Nav2 配置 | ✅ 首闭环（08-15）+ 降额过缝验证（08-17） | AMCL 定位 + MPPI 跟踪 + velocity_smoother；降额参数（0.2/0.15/0.4）实车闭环成功，见 [retrospect 08-15](retrospect/2026-08-15_nav2_bringup.md)；08-17 inflation 0.30 过缝验证通过（无碰撞），见 [retrospect 08-17](retrospect/2026-08-17_nav2_initialpose_inflation_fix.md)；全速验证暂缓 |
| A1 避障实测（08-25 起现行主线） | 🟡 进行中 | 08-25 首轮 + 漏录重录决策；**低物盲区断点定位（09-04）→ 修法 B VM 验收 PASS（09-05，bag 抽帧重发法；实车验证 = N97 检查单，见 [retrospect 09-05](retrospect/2026-09-05_lowobstacle_fixB_vm_acceptance.md)）**→ 实车撞箱实锤（09-06：local 254 / global 无 = global 结构性没源，[retrospect 09-06](retrospect/2026-09-06_lowobstacle_fixB_crashbox.md)）→ **09-08：修法 B 实车第一次接近停障有效 + ringlaw 盲区边界 1.59m 实锤 + 二次失效根因实锤（global 整层清空抹 mark、盲区不可再生）→ 收手定论**（机制精修停投、180077c mark-only 保留不回滚，主线转 3D 规控，见 [pivot 09-08](retrospect/2026-09-08_lowobstacle_pivot_decision.md)/[secondfail 09-08](retrospect/2026-09-08_lowobstacle_secondfail_clearevent.md)）；判据 5/5、09-10 收手线见 [recruitment-learning-plan.md §4.1](roadmaps/recruitment-learning-plan.md)；执行卡 [execution.md A1](minimal-loop2/execution.md)、重录卡 [relog-operation.md](minimal-loop2/relog-operation.md) |
| W2 收尾核对 | 🟡 待核 | D5-6 连续导航 / D7 到达误差是否已随 A1 覆盖（[pending-tasks.md §⑤](pending-tasks.md)、[w2-operation.md](minimal-loop/w2-operation.md)） |
| 全速版 Nav2 验证 | ⏸️ 暂缓（08-17 决策） | 切回 nav2_params.yaml 前须先同步膨胀参数 0.55→0.30（[retrospect 08-17](retrospect/2026-08-17_nav2_initialpose_inflation_fix.md)）**及低带配置（obstacle_low_layer 独立 mark-only 层，180077c）** |

### Phase 4：D435 + Jetson 视觉 AI ⏳

| 模块 | 状态 | 备注 |
|:-----|:----:|:------|
| D435 驱动 | ◇ | `realsense2_camera` |
| Jetson ROS2 环境 | ◇ | Foxy 与 N97 Humble 互通 |
| YOLO 推理节点 | ◇ | 已有部署经验 |
| 视觉→导航集成 | ◇ | |
| 传感器加装布局（MID-70 + D435） | ◆ 装法定档（09-16） | MID-70 装 VLP-16 下方（离地 0.55~0.65m、前倾 15~20°）+ D435 夹两雷达之间（视觉导航栈用、不检测低物）；拟走双雷达组合（roadmap 方案 b）。几何评价：0.35m 箱盲区 1.59m→0.14~0.25m，近距贴地 <0.46m 归 L4 行为层；**待实车安装结构核算（三层叠装/供电/网口）+ 外参标定** — [survey](surveys/sensor-mounting-layout-survey.md) |

### Phase 5：系统集成与硬化 ⏳

| 模块 | 状态 | 备注 |
|:-----|:----:|:------|
| 气动系统接入 | ◇ | 外部引用（STM32_Now 工作区）：/home/lin/ProjectRequirement/MCU/Lin_STM32/STM32_F103C8T6/STM32_Now/3_Diacifa_t1，CAN ID 0x141 |
| EVENT 异常上报 | ◇ | 设计待实现 |
| 行为树/状态机 | ◇ | |
| 全系统启动 launch | ◇ | |

---

## 三、依赖关系图

```
Phase 0 底盘CAN控制  ──────────────── 已完成
       │
       ├──→ Phase 1: IMU+odom EKF  ←── 下一步
       │              │
       │              └──→ Phase 3: Nav2 导航
       │
       └──→ Phase 2: VLP16 + KISS-ICP SLAM
                              │
                              └──→ Phase 3 (地图来源)
                                     │
                                     └──→ Phase 5 系统集成
                                              ↑
                                      Phase 4 视觉AI (独立,可并行)
```

---

## 四、建议优先级

```
现在──────→ 短期 ──────→ 中期 ──────→ 长期
│           │            │            │
▼           ▼            ▼            ▼
Phase 0  Phase 1    Phase 2+3    Phase 4+5
已完成    IMU+EKF    SLAM+导航    视觉AI+集成
          (1~2周)    (2~3周)      (2~3周)
```

---

## 五、风险跟踪

| 风险 | 阶段 | 可能性 | 缓解 |
|:-----|:----:|:------:|:-----|
| VLP16 网络配置 | Phase 2 | 🟡 中 | ✅ 已解决：设备 IP 10.18.18.6，目标 IP 10.18.18.20（2026-08-02 从 10.10.3.x 迁移） |
| Jetson/N97 跨版本通信 | Phase 4 | 🟡 中 | 先用简单话题验证 |
| 多传感器加装（MID-70 + D435） | Phase 4 | 🟡 中 | 装法/几何已评价（09-16）；待核：三层叠装机械实现、供电余量、交换机空闲口、N97 算力、双 905nm 雷达互扰、D435 IR 投影互扰 — [survey](surveys/sensor-mounting-layout-survey.md) |

---

## 六、平台分叉后的进度口径（2026-11-06 新增）

> 上文 §一~§五 的 Phase 0~5 进度是 **VLP-16 时代基线**，保留用于回溯；老车现状已变，不能直接引用。
> 上位文档 = [two-car-architecture.md](two-car-architecture.md)；决策 = [retrospect/2026-11-06_platform_split_old_retrofit.md](retrospect/2026-11-06_platform_split_old_retrofit.md)。

| 车 | 当前阶段 | 近期目标 | 说明 |
|:---|:---|:---|:---|
| **老车 R2-OLD** | 平替 S0（接口冻结） | S1 单 LD06 + explore 闭环 | VLP-16 已撤；2D 线不继承 Phase 2/3 的 3D 百分比 |
| **新车 R2-NEW** | 方案/选型 | 底盘/上层/传感器方案 + 3D LIO 选型 | 不阻塞老车；3D 线从 Phase 2 资产迁移 |

**口径规则**：

1. 老车进度从 **S0 接口冻结**重新起算，不用 VLP-16 的 25%/100% 直接折算。
2. 旧 Phase 2/3 的完成度保留为「VLP-16 历史基线」，作品集/复盘可引用；不写成老车现状。
3. 新车进度单列，未定项标 `TBD`；不与老车抢同一实车窗口。
4. 每次阶段验收按 [two-car-architecture.md §三/§四](two-car-architecture.md) 的闸门更新本表，不改历史行。

### 6.1 S1 进度快照（2026-11-07）

- **驱动/规格** ✅：LD06 单/双实例 10 Hz、`/scan` beam 452~455/圈、角分辨率 ~0.795°、crop 机制实测 — [ld06-dual-lidar P7](old-car/ld06-dual-lidar.md)
- **软件依赖** 🟢：slam_toolbox / Nav2 已装；explore_lite 无 apt 包、需源码构建。**11-07 纠错**：此前记的"网络阻塞"不成立——根因是代理 TUN 未开，开启后 VM/N97 `git ls-remote` 均 exit=0（两机本地仍无副本，须 clone）。**11-07 13:00 已构建**：N97 `~/Lin_workspace/explore_ws` clone `326cf8a` + `colcon build --packages-up-to explore_lite` 成功，`explore_lite explore` 可执行在位（G5 销项）；**同日三份配置落文件**（`slam_toolbox_mapping.yaml` / `nav2_explore.launch.py` / `explore_params.yaml`，G1/G2/G3），**均未实测运行**；**11-07 晚复核订正**：`return_to_init` 与 7 参数实为 `declare_parameter` 已声明（原冒烟系构造期阻塞假阴性）— [explore-plan §3.1.3](minimal-loop2/explore-plan.md)
- **老车 Nav2 参数 + rviz 配置（11-07 六项定夺落地）** ✅ 已落文件：G4 新建 `nav2_params_ld06.yaml`（按定夺 = low 版**只删低带源** `velodyne_low`/`obstacle_low_layer`，膨胀 0.30 与降额速度照抄），`nav2_explore.launch.py` 默认改指它（原行注释留档）；G8 修复 `setup.py` 只 `glob('config/*.yaml')` 致 `nav2.rviz` 不进 install（`rviz:=true` 加载不到配置，原行注释留档）。`colcon build --packages-select r2_bringup` 已验证 install 副本含两文件。**均未实测运行**
- **安装几何** ❌：待实车量测（[sensor-mount §六](phase0/sensor-mount.md)）；`ld06.launch.py` 缺 x/y 参数、z 为占位。**11-07 定夺**：实际测算（含雷达 0° 朝向是否合适）等到 G10 再动，届时 LD06 的 URDF/TF 关系一并重写（现 `r2_sensors/config/r2.urdf` 仍是 VLP-16 的 `base_link→velodyne` z=0.655）
- **S1 首跑** ❌：等几何 + explore_lite；缺口全表见 [s1-readiness-gap.md](old-car/s1-readiness-gap.md)（23 项，G11 部分销项）

### 6.2 S1 进度快照（2026-11-08，不改 §6.1 历史行）

- **安装几何** ✅ G10 已实车量测回填（x=0.275 / y=0.290 / z=0.040 / yaw=−1.5708，yaw 同日实物复核 ≲2°）— [sensor-mount §6.1](phase0/sensor-mount.md)
- **自车遮挡 → 方案 B 过滤链** ✅ 上车：`/scan_raw` → `scan_to_scan_filter_chain` → `/scan`；polygon 晚修订 `x[−0.45,+0.40] y±0.34`（生效 ±0.48/±0.37）— [ld06_scan_filter.yaml](../ldlidar_stl_ros2/config/ld06_scan_filter.yaml)、[G24](old-car/s1-readiness-gap.md)
- **全链实车首跑（导航侧）** ✅ **39 目标 39 成功 / 0 失败**（真实 EKF 里程计 + RViz Nav2 Goal，21:01~21:26，跳过 explore）— [retrospect 全链首跑](retrospect/2026-11-08_oldcar_s1_fullchain_pass.md)
- **explore 闭环** ⬜ 未复测：过滤放宽后 `No frontiers found` 是否消失未知；覆盖率 >80% 未量化（未存图/未录包）— [explore-plan §3.5](minimal-loop2/explore-plan.md)

