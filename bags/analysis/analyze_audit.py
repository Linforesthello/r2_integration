#!/usr/bin/env python3
"""D0 定量基线分析（官方 rosbag2_py）
指标: 三源(轮速/EKF/KISS)轨迹对比、yaw 三源逐帧、静止漂移、跳变检测
用法: python3 analyze_audit.py <bag_dir>
"""
import sys, math, bisect
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import Imu
from nav_msgs.msg import Odometry


def quat_to_yaw(w, x, y, z):
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def main(bag_dir):
    r = SequentialReader()
    r.open(StorageOptions(uri=bag_dir, storage_id='sqlite3'),
           ConverterOptions(input_serialization_format='cdr', output_serialization_format='cdr'))
    wheels, ekf, kiss, imu = [], [], [], []
    while r.has_next():
        topic, data, _ = r.read_next()
        if topic == '/odom_wheels':
            m = deserialize_message(data, Odometry)
            t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
            p = m.pose.pose
            wheels.append((t, p.position.x, p.position.y,
                           quat_to_yaw(p.orientation.w, p.orientation.x, p.orientation.y, p.orientation.z)))
        elif topic == '/odometry/filtered':
            m = deserialize_message(data, Odometry)
            t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
            p = m.pose.pose
            ekf.append((t, p.position.x, p.position.y, p.position.z,
                        quat_to_yaw(p.orientation.w, p.orientation.x, p.orientation.y, p.orientation.z)))
        elif topic == '/kiss/odometry':
            m = deserialize_message(data, Odometry)
            t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
            p = m.pose.pose
            kiss.append((t, p.position.x, p.position.y,
                         quat_to_yaw(p.orientation.w, p.orientation.x, p.orientation.y, p.orientation.z)))
        elif topic == '/imu/data':
            m = deserialize_message(data, Imu)
            t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
            o = m.orientation
            imu.append((t, quat_to_yaw(o.w, o.x, o.y, o.z)))

    t0 = wheels[0][0]
    dur = wheels[-1][0] - t0
    print(f"=== 基线数据: {dur:.1f}s ===")
    print(f"帧数: 轮速 {len(wheels)} / EKF {len(ekf)} / KISS {len(kiss)} / IMU {len(imu)}")

    # 1. 静止段（前 30s）漂移
    for name, data in (("轮速", wheels), ("EKF", ekf), ("KISS", kiss)):
        seg = [d for d in data if d[0] - t0 < 30]
        if len(seg) > 2:
            dx = seg[-1][1] - seg[0][1]
            dy = seg[-1][2] - seg[0][2]
            dyaw = (seg[-1][3] - seg[0][3] + math.pi) % (2 * math.pi) - math.pi
            print(f"静止30s漂移 {name}: Δxy={math.hypot(dx, dy)*100:.1f}cm  Δyaw={dyaw*180/math.pi:.2f}°")

    # 2. 三源 yaw 对比（每 2s 采样）
    print("\n=== yaw 三源对比（每2s采样）===")
    print(f"{'t(s)':>6} {'轮速°':>8} {'IMU°':>8} {'EKF°':>8} {'轮速-IMU°':>10} {'EKF-IMU°':>9}")
    ts = [i[0] for i in imu]
    for k in range(0, int(dur), 2):
        t = t0 + k
        def yaw_at(data, yidx=3):
            idx = bisect.bisect_left([d[0] for d in data], t)
            idx = min(max(idx, 0), len(data) - 1)
            return data[idx][yidx]
        wy = yaw_at(wheels); iy = yaw_at(imu, yidx=1); ey = yaw_at(ekf, yidx=4)
        d1 = (wy - iy + math.pi) % (2 * math.pi) - math.pi
        d2 = (ey - iy + math.pi) % (2 * math.pi) - math.pi
        print(f"{k:>6} {wy*180/math.pi:>8.1f} {iy*180/math.pi:>8.1f} {ey*180/math.pi:>8.1f} "
              f"{d1*180/math.pi:>10.1f} {d2*180/math.pi:>9.1f}")

    # 3. 位置跳变检测（EKF 相邻帧位移 > 阈值）
    print("\n=== EKF 位置跳变检测（>0.5m/帧）===")
    jumps = 0
    for i in range(1, len(ekf)):
        dx = ekf[i][1] - ekf[i-1][1]
        dy = ekf[i][2] - ekf[i-1][2]
        if math.hypot(dx, dy) > 0.5:
            jumps += 1
            print(f"  跳变 @t={ekf[i][0]-t0:.1f}s: Δ={math.hypot(dx,dy)*100:.0f}cm")
    print(f"跳变总数: {jumps}")

    # 4. 起点终点对比
    print("\n=== 起点→终点位移 ===")
    for name, data in (("轮速", wheels), ("EKF", ekf), ("KISS", kiss)):
        dx = data[-1][1] - data[0][1]
        dy = data[-1][2] - data[0][2]
        print(f"  {name}: Δ=({dx:.2f}, {dy:.2f}) |Δ|={math.hypot(dx,dy):.2f}m")


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
