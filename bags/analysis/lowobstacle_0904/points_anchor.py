#!/usr/bin/env python3
"""用 points(x,y,z) 锚定 scan 角度的左右：
取指定时刻的 /velodyne_points 帧，找车前方雷达水平面以下的物体点簇质心 (x,y)，
y>0 = 车体左侧(ROS x前y左)；同时算该质心的 atan2(y,x) 方位，对照 scan 同刻带号。
用法: source /opt/ros/humble/setup.bash && python3 points_anchor.py <t1,t2,...>
"""
import sys, math
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import PointCloud2

BAG = "/home/lin/Lin_workspace/r2_integration/bags/raw/relog_0903_2104"
TS = [float(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [150, 205, 250, 233]

def pc2_np(msg):
    """按 field offset/datatype 提取 x,y,z (float32) -> (n,3)"""
    n = msg.width * msg.height
    raw = np.frombuffer(bytes(msg.data), dtype=np.uint8).reshape(n, msg.point_step)
    out = np.empty((n, 3))
    for i, ax in enumerate(("x", "y", "z")):
        for f in msg.fields:
            if f.name == ax and f.datatype == 7:
                seg = raw[:, f.offset:f.offset + 4].copy()
                out[:, i] = seg.view(np.float32).reshape(n)
    return out

def main():
    st = rosbag2_py.StorageOptions(uri=BAG, storage_id="sqlite3")
    cv = rosbag2_py.ConverterOptions("", "")
    r = rosbag2_py.SequentialReader(); r.open(st, cv)
    r.set_filter(rosbag2_py.StorageFilter(topics=["/velodyne_points"]))
    t0 = None
    got = {t: None for t in TS}
    remaining = set(TS)
    while r.has_next() and remaining:
        topic, data, t = r.read_next()
        if t0 is None:
            t0 = t
        el = (t - t0) / 1e9
        for tg in list(remaining):
            if el >= tg - 0.15 and got[tg] is None:
                got[tg] = el
                remaining.discard(tg)
                break
    # 重新线性取帧：上面逻辑每目标扫到即存, 但已越过, 需二次遍历 —— 简化: 直接重开一次取最近帧
    # (一次遍历中保存每目标首帧, 上面 got 记录的是 el；重新开 reader 取对应 el 数据)
    # —— 更稳: 直接单趟存 [el, data] for el in got 需要数据本身 → 重开第二趟
    r2 = rosbag2_py.SequentialReader()
    r2.open(rosbag2_py.StorageOptions(uri=BAG, storage_id="sqlite3"), cv)
    r2.set_filter(rosbag2_py.StorageFilter(topics=["/velodyne_points"]))
    t0b = None; frames = {}
    while r2.has_next() and len(frames) < len(TS):
        topic, data, t = r2.read_next()
        if t0b is None: t0b = t
        el = (t - t0b) / 1e9
        for tg, tg_el in got.items():
            if tg_el is not None and abs(el - tg_el) < 0.2 and tg not in frames:
                frames[tg] = (el, data)
    for tg in sorted(frames):
        el, data = frames[tg]
        msg = deserialize_message(data, PointCloud2)
        pts = pc2_np(msg)
        print(f"\n=== t~{tg:.0f}s (实际 {el:.2f}s) points_n={len(pts)} ===")
        # 物体在雷达水平面下：z < -0.1（雷达离地约 0.65+0.12m 附近, 地面 z≈-0.7~-0.8）
        # 先看 z 直方图粗判地面位置
        z = pts[:, 2]
        zz = z[(z > -2) & (z < 2)]
        zc = np.percentile(zz, [5, 50, 95])
        print(f"  z p5/p50/p95 = {zc[0]:.2f}/{zc[1]:.2f}/{zc[2]:.2f}")
        # 物体点：前向 x 在 0.5~5.4m（车前空间），高于地面>0.05 但低于雷达面
        for xr in [(0.8, 2.6, "车前~2m区"), (3.0, 4.6, "车前~4m区")]:
            x0, x1, tag = xr
            sel = pts[(pts[:, 0] > x0) & (pts[:, 0] < x1) & (pts[:, 1] > -0.8) & (pts[:, 1] < 0.8)]
            if len(sel) == 0:
                print(f"  {tag}: 无点")
                continue
            # 区分地面与物：物=局部 z 高于该 x 处地面
            sel_z = sel[:, 2]
            zmin = np.percentile(sel_z, 20)   # 近地面层
            obj = sel[sel[:, 2] > zmin + 0.03]  # 高于地面 3cm
            if len(obj) == 0:
                print(f"  {tag}: 仅地面 {len(sel)}点 (zmin={zmin:.2f})")
                continue
            cx, cy = obj[:, 0].mean(), obj[:, 1].mean()
            az = math.degrees(math.atan2(cy, cx))
            print(f"  {tag}: 物点 {len(obj)}/{len(sel)}  质心(x={cx:.2f}, y={cy:+.2f}, z={obj[:,2].mean():.2f})"
                  f"  atan2方位={az:+.1f}°  -> y{'<0 右侧' if cy < 0 else '>0 左侧'}")

if __name__ == "__main__":
    main()
