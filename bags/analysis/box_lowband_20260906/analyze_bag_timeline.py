#!/usr/bin/env python3
"""box_lowband bag 运动学时间线概要：goal/plan/cmd_vel/odom/scan 事件轴"""
import sys
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

BAG = '/home/lin/Lin_workspace/r2_integration/bags/raw/box_lowband_20260906_091644'

reader = rosbag2_py.SequentialReader()
reader.open(
    rosbag2_py.StorageOptions(uri=BAG, storage_id='sqlite3'),
    rosbag2_py.ConverterOptions('', 'cdr'),
)
t2t = {t.name: t.type for t in reader.get_all_topics_and_types()}
types = {}
for n, ty in t2t.items():
    types[n] = get_message(ty)

# 轻话题全收 + odom 全收
targets = {'/goal_pose', '/cmd_vel', '/plan', '/odometry/filtered', '/tf'}
goals, cmds, plans, odoms, tfs = [], [], [], [], []
t0 = None
while reader.has_next():
    topic, data, t = reader.read_next()
    if topic not in targets:
        continue
    if t0 is None:
        t0 = t
    sec = (t - t0) / 1e9
    msg = deserialize_message(data, types[topic])
    if topic == '/goal_pose':
        inner = msg.pose.pose if hasattr(msg.pose, 'pose') else msg.pose  # PoseWithCovariance 或 PoseStamped
        p = inner.position
        goals.append((sec, p.x, p.y, inner.orientation.z))
    elif topic == '/cmd_vel':
        tw = msg.twist if hasattr(msg, 'twist') else msg  # TwistStamped 或裸 Twist
        cmds.append((sec, tw.linear.x, tw.angular.z))
    elif topic == '/plan':
        ps = msg.poses
        if ps:
            goals_info = None
            plans.append((sec, len(ps), ps[0].pose.position.x, ps[0].pose.position.y,
                          ps[-1].pose.position.x, ps[-1].pose.position.y))
    elif topic == '/odometry/filtered':
        p = msg.pose.pose.position
        odoms.append((sec, p.x, p.y, msg.twist.twist.linear.x))
    elif topic == '/tf':
        # 只记录 odom->base_link 平移
        for tr in msg.transforms:
            if tr.header.frame_id == 'odom' and tr.child_frame_id == 'base_link':
                tfs.append((sec, tr.transform.translation.x, tr.transform.translation.y))

print(f'=== bag 总时长 {reader.get_metadata().duration} ns ===')
print(f'\n=== 时间线摘要 (t=0 为首条消息 {t0/1e9:.1f}) ===')
if goals:
    print('-- goal_pose --')
    for g in goals:
        print(f'  t={g[0]:7.1f}s  pos=({g[1]:.2f},{g[2]:.2f})  yaw_z={g[3]:.3f}')
if plans:
    print('-- /plan 时间线 --')
    for p in plans:
        print(f'  t={p[0]:7.1f}s  n={p[1]}  start=({p[2]:.2f},{p[3]:.2f}) end=({p[4]:.2f},{p[5]:.2f})')
print('-- odom/base_link 起点终点 --')
if tfs:
    print(f'  首帧 t={tfs[0][0]:.1f} ({tfs[0][1]:.2f},{tfs[0][2]:.2f})  末帧 t={tfs[-1][0]:.1f} ({tfs[-1][1]:.2f},{tfs[-1][2]:.2f})')
    # 车速段
    moved = [o for o in odoms if abs(o[3]) > 0.02]
    print(f'  /odometry/filtered 线速度>0.02 的帧 {len(moved)}/{len(odoms)}')
    if moved:
        print(f'  运动段 t: {moved[0][0]:.1f} ~ {moved[-1][0]:.1f}s')
        # 分组连续运动段
        segs = []
        s0 = moved[0][0]
        prev = moved[0][0]
        for m in moved[1:]:
            if m[0] - prev > 1.0:
                segs.append((s0, prev))
                s0 = m[0]
            prev = m[0]
        segs.append((s0, prev))
        print(f'  运动段分组(间隙>1s): {[(f"{a:.0f}-{b:.0f}s") for a,b in segs]}')
if cmds:
    c_on = [c for c in cmds if abs(c[1]) > 0.001 or abs(c[2]) > 0.001]
    print(f'\n-- cmd_vel 非零 {len(c_on)}/{len(cmds)} 条')
    if c_on:
        print(f'  首个 t={c_on[0][0]:.1f}s 末个 t={c_on[-1][0]:.1f}s')
        # 速度统计
        lin = [abs(c[1]) for c in c_on]
        ang = [abs(c[2]) for c in c_on]
        print(f'  |lin| max={max(lin):.2f} mean={np.mean(lin):.2f} |  |ang| max={max(ang):.2f}')
