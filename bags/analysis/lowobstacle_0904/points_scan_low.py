#!/usr/bin/env python3
"""points(z 层/ring) vs scan 对照 —— 低物盲区断点判定（方位已修正：-角=右前 y<0）

对窗口内每 ~0.5s 采样：
  1) /scan 右前 -20°~0° 最近距离
  2) /velodyne_points 前方 |方位|<=25°、x 0.6~4.5m 内，按 z 层计数:
       地面 z0(实测) / 矮层 (z0+0.03, z0+0.40] / 高层 (z0+0.40, z0+1.5]
     并区分 y<0(右) 与 y>=0(左)；矮层点统计 ring 集合与最近距离
判定: 纯矮簇(无高层伴随)存在 → 低物被雷达照到(points 有)；scan 同方位无 → 断点=转换层；
      矮簇也不存在 → 断点=物理照射层。
用法: bash -c "source /opt/ros/humble/setup.bash && python3 points_scan_low.py"
"""
import math
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import LaserScan, PointCloud2

BAG = "/home/lin/Lin_workspace/r2_integration/bags/raw/relog_0903_2104"
WIN = [(247.5, 258.8), (263.5, 277.8)]     # 低物候选窗口

def pc2(msg):
    n = msg.width * msg.height
    raw = np.frombuffer(bytes(msg.data), dtype=np.uint8).reshape(n, msg.point_step)
    cols = {}
    out = np.empty((n, 5))   # x,y,z,intensity,ring
    for f in msg.fields:
        if f.name == "ring" and f.datatype in (4, 6, 2):   # uint16/uint32/uint8
            seg = raw[:, f.offset:f.offset + 2].copy()
            cols["ring"] = seg.view(np.uint16).reshape(n).astype(np.float64)
        elif f.name in ("x", "y", "z", "intensity") and f.datatype == 7:
            seg = raw[:, f.offset:f.offset + 4].copy()
            cols[f.name] = seg.view(np.float32).reshape(n)
    if "ring" in cols:
        return np.column_stack([cols["x"], cols["y"], cols["z"], cols["intensity"], cols["ring"]])
    return np.column_stack([cols["x"], cols["y"], cols["z"], cols["intensity"], np.zeros(n)])

def scan_right(msg):
    """右前 -20°~0° 最近有限距离"""
    best = float("inf")
    for i, rv in enumerate(msg.ranges):
        if rv <= msg.range_min or rv >= msg.range_max: continue
        a = msg.angle_min + i * msg.angle_increment
        d = math.degrees(a)
        if -20 <= d < 0 and rv < best: best = rv
    return best if math.isfinite(best) else float("nan")

def main():
    st = rosbag2_py.StorageOptions(uri=BAG, storage_id="sqlite3")
    cv = rosbag2_py.ConverterOptions("", "")
    r = rosbag2_py.SequentialReader(); r.open(st, cv)
    r.set_filter(rosbag2_py.StorageFilter(topics=["/velodyne_points", "/scan"]))
    # 单趟收集目标帧（两话题时间对齐取 0.5s 采样最近对）
    t0 = None
    buf = {}
    frames = []
    want_next = WIN[0][0]
    wi = 0
    while r.has_next():
        topic, data, t = r.read_next()
        if t0 is None: t0 = t
        el = (t - t0) / 1e9
        # 越过当前窗尾 -> 切下一窗
        while wi < len(WIN) and el > WIN[wi][1]:
            wi += 1
            want_next = WIN[wi][0] if wi < len(WIN) else 1e9
        if wi >= len(WIN): break
        if el < WIN[wi][0] - 0.3: continue
        buf[topic] = (el, data)
        if "/scan" in buf and "/velodyne_points" in buf:
            # 采样: 与 scan 时间差 <0.15 才配对
            se, sd = buf["/scan"]; pe, pd = buf["/velodyne_points"]
            if abs(se - pe) < 0.15:
                frames.append((se, sd, pd))
                buf.clear()
                # 下一采样目标
                want_next = se + 0.6
            elif el > want_next:
                buf.clear()
    print(f"paired_frames={len(frames)}", file=open('/dev/stderr','w'))
    # z0 地面参考: 用第一帧取远处开阔地面 z 低端
    # 简化: 全点 z 的 2% 分位作为地面 z0 参考
    allz = []
    for _, sd, pd in frames[::3]:
        pts = pc2(deserialize_message(pd, PointCloud2))
        allz.append(pts[:, 2])
    z0 = np.percentile(np.concatenate(allz), 1.0)
    print(f"# z0(地面参考,全点z 1%分位)={z0:.2f}m  → 矮层(z0+0.03~z0+0.40)=[{z0+0.03:.2f},{z0+0.40:.2f}]  高层>{z0+0.40:.2f}")
    print("t(s)\tscan右前m\t右矮\t右高\t左矮\t左高\t右矮簇(方位°@距离m,n,ring,最高zm)")
    for se, sd, pd in frames:
        sm = deserialize_message(sd, LaserScan)
        pts = pc2(deserialize_message(pd, PointCloud2))
        srm = scan_right(sm)
        x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]
        ring = pts[:, 4]
        # 前方 |方位|<=25°, 距离 x 0.6~4.5
        az = np.degrees(np.arctan2(y, x))
        m = (x > 0.6) & (x < 4.5) & (np.abs(az) <= 25) & (np.abs(y) < 4.5 * 0.47)
        lo_hi = (z > z0 + 0.40) & (z < z0 + 1.5)
        hi_n = int(((m & lo_hi & (y < 0))).sum()), int(((m & lo_hi & (y >= 0))).sum())
        lowm = m & (z > z0 + 0.03) & (z <= z0 + 0.40)
        rl = lowm & (y < 0); ll = lowm & (y >= 0)
        rln, lln = int(rl.sum()), int(ll.sum())
        # 右矮簇：简单网格聚类(0.3m)
        desc = ""
        if rln > 3:
            xs, ys, zs, rs = x[rl], y[rl], z[rl], ring[rl]
            # 按 x 四舍五入0.3 聚类
            cl = {}
            for xi, yi, zi, ri in zip(xs, ys, zs, rs):
                k = (round(xi / 0.3), round(yi / 0.3))
                cl.setdefault(k, []).append((xi, yi, zi, ri))
            parts = []
            for k, p in cl.items():
                if len(p) < 3: continue
                px = [q[0] for q in p]; py = [q[1] for q in p]; pz = [q[2] for q in p]
                azc = math.degrees(math.atan2(np.mean(py), np.mean(px)))
                dz = np.mean([q[2] for q in p])
                rset = sorted(set(int(q[3]) for q in p))
                parts.append(f"{azc:+.0f}°@{np.mean(px):.2f}m,n={len(p)},r{min(rset)}-{max(rset)},z={dz:.2f}")
            desc = " | ".join(parts[:3])
        print(f"{se:6.2f}\t{srm:6.2f}\t{rln:5d}\t{hi_n[0]:5d}\t{lln:5d}\t{hi_n[1]:5d}\t{desc}")

if __name__ == "__main__":
    main()
