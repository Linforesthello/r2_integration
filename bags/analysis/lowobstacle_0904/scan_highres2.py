#!/usr/bin/env python3
"""修正版聚段：0.1m 距离档跳变>=0.3m 即断段，同一驻留段内距离单一稳定。
输出：稳定驻留段表 = (起止, 带°, 档0.1m精确值, 稳定度)。直接对应一次「放置」。
外加每带每 1s 的 0.1m 数值时间线（关键带打印），供精读。"""
import sys, math
import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import LaserScan

BAG = "/home/lin/Lin_workspace/r2_integration/bags/raw/relog_0903_2104"
NB = 30
def band_index(a):
    d = math.degrees(a)
    if d >= 15 or d < -15: return None
    return int(d) + 15

def main():
    st = rosbag2_py.StorageOptions(uri=BAG, storage_id="sqlite3")
    cv = rosbag2_py.ConverterOptions("", "")
    r = rosbag2_py.SequentialReader(); r.open(st, cv)
    t0 = None; series = []
    while r.has_next():
        topic, data, t = r.read_next()
        if topic != "/scan": continue
        if t0 is None: t0 = t
        el = (t - t0) / 1e9
        m = deserialize_message(data, LaserScan)
        band = [float("inf")] * NB
        for i in range(len(m.ranges)):
            rv = m.ranges[i]
            if rv <= m.range_min or rv >= m.range_max: continue
            k = band_index(m.angle_min + i * m.angle_increment)
            if k is not None and rv < band[k]: band[k] = rv
        series.append((el, band))
    # 基准
    base = [float("inf")] * NB
    for _, b in series:
        for k in range(NB):
            if math.isfinite(b[k]) and (not math.isfinite(base[k]) or b[k] > base[k]):
                base[k] = b[k]
    # 逐带：档跳变断段（0.3m），驻留>=1.0s 才算
    print("# 稳定驻留段表（档跳变>0.3m 断段；驻留>=1.0s；平均与最近均 0.1m 档）")
    print("起止(s)\t时长\t带°\t平均m\t最近m\t基准m")
    for k in range(NB):
        if not math.isfinite(base[k]): continue
        thr = base[k] - 0.5
        segs = []; cur = None
        for el, b in series:
            d = b[k]
            occl = math.isfinite(d) and d <= thr
            if occl:
                d10 = round(d, 1)
                if cur is None:
                    cur = [el, el, [d10], d]
                elif abs(d10 - (sum(cur[2]) / len(cur[2]))) > 0.3:
                    segs.append(cur); cur = [el, el, [d10], d]
                else:
                    cur[1] = el; cur[2].append(d10)
                    if d < cur[3]: cur[3] = d
            elif cur is not None:
                if el - cur[1] > 0.4:   # 断开超过 0.4s -> 收段
                    segs.append(cur); cur = None
        if cur is not None: segs.append(cur)
        for t0s, t1s, ds, dmin in segs:
            if t1s - t0s >= 1.0:
                davg = sum(ds) / len(ds)
                print(f"{t0s:6.1f}~{t1s:6.1f}\t{t1s - t0s:5.1f}\t{k - 14.5:+7.1f}\t{davg:6.2f}\t{dmin:6.2f}\t{base[k]:5.2f}")

if __name__ == "__main__":
    main()
