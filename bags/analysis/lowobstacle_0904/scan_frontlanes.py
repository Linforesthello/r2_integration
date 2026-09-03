#!/usr/bin/env python3
"""车头前方窄带全程时间线：每 2s 打印 0°±20° 五个 5° 窄带的最近距离"""
import math
import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import LaserScan

BAG = "/home/lin/Lin_workspace/r2_integration/bags/raw/relog_0903_2104"
BANDS = [(-5, 5), (-10, -5), (5, 10), (-15, -10), (10, 15), (-20, -15), (15, 20)]

storage = rosbag2_py.StorageOptions(uri=BAG, storage_id="sqlite3")
conv = rosbag2_py.ConverterOptions("", "")
r = rosbag2_py.SequentialReader()
r.open(storage, conv)
start_t = None
rows = {}
while r.has_next():
    topic, data, t = r.read_next()
    if topic != "/scan":
        continue
    if start_t is None:
        start_t = t
    el = (t - start_t) / 1e9
    m = deserialize_message(data, LaserScan)
    bands = {}
    for lo, hi in BANDS:
        best = float("inf")
        for i, rv in enumerate(m.ranges):
            if rv <= m.range_min or rv >= m.range_max:
                continue
            a = math.degrees(m.angle_min + i * m.angle_increment)
            a = (a + 180) % 360 - 180
            if lo <= a < hi and rv < best:
                best = rv
        bands[(lo, hi)] = best
    key = int(el // 2) * 2
    rows.setdefault(key, [None] * len(BANDS))
    for j, (lo, hi) in enumerate(BANDS):
        v = bands[(lo, hi)]
        if math.isfinite(v):
            rows[key][j] = v if rows[key][j] is None else min(rows[key][j], v)

print("t(s) | 0±5°  -5~-10  +5~+10  -10~-15  +10~+15  -15~-20  +15~+20")
for k in sorted(rows):
    vals = [f"{v:6.2f}" if v is not None else "    ." for v in rows[k]]
    print(f"{k:4d} | " + "  ".join(vals))
