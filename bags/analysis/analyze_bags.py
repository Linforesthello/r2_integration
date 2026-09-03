#!/usr/bin/env python3
"""底盘修复验证：历史 bag（修复前）vs after bag（修复后）对比分析
用官方 rosbag2_py 读 bag。指标:
  1. 轮速 yaw vs IMU yaw 全程偏差（最大/平均/终点）
  2. 闭环位移差（起点→终点 |Δpos|）
  3. EKF z 漂移（起点 vs 终点）
  4. after bag 额外: KISS-ICP 闭环位移（位置基准）
"""
import sys, math, bisect
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import Imu
from nav_msgs.msg import Odometry

TOPIC_TYPES = {
    '/odom_wheels': Odometry,
    '/imu/data': Imu,
    '/odometry/filtered': Odometry,
    '/kiss/odometry': Odometry,
}


def quat_to_yaw(w, x, y, z):
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def analyze(bag_dir):
    result = {'name': bag_dir.rsplit('/', 1)[-1]}
    wheels, imus, ekf, kiss = [], [], [], []

    reader = SequentialReader()
    reader.open(StorageOptions(uri=bag_dir, storage_id='sqlite3'),
                ConverterOptions(input_serialization_format='cdr', output_serialization_format='cdr'))
    types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    while reader.has_next():
        topic, data, _ = reader.read_next()
        msgtype = TOPIC_TYPES.get(topic)
        if msgtype is None:
            continue
        m = deserialize_message(data, msgtype)
        t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        if topic == '/odom_wheels':
            p = m.pose.pose
            wheels.append((t, p.position.x, p.position.y,
                           quat_to_yaw(p.orientation.w, p.orientation.x, p.orientation.y, p.orientation.z)))
        elif topic == '/imu/data':
            o = m.orientation
            imus.append((t, quat_to_yaw(o.w, o.x, o.y, o.z)))
        elif topic == '/odometry/filtered':
            p = m.pose.pose.position
            ekf.append((t, p.x, p.y, p.z))
        elif topic == '/kiss/odometry':
            p = m.pose.pose.position
            kiss.append((t, p.x, p.y))

    if len(wheels) < 2:
        return {**result, 'error': 'wheels 数据不足'}
    result['duration'] = wheels[-1][0] - wheels[0][0]

    # 1. 轮速 vs IMU yaw 对齐对比
    if imus:
        imu_ts = [i[0] for i in imus]
        diffs = []
        for t, _, _, wyaw in wheels:
            idx = min(bisect.bisect_left(imu_ts, t), len(imus) - 1)
            d = (wyaw - imus[idx][1] + math.pi) % (2 * math.pi) - math.pi
            diffs.append(d)
        result['yaw_max_deg'] = max(abs(d) for d in diffs) * 180 / math.pi
        result['yaw_avg_deg'] = (sum(abs(d) for d in diffs) / len(diffs)) * 180 / math.pi
        result['yaw_end_deg'] = abs(diffs[-1]) * 180 / math.pi

    # 2. 闭环位移差
    result['wheels_loop_m'] = math.hypot(wheels[-1][1] - wheels[0][1], wheels[-1][2] - wheels[0][2])
    if ekf:
        result['ekf_loop_m'] = math.hypot(ekf[-1][1] - ekf[0][1], ekf[-1][2] - ekf[0][2])
        result['ekf_z_drift_m'] = ekf[-1][3] - ekf[0][3]
    if kiss:
        result['kiss_loop_m'] = math.hypot(kiss[-1][1] - kiss[0][1], kiss[-1][2] - kiss[0][2])
    return result


if __name__ == '__main__':
    bags = sys.argv[1:] if len(sys.argv) > 1 else []
    print(f"{'bag':<24}{'时长s':>7}{'yaw最大°':>9}{'yaw平均°':>9}{'yaw终点°':>9}{'轮速闭环m':>10}{'KISS闭环m':>10}{'EKF闭环m':>10}{'z漂移m':>9}")
    for b in bags:
        r = analyze(b)
        if 'error' in r:
            print(f"{r['name']:<24} {r['error']}")
            continue
        print(f"{r['name']:<24}{r['duration']:>7.0f}"
              f"{r.get('yaw_max_deg', float('nan')):>9.1f}"
              f"{r.get('yaw_avg_deg', float('nan')):>9.1f}"
              f"{r.get('yaw_end_deg', float('nan')):>9.1f}"
              f"{r.get('wheels_loop_m', float('nan')):>10.2f}"
              f"{r.get('kiss_loop_m', float('nan')):>10.2f}"
              f"{r.get('ekf_loop_m', float('nan')):>10.2f}"
              f"{r.get('ekf_z_drift_m', float('nan')):>9.2f}")
