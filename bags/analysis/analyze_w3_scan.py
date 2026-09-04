#!/usr/bin/env python3
"""W3 bag（1357/1401/1405）·/scan 层障碍可见性对账 —— 复盘 §六-4 / closing §五 #2。

约束（先验，ros2-ops §9.3）：W3 三 bag 未录 costmap 系列 → "costmap_raw 有无 254/100"
无法直接读，本脚本对账其可对部分 = 候选解释 a（W3 障碍是否低矮/低于 /scan 光带）：
若障碍在 /scan 层被稳定返回至贴近距离（<1.5m），结合单环 +1° 光带高度表（复盘 §十-3：
光带离地 ≈ H + d·tan1°，H≈0.7~0.8m → @0.5m≈0.78~0.88m），可裁定障碍高度口径。

用法: python3 analyze_w3_scan.py <bag1> [bag2 ...]
输出: 每 bag 时间轴上「障碍段」（前向 ±20° 最近距离显著收窄）事件表 + 最近距离统计。
"""
import sys
import numpy as np
from rclpy.serialization import deserialize_message
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from sensor_msgs.msg import LaserScan

def scan_analysis(path):
    r = SequentialReader()
    r.open(StorageOptions(uri=path, storage_id="sqlite3"),
           ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"))
    t0 = None
    rows = []
    while r.has_next():
        topic, msg, t = r.read_next()
        if topic != "/scan":
            continue
        if t0 is None:
            t0 = t
        s = deserialize_message(msg, LaserScan)
        n = len(s.ranges)
        ang = np.linspace(s.angle_min, s.angle_min + n * s.angle_increment, n)[:n]
        rr = np.array(s.ranges, dtype=np.float64)
        fin = np.isfinite(rr)
        # 前向 ±20°（与 09-03 复盘同口径）
        m = fin & (np.abs(np.degrees(ang)) <= 20.0)
        front = rr[m]
        # 全向 90th 分位 = 开阔基准的保守替代（有墙环境）
        base = np.percentile(rr[fin], 90) if fin.sum() else np.inf
        near = front.min() if front.size else np.inf
        rows.append(((t - t0) / 1e9, near, base))
    ts = np.array([x[0] for x in rows])
    near = np.array([x[1] for x in rows])
    base = np.array([x[2] for x in rows])
    # 障碍段 = 前向最近 < min(3.5, 0.55*基准中位) 且持续 ≥1.2s
    thresh = min(3.5, 0.55 * np.median(base))
    seg = near < thresh
    print(f"\n== {path.split('/')[-1]} ==  scan帧={len(ts)}  开阔基准中位={np.median(base):.2f}m  障碍判定阈值={thresh:.2f}m")
    print(f"   最近距离: min={near.min():.2f}m  分位 P10/P50/P90={np.percentile(near,[10,50,90]).round(2)}m  "
          f"<1.5m 帧占比={(near<1.5).mean()*100:.1f}%  <0.8m 帧占比={(near<0.8).mean()*100:.1f}%")
    # 障碍段切片（合并 <0.8s 间隙）
    ev = []
    start = None
    for i, b in enumerate(seg):
        if b and start is None:
            start = i
        elif not b and start is not None:
            if ts[i - 1] - ts[start] >= 1.2:
                ev.append((ts[start], ts[i - 1], near[start:i].min()))
            start = None
    if start is not None and ts[-1] - ts[start] >= 1.2:
        ev.append((ts[start], ts[-1], near[start:].min()))
    print(f"   障碍驻留段(≥1.2s) {len(ev)} 段:")
    for a, b, m2 in ev[:14]:
        print(f"     {a:7.1f}~{b:7.1f}s  {b-a:5.1f}s  段内最近={m2:.2f}m")
    return rows

for p in sys.argv[1:]:
    scan_analysis(p)
print("\ndone")
