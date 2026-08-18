# W3 操作手册：动态避障 + 综合演练

> 关联计划: [plan.md](plan.md) W3（08-20 ~ 08-26）
> 执行机器: N97（192.168.1.210，需开机）+ VM（分析）
> 前置: W2 收尾完成（到达误差测量、连续导航测试，见 [w2-operation.md](w2-operation.md) D5-7）
> 状态: **计划（08-20 启动）**——本文档为操作手册，执行后在对应验收项打勾并记执行记录
> 参数纪律: 保持降额参数 `nav2_params_low.yaml`（0.2/0.15/0.4，全速验证暂缓 08-17 决策）

---

## 进度总览

| 日 | 事项 | 状态 |
|:--|:---|:---|
| D1 | local costmap + 避障配置确认 | ⏳ 计划 |
| D2 | 静态障碍绕行 + 人横穿测试 | ⏳ 计划 |
| D3 | 恢复行为（无解/堵死 → 重规划） | ⏳ 计划 |
| D4-5 | 综合演练（多目标 + 动态障碍 + 全程 bag） | ⏳ 计划 |
| D6-7 | W3 验收 + 复盘留档 | ⏳ 计划 |

---

## D1：local costmap + 避障配置确认

### 1.1 现状盘点（W2 已修参数，直接复用）

| 参数 | 值 | 来源 |
|:---|:---|:---|
| 雷达 min_range | 0.5 | 08-15 修复（出厂 0.9 盲区） |
| local_costmap | 6×6 m | 08-15 修复（3×3 太小） |
| footprint | 0.84×0.66 | 08-15 修复（urdf + 0.02 buffer） |
| inflation_radius | 0.30（local/global） | 08-17 修复（0.55 全覆盖外接圆） |
| MPPI CostCritic | consider_footprint=true | 已开（足迹级防撞兜底） |

### 1.2 实车确认（操作）

1. 全栈启动（07-handover §三，Nav2 用 `nav2_params_low.yaml`）
2. 设初始位姿（w2-operation §4.3 纪律）→ 发一个近处 goal（3~5m）
3. **costmap 实时刷新验证**：车旁站人，缓慢走近/走远，rviz 观察 local_costmap 膨胀圈
   随人体移动实时更新（08-15 已见现象，此处正式记录）

**预期**：人体进入雷达视野（>0.5m）后 1~2 个扫描周期内膨胀圈出现；人离开后消失。

---

## D2：静态障碍绕行 + 人横穿测试

### 2.1 静态障碍绕行

**场景**：场地中放置箱子/立柱（体积 ≥0.3m³，人形盲区外），发对侧 goal 使路径必经障碍。

```bash
# 录制（话题与 W2 连续测试一致）
ros2 bag record -o ~/Lin_workspace/r2_integration/bags/nav2_avoid_$(date +%m%d_%H%M) \
  /scan /odometry/filtered /cmd_vel /cmd_vel_smoothed /goal_pose /amcl_pose /tf /tf_static /map
```

**操作**：设初始位姿 → 发 goal → 观察规划路径先绕开障碍（global costmap 已记忆）→
若局部规划再遇障碍（local costmap 实时）→ 观察绕行轨迹。

**验收**（plan.md 验收标准）：车绕行到达目标，无碰撞；到达误差 <0.5m（w2-operation D7 脚本计算）。

### 2.2 人横穿测试

**场景**：车按 goal 直行中，人从侧向横穿车行路径。

**操作**：
1. 发长直行 goal（≥5m）
2. 车行至中途，人从侧向以正常步速横穿（保持 >0.5m 余量，安全前置）
3. 记录车反应：**减速 → 停车 → 人离开后重规划/恢复行进**

**验收**：人横穿期间车减速或停车（无急刹/碰撞）；人离场后车自主恢复到达 goal。
**安全纪律**：全程手放急停（遥控器/底盘电源），首次测试人横穿距离放远（≥2m），逐次逼近。

---

## D3：恢复行为（无解/堵死 → 重规划）

### 3.1 配置确认

- Nav2 恢复行为：clearing rotation + backup 等（nav2_params_low.yaml `recoveries_server` 段检查）
- MPPI 无解时行为：costmap 重规划触发条件

### 3.2 实车测试（操作）

**场景**：三面围堵（两个箱子 + 墙），发围堵内 goal 或使路径被堵死。

1. 设初始位姿 → 发 goal → 车接近障碍
2. 观察：planner 重规划 / 原地旋转（clearing rotation）/ backup
3. 移开一个箱子解除围堵 → 观察车是否恢复行进到达 goal

**验收**：堵死时车不撞障碍、原地旋转或后退重规划；解除后自主恢复。

---

## D4-5：综合演练（多目标 + 动态障碍 + 全程 bag）

**场景**：完整场地流程——起点 → 3~5 个目标点序列（含 90° 转角、窄缝、障碍绕行）→ 中途
安排 1~2 次人横穿/临时障碍入场。

**操作**：
1. 全栈启动 + 录 bag（话题同 D2）
2. 设初始位姿 → 连续发目标序列，每段间隔 ~10s
3. 中途人工注入动态障碍（人横穿 ×2、临时箱入场 ×1）
4. 全程记录：goal 数、成功到达数、碰撞次数、人工干预次数

**验收数据**：每 goal 到达误差（w2 D7 脚本）、总时长、无碰撞。

---

## D6-7：W3 验收 + 复盘留档

### 验收清单（对照 plan.md 第一节）

- [ ] **地图**: map_0815_clean 复用 ✅（W1 已验证）
- [ ] **导航**: 任意两点 goal 自主到达，终点误差 <0.5m（量化数据）
- [ ] **避障**: 障碍物入场车绕行到达；人横穿车减速/停车/重规划（实测记录）
- [ ] **稳定**: 连续 3 次完整流程无人工干预（综合演练数据）

### 收尾（闭环完成后）

- [ ] retrospect 复盘留档（`retrospect/YYYY-MM-DD_minimal_loop_done.md`：数据/经验/遗留）
- [ ] 02-progress / 03-current_state / 07-handover / plan.md 状态更新
- [ ] 作品集素材整理：运行视频、bag、日志、参数、复盘（量化验收数据）
- [ ] git 提交（`R2|` + 描述体，关联 retrospect）
- [ ] W4 遗留项评估：z 漂移 slip 复测、FAST-LIO2 评估、VNC 自启、performance 持久化

---

## 相关

- 计划: [plan.md](plan.md)（W3 + 验收标准）｜ W1: [w1-operation.md](w1-operation.md) ｜ W2: [w2-operation.md](w2-operation.md)
- 排障根源: [retrospect 08-15](../retrospect/2026-08-15_nav2_bringup.md) ｜ [retrospect 08-17](../retrospect/2026-08-17_nav2_initialpose_inflation_fix.md)
- 启动命令: [07-handover](../07-handover.md) §三
