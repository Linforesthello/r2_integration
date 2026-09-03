#!/usr/bin/env python3
"""0.1s × 1° × 0.1m 逐帧过程回放。
- 遍历全部 /scan 帧(~101ms)，每帧解前向 ±15° 30 带最近距离(0.1m 档)。
- 打印：帧间任一带变化>=0.1m 的动态帧全打；静止(无变化)连续>=1s 压缩为锚行。
- 附：帧级细段表（遮挡相对基准>=0.5m；档跳变>0.3m 断段；驻留>=0.4s）。
输出重定向到文件。
用法: bash -c "source /opt/ros/humble/setup.bash && python3 scan_process.py [bag] > out 2>err"
"""
import sys, math
import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import LaserScan

BAG = "/home/lin/Lin_workspace/r2_integration/bags/raw/relog_0903_2104"
NB = 30

def bi(a):
    d = math.degrees(a)
    return int(d) + 15 if -15 <= d < 15 else None

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
            k = bi(m.angle_min + i * m.angle_increment)
            if k is not None and rv < band[k]: band[k] = rv
        series.append((el, band))
    n = len(series)
    print(f"frames={n} span={series[-1][0]-series[0][0]:.2f}s dt_med={np_med_dt(series):.4f}s", file=sys.stderr)
    # ---- 帧级逐帧回放 ----
    print(f"# t(s) | 30带距离 [{-14.5:+.1f}°..{+14.5:+.1f}°] ('.'=无有效返回/inf)")
    quiet = 0.0; quiet_cnt = 0
    def fmt(b):
        return " ".join("." if not math.isfinite(v) else f"{v:.1f}" for v in b)
    for i, (el, b) in enumerate(series):
        if i == 0:
            print(f"{el:7.2f} | {fmt(b)}")
            continue
        prev = series[i-1][1]
        diffs = []
        for k in range(NB):
            a, c = prev[k], b[k]
            if math.isfinite(a) and math.isfinite(c):
                diffs.append(abs(c - a))
            elif math.isfinite(a) != math.isfinite(c):
                diffs.append(9.9)      # inf 出入 = 结构出现/消失，视为大变化
        chg = max(diffs) if diffs else 0.0
        if chg >= 0.1:
            if quiet_cnt > 0:
                print(f"...[静止 {quiet_cnt*0.1:.1f}s]")
                quiet_cnt = 0
            print(f"{el:7.2f} | {fmt(b)}")
        else:
            quiet_cnt += 1
    # ---- 帧级细段表 ----
    base = [float("inf")] * NB
    for _, b in series:
        for k in range(NB):
            if math.isfinite(b[k]) and (not math.isfinite(base[k]) or b[k] > base[k]):
                base[k] = b[k]
    print("\n# 帧级细段表(驻留>=0.4s, 档跳变>0.3m 断段, 容缺<=0.2s)")
    print("起止(s)\t时长\t带°\t平均m\t最近m")
    for k in range(NB):
        if not math.isfinite(base[k]): continue
        thr = base[k] - 0.5
        segs = []; cur = None; last_occl = None
        for el, b in series:
            d = b[k]; occl = math.isfinite(d) and d <= thr
            if occl:
                d10 = round(d, 1)
                if cur is None:
                    cur = [el, el, [d10], d]
                elif last_occl is not None and el - last_occl <= 0.2 and abs(d10 - sum(cur[2])/len(cur[2])) <= 0.3:
                    cur[1] = el; cur[2].append(d10)
                    if d < cur[3]: cur[3] = d
                else:
                    segs.append(cur); cur = [el, el, [d10], d]
                last_occl = el
            elif cur is not None:
                if last_occl is not None and el - last_occl > 0.2:
                    segs.append(cur); cur = None
                # else 短缺口内继续等
        if cur is not None: segs.append(cur)
        for a, b2, ds, dm in segs:
            if b2 - a >= 0.4:
                print(f"{a:7.2f}~{b2:7.2f}\t{b2-a:5.2f}\t{k-14.5:+6.1f}\t{sum(ds)/len(ds):6.2f}\t{dm:6.2f}")

def np_med_dt(series):
    dts = sorted(series[i][0]-series[i-1][0] for i in range(1, len(series)))
    return dts[len(dts)//2]

if __name__ == "__main__":
    main()
