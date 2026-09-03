#!/usr/bin/env python3
"""relog_0903_2104 精解析重跑：前向 ±15°，1° 角带 × 0.1m 距离档，全帧（10Hz 不抽稀）

输出 1: ASCII 轮廓热图 —— 行=1° 带（-15..+15），列=1s，格字符=该秒该带最近距离档：
        '.'=≥5.0m(含尽端墙5.42/开阔)  '5'=4.5-4.9  '4'=3.5-4.4  '3'=3.0-3.4  '2'=2.0-2.9  '1'=1.0-1.9  '0'=<1.0
输出 2: 遮挡事件表 —— 每个(1°带)相对自身开阔基准(带内全程最大值)收窄≥0.5m、
        连续驻留≥0.8s(容缺≤0.3s)的段：平均距离(0.1m)、起止时刻。箱子/人/矮物事件的精确定位依据。

用法: bash -c "source /opt/ros/humble/setup.bash && python3 scan_highres.py [bag_dir]"
"""
import sys
import math

import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import LaserScan

BAG = sys.argv[1] if len(sys.argv) > 1 else \
    "/home/lin/Lin_workspace/r2_integration/bags/raw/relog_0903_2104"
NB = 30          # ±15°，每 1° 一带

def band_index(a):
    """归一化角度(rad) -> 带号。带 k 覆盖 [-15+k, -14+k) 度"""
    d = math.degrees(a)
    if d >= 15 or d < -15:
        return None
    return int(d) + 15          # -15..-14 -> 0 ... 14..15 -> 29

def main():
    storage = rosbag2_py.StorageOptions(uri=BAG, storage_id="sqlite3")
    conv = rosbag2_py.ConverterOptions("", "")
    r = rosbag2_py.SequentialReader()
    r.open(storage, conv)

    t0 = None
    series = []                  # (el_float, [30] 带最近有效距离 or inf)
    while r.has_next():
        topic, data, t = r.read_next()
        if topic != "/scan":
            continue
        if t0 is None:
            t0 = t
        el = (t - t0) / 1e9
        m = deserialize_message(data, LaserScan)
        band = [float("inf")] * NB
        n = len(m.ranges)
        for i in range(n):
            rv = m.ranges[i]
            if rv <= m.range_min or rv >= m.range_max:
                continue
            a = m.angle_min + i * m.angle_increment
            k = band_index(a)
            if k is not None and rv < band[k]:
                band[k] = rv
        series.append((el, band))
    print(f"frames={len(series)}  t_end={series[-1][0]:.2f}s", file=sys.stderr)

    # ---- 各带开阔基准 = 带内全程最大有限距离 ----
    base = [float("inf")] * NB
    for _, b in series:
        for k in range(NB):
            if math.isfinite(b[k]) and (not math.isfinite(base[k]) or b[k] > base[k]):
                base[k] = b[k]

    # ---- 输出 1: ASCII 轮廓热图（1s/列，分 3 段）----
    def ch(d):
        if not math.isfinite(d) or d >= 5.0:
            return "."
        if d >= 4.5: return "5"
        if d >= 3.5: return "4"
        if d >= 3.0: return "3"
        if d >= 2.0: return "2"
        if d >= 1.0: return "1"
        return "0"
    n_sec = int(series[-1][0]) + 1
    per_sec = [[float("inf")] * NB for _ in range(n_sec)]
    for el, b in series:
        s = int(el)
        if s < n_sec:
            for k in range(NB):
                if b[k] < per_sec[s][k]:
                    per_sec[s][k] = b[k]
    print("\n## ASCII 轮廓（行=1°带；列=1s；.≥5m / 5=4.5-4.9 / 4=3.5-4.4 / 3=3.0-3.4 / 2=2.0-2.9 / 1=1.0-1.9 / 0=<1.0）")
    for seg in range(4):
        lo, hi = seg * 75, min((seg + 1) * 75, n_sec)
        if lo >= n_sec:
            break
        print(f"--- {lo:3d}s~{hi:3d}s（行标为该秒十秒位与个秒位，可对行数定位秒） ---")
        tick = "      " + "".join(
            str((s % 100) // 10) if (s % 100) % 10 == 0 else " " for s in range(lo, hi))
        unit = "      " + "".join(str(s % 10) if (s % 10) in (0, 5) else " " for s in range(lo, hi))
        print(tick)
        print(unit)
        for k in range(NB):
            ang = k - 14.5
            row = "".join(ch(per_sec[s][k]) for s in range(lo, hi))
            print(f"{ang:+6.1f} {row}")

    # ---- 输出 2: 遮挡事件表（游标聚段，容缺 0.3s）----
    print(f"\n## 遮挡事件表（各带基准收窄≥0.5m 且驻留≥0.8s；平均距离已取 0.1m 档）")
    print(f"# 各带开阔基准(m): " + " ".join(
        f"{k - 14.5:+5.1f}:{base[k]:.2f}" for k in range(NB) if math.isfinite(base[k])))
    print("起止(s)\t时长\t带°\t基准m\t平均m\t最近m")
    events = []
    for k in range(NB):
        if not math.isfinite(base[k]):
            continue
        thr = base[k] - 0.5
        cur = None
        last_t = None
        for el, b in series:
            d = b[k]
            occl = math.isfinite(d) and d <= thr
            if occl:
                if cur is None:
                    cur = [el, el, d, 1, d]
                else:
                    cur[1] = el; cur[2] += d; cur[3] += 1
                    if d < cur[4]: cur[4] = d
                last_t = el
            elif cur is not None:
                if el - last_t > 0.3:
                    events.append((cur[0], cur[1], k, cur[2] / cur[3], cur[4]))
                    cur = None
        if cur is not None:
            events.append((cur[0], cur[1], k, cur[2] / cur[3], cur[4]))
    events.sort()
    for t0, t1, k, davg, dmin in events:
        if t1 - t0 < 0.8:
            continue
        print(f"{t0:6.1f}~{t1:6.1f}\t{t1 - t0:5.1f}\t{k - 14.5:+6.1f}\t{base[k]:5.2f}\t{davg:6.2f}\t{dmin:6.2f}")

if __name__ == "__main__":
    main()
