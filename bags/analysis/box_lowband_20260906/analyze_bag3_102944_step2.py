#!/usr/bin/env python3
"""bag3 (102944) step2：global 254 簇生命事件 + 车距演化 + velodyne 带内点对照
目标：实锤「靠近后黑块消失」的时刻与车距，定位 3 箱簇"""
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

BAG = '/home/lin/Lin_workspace/r2_integration/bags/raw/box_lowband_20260906_102944'

def open_bag():
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=BAG, storage_id='sqlite3'),
           rosbag2_py.ConverterOptions('', 'cdr'))
    t2t = {t.name: t.type for t in r.get_all_topics_and_types()}
    return r, {n: get_message(ty) for n, ty in t2t.items()}

# ---- 读 global costmap 254 簇 + 车轨迹 ----
r, types = open_bag()
t0 = None
rows = []   # (sec, [(mx,my,cnt)])
car = []    # (sec, ox, oy)
while r.has_next():
    topic, data, t = r.read_next()
    if t0 is None:
        t0 = t
    sec = (t - t0) / 1e9
    msg = deserialize_message(data, types[topic])
    if topic == '/global_costmap/costmap_raw':
        meta = msg.metadata
        ox, oy = meta.origin.position.x, meta.origin.position.y
        res = meta.resolution
        d = np.frombuffer(msg.data, dtype=np.uint8).reshape(meta.size_y, meta.size_x)
        cl = []
        ys, xs = np.nonzero(d == 254)
        if len(ys):
            keys = (np.floor(xs * res / 0.15).astype(int) * 100000) + np.floor(ys * res / 0.15).astype(int)
            u, inv, cnt = np.unique(keys, return_inverse=True, return_counts=True)
            for idx in np.nonzero(cnt >= 3)[0]:
                msk = inv == idx
                cl.append((ox + (xs[msk].mean() + 0.5) * res, oy + (ys[msk].mean() + 0.5) * res, cnt[idx]))
        rows.append((sec, cl))
    elif topic == '/tf':
        for tr in msg.transforms:
            if tr.header.frame_id == 'odom' and tr.child_frame_id == 'base_link':
                car.append((sec, tr.transform.translation.x, tr.transform.translation.y))

# ---- map->odom ----
r2, types2 = open_bag()
mo = None
while r2.has_next():
    topic, data, t = r2.read_next()
    if topic != '/tf':
        continue
    for tr in deserialize_message(data, types2[topic]).transforms:
        if tr.header.frame_id == 'map' and tr.child_frame_id == 'odom':
            mo = (tr.transform.translation.x, tr.transform.translation.y,
                  2 * np.arctan2(tr.transform.rotation.z, tr.transform.rotation.w))
            break
    if mo:
        break
mty, mtx, myaw = mo[1], mo[0], mo[2]
ct, st = np.cos(myaw), np.sin(myaw)

def odom2map(xo, yo):
    return (mtx + xo * ct - yo * st, mty + xo * st + yo * ct)

def dist_to_car(sec, mx, my):
    # 前后 1s 内车最近距离
    best = None
    for csec, xo, yo in car:
        if abs(csec - sec) > 1.5:
            continue
        xmo, ymo = odom2map(xo, yo)
        dd = np.hypot(xmo - mx, ymo - my)
        best = dd if best is None or dd < best else best
    return best

print(f'global 254 帧 {len(rows)}   map->odom yaw={np.degrees(myaw):.2f}° t=({mtx:.2f},{mty:.2f})')

# ---- 簇追踪（生命事件）----
track = {}
events = []
for sec, cl in rows:
    cur = {}
    for cx, cy, n in cl:
        key = None
        for k in list(track.keys()):
            ksec, kx, ky, _ = track[k]
            if (cx - kx) ** 2 + (cy - ky) ** 2 < 0.25:
                key = k
                break
        if key is None:
            key = 'c%d' % len(events)
        cur[key] = (cx, cy, n)
        track[key] = (sec, cx, cy, n)
    for k in list(track.keys()):
        if k not in cur:
            s, kx, ky, n = track[k]
            events.append((s, sec, kx, ky, n))
            del track[k]
for k, (s, kx, ky, n) in track.items():
    events.append((s, rows[-1][0], kx, ky, n))
events = [e for e in events if e[1] - e[0] > 2]
events.sort(key=lambda e: e[0])
print(f'\n=== 254 簇生命事件（持续>2s，共 {len(events)}）===')
for s, e2, kx, ky, n in events:
    dm = dist_to_car((s + e2) / 2, kx, ky)
    d_ap = dist_to_car(s, kx, ky)
    d_dp = dist_to_car(e2, kx, ky)
    print('  t=%6.1f~%6.1fs  map=(%5.2f,%5.2f)  格数~%3d  车距: 出现时%5.2fm 消失时%5.2fm' % (s, e2, kx, ky, n, d_ap or 0, d_dp or 0))
