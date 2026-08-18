# Nav2 · 多次设初始位姿诊断 + 膨胀参数过缝修复（08-17 实车）

> 事件日期：2026-08-17（N97 实车，降额参数 nav2_params_low）
> 关联：[07-handover.md](../07-handover.md) ｜ [nav2_params_low.yaml](../../r2_bringup/config/nav2_params_low.yaml)

## 一、现象

1. **多次设置 2D Pose Estimate 后 map 重叠、障碍生效**（诊断，见 §四）
2. **costmap 膨胀过大，明明有路不通过、窄缝过不去**（已修复，见 §二~三）

## 二、根因（现象 2）

- `inflation_radius 0.55m` ≈ footprint 0.84×0.66 的**外接圆半径 0.534m**（对角线一半）——膨胀灰区正好把车自身扫过的范围全覆盖，缝内所有格子 cost 都不为 0
- `cost_scaling_factor 3.0` 衰减偏缓：cost = 253·e^(−csf·(d−内切半径))，距障碍 0.3m 处 cost 仍 ~100，整条缝都是"灰区"
- Navfn 全局规划 / MPPI CostCritic 对高成本区避让 → 路径规划不出来
- **关键认知**：MPPI CostCritic 已开 `consider_footprint=true`（足迹级碰撞检查），真正的防撞兜底在控制器层，膨胀层不必覆盖整个外接圆，可以收小只留"路径余量"语义

## 三、改动与验证

- 改动：`nav2_params_low.yaml` local/global 两处 `inflation_radius 0.55→0.30`（csf 保持 3.0，作第二步变量），文件头注释同步（commit fc778da）
- 物理余量估算：缝宽 > 0.84 + 0.6 = 1.44m 可规划；1.2m 以下每侧余量 <18cm，建议人工排除，不靠参数硬挤
- **验证（08-17 实车）**：基本无碰撞，能通过过道（此前明明有路却不通过）
- 决策（08-17）：**全速参数验证暂缓，保持降额现状**；⚠️ 后续切 `nav2_params.yaml` 前注意其膨胀参数仍是 0.55，需先同步

## 四、现象 1 诊断（多次设初始位姿 → map 重叠）

- **机制**：每次点击发布 /initialpose → AMCL 粒子复位到点击位姿；点击不准 + update_min_d/a（0.25/0.2）下静止不更新 → 错位持续；车动后按扫描匹配收敛，室内对称/重复结构（四面相似墙、类似角落）易锁到错误局部最优 → map→odom TF 错 → scan 轮廓与地图错位（视觉上"map 重叠/重影"），错位 scan 被 global costmap（map 系）标记并膨胀 → "障碍生效"
- **待确认**：Humble AMCL 默认 `always_reset_initial_pose=false`，部分版本首次设置后忽略后续 /initialpose（日志出现 "Ignoring initial pose" 即后续点击无效）→ 下次复现看 AMCL 终端日志确认
- **操作纪律**（避免复现）：
  1. 停遥控、RViz 拉远视角看清全图、在特征点（墙角等）点击、箭头对准车头方向，**只设一次**
  2. 设完先动一下（前进 ~0.5m 或原地转 30°+），确认粒子云收缩、scan 与地图墙对齐，再发 goal
  3. 已错位：RViz Nav2 面板 Clear Costmap（Global）清旧障碍 → 重新准确设初始位姿 → 仍不行 `ros2 service call /reinitialize_global_localization std_srvs/srv/Empty {}` 全图撒粒子再动一下 → 最后手段重启 nav2.launch

## 五、经验

- 膨胀参数不是越大越安全：footprint 级碰撞检查（consider_footprint）已兜底时，inflation 只承担"路径余量"语义
- 排障纪律：每次只加一个变量——先收 inflation_radius，csf 留作第二步
