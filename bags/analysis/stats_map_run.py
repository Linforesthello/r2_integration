#!/usr/bin/env python3
"""统计 map_run_0809_2133：验证重影根因假设（点数/车速/帧间位移/帧间隔）

统计项:
  1. /kiss/frame 每帧点数分布 + 各距离段(<5m,5-10m,10-20m,>20m)点数占比
  2. /kiss/odometry 帧间隔分布 + 帧间位移(平移 m / 旋转 °)分布
  3. /cmd_vel 速度分布(线速 m/s / 角速 rad/s) —— 是否"快速转移"
  4. 大空窗(>0.5s)期间位移 —— 空窗期运动量

用法: python3 stats_map_run.py <bag_dir>
"""
import sys, math, bisect
sys.path.insert(0, '/home/lin/.local/lib/python3.10/site-packages')
import numpy as np
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import PointCloud2
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist


def q_to_yaw(qx, qy, qz, qw):
    return math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))


def pct(v, lo, hi):
    return f'{np.percentile(v, lo):.2f}~{np.percentile(v, hi):.2f}'


def main(bag_dir):
    # ---- 1. kiss/frame 点数 + 距离段 ----
    r = SequentialReader()
    r.open(StorageOptions(uri=bag_dir, storage_id='sqlite3'),
           ConverterOptions(input_serialization_format='cdr', output_serialization_format='cdr'))
    npts, seg = [], []
    while r.has_next():
        t, data, _ = r.read_next()
        if t != '/kiss/frame':
            continue
        m = deserialize_message(data, PointCloud2)
        n = m.width * m.height
        if n == 0:
            continue
        npts.append(n)
        ps = m.point_step or 22
        arr = np.frombuffer(bytes(m.data), dtype=np.uint8).reshape(n, ps)
        xyz = arr[:, :12].view(np.float32).reshape(n, 3)
        valid = np.isfinite(xyz).all(axis=1)
        if not valid.any():
            seg.append((0, 0, 0, 0))
            continue
        d = np.linalg.norm(xyz[valid, :2], axis=1)
        nv = len(d)
        seg.append(((d < 5).sum() / nv, ((d >= 5) & (d < 10)).sum() / nv,
                    ((d >= 10) & (d < 20)).sum() / nv, (d >= 20).sum() / nv))
    npts = np.array(npts)
    seg = np.array(seg) * 100
    print('=== 1. /kiss/frame 每帧点数 ===')
    print(f'  帧数 {len(npts)} | 点数/帧: min={npts.min()} p25={np.percentile(npts,25):.0f} '
          f'p50={np.percentile(npts,50):.0f} p75={np.percentile(npts,75):.0f} max={npts.max()}')
    print(f'  距离段占比%: <5m {seg[:,0].mean():.1f} | 5-10m {seg[:,1].mean():.1f} '
          f'| 10-20m {seg[:,2].mean():.1f} | >20m {seg[:,3].mean():.1f}')

    # ---- 2. kiss/odometry 帧间隔 + 帧间位移 ----
    r = SequentialReader()
    r.open(StorageOptions(uri=bag_dir, storage_id='sqlite3'),
           ConverterOptions(input_serialization_format='cdr', output_serialization_format='cdr'))
    t_od, p_od, y_od = [], [], []
    while r.has_next():
        t, data, _ = r.read_next()
        if t != '/kiss/odometry':
            continue
        m = deserialize_message(data, Odometry)
        ts = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        pp = m.pose.pose.position
        t_od.append(ts)
        p_od.append([pp.x, pp.y, pp.z])
        o = m.pose.pose.orientation
        y_od.append(q_to_yaw(o.x, o.y, o.z, o.w))
    t_od = np.array(t_od); p_od = np.array(p_od); y_od = np.array(y_od)
    dt = np.diff(t_od)
    disp = np.linalg.norm(np.diff(p_od, axis=0), axis=1)
    dyaw = np.abs(np.diff(np.unwrap(y_od))) * 180 / math.pi
    print('\n=== 2. /kiss/odometry 帧间隔与帧间位移 ===')
    print(f'  位姿帧数 {len(t_od)} | 时长 {t_od[-1]-t_od[0]:.1f}s | 平均帧率 {len(t_od)/(t_od[-1]-t_od[0]):.2f}Hz')
    print(f'  帧间隔 dt:   p50={np.percentile(dt,50)*1000:.0f}ms p90={np.percentile(dt,90)*1000:.0f}ms '
          f'p99={np.percentile(dt,99)*1000:.0f}ms max={dt.max()*1000:.0f}ms | >0.5s 共 {(dt>0.5).sum()} 处')
    print(f'  帧间位移:    p50={np.percentile(disp,50)*100:.1f}cm p90={np.percentile(disp,90)*100:.1f}cm '
          f'p99={np.percentile(disp,99)*100:.1f}cm max={disp.max()*100:.1f}cm')
    print(f'  帧间转角:    p50={np.percentile(dyaw,50):.2f}° p90={np.percentile(dyaw,90):.2f}° '
          f'p99={np.percentile(dyaw,99):.2f}° max={dyaw.max():.2f}°')

    # 大空窗期间的位移（相邻两帧间）
    big = dt > 0.5
    print(f'  >0.5s 空窗期间帧间位移: p50={np.percentile(disp[big],50)*100:.1f}cm '
          f'p90={np.percentile(disp[big],90)*100:.1f}cm max={disp[big].max()*100:.1f}cm '
          f'(共 {big.sum()} 处, 中位位移 {np.median(disp[big])/np.median(disp):.1f}x 普通帧)')

    # ---- 3. cmd_vel 速度 ----
    r = SequentialReader()
    r.open(StorageOptions(uri=bag_dir, storage_id='sqlite3'),
           ConverterOptions(input_serialization_format='cdr', output_serialization_format='cdr'))
    vx, wz = [], []
    while r.has_next():
        t, data, _ = r.read_next()
        if t != '/cmd_vel':
            continue
        m = deserialize_message(data, Twist)
        vx.append(m.linear.x)
        wz.append(m.angular.z)
    vx = np.array(vx); wz = np.array(wz)
    print('\n=== 3. /cmd_vel 速度 ===')
    if len(vx):
        print(f'  指令帧数 {len(vx)}')
        print(f'  线速度 |vx|:  p50={np.percentile(np.abs(vx),50):.2f} p90={np.percentile(np.abs(vx),90):.2f} '
              f'max={np.abs(vx).max():.2f} m/s | 非零率 {(np.abs(vx)>0.01).mean()*100:.0f}%')
        print(f'  角速度 |wz|:  p50={np.percentile(np.abs(wz),50):.2f} p90={np.percentile(np.abs(wz),90):.2f} '
              f'max={np.abs(wz).max():.2f} rad/s | 非零率 {(np.abs(wz)>0.01).mean()*100:.0f}%')
        print(f'  快速转移段(>0.3m/s 或 >0.5rad/s): 时长占比 {((np.abs(vx)>0.3)|(np.abs(wz)>0.5)).mean()*100:.0f}%')
    else:
        print('  无 /cmd_vel')


if __name__ == '__main__':
    main(sys.argv[1])
