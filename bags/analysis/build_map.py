#!/usr/bin/env python3
"""KISS-ICP 逐帧点云累积建图（方案B：位姿变换到世界系，标准 LiDAR 建图法）

原理:
  每帧 /kiss/frame（velodyne 系，全分辨率）
    × /kiss/odometry 位姿（odom_lidar→velodyne，时间对齐）
    → 变换到 odom_lidar 世界系 → 逐帧累积 = 全局稠密地图

用法: python3 build_map.py <bag_dir> [输出.ply] [抽稀间隔=5]
"""
import sys, math, bisect
sys.path.insert(0, '/home/lin/.local/lib/python3.10/site-packages')
import numpy as np
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import PointCloud2
from nav_msgs.msg import Odometry


def quat_to_matrix(qx, qy, qz, qw):
    """四元数 → 3x3 旋转矩阵（标准公式）"""
    x, y, z, w = qx, qy, qz, qw
    return np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - z*w),     2*(x*z + y*w)],
        [2*(x*y + z*w),     1 - 2*(x*x + z*z), 2*(y*z - x*w)],
        [2*(x*z - y*w),     2*(y*z + x*w),     1 - 2*(x*x + y*y)],
    ])


def read_odoms(bag_dir, topic='/kiss/odometry'):
    """第一遍：读全部位姿 (t, R(3x3), t_vec(3))"""
    r = SequentialReader()
    r.open(StorageOptions(uri=bag_dir, storage_id='sqlite3'),
           ConverterOptions(input_serialization_format='cdr', output_serialization_format='cdr'))
    odoms = []
    while r.has_next():
        t, data, _ = r.read_next()
        if t != topic:
            continue
        m = deserialize_message(data, Odometry)
        ts = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        p = m.pose.pose
        R = quat_to_matrix(p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w)
        odoms.append((ts, R, np.array([p.position.x, p.position.y, p.position.z])))
    return odoms


def build(bag_dir, every_n=5):
    odoms = read_odoms(bag_dir)
    if not odoms:
        raise SystemExit('bag 中无 /kiss/odometry')
    ots = [o[0] for o in odoms]
    print(f'位姿帧数: {len(odoms)}')

    r = SequentialReader()
    r.open(StorageOptions(uri=bag_dir, storage_id='sqlite3'),
           ConverterOptions(input_serialization_format='cdr', output_serialization_format='cdr'))
    pts_world = []
    n_frame = 0
    while r.has_next():
        t, data, _ = r.read_next()
        if t != '/kiss/frame':
            continue
        m = deserialize_message(data, PointCloud2)
        if m.height * m.width == 0:
            continue
        n_frame += 1
        if n_frame % every_n != 0:
            continue
        ts = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        # 时间对齐：最近位姿
        idx = bisect.bisect_left(ots, ts)
        idx = min(max(idx, 0), len(odoms) - 1)
        _, R, tvec = odoms[idx]
        # 解析点云 xyz（PointCloud2 标准布局，偏移 0/4/8，float32）
        n = m.width * m.height
        arr = np.frombuffer(bytes(m.data), dtype=np.uint8)
        xyz = arr.reshape(n, -1)[:, :12].copy().view(np.float32).reshape(n, 3)
        # 变换到世界系: p_world = R @ p_local + t
        pts_world.append(xyz @ R.T + tvec)
    if not pts_world:
        raise SystemExit('bag 中无 /kiss/frame')
    return np.vstack(pts_world), n_frame


def save_ply(path, xyz):
    with open(path, 'wb') as f:
        f.write(f"ply\nformat binary_little_endian 1.0\nelement vertex {len(xyz)}\n"
                "property float x\nproperty float y\nproperty float z\nend_header\n".encode())
        f.write(xyz.astype('<f4').tobytes())


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    bag = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else 'map_raw.ply'
    every = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    pts, nf = build(bag, every)
    print(f'累积 {len(pts)} 点（{nf} 帧 / 抽稀 {every}）')
    save_ply(out, pts)
    print(f'已保存 {out}')
