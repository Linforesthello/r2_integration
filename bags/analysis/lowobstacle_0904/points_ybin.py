#!/usr/bin/env python3
"""窄条 y 分布对照：x∈(1.7,2.1) 与 x∈(3.5,4.4) 内 points 按 y 0.05m 分桶计数 + z 层。
同时打印帧 frame_id/fields/point_step，及点云 x∈(0,5.5) 全 y 桶分布（看物体+墙）。
用法: source /opt/ros/humble/setup.bash && python3 points_ybin.py <t>
"""
import sys, math
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import PointCloud2

BAG = "/home/lin/Lin_workspace/r2_integration/bags/raw/relog_0903_2104"
T = float(sys.argv[1]) if len(sys.argv) > 1 else 150

def pc2(msg):
    n = msg.width * msg.height
    raw = np.frombuffer(bytes(msg.data), dtype=np.uint8).reshape(n, msg.point_step)
    out = np.empty((n, 4))
    for i, ax in enumerate(("x", "y", "z", "intensity")):
        for f in msg.fields:
            if f.name == ax and f.datatype == 7:
                seg = raw[:, f.offset:f.offset + 4].copy()
                out[:, i] = seg.view(np.float32).reshape(n)
    return out

def hg(pts, x0, x1, ymin=-1.0, ymax=1.0, zmin=-1.0, zmax=-0.05):
    sel = pts[(pts[:,0]>=x0)&(pts[:,0]<x1)&(pts[:,1]>=ymin)&(pts[:,1]<=ymax)&(pts[:,2]>=zmin)&(pts[:,2]<zmax)]
    if len(sel)==0:
        print(f"  x[{x0:.1f},{x1:.1f}) 地面层(z<-0.05): 0 点")
        return
    hist = {}
    for y in sel[:,1]:
        k = round(y*20)/20   # 0.05m
        hist[k] = hist.get(k,0)+1
    ks = sorted(hist)
    print(f"  x[{x0:.1f},{x1:.1f}) 地面层(z<-.05) n={len(sel)}")
    print("    y桶(0.05m): " + " ".join(f"{k:+.2f}:{hist[k]}" for k in ks if hist[k]>=3))

def main():
    st = rosbag2_py.StorageOptions(uri=BAG, storage_id="sqlite3")
    cv = rosbag2_py.ConverterOptions("", "")
    r = rosbag2_py.SequentialReader(); r.open(st, cv)
    r.set_filter(rosbag2_py.StorageFilter(topics=["/velodyne_points"]))
    t0=None; best=None
    while r.has_next():
        topic, data, t = r.read_next()
        if t0 is None: t0 = t
        el=(t-t0)/1e9
        if el >= T-0.1:
            best=(el,data); break
    el, data = best
    msg = deserialize_message(data, PointCloud2)
    print(f"t~{T}s 实际 {el:.2f}s  frame_id={msg.header.frame_id}  n={msg.width*msg.height}  "
          f"fields={[(f.name,f.offset,f.datatype) for f in msg.fields]}  point_step={msg.point_step}")
    pts = pc2(msg)
    # 全局：前方 x∈(0,5.5) 物体层(z在-0.8~0.3) y 分布
    sel = pts[(pts[:,0]>0)&(pts[:,0]<5.5)&(pts[:,2]>-0.9)&(pts[:,2]<0.5)]
    print(f"  前向 x<5.5 全 y 点(含墙) n={len(sel)}")
    for ymin,ymax,tag in [(-1.2,-0.5,'右远'),(-0.5,-0.15,'右'),(-0.15,0.15,'中'),(0.15,0.5,'左'),(0.5,1.2,'左远')]:
        m = sel[(sel[:,1]>=ymin)&(sel[:,1]<ymax)]
        if len(m): print(f"    y[{ymin:+.1f},{ymax:+.1f}) {tag}: {len(m)}点  质心x={m[:,0].mean():.2f} y={m[:,1].mean():+.2f} z={m[:,2].mean():+.2f}")
    # 物体窄条
    hg(pts, 1.7, 2.1)          # 2m 档箱位
    hg(pts, 3.5, 4.4, ymin=-0.6, ymax=0.6)  # 4m 档箱位

if __name__ == "__main__":
    main()
