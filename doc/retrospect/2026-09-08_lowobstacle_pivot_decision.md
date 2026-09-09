# 低物链收手定论 + 主线转向 3D 规控 —— 方向决策（2026-09-08）

> 日期：2026-09-08｜类型：方向决策（用户定）｜状态：✅ 已定稿落地（决策正文）
> 决策人：用户（09-08「执行 B，写入文档」指令确认 pivot 方向；倾向原话见 §二 引文）
> 关联：[09-08 二次失效根因（bag 实锤）](2026-09-08_lowobstacle_secondfail_clearevent.md)、[09-08 ring 律/纯净数据](2026-09-08_lowobstacle_ringlaw_cleandata.md)、[09-08 A/B 验收](2026-09-08_lowobstacle_fixB_ab_acceptance.md)、[09-06 撞箱](2026-09-06_lowobstacle_fixB_crashbox.md)、[感知手段调研（survey）](../surveys/3d-lidar-2d-navigation-survey.md)、排期权威 [recruitment-learning-plan §4.1/§4.3/§5.1](../roadmaps/recruitment-learning-plan.md)

---

## 一、决策（结论先行）

1. **低物感知机制精修 —— 收手定论**（不再投入实车/VM 窗口）：
   - 物理边界（0.35m 箱 1.59m 临界，ring 几何律）无参数可改（09-02 已认知，09-08 实锤定稿）
   - **结构性冲突实锤**（09-08 bag 逐帧）：盲区保留 mark 会被导航栈自身的 global 整层清空事件一票抹除、且盲区内不可再观测 → 第二次接近必然失效；修法 B（mark-only 保留）在无清空事件时工作正常，但"保留信息 vs clear 语义"冲突无根治解，变通（禁清 global/独立层保 mark）皆为打补丁
   - 近期测试场景维持 [recruitment-learning-plan §4.1 ③](../roadmaps/recruitment-learning-plan.md) 既有处置：**统一用高箱规避干扰**（A1 判据本就不含低物停障）
2. **成果保留不回滚**：降额版 `nav2_params_low.yaml` 的 velodyne_low 独立 mark-only 结构（180077c）保持生效——第一次接近停障有效是实测事实（09-08 bag 窗 A），不因收手而回滚；全速版切回警示（07-handover）维持
3. **主线转向 3D 规控方向**：A2（FAST-LIO2 TF 桥 + 建图源）按既有排期入阶段二（[recruitment-learning-plan §5.1](../roadmaps/recruitment-learning-plan.md)，用户 09-02 定）；3D 重定位/explore 等维持远期池（[planning-control-roadmap §5.8](../roadmaps/planning-control-roadmap.md) 等），不因本次提前
4. **边界**：A1 避障判据 5/5 与 09-10 收手线不变——本次收手只关闭"低物机制精修"子线，不影响线 1 主链路执行

## 二、决策输入（证据链全回指源文档，不复制细节）

**用户 pivot 倾向（09-08 会话原文）**："在不增加传感器的基础上我感觉到极限了，是否应该就此跳过？后面上 3D 的规控方案（fastlio 多传感器规划重定位等等）以及 explore 方向"——09-08「执行 B + 写入文档」指令 = 拍板落盘。

| 输入 | 内容 | 证据 |
|:---|:---|:---|
| ① 物理几何边界 | 0.35m 箱在传感轴 1.59m 外即被 -15° 环越顶，<1.59m 进入绝对盲区（ring 律，纯净三录实锤） | [09-08 ringlaw/cleandata](2026-09-08_lowobstacle_ringlaw_cleandata.md)、[survey §三B](../surveys/3d-lidar-2d-navigation-survey.md) |
| ② 保留机制的结构性冲突（新） | 修法 B 实车第一次接近有效（mark 保留 9.5s 静止不衰减）；新 goal 触发 global 障碍层整层清空（单帧 2260 格 = 全部非静态 254 归零），保留箱 mark 被抹（箱区 -52%）；盲区不可再生 → 第二次接近直行穿越实锤 | [09-08 secondfail_clearevent](2026-09-08_lowobstacle_secondfail_clearevent.md) |
| ③ 替代手段现状 | FAST-LIO2 已实车验证（08-24 旋转 <2° / 平移 0.5%）；A2 TF 桥/建图源方案已定 08-18；加传感器（MID-70/D435）触发条件已满足但排期后置 | [08-24 fastlio2 验证](2026-08-24_fastlio2_verification.md)、[execution.md A2 卡](../minimal-loop2/execution.md)、[recruitment-learning-plan §4.3/§6 池](../roadmaps/recruitment-learning-plan.md) |

## 三、选项与影响（决策记录，用户 09-08 定）

| 选项 | 做法 | 影响 | 结果 |
|:---|:---|:---|:---:|
| A. 继续精修低物（变通） | 禁 planner-fail 清 global / 独立静态代理层保 mark / 接近段禁 clear | 反复打补丁对抗 nav2 clear 语义；物理盲区仍在，一次清空即前功尽弃；消耗 09-10 前宝贵窗口 | ✗ |
| **B. 收手 + 主线转 3D（采纳）** | 机制精修停；高箱规避维持；A2/explore 按既有排期 | 释放窗口给 A1 主链 + 求职线；低物问题以"感知边界+手段升级"定论留档（面试/作品集口径：物理边界可量化陈述 + 结构性冲突认知） | ✅ |
| C. 保持现态等阶段二 | 低物链搁置不表态 | 文档无定论，交接/复盘时反复重新评估 | ✗ |

## 四、收口动作清单（本次刷新落地）

- [x] 07-handover：§四 第 1 项（修法 B 实车验证）→ 完成态改写；头部状态行刷新 — 待授权提交
- [x] pending-tasks ⑤：近距丢黑块行刷新（180077c 已提交 → N97 已拉取 → 实车验证完成 → 收手）；costmap 刷新慢行补源链接 — 待授权提交
- [x] recruitment-learning-plan：§4.3 增"低物机制精修收手"行；头部刷新注记 — 待授权提交
- [x] survey 3d-lidar：头部状态行补 09-08 收手注记 — 待授权提交
- [x] retrospect/README + 根 README 树：登记 clearevent + pivot 两篇 — 待授权提交

## 五、遗留（与本文决策相关，不阻塞）

- clear 触发器（goal6 时 planner 为何失败 / 谁调 clear 服务）实机 BT/planner 日志确认——仅当低物链再开时有价值，默认不追
- map 刷新慢（rviz 观感滞后）查证——用户另记，未排期（疑与 global 0.64Hz 节流同源，见 [pending-tasks ⑤](../pending-tasks.md)）
- 面试口径素材：低物链全程叙事（物理盲区几何推导 + ring 律 1.59m 实锤 + 修复设计（双层 mark-only）+ 结构性冲突根因定位）已是完整技术故事，可入作品集深挖稿备选（[recruitment-learning-plan §4.2 素材卡](../roadmaps/recruitment-learning-plan.md)）

## 六、方法模板节

本次"感知边界 → 收手转方向"决策的提炼卡：

1. ① 感知类问题先分「物理边界 vs 工程缺陷」：边界（几何/能量/信息论不可参数化）与缺陷（可修）分开列证据，各自实锤后再判收手与否（本链：盲区 1.59m = 物理边界；"第二次失效"初看像缺陷，最终根因 = 工程语义冲突，但修复收益受物理边界封顶）
2. ② 判"投入是否已越过收益曲线"：修复有效性证据（第一次 PASS）≠ 场景闭环（第二次必失效）——用完整场景链（第一次+第二次）验收，单场景 PASS 不构成闭环证据
3. ③ 收手决策必须落「选项 × 影响」表 + 用户拍板记录 + 成果保留清单（不回滚、不删码），并同步刷新 4 类状态文档（交接/待办/排期/调研承载），防文档口径分裂

## 七、经验点层次标注节

| 经验点 | 建议去向 |
|:---|:---|
| 感知"物理边界"与"工程缺陷"分离取证，边界实锤即收手阈值（避免在几何极限上无限打补丁） | 规则层候选（排障纪律增补）或 draft（analysis-methods.md） |
| 验收须覆盖完整场景链：修复有效 ≠ 场景闭环（第一次 PASS、第二次失效即一例） | 规则层候选（排障纪律增补）|
| 收手决策文档 = 决策陈述 + 选项×影响 + 用户拍板 + 成果保留 + 状态文档同步清单，五件套 | draft（doc-engineering 或 analysis-methods）|
| 面试叙事：物理盲区几何推导 + 修复设计 + 结构性冲突 = 完整技术故事，比"修好了"更有深度 | 事件层留存（本文档 §五）|
