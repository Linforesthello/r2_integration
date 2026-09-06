#!/usr/bin/env python3
"""在 velodyne_points 中找车前方 ±15° 的 0.35m 低箱（静止段分窗）"""
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

# 静止窗（相对 bag 首消息时间）
WINDOWS = {
    'S1a 摆箱前期 (0-30s)': (0, 30),
    'S1b 摆箱中 (30-60s)': (30, 60),
    'S1c 摆箱后期 (60-95s)': (60, 95),
    'S1d 观察段 (95-115s)': (95, 115),
    'S2 (125-132s)': (125, 132),
    'S3 (142-193s)': (142, 193),
    'S4 (200-206s)': (200, 206),
    'S5 (210-220s)': (210, 220),
}

def parse_pc2(msg):
    """提取 xyz (N,3)，velodyne 系"""
    W = msg.point_step
    H = msg.height
    n = msg.width * H
    raw = np.frombuffer(msg.data, dtype=np.uint8).reshape(n, W) if W > 0 else None
    if raw is None:
        return np.zeros((0, 3))
    off = {f.name: (f.offset, f.datatype) for f in msg.fields}
    x = raw[:, off['x'][0]:off['x'][0]+4].copy().view(np.float32).ravel()
    y = raw[:, off['y'][0]:off['y'][0]+4].copy().view(np.float32).ravel()
    z = raw[:, off['z'][0]:off['z'][0]+4].copy().view(np.float32).ravel()
    return np.stack([x, y, z], axis=1)

acc = {k: [] for k in WINDOWS}
t0 = None
n_frames = 0
while reader.has_next():
    topic, data, t = reader.read_next()
    if topic != '/velodyne_points':
        continue
    if t0 is None:
        t0 = t
    sec = (t - t0) / 1e9
    # 抽帧 ~5Hz (每0.2s)
    if n_frames % 2 != 0:
        n_frames += 1
        continue
    n_frames += 1
    for wname, (a, b) in WINDOWS.items():
        if a <= sec < b:
            pts = parse_pc2(deserialize_message(data, types[topic]))
            acc[wname].append(pts)
            break

print('窗累加点云完成，开始筛选...')
for wname, frames in acc.items():
    if not frames:
        print(f'\n[{wname}] 无帧')
        continue
    P = np.vstack(frames)
    r = np.hypot(P[:, 0], P[:, 1])
    az = np.degrees(np.arctan2(P[:, 1], P[:, 0]))
    # 低箱筛选：z 在 velodyne 系 -0.64~-0.28（地 -0.655，箱 0.05~0.35m 高），正前 ±16°，0.5~5m
    m = (P[:, 2] > -0.64) & (P[:, 2] < -0.28) & (np.abs(az) < 16) & (r > 0.5) & (r < 5.0)
    sel = P[m]
    print(f'\n[{wname}] 原始点 {len(P)}，正前低点 {len(sel)}')
    if len(sel) < 10:
        continue
    # 0.1m 格直方图
    gx = np.floor(sel[:, 0] / 0.1).astype(int)
    gy = np.floor(sel[:, 1] / 0.1).astype(int)
    keys = gx * 100000 + gy
    u, inv, cnt = np.unique(keys, return_inverse=True, return_counts=True)
    order = np.argsort(-cnt)
    print('  前 12 个稠密 0.1m 格 (x,y,z范围, 点数):')
    for idx in order[:12]:
        msk = inv == idx
        xs, ys, zs = sel[msk, 0], sel[msk, 1], sel[msk, 2]
        print(f'    中心=({xs.mean():.2f},{ys.mean():.2f}) z=[{zs.min():.2f},{zs.max():.2f}] n={cnt[idx]} '
              f'dist={np.hypot(xs.mean(), ys.mean()):.2f}m az={np.degrees(np.arctan2(ys.mean(), xs.mean())):.1f}°')
