#!/usr/bin/env python3
"""测量 relog_0903_2104 中「高箱」实际顶面高度（z 剖面），交叉验证 /scan 光束角。

用法: python3 box_top_height.py <bag_dir>
只读 /velodyne_points；采样 = 时间等间隔帧（ros2-ops §5 纪律）。
输出: 每采样帧 右前箱区(2m/4m 档) 点云 z 分布 → 顶面 z → 箱高 = 顶面 - 地面。
"""
import sys
import numpy as np
from rclpy.serialization import deserialize_message
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from sensor_msgs.msg import PointCloud2, PointField

BAG = sys.argv[1] if len(sys.argv) > 1 else (
    "/home/lin/Lin_workspace/r2_integration/bags/raw/relog_0903_2104")

reader = SequentialReader()
reader.open(
    StorageOptions(uri=BAG, storage_id="sqlite3"),
    ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"))
topics = {t.name: t for t in reader.get_all_topics_and_types()}
tinfo = next(t for t in reader.get_all_topics_and_types() if t.name == "/velodyne_points")
assert tinfo.type == "sensor_msgs/msg/PointCloud2"

FIELD = {}
for f in [PointField.INT8, PointField.UINT8, PointField.INT16, PointField.UINT16,
          PointField.INT32, PointField.UINT32, PointField.FLOAT32, PointField.FLOAT64]:
    FIELD[f] = np.dtype({PointField.FLOAT32: np.float32,
                         PointField.FLOAT64: np.float64,
                         PointField.INT8: np.int8, PointField.UINT8: np.uint8,
                         PointField.INT16: np.int16, PointField.UINT16: np.uint16,
                         PointField.INT32: np.int32, PointField.UINT32: np.uint32}[f])

def read_cloud(msg):
    pc = deserialize_message(msg, PointCloud2)
    n = pc.width * pc.height
    buf = np.frombuffer(bytes(pc.data), dtype=np.uint8).reshape(n, pc.point_step)
    out = {}
    for f in pc.fields:
        out[f.name] = buf[:, f.offset:f.offset + FIELD[f.datatype].itemsize] \
            .view(FIELD[f.datatype]).reshape(n)
    return out

def z_profile(cloud, x0, x1, y0, y1):
    m = (cloud["x"] >= x0) & (cloud["x"] <= x1) & (cloud["y"] >= y0) & (cloud["y"] <= y1)
    return cloud["z"][m]

# 采样时刻（复盘稳定驻留窗内，时间等间隔）
win_2m = [(140, 178, 1.5, 2.5, -0.7, -0.05)]      # 2m 档箱区
win_4m = [(188, 220, 3.4, 4.5, -0.6, -0.05)]      # 4m 档箱区
win_clear = [(282, 283.2, 1.5, 2.5, -0.7, -0.05)]  # 收尾清空段（对照）

reader.seek(0)
t_start = None
targets = []
for (a, b, *box) in win_2m + win_4m + win_clear:
    targets.append((a, b, box, "2m档" if box[0] == 1.5 else ("4m档" if box[0] == 3.4 else "清空段")))
count = 0
last_print = -10.0
while reader.has_next():
    topic, msg, t = reader.read_next()
    if t_start is None:
        t_start = t
    ts = (t - t_start) / 1e9
    if topic == "/velodyne_points" and ts - last_print >= 0.8:
        for (a, b, box, name) in targets:
            if a <= ts <= b:
                last_print = ts
                c = read_cloud(msg)
                zs = z_profile(c, *box)
                if len(zs) > 50:
                    ground = np.percentile(zs, 2)
                    top = np.percentile(zs, 98)
                    print(f"t={ts:7.2f} {name} n={len(zs):6d} z_min~{ground:+.3f} z_top~{top:+.3f} h={top - ground:+.3f}m")
                break
        count += 1
print("done")
