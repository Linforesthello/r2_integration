# 低物盲区修法 B VM 验收全记录（bag 抽帧重发法定型 + 方法模板 + 经验点）

> 日期：2026-09-05
> 任务：低物盲区（0.3m 矮物扫不到）修法 B 的 VM 验收——**local costmap voxel_layer 增 `velodyne_low` 低带源**是否把矮物 mark 入图
> 状态：✅ **验收 PASS**（W1/W2 双判据命中，89 帧证据）；方法 = 用户选定的方向 B（wall 时间 + 静态 tf + bag 抽帧改 stamp 重发）
> 关联：[复盘 09-04（断点定位）](2026-09-04_lowobstacle_breakpoint.md)、[低物感知手段调研 §二 ②](../surveys/3d-lidar-2d-navigation-survey.md)、
> [costmap_experiment.md 08-25（方法前身）](../minimal-loop2/costmap_experiment.md)、[修法 A 待启登记](../pending-tasks.md §⑤)
> 证据落位：raw_data/`raw_vmreplay_B3_*`、`raw_vmreplay_probe_*`（2026-09-05，不入 git）
> 经验母本（迁自 /tmp，后续归档用）：raw_data/`raw_经验条_新技术路线VM回放测试_2026-09-05.md`、
> raw_data/`raw_经验条_VM回放costmap观察源坑_2026-09-05.md`

---

## 一、任务与验收对象

- **盲区根因**（复盘 09-04 定论）：/scan 由 velodyne_laserscan 用**单环 ring 8（+1° 上仰）**生成，光束最低 z≈0.66m，
  物理上够不到 0.3m 矮物；/velodyne_points 全环中 ring 0–4 能打到矮物（复盘矮物命中 ring 证据：n107-112 r0-3）。
- **修法 B**：local costmap voxel_layer 增加观察源 `velodyne_low`（topic=/velodyne_points，PointCloud2，
  高度带 min 0.0 / max 0.40（odom 系），marking+clearing），/scan 源保留 → observation_sources = `"scan velodyne_low"`。
  实施于 [nav2_params_low.yaml](../../r2_bringup/config/nav2_params_low.yaml)，VM colcon build 已同步 install（0 diff）。
- **几何依据**：VLP-16 光学中心距地 0.775m，odom 系地面 z≈-0.12（EKF z 锁 0）→ 带底 0 起已滤地；
  0.3m 物顶 odom z≈+0.18 ∈ 带内；ring 8 光束最低 z≈0.66 永不进带。
- **验收判据**：矮物预测方位/距离（复盘 09-04 §五：W2 静止段 -6°@2.63m / -3°@2.69m / -2°@2.94m；
  W1 -3°@2.06m / -8°@2.01m / -3°@2.33m）出现 **254 格**；同帧 bag scan 矮物方位 5.4m 开阔 → 该位置 254
  **只能来自新源**（scan 贡献排除）。

## 二、验收方法决策（sim 回放死路 → 方向 A/B/C → B）

### 2.1 直路死胡同（v1→v4 轮）：sim time + bag 全回放 + costmap 观察源

假设：bag 全回放（含 /tf + /clock）→ costmap use_sim_time → 观察源自动消费 → 读图判据。**4 轮全失败**：

| 轮 | 做法 | 结果 |
|:--|:--|:--|
| v1 | costmap + bag 全话题回放 | configure 崩溃（observation_sources YAML list 类型错，见 §3）|
| v2 | 修正参数 + bag 自带 tf | 订阅建立但 MessageFilter 不 ready，0 mark |
| v3 | 参数顺序坑修正后重试 | 同上 |
| v4 | 注入静态 tf（odom→base_link + base_link→velodyne）+ bag sensor | 同上，0 mark |

**定论**：**sim time + bag 回放 + costmap pointcloud 观察源 = nav2 已知 trouble 区**（ROS Index nav2_costmap_2d 明示）；
且 **costmap_experiment.md（08-25）已记录同方向结论**（"放弃 bag 回放 → 静态注入 + wall time"）——绕 4 轮才回到既有结论（教训见 §六 E2/E5）。

### 2.2 方向分叉（用户定夺，选 B）

| 方向 | 内容 | 代价 |
|:--|:--|:--|
| A | 整栈 nav2.launch.py sim time（官方 launch 覆盖 use_sim_time）| 重；AMCL 噪音 |
| **B（选）** | **wall 时间 + 静态 tf + 从 bag 抽矮物帧改 stamp 实时重发** | 变量最少：08-25 验证形态 + 真实点云 |
| C | 继续深挖 sim 轴（MessageFilter 不 ready 精确机制）| 方向未明，成本高 |

> B 的取舍逻辑：sim 轴问题根源 = "时间轴回放" → **砍掉时间轴**（消息 stamp 改当下 wall time），
> 机器人位姿用静态恒等 tf 固定于 odom 原点 → bag 帧内矮物相对位姿原样保留 → 判据照常成立。

## 三、试错路径（坑全记录，按时间）

### 3.1 预研/编排层坑（v1-v4 期间）

| 坑 | 机制 | 解法 |
|:--|:--|:--|
| observation_sources 配 YAML list | humble 版参数声明为 **string** 型；list 在 configure 报 "Wrong parameter type... setting to {string_array}" | WebSearch 核实（官方 obstacle 文档 + docs issue #851）→ 空格分隔 string `"scan velodyne_low"` |
| `ros2 bag play --clock "$BAG"` | --clock 带可选 Hz 参数，吞掉 bag_path | 显式 `--clock 100` |
| `ros2 bag play --topics ... "$BAG"` | --topics 为 nargs='+' 贪婪，吃掉 bag_path（"required: bag_path"）| bag_path 前置 |
| `ros2 lifecycle set activate` CLI 挂死 | 等 service response 无限期（costmap 侧 transition 实际成功；log 出现 get_state timeout）| `timeout 15 ... \|\| true` 包裹 |

### 3.2 B 轮次（wall 链路）：假阴性 ×2，均出在观测侧

| 轮 | 现象 | 根因 | 教训编号 |
|:--|:--|:--|:--|
| B1 | jsonl 0 行 | **reader 判据错**：raw lethal 存 254 原值，误用 int8 溢出 -2 | E3 |
| 判别轮 | synthetic scan（0° 1.0m）mark 正常：raw `{253:132, 254:3}`，格≈(0.98,±0.02) | 链路本身无问题 → 问题收敛到读取/重放侧 | — |
| B2 | jsonl 仍 0 行 | **reader 崩在 `meta.frame_id` AttributeError**（CostmapMetaData 无该字段，frame 在 header）——第 1 轮判据错导致 marks 恒空、永不触发报错行，修正后一收到 254 即崩于写盘前 | E4 |
| **B3** | **89 帧记录，W1/W2 全命中 → PASS** | 修 reader（header.frame_id）+ replay SIGTERM 容错（publish 抛 context invalid = kill 收尾噪音，正常退出）| — |

### 3.3 旁支事故

- 清理编排残留用 `pkill -9 -x python3`（宽泛兜底名）→ **误杀 Greenwave Monitor 常驻进程**（用户环境，欠一次恢复，暂缓）→ 教训 E6。

## 四、验收结果（B3 轮，判据输出）

reader（raw 254 原值判据）89 帧记录，去重 254 格 1245 个。判据：

```
[PASS] W2 主判据（-6°@2.63 / -3°@2.69 / -2°@2.94）：实际格 -4.4°/2.61m、-2.0°/2.8m 等（容差内）
[PASS] W1 辅证（-3°@2.06 / -8°@2.01 / -3°@2.33）：实际格 -1.3°/2.25m、-8.5°/2.02m（精确命中）
扇区明细：2.0-2.25m 与 2.6-2.75m 两带、右前 -1°~-9° 连续格簇 = 矮物点云表面入图形态
汇总：PASS — 低带源把矮物 mark 入 local costmap
```

- 排除 scan 贡献：同轮重放 bag scan 矮物方位 5.4m 开阔 → 2.0–2.9m 的 254 只可能来自 velodyne_low 源；
- z 带过滤语义与设计一致（odom 系 [0, 0.40]：地 -0.12 滤掉、0.3m 物顶 +0.18 入带）——经实证未踩 sensor-frame 过滤歧义。

## 五、方法模板（可复用：VM 上验证观察源/新配置）

```
① 静态 tf：odom→base_link（恒等）+ base_link→velodyne (0,0,0.655)     # wall 发布，无时间轴问题
② costmap：standalone nav2_costmap_2d（--params-file 目标配置）+ use_sim_time: False
③ 抽帧：rosbag2_py 读 bag 决定性时间窗 → 等间隔采样 N 帧（points+scan 同窗成对；本案例 2 窗 × 8 = 32 帧）
④ 重发：header.stamp 改写为当下 wall time；best_effort QoS（sensor 惯例）；循环发布
⑤ 读取：订阅 /costmap/costmap_raw（nav2_msgs/Costmap），lethal = data 原值 254 → 世界坐标
⑥ 判据：预测方位/距离容差内出现 254 格；同帧旧源数据在该方位开阔 → 排除旧源贡献
```

- 前置坑位：编排内 lifecycle 用 timeout 包裹；清理进程按**具体进程名/PID**（E6）；replay 需 SIGTERM 容错；
- 判据读数（E3）：raw 254 = lethal；master（OccupancyGrid）= 100（254 映射）；253/99 = 内切膨胀圈（**不是**障碍，勿作判据）。

## 六、经验点清单（层次已标注，09-10 盘点时筛选抽取）

> 全部先落事件层；标**建议去向**（四层制见 [2026-09-04_experience-layer-decision.md](2026-09-04_experience-layer-decision.md)）：
> 事件层（本文）→ draft 层（analysis-methods）→ 规则层（ros2-ops / ros2-qos-dds / standards）。

| # | 经验点 | 建议去向（未来筛） |
|:--|:--|:--|
| E1 | **VM 验证观察源/配置的方法模板**（§五 ①–⑥：wall + 静态 tf + bag 抽帧改 stamp 重发）| draft：analysis-methods（主题：VM 回放/重放测试法）|
| E2 | sim-time bag 回放 + costmap 观察源 = nav2 known trouble（ROS Index 明示 + 08-25 已记录）——**别绕** | 规则层：ros2-ops §9 旁支或 draft |
| E3 | costmap 读数语义：raw lethal = **254 原值**（int8 不溢出存储）；master = 100；253/99 = 膨胀圈非障碍（判据 ==254/100）| 规则层：ros2-ops（costmap 读数判据表）|
| E4 | **空结果先自查读取/记录链**（判据对否、记录器崩没崩——两次假阴性均在观测侧，jsonl 空 ≠ 无 mark）| 规则层：ros2-ops §7 排障纪律追加 |
| E5 | 排障先查项目内既有结论（doc/retrospect + raw_data）——E2 场景绕 4 轮才回到 08-25 记录 | 规则层：ros2-ops §7（先查本仓再外搜）|
| E6 | 进程清理**按具体进程名/PID**，禁 `pkill -x python3` 类宽泛兜底（误杀 Greenwave Monitor 事故）| 规则层：ros2-ops §10 进程卫生追加 |
| E7 | 低带 z 带设计实证：odom 系 [0, 0.40]（地 -0.12 滤、0.3m 物顶 +0.18 入带），过滤语义与几何一致 | 事件层留存（修法 B 专属，随 A 方案推进再提炼）|
| E8 | 方向取舍逻辑：sim 轴问题 → **砍时间轴**（stamp 改当下）而非调时间轴；每方向一变量对照（synthetic → 真实帧逐层加变量）| draft：analysis-methods |

## 七、遗留与后续

- [ ] **修法 A（待启）**：global obstacle_layer 增同源；前置 = B 验收通过（本日完成 ✅）+ 当前文档整理完 → 可启（用户决策，见 [pending-tasks.md §⑤](../pending-tasks.md)）
- [ ] **N97 实车检查单**（切 yaml 前）：install 副本同步（colcon build）、实车启动顺序（IMU 校准→EKF）、publish_voxel_map 验证、带顶 0.40 初值评估
- [ ] Greenwave Monitor 欠一次恢复（09-05 pkill 误杀，用户暂缓；恢复命令 = `ros2 launch greenwave_monitor hz.launch.py gw_monitored_topics:=…`）
- [ ] 09-10 收口盘点时：按 §六 标注筛选 E1/E2/E3/E4/E5/E6 抽取去向；两份 raw_data 经验母本归档（事件层已成文后可并入/回指）
