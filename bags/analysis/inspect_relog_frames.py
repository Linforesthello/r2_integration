#!/usr/bin/env python3
"""relog_0903_2104 第二阶段探查：scan 帧结构 + costmap_raw 254/253 格空间分布

1) 取若干时刻的 /scan 帧：打印 angle 参数/range 参数/长度；按 16 方位扇区打印最近距离
   -> 定位「0.5m 持续返回」的方位与距离档（箱子各档）
2) 取对应时刻 /local_costmap/costmap_raw 快照：254/253 格世界坐标 -> 简单网格聚类簇
   -> 区分恒定簇（车周?）与箱子簇（何时出现/消失）
3) 对照 /local_costmap/costmap (OccupancyGrid)

用法: bash -c "source /opt/ros/humble/setup.bash && python3 inspect_relog_frames.py <bag_dir> <t1,t2,...>"
"""
import sys
import math
import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import LaserScan
from nav2_msgs.msg import Costmap
from nav_msgs.msg import OccupancyGrid

BAG = sys.argv[1] if len(sys.argv) > 1 else \
    "/home/lin/Lin_workspace/r2_integration/bags/raw/relog_0903_2104"
TS = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [5, 60, 120, 160, 200, 240, 275]

TYPES = {
    "/scan": LaserScan,
    "/local_costmap/costmap_raw": Costmap,
    "/local_costmap/costmap": OccupancyGrid,
}

def clusterize(cells, step):
    """极简网格聚类：cells=[(x,y)]，返回 [(cx,cy,n,minx,maxx,miny,maxy)]"""
    grid = {}
    for x, y in cells:
        key = (int(x / step), int(y / step))
        grid.setdefault(key, []).append((x, y))
    clusters = []
    used = set()
    for k, pts in grid.items():
        if k in used:
            continue
        # 8 邻域合并
        stack = [k]
        grp = list(pts)
        used.add(k)
        while stack:
            gx, gy = stack.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nk = (gx + dx, gy + dy)
                    if nk in grid and nk not in used:
                        used.add(nk)
                        grp.extend(grid[nk])
                        stack.append(nk)
        xs = [p[0] for p in grp]
        ys = [p[1] for p in grp]
        clusters.append((sum(xs) / len(xs), sum(ys) / len(ys), len(grp),
                         min(xs), max(xs), min(ys), max(ys)))
    clusters.sort(key=lambda c: -c[2])
    return clusters

def cells_of_vals(msg, vals):
    """raw Costmap(或OccupancyGrid) data 中取值 in vals 的格世界坐标"""
    # 统一把 data 转字节/数值数组
    try:
        md = msg.metadata
    except AttributeError:
        md = msg.info
    # metadata 字段名兜底
    if hasattr(md, "origin"):
        ox = getattr(md.origin, "x", 0.0)
        oy = getattr(md.origin, "y", 0.0)
    else:
        ox = oy = 0.0
    sx = md.size_x if hasattr(md, "size_x") else md.width
    sy = md.size_y if hasattr(md, "size_y") else md.height
    res = md.resolution
    n = len(msg.data)
    out = []
    step = max(1, n // sy)  # OccupancyGrid data 行主序，raw Costmap 也按行主序假设
    for i, v in enumerate(msg.data):
        if v in vals:
            col = i % sx
            row = i // sx
            out.append((ox + (col + 0.5) * res, oy + (row + 0.5) * res))
    return out

def main():
    storage = rosbag2_py.StorageOptions(uri=BAG, storage_id="sqlite3")
    conv = rosbag2_py.ConverterOptions("", "")
    r = rosbag2_py.SequentialReader()
    r.open(storage, conv)
    start_t = None
    want = set(TS)
    got = {t: {} for t in TS}
    # 按目标时刻收集最近的前后帧
    while r.has_next() and want:
        topic, data, t = r.read_next()
        if topic not in TYPES:
            continue
        if start_t is None:
            start_t = t
        el = (t - start_t) / 1e9
        # 取离目标 0.25s 内的帧
        for tg in list(want):
            if abs(el - tg) <= 0.25:
                got[tg][topic] = (el, data)
        # 去掉已集齐的时刻
        for tg in list(want):
            if len(got[tg]) == 3:
                want.remove(tg)
    # ---- scan 打印 ----
    print("## scan 帧结构（所选时刻）")
    for tg in TS:
        if "/scan" not in got[tg]:
            continue
        el, data = got[tg]["/scan"]
        m = deserialize_message(data, LaserScan)
        print(f"\nt={tg:>3}s (实际 {el:.2f}s): angle_min={m.angle_min:.4f} angle_max={m.angle_max:.4f} "
              f"inc={m.angle_increment:.5f} n={len(m.ranges)} range_min={m.range_min:.2f} range_max={m.range_max:.1f}")
        # 16 方位扇区最近距离
        print("   方位(deg) 最近(m): ", end="")
        for s in range(16):
            a0 = -math.pi + s * (2 * math.pi / 16)
            a1 = a0 + 2 * math.pi / 16
            best = float("inf")
            for i, rv in enumerate(m.ranges):
                if rv <= m.range_min or rv >= m.range_max:
                    continue
                a = m.angle_min + i * m.angle_increment
                a = (a + math.pi) % (2 * math.pi) - math.pi
                if a0 <= a < a1 and rv < best:
                    best = rv
            print(f"{math.degrees(a0):6.0f}:{best:6.2f}", end="  ")
        print()
    # ---- costmap 254/253 分布 ----
    print("\n## costmap_raw 254/253 簇（世界坐标，聚类步长 0.1m）")
    for tg in TS:
        if "/local_costmap/costmap_raw" not in got[tg]:
            continue
        el, data = got[tg]["/local_costmap/costmap_raw"]
        m = deserialize_message(data, Costmap)
        c254 = cells_of_vals(m, {254})
        c253 = cells_of_vals(m, {253})
        k254 = clusterize(c254, 0.1)
        k253 = clusterize(c253, 0.2)
        print(f"\nt={tg:>3}s: 254格={len(c254)} 253格={len(c253)}")
        print("  254 簇 top5 (cx,cy,n,范围):")
        for c in k254[:5]:
            print(f"    ({c[0]:.2f},{c[1]:.2f}) n={c[2]:4d} x[{c[3]:.2f},{c[4]:.2f}] y[{c[5]:.2f},{c[6]:.2f}]")
        print("  253 簇 top3 (cx,cy,n):")
        for c in k253[:3]:
            print(f"    ({c[0]:.2f},{c[1]:.2f}) n={c[2]:5d} x[{c[3]:.2f},{c[4]:.2f}] y[{c[5]:.2f},{c[6]:.2f}]")

if __name__ == "__main__":
    main()
