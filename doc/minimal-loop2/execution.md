# 最小闭环 2 · 执行卡（评价标准 + 流程）

> 用途: 每个阶段执行前**先在本文件补全执行卡**（判据 + 流程 + 预期现象），再上机执行；执行中打勾，达标即走
> 规矩（2026-08-24 定）: 细化的评价标准与流程一律留本地文档，不在对话里定——提前规划/预测后续步骤，执行才有效率
> 关联: [plan.md](plan.md)（总计划：序列/时间窗/验收原则）｜ 状态: A1 待启动（08-24）

---

## A1：W3 避障验收（08-24 ~ 08-26，实车两天）

### 1.1 评价标准（判据核对表）

| # | 项 | 判据 | 记录 |
|:--|:---|:---|:---|
| 1 | 静态绕行 | 3/3 次绕行到达、无碰撞 | ☐ |
| 2 | 人横穿 | ≥2 次记录：减速/停车 → 人离场恢复到达 | ☐ |
| 3 | 恢复行为 | ≥1 次：堵死不撞、原地旋转/backup、解除后自主恢复 | ☐ |
| 4 | 到达误差 | 每 goal <0.5m（`analyze_nav2_goal_error.py` 输出） | ☐ |
| 5 | 稳定 | 综合演练连续 3 次流程无人工干预 | ☐ |

达标 5/5 → A1 关，进 A2；否则补测缺口项（当天）。

### 1.2 前置条件

- [ ] N97 在线；降额参数 `nav2_params_low.yaml`（0.2/0.15/0.4）；`map_0815_clean`
- [ ] 箱子/立柱障碍物 ≥2 个（≥0.3m³）；人横穿安全区（首次 ≥2m）
- [ ] 手放急停随时可拍；全程录 bag + rviz 截图 + **运行视频（作品集素材）**

### 1.3 流程

**Day 1：启动 + 静态绕行 + 人横穿**

```bash
# ① 前置0 + 全栈（07-handover §三）：performance → CAN → 雷达 → 底盘(publish_tf:=false)
#   → IMU(静止3s校准) → EKF → Nav2:
ros2 launch r2_bringup nav2.launch.py \
  map:=/home/lin/maps/map_0815_clean.yaml \
  params_file:=~/Lin_workspace/r2_integration/install/r2_bringup/share/r2_bringup/config/nav2_params_low.yaml \
  rviz:=true
# ② 录 bag（话题含 /goal_pose /cmd_vel_smoothed——到达误差脚本依赖）:
ros2 bag record -o ~/Lin_workspace/r2_integration/bags/nav2_avoid_$(date +%m%d_%H%M) \
  /scan /odometry/filtered /cmd_vel /cmd_vel_smoothed /goal_pose /amcl_pose /tf /tf_static /map
```

- 设初始位姿：**只设一次**，设完先动一下确认粒子收敛（08-17 纪律，防 map 重叠）
- **热身**：近处 goal 3~5m。预期: 人走近/走远，local_costmap 膨胀圈 1~2 扫描周期实时出现/消失
- **静态绕行 ×3**：障碍放路径必经处 → 发对侧 goal。预期: global path 先绕开 → 局部再遇实时绕行 → 无碰撞到达
- **人横穿 ×2**：长直行 ≥5m 中途横穿。预期: 减速 → 停车 → 人离场重规划/恢复

**Day 2：恢复行为 + 综合演练 + 验收**

- **恢复行为 ×1**：三面围堵（两箱+墙）堵死路径。预期: 不撞、原地旋转/backup → 移箱解除 → 自主恢复到达
- **综合演练**：3 目标序列（含 90° 转角、窄缝）+ 中途 1 次横穿。预期: 连续 3 次无人工干预
- **验收**：bag 拷 VM → `python3 ~/Lin_workspace/bags/analysis/analyze_nav2_goal_error.py <bag_dir>` → 判据核对

### 1.4 预判风险与预案

| 风险 | 预案 |
|:---|:---|
| AMCL 静止不发布 /amcl_pose | 停稳后取最近帧（脚本已处理），别等它实时出数 |
| 窄缝/盲区再碰 | 已修参数（min_range 0.5 / costmap 6×6 / footprint 0.84×0.66 / inflation 0.30），若复现按 08-17 思路查 |
| 时间超预算 | 判据达标即收，静态绕行降为 2/3 时记录缺口改天补，不拖 Day 2 流程 |

---

## A2：FAST-LIO2 落地（08-24 ~ 08-26，A1 之后，0.5~1 天）

> 前置事实: 08-24 实车验证全项通过（旋转 <2° / 平移 0.5%）；部署手册 [fastlio2-n97-deploy.md](../fastlio2-n97-deploy.md) §五 TF 方案已定案
> 两个子任务: ②a TF 桥接入 R2 TF 树 ｜ ②b 建图源切换（FAST-LIO2 替代 KISS 重建图）

### 2.1 评价标准（判据核对表）

| # | 项 | 判据 | 记录 |
|:--|:---|:---|:---|
| 1 | TF 桥 | rviz 中 FAST-LIO 轨迹（camera_init→body）经桥与 R2 车体对齐可视；TF 树无断链/无双父警告 | ☐ |
| 2 | 建图 | FAST-LIO2 新图目检无重影；墙段连续 ≥10m（沿用 D3b 验收口径） | ☐ |
| 3 | 管线复用 | 新图经 pcd_to_map 出 2D 占用网格（z_min 0.3 是否上调待实测验证，雷达已抬至 0.655m） | ☐ |

### 2.2 决策点（执行前先定，30 分钟）

- **决策 1 桥接用途**：(a) 仅可视化对比（rviz 双系并存）还是 (b) 替代 EKF 作 Nav2 里程计源？
  建议先 (a) 打通验证，(b) 留 A2 之后。**影响**：决定 camera_init→odom 是否需要对齐标定。
- **决策 2 双父冲突**：EKF 已 publish_tf=false，桥链（odom→camera_init→body→base_link）与 EKF 的
  odom→base_link 并存会双父——处理：桥接期 EKF 保持停发 / 桥链用独立 frame（如 fastlio_body）待定。
- **决策 3 外参**：body→base_link 平移 = G354 实测 (-0.36, -0.035, +0.185)，旋转单位阵（mount_axes 已映射）。

### 2.3 流程框架

1. VM 侧先把两个静态桥写进 launch（`fastlio_bridge.launch.py`，/tf_static，transient_local——手册 §五纪律）
2. N97: FAST-LIO（`~/fast_lio_ws`，PATH=/usr/bin 编译产物）→ 桥节点 → rviz 对比 EKF 轨迹
3. 建图: 沿 D3b 录制纪律重跑一圈 → build_map/pcd_to_map 出图（z_min 参数实测定）

### 2.4 预判风险

| 风险 | 预案 |
|:---|:---|
| camera_init→odom 对齐无初值 | 启动时车不动，取 FAST-LIO 首帧位姿作静态对齐（待定实现） |
| 桥接后 TF 树混乱 | 先 rviz 单系验证，再并入；回滚 = 不启桥节点（零风险） |
| 新图地面雾 | z_min 0.3 按 0.655 抬升量上调 ~0.1 试（w1-operation 已标注） |

---

## B1：RL 部署（08-26 ~ 08-29，2~3 天，降级执行）

### 3.1 评价标准

| # | 项 | 判据 | 记录 |
|:--|:---|:---|:---|
| 1 | 环境跑通 | mjlab 或 Isaac Gym 装通，跑一个既有示例出**一次训练曲线/收敛截图** | ☐ |
| 2 | 概念讲清 | 能讲：RL 四足控制范式（asymmetric actor-critic / teacher-student / sim2real 域随机化），配 1 张自跑图 | ☐ |

### 3.2 流程框架（执行前按规矩补全细节卡）

1. 选型: 本机 GPU（3050 Ti / 云 4090?）→ mjlab（CPU 可跑，Go2 示例）vs Isaac Lab（GPU 必需）
2. 安装 → 官方示例跑通（优先官方路径）→ 出曲线
3. 收尾: 数据/截图入作品集素材；不给完整复现曲线（时间窗不允许，降级执行依据 plan.md 三）

---

## B2：新架构尝试（08-29 ~ 08-31，1~2 天，选一）

| 候选 | 判据 | 说明 |
|:---|:---|:---|
| explore_lite 探索 | 演示视频 + 探索覆盖率 >80%（场地 5×5m） | m-explore-ros2 源码构建，N97 轻量 |
| D435 视觉接入 | 检测演示（YOLO 既有经验）+ 3D 坐标输出 | Phase 4 前置，多模态叙事 |

> 选择依据: B1 结束后看余力与叙事缺口；执行前补全执行卡。

---

## C1：秋招冲刺（09-01 ~ 09-10，硬截止线）

| # | 项 | 判据 | 记录 |
|:--|:---|:---|:---|
| 1 | 作品集 | 2 个项目页（R2 导航闭环 + FAST-LIO2 部署/验证）上线 | ☐ |
| 2 | 面试深挖稿 | 每项目 5 分钟技术深挖（流程/数据/坑/指标）成稿 | ☐ |
| 3 | 数学/C++ | 每日穿插（具体安排引个人成长计划线 2，本文件不重复） | ☐ |

> B 段超时**不顺延 C1**（plan.md 四）。

---

## 相关

- 总计划: [plan.md](plan.md) ｜ 第一个 loop: [w3-operation.md](../minimal-loop/w3-operation.md)（本卡 A1 的详细来源）
- 部署手册: [fastlio2-n97-deploy.md](../fastlio2-n97-deploy.md)（A2 依据）｜ 验证数据: [retrospect 08-24](../retrospect/2026-08-24_fastlio2_verification.md)
- 到达误差脚本: `~/Lin_workspace/bags/analysis/analyze_nav2_goal_error.py`
