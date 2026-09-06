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

## 八、修法 A 实车验证 + 新问题（近距丢黑块）—— 2026-09-06 上午实车，commit e87a3f8 已推送

### 8.1 验证结果（bag：box_lowband_20260906_101449 / _102944，N97 10:14/10:29 录）

- ✅ **修法 A 生效**：global 能刷出低箱黑块（254 格簇出现，箱子远距时 global 254 数量稳定）
- ❌ **新问题**：车接近后（约 1.4~1.9m）箱子黑块逐帧减少到 **0** → global 失明 → 撞箱
- 摆设：1×0.7m 长方体 + 2×0.35m 立方体，车前方 ±30°
- 102944 bag 无导航轨迹执行（trajectories/plan 0）——手动推车逼近验证；101449 同

### 8.2 机制分析（bag3 102944 定点追踪：箱区窗口逐帧 254 计数 vs 车距）

| 箱 | 远距稳定值 | 逼近变化 | 归零距离 |
|:--|:--|:--|:--|
| B1（0.35m） | ~20 格 @2.85m | 1.9m 起逐帧降：15→11→6→0 | **~1.4m** |
| B2（0.35m 大反射） | ~85 格 @2.97m | 降到 44-45 后 0.77m 保持 | 未归零（部分保留） |
| B3（0.35m） | ~17 格 @3.58m | 1.15m 处 4~11 格波动 | 部分保留 |

**机制修正（重要）**：初判为"clearing 竞争"，定点几何复核后修正为双因素：

1. **近距几何视锥盲区（mark 输入归零）**：VLP-16 最低环 -15°，光学中心 odom z≈0.655。
   0.35m 箱顶 odom z≈0.23 → 最低环打顶临界距离 d = (0.655-0.23)/tan15° ≈ **1.59m**；
   **d < 1.59m 时全部 16 环从箱顶上方掠过，低带源对该箱完全无点** → 无 mark 输入
2. **同层 clear 持续清空**：2D ObstacleLayer 中 scan 源 raytrace clear（射线打远处墙、路径穿箱格）
   与 low 源自身 clear 会把已有 254 逐帧清掉；mark 输入归零后净效果 = 254 逐帧衰减到 0
3. B2 保留（未归零）说明存在箱体更高/更大反射点 → 仍可被更高环在临界内打中？——部分保留的格可能来自 scan 之外的残余或带顶内更高反射；细节待后续

### 8.3 修复方向修正（原 §7.2 方案在近距失效——近距无 mark 输入是几何必然，非 clearing 参数可解）

| 方向 | 做法 | 评估 |
|:--|:--|:--|
| A（原 §7 设想） | velodyne_low `clearing: False` | **不够**：只减缓清空速度；scan 2D clear 与低带源无点仍会净清空 |
| **B（当前推荐）** | **velodyne_low 拆为独立层（只 mark 不 clear，或 mark-only layer）**：nav2 每 layer 独立，low 源 mark 进独立层后不被 scan 的 raytrace clear（同层内才互相清）；近距无点只是"不再新增"，已 mark 254 保留 | 治 clearing；不治"首次 mark 后移动接近"（mark 已留存即可防撞） |
| C | 增大带顶 0.40→0.6+ | 近距临界只与箱顶/环角有关，带顶上调对 0.35m 箱临界影响小（打顶临界 ~1.59m 是几何固定）——**不解决** |
| D | 放弃 VLP-16 低带路线，换近距传感器（D435/超声波） | 结构性解法，成本高，后续 phase4 再议 |

> 结论：**方向 B（mark-only 独立低层）为下一实施候选**——把 low 源的 mark 与 scan 的 clear 隔离。
> 实施前需验证 nav2 多 layer 参数结构（global/local plugins 增一层 + 该层仅 velodyne_low mark）。

### 8.4 数据与脚本落位

- bag：`bags/raw/box_lowband_20260906_101449`（105.7s）、`_102944`（197.9s，全话题，含 3 箱逼近撞箱）
- 脚本：`bags/analysis/box_lowband_20260906/analyze_bag3_102944_step1.py`（时间线+找箱）、`step2.py`（254 簇追踪）、
  定点判据（heredoc 版，待整合归档）
- 截图：`doc/retrospect/截图 2026-09-06 *.png`（rviz：三箱全局/局部视野）
- N97 运行参数实参核验：global obstacle_layer observation_sources = "scan velodyne_low"（修法 A 生效确认）

## 九、经验点补（§五 E1-E8 之外）

| # | 经验点 | 建议去向 |
|:--|:--|:--|
| E9 | **全图 diff 判丢失会被 costmap origin/窗口变化污染**（假消失呈地图边缘整带）——判局部丢改用**定点窗口逐帧计数 vs 车距曲线** | 规则层：analysis-methods |
| E10 | **几何视锥临界**：低带源对 h 高物的打顶临界 d=(z_光学−z_顶)/tan(最低环角)；低于临界全线掠过——低物 mark 输入是**距离函数**，非"看到就持续有" | 规则层/draft |
| E11 | nav2 同层内 clear 无差别（scan clear 会清同层 low mark）；**mark/clear 冲突隔离 = 拆独立层**是标准做法 | draft（nav2 多层设计） |
| E12 | 大话题 hz 检测工具约束：CLI `hz` best_effort 假阴性 → 自研 rclpy 并发测频脚本（QoS 自适应 + TL 话题处理），一次 10s 全车出表 | 规则层：ros2-qos-dds 附录 |

## 十、全车话题 hz 检测（2026-09-06，N97 现场，含早间 3Hz 疑云复核）

工具：`scripts/topic_hz_check.py`（并发单窗口测频，rclpy；reliable→best_effort QoS 自适应；
transient_local 话题 TL 订阅；期望表依据本日 bag 实测推算）

实测结果（nav2 全套 + velodyne 运行中，10s 窗）：

| 类别 | 话题 | 实测 Hz | 期望 | 判定 |
|:--|:--|:--|:--|:--|
| 雷达 | /velodyne_points | 10.36 | 10 | ✅ |
| | /scan | 10.36 | 10 | ✅ |
| | /velodyne_packets | 10.36 | 10 | ✅ |
| 里程计 | /odom_wheels | 50.6 | 50 | ✅ |
| | /odometry/filtered | 30.4 | 30 | ✅ |
| | /tf | 40.5 | 40 | ✅ |
| IMU | /imu/data | 82.2 | 85 | ✅ |
| costmap | /local_costmap/costmap_raw | 1.71 | 2 | ✅ |
| | /local_costmap/voxel_grid | 5.07 | 5 | ✅ |
| | /local_costmap/clearing_endpoints | 10.0 | 10 | ✅ |
| | /global_costmap/costmap_raw | **0.64** | 1.0 | ❌ 观察项 |
| 监测 | /diagnostics | 18.1 | 18 | ✅ |

结论：
- **points/scan 全程 10.36Hz 稳定达标——早间"3Hz"现象未复现**（观测点未对齐问题仍开放，greenwave
  BEST_EFFORT 订阅 reliable 大消息风险待高负载复核，见 §二/raw_data 0909）
- **观察项：global costmap 名义 1.0Hz 实测 0.64Hz**（大图 update 节流 ~1.56s/帧）——global 障碍反映
  延迟与撞箱链相关（planner 用过期图），后续深究方向：global update 耗时/分辨率/裁剪

经验点：E12（大话题测频工具约束与自研脚本）。

## 十一、整体结构审视：盲区问题链的四层归属（2026-09-06，系统性复盘）

> 载体分工：本文 = 事件复盘（撞箱链时间序 + 分层审视）；手段结论升级承载于
> [surveys/3d-lidar-2d-navigation-survey.md](../surveys/3d-lidar-2d-navigation-survey.md) §三B。

### 11.1 问题打在四个不同层

| 层 | 暴露问题（按时间） | 性质 | 状态 |
|:--|:--|:--|:--|
| L1 物理/布局 | 0.35m 低箱 <1.59m 全线掠顶（09-06 实锤）；0.6m 近障更低环也够不到 | **几何必然**，非软件 bug | 未修（除非改布局/传感器） |
| L2 转换层 | /scan 单环 ring8 结构盲 0.3m 矮物（09-04），points 全环有数据 | 数据路径选择 | ✅ 已绕过（低带源直进 costmap） |
| L3 costmap 层 | 同层多源 mark/clear 冲突；local/global 不对称（首撞根因）；global update 节流 0.64Hz | 语义与配置 | 部分修（global 已加源）；clear 冲突未修；节流未查 |
| L4 规划/行为层 | planner 只看 global；**无近距兜底机制**（撞箱无减速迹象） | 安全架构缺失 | 未修 |

### 11.2 三个系统级洞察

1. **单传感器挖潜到物理尽头**：转换层→local→global→L1 物理墙——近距低物信息对高置
   VLP-16 在几何上不存在，中间层改多少都没用
2. **costmap 2D 平面模型 = 语义问题非参数问题**：同层 clear 无差别（scan 看不见低箱却清其 mark）；
   每加"看不见 X 却影响 X"的源都要层隔离——结构性修补
3. **安全架构缺失 > 感知精度**：所有安全押在 perception 完美上；无几何盲区锥减速/停车兜底
   （对比 08-17 降额哲学：实机安全有分层，避障链没有）

### 11.3 结构调整建议（尺度排序）

| 尺度 | 动作 | 解决层 | 说明 |
|:--|:--|:--|:--|
| 近期（A1 阻塞） | ① velodyne_low 拆独立 mark-only 层 | L3 | 治 clear 冲突（真实 bug）；只保"已 mark 不消失"，首次逼近仍可能盲 |
| 近期/中期 | ② 近距盲区锥策略（<1.6m 低带无数据 → 限速/停车/plan cost 惩罚） | L4 | fail-safe 兜底，不依赖感知完美 |
| 中期 | ③ global 0.64Hz 深究 | L3 | 障碍反映延迟独立问题 |
| 远期（已有线） | ④ 物理布局/多模态（D435/MID-70/降装，roadmap §3 + survey §二④） | L1 | 结构性解法 |

### 11.4 待决策（用户定夺）

- **A1 验收口径**：静态绕行低物判据 = "感知解决"（继续 costmap 挖潜，物理上到 1.59m 为限）
  还是"感知+行为策略联合解决"（加②盲区锥兜底）——影响 A1 收口方式与 09-10 收手线记录
