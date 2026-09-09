# 数据分析方法经验长文档（draft 层）

> 定位：**规范抽取前的经验沉淀层**——retrospect 事件里冒出的方法经验，先在本地以长文档形态完整展开
> （背景/反例/示例/验证），**不直接写入规范**；同一主题的经验复用 2+ 次、形态成熟后，按「抽取状态表」
> 抽成短条款入对应规范（本域候选 = [ros2-ops.md §5](ros2-ops.md) bag 分析 / §7 排障纪律 / §9 漏录决策），
> 抽取后本文件相应条目替换为状态回指，不重复维护。
> 依据：2026-09-04 会话定——直接往 ops 写入单事件新经验不合适（ops = 稳定规范层）；长文档先沉淀，
> 定期盘点时再集中抽取（散落回顾 → 集中化的中间层）。
> 关联：[standards.md §1.1](standards.md)（单一事实来源：事件叙事权威在 retrospect/，本层 = 方法形态）、
> [retrospect/README.md](retrospect/README.md)（事件索引）

---

## 主题 A：bag / 点云 / scan 数据分析操作方法

> 来源事件：[2026-09-04 低物盲区断点复盘](retrospect/2026-09-04_lowobstacle_breakpoint.md)（§七 规则原文 + §十 证据链）。
> 此前同主题教训（ros2-ops §5 已有条款，不重复）：08-06 第三方库坑、08-12 索引采样漏运动段。
> 候选去向：ros2-ops §5（成熟后）。

### A1 帧间/逐 bin diff：禁用 `max(generator)`

- **规则**：序列含 nan（inf−inf 产生）时 `max()` 保留首个 nan → 阈值比较恒 False，**静默漏报**
- **反例**：`d = max(max(a) - max(b) ...)` 写法在一次事件中导致 0.3m 矮物帧间差全被吞掉，肉眼无报错
- **正确做法**：显式 list 收集 + `isfinite` 跳过双 nan/inf；inf↔finite 切换显式计为大变化
- **验证**：复盘 §五 决定性帧对照（4 组无人静止帧同帧 scan 5.42~5.43m vs points 矮簇 9~112 点）

### A2 PointCloud2 解析：按 field 提取，不整体 reshape

- **规则**：point_step 含非 float32 字段（ring=uint16、time=float32 等）时整体 numpy view 直接炸类型错
- **正确做法**：`np.frombuffer(uint8).reshape(n, point_step)` → 按 `msg.fields` 的 offset/datatype 逐 field 切片 view；
  注意 datatype 值映射要用 `np.dtype(...)` **实例**，用 np 标量类型类会取到 getset_descriptor（本事件实测踩坑两次）
- **验证**：复盘所有分析脚本（`bags/analysis/lowobstacle_0904/*.py`）

### A3 LaserScan 方位符号：先验校验，勿等现场习惯反推

- **规则**：ROS 约定 scan 正角 = 左（y>0）；动手前用同帧 points 的 y 符号/atan2 校验方位约定
- **反例**：本事件整批解读把负角当「车体左侧/左前」报告，实为右侧——用户一句「我一般从右侧经过」触发
  全量反转（复盘 §二）
- **正确做法**：`np.sign(y)`/`atan2(y,x)` 与 scan angle_min 对齐一次，写进脚本头注释

### A4 驻留聚类：用距离跳变断段，不用角带平均

- **规则**：1° 角带平均会把相邻驻留混成假 avg（平均距离掩盖真实边界）
- **正确做法**：0.1m 距离档跳变 >0.3m 断段 → 得到干净稳定事件表
- **事件表判据参数**（09-04 遮挡事件表）：带基准 = 带内全程最大距离（开阔参照）；
  收窄 ≥0.5m 且驻留 ≥0.8s（容缺 ≤0.3s）记为事件行（[09-04 复盘](retrospect/2026-09-04_lowobstacle_breakpoint.md) §三 scan_highres.py 判据）
- **验证**：复盘「精华总览」稳定驻留表（全景表 vs 初版 1° 带表差异）

### A5 环编号 → 仰角：实测标定，不读 db 表推断

- **规则**：VLP16db.yaml 的 laser_id 是**交织发射序**（-15/+1/-13/+3…°）；pointcloud `ring` 字段是 calibration.cpp
  按仰角升序**重映射**后的索引（ring 0=-15° … ring 7=-1°、ring 8=+1° … ring 15=+15°）。要钉死某条 scan 用了
  哪根环，用静止开阔段点云按 ring 聚合 `asin(z/R)` 中位角实测（[ring_angle_table.py](../bags/analysis/lowobstacle_0904/ring_angle_table.py)）
- **验证**：/scan 现行光束 = ring 8 = +1.0° 上仰（源码链 + 实测仰角表双钉死，复盘 §10.1/10.2）；
  「偶数环向下」说的是发射序，不是 ring 序——曾导致方向误判
- **泛化（09-09 盘点）**：A5 即「机制核查双钉法」特例——钉死任何"源码声明 vs 运行行为"差异需
  **两条独立证据链交叉闭环**：源码链（declare/实现/映射处）+ 同 bag 实测（行为侧独立观测）；
  只一条链 = 未钉死（A5 例：calibration.cpp 重映射源码 + 静止段点云按 ring 聚合实测仰角表）

### A6 读消息前先 `ros2 interface show` 定字段名

- **规则**：写 reader 前对消息类型 `ros2 interface show <type>` 一锤定音字段名——省掉运行时
  AttributeError 与改判据重跑
- **反例**：`CostmapMetaData` 字段是 `metadata`（写 `meta` 崩）；`VoxelGrid` 是 `resolutions`
  （Vector3，不是 `resolution`），data 是 uint32[]——各踩一次（[costmap_experiment](minimal-loop2/costmap_experiment.md) §六-5）

## 主题 B：复盘遗留对账收口方法

> 来源事件：复盘 §六 五项收口（§10.5 W3 对账 + §六 补注 两项用户对账）+ [09-03 closing 更新记录](retrospect/2026-09-03_costmap_far_refresh_closed.md)。
> 候选去向：ros2-ops §5/§9 邻域（对账口径）或沉淀后再定。

### B1 数据缺口：先声明可查证范围，再分治候选解释

- **规则**：目标问题所需话题未录（如 costmap 系列）→ 先按 bag metadata 声明「不可直接查证」（这正是 ros2-ops §9
  判重录的缺口证据），**不停摆**：用已有数据逐条裁定**可裁的候选解释**，不可裁的标注「无数据」+ 维持既定归因；
  推断与实测在结论里分开标
- **案例**：W3 对账——254/100 不可直接读 → /scan 层裁定候选 a（低物）**排除**（障碍贴车 0.50~0.85m ⇒ 高 ≥~0.8m），
  b/c 无数据标注不裁（复盘 §10.5）

### B2 口述/旧记录 vs bag 不一致：量化呈现 + 用户四型收口

- **规则**：先给量化证据差（例：「bag 无 4.5~5m 稳定驻留，最远 = 4.2m 短停 1.4s」），让用户按现场记忆选收口型：
  ① 记不清按 bag 为准 ② 确测过但不在 bag（两证并存标注）③ 两证指同一事件 ④ 跳过；
  裁定回写状态行 + 表下补注；无法统一时**不覆盖任何一方**
- **案例**：§六-1（5m 档 = 4.2m 短停同一事件）、§六-5（矮物同一物全程在场）

### B3 文档假设用实测钉死，修正回写源文档

- **规则**：引用既有文档的数值/表述凡可实测（障碍高、光束角、环序、时间窗），先测后引；证伪处回写源文档留痕
- **案例**：「0.6m+ 高箱」→ 顶面 z 实测反推 ≈1.0m（[box_top_height.py](../bags/analysis/lowobstacle_0904/box_top_height.py)）；
  断点结论从「物理盲区」细化为「转换层单环」（复盘 §10.3 + closing 更新记录双向留痕）

## 主题 C：会话/记录日期实证核验

> 来源事件：[09-09 双仓闭环复盘](retrospect/2026-09-09_datefix_linkfix_dual_repo.md)（低物链工作日期归属争议 → 09-07 零活动实证，文档误标 09-07 全批修正）。
> 候选去向：成熟后并入 doc-engineering（证据核验类）或盘点时再定。

### C1 session transcript 按北京日统计定真实工作日

- 证据源：Claude session transcripts `~/.claude/projects/*/*.jsonl`（每行 `timestamp` 为 **UTC**，须 +8h 换算北京时间）
- 做法：按北京日分组统计消息量——**零活动日 = 铁证**（案例：09-07 无任何消息 vs 09-08 10:02~21:35 密集活动）
- 交叉：`git log --format='%ai %h %s'` 对照 commit 实际时间 vs 文档内日期，可判定"文档日期笔误"而非"当日没做工作"

### C2 bag metadata 时间戳交叉验证

- `metadata.yaml` 的 `starting_time.nanoseconds_since_epoch` → 除 1e9 → epoch 转北京时间
  （案例：1788833996504237069 = 09-08 10:19:56 +08，为"盒子 bag 录制于 09-08"落物理物证）

### C3 实证修正的应用判据

- 文档日期与提交/会话实证不符 → 以实证为准修正：git 资产走 `git mv` 保史 + sed + 引用方同步；
  **未追踪磁盘资产**（bag 目录、raw_data）单独 mv + 内层路径 sed（方法卡②见事件篇）

---

## 主题 D：VM 回放 / 对照实验法（无真车复现）

> 来源事件：09-05 修法 B VM 验收（抽帧重发定型）+ 09-08 A/B（反转重放）+ 08-15 kiss 漂移（双录对照）
> + 08-11 帧率修复（处理时长判定）+ 08-18 Laser_map 排障（插桩）+ 08-13 分层建图（IoU 验收）。
> 候选去向：成熟子卡盘点后抽 ros2-ops §7（排障/验证纪律）或独立小节。

### D1 bag 抽帧改 stamp 重发卡（VM 单机复现 costmap 行为）

- **适用**：costmap/感知行为要在 VM 复现又无真车——砍掉"时间轴回放"：sim 轴根源 = 时间轴，
  wall 时间 + 静态 tf 把变量压到最少（方向 B 取舍，[09-05 篇 §2.2](retrospect/2026-09-05_lowobstacle_fixB_vm_acceptance.md)）
- ① 静态 tf：odom→base_link 恒等 + base_link→velodyne (0,0,0.655)，wall 发布
- ② costmap：standalone nav2_costmap_2d（--params-file 目标配置）+ `use_sim_time: False`
- ③ 抽帧：rosbag2_py 读决定性时间窗 → 等间隔采样 N 帧（points+scan 同窗成对）
- ④ 重发：`header.stamp` 改当下 wall time；best_effort QoS；循环发布
- ⑤ 读取：订阅 `costmap_raw`（nav2_msgs/Costmap），lethal = data 原值 254 → 世界坐标
- ⑥ 判据：预测方位/距离容差内出现 254；同帧旧源数据在该方位开阔 → 排除旧源贡献
- **已知坑勿绕**：sim-time 回放 + costmap 点云观察源 = Nav2 known trouble（绕行 = 重启排障，
  09-05 E2，ros2-ops §7）

### D2 反转整包重放 A/B 卡（mark→clear 竞争动态因果链）

- **适用**：无真车复现"随距离演化的 mark→clear 竞争"行为差异（配置 A/B、近距丢黑、清除链问题）——
  承接 D1 的动态变体（[09-08 A/B §七](retrospect/2026-09-08_lowobstacle_fixB_ab_acceptance.md)）
- ① 录单方向完整渐变场景：静止车 + 已知尺寸目标物沿车头轴逐档移动（每档停 3~5s），覆盖全盲→首线→多线
- ② 先离线定几何律（见 E5），**不拿现场目测当定论**
- ③ 定 mark 相与 clear 相素材：同一条记录内选停驻段（mark）与盲区段（clear，天然无目标点）
- ④ 整包反转重放：points/scan 帧逆序发（stamp 改 wall now；按需 2× 加速），A/B 各跑一遍；
  顺带得到"衰减 onset 与盲区边界时间对齐"的因果自证
- ⑤ 串行 + 残留守卫：先 A 后 B 绝不并发；每轮前 `pgrep` 守卫 exit 1、轮后按命令行特征 pkill + 复验
- ⑥ 区域判据：目标物可达 x 区间 + |y| 半宽圈定 ROI 统计 raw 254 格数轨迹；OLD 终态趋 0 vs
  NEW 终态保持 >0；背景（旁侧物/墙）同轨迹做一致性检查
- **A/B 首帧字节一致性** = 双发布者污染信号，数据作废（09-08 ringlaw E7）

### D3 双录对照隔离法：短直行 vs 长绕圈同管线

- **用途**：隔离"录制内容"与"链路/环境"谁在贡献异常（[08-15 kiss 漂移](retrospect/2026-08-15_kiss_drift_170058.md) 已实践两轮）
- 做法：同一条处理管线分别跑短直行段与长绕圈段——差异只出现在长录 = 内容问题（旋转段配准退化），
  两录同病 = 链路/环境问题
- 08-15 例：短录干净 vs 长绕 163° 漂移 → 漂移归因旋转/空窗内容而非链路

### D4 处理时长 p50 ≈ 2× 输入周期 = 规律性隔帧丢帧

- 判据：下游 p50 恰为输入周期 2 倍（如 /kiss/frame p50=202ms vs points dt 恒 101ms）=
  **规律性隔帧丢帧**（单帧处理 ~2 周期，逐帧排队），非偶发卡顿 → CPU/算力瓶颈
  （[08-11 帧率修复](retrospect/2026-08-11_kiss_frame_rate_fix.md) §2；p50 ≈ 2× 后直查 governor/算力）
- 偶发卡顿表现为 p50 略升 + 长尾，不呈精确倍数

### D5 源码插桩定位执行侧（注入→定位→还原三阶段）

- **适用**：配置/参数看似没生效、要钉"执行侧到底跑到哪"（[08-18 Laser_map](retrospect/2026-08-18_fastlio_laser_map_debug.md)）
- ① 注入：源码头加 `RCLCPP_INFO("[diag] …状态量")` → 重编译（--packages-select + symlink-install）
- ② 定位：按 diag 输出裁定事实（例：en=1 = 参数已加载 / 每秒触发 = timer 正常 / 计数增长 = 主循环执行中
  → 执行侧全通，问题只剩发布→接收或验证手段）
- ③ 还原：删插桩 → 重编译 → 重启复验 grep 日志**不再出现 [diag]** → 原验证姿势复跑
- 与「逐段隔离」（参数 param get → 执行 diag → 发布 echo）配合：每段一个验证动作，问题在哪段一目了然

### D6 多段点云合并：IoU 一致性验收门槛

- **规则**：多段合并前先对齐（旋转粗搜 ±4° 步长 0.5° + FFT 互相关平移精搜，重叠区 IoU 最大），
  **IoU ≥0.30 才合段**（[08-13 分层建图](retrospect/2026-08-13_layer_map_3d2d.md) §一/§二）：
  同系 seg1+seg2 IoU 0.47（最佳偏移 = 0）；seg3 旋转 1°+平移后仍仅 0.20 < 0.30 = 内容不一致 → 剔除
- 不靠目测判"像不像同一场地"——数值门槛防拖花地图

## 主题 E：点云场景测量与事件定位法

> 来源事件：09-06 撞箱复盘（找箱/定点窗口/几何律）+ 09-08 ringlaw（共享背景/数值优先/脚本复用）
> + 09-08 secondfail（单帧事件定位）+ 09-08 pivot（物理边界分离）+ w2-operation D7.2（到达误差）。
> 候选去向：成熟子条盘点后抽 ros2-ops §5/§7 或对应专题。

### E1 点云找箱法（已知障碍、未知位置）

- ① 找箱（velodyne 系）：筛选高度带（离地 0.3~0.4m 平顶）→ 0.1m 密度簇 → **平顶 z 固定范围即箱体**
- ② 定位（odom 系）：车初始位姿 + 箱相对方位/距离 → 箱子世界坐标（静止段可靠，动段需 tf 全链路）
- ③ 验证 source 分层：箱子世界坐标 → local（odom 系）/global（map 系）costmap_raw 各自取 ±0.7m
  窗口值直方图
- 可复用任意"已知障碍未知位置"（[09-06 §三](retrospect/2026-09-06_lowobstacle_fixB_crashbox.md)；
  实现 find_box_in_points.py，09-08 起为后续脚本母版）

### E2 共享背景识别法（免人工辨认背景/被测物）

- 同场景两包（不同被测物摆位）"远带/侧向物簇逐格等值" = 背景，差异带 = 被测物贡献
  （[09-08 ringlaw E8](retrospect/2026-09-08_lowobstacle_ringlaw_cleandata.md)）
- 兼作纯净数据判据：背景稳定 = 两包背景簇逐格等值；主箱签名 = 预期距离处出现且仅出现被测物的环数组合

### E3 定点窗口逐帧计数（判局部事件，禁全图 diff）

- **规则**：判某物"有没有/何时变"用固定 ROI（箱区 ±0.7m 窗口）逐帧统计 254 格数 → 轨迹 vs 车距；
  **全图 diff 被环境变化淹没**（09-06 8.2：手动推车段人腿 mark + 箱格移动 → 全图 254 上涨淹没箱格信号）
- 输出形态：远距稳定值 → 逼近逐帧降（1.9m 起 15→11→6→0）→ 归零距离（~1.4m），onset/归零与
  几何盲区预测对齐即因果实锤

### E4 costmap 单帧事件定位卡（整层清空 vs 渐次衰减）

- 时间线粗后细：① 速度/goal/plan 全览锁定运动段 → ② 统一 map 系几何 → ③ 地图上下文
  → ④ ROI 定点帧级计数 → ⑤ 同窗其他话题交叉（[09-08 secondfail](retrospect/2026-09-08_lowobstacle_secondfail_clearevent.md) §五）
- **单帧整层清空（ClearEntirely 特征）vs 渐次衰减**判据：单帧全层归零（伴随目标格 −52%）= 清除事件；
  逐帧降 = 观测衰减。**plan 空窗 + 清除帧与首 plan 同刻** = planner-fail → clear → replan 恢复链指纹
  （无需 BT 日志可先钉时间窗）

### E5 几何律标定卡 + 视锥临界公式

- 离线定几何律：读本机 VLP16db.yaml 得 ring 角 → 目标高度 + 雷达光学中心高 → 每 ring 可见距窗与
  临界距 **d = (z光 − z顶) / tanθ**（最下环 θ = −15°，0.35m 箱临界 1.59m 实测定稿，
  数值唯一事实源 = [3d 感知调研 §三B](surveys/3d-lidar-2d-navigation-survey.md)）
- 验证：逐帧高度谱反推命中 ring（h = H − d·tanθ），理论 ↔ 实测偏差 <1cm 才算对账
  （[09-08 ringlaw E9](retrospect/2026-09-08_lowobstacle_ringlaw_cleandata.md)）；
  未对账的"理论正确"不算数

### E6 感知问题先分「物理边界 vs 工程缺陷」

- 边界（几何/能量/信息论不可参数化）与缺陷（可修）**分开列证据、各自实锤**后再判收手
  （[09-08 pivot §五-1](retrospect/2026-09-08_lowobstacle_pivot_decision.md)）——避免在几何极限上无限打补丁；
  同一现象可双因（盲区 1.59m = 物理边界；"第二次失效" = 工程 clear 冲突），修复收益受边界封顶

### E7 数值点云分析优先，勿读渲染图

- 高度谱/簇直方等数值分析优先；像素级读图非 AI 擅长且不可靠，渲染仅作人工浏览辅助
  （[09-08 ringlaw E5](retrospect/2026-09-08_lowobstacle_ringlaw_cleandata.md)）
- 直接读渲染图下结论 = 复现"看着像"风险；数值与渲染冲突时以数值为准

### E8 复用成熟脚本参数化，不每次重写

- 写分析脚本前先借鉴既有成熟脚本（09-06 `find_box_in_points`/`render_frames` 为后续母版）
  参数化复用——每次重写正确率差且低效（[09-08 ringlaw E3](retrospect/2026-09-08_lowobstacle_ringlaw_cleandata.md)）

### E9 Nav2 到达误差量化法

- 停稳判据：`/cmd_vel_smoothed` 线/角速度均 <0.01 持续 ≥2s；停稳时实际位姿取最近一帧
  `/amcl_pose`（**AMCL 静止不发布**，须前后取最近帧）；误差 = 2D 欧氏距离 + 归一化航向差
  （[w2-operation D7.2](minimal-loop/w2-operation.md)；权威脚本 `bags/analysis/analyze_nav2_goal_error.py`）

---

## 抽取状态跟踪表

| 条款 | 状态 | 候选去向 | 成熟条件（待满足） |
|:--|:--|:--|:--|
| A1 diff nan | 沉淀 | ros2-ops §5 | 复用 1+ 次或盘点抽取 |
| A2 PointCloud2 解析 | 沉淀 | ros2-ops §5 | 同上 |
| A3 方位符号 | 沉淀 | ros2-ops §5 | 同上 |
| A4 断段判据 | 沉淀 | ros2-ops §5 | 同上 |
| A5 ring 实测 | 沉淀 | ros2-ops §5 | 同上 |
| B1 可查证范围分治 | 沉淀 | ros2-ops §5/§9 邻域 | 复盘收口流程定型后再评 |
| B2 四型收口 | 沉淀 | ros2-ops §5/§9 邻域 | 同上 |
| B3 实测钉文档 | 沉淀 | ros2-ops §5/§9 邻域 | 同上 |
| C1 transcript 北京日统计 | 沉淀 | doc-engineering（证据核验类） | 09-10 盘点复核 |
| C2 bag metadata 交叉验证 | 沉淀 | 同上 | 同上 |
| C3 实证修正应用判据 | 沉淀 | 同上 | 同上 |
| D1 抽帧改 stamp 重发卡 | 沉淀 | ros2-ops §7 | 复用 2+ 次或盘点抽取 |
| D2 反转整包 A/B 卡 | 沉淀 | 同上 | 同上 |
| D3 双录对照隔离 | 沉淀 | 同上 | 同上 |
| D4 处理时长 2× 判定 | 沉淀 | 同上 | 同上 |
| D5 源码插桩三阶段 | 沉淀 | 同上 | 同上 |
| D6 IoU 合并门槛 | 沉淀 | ros2-ops §5/§7 | 同上 |
| E1 点云找箱法 | 沉淀 | ros2-ops §5/§7 或专题 | 同上 |
| E2 共享背景识别 | 沉淀 | ros2-ops §5 | 同上 |
| E3 定点窗口逐帧 | 沉淀 | ros2-ops §5 | 同上 |
| E4 单帧事件定位卡 | 沉淀 | ros2-ops §11 邻域 | 同上 |
| E5 几何律标定卡 | 沉淀 | 数值留 survey §三B，卡入专题 | 同上 |
| E6 物理边界分离 | 沉淀 | ros2-ops §7 | 同上 |
| E7 数值优先勿读图 | 沉淀 | ros2-ops §5/§7 | 同上 |
| E8 脚本母版复用 | 沉淀 | ros2-ops §7 | 同上 |
| E9 到达误差量化 | 沉淀 | w2/startup 验证基线位 | 同上 |

> 盘点节奏：**方案 A 已定稿**（09-04，阶段收尾即盘点，首个 = 09-10 A1 收口；分层架构与决策全文见
> [retrospect/2026-09-04_experience-layer-decision.md](retrospect/2026-09-04_experience-layer-decision.md)）——
> 本文件为方法 draft 层唯一载体：新增经验**先落此完整展开**，不直接进规范；成熟子集经盘点抽入规范后回指。
