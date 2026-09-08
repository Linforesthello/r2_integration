#!/usr/bin/env python3
"""boxfix_dbl_20260908_1836 t3：静态地图 ASCII 轮廓 + 静止窗低带点云找箱（map 系）
找箱法复用 09-06 step1：高度带 0.05-0.42m(vel z∈[-0.725,-0.355]) + 0.1m 密度簇；
本版把簇投影到 map 系并滤紧凑 bbox(<0.8m) 排除墙体长条"""
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

BAG = '/home/lin/Lin_workspace/r2_integration/bags/boxfix_dbl_20260908_1836'
T0 = 1788863802741155504

def open_bag():
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=BAG, storage_id='sqlite3'),
           rosbag2_py.ConverterOptions('', 'cdr'))
    t2t = {t.name: t.type for t in r.get_all_topics_and_types()}
    return r, {n: get_message(ty) for n, ty in t2t.items()}

r, types = open_bag()
tf_o2b, tf_m2o = [], []
map_msg = None
vel_wins = {'w0': (0, 60), 'w1': (160.5, 170.5), 'w2': (178, 193), 'w3': (206.5, 229)}
vel_buf = {k: [] for k in vel_wins}
while r.has_next():
    topic, data, t = r.read_next()
    sec = (t - T0) / 1e9
    msg = deserialize_message(data, types[topic])
    if topic == '/tf':
        for tr in msg.transforms:
            q = tr.transform.rotation
            yaw = np.arctan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
            v = (sec, tr.transform.translation.x, tr.transform.translation.y, yaw)
            if tr.header.frame_id == 'odom' and tr.child_frame_id == 'base_link':
                tf_o2b.append(v)
            elif tr.header.frame_id == 'map' and tr.child_frame_id == 'odom':
                tf_m2o.append(v)
    elif topic == '/map':
        map_msg = msg
    elif topic == '/velodyne_points':
        for name, (a, b) in vel_wins.items():
            if a <= sec <= b:
                vel_buf[name].append((sec, msg))

# ---- 地图 ASCII ----
mg = map_msg
res = mg.info.resolution
ox, oy = mg.info.origin.position.x, mg.info.origin.position.y
d = np.frombuffer(mg.data, dtype=np.int8).reshape(mg.info.height, mg.info.width)
# 走廊范围：x∈[0.5,6.5], y∈[-1.6,2.4] → 粗 0.1m 格
print(f'=== 静态地图 res={res} {mg.info.width}x{mg.info.height} origin=({ox:.2f},{oy:.2f}) 值: {np.unique(d, return_counts=True)}')
X0, X1, Y0, Y1 = 0.5, 6.5, -1.6, 2.4
cs = int((X1 - X0) / 0.1); rs = int((Y1 - Y0) / 0.1)
lines = []
for rr in range(rs):
    line = ''
    for cc in range(cs):
        wx, wy = X0 + cc*0.1, Y1 - rr*0.1
        i = int((wx - ox) / res); j = int((wy - oy) / res)
        if 0 <= i < mg.info.width and 0 <= j < mg.info.height:
            v = d[j, i]
            line += '#' if v >= 50 else (' ' if v < 0 else '.')
        else:
            line += '?'
    lines.append(f'{wy:5.2f} {line}')
print('x 轴: 每字符 0.1m, 行标签 = y (顶部为大 y)')
for ln in reversed(lines):
    print(ln)

# ---- 找箱：静止窗低带簇 → map 系 ----
def interp(t, arr):
    a = np.array(arr)
    if not len(a) or t <= a[0, 0]: return a[0, 1:]
    if t >= a[-1, 0]: return a[-1, 1:]
    i = np.searchsorted(a[:, 0], t)
    w = (t - a[i-1, 0]) / (a[i, 0] - a[i-1, 0])
    return a[i-1, 1:] * (1 - w) + a[i, 1:] * w

def rot(p, yaw):
    c, s = np.cos(yaw), np.sin(yaw)
    return np.array([c*p[0]-s*p[1], s*p[0]+c*p[1]])

print('\n=== 静止窗低带(0.05-0.42m)找箱（map 系紧凑簇 top5）===')
for name, (a, b) in vel_wins.items():
    frames = vel_buf[name]
    if not frames:
        print(f'  [{name} {a}~{b}s] 无帧'); continue
    acc = []
    for sec, msg in frames:
        W = msg.point_step
        raw = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.width*msg.height, W)
        off = {f.name: f.offset for f in msg.fields}
        x = raw[:, off['x']:off['x']+4].copy().view(np.float32).ravel()
        y = raw[:, off['y']:off['y']+4].copy().view(np.float32).ravel()
        z = raw[:, off['z']:off['z']+4].copy().view(np.float32).ravel()
        m = (z > -0.725) & (z < -0.355) & (np.hypot(x, y) < 7.0)
        if not m.any():
            continue
        ob = interp(sec, tf_o2b); mo = interp(sec, tf_m2o)
        for xv, yv in zip(x[m], y[m]):
            p_od = rot(np.array([xv, yv]), ob[2]) + np.array([ob[0], ob[1]])
            p_m = rot(p_od, mo[2]) + np.array([mo[0], mo[1]])
            acc.append(p_m)
    if not acc:
        print(f'  [{name} {a}~{b}s] 低带无点'); continue
    P = np.vstack(acc)
    gx = np.floor(P[:, 0] / 0.1).astype(int); gy = np.floor(P[:, 1] / 0.1).astype(int)
    keys = gx * 10000 + gy
    u, inv, cnt = np.unique(keys, return_inverse=True, return_counts=True)
    order = np.argsort(-cnt)
    print(f'  [{name} {a}~{b}s] 低带点 {len(P)} 簇 top5:')
    for idx in order[:8]:
        msk = inv == idx
        if cnt[idx] < 8:
            continue
        xs, ys = P[msk, 0], P[msk, 1]
        bx = (xs.max() - xs.min()); by = (ys.max() - ys.min())
        if bx > 0.9 or by > 0.9:   # 长条=墙/管线，滤
            continue
        print(f'    心=({xs.mean():5.2f},{ys.mean():5.2f}) 尺寸 {bx:.2f}x{by:.2f}m 帧点n={cnt[idx]}')
