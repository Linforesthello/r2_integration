#!/usr/bin/env python3
"""车前方 ±15° 锥形内低物簇跟踪（velodyne 系筛 -> odom 系输出）"""
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

VL_Z = 0.655  # tf_static 实测 base_link->velodyne z
GROUND_V = -0.655  # velodyne 系地面

# 帧 5Hz
WINDOWS = {
    'S1a 0-30s': (0, 30), 'S1b 30-60s': (30, 60), 'S1c 60-95s': (60, 95), 'S1d 95-115s': (95, 115),
    'D1 115-125s': (115, 125), 'S2 125-132s': (125, 132), 'D2 132-142s': (132, 142),
    'S3 142-193s': (142, 193), 'D3 193-200s': (193, 200), 'S4 200-206s': (200, 206),
    'D4 206-210s': (206, 210), 'S5 210-220s': (210, 220), 'D5 220-224s': (220, 224),
}
def sec_to_win(sec, wins):
    for k, (a, b) in wins.items():
        if a <= sec < b:
            return k
    return None

# 重新读一遍（上面 acc 逻辑坏：win 计算在 append 前 ok 但循环顺序先 /tf 后 points，odom_pose 每帧前更新 —— 重写主循环）
print('重跑主循环（tf+points 顺序正确版）...')
# —— 直接重开 reader 更稳 ——
r2 = rosbag2_py.SequentialReader()
r2.open(rosbag2_py.StorageOptions(uri=BAG, storage_id='sqlite3'),
        rosbag2_py.ConverterOptions('', 'cdr'))
t0 = None
pose = None  # (x,y,yaw_deg)
acc2 = {k: [] for k in WINDOWS}
frames = 0
while r2.has_next():
    topic, data, t = r2.read_next()
    if topic == '/tf':
        for tr in deserialize_message(data, types[topic]).transforms:
            if tr.header.frame_id == 'odom' and tr.child_frame_id == 'base_link':
                tr_ = tr.transform.translation
                q = tr.transform.rotation
                yaw = np.degrees(np.arctan2(2*(q.w*q.z + q.x*q.y), 1 - 2*(q.y*q.y + q.z*q.z)))
                pose = (tr_.x, tr_.y, yaw)
    elif topic == '/velodyne_points':
        if t0 is None:
            t0 = t
        sec = (t - t0) / 1e9
        frames += 1
        if frames % 2 != 0:
            continue
        if pose is None:
            continue
        msg = deserialize_message(data, types[topic])
        W = msg.point_step
        raw = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.width * msg.height, W)
        off = {f.name: f.offset for f in msg.fields}
        x = raw[:, off['x']:off['x']+4].copy().view(np.float32).ravel()
        y = raw[:, off['y']:off['y']+4].copy().view(np.float32).ravel()
        z = raw[:, off['z']:off['z']+4].copy().view(np.float32).ravel()
        az = np.degrees(np.arctan2(y, x))
        r = np.hypot(x, y)
        m = (np.abs(az) < 15.5) & (r > 0.5) & (r < 6.0) & (z > GROUND_V + 0.05) & (z < GROUND_V + 0.45)
        if not m.any():
            continue
        Pc = np.stack([x[m], y[m], z[m]], axis=1)
        # velodyne -> odom（车头角 yaw 由 R 旋转 velodyne x->odom x）
        yaw_r = np.radians(pose[2])
        ct, st = np.cos(yaw_r), np.sin(yaw_r)
        xo = pose[0] + Pc[:, 0] * ct - Pc[:, 1] * st
        yo = pose[1] + Pc[:, 0] * st + Pc[:, 1] * ct
        zo = pose[2] + Pc[:, 2] + VL_Z  # base_link z~0(EKF 锁) + velodyne 偏移
        Po = np.stack([xo, yo, zo], axis=1)
        w = sec_to_win(sec, WINDOWS)
        if w:
            acc2[w].append(Po)

for wname, frames_ in acc2.items():
    if not frames_:
        print(f'\n[{wname}] 无帧'); continue
    P = np.vstack(frames_)
    gx = np.floor(P[:, 0] / 0.15).astype(int)
    gy = np.floor(P[:, 1] / 0.15).astype(int)
    keys = gx * 100000 + gy
    u, inv, cnt = np.unique(keys, return_inverse=True, return_counts=True)
    order = np.argsort(-cnt)
    print(f'\n[{wname}] 锥内低物点 {len(P)}，0.15m 簇 top 8:')
    for idx in order[:8]:
        msk = inv == idx
        xs, ys, zs = P[msk, 0], P[msk, 1], P[msk, 2]
        print(f'    odom=({xs.mean():.2f},{ys.mean():.2f}) 顶z={np.percentile(zs, 95):.2f} '
              f'范围x[{xs.min():.2f},{xs.max():.2f}] y[{ys.min():.2f},{ys.max():.2f}] n={cnt[idx]}')
