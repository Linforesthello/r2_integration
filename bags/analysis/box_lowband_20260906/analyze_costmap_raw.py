#!/usr/bin/env python3
"""读 local_costmap/costmap_raw 全序列：静止段帧差找新簇 + 值直方图演化"""
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

BAG = '/home/lin/Lin_workspace/r2_integration/bags/raw/box_lowband_20260906_091644'
reader = rosbag2_py.SequentialReader()
reader.open(
    rosbag2_py.StorageOptions(uri=BAG, storage_id='sqlite3'),
    rosbag2_py.ConverterOptions('', 'cdr'),
)
t2t = {t.name: t.type for t in reader.get_all_topics_and_types()}
types = {n: get_message(ty) for n, ty in t2t.items()}

frames = []  # (t, origin_x, origin_y, res, w, h, data_uint8)
t0 = None
while reader.has_next():
    topic, data, t = reader.read_next()
    if topic != '/local_costmap/costmap_raw':
        continue
    if t0 is None:
        t0 = t
    sec = (t - t0) / 1e9
    msg = deserialize_message(data, types[topic])
    meta = msg.metadata
    origin = meta.origin.position
    d = np.frombuffer(msg.data, dtype=np.uint8).reshape(meta.size_y, meta.size_x)
    frames.append((sec, origin.x, origin.y, meta.resolution, d))

print(f'costmap_raw 帧数 {len(frames)}')
print(f'尺寸 {frames[0][4].shape}, 分辨率 {frames[0][3]}, 首帧 t={frames[0][0]:.1f}')

def world_of(r, c, ox, oy, res):
    return ox + (c + 0.5) * res, oy + (r + 0.5) * res

# 值统计函数
def hist(d):
    u, c = np.unique(d, return_counts=True)
    cnt = dict(zip(u.tolist(), c.tolist()))
    return cnt

# 静止段（t<118s）：与第一帧 diff，找新增"非 free"格（放箱痕迹）
t_static = [f for f in frames if f[0] < 110.0]
print(f'静止段帧 {len(t_static)}，分析帧差（相对首帧变化簇）...')
base = t_static[0][4]
prev_d = base.copy()
print(f'首帧直方图: {hist(base)}')

# 全静止段逐帧累积"与首帧不同的格"，找值增加的格
added = {}
for sec, ox, oy, res, d in t_static[1:]:
    # 与首帧比较（车静止 odom 固定，同格可比）
    mask = d != base  # 有变化的格（含变 free/变 occupied）
    ys, xs = np.nonzero(mask)
    for r, c in zip(ys, xs):
        v = int(d[r, c])
        key = (r, c)
        if key not in added or added[key] < v:
            added[key] = v
print(f'与首帧相比出现过变化的格数: {len(added)}')

# 聚类变化格（值>=1 视为可能箱子）
from collections import defaultdict
clusters = []
cand = {k: v for k, v in added.items() if v >= 1}
print(f'其中曾 >=1(非free) 的格: {len(cand)}')
val_hist = defaultdict(int)
for v in cand.values():
    val_hist[v] += 1
print(f'这些格的值分布: {dict(val_hist)}')

# 简单网格聚类（5cm 格，聚 0.5m）
grid = {}
for (r, c), v in cand.items():
    gk = (round(r / 10), round(c / 10))  # 0.5m 桶
    grid.setdefault(gk, []).append((r, c, v))
print(f'\n变化格空间桶(0.5m): {len(grid)} 个, 前 15 大桶:')
big = sorted(grid.items(), key=lambda kv: -len(kv[1]))[:15]
ox0, oy0 = t_static[0][1], t_static[0][2]
res = t_static[0][3]
for gk, pts in big:
    vals = defaultdict(int)
    for _, _, v in pts:
        vals[v] += 1
    # 桶中心世界坐标
    r_c = sum(p[0] for p in pts) / len(pts)
    c_c = sum(p[1] for p in pts) / len(pts)
    wx, wy = world_of(r_c, c_c, ox0, oy0, res)
    print(f'  中心=({wx:.2f},{wy:.2f}) n={len(pts)} 值分布={dict(vals)}')

# 运动段：抽几帧看值分布演化（找箱子到底有没有成 254）
print('\n=== 全程值直方图演化(每~30s一帧) ===')
for sec, ox, oy, res, d in frames[:: max(1, len(frames) // 10)]:
    print(f'  t={sec:6.1f}s  直方图={hist(d)}')
