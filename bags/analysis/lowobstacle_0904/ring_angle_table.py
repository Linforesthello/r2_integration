#!/usr/bin/env python3
"""收尾清空段(≥279.6s)每环实测垂直角表：/velodyne_points ring -> asin(z/R)。

用途: 经验验证 ring 编号 -> 垂直角 映射（对照 calibration.cpp 升序重映射 + VLP16db）。
"""
import numpy as np
from rclpy.serialization import deserialize_message
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from sensor_msgs.msg import PointCloud2, PointField

DT = {int(k): np.dtype(v) for k, v in {
    PointField.INT8: np.int8, PointField.UINT8: np.uint8, PointField.INT16: np.int16,
    PointField.UINT16: np.uint16, PointField.INT32: np.int32, PointField.UINT32: np.uint32,
    PointField.FLOAT32: np.float32, PointField.FLOAT64: np.float64}.items()}

def rd(msg):
    pc = deserialize_message(msg, PointCloud2)
    n = pc.width * pc.height
    b = np.frombuffer(bytes(pc.data), dtype=np.uint8).reshape(n, pc.point_step)
    o = {}
    for f in pc.fields:
        o[f.name] = b[:, f.offset: f.offset + DT[int(f.datatype)].itemsize] \
            .view(DT[int(f.datatype)]).reshape(n)
    return o

r = SequentialReader()
r.open(StorageOptions(uri="/home/lin/Lin_workspace/r2_integration/bags/raw/relog_0903_2104",
                      storage_id="sqlite3"),
       ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"))
t0 = None
res = {}
while r.has_next():
    topic, msg, t = r.read_next()
    if t0 is None:
        t0 = t
    ts = (t - t0) / 1e9
    if topic == "/velodyne_points" and 279.6 <= ts <= 283.3:
        c = rd(msg)
        R = np.hypot(c["x"], c["y"])
        m = (R > 1.5) & (R < 5.6)
        for ring in range(16):
            sel = m & (c["ring"] == ring)
            if sel.sum() > 10:
                res.setdefault(ring, []).extend(
                    np.degrees(np.arcsin(c["z"][sel] / R[sel])).tolist())
print("ring | 实测中位垂直角(deg) | n")
for ring in sorted(res):
    a = np.array(res[ring])
    print(f"{ring:3d}  | {np.median(a):+6.2f}  | {len(a)}")
