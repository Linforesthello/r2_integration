#!/usr/bin/env python3
"""09-08 纯净 bag（box_static / box_near）低带簇定位（复用 09-06 find_box_in_points 逻辑）。
用法: python3 cleanbag_clusters.py <bag路径>   全帧累积 ±16° 锥内 0.1m 格直方图 top12。
低带 z 带 = (-0.73, -0.41)（ground=-0.775, 箱 0.05~0.365m）；全高带含对照。
纯离线（rosbag2_py + numpy），不开 ROS。
"""
import sys, numpy as np, rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

def parse_pc2(msg):
    W = msg.point_step
    raw = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.width*msg.height, W)
    off = {f.name: f.offset for f in msg.fields}
    x = raw[:, off['x']:off['x']+4].copy().view('<f4').ravel()
    y = raw[:, off['y']:off['y']+4].copy().view('<f4').ravel()
    z = raw[:, off['z']:off['z']+4].copy().view('<f4').ravel()
    return np.stack([x, y, z], axis=1)

BAG = sys.argv[1]
GROUND = -0.775   # 09-06 实测 velodyne 系地面
reader = rosbag2_py.SequentialReader()
reader.open(rosbag2_py.StorageOptions(uri=BAG, storage_id='sqlite3'), rosbag2_py.ConverterOptions('','cdr'))
t2t = {t.name: t.type for t in reader.get_all_topics_and_types()}
types = {n: get_message(ty) for n, ty in t2t.items()}

acc = []; t0 = None
while reader.has_next():
    topic, data, t = reader.read_next()
    if topic != '/velodyne_points':
        continue
    if t0 is None:
        t0 = t
    acc.append(parse_pc2(deserialize_message(data, types[topic])))
P = np.vstack(acc)
print(f'== {BAG.split("/")[-1]}  全帧累积点 {len(P)}（{len(acc)} 帧）')
r = np.hypot(P[:, 0], P[:, 1])
az = np.degrees(np.arctan2(P[:, 1], P[:, 0]))
for label, (zl, zh) in [('低带(箱 0.05~0.365m)', (GROUND+0.05, GROUND+0.365)),
                        ('全高(地~0.5m 物)', (GROUND-0.1, GROUND+0.5))]:
    m = (P[:, 2] > zl) & (P[:, 2] < zh) & (np.abs(az) < 16) & (r > 0.5) & (r < 6.0)
    sel = P[m]
    print(f'  [{label}] 锥内点 {len(sel)}')
    if len(sel) < 10:
        continue
    gx = np.floor(sel[:, 0] / 0.1).astype(int)
    gy = np.floor(sel[:, 1] / 0.1).astype(int)
    keys = gx * 100000 + gy
    u, inv, cnt = np.unique(keys, return_inverse=True, return_counts=True)
    for idx in np.argsort(-cnt)[:12]:
        msk = inv == idx
        xs, ys, zs = sel[msk, 0], sel[msk, 1], sel[msk, 2]
        print(f'    格=({xs.mean():.2f},{ys.mean():.2f}) n={cnt[idx]} z->h=[{zs.min()-GROUND:.3f},{zs.max()-GROUND:.3f}]m '
              f'dist={np.hypot(xs.mean(), ys.mean()):.2f}m az={np.degrees(np.arctan2(ys.mean(), xs.mean())):.1f}°')
