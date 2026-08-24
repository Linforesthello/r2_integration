# minimal-loop 执行目录

> 最小闭环打通计划（[plan.md](plan.md)）的执行文档目录
> 按 D0 审计 → W1 建图 → W2 导航 → W3 避障 的顺序推进

## 文件索引

| 文件 | 内容 |
|:-----|:-----|
| [0audit.md](0audit.md) | D0 系统现状审计结论（节点/话题/TF/频率/定量基线/定案项） |
| [0status_list.md](0status_list.md) | 审计原始输出（节点清单/话题闭合/TF 四链路） |
| [0status_hz.md](0status_hz.md) | 审计原始输出（各话题频率实测） |
| [frames_2026-08-06_21.40.43.gv](frames_2026-08-06_21.40.43.gv) | TF 树快照（graphviz 源） |
| [frames_2026-08-06_21.40.43.pdf](frames_2026-08-06_21.40.43.pdf) | TF 树快照（PDF） |
| [frames_2026-08-06-1.png](frames_2026-08-06-1.png) | TF 树快照（PNG） |
| [w1-operation.md](w1-operation.md) | W1 操作手册（TF 工程 + 建图落地，命令级，D1~D5；✅ 已完结） |
| [w2-operation.md](w2-operation.md) | W2 操作手册（Nav2 最小导航闭环，D1~D7；🟡 收尾中：D5-6 连续导航测试 + D7 验收，含到达误差测量方案） |
| [w3-operation.md](w3-operation.md) | W3 操作手册（动态避障 + 综合演练，D1~D7；计划 08-20 启动） |
| [nav2-bringup.md](nav2-bringup.md) | Nav2 实机导航 bringup 执行记录（D4 复用验证 + 首闭环；✅ 08-15 完成；08-17 降额过缝验证通过，全速暂缓） |
| [map-verify-flow.md](map-verify-flow.md) | 建图验证流程（3D→2D 导航层生成） |

## 当前状态（2026-08-18）

- ✅ D0 审计完成：TF 定案（69/13/56）、定量基线健康
- ✅ W1 建图全链路（08-15 完结）：D2 重影消除（08-11）→ 干净 bag 重录 + 人形块过滤（08-15）→ 清洗版导航图 map_0815_clean
- ✅ W2 核心闭环（08-15/08-17）：Nav2 首闭环跑通（降额 0.2m/s）+ 降额过缝验证通过（inflation 0.30，无碰撞）
- 🟡 W2 收尾（进行中）：D5-6 连续导航测试、D7 验收（到达误差测量，方案见 [w2-operation.md](w2-operation.md) D7）
- ⏳ 待办：W3 避障 + 综合演练（08-20 启动，见 [w3-operation.md](w3-operation.md)）；全速验证**暂缓 08-17，保持降额现状**

## 关键结论速查

- base_link 离地 12cm；雷达光学中心离地 77~78cm；base_link→velodyne = 0.655m（08-24 复测更新）
- base_footprint 已删除（TF2 双父冲突）
- 记录项：transform 层偶发丢帧（6.4Hz vs 驱动 9.9Hz）；EKF 输出偶发 332ms 抖动——先端到端，建图验证受影响再处理
