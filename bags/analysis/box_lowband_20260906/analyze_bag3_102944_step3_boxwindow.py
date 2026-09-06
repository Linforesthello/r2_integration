#!/usr/bin/env python3
"""bag3 (102944) step3（定点判据，产出 §8.2 曲线）：
对候选箱 map 坐标逐帧统计 global costmap_raw 箱区 ±0.3m 窗内 254 格数 + 最近车距。
用法：改 CAND 候选位置，输出 = 箱区 254 随车距衰减曲线（定位"丢黑块临界距离"）。
判据：254 随车距单调降到 0 = 近距几何视锥盲区（mark 输入归零）+ 同层 clear 清空。
关联：retrospect 2026-09-06 §8.2（机制表：B1 归零 @~1.4m，B2/B3 部分保留）
"""
import math
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

BAG = '/home/lin/Lin_workspace/r2_integration/bags/raw/box_lowband_20260906_102944'
# map 系候选箱位（来自早期静止段 velodyne 簇 + 车起点换算；B4 高箱位未命中）
CAND = {
    'B1(低)': (3.63, -0.27),
    'B2(低,大反射)': (3.73, 0.63),
    'B3(低)': (4.38, 0.16),
    'B4(高?)': (4.60, -0.60),
}

def open_bag():
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=BAG, storage_id='sqlite3'),
           rosbag2_py.ConverterOptions('', 'cdr'))
    t2t = {t.name: t.type for t in r.get_all_topics_and_types()}
    return r, {n: get_message(ty) for n, ty in t2t.items()}

def yaw_of_qz(qz, qw):
    return 2 * math.atan2(qz, qw)

r, types = open_bag()
t0 = None
cars = []     # (sec, map_x, map_y)
gm_rows = []  # (sec, costmap_uint8, origin_x, origin_y, res, (mo_x,mo_y,mo_yaw))
mo = None
while r.has_next():
    topic, data, ts = r.read_next()
    if t0 is None:
        t0 = ts
    sec = (ts - t0) / 1e9
    msg = deserialize_message(data, types[topic])
    if topic == '/tf':
        for tr in msg.transforms:
            if tr.header.frame_id == 'map' and tr.child_frame_id == 'odom':
                mo = (tr.transform.translation.x, tr.transform.translation.y,
                      yaw_of_qz(tr.transform.rotation.z, tr.transform.rotation.w))
            elif tr.header.frame_id == 'odom' and tr.child_frame_id == 'base_link' and mo:
                ox, oy = tr.transform.translation.x, tr.transform.translation.y
                c, s = math.cos(mo[2]), math.sin(mo[2])
                cars.append((sec, mo[0] + ox * c - oy * s, mo[1] + ox * s + oy * c))
    elif topic == '/global_costmap/costmap_raw' and mo:
        meta = msg.metadata
        d = np.frombuffer(msg.data, dtype=np.uint8).reshape(meta.size_y, meta.size_x)
        gm_rows.append((sec, d.copy(), meta.origin.position.x, meta.origin.position.y,
                        meta.resolution, mo))

print('gm 帧 %d, 车点 %d' % (len(gm_rows), len(cars)))
for name, (mx, my) in CAND.items():
    print('\n=== %s map(%.2f,%.2f) ===' % (name, mx, my))
    prev = -1
    for sec, d, ox, oy, res, mo in gm_rows[::2]:
        r0 = int((my - 0.3 - oy) / res); r1 = int((my + 0.3 - oy) / res)
        c0 = int((mx - 0.3 - ox) / res); c1 = int((mx + 0.3 - ox) / res)
        r0, r1 = max(r0, 0), min(r1, d.shape[0])
        c0, c1 = max(c0, 0), min(c1, d.shape[1])
        n254 = int((d[r0:r1, c0:c1] == 254).sum()) if (r1 > r0 and c1 > c0) else 0
        if n254 != prev:
            best = min((np.hypot(cx - mx, cy - my) for (cs, cx, cy) in cars if abs(cs - sec) < 1.5), default=-1)
            print('  t=%6.1fs 254=%4d 车距=%5.2fm' % (sec, n254, best))
            prev = n254
