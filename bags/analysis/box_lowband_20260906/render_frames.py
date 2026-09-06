#!/usr/bin/env python3
"""渲染关键帧 velodyne 俯视图（高度着色），定位 0.35 箱"""
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BAG = '/home/lin/Lin_workspace/r2_integration/bags/raw/box_lowband_20260906_091644'
reader = rosbag2_py.SequentialReader()
reader.open(
    rosbag2_py.StorageOptions(uri=BAG, storage_id='sqlite3'),
    rosbag2_py.ConverterOptions('', 'cdr'),
)
t2t = {t.name: t.type for t in reader.get_all_topics_and_types()}
types = {n: get_message(ty) for n, ty in t2t.items()}

# 需要的帧: 目标秒 -> 标签
WANT = {60.0: 'S1_t60', 120.0: 'D1_t120', 140.0: 'D2_t140', 170.0: 'S3_t170', 215.0: 'S5_t215'}

def parse_pc2(msg):
    W = msg.point_step
    raw = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.width * msg.height, W)
    off = {f.name: f.offset for f in msg.fields}
    x = raw[:, off['x']:off['x']+4].copy().view(np.float32).ravel()
    y = raw[:, off['y']:off['y']+4].copy().view(np.float32).ravel()
    z = raw[:, off['z']:off['z']+4].copy().view(np.float32).ravel()
    return np.stack([x, y, z], axis=1)

t0 = None
found = {}
while reader.has_next():
    topic, data, t = reader.read_next()
    if topic != '/velodyne_points':
        continue
    if t0 is None:
        t0 = t
    sec = (t - t0) / 1e9
    for want, label in WANT.items():
        if abs(sec - want) < 0.12 and label not in found:
            found[label] = parse_pc2(deserialize_message(data, types[topic]))
            # 读最近 odom->base_link 也存下
for k in found:
    P = found[k]
    # velodyne 系: 地 = -0.775
    ground = P[:, 2] < -0.70
    fig, ax = plt.subplots(1, 2, figsize=(18, 7))
    for a, (xr, yr, title) in zip(ax, [
            ((-8, 9), (-7, 7), '全览'),
            ((0.5, 3.5), (-1.0, 1.2), '正前方局部')]):
        m = (P[:, 0] > xr[0]) & (P[:, 0] < xr[1]) & (P[:, 1] > yr[0]) & (P[:, 1] < yr[1])
        sel = P[m]
        h = -(sel[:, 2] + 0.775)  # 高度
        sc = a.scatter(sel[:, 0], sel[:, 1], c=h, s=0.4, cmap='viridis', vmin=0, vmax=1.2)
        a.set_xlim(*xr); a.set_ylim(*yr)
        a.set_aspect('equal'); a.set_title(f'{k} {title}')
        a.set_xlabel('x (车头+)'); a.set_ylabel('y')
        plt.colorbar(sc, ax=a, label='高度(m)')
    # 车轮廓示意 (base_link footprint 半 0.42/0.33) 在原点
    ax[0].plot([0, 0], [0, 0], 'r+', markersize=18)
    ax[1].plot([0, 0], [0, 0], 'r+', markersize=18)
    ax[1].add_patch(matplotlib.patches.Rectangle((-0.42, -0.33), 0.84, 0.66, fill=False, ec='r'))
    fig.suptitle(f'{k}  velodyne frame（原点=车，色=离地高 0~1.2m）')
    fig.savefig(f'/tmp/frame_{k}.png', dpi=90)
    plt.close(fig)
    print(f'saved /tmp/frame_{k}.png  (点 {len(P)})')
