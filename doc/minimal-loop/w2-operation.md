# W2 操作手册：Nav2 最小导航闭环

> 关联计划: [plan.md](plan.md) W2（08-13 ~ 08-19）
> 执行机器: N97（192.168.1.210，需开机）+ VM（改代码/分析）
> 前置: W1 完成（地图 `map_0815_clean` 就绪，见 [w1-operation.md](w1-operation.md) D4）
> 状态: 首闭环 ✅ 08-15 ｜ 降额过缝 ✅ 08-17 ｜ **收尾中（08-18）：D5-6 连续导航测试、D7 验收待做**

---

## 进度总览

| 日 | 事项 | 状态 | 说明 |
|:--|:---|:---|:---|
| D1 | Nav2 安装 + 全向轮参数 | ✅ 08-15 | `nav2_params_low.yaml` 降额参数入库 |
| D2 | 定位（KISS 桥 → **直接 AMCL**） | ✅ 架构变更 | KISS 桥未走，直接上正式方案 |
| D3 | rviz 发 goal 首闭环 | ✅ 08-15 | 首个自主导航闭环成功（降额） |
| D4 | 任意点 + 转角 + 绕行 | 🟡 部分 | 08-17 过缝验证覆盖；系统测并入 D5-6 |
| D5-6 | 连续导航测试 | ⏳ 待做 | 见本手册 D5-6 节 |
| D7 | W2 验收（含到达误差测量） | ⏳ 待做 | 见本手册 D7 节 |

---

## D1：Nav2 安装 + 全向轮参数（✅ 08-15）

### 1.1 安装确认（N97）

```bash
dpkg -l | grep -E "nav2-(amcl|map_server|mppi_controller|planner|controller|bt_navigator|lifecycle_manager|velocity_smoother)"
# 预期全部 ii；缺则 sudo apt install ros-humble-nav2-*
```

### 1.2 参数文件（VM 侧已入库）

| 文件 | 用途 | 状态 |
|:---|:---|:---|
| `nav2_params.yaml` | 全速版（0.5/0.3/0.8） | ⚠️ 膨胀参数仍 0.55，**切回前须先同步**（08-17 决策） |
| `nav2_params_low.yaml` | 降额版（0.2/0.15/0.4） | **当前实车唯一在用** |

**三处限幅链路**（全向底盘 + Nav2 一次跑通，无方向性返工）：
MPPI controller_server `vx/vy/wz_max` → velocity_smoother `max_velocity` → 底盘 `r2_params.yaml` `max_vx/vy/omega`。

### 1.3 MPPI model_dt 硬约束（08-15 踩坑）

`model_dt ≥ 1/controller_frequency(30Hz)`；0.033 → 0.04，否则 MPPI configure 报
"Controller period more then model dt" 致 lifecycle bringup 中断。

---

## D2：定位 —— 直接 AMCL（✅ 架构变更说明）

plan.md 原方案：W2 D2 做 KISS-ICP 定位桥（map→odom 桥 = KISS 映射，快速方案）。
**实际执行（08-15）**：跳过快速方案，**直接上正式方案 AMCL**——Nav2 测试期间不启动 KISS
（AMCL 定位不需要，省 N97 CPU），符合"先端到端"原则。

Nav2 场景 TF 链：

```
map ←[AMCL]→ odom ←[EKF]→ base_link ←[静态]→ velodyne / imu_link
```

---

## D3：首闭环（✅ 08-15）

### 3.1 启动顺序（N97，分终端）

见 [nav2-bringup.md](nav2-bringup.md) §二-4 表（CAN → 雷达 → 底盘 → IMU → EKF → Nav2），
**KISS 不启动**；前置：`performance` governor（每次开机必做，见 07-handover §三）。

### 3.2 操作要点（08-15 实车验证）

1. **先设 2D Pose Estimate，再谈"地图不显示/报错"**——map frame 依赖 AMCL 初始位姿；
   设位姿前 planner 报 "map frame does not exist" 是**正常等待噪音，不是故障**
2. 粒子 5s 内收敛到车位置 = AMCL 定位成功
3. **AMCL 静止不发布 /amcl_pose 与粒子是设计行为**（update_min_d/a 阈值内不更新粒子滤波），
   车动起来才发布——判断 AMCL 是否工作看 lifecycle 状态 + 动起来后的发布
4. 首闭环降额实测：`/cmd_vel_smoothed` 峰值 0.200/0.150/0.400 **精确钳在限幅**（smoother 生效）；
   车停稳于目标点，闭环成功（有擦碰 → 根因与修复见 D4）

### 3.3 数据与资产

- bag `~/Lin_workspace/bags/raw/nav2_first_loop/`（32.7 MiB，10 话题）
- 截图 `bags/rviz_nav2_first_loop.png` / `_2.png`
- 分析脚本 `bags/analysis/analyze_nav2_first_loop.py`

---

## D4：任意点 + 转角 + 绕行（🟡 08-17 部分覆盖）

### 4.1 撞障碍根因三件套（08-15 定位修复，08-17 实测覆盖：基本无碰撞）

| 根因 | 修复 |
|:---|:---|
| 雷达裁剪盲区 0.9m（velodyne_transform_node 出厂默认 `min_range`） | launch 覆写 `min_range: 0.5` |
| local_costmap 3×3m 太小（有效避障窗口仅 0.2m） | width/height 3 → 6 |
| footprint 0.62×0.62 vs urdf 车体 0.8×0.6 | footprint → 0.84×0.66（+0.02 buffer） |

### 4.2 窄缝过不去（08-17 修复）

`inflation_radius 0.55→0.30`（local/global，csf 保持 3.0）。0.55 ≈ footprint 外接圆半径 0.534m
→ 膨胀灰区全覆盖车扫过范围，窄缝全灰无法规划。收小后**实测无碰撞、能过过道**。
物理余量估算：缝宽 > 0.84+0.6 = 1.44m 可规划；1.2m 以下每侧 <18cm，人工排除，不靠参数硬挤。

### 4.3 初始位姿操作纪律（08-17 诊断：多次设位姿 → map 重叠）

1. 停遥控、RViz 拉远视角，在特征点（墙角）点击、箭头对准车头方向，**只设一次**
2. 设完先动一下（前进 ~0.5m 或原地转 30°+），确认粒子收缩、scan 与地图墙对齐，再发 goal
3. 已错位：Nav2 面板 **Clear Costmap(Global)** → 重新准确设初始位姿 → 仍不行
   `ros2 service call /reinitialize_global_localization std_srvs/srv/Empty {}` 全图撒粒子再动一下
   → 最后手段重启 nav2.launch

---

## D5-6：连续导航测试（⏳ 待做，08-18 起）

**目标**：多目标点序列（≥5 个 goal 连续下达，含直线/转角/折返/绕行场景），全程 bag，
为 D7 验收提供量化数据。

```bash
# 录制话题（⚠️ 比 08-15 首次闭环多 /goal_pose 与 /cmd_vel_smoothed——到达误差测量依赖）
ros2 bag record -o ~/Lin_workspace/r2_integration/bags/nav2_cont_$(date +%m%d_%H%M) \
  /scan /odometry/filtered /cmd_vel /cmd_vel_smoothed /goal_pose /amcl_pose /tf /tf_static /map
```

**操作**：
1. 全栈启动（§3.1）+ Nav2（`nav2_params_low.yaml` 降额参数）
2. rviz 设初始位姿（§4.3 纪律）→ 确认粒子收敛
3. 连续发 ≥5 个 goal（点间隔 ≥2m，含一次 90° 转角、一次折返），**每段间隔 ~10s 等车完全停稳**
4. 全程盯 `/cmd_vel_smoothed` 与 costmap；异常记 bag 时间点，事后复盘

**验收**：全部 goal 到达且停稳；误差见 D7 脚本计算。

---

## D7：W2 验收（⏳ 待做）

### 7.1 验收清单（对照 plan.md 第一节验收标准）

- [ ] 地图复用: `map_0815_clean` ✅（08-15 D4 已验证）
- [ ] 导航: 任意两点发 goal 自主到达，**终点误差 < 0.5m**（D5-6 bag + 本段脚本计算）
- [ ] 全程无碰撞（降额参数）
- [ ] bag 留档 + rviz 截图
- [ ] rviz 显示项确认: Global Planner→Path、Controller→Trajectories（默认关）、Amcl Particle Swarm 运行中勾选
- [ ] W2 复盘 → retrospect 留档 → 02-progress / 07-handover 更新 → git 提交

### 7.2 到达误差测量方案

**原理**：rviz 发 goal → `/goal_pose`（map 系 PoseStamped）；车停稳（`/cmd_vel_smoothed`
线/角速度均 < 0.01 持续 ≥2s）时的实际位姿取最近一帧 `/amcl_pose`（map 系，AMCL 定位输出）；
误差 = 2D 欧氏距离 + 归一化航向差。注意 AMCL 静止不发布（D3-3），停稳后取前后最近帧。

**脚本**（权威版 `~/Lin_workspace/bags/analysis/analyze_nav2_goal_error.py`，官方 rosbag2_py 零依赖，
已在 VM 用 nav2_first_loop 验证读取逻辑；该旧 bag 无 /goal_pose 输出提示，N97 新录 bag 含即可计算）：

```bash
python3 ~/Lin_workspace/bags/analysis/analyze_nav2_goal_error.py <bag_dir>
```

输出示例：

```
goal#  goal 时间              误差(m)  航向差(deg) 达标(<0.5m)
    1        1726382501.234       0.311         3.21 ✅
    2        1726382530.887       0.762        -2.40 ❌
```

---

## 相关

- 计划: [plan.md](plan.md) ｜ W1: [w1-operation.md](w1-operation.md) ｜ W3: [w3-operation.md](w3-operation.md)
- Nav2 bringup 操作记录: [nav2-bringup.md](nav2-bringup.md)
- 排障根源: [retrospect 08-15](../retrospect/2026-08-15_nav2_bringup.md) ｜ [retrospect 08-17](../retrospect/2026-08-17_nav2_initialpose_inflation_fix.md)
- 启动命令: [07-handover](../07-handover.md) §三
