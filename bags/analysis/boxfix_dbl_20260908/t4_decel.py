#!/usr/bin/env python3
"""boxfix_dbl_20260908_1836 t4：两次减速点逐帧取证
每帧(global costmap_raw 全帧 + local costmap_raw 全帧)输出：
  t | v | 车头前方 ROI(前后 xr+0.4~xr+2.4, 侧 ±0.8) 254 格数/253 格数/254质心 | 全图254 | 帧origin
robot 取 odom->base_link（odometry/filtered 的 tf）；global 用 map 系、local 用 odom 系"""
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

BAG = '/home/lin/Lin_workspace/r2_integration/bags/boxfix_dbl_20260908_1836'
T0 = 1788863802741155504
WIN = {'A(第一次接近)': (152.0, 172.0), 'B(第二次接近)': (170.0, 193.0)}

def open_bag():
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=BAG, storage_id='sqlite3'),
           rosbag2_py.ConverterOptions('', 'cdr'))
    t2t = {t.name: t.type for t in r.get_all_topics_and_types()}
    return r, {n: get_message(ty) for n, ty in t2t.items()}

# ---- 预读 tf（odom->base_link + map->odom）与 cmd_vel_smoothed ----
r, types = open_bag()
tf_o2b, tf_m2o, vel = [], [], []
while r.has_next():
    topic, data, t = r.read_next()
    sec = (t - T0) / 1e9
    msg = deserialize_message(data, types[topic])
    if topic == '/tf':
        for tr in msg.transforms:
            q = tr.transform.rotation
            yaw = np.arctan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
            v = (sec, tr.transform.translation.x, tr.transform.translation.y, yaw)
            if tr.header.frame_id == 'odom' and tr.child_frame_id == 'base_link':
                tf_o2b.append(v)
            elif tr.header.frame_id == 'map' and tr.child_frame_id == 'odom':
                tf_m2o.append(v)
    elif topic == '/cmd_vel_smoothed':
        tw = msg.twist if hasattr(msg, 'twist') else msg
        vel.append((sec, abs(tw.linear.x)))

def interp(t, arr):
    a = np.array(arr)
    if not len(a): return None
    if t <= a[0, 0]: return a[0, 1:]
    if t >= a[-1, 0]: return a[-1, 1:]
    i = np.searchsorted(a[:, 0], t)
    w = (t - a[i-1, 0]) / (a[i, 0] - a[i-1, 0])
    return a[i-1, 1:] * (1 - w) + a[i, 1:] * w

def rot(p, yaw):
    c, s = np.cos(yaw), np.sin(yaw)
    return np.array([c*p[0]-s*p[1], s*p[0]+c*p[1]])

def analyze(topic_key, frame_label, win_name, a, b, use_map):
    """逐帧统计 ROI 254/253；use_map=True → robot 位姿取 map 系"""
    r2, types2 = open_bag()
    t0 = None
    print(f'\n=== {frame_label} · {win_name} [{a:.1f}~{b:.1f}s] ===')
    print(f'{"t(s)":>6} {"|v|":>5} {"robot_x":>7} {"robot_y":>7} {"ROI254":>6} {"ROI253":>6} {"254质心":>12} {"全图254":>7}')
    while r2.has_next():
        topic, data, t = r2.read_next()
        if topic != topic_key:
            continue
        sec = (t - T0) / 1e9
        if sec < a:
            continue
        if sec > b:
            break
        ob = interp(sec, tf_o2b); mo = interp(sec, tf_m2o)
        if ob is None or mo is None:
            continue
        vv = interp(sec, vel)
        vsp = abs(vv[0]) if vv is not None else float('nan')
        if use_map:  # global costmap 为 map 系
            rp = rot(np.array([ob[0], ob[1]]), mo[2]) + np.array([mo[0], mo[1]])
        else:
            rp = np.array([ob[0], ob[1]])
        msg = deserialize_message(data, types2[topic])
        meta = msg.metadata
        ox, oy = meta.origin.position.x, meta.origin.position.y
        res = meta.resolution
        d = np.frombuffer(msg.data, dtype=np.uint8).reshape(meta.size_y, meta.size_x)
        full254 = int((d == 254).sum())
        # ROI：前方带 xr+0.4~xr+2.4、y ±0.8（仅车头大致 +x 直行场景）
        c_lo = int((rp[0] + 0.4 - ox) / res); c_hi = int((rp[0] + 2.4 - ox) / res) + 1
        r_lo = int((rp[1] - 0.8 - oy) / res); r_hi = int((rp[1] + 0.8 - oy) / res) + 1
        c_lo, r_lo = max(c_lo, 0), max(r_lo, 0)
        c_hi, r_hi = min(c_hi, meta.size_x), min(r_hi, meta.size_y)
        win = d[r_lo:r_hi, c_lo:c_hi]
        n254 = int((win == 254).sum()); n253 = int((win == 253).sum())
        cx = cy = float('nan')
        ys, xs = np.nonzero(win == 254)
        if len(ys):
            cx = ox + (c_lo + xs.mean() + 0.5) * res
            cy = oy + (r_lo + ys.mean() + 0.5) * res
        print(f'{sec:6.1f} {vsp:5.2f} {rp[0]:7.2f} {rp[1]:7.2f} {n254:6d} {n253:6d} ({cx:5.2f},{cy:5.2f}) {full254:7d}')

for wname, (a, b) in WIN.items():
    analyze('/global_costmap/costmap_raw', 'GLOBAL(map)', wname, a, b, use_map=True)
    analyze('/local_costmap/costmap_raw', 'LOCAL(odom)', wname, a, b, use_map=False)
