#!/usr/bin/env python3
"""relog_0903_2104 三层断点分析 · 第一阶段：1s 时间线

读 /scan + /local_costmap/costmap_raw + /odometry/filtered，逐秒输出：
  - costmap_raw: 254(=lethal) / 253 格计数
  - scan: 前方 ±60° 最近距离（m）、全角最近距离
  - odom: x/y（静止验证）
输出到 stdout，供识别箱子各距离段（1m/2m/4m/5m）与低物测试时刻候选窗。

用法: bash -c "source /opt/ros/humble/setup.bash && python3 analyze_relog_layers.py <bag_dir>"
"""
import sys
import math

import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import LaserScan
from nav2_msgs.msg import Costmap
from nav_msgs.msg import Odometry

BAG = sys.argv[1] if len(sys.argv) > 1 else \
    "/home/lin/Lin_workspace/r2_integration/bags/raw/relog_0903_2104"
FRONT = math.pi / 3  # 前方扇区 ±60°

TYPE_MAP = {
    "/scan": (LaserScan, "/scan"),
    "/local_costmap/costmap_raw": (Costmap, "/local_costmap/costmap_raw"),
    "/odometry/filtered": (Odometry, "/odometry/filtered"),
}

def open_reader(bag):
    storage = rosbag2_py.StorageOptions(uri=bag, storage_id="sqlite3")
    conv = rosbag2_py.ConverterOptions("", "")
    r = rosbag2_py.SequentialReader()
    r.open(storage, conv)
    topics = {}
    for t in r.get_all_topics_and_types():
        topics[t.name] = t.type
    return r, topics

def scan_front_min(msg):
    """前方 ±60° 有限 range 最小值（angle 归一到 [-pi,pi)）"""
    n = len(msg.ranges)
    if n == 0:
        return float("nan")
    inc = msg.angle_increment
    best = float("inf")
    for i in range(n):
        if msg.ranges[i] <= msg.range_min or msg.ranges[i] >= msg.range_max:
            continue
        a = msg.angle_min + i * inc
        a = (a + math.pi) % (2 * math.pi) - math.pi   # -> [-pi, pi)
        if abs(a) <= FRONT:
            if msg.ranges[i] < best:
                best = msg.ranges[i]
    return best if math.isfinite(best) else float("nan")

def count_marks(msg):
    """raw Costmap data: 254 / 253 格计数（未膨胀图里 254=lethal）"""
    c254 = c253 = 0
    for v in msg.data:
        if v == 254:
            c254 += 1
        elif v == 253:
            c253 += 1
    return c254, c253

def main():
    r, topics = open_reader(BAG)
    start_t = None
    bin_d = {}   # elapsed_sec(int) -> dict
    while r.has_next():
        topic, data, t = r.read_next()
        if topic not in TYPE_MAP:
            continue
        if start_t is None:
            start_t = t
        el = int((t - start_t) / 1_000_000_000)
        b = bin_d.setdefault(el, {"s": [], "r": None, "o": None})
        if topic == "/scan":
            msg = deserialize_message(data, LaserScan)
            b["s"].append(scan_front_min(msg))
        elif topic == "/local_costmap/costmap_raw":
            msg = deserialize_message(data, Costmap)
            c254, c253 = count_marks(msg)
            b["r"] = (c254, c253)
        else:
            msg = deserialize_message(data, Odometry)
            b["o"] = (msg.pose.pose.position.x, msg.pose.pose.position.y)
    # 输出时间线
    print(f"# t(s)\tscanN\tfront_min(m)\tall_min(m)\traw254\traw253\todom_x\todom_y")
    for el in sorted(bin_d):
        b = bin_d[el]
        s = b["s"]
        fm = min(s) if s else float("nan")
        allm = float("nan")
        r254 = r253 = 0
        if b["r"] is not None:
            r254, r253 = b["r"]
        ox = oy = 0.0
        if b["o"] is not None:
            ox, oy = b["o"]
        print(f"{el:4d}\t{len(s):3d}\t{fm:8.3f}\t{allm:8.3f}\t{r254:4d}\t{r253:4d}\t{ox:8.3f}\t{oy:8.3f}")

if __name__ == "__main__":
    main()
