# 老车 S1 链路重跑 + explore 零前沿根因（LD06 自车遮挡）

> **日期**：2026-11-08（17:27 链路重跑；17:48~18:02 诊断重跑）
> **任务**：② 链路联调——LD06（G10 新几何）→ 静态 TF 顶替里程计 → slam_toolbox → Nav2(explore 版) → explore_lite；
> 以及「explore 报零前沿」的根因定位。
> **状态**：✅ 链路验收 PASS；✅ 零前沿根因已定位（物理安装）；🟡 软件屏蔽方案待定夺
> **关联**：[11-08 静态联调（旧几何）](2026-11-08_oldcar_s1_static_bringup.md)（本文的前序；
> 其「规划全败未定因」仍未处置）｜[sensor-mount §6.1/§6.1.2](../phase0/sensor-mount.md)（几何定义）
> ｜[old-car/startup.md](../old-car/startup.md)（启动权威）｜[s1-readiness-gap.md](../old-car/s1-readiness-gap.md) G24
> **证据落位**（均本地，不入 git）：
> `doc/raw_data/raw_s1_chain_rerun_n97_2026-11-08_1727.md`（链路重跑终端实录）、
> `doc/raw_data/raw_s1_explore_zero_frontier_diag_2026-11-08_1751.md`（诊断重跑全部探针输出与源码摘录）。

---

## 一、结论先行

1. **链路本身 PASS**：新几何（x=0.275/y=0.290/z=0.040/yaw=−90°）下 LD06 → slam_toolbox → Nav2 全链起身，
   TF 三链完整，7 个 lifecycle 节点全激活，收尾干净。
2. **explore_lite 报 `No frontiers found`，不是 explore 的缺陷，也不是参数问题**：根因是
   **LD06 装得太低且落在车体轮廓内，约 1/3 光束打在机器人自身结构上**（406 束中 128 束落点落在车体矩形内），
   自车回波 → lethal 格 → 0.30 m 膨胀罩住机器人自身 → 自由空间被切成 55 个连通域 →
   explore 从机器人可达的自由区只剩 **18 格** → 挂在上面的唯一前沿簇不足 0.5 m，被 `min_frontier_size` 滤掉。
3. **单靠 Nav2 侧参数修不好这件事**：explore 读的是 `/global_costmap/costmap`，其中 static_layer 来自
   slam_toolbox 的 `/map`；`/map` 由**原始 `/scan`** 建出。污染发生在最上游，任何只有 costmap 层的过滤都绕不过去。

---

## 二、链路重跑验收（17:27）

| # | 判据 | 实测 | 判 |
|:--|:---|:---|:--:|
| 1 | LD06 新几何上位 | `translation (0.275, 0.290, 0.040)`、`rotation z=−0.707108 w=0.707105` | ✅ |
| 2 | `/scan` 出数 | `ldlidar communication is normal` → `Publish topic message` | ✅ |
| 3 | slam_toolbox 建图 | `Registering sensor` + 产出 `/map`（当轮 161×132） | ✅ |
| 4 | Nav2 起全 | 7 节点 `Managed nodes are active`；`StaticLayer: Resizing costmap to 161 X 132` | ✅ |
| 5 | TF 三链完整 | `base_link→base_laser`（含几何）/ `odom→base_link`（零）/ `map→odom`（逐秒更新） | ✅ |
| 6 | 进程卫生 | `ps` / `ros2 node list` 双空 | ✅ |
| 7 | explore 发目标 | **零前沿，立即停止** | ❌（见 §三） |

时序：slam 启动 → explore 启动 **25 s**；Nav2 激活 → explore 启动 **7 s**
（对比 11-08 旧几何轮：128 s / 71 s）。

---

## 三、零前沿根因：五环证据链

> 原则：每一环都是实测，不是推断；复刻算法与上游源码逐字对齐（见 §四）。

| 环 | 观测 | 数据 |
|:--|:---|:---|
| ① 症状复现 | 诊断重跑中 explore 输出与 17:27 轮逐字一致 | `Connected to move_base nav2 server` → 同微秒 `No frontiers found` |
| ② **朴素口径有前沿** | 若用「未知格 ∧ 4 邻有自由格」直数 | `/global_costmap/costmap`：**434 个前沿格**，185 簇，top10 = [15,10,10,10,9,9,…]（≥10 格的有 3 簇） |
| ③ **逐字复刻 explore 判定链** | 复刻转换表 + `nearestCell` + 下降 BFS + `min_frontier_size` | **BFS 可达 18 格、前沿簇 1 个、过滤后 0 簇** → 与 explore 实际输出一致 |
| ④ 自由区被切碎 | 4 邻连通域分解（同 explore 可穿越口径） | 自由格 2163，**连通域 55 个**，46 个 ≤20 格；**机器人所在格值 = 99（内切膨胀），不属于任何自由连通域** |
| ⑤ 碎片成因 = 自车回波 | 回波投到 `base_link` 系，用车体矩形判定 | **128 / 406 束落在车体矩形内**；<0.5 m 的 129 束中 **126 束在车体内**，最近距车心 **0.09 m**；角段 259°~359° |

**⑤ 的几何判读**：短距回波集中在 259°~359°，正是「从 LD06 装点 (0.275, 0.29) 指向车体中心 (0,0)」
的方向（车尾=270°、车右=0°，该扇区覆盖车尾—右侧）。129 束短距回波中 126 束落点在 ±0.40/±0.30 的车体矩形内，
最近距车心 0.09 m——机器人中心附近不可能有外部物体。

**排除项**（逐条已核，避免重复排查）：

| 候选 | 结论 | 依据 |
|:---|:---|:---|
| 取值转换表错（`-1` 未映到 255） | ❌ 排除 | `init_translation_table()`：`[0]=0`、`[99]=253`、`[100]=254`、`[255]=255`，逐字核对 |
| `track_unknown_space: false` | ❌ 排除 | `nav2_params_ld06.yaml:291` 在 `global_costmap:`（281）段内 = `true` |
| 拿到旧快照 | ❌ 排除 | explore 订阅后 ~1 s 收首帧，符合 volatile 订阅 transient_local 发布者的正常首帧延迟 |
| 时序过早（地图还没建开） | ❌ 排除 | 60 s 后复测：地图更大（161×132 → 161×161），自由区反而更碎 |
| `inflation 0.30 < inscribed 0.34` 的 ERROR | ❌ 无关 | 11-08 已记录为已知副作用（[11-08 E4](2026-11-08_oldcar_s1_static_bringup.md)） |

---

## 四、判定链复刻（把第三方节点的判据拿回自己手里）

复刻依据（N97 `~/Lin_workspace/explore_ws/src/m-explore-ros2/explore/`，clone `326cf8a`）：

| 环节 | 源码位置 | 语义 |
|:---|:---|:---|
| 值转换 | `src/costmap_client.cpp:260-280` | OccupancyGrid → costmap char（`[255]=255` = NO_INFORMATION） |
| BFS 起点 | `src/frontier_search.cpp:55` | `nearestCell(clear, robot_pos, FREE_SPACE)`，nhood8 全图搜 |
| BFS 展开 | `src/frontier_search.cpp:71` | `map_[nbr] <= map_[idx]` **下降搜索** → 只能穿越同为 free 的格 |
| 前沿定义 | `src/frontier_search.cpp:177` | `map_[idx] == NO_INFORMATION` 且 4 邻有 `FREE_SPACE` |
| 尺寸过滤 | `src/frontier_search.cpp:79` | `size * resolution >= min_frontier_size`（0.5 m ⇒ 10 格） |

复刻输出（同一帧 costmap，17:58:04）：

```text
char 分布: free=2102 inscribed=4464 lethal=366 noinfo=18989
机器人格=(67,12) char值=253
nearestCell: 找到 free clear=(64,10) 搜索访问 29 格
BFS 可达格数 = 18（其中 free = 18）
通过 min_frontier_size 前的簇数 = 1 → 过滤后 0 簇
```

**关键认知**：`map_[nbr] <= map_[idx]` 这条下降搜索意味着 **explore 只能沿 free 格行走**，
膨胀格（1~253）一律不可穿越。因此「自由区是否连通」是 explore 可用性的**独立指标**，
与「地图里有没有未知格」同等重要。

---

## 五、与 11-08 旧几何轮的对照（推断，未复测）

| 项 | 11-08（旧） | 11-08（本轮） |
|:---|:---|:---|
| LD06 静态 TF | x=y=0、z=0.18、yaw=0 | x=0.275、y=0.29、z=0.04、yaw=−90° |
| 光学中心离地 | ≈0.30 m | **0.16 m**（比低框架平面只高 6 cm） |
| explore 结果 | 发出 7 个目标 | 零前沿 |

**推断**：0.30 m 高于车体，扫描面 360° 通畅；0.16 m 落在车体内部/贴边，被自身结构挡掉约 1/3。
该推断**未直接复测**（未做"抬高雷达再跑"的对照实验），列为待验证项。

---

## 六、方法模板（可复用操作卡）

**① 「第三方节点判定为否」的分层定位法**（本例：explore 说没有前沿）

1. **症状复现**：确认现象可稳定重现，记下时间戳级别的指纹（本例 = 同微秒 `Connected` + `No frontiers found`）。
2. **朴素口径反证**：用最直白的定义（本例：未知 ∧ 4 邻自由）直数一遍。若为 0 → 结论与节点一致，去查数据；
   **若 > 0 → 差异在判据，不在数据**。
3. **逐字复刻上游算法**：读源码，把转换表/搜索方式/过滤阈值逐行复刻到脚本里，在**同一帧数据**上重放。
   复刻输出与节点一致 ⇒ 判定链钉死；不一致 ⇒ 差异在采样时刻或输入快照。
4. 复刻脚本保留在 raw_data 档内，后续同型问题直接改参数复用。

**② 「空间被切碎」诊断法**（规划/探索类问题的通用指标）

1. 对目标层（costmap / map）做**自由格 4 邻连通域分解**，输出：连通域个数、top N 尺寸、
   **机器人所在格的取值与所属连通域编号**。
2. 判据：机器人格不是 free、或所属连通域 ≤20 格 ⇒ 空间已被膨胀/障碍切成碎片，问题在上游感知或膨胀参数。
3. 与「未知格数/前沿格数」一起看：**有未知格 ≠ 有可用前沿**。

**③ 回波归属判定法**（区分"自车结构"与"真实近距障碍"）

1. 取一帧 `/scan`，按静态 TF 把每个波束端点投到 `base_link`。
2. 用车体矩形（物理半长/半宽，另加 buffer）判定：**落点在矩形内 ⇒ 必然是自车结构**。
3. 交叉核对角段：若短距回波的角段中心正好指向「装点→车心」方向，则归属确认。
4. 同时统计比例：本例 128/406（31%）——超过 10% 即应视为安装问题，而非偶发噪点。

**④ 无 tty / `setsid` 启动的 ROS 进程收尾**

1. `kill -INT <ros2 launch PID>` 在无 tty 环境下可能 **rc=0 但进程不退出**（本轮实测）。
2. `kill -TERM <ros2 launch PID>` 能杀包装进程，但**子节点成孤儿继续跑**（ros2-ops §10 同源）。
3. 正确收尾：先 `ps -eo pid,cmd` 抓全部子 PID → 逐个 `kill -INT` → 复验 `ps` 为空。
4. `ros2 node list` 残留 ≠ 进程残留：先 `ros2 daemon stop` 再 `ros2 node list --no-daemon` 复核。

**⑤ 条件偏差记录**：换执行方式（人手 → AI 代执行）时，先核前置条件是否与基线一致。
本轮治理器仍是 `powersave`（AI 无 sudo 密码），与上一轮不可完全类比——**记录进原始数据档，不静默忽略**。

---

## 七、经验点层次标注

| 编号 | 经验点 | 建议去向 |
|:---|:---|:---|
| E1 | 「第三方节点判否」时先复刻其判据，再谈它的对错——复刻一致即钉死判定链，避免在参数层空转 | **draft 层**（analysis-methods 新增主题） |
| E2 | explore_lite 前沿判据 = 「只能穿越 free 的下降 BFS」+ `min_frontier_size`；**有未知格 ≠ 有可用前沿** | **draft 层**，后续可抽入 ros2-ops §12（感知/可观测性判据区） |
| E3 | 自车回波判定：`/scan` 端点投 `base_link` + 车体矩形判定；比例 >10% 视为安装问题 | **draft 层**；成熟后入 sensor-mount 的安装验收卡 |
| E4 | 自由区连通域是规划/探索可用性的独立指标（机器人所在格的连通域尺寸） | **draft 层** |
| E5 | 无 tty / `setsid` 启的 ROS 栈收尾必须逐子 PID；`ros2 node list` 残留先排 daemon 缓存 | **draft 层**，与 ros2-ops §10 现有条目互补（不直接改写规则层） |
| E6 | 换执行方式（用户手工 → AI 代执行）须先核前置条件，偏差如实入原始数据档 | **事件层留存**（本文 §六-⑤） |
| E7 | 感知问题的归因顺序：先分「物理安装」与「算法/参数」，再谈修法；本例物理在前 | **事件层留存**，与 ros2-ops §7.1「物理边界 vs 工程缺陷」同型 |

---

## 八、遗留与回指

- **软件屏蔽方案待定夺**（不改雷达安装位置为前提）：去向 [s1-readiness-gap G24](../old-car/s1-readiness-gap.md)、[pending-tasks](../pending-tasks.md)。
- **11-08 旧几何轮的「规划全败未定因」**仍未处置（那轮 explore 发得出目标，本轮发不出，说明两轮卡在不同环节）——[11-08 §4.1](2026-11-08_oldcar_s1_static_bringup.md)。
- **物理整改（抬高/外移雷达）**未采纳为当前路线，但未否决；"抬高 10~15 cm 对照重跑"仍是验证本推断最便宜的手段。
