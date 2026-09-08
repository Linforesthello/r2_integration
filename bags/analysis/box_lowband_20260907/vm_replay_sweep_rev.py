#!/usr/bin/env python3
"""box_TrendsParallel 反转重放：整包帧逆序发（A/B 用）。
正向 = 箱 1.0→2.1m 远离；逆序 = 箱 2.1m→1.5m→盲区 的「车接近」完整因果链：
  开段 = 箱静止 2.10m 3-ring 命中（mark 相）→ 中段 = 逐帧靠近 ring 递减 → 尾段(bag t<35.5)
        = 箱 <1.57m 全盲，points 无箱点而 scan 持续清（clear 相，复现 N97 归零因果）。
stamp 改写 wall now；best_effort；2× 加速。
"""
import sys, time
import numpy as np
import rosbag2_py
import rclpy
from sensor_msgs.msg import PointCloud2, LaserScan
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

BAG = "/home/lin/Lin_workspace/r2_integration/bags/raw/box_TrendsParallel_20260907_1056"
SPEEDUP = 2.0          # 2× 加速（原始 85.9s → ~43s）
TAIL_S = 8.0           # 播完后再等 N 秒（old 版清链/收敛）

class Replay(Node):
    def __init__(self):
        super().__init__('vm_sweep_rev_replay')
        qos = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT,
                         history=HistoryPolicy.KEEP_LAST, depth=5,
                         durability=DurabilityPolicy.VOLATILE)
        self.pub_pc = self.create_publisher(PointCloud2, '/velodyne_points', qos)
        self.pub_scan = self.create_publisher(LaserScan, '/scan', qos)

def open_reader():
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=BAG, storage_id="sqlite3"),
            rosbag2_py.ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"))
    return r

def main():
    rclpy.init()
    node = Replay()
    rd = open_reader()
    t2t = {m.name: m.type for m in rd.get_all_topics_and_types()}
    types = {'pc': get_message(t2t['/velodyne_points']), 'scan': get_message(t2t['/scan'])}
    t0 = None
    msgs = []          # (bag_sec, 'pc'|'scan', msg)
    while rd.has_next():
        topic, data, t = rd.read_next()
        if topic not in ('/velodyne_points', '/scan'):
            continue
        if t0 is None:
            t0 = t
        sec = (t - t0) / 1e9
        kind = 'pc' if topic == '/velodyne_points' else 'scan'
        msg = deserialize_message(data, types[kind])
        msgs.append((sec, kind, msg))
    msgs.sort(key=lambda x: -x[0])          # 逆序（尾帧在前）
    print(f"[load] {len(msgs)} 条（pc+scan），逆序播 2× 加速", flush=True)
    node.get_clock().sleep() if False else None
    # 以首条发出时刻为 T0，间隔按 bag 原始间距/SPEEDUP
    n = 0
    prev = None
    for sec, kind, msg in msgs:
        now = node.get_clock().now()
        msg.header.stamp = now.to_msg()
        if kind == 'pc':
            node.pub_pc.publish(msg)
        else:
            node.pub_scan.publish(msg)
        n += 1
        if prev is not None:
            dt = (prev - sec) / SPEEDUP     # 逆序相邻帧原始时间差
            if dt > 0:
                time.sleep(min(dt, 0.25))
        prev = sec
        if n % 400 == 0:
            print(f"[replay] {n} 条  bag_sec≈{sec:.1f}", flush=True)
    print(f"[replay] 播完 {n} 条（bag_sec≈{msgs[-1][0]:.1f} 盲区尾段），尾窗 {TAIL_S}s…", flush=True)
    time.sleep(TAIL_S)
    print("[replay] 完毕", flush=True)

if __name__ == "__main__":
    main()
