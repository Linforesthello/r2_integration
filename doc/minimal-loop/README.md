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
| [w1-operation.md](w1-operation.md) | W1 操作手册（TF 工程 + 建图落地，命令级，D1~D5） |
| [nav2-bringup.md](nav2-bringup.md) | Nav2 实机导航 bringup（D4 复用验证 + 首闭环；✅ 08-15 完成；08-17 降额过缝验证通过，全速暂缓） |
| [map-verify-flow.md](map-verify-flow.md) | 建图验证流程（3D→2D 导航层生成） |

## 当前状态（2026-08-17）

- ✅ D0 审计完成：TF 定案（69/13/56）、定量基线健康
- ✅ W1 建图全链路：D2 重影消除（08-11）→ 干净 bag 重录 + 人形块过滤（08-15）→ 清洗版导航图 map_0815_clean
- ✅ Nav2 首闭环跑通（08-15，降额 0.2m/s）：D4 地图复用验证通过 + 自主导航成功
- ✅ 降额过缝验证通过（08-17）：inflation_radius 0.55→0.30 修复窄缝 costmap 全灰过不去，实测无碰撞、能过过道；盲区/footprint 修复顺带覆盖
- ⏳ 待办：全速验证（**暂缓 08-17，保持降额现状**）→ 避障实测（见 [nav2-bringup.md](nav2-bringup.md)）

## 关键结论速查

- base_link 离地 13cm；雷达光学中心离地 69cm；base_link→velodyne = 0.56m（URDF 已更新）
- base_footprint 已删除（TF2 双父冲突）
- 记录项：transform 层偶发丢帧（6.4Hz vs 驱动 9.9Hz）；EKF 输出偶发 332ms 抖动——先端到端，建图验证受影响再处理
