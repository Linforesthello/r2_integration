# 建图验证流程（录制 → 传回 VM → 分析 → 逐帧 → 出图 → 判断）

> 目的：一次完整建图录制的标准化流程，每步可复现、有量化验收，最终产出合格 2D 地图。
> 适用范围：R2 + VLP-16 + KISS-ICP 建图链路（Phase 3）。
> 方法来源：2026-08-13 全链路排查与三段验证（seg1/seg2/seg3），见 [retrospect/2026-08-13_map_chain_investigation.md](../retrospect/2026-08-13_map_chain_investigation.md)。
> 关键结论：**地图质量 = 位姿质量**。纯激光旋转退化（原地转漂移 10-18cm）是重影根因；
> 带平移约束的转弯（前进+转向）可抑制到 <10cm。录制纪律比任何参数都重要。

---

## 流程总览

```
[1 录制 N97] → [2 传回 VM] → [3 bag 统计] → [4 逐帧分析] → [5 出图] → [6 判断验收]
```

---

## 1. 录制（N97）

前置与启动顺序见 [w1-operation.md §1.1](w1-operation.md)，录制纪律见 [D3b](w1-operation.md)。

**动作纪律（决定地图质量的 90%）**：
- ❌ 禁止原地旋转（纯旋转退化 → 漂移 10-18cm + 残留 → 重影）
- ✅ 转弯时保持前进（弧线转弯，平移约束抑制退化）
- ✅ 慢速匀速，段长 ≤3 分钟，段间停录 10-30s
- ✅ 全程盯 `ros2 topic hz /kiss/odometry`，掉 <7Hz 立即停录

```bash
# 录制（每段一个 bag，段号递增）
ros2 bag record -o ~/Lin_workspace/r2_integration/bags/map_final_$(date +%m%d_%H%M)_segN \
  /velodyne_points /kiss/frame /kiss/odometry /odom_wheels /odometry/filtered /tf /tf_static
```

## 2. 传回 VM

```bash
# N97 上
scp -r ~/Lin_workspace/r2_integration/bags/map_final_*_segN lin@192.168.1.204:~/Lin_workspace/r2_integration/bags/raw/
```

## 3. bag 统计（帧率 / 空窗）

```bash
# 完整统计（点数/车速/帧间隔/空窗）
python3 ~/Lin_workspace/r2_integration/bags/analysis/stats_map_run.py <bag_dir>
```

**验收门槛**：KISS ≥7Hz、无 >0.5s 空窗（有 → 录制条件问题：CPU 争抢/性能模式未切，重录）。

## 4. 逐帧分析（KISS vs EKF 位姿偏差，检测旋转退化）

```bash
# EKF(IMU+轮速) 为可信基准，KISS 为纯激光估计；起点对齐后逐帧对比位置偏差
python3 ~/Lin_workspace/r2_integration/bags/analysis/analyze_kiss_vs_ekf.py <bag_dir>
```

输出：逐帧表（偏差大帧全列）+ 每 4s 段偏差 + 自动结论。

**判定阈值（2026-08-13 实测）**：

| 场景 | 峰值偏差 | 结束残留 | 判定 |
|:-----|:-----|:-----|:-----|
| 直行 | <1cm | <1cm | ✅ |
| 前进+转弯 | <10cm | <3cm | ✅ 可建图 |
| 原地旋转 | 10-18cm | >10cm | ⚠️ 重影风险，重录 |

## 5. 出图（3D 累积 → 2D 占用网格）

```bash
# bag → 3D 点云（抽稀 5）
python3 ~/Lin_workspace/r2_integration/bags/analysis/build_map.py <bag_dir> <输出>.ply 5
# 3D → 2D 占用网格（z_min 默认 0.3，勿改回 0.1：地面雾 28% 占用格）
python3 ~/Lin_workspace/r2_integration/bags/analysis/pcd_to_map.py <输出>.ply <输出>.pgm
```

产物整理规范：raw/ 只放 bag；ply/pgm/预览图归位 `maps/<地图名>/`，对比图 `maps/<地图名>/compare_*.png`（见 [bags README](../../bags/README.md)）。

## 6. 判断是否合理（验收）

**数值验收**：

| 指标 | 合格 | 说明 |
|:-----|:-----|:-----|
| 最长连续墙段 | ≥5m | 墙线完整性 |
| 墙厚 p50 | ≤3 格(15cm) | 单线墙；重影双线 → p90 明显变厚 |
| 孤立碎片 | <1% | 噪点占比 |
| 地面雾 | 无 | z_min 0.3 已滤；有 → 参数被改回 0.1 |
| 无重影双线 | 目视确认 | N97 rviz 或预览图 |

```bash
# 出图后快速数值检查（墙段/碎片/厚度）
python3 - <<'EOF'
import numpy as np
from scipy import ndimage
def load_pgm(p):
    with open(p,'rb') as f:
        assert f.readline().strip()==b'P5'
        w,h = map(int, f.readline().split()); f.readline()
        return np.frombuffer(f.read(),dtype=np.uint8).reshape(h,w)
occ = (load_pgm('<输出>.pgm')>0).astype(np.uint8)
lab, n = ndimage.label(occ); sizes = np.bincount(lab.ravel())[1:]
iso = (sizes==1).sum()
lens=[]
for row in occ:
    c=0
    for v in row:
        if v: c+=1
        else:
            if c: lens.append(c)
            c=0
    if c: lens.append(c)
lens=np.array(lens)
print(f"占用格 {occ.sum()} 墙厚p50={np.median(lens)} p90={np.percentile(lens,90):.0f} "
      f"最长段 {lens.max()}格={lens.max()*0.05:.2f}m 碎片 {iso}({iso/occ.sum()*100:.1f}%)")
EOF
```

**不合格处置**：
- 重影双线 + 残留偏差大 → 重录（检查动作：是否原地转）
- 地面雾 → 检查 z_min（0.3）
- 墙段断续/碎片多 → 检查录制帧率（≥7Hz）与行驶速度

---

## 相关

- 录制/启动手册：[w1-operation.md](w1-operation.md)（D1-D5 + D3b 正式长录纪律）
- 排查留档：[retrospect/2026-08-13_map_chain_investigation.md](../retrospect/2026-08-13_map_chain_investigation.md)
- 脚本：[stats_map_run.py](../../bags/analysis/stats_map_run.py)、[analyze_kiss_vs_ekf.py](../../bags/analysis/analyze_kiss_vs_ekf.py)、[build_map.py](../../bags/analysis/build_map.py)、[pcd_to_map.py](../../bags/analysis/pcd_to_map.py)
