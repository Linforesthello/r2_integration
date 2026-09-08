#!/usr/bin/env python3
"""boxfix_dbl_20260908_1836 t2：全量几何统一到 map 系
车轨(map) = map->odom ∘ odom->base_link；goal/plan 本就是 map 系；
各静止窗点云找箱（低带 0.05-0.42m，map 系 0.1m 簇，紧凑 bbox 过滤墙体）"""
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

BAG = '/home/lin/Lin_workspace/r2_integration/bags/boxfix_dbl_20260908_1836'
T0 = 1788863802741155504  # bag 首帧 wall ns（ros2 bag info Start）

def open_bag():
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=BAG, storage_id='sqlite3'),
           rosbag2_py.ConverterOptions('', 'cdr'))
    t2t = {t.name: t.type for t in r.get_all_topics_and_types()}
    return r, {n: get_message(ty) for n, ty in t2t.items()}

r, types = open_bag()
tf_o2b, tf_m2o = [], []   # (sec, x, y, yaw)
tf_static = {}
goal_list, plan_list = [], []
while r.has_next():
    topic, data, t = r.read_next()
    sec = (t - T0) / 1e9
    msg = deserialize_message(data, types[topic])
    if topic == '/tf_static':
        for tr in msg.transforms:
            tf_static[(tr.header.frame_id, tr.child_frame_id)] = tr.transform
    elif topic == '/tf':
        for tr in msg.transforms:
            q = tr.transform.rotation
            yaw = np.arctan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
            v = (sec, tr.transform.translation.x, tr.transform.translation.y, yaw)
            if tr.header.frame_id == 'odom' and tr.child_frame_id == 'base_link':
                tf_o2b.append(v)
            elif tr.header.frame_id == 'map' and tr.child_frame_id == 'odom':
                tf_m2o.append(v)
    elif topic == '/goal_pose':
        inner = msg.pose.pose if hasattr(msg.pose, 'pose') else msg.pose  # PoseStamped
        goal_list.append((sec, msg.header.frame_id, inner.position.x, inner.position.y))
    elif topic == '/plan':
        ps = msg.poses
        if ps:
            plan_list.append((sec, ps[-1].pose.position.x, ps[-1].pose.position.y))

tf_o2b.sort(); tf_m2o.sort()
print(f'odom->base_link {len(tf_o2b)}  map->odom {len(tf_m2o)}')
print(f'tf_static: {[(k, v.translation.x, v.translation.y, v.translation.z) for k, v in tf_static.items()]}')

def interp(t, arr):
    a = np.array(arr)
    if t <= a[0, 0]: return a[0, 1:]
    if t >= a[-1, 0]: return a[-1, 1:]
    i = np.searchsorted(a[:, 0], t)
    w = (t - a[i-1, 0]) / (a[i, 0] - a[i-1, 0])
    return a[i-1, 1:] * (1 - w) + a[i, 1:] * w

def rot(p, yaw):
    c, s = np.cos(yaw), np.sin(yaw)
    return np.array([c*p[0]-s*p[1], s*p[0]+c*p[1]])

def odom2map(p, mo):
    # mo = (x, y, yaw) map->odom：p_map = R(mo_yaw) p_odom + t
    return rot(p, mo[2]) + np.array([mo[0], mo[1]])

def base2odom(p, ob):
    return rot(p, ob[2]) + np.array([ob[0], ob[1]])

# ---- A. 车轨迹 + 目标统一 map 系（1s 步采样）----
print('\n=== A. map 系时间线（采样 1s；v 来自 odom twist 侧记省略，姿态为 tf）===')
ts = np.arange(0, 230, 1.0)
last = None
for tt in ts:
    ob = interp(tt, tf_o2b)
    mo = interp(tt, tf_m2o)
    pm = odom2map(np.array([ob[0], ob[1]]), mo)
    yaw_m = (ob[2] + mo[2] + np.pi) % (2*np.pi) - np.pi
    tag = ''
    for g in goal_list:
        if abs(g[0] - tt) < 0.5:
            tag += f' <GOAL g@{g[0]:.0f}s map({g[2]:.2f},{g[3]:.2f})>'
    if last is None or np.hypot(pm[0]-last[0], pm[1]-last[1]) > 0.02 or abs(yaw_m-last[2]) > 0.02:
        print(f'  t={tt:6.1f}s  map=({pm[0]:6.2f},{pm[1]:6.2f})  yaw={np.degrees(yaw_m):6.1f}°{tag}')
        last = (pm[0], pm[1], yaw_m)
print(f'\n-- goal_pose（frame_id 确认）--')
for g in goal_list:
    print(f'  t={g[0]:7.1f}s  frame={g[1]}  map=({g[2]:.2f},{g[3]:.2f})')
print(f'-- /plan 末点（map 系）--')
for p in plan_list:
    print(f'  t={p[0]:7.1f}s  end=({p[1]:.2f},{p[2]:.2f})')
