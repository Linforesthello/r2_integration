#!/usr/bin/env python3
"""Nav2 goal 到达误差分析（官方 rosbag2_py，零依赖）

用法: python3 analyze_nav2_goal_error.py <bag_dir>
输入话题: /goal_pose /amcl_pose /cmd_vel_smoothed
输出: 每次 goal 的到达误差（欧氏距离 m、航向差 deg）+ 达标判定（<0.5m，plan.md 验收标准）

方法:
- /goal_pose: rviz 每次发 goal 的 map 系目标位姿（PoseStamped）
- 到达判定: /cmd_vel_smoothed 速度与角速度均 < 阈值持续 >= 2s（Nav2 到达后停稳）
- 实际停位: 停稳时刻最近的 /amcl_pose（map 系，AMCL 定位输出）

注意:
- AMCL 静止时不发布 /amcl_pose（update_min_d/a 设计行为），停稳后取最近一帧
- bag 无 /goal_pose（如 nav2_first_loop）时输出提示，无法计算
"""
import sys
import numpy as np
import rclpy.serialization as ser
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from geometry_msgs.msg import PoseStamped, Twist, PoseWithCovarianceStamped

SPEED_EPS = 0.01      # 停稳阈值 m/s（或 rad/s）
STOP_HOLD = 2.0       # 停稳持续判定 s
GOAL_RADIUS_OK = 0.5  # 达标半径 m（plan.md 验收标准终点误差 <0.5m）


def yaw_of(q):
    x, y, z, w = q.x, q.y, q.z, q.w
    return np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def yaw_diff(a, b):
    d = a - b
    return (d + np.pi) % (2 * np.pi) - np.pi


def main(bag_path):
    reader = SequentialReader()
    reader.open(StorageOptions(uri=bag_path, storage_id='sqlite3'),
                ConverterOptions(input_serialization_format='cdr',
                                  output_serialization_format='cdr'))
    topics = {t.name: t.type for t in reader.get_all_topics_and_types()}

    goals, amcl, vels = [], [], []
    while reader.has_next():
        topic, data, t = reader.read_next()
        if topic == '/goal_pose':
            m = ser.deserialize_message(data, PoseStamped)
            goals.append((t / 1e9, m.pose))
        elif topic == '/amcl_pose':
            m = ser.deserialize_message(data, PoseWithCovarianceStamped)
            amcl.append((t / 1e9, m.pose.pose))
        elif topic == '/cmd_vel_smoothed':
            m = ser.deserialize_message(data, Twist)
            vels.append((t / 1e9, np.hypot(m.linear.x, m.linear.y), abs(m.angular.z)))

    if not goals:
        print(f'[warn] {bag_path} 无 /goal_pose，无法计算到达误差')
        print(f'  可用话题: {sorted(topics)}')
        return 1
    if not vels:
        print(f'[warn] 无 /cmd_vel_smoothed（velocity_smoother 输出），无法判定停稳')
        print(f'  可用话题: {sorted(topics)}')
        return 1

    t_amcl = np.array([a[0] for a in amcl])
    t_vel = np.array([v[0] for v in vels])
    v_mag = np.array([v[1] for v in vels])

    print(f'{"goal#":>6} {"goal 时间":<20} {"误差(m)":>8} {"航向差(deg)":>12} 达标(<0.5m)')
    for i, (tg, pose) in enumerate(goals):
        idx = np.searchsorted(t_vel, tg)
        if idx >= len(t_vel):
            print(f'{i + 1:>6} {tg:20.3f}  goal 后无速度数据，跳过')
            continue
        # 停稳窗口: 速度与角速度均低于阈值持续 STOP_HOLD
        run_start = None
        t_stop = None
        for j in range(idx, len(t_vel)):
            if v_mag[j] < SPEED_EPS and vels[j][2] < SPEED_EPS:
                if run_start is None:
                    run_start = t_vel[j]
                elif t_vel[j] - run_start >= STOP_HOLD:
                    t_stop = t_vel[j]
                    break
            else:
                run_start = None
        if t_stop is None:
            print(f'{i + 1:>6} {tg:20.3f}  未检测到停稳（持续 2s），跳过')
            continue
        # 停稳时刻最近的 amcl 帧（停稳后 AMCL 可能不发布，取前后最近）
        k = int(np.argmin(np.abs(t_amcl - t_stop)))
        pa = amcl[k][1]
        err = np.hypot(pose.position.x - pa.position.x, pose.position.y - pa.position.y)
        dy = yaw_diff(yaw_of(pose.orientation), yaw_of(pa.orientation)) * 180 / np.pi
        ok = '✅' if err < GOAL_RADIUS_OK else '❌'
        print(f'{i + 1:>6} {tg:20.3f} {err:8.3f} {dy:12.2f} {ok}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
