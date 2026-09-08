# 09-08 近距丢黑块修复（修法 B·global 独立层）VM A/B 验收 PASS + ring 几何律实测定稿

> 日期：2026-09-08
> 任务：近距丢黑块修复的纯净数据源重录 + VM A/B 对照验收（config 修复已在 09-07 前完成，见下）
> 状态：✅ A/B 验收 PASS（OLD 箱区 254 25→2 归零复现 / NEW 24→117 稳定保留）；留档完成
> 关联：前篇 [2026-09-06_lowobstacle_fixB_crashbox.md](2026-09-06_lowobstacle_fixB_crashbox.md)（近距丢黑块发现与取证）、
>       [2026-09-05_lowobstacle_fixB_vm_acceptance.md](2026-09-05_lowobstacle_fixB_vm_acceptance.md)（修法 B 首版 VM PASS + 抽帧重发法模板）、
>       [07-handover.md](../07-handover.md)（交接状态）、[pending-tasks.md](../pending-tasks.md)（待办）
> 证据落位：3 个纯净 bag 于 N97 录制、VM 副本 `bags/raw/box_static_20260908_1019` / `box_near_20260908_1020` /
>       `box_TrendsParallel_20260908_1056`；分析脚本 `bags/analysis/box_lowband_20260908/`（12 件，含 A/B 验证台）
> 方法模板：见 §七（反转重放 A/B 操作卡）；经验点清单：见 §八

---

## 结论先行

1. **修复有效**（VM A/B）：同一份"箱逐渐远离"bag 反转重放复现 N97 接近因果链——旧配置（单层两源，
   scan+low 同层清除）箱区 254 **25 → 2**（衰减 onset 与几何盲区边界时间精确对齐）；新配置（low 拆
   独立 mark-only 层）**24 → 117 稳定保留**，scan 清除射线不再能抹掉低带黑块。
2. **ring 几何律实测定稿**：VLP-16 共 8 条向下 ring（-1/-3/-5/-7/-9/-11/-13/-15°）；0.35m 矮箱在
   光学中心高 0.775m 下，最近命中 ring = -15°，**临界消失距 = 1.59m**（传感器轴；车体前缘参照 ≈1.2m）。
   数据逐帧高度谱与理论偏差 <1cm；用户现场观察（150cm 处 2~3 线 / 120cm 扫不到）与模型自洽。
3. **盲区是本底几何，不是 bug**：箱 <1.59m（0.35m 箱）/ 各高度箱有各自的临界距；修复保的是
   "接近过程中已见到的黑格不被后续清除"，不解决"从未见到"的固有盲区（见 §六遗留）。

---

## 一、背景与问题链

| 日期 | 事件 | 结论/产物 |
|:---|:---|:---|
| 09-06 | N97 实车取证：导航撞 0.35m 矮箱；低带源近距丢箱 → scan 同层清除 → 254 归零 → 规划盲 | [crashbox retrospect](2026-09-06_lowobstacle_fixB_crashbox.md) |
| 09-06~07 | config 修复（工作区 `nav2_params_low.yaml`）：`velodyne_low` 拆出为独立 `obstacle_low_layer`，mark-only（clearing: False）；主 `obstacle_layer` 只留 scan | 工作区未提交改动 |
| 09-06 | VM A/B 初试（102944 手动推车接近窗 [81,108]s）失败：手动推车段人腿在低带持续 mark + 车动箱格移动，全图 254 上涨淹没箱格信号，old 版未现归零 | 教训 → 用户提议纯净重录 |
| 09-08 | 用户 N97 重录 3 个纯净 bag（无人介入、车静止、正前不同距离箱体 + 动态远离过程） | 本日数据源 |
| 09-08 | ring 几何律标定 + 反转重放 A/B | 本文 ✅ |

---

## 二、纯净数据源（3 bag，2026-09-08 录制）

录制命令（N97，仅雷达栈，`ros2 launch r2_sensors velodyne.launch.py`；话题
`/velodyne_points /scan /tf_static`）：

```bash
cd ~/Lin_workspace/r2_integration/bags
ros2 bag record -o box_static_$(date +%Y%m%d_%H%M)  /velodyne_points /scan /tf_static   # 主数据
ros2 bag record -o box_near_$(date +%Y%m%d_%H%M)    /velodyne_points /scan /tf_static   # 盲区旁证
ros2 bag record -o box_TrendsParallel_$(date +%Y%m%d_%H%M) /velodyne_points /scan /tf_static  # 动态远离
```

| bag（VM 副本） | dur | 帧数 | 场景 | 数据角色 |
|:---|:---|:---|:---|:---|
| box_static_20260908_1019 | 21.5s | points 213 / scan 214 | 车静止，35cm 立方箱面 1.95~2.3m（3 ring 命中） | 初筛/簇定位 |
| box_near_20260908_1020 | 15.7s | 156/156 | 同一箱移至近距（实测 ≈0 命中） | **盲区旁证**（近距确实扫不到） |
| box_TrendsParallel_20260908_1056 | 85.9s | 853/853 | 箱沿车头轴从 ~1.0m 逐档远离至 2.11m 静止（末 8s 停驻） | **A/B 验收主数据** |

- 布局：35cm 立方箱正前方（实测 az +1.3~1.5°、横向宽 ~0.37m，在 ±10° 内）；旁侧 ~13~15° 有对照箱
  （顶高 ~0.5m）；~4.9m 处背景（两包均一致）。
- 移箱人站箱后偏出轴线（±16° 锥外低带数据与背景一致，未见人腿污染）。
- tf_static：`base_link→velodyne (0,0,0.655)`（两包实测一致，与 VM 测试台硬编码同值）。
- VM 传包：`scp -r lin@192.168.1.210:.../bag*  ~/Lin_workspace/r2_integration/bags/raw/`（2026-09-08 完成）。

---

## 三、ring 几何律（实测定稿）

### 3.1 理论（校准文件实源）

VLP-16 校准 `VLP16db.yaml`（/opt/ros/humble/share/velodyne_pointcloud/params/）16 ring 仰角：
8 条向下 = **-1/-3/-5/-7/-9/-11/-13/-15°**（id 14/12/10/8/6/4/2/0），其余向上（对 0.35m 地物不可见）。

几何：ring θ 在水平距 d 的射线高度 h = H − d·tanθ（H=0.775 雷达光学中心离地，09-06 定）。
0.35m 箱（顶 0.35、贴地）可见条件 0 ≤ h ≤ 0.35 → 每条 ring 可见距窗 **[0.425/tanθ, 0.775/tanθ]**，
**最近一条 = -15°：1.59m 处过顶消失（临界距）**。逐条：

| ring | 消失距(打顶) | 打地距 | | ring | 消失距 | 打地距 |
|:---|:---|:---|:---|:---|:---|:---|
| -15° | **1.59m** | 2.89m | | -7° | 3.46m | 6.31m |
| -13° | 1.84m | 3.36m | | -5° | 4.86m | 8.86m |
| -11° | 2.19m | 3.99m | | -3° | 8.11m | 14.8m |
| -9° | 2.68m | 4.89m | | -1° | 24.4m | 44.4m |

> 反向推论：1.59m（传感器轴）≈ 车体前缘 1.2m + 0.42 偏置；用户实测 **~120cm 扫不到 ✓**。
> 附加效应：箱顶面可被 d_top(θ) 落在箱深内（[箱面前缘, 前缘+0.35m]）的 ring 擦中 → 高度恒定 ≈ 箱顶高（0.35m 的"顶面回波"，见 3.2）。

### 3.2 数据验证（box_TrendsParallel 逐帧高度谱，`sweep_frames.py`）

箱面距离随 bag 时间演化（fwd）：盲区 0~35.5s（探测不到，0 线）→ 35.5s 起 1 线贴顶 h≈0.346 → 46s
1.66~1.71m 3 线 → 66~78s 渐移至 2.0~2.1m → **78~86s 停驻 2.10~2.11m**。

停驻位命中谱（3 ring，与理论偏差 <1cm）：

| 命中 | 理论 h(d=2.10) | 实测 h 簇 |
|:---|:---|:---|
| -15°（面下部） | 0.212 | 0.214~0.215 |
| -13°（面中部） | 0.290 | 0.290~0.296 |
| -11°（顶面擦边回波） | ~0.353（=箱顶高） | 0.351~0.355 |

用户现场佐证（"3 条线都在 0.34~0.35m" = 顶面回波组；箱中心 ≈ 2.28m ≈ face 2.10 + 半深 0.175，与其
"220~230cm"量法自洽）。**用户提示语 = 佐证，分析以点云数据为准**（本次逐帧谱先行，未用提示反推）。

### 3.3 低带映射确认

costmap odom 系低带 [0, 0.40] ↔ 实际离地高 [0.12, 0.52]（odom 地面 z=-0.12 + tf 0.655）。
箱面命中 0.215/0.295/0.353 全部 ≥0.12 ✓ 入带；仅最贴地 (<0.12) 命中被滤——mark 完整性不受影响。
box_near 包实证近距（1.0~1.7m 区）低带命中 ≈ 0：盲区本底。

---

## 四、VM A/B 验收（反转重放法）

### 4.1 设计要点

- **反转整包重放**：bag 正向 = 箱远离（1.0→2.11m）；逆序发帧 = 车接近完整因果链
  （开段停驻 2.10m mark 相 → 中段接近逐 ring 消失 → 尾段 = bag 前 35.5s 盲区帧，points 无箱点
  + scan 持续清 = clear 相）。**单一 bag 自证，无需诱导掐点源、无需真车撞箱**。
- 测试台：static tf（odom→base_link identity + 0.655 base_link→velodyne）+ standalone
  nav2_costmap_2d（rolling 8×8、res 0.05、2Hz）+ reader 记 `/costmap/costmap_raw` 254 格 → jsonl。
- 配置对照：`costmap_vm_global_old.yaml`（= git HEAD 单层双源，scan+velodyne_low 均 clearing:True）
  vs `costmap_vm_global_new.yaml`（= 工作区修复：obstacle_layer scan-only + obstacle_low_layer
  velodyne_low mark-only）。
- 卫生：**A/B 串行执行**（09-06 教训：并行/残留节点同话题双发布者污染数据）；每轮前 pgrep 残留守卫、
  轮后 pkill -f 精确清理并验证；2× 加速重放（85.9s→~43s）。

### 4.2 结果对照（箱区 x∈[1.3,2.6]·|y|<0.5 的 254 格数）

| 重放 t | 反转后阶段 | **OLD** | **NEW** |
|:---|:---|:---:|:---:|
| 0~17s | mark 相（箱静止 2.10m 3-ring） | 25 | 24→93 |
| ~22s | 接近中（箱面 ~1.7m） | 25→16 | 111 |
| ~25s | **过 1.59m 盲区边界**（(85.9−35.5)/2 ✓） | 3 | 117 |
| 26~51s | 盲区 clear 相 | **2** | **117**（稳定） |

- OLD：25→2，**衰减 onset（t≈22.5~26.5s）与几何盲区边界时间精确对齐** = N97 撞箱前"黑块消失"机制复现。
- NEW：接近全程逐格累积 24→117 后**稳定保持**，scan 射线（0.7m+ 高掠过箱顶打到远处）抹不掉低带黑块。
- 背景一致性：旁侧对照箱在两轮均持续（OLD ~80 平衡 / NEW 87→157 累积），符合各自层语义。
- 诚实备注：OLD 终态残留 2 格（区域边缘残格，非 0；主箱区 25→2 已 92% 清除，机制判定不受影响）。
- 判据达成：**NEW 终态 117 ≫ OLD 2**，近距 254 不归零修复验证 PASS。

### 4.3 复现方法（资产化）

分析/验证资产 `bags/analysis/box_lowband_20260908/`：

| 文件 | 用途 |
|:---|:---|
| cleanbag_clusters.py | 纯净 bag 低带簇定位（复用 09-06 find_box_in_points 逻辑） |
| ring_law.py | ring 几何律理论表（读本机 VLP16db.yaml） |
| sweep_frames.py + sweep_frames_out.txt | TrendsParallel 逐帧精析（x_front + 命中高度谱） |
| ring_law_out.txt / cleanbag_clusters_{static,near}_out.txt | 输出 |
| costmap_vm_global_old.yaml / _new.yaml | A/B 配置（= git HEAD vs 工作区修复） |
| vm_replay_sweep_rev.py | 反转整包重放器（2× 加速） |
| vm_run_ab_sweep.sh | A/B 编排（守卫 + 生命周期 + 清理） |
| vm_read_marks.py | 254 格 jsonl reader |
| vm_ab_sweep_{old,new}_marks.jsonl | A/B 原始输出（入 raw_data 语义，本目录留副本） |

---

## 五、现场经验补充（raw_data）

用户现场观察与录制/scp 日志原文 → [raw_data/raw_箱体实测观察_2026-09-08](../raw_data/raw_箱体实测观察_2026-09-08_1027.md)（不入 git）。
要点：140cm 首线观察（模型外推 ≈ 参照点含 ±20cm 不确定性，以点云为准）；±10° 内 35cm 箱；
150cm 2~3 线 / 120cm 无；终停 220~230cm 3 线 0.34~0.35m —— 全部与 ring 律自洽（§3.2）。

---

## 六、遗留与去向

| # | 项 | 状态/去向 |
|:---|:---|:---|
| 1 | 修复 config（nav2_params_low.yaml obstacle_low_layer 拆分）**待提交** | commit 待授权；N97 pull + colcon build 后生效 |
| 2 | 全速版 `nav2_params.yaml` 同构修复（含膨胀 0.55→0.30 同步） | 未做；切回前必须同步（07-handover 警示） |
| 3 | 实车 N97 验证（可选窗口 09-10 前）：A/B 检查单同 09-05 §（install 同步→publish_voxel_map→带顶评估） | 视窗口 |
| 4 | 固有盲区（<1.59m 0.35m 箱任何 ring 不可见）不因本修复消失 | 产品语义边界，文档留档即可；更深方案见 [surveys/3d-lidar-2d-navigation-survey.md](../surveys/3d-lidar-2d-navigation-survey.md) |
| 5 | 09-10 收手线：A1 补跑（静态绕行）若窗口未开即记录缺口收手 | recruitment-learning-plan §4.1 |

---

## 七、方法模板：反转重放 A/B 验收操作卡（可复用）

> 适用：需要在 VM 上"无真车复现"一个 **mark→清除竞争** 的 costmap 行为差异（配置 A/B、近距丢黑、
> 清除链问题）。本卡承接 09-05 抽帧重发法（[2026-09-05 §五](2026-09-05_lowobstacle_fixB_vm_acceptance.md)）的"动态因果链"变体。

① **录一个方向的完整渐变场景**：静止车 + 目标物（尺寸已知）+ 沿车头轴逐档移动（每档停 3~5s），
   覆盖 全盲 → 首线 → 多线 全段。话题仅 `/velodyne_points /scan /tf_static`（+必要 TF）。
② **先离线定几何律**：读本机 VLP16db.yaml 得 ring 角 → 由目标物高度/雷达离地算每条 ring 可见距窗与
   临界距 → 用逐帧高度谱验证（h = H − d·tanθ 反推命中 ring），**不拿现场目测当定论**。
③ **定 mark 相与 clear 相素材**：同一条记录内选停驻段（mark 相）与盲区段（clear 相，天然无目标物点）。
④ **整包反转重放**：全部 points/scan 帧逆序发（stamp 改 wall now；best_effort；可按需 2× 加速），
   A/B 各跑一遍；顺带得到"衰减 onset 与盲区边界对齐"的因果时间自证。
⑤ **串行执行 + 残留守卫**：先 A 后 B（绝不并发）；每轮前 `pgrep -f "nav2_costmap_2d --ros-args"`
   守卫 exit 1；轮后按命令行特征 `pkill -f` 清理 + 复验；reader 与编排共用测试台资产。
⑥ **区域判据**：以目标物可达 x 区间 + |y| 半宽圈定 ROI，统计 raw 254 格数轨迹；
   判据 = OLD 终态趋 0 vs NEW 终态保持 >0；并记录背景（旁侧物/墙）同轨迹做一致性检查。
⑦ **收尾**：jsonl/轨迹表入分析目录留档；经验/方法回写 retrospect（本文 §八）。

---

## 八、经验点层次标注节

| # | 经验点（含教训） | 建议去向 |
|:---|:---|:---|
| 1 | **手动推车段 bag 不适合做低带 A/B**：人腿在低带持续 mark + 车动箱格移动/拖尾 → 全图 254 淹没箱格信号；验证数据源必须"无人介入 + 物距可重复" | 事件层留存（09-06/09-08 互指） |
| 2 | **反转重放 = 用"远离"录制自证"接近"因果链**（含盲区边界时间对齐的自验），免真车撞箱/免掐点源 | draft：analysis-methods（成熟后并入 ros2-ops §9/§7） |
| 3 | **成熟分析脚本复用纪律**（用户 09-08 明确要求）：先读既有 find_box_in_points/render_frames/sweep_frames 再参数化，不每次新写；新写正确率低、效率低 | 规则层候选：ros2-ops §7（需用户批准后写入） |
| 4 | **几何问题先标定后解释**：ring 角来自校准文件实源，现场目测（140/150/120cm）只作佐证不反推结论；逐帧高度谱与理论偏差 <1cm = 可信判据 | analysis-methods 数据验证法（draft） |
| 5 | **A/B 台进程卫生与串行纪律**：同话题双发布者数据逐字节污染（09-06 byte-identical 首帧教训）；预检守卫 + pkill -f 精确清理 + 轮间验证 | 规则层：ros2-ops §10 已有进程卫生；补充 A/B 并发污染案例（待批） |
| 6 | **固有盲区 ≠ 回归**：近距丢黑有两成分——几何盲区（本底，任何配置都无输入）与"见后清"竞争（本修复对象）；报告必须二分，避免把本底误判为 bug 残留 | 事件层留存 |
| 7 | 2D costmap 无 z 概念、clear 是"射线穿透层"语义；修法 B 用**分层隔离清除**而非改清除逻辑 = 最小侵入 | 事件层 + nav2-knowledge-tree 候选（draft） |

---

## 相关

- 前篇：[2026-09-06_lowobstacle_fixB_crashbox.md](2026-09-06_lowobstacle_fixB_crashbox.md) ｜ [2026-09-05_lowobstacle_fixB_vm_acceptance.md](2026-09-05_lowobstacle_fixB_vm_acceptance.md)
- 调研：低矮障碍感知全景 [surveys/3d-lidar-2d-navigation-survey.md](../surveys/3d-lidar-2d-navigation-survey.md)
- 资产：`bags/analysis/box_lowband_20260908/`（脚本 + 输出 + A/B 台 + 原始 jsonl）
