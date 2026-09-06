# 低物盲区修法 B N97 实车撞箱验证全记录（修复方向实锤 + 方法模板 + 经验点）

> 日期：2026-09-06
> 任务：修法 B（local voxel_layer 增 velodyne_low 低带源）N97 实车验证——实车故意试探导航避障，
> 结果**车直接撞上/推开 0.35m 箱子**；本次全探索定位根因并实锤修复方向。
> 状态：✅ **根因坐实**（global 无低带源 = 结构性断层；修复 = 开启修法 A，待设计方案实施）
> 关联：[09-05 修法 B VM 验收](2026-09-05_lowobstacle_fixB_vm_acceptance.md)（修法 A 待启来源）、
> [09-04 断点定位](2026-09-04_lowobstacle_breakpoint.md)、[低物感知调研 §二 ②](../surveys/3d-lidar-2d-navigation-survey.md)
> 证据落位：bag `bags/raw/box_lowband_20260906_091644`（236s，全话题，VM 副本已验证与 N97 大小一致）；
> 分析脚本 `bags/analysis/box_lowband_20260906/`（7 个，入库）；
> 前期取证 `raw_data/raw_低带几何_VLP16频率查证_2026-09-06_0909.md`
> 数据验证：本次 bag 录制期间 VLP-16 points/scan 全程 9.9Hz（无 3Hz 段）——3Hz 问题未复现，观测源待查

---

## 一、结论先行

1. **箱子在 local costmap 有 254 黑块，在 global costmap 没有（254=0）**——velodyne_low 已工作（local），
   但 global obstacle_layer 只有 scan 源（修法 A 未启）。
2. **planner 用 global costmap 规划** → 箱子对 planner 不存在 → 生成直冲路线 → 撞上/推开，全程无避让。
3. **修复方向实锤 = 开启修法 A（global 增 velodyne_low 同源）**——09-05 登记的"待启"项实为本次事故的修复。
4. 与之前"0.6m 近 / 0.7m 高扫不到"**不是同一根因**：近障是带顶几何盲区（打点 z≈0.49>0.40），本次撞箱是
   global 层结构性没源；两问题独立，需分别处理。

## 二、取证过程（时间序）

### 2.1 N97 节点/频率取证（09-06 09:00，见 raw_data 留档）

- velodyne 三节点 08:45 启动，packets/points/scan 实测均 9.91Hz（达标）；CPU governor=performance；
  生效参数（/tmp/launch_params_*）无 rpm/range 异常；N97 git 工作区干净
- 风险点记录：points/scan 发布端 RELIABLE，greenwave_monitor 订阅 BEST_EFFORT（qos-dds 手册 §一 / §三.1 有损模式），
  空闲不丢，跑全套高负载时可能掉——3Hz 观测点未对齐（用户暂缓）

### 2.2 bag 录制（09-06 09:16:45 → 09:20:41，236s）

- 全话题核心集合（points/scan/costmap_raw/costmap_updates/voxel_grid/clearing_endpoints/tf/map/
  odometry/filtered/cmd_vel/cmd_vel_smoothed/amcl_pose/plan/plan_smoothed/goal_pose/…）
- 初始使用 `--qos-profile-overrides` 内联参数失败（Humble 只支持 `--qos-profile-overrides-path`，
  且文件不存在报错）；最终用户确认**不走 QoS 覆盖**直接默认录——与往期 bag 一致
- 体检：points 2329 条/236s ≈ 9.87Hz 全程；/scan 9.93Hz；goal_pose 5 条；plan 29 条；
  **trajectories/plan_smoothed/transformed_global_plan 为 0**（controller 未执行轨迹，如避让行为）

### 2.3 分析链（脚本 bags/analysis/box_lowband_20260906/）

| 步 | 脚本 | 产出 |
|:--|:--|:--|
| ① 时间线 | analyze_bag_timeline.py | 5 次 nav goal 全在 +x 一线；运动段分组；cmd_vel 峰值 0.2m/s（降额） |
| ② costmap_raw 帧差 | analyze_costmap_raw.py | 静止段值直方图 {0:4011, 253:7281, 254:3108}——**无 255/无 1-252 灰阶**（异常信号） |
| ③ 点云找箱（velodyne 系） | find_box_in_points.py | S1 全窗正前 1.65m z=[-0.44,-0.43]（离地 0.335m 平顶）= 0.35m 箱，0-115s 不动 |
| ④ odom 跟踪（废弃） | find_box_odom.py | 全图聚类被环境低物淹没——弃用，改锥形 |
| ⑤ 锥形跟踪 | find_box_cone.py | 锥内低物簇（x,y 可用；**z 打印有 bug：pose[2] 实为 yaw**，已弃该脚本 z 列） |
| ⑥ 渲染（辅助） | render_frames.py | /tmp/frame_*.png 俯视图（点密，数值为准） |
| ⑦ **收官验证** | verify_box_costmap.py | local/global 箱区格值实测（#四），结论成立 |

### 2.4 关键事实链

- 箱子 odom ≈ **(2.33, 0.20)**（车初始位姿 (0.68,0.30) + velodyne 正前 1.65m az≈-3°~-8.7°；map 系 (2.46,-0.13)）
- 5 次 goal：118s (1.91,0.37) / 133s **(2.46,0.17)**（距箱 0.14m）/ 194s (1.35,0.22) / 206s (0.93,0.36) / 221s (0.75,0.06)
  —— 用户确认：**故意试探避障**，goal#2 基本贴箱
- 用户 rviz 观察：local 有箱子灰区、global 无对应黑区 → 与 #四 数据完全一致

## 三、方法模板（可复用：点云找箱→箱格分区实锤法）

```
① 找箱（velodyne 系）：筛选高度带（离地 0.3~0.4m 平顶）→ 0.1m 密度簇 → 平顶 z 固定范围即箱体
② 定位（odom 系）：车初始位姿 + 箱相对方位/距离 → 箱子世界坐标（静止段可靠，动段需 tf 全链路）
③ 验证 source 分层：箱子世界坐标 → local（odom 系）/ global（map 系）costmap_raw 各自取 ±0.7m 窗口值直方图
④ 判据：254(lethal)>0=有黑块；只有 253=内切圈无黑块；无 254=结构性没源（不是"刷新慢"，是**从未写入**）
⑤ 排除：global 253 零星来自邻近障碍圈，不算箱子 mark
```

## 四、收官验证数据（t≈50s 静止段，箱区 ±0.7m 窗口）

| costmap | 帧 origin (m) | 箱区直方图 | 判定 |
|:--|:--|:--|:--|
| **LOCAL**（odom 系，velodyne_low 在） | (-2.35,-2.70)，res 0.05 | 254:**316** 格 + 253:477 + 0:48 | **有黑块** ✅ velodyne_low 工作 |
| **GLOBAL**（map 系，scan 源 only） | (-9.67,-22.12)，res 0.05 | 254:**0** 格 + 253:98（邻近障碍圈）+ 0:743 | **无黑块** ❌ |

- map->odom tf：yaw -2.2°、t=(0.127,-0.238)（AMCL 静止段稳定）
- 253 内切圈 98 格 = 箱区 0.7m 内其他硬障碍的膨胀圈（非箱子自身 mark）

## 五、经验点清单（层次已标注，09-10 盘点时筛选）

| # | 经验点 | 建议去向 |
|:--|:--|:--|
| E1 | **局部/全局 costmap 分层对比判据**：local 有 254、global 无 = 结构性没源（层配置差异），非刷新慢；"已发现还撞"先查 planner 用哪层 | 规则层：ros2-ops（costmap 分层排查） |
| E2 | 点云找箱法：高度带 + 密簇 + 平顶 z 特征（①-②），可复用于任意"已知障碍未知位置" | draft：analysis-methods |
| E3 | costmap_raw 值直方图异常信号：正常局部图应含 255(unknown)/1-252(梯度)；全 0/253/254 无灰阶 = 观察源覆盖异常，需深查 | 规则层：ros2-ops |
| E4 | **坐标转换脚本坑**：tf yaw 与 z 混淆（pose[2]=yaw 当 z 用，z 输出 6.59/-10 等怪值即信号）——转换前先 print 中间量 sanity check | 规则层/draft |
| E5 | 0.6m 近障几何盲区（带顶 0.40）与本次撞箱（global 无源）是**两个独立问题**，修复方向不同，勿混为一谈 | 事件层 |
| E6 | 修法 A 待启（global obstacle_layer 增 velodyne_low）经实车事故验证价值——**待启项=潜在事故，推进优先级应提前** | 事件层/规则层 |
| E7 | Humble `ros2 bag record` 仅支持 `--qos-profile-overrides-path`（无内联）；QoS 覆盖文件不存在直接报错 | 规则层：ros2-ops §4 |
| E8 | 本 bag controller 无轨迹输出（trajectories 0 条）→ 车无避让行为实现；验证避让能力需先修 global（修法 A） | 事件层 |

## 六、遗留与后续

- [x] **修法 A 设计方案**（2026-09-06 成稿，见 §七，**待用户批准后实施**）
- [ ] N97 实车检查单：改 VM 源码 → git push → N97 pull → colcon build（install 同步）→ 实车复测避让
- [ ] 带顶 0.40 问题（0.6m 近/0.7m 高障碍）：几何盲区独立推进（带顶上调需评估侧壁/噪声风险）
- [ ] 3Hz 观测点未对齐（暂缓）；greenwave BEST_EFFORT 订阅 reliable 大消息风险（待高负载复核）
- [ ] costmap_raw 全图无灰阶异常（E3）——需后续确认是否低带源 max_obstacle_height 2.0 过宽导致，随修法 A 一起复核

## 七、修法 A 修改方案设计（2026-09-06，待批准）

### 7.1 目标

让 global costmap 也能看到的低矮障碍（≤0.4m，含 0.35m 箱类）→ planner 规划时避让，
从根上消除「local 看得见、global 看不见 → planner 直冲」的撞箱模式。

### 7.2 改动设计（降额版 `r2_bringup/config/nav2_params_low.yaml` → global_costmap）

`obstacle_layer`（line 298 起）改动 2 处：

1. `observation_sources: scan` → `observation_sources: "scan velodyne_low"`（humble 版 string 型空格分隔，同 local voxel 写法）
2. `velodyne_low:` 块（复刻 local voxel 参数，数据源一致）：

```yaml
        velodyne_low:
          topic: /velodyne_points
          data_type: "PointCloud2"
          min_obstacle_height: 0.0
          max_obstacle_height: 0.40
          marking: True
          clearing: True
          raytrace_max_range: 8.0
          raytrace_min_range: 0.0
          obstacle_max_range: 8.0
          obstacle_min_range: 0.0
          expected_update_rate: 10.0
```

**ObstacleLayer vs VoxelLayer 差异说明**：global 为 2D ObstacleLayer（非 voxel），
PointCloud2 观察源同样支持 min/max_obstacle_height 高度带过滤，过滤后几何语义 = 低带内点 2D mark +
2D raycast clear（到障碍格为止），与 local voxel 3D raycast 行为相近（voxel 的 3D 清空自洽优势
仅体现在"射线越过障顶不清障格"的 corner case；2D 语义经验近同，不影响本场景）。

### 7.3 验证（N97 实车检查单）

1. VM 改 → git push → N97 pull → `colcon build`（install 同步，launch 加载 install 副本）
2. 原场景复测：放 0.35m 箱（原 odom (2.33,0.20) 位）→ rviz 确认 **global costmap 箱区出现 254 黑块**
3. 重发 goal#2（(2.46,0.17) 距箱 0.14m 位）：预期 planner 绕行（battery: inflation 0.30 外扩）或停车，**不碰撞**
4. 录 bag 回放验证（复用 [bags/analysis/box_lowband_20260906/verify_box_costmap.py](../../../bags/analysis/box_lowband_20260906/verify_box_costmap.py)）
5. 确认 controller 行为（本次 bag `trajectories` 0 条；复测时看是否出避让轨迹）

### 7.4 同步事项（实施时一并做）

| 项 | 内容 |
|:--|:--|
| 全速版 `nav2_params.yaml` | 同改动（07-handover 警示：切回全速版前须同步膨胀 0.30 + 低带源——修法 A 同理加入该段，避免切回时"global 失明"复发） |
| 文档 | 07-handover §三 配置警示更新（低带源 = local+global 双源）；pending-tasks 修法 A 待启项勾除（实施完成后） |
| 预期速率 | global update_frequency 1.0 评估：车 0.2m/s、箱距 1.9m ≈ 9.5s 内 1Hz 更新 ~9 次、planner 重规划窗口足够；激进场景可调 2~5Hz（本次不动，避免无变量） |

### 7.5 风险与边界

- 带顶 0.40 不动：0.35 箱 @1.65m 中带（实测入带成功）；0.6m 近障是另一问题的几何盲区，**不混入本方案**
- global 观察源新增后，环境中所有 ≤0.4m 低矮物（踢脚线等）将 mark 进 global——预期效果，信噪比由实车观察
- E3 残留（costmap_raw 无灰阶）随本改动一并复核（观察源 max_obstacle_height 2.0 是否过宽，暂不改）
