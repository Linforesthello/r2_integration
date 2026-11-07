#!/usr/bin/env python3
"""LaserScan 规格探针：抓 N 帧，打印波束数/角分辨率/量程/连续 NaN 段（角度裁剪带）。

用途：
- 新雷达接入或换固件后，实测 `/scan` 真实字段，不把驱动常量/消息字段当传感器规格；
- 验证驱动 angle crop（NaN 掩盖）是否生效、掩盖带在发布角坐标下的范围。

典型用法（目标机本地执行）：
    source /opt/ros/humble/setup.bash
    source ~/Lin_workspace/r2_integration/install/setup.bash
    python3 scripts/probe_laserscan.py --topic /scan --count 3

验收背景（2026-11-07 N97 LD06 实测）：
- beam 数逐帧变化（455/452/454），`angle_increment = 2π/(beam_size-1)` 由驱动反推；
- `range_max=25.0` 是驱动常量，不是 LD06 规格；
- crop 参数按**雷达原始角**（度）计算，而 `laser_scan_dir=true` 时发布角 = 360° − 原始角
  （同一裁剪带在发布侧呈镜像；见 ld06-dual-lidar.md P7）。

实现注意（2026-11-07 踩坑后定型）：
- **不要在订阅回调里调 rclpy.shutdown()**：Humble 单线程 executor 下会死锁；且 rclpy 安装了
  SIGINT/SIGTERM handler，外部 `timeout` 的 SIGTERM 也杀不死进程（实测卡 100s+）。
- 本脚本用 `spin_once` 轮询 + `os._exit(0)` 硬退出，绕开 shutdown 路径；外层仍建议
  `timeout -k 5 <秒>`（SIGKILL 兜底）。
- 只订阅、不修改任何节点；退出时不需要 ros2 daemon 清理（未调用 CLI）。
"""
import argparse
import math
import os
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan


class ScanProbe(Node):
    def __init__(self, topic, want, best_effort):
        super().__init__('laserscan_probe')
        self.msgs = []
        reliability = (ReliabilityPolicy.BEST_EFFORT if best_effort
                       else ReliabilityPolicy.RELIABLE)
        qos = QoSProfile(depth=10, reliability=reliability)
        self.create_subscription(LaserScan, topic, self.cb, qos)
        print(f'probe: subscribed {topic} ({"best_effort" if best_effort else "reliable"}), '
              f'waiting for {want} message(s) ...', flush=True)

    def cb(self, msg):
        self.msgs.append(msg)
        print(f'probe: got msg #{len(self.msgs)} len(ranges)={len(msg.ranges)}', flush=True)


def nan_runs(ranges):
    """返回连续 NaN 段的 (start, end) 索引列表。"""
    runs = []
    start = None
    for i, x in enumerate(ranges):
        if not math.isfinite(x):
            if start is None:
                start = i
        elif start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(ranges) - 1))
    return runs


def report(msgs, top_runs):
    for i, m in enumerate(msgs):
        ranges = list(m.ranges)
        n = len(ranges)
        incd = math.degrees(m.angle_increment)
        finite = sum(1 for x in ranges if math.isfinite(x))
        print(f'=== msg #{i} ===')
        print(f'frame_id            : {m.header.frame_id}')
        print(f'stamp               : {m.header.stamp.sec}.{m.header.stamp.nanosec:09d}')
        print(f'len(ranges)         : {n}')
        print(f'len(intensities)    : {len(m.intensities)}')
        print(f'angle_min (deg)     : {math.degrees(m.angle_min):.4f}')
        print(f'angle_max (deg)     : {math.degrees(m.angle_max):.4f}')
        print(f'angle_increment(deg): {incd:.4f}')
        print(f'(n-1)*inc (deg)     : {(n - 1) * incd:.4f}')
        print(f'time_increment (s)  : {m.time_increment:.9f}  ({1e3 * m.time_increment:.4f} ms)')
        if m.scan_time > 0:
            print(f'scan_time (s)       : {m.scan_time:.9f}  (implies {1 / m.scan_time:.3f} Hz)')
        else:
            print(f'scan_time (s)       : {m.scan_time}')
        print(f'range_min           : {m.range_min}')
        print(f'range_max           : {m.range_max}')
        print(f'finite range count  : {finite}  (nan/inf: {n - finite})')
        finite_vals = [x for x in ranges if math.isfinite(x)]
        if finite_vals:
            print(f'finite range min/max: {min(finite_vals):.3f} / {max(finite_vals):.3f} m')
        runs = sorted(nan_runs(ranges), key=lambda r: r[1] - r[0], reverse=True)
        if runs and top_runs > 0:
            print(f'contiguous NaN runs (top {top_runs}, published angle = index * angle_increment):')
            for a, b in runs[:top_runs]:
                print(f'  idx {a:4d}..{b:4d}  bins={b - a + 1:4d}  '
                      f'angle {a * incd:7.2f}..{(b + 1) * incd:7.2f} deg  '
                      f'width={(b - a + 1) * incd:6.2f} deg')
        print()

    lens = [len(m.ranges) for m in msgs]
    incs = {round(math.degrees(m.angle_increment), 6) for m in msgs}
    print('len consistency     :', lens, ' all_equal =', len(set(lens)) == 1)
    print('angle_increment set :', sorted(incs), 'deg')
    stamps = [m.header.stamp.sec + m.header.stamp.nanosec * 1e-9 for m in msgs]
    if len(stamps) >= 2:
        deltas = [stamps[i + 1] - stamps[i] for i in range(len(stamps) - 1)]
        print('stamp deltas (ms)   :', [f'{d * 1e3:.2f}' for d in deltas])


def main():
    parser = argparse.ArgumentParser(description='LaserScan 规格探针')
    parser.add_argument('--topic', default='/scan', help='LaserScan 话题（默认 /scan）')
    parser.add_argument('--count', type=int, default=3, help='抓取帧数（默认 3）')
    parser.add_argument('--timeout', type=float, default=15.0, help='等待超时秒数（默认 15）')
    parser.add_argument('--nan-runs', type=int, default=5,
                        help='每帧打印最长的 N 个连续 NaN 段（0=不打印，默认 5）')
    parser.add_argument('--best-effort', action='store_true',
                        help='以 best_effort 订阅（默认 reliable，匹配常见驱动发布端）')
    args = parser.parse_args()

    rclpy.init()
    node = ScanProbe(args.topic, args.count, args.best_effort)
    deadline = time.monotonic() + args.timeout
    while len(node.msgs) < args.count and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.2)

    if not node.msgs:
        print('NO MESSAGE RECEIVED', flush=True)
        sys.stdout.flush()
        os._exit(2)

    report(node.msgs, args.nan_runs)
    sys.stdout.flush()
    os._exit(0)


if __name__ == '__main__':
    main()
