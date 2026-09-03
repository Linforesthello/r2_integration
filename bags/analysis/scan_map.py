#!/usr/bin/env python3
"""单环 2D 建图：从 /velodyne_points 提取 ring=0 水平环 → 位姿变换 → 2D 栅格

原理:
  ring=0 是 VLP-16 最接近水平面的激光环（雷达系）
  每帧 ring0 点 (x,y) × /kiss/odometry 位姿 → 世界系 → 栅格累积
  天然 2D，无 z 滤波问题，等效 /scan 建图

用法: python3 scan_map.py <bag_dir> [输出.pgm] [分辨率=0.05] [占用阈值=3]
"""
import sys, math, bisect
sys.path.insert(0, '/home/lin/.local/lib/python3.10/site-packages')
import numpy as np
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import PointCloud2
from nav_msgs.msg import Odometry


def quat_to_matrix(qx, qy, qz, qw):
    x, y, z, w = qx, qy, qz, qw
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def main(bag_dir, out='map2d.pgm', res=0.05, thr=3):
    # 第一遍：位姿
    r = SequentialReader()
    r.open(StorageOptions(uri=bag_dir, storage_id='sqlite3'),
           ConverterOptions(input_serialization_format='cdr', output_serialization_format='cdr'))
    odoms = []
    while r.has_next():
        t, data, _ = r.read_next()
        if t != '/kiss/odometry':
            continue
        m = deserialize_message(data, Odometry)
        ts = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        p = m.pose.pose
        odoms.append((ts, quat_to_matrix(p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w),
                      np.array([p.position.x, p.position.y, p.position.z])))
    if not odoms:
        raise SystemExit('无 /kiss/odometry')
    ots = [o[0] for o in odoms]
    print(f'位姿 {len(odoms)} 帧')

    # 第二遍：提取 ring0 点并变换累积
    r = SequentialReader()
    r.open(StorageOptions(uri=bag_dir, storage_id='sqlite3'),
           ConverterOptions(input_serialization_format='cdr', output_serialization_format='cdr'))
    all_pts = []
    nf = 0
    while r.has_next():
        t, data, _ = r.read_next()
        if t != '/velodyne_points':
            continue
        m = deserialize_message(data, PointCloud2)
        n = m.width * m.height
        if n == 0:
            continue
        nf += 1
        if nf % 3 != 0:   # 抽稀：每 3 帧
            continue
        ps = m.point_step or 22
        arr = np.frombuffer(bytes(m.data), dtype=np.uint8)
        pts = arr.reshape(n, ps).copy()
        xyz = pts[:, :12].view(np.float32).reshape(n, 3)
        ring = pts[:, 16].astype(np.uint8)
        valid = np.isfinite(xyz).all(axis=1) & (ring == 0)
        if not valid.any():
            continue
        xy = xyz[valid, :2]
        # 位姿（时间对齐最近）
        ts = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        idx = min(bisect.bisect_left(ots, ts), len(odoms) - 1)
        _, R2, tvec = odoms[idx]
        R2d = R2[:2, :2]
        all_pts.append(xy @ R2d.T + tvec[:2])

    if not all_pts:
        raise SystemExit('无有效 ring0 点')
    xy = np.vstack(all_pts)
    print(f'累积 ring0 点 {len(xy)}（{nf} 帧/抽稀3）')

    # 栅格化
    x_min, y_min = xy.min(axis=0) - 1.0
    x_max, y_max = xy.max(axis=0) + 1.0
    w = int((x_max - x_min) / res)
    h = int((y_max - y_min) / res)
    grid = np.zeros((h, w), dtype=np.int32)
    ix = ((xy[:, 0] - x_min) / res).astype(int)
    iy = ((xy[:, 1] - y_min) / res).astype(int)
    np.add.at(grid, (np.clip(iy, 0, h-1), np.clip(ix, 0, w-1)), 1)
    occ = np.where(grid >= thr, 100, 0).astype(np.uint8)

    # 保存 PGM + YAML
    with open(out, 'wb') as f:
        f.write(b'P5\n%d %d\n255\n' % (w, h))
        f.write(occ.tobytes())
    yaml = (f"image: {out}\nresolution: {res}\norigin: [{x_min}, {y_min}, 0.0]\n"
            f"negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.25\n")
    open(out.replace('.pgm', '.yaml'), 'w').write(yaml)
    print(f'地图 {w}x{h} 格（{w*res:.1f}x{h*res:.1f}m）占用 {(occ==100).sum()} 格')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'map2d.pgm',
         float(sys.argv[3]) if len(sys.argv) > 3 else 0.05,
         int(sys.argv[4]) if len(sys.argv) > 4 else 3)
