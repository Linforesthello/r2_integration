#!/usr/bin/env python3
"""odom 系全程跟踪低带点簇：箱子（0.35 平顶）位置演化，判是否被车撞/推"""
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
from scipy.spatial.transform import Rotation

BAG = '/home/lin/Lin_workspace/r2_integration/bags/raw/box_lowband_20260906_091644'
reader = rosbag2_py.SequentialReader()
reader.open(
    rosbag2_py.StorageOptions(uri=BAG, storage_id='sqlite3'),
    rosbag2_py.ConverterOptions('', 'cdr'),
)
t2t = {t.name: t.type for t in reader.get_all_topics_and_types()}
types = {n: get_message(ty) for n, ty in t2t.items()}

# 先拿 tf_static: base_link->velodyne
vl = None
r1 = rosbag2_py.SequentialReader()
r1.open(rosbag2_py.StorageOptions(uri=BAG, storage_id='sqlite3'),
        rosbag2_py.ConverterOptions('', 'cdr'))
while r1.has_next():
    topic, data, t = r1.read_next()
    if topic == '/tf_static':
        for tr in deserialize_message(data, types[topic]).transforms:
            if tr.header.frame_id == 'base_link' and tr.child_frame_id == 'velodyne':
                tr_ = tr.transform.translation
                q = tr.transform.rotation
                R = Rotation.from_quat([q.x, q.y, q.z, q.w]).as_matrix()
                vl = (np.array([tr_.x, tr_.y, tr_.z]), R)
                break
    if vl is not None:
        break
if vl is None:
    # 兜底：无 tf_static 就按文档 0.655
    vl = (np.array([0.0, 0.0, 0.655]), np.eye(3))
    print('tf_static 无 base_link->velodyne，用文档兜底 (0,0,0.655)')
else:
    print(f'base_link->velodyne 平移 = {vl[0]}')

# 主循环
t0 = None
odom_pose = (np.zeros(3), np.eye(3))  # 最新 odom->base_link
WINDOWS = {
    'S1 (0-115s) 摆箱观察': (0, 115),
    'S2 (125-132s)': (125, 132),
    'S3 (142-193s)': (142, 193),
    'S4 (200-206s)': (200, 206),
    'S5 (210-220s)': (210, 220),
    '动段D1 (115-125s)': (115, 125),
    '动段D2 (132-142s)': (132, 142),
    '动段D3 (193-200s)': (193, 200),
    '动段D4 (206-210s)': (206, 210),
    '动段D5 (220-224s)': (220, 224),
}
acc = {k: [] for k in WINDOWS}

def parse_pc2(msg):
    W = msg.point_step
    raw = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.width * msg.height, W)
    off = {f.name: f.offset for f in msg.fields}
    x = raw[:, off['x']:off['x']+4].copy().view(np.float32).ravel()
    y = raw[:, off['y']:off['y']+4].copy().view(np.float32).ravel()
    z = raw[:, off['z']:off['z']+4].copy().view(np.float32).ravel()
    return np.stack([x, y, z], axis=1)

frames = 0
while reader.has_next():
    topic, data, t = reader.read_next()
    if topic == '/tf':
        for tr in deserialize_message(data, types[topic]).transforms:
            if tr.header.frame_id == 'odom' and tr.child_frame_id == 'base_link':
                tr_ = tr.transform.translation
                q = tr.transform.rotation
                R = Rotation.from_quat([q.x, q.y, q.z, q.w]).as_matrix()
                odom_pose = (np.array([tr_.x, tr_.y, tr_.z]), R)
    elif topic == '/velodyne_points':
        if t0 is None:
            t0 = t
        sec = (t - t0) / 1e9
        frames += 1
        if frames % 2 != 0:  # ~5Hz
            continue
        for wname, (a, b) in WINDOWS.items():
            if a <= sec < b:
                pts = parse_pc2(deserialize_message(data, types[topic]))
                # velodyne -> base_link -> odom
                tb, Rb = odom_pose
                p_b = (pts - vl[0]) @ vl[1]          # velodyne->base_link (R 正交转置逆)
                p_o = p_b @ Rb.T + tb
                acc[wname].append(p_o)
                break

for wname, frames_ in acc.items():
    if not frames_:
        continue
    P = np.vstack(frames_)
    # 低带: odom z 0.05~0.35 (0.35 箱体在带内部分)，排除过高的环境物干扰后聚类
    m = (P[:, 2] > 0.03) & (P[:, 2] < 0.33)
    sel = P[m]
    print(f'\n[{wname}] 带内点 {len(sel)}/{len(P)}')
    if len(sel) < 30:
        continue
    gx = np.floor(sel[:, 0] / 0.15).astype(int)
    gy = np.floor(sel[:, 1] / 0.15).astype(int)
    keys = gx * 100000 + gy
    u, inv, cnt = np.unique(keys, return_inverse=True, return_counts=True)
    order = np.argsort(-cnt)
    print('  0.15m 格密度 top 10:')
    for idx in order[:10]:
        msk = inv == idx
        xs, ys, zs = sel[msk, 0], sel[msk, 1], sel[msk, 2]
        print(f'    中心=({xs.mean():.2f},{ys.mean():.2f}) z_top={np.percentile(zs,95):.2f} '
              f'z范围=[{zs.min():.2f},{zs.max():.2f}] n={cnt[idx]}')
