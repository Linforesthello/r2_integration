# Costmap 独立实验留档（W3 避障问题①排查）

> 日期：2026-08-25
> 任务：minimal-loop2 A1（W3 避障验收）——问题①"costmap 远端不刷新（黑色障碍格只在眼前出现）"的独立实验
> 目的：区分「costmap 没 mark」（配置/感知问题）vs「costmap 有 mark 但 MPPI 不管」（前瞻问题）
> 状态：⚠️ 有重大进展但**尚未最终定论**（远距离测试待重做）
> 关联：planning-control-roadmap.md §5.7ter（运动模式争议点）、三 bag 分析（1357/1401/1405，`~/Lin_workspace/bags/analysis/browse_avoid_bags.py`）

---

## 一、结论速览（当前证据支持）

| 问题 | 结论 | 证据 |
|:-----|:-----|:-----|
| ① costmap 远端不刷新 | **costmap mark 管线本身正常**；"0 mark"是 lifecycle 未激活假象。远距离（>1m）mark 未验证成功（测试异常，待重做） | 激活后 1m 障碍 → lethal 正确 mark；raw 有 254×2 |
| ② 避让不及时 | MPPI 空间前瞻不足（已定论，非 costmap 问题） | 48步×0.04s×0.2m/s=0.38m + footprint 前缘 0.42m → critical 0.5~0.8m |
| ③ 低矮障碍扫不到 | 雷达高度/角分辨率物理盲区（已定论） | 安装定义 + 数据 |
| ④ footprint 边缘碰撞 | 0.08m 间隙实锤（已定论） | 1401 倒车贴 0.5m 障碍数据 |

**核心发现（本次实验）**：
1. **costmap 节点是 lifecycle 节点**——未 configure/activate 不发布任何话题（topic list 只有 transition_event）→ 此前多轮"0 mark"读数全部作废
2. **OccupancyGrid 是 int8**：cost 254（lethal）→ 100（黑色），253（内切膨胀）→ 99，其余 1-252 → 1-99 等比映射。读"有 mark"的正确判据是 **值==100（或 >80）**，99 是膨胀圈不是障碍
3. **/costmap/costmap_raw 类型是 `nav2_msgs/msg/Costmap`**（不是 OccupancyGrid）——Humble 定制版混合命名；此前 raw 一直读不到 = 类型不匹配

---

## 二、实验环境

```
静态 TF:   odom→base_link（单位变换）+ base_link→velodyne (0,0,0.655)
costmap:   单节点 nav2_costmap_2d（--log-level debug）
           /tmp/costmap_test.yaml  → VoxelLayer 版（plugins: voxel_layer + inflation_layer）
           /tmp/costmap_obs.yaml   → ObstacleLayer 版
scan:      /tmp/pub_simple_scan.py（极简 898 点，0°±2° 共 7 点有限，其余 inf，5Hz，BEST_EFFORT）
           （后改为参数化：python3 pub_simple_scan.py <距离>）
读取:      /tmp/read_mark.py（master/raw/voxel/clearing_endpoints 四路）
           /tmp/check_mark.py（master 轻量：lethal==100 格坐标 + 车头剖面）
           /tmp/read_raw.py（raw 专用：nav2_msgs/msg/Costmap）
日志:      /tmp/costmap5.log（VoxelLayer 1.4MB）、/tmp/costmap7.log（ObstacleLayer 36KB）、/tmp/costmap_re.log
```

实验配置（VoxelLayer 版核心参数）：6×6 rolling_window / 0.05m / footprint 0.84×0.66 / obstacle_max_range=8.0 / raytrace_max_range=8.0 / marking+clearing=True / max_obstacle_height=2.0 / mark_threshold=0 / inflation 0.30 / cost_scaling 3.0
**话题与类型（Humble 版命名，多次踩坑后确认）**


| 话题 | 类型 | 说明 |
|:-----|:-----|:-----|
| /costmap/costmap | nav_msgs/OccupancyGrid | 最终图（layer 合并 + 膨胀 + int8 映射）。Humble 版发布 `~/costmap`，新版 nav2 才叫 `~/map`（nav2_msgs/msg/Costmap） |
| /costmap/costmap_raw | **nav2_msgs/msg/Costmap** | layer 合并后原始图（未膨胀）。字段是 `metadata`（CostmapMetaData），写 `meta` 会 AttributeError |
| /costmap/voxel_grid | nav2_msgs/VoxelGrid | VoxelLayer 内部 voxel 计数。字段 `resolutions`（Vector3 x/y/z），不是 resolution；data 是 uint32[] |
| /costmap/clearing_endpoints | sensor_msgs/PointCloud2 | raytrace 端点（clearing 是否在跑） |

订阅 QoS：costmap 发布端 RELIABLE+TRANSIENT_LOCAL、订阅端 BEST_EFFORT；scan 两端 BEST_EFFORT（sensor_data）。


**为何不用 bag 回放（前期尝试，已放弃）**


最早想把实车 bag 里的 /scan 回放给实验 costmap，连续踩坑：

- `ros2 bag play --loop --clock`：时间回跳清 TF buffer（`Detected jump back in time. Clearing TF buffer`）→ costmap 报 odom/base_link 不连通
- 不带 --loop：bag 播完进程退出，/tf 订阅两端 0 条
- tf2_echo 默认 wall time 查不到 → 调 use_sim_time 探测 → "odom frame does not exist"（TF buffer 空）

**决策：放弃 bag 回放** → 静态注入（static_transform_publisher + wall time `use_sim_time: False` + 极简单帧 scan）。绕开时间轴问题，链路更干净、每变量可控。



---

## 三、完整排查过程
### 3.0 前史（16:00 前）：yaml 段名不匹配——实验最早的卡点


| 时间 | 日志 | 内容 |
|:-----|:-----|:-----|
| 15:35 | costmap.log | 首轮：yaml 段名 `local_costmap:` 不匹配 → 参数全丢，跑默认配置 |
| 15:37 | costmap2.log | 补 `--ros-args --params-file` 仍不生效（段名问题未察觉） |
| 16:09 | costmap3.log | 段名修正为 `/costmap/costmap:` 后重试 |
| 16:17 | costmap4.log | 参数加载验证通过（日志 `Using plugin "voxel_layer"`） |

- **症状**：节点跑默认参数（static_layer + obstacle_layer 全默认值），日志狂报 `Robot is out of bounds` + `Timed out waiting for transform from base_link to map`；`ros2 param get` 全 Parameter not set
- **根因**：yaml 段名必须匹配**节点全名** `/costmap/costmap:`（含命名空间）——`local_costmap:` 段被静默忽略；costmap 是 LifecycleNode，参数缺失不报错，症状像"配置错乱"而非"参数没加载"
- **修复**：段名改 `/costmap/costmap:` + 显式 `--ros-args --params-file`
- **验证**：`ros2 param get /costmap/costmap plugins` → `['voxel_layer','inflation_layer']`



### 3.1 第一轮（16:17~16:26）：「0 mark」误判期

- VoxelLayer 版（costmap5，1.4MB 日志）：`MessageFilter [target=odom]: Message ready` 完整出现（消息+TF 链路通）、`Updating map...` 5Hz 循环、`Map update time: 0.002s`（update 极快）
- ObstacleLayer 版（costmap7，36KB）：无 MessageFilter 日志、订阅稀疏取消息（间隔 0.6~34s，非 5Hz 规律）
- 现场发现**两个同名 /costmap/costmap 节点进程并存**（16:21 无 debug + 16:25 debug），/scan 订阅只有 1 个 → 实验环境被污染（同名节点竞争）
- 两版 master 读出来 obstacle 格（cost>80）全 0 → **误判「costmap 没 mark」**

- 补充实锤：`ros2 topic info /costmap/costmap --verbose` → **Publisher count: 2**（双发布者并存）；/scan 订阅仅 1 个 → 读数可能来自**没订阅上 scan 的进程**——VoxelLayer 版满日志 vs ObstacleLayer 版空日志，正是 scan 消息被另一进程拿走的竞争表现
- 期间 pub_scan.py（360s 定时版）进程活着但 0 消息（0.3% CPU 疑似卡住）→ 重写无限循环版 pub_scan2 → 5s 收 26 条正常



### 3.2 源码级排查（Humble 分支，GitHub 拉取）

> layer 实现不在 `src/`，在 **`nav2_costmap_2d/plugins/`**（obstacle_layer.cpp / voxel_layer.cpp / inflation_layer.cpp）

| 文件 | 关键逻辑 | 结论 |
|:-----|:---------|:-----|
| observation_buffer.cpp | bufferCloud：origin transform + 点云 transform + z 过滤（min/max_obstacle_height）+ push_front + purgeStaleObservations（keep_time=0 → 保留最新 1 条） | 无失败日志，链路通 |
| obstacle_layer.cpp | onInitialize：订阅 QoS=sensor_data（BEST_EFFORT）；laserScanCallback：transformLaserScanToPointCloud（异常→WARN+丢弃，无异常日志）；updateBounds：mark 条件（距离/高度/worldToMap 全过） | 参数默认值确认：source.max_obstacle_height 默认 **0.0**（若 yaml 缩进错会滤掉所有点——实测 yaml 缩进正确，排除） |
| voxel_layer.cpp | updateBounds：3D 欧氏距离判断 + worldToMap3D + markVoxelInMap(mark_threshold=0) | 条件全通过 |
| inflation_layer.cpp | updateCosts：膨胀源 = master 中 **LETHAL(254)** 格，逐格 costLookup 写入 | 有 254 才有膨胀圈 |
| costmap_2d_ros.cpp | mapUpdateLoop：getRobotPose → layered_costmap_->updateMap（resetMaps 每帧清零 → layer updateBounds → updateCosts 合并） | 无早退日志 |
**mark_threshold 官方定义（WebSearch 核实，2026-08-25）**


来源：[Voxel Layer Parameters](https://docs.nav2.org/configuration/packages/costmap-plugins/voxel.html)（docs.nav2.org 官方文档）、[turtlebot4 issue #247](https://github.com/turtlebot/turtlebot4/issues/247)、[voxel_layer.cpp 源码](https://github.com/Sarath18/navigation2/blob/ed6ff7d18fa75d101c4e7e29c77e713dc11164eb/nav2_costmap_2d/plugins/voxel_layer.cpp)

- `mark_threshold` = 一列中最小 voxel 数，达到才在 2D 图标记 occupied；`mark_threshold: 0` = 任一 voxel 命中即标记（turtlebot4 / Robotics SE 多示例的常见可用配置）
- `unknown_threshold`（空 voxel 最小数标记 unknown）默认 15
- mark_threshold 设过高（超过列内实际 voxel 数或超过 z_voxels）→ 障碍**永不 mark**——本实验与实车均配置 0，排除
- 相关坑：turtlebot4 #247 症状与本实验"不 mark"相似，根因是观察源用了**相对 topic**（topic: scan）导致订阅错话题；改**绝对路径**（topic: /scan）修复——本实验与实车配置均为绝对路径 ✓
- 排查点补充（obstacle_layer.cpp，对应正文 3.2 表格）：laserScanCallback 中仅当 `marking: True` 才把观测 push 进 `marking_buffers_`（updateBounds 经 getMarkingObservations 消费）——本实验与实车 scan 源均配置 marking: True，排除"marking 未开导致不 mark"



### 3.3 决定性发现（重来实验，16:50~）

用户叫停污染实验，**全部重来**（清理双进程 → 单进程重搭）：

1. **lifecycle 未激活**：topic list 只有 /costmap/costmap/transition_event → `ros2 lifecycle set /costmap/costmap configure + activate` 后全部话题上线（costmap/costmap_raw/voxel_grid/clearing_endpoints/footprint）——**此前所有「0 mark」读数 = 未激活假象**
2. **激活后四路读数（极简 1m 障碍）**：

   - master：126 格 >0，值分布 **{99: 124, 100: 2}**（99=膨胀圈、100=lethal，无其它梯度）；lethal==100 的 2 格在 world≈(0,0.95) ✓ 障碍正确 mark
   - raw（nav2_msgs/msg/Costmap）：**254×2 + 253×124** —— voxel 层写 lethal、膨胀输出 253 ✓
   - clearing_endpoints：7 点 = 7 个有限 scan 点 ✓ raytrace 在跑
   - voxel_grid：uint32 读全非零垃圾（max=0x2000FFFF）——**疑似消息字段/读法问题，不影响 mark（待查）**
3. **OccupancyGrid int8 映射实锤**：254→100、253→99.6→99。此前用「cost>80 判据」读「99」会漏判——99 不是障碍格！**正确判据：==100**
4. 车头剖面确认膨胀圈形状：`...99 99 99 99 99 99 100 99 99 99 99 99 99...`（障碍格 100 + 两侧膨胀 99）

### 3.4 实车配置对比（16:59 核对，排除配置层）


对照 [r2_bringup/config/nav2_params_low.yaml](../../r2_bringup/config/nav2_params_low.yaml) local_costmap 段——与实验配置**逐字段一致**（连 update/publish_frequency 都相同）：

| 项 | 实验 | 实车 local_costmap |
|:---|:---|:---|
| plugins | voxel_layer + inflation_layer | voxel_layer + inflation_layer |
| update/publish_frequency | 5.0 / 2.0 | 5.0 / 2.0 |
| 地图 | 6×6 rolling / 0.05m | 6×6 rolling / 0.05m |
| footprint | 0.84×0.66 | 0.84×0.66 |
| inflation | 0.30 / csf 3.0 | 0.30 / csf 3.0 |
| voxel_layer | mark_threshold 0 / z_res 0.05 / z_voxels 16 / max_h 2.0 | 同左 |
| scan | topic /scan / obstacle+raytrace 8.0 / marking+clearing True | 同左 |

→ **实验 = 实车 local_costmap 的 1:1 复刻**。实验证明的「激活后 mark 管线正常」**直接适用于实车 local_costmap**：问题①「远端不刷新」大概率不是 mark 管线不工作，剩余疑点收敛为：

1. 实车 costmap 节点 lifecycle 激活/订阅状态（实验早期同样假象过）——实车侧 `ros2 lifecycle get` 确认
2. 显示层/MPPI 前瞻（与 ② 同根因：空间前瞻 0.38m）
3. 远距离（>1m）mark 本身——实验 3.5 异常未完成，待重做

> 注：实车 **global_costmap** 才是 obstacle_layer + static_layer（含 track_unknown_space: true），与 local 不同；global 层不参与 MPPI 避让（MPPI 用 local），问题①只涉及 local。


### 3.5 远距离测试（1~5m，异常，未完成）

- 参数化 pub_simple_scan.py（距离命令行传入），循环测 1/2/3/4/5m
- **异常**：5 个距离的 lethal 全部在 world=(−0.05,0.95)/(0,0.95)——**障碍位置没变（一直 0.95m）**
- 每轮 pub 进程都报「退出 1」（后台任务退出记录）→ **发布器启动失败**，costmap 收到的可能是残留/错误数据，本轮测试无效
- 待查：/tmp/pub_dist.log（pub 报错原因）

---

## 四、遗留问题（待办）

1. **pub_simple_scan.py 退出 1 原因**：查 /tmp/pub_dist.log（可能 heredoc 写入问题 / 参数解析 / QoS）
2. **远距离 mark 测试重做**（2/3/4/5m）——问题①的最终判据：
   - 远端 mark 正常 → costmap 侧排除，问题①归入「MPPI 前瞻/显示层」，与 ②③④ 同根因链
   - 远端不 mark → 深挖距离过滤（obstacle_max_range 是否真正生效、raytrace 交互）
3. **voxel_grid 数据垃圾**：uint32 读异常（max=0x2000FFFF≈uint8 合并），确认消息 data 字段类型（Humble VoxelGrid.msg）——不影响 mark 结论，但影响 voxel 层状态观测
4. **实车侧验证**（N97）：`ros2 lifecycle get /local_costmap/local_costmap` 确认激活状态 + `ros2 topic echo /local_costmap/costmap --field data`（或 rviz）实测远端正值。实车 local_costmap 与实验 1:1 一致（voxel_layer 版），无插件差异；global_costmap 的 obstacle_layer+static_layer 是另一层，不参与 MPPI 避让


## 五、下一步计划（排序）

1. 修 pub_simple_scan 启动失败 → 重跑远距离（2/3/4/5m）mark 测试（本实验收尾）
2. 根据结果定论问题①：
   - 远端 mark 正常 → ①归因 MPPI 前瞻（与 ② 统一根因：空间前瞻 0.38m 不足），输出 4 问题最终结论
   - 远端不 mark → 按 §四-2 深挖
3. 汇总 A1 验收结论（4 问题最终根因 + 到达误差数据）+ 运动模式方案①（TwirlingCritic 10→30 + PathAngleCritic w 2→10）是否落地
4. 留档同步：本实验文档 → 关联 planning-control-roadmap.md §5.7ter、Obsidian 镜像（按 obsidian-sync.md 流程）

## 六、实验纪律与排障教训（本实验踩坑沉淀）


1. **pkill 自杀陷阱**：`pkill -f <关键字>` 会匹配到当前 bash 命令行自身 → 自杀（Exit 144）。规避三法：① 变量拼接 `P="nav2_costmap_2"d; pkill -f "$P"` ② 按 PID 直杀 `kill -9 <pid>` ③ 根治：pkill 与启动命令**分块执行**（不同 Bash 调用）
2. **lifecycle 节点不发话题**：未 configure/activate 的 costmap 只发布 transition_event——activate 前的所有读数作废。起进程后先 `ros2 lifecycle set <node> configure + activate` 再读
3. **同名节点竞争**：起进程前先 pkill + `ps -ef | grep costmap` 确认单进程；实验曾出现两个 /costmap/costmap 并存 → 读数张冠李戴（VoxelLayer 满日志 vs ObstacleLayer 空日志的真相）
4. **bag 回放时间轴坑**：--loop/--clock 时间回跳清 TF buffer → 静态注入（static_transform_publisher + wall time）更可控
5. **读消息前先确认字段**：`ros2 interface show <msg>` 一锤定音（Costmap.metadata 不是 meta；VoxelGrid.resolutions 不是 resolution）——省掉两次 AttributeError
6. **yaml 段名 = 节点全名**：costmap 参数段名必须是 `/costmap/costmap:`（含命名空间），否则静默跑默认参数，症状像配置错乱而非参数缺失（"Robot is out of bounds" / "Timed out waiting for transform"）


## 七、相关文件清单

- 实验脚本：/tmp/pub_simple_scan.py、/tmp/read_mark.py、/tmp/check_mark.py、/tmp/read_raw.py
- 实验配置：/tmp/costmap_test.yaml（VoxelLayer）、/tmp/costmap_obs.yaml（ObstacleLayer）
- 实验日志：/tmp/costmap5.log、/tmp/costmap7.log、/tmp/costmap_re.log、/tmp/pub_dist.log
- 源码副本（Humble 分支）：/tmp/nav2_observation_buffer.cpp、/tmp/nav2_obstacle_layer.cpp、/tmp/nav2_voxel_layer.cpp、/tmp/nav2_inflation_layer.cpp、/tmp/nav2_costmap_2d_ros.cpp、/tmp/nav2_layered_costmap.cpp
- 实车配置：r2_bringup/config/nav2_params_low.yaml（obstacle_max_range=8.0 等，与实验一致）

- 早期脚本（已弃）：/tmp/pub_scan.py（360s 定时版，疑似卡死）、/tmp/pub_scan2.py（无限循环版）
