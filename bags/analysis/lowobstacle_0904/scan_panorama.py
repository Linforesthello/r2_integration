#!/usr/bin/env python3
"""scan 360° 全景：10° 桶最近距离（人走开尾段 vs 开场），供现场方位对齐"""
import math, sys
import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import LaserScan

BAG = "/home/lin/Lin_workspace/r2_integration/bags/raw/relog_0903_2104"
TARGETS = [5.0, 275.0]

storage = rosbag2_py.StorageOptions(uri=BAG, storage_id="sqlite3")
conv = rosbag2_py.ConverterOptions("", "")
r = rosbag2_py.SequentialReader()
r.open(storage, conv)
start_t = None
got = {t: None for t in TARGETS}
while r.has_next() and any(v is None for v in got.values()):
    topic, data, t = r.read_next()
    if topic != "/scan":
        continue
    if start_t is None:
        start_t = t
    el = (t - start_t) / 1e9
    for tg in TARGETS:
        if got[tg] is None and abs(el - tg) <= 0.2:
            got[tg] = (el, deserialize_message(data, LaserScan))

def bucket_min(msg, b_deg, w=5.0):
    best = float("inf")
    for i, rv in enumerate(msg.ranges):
        if rv <= msg.range_min or rv >= msg.range_max:
            continue
        a = math.degrees(msg.angle_min + i * msg.angle_increment)
        a = (a + 180) % 360 - 180
        if abs(a - b_deg) <= w:
            best = min(best, rv)
    return best

for tg in TARGETS:
    el, msg = got[tg]
    print(f"\n===== t={tg}s (实际 {el:.1f}s) 每 10° 桶最近距离 =====")
    print("角度(°) 距离(m) | 角度(°) 距离(m) | 角度(°) 距离(m)")
    centers = list(range(-170, 180, 10))
    for i in range(0, len(centers), 3):
        row = []
        for c in centers[i:i+3]:
            d = bucket_min(msg, c)
            row.append(f"{c:+5d}  {d:7.2f}")
        print("  ".join(row))
