#!/usr/bin/env python3
"""102944 离线找 B1 接近窗口：读 /tf，算 robot(map系) 与 B1 距离曲线。
B1 map=(3.63,-0.27)。输出 1s 粒度距离序列（尾段），人工挑接近窗口 bag 秒。
纯离线（rosbag2_py + numpy），不开 ROS。
"""
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

BAG = '/home/lin/Lin_workspace/r2_integration/bags/raw/box_lowband_20260906_102944'
B1_MAP = np.array([3.63, -0.27])

r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=BAG, storage_id='sqlite3'),
       rosbag2_py.ConverterOptions('', 'cdr'))
t2t = {t.name: t.type for t in r.get_all_topics_and_types()}
types = {n: get_message(ty) for n, ty in t2t.items()}

def quat_yaw(q):
    return np.arctan2(2*(q.w*q.z + q.x*q.y), 1 - 2*(q.y*q.y + q.z*q.z))

t0 = None
odom_robot = {}   # sec -> (x,y) robot in odom
map_odom = []     # sec -> (x,y,yaw) map->odom?? or odom->map

# 先粗扫记录 map->odom/odom->map 出现次数
while r.has_next():
    topic, data, t = r.read_next()
    if t0 is None:
        t0 = t
    sec = (t - t0) / 1e9
    msg = deserialize_message(data, types[topic])
    if topic != '/tf':
        continue
    for tr in msg.transforms:
        if tr.header.frame_id == 'odom' and tr.child_frame_id == 'base_link':
            odom_robot[sec] = (tr.transform.translation.x, tr.transform.translation.y)
        elif tr.header.frame_id == 'map' and tr.child_frame_id == 'odom':
            # map->odom: 把 map 点转到 odom 需要逆
            map_odom.append((sec, tr.transform.translation.x, tr.transform.translation.y, quat_yaw(tr.transform.rotation)))
print(f'tf: robot(odom) {len(odom_robot)} 帧, map->odom {len(map_odom)} 帧')
if map_odom:
    arr = np.array(map_odom)
    print('map->odom: t 范围 %.1f~%.1f' % (arr[:,0].min(), arr[:,0].max()))
    print('map->odom 尾 5 条:')
    for row in arr[-5:]:
        print('  t=%.1f x=%.3f y=%.3f yaw=%.1f°' % (row[0], row[1], row[2], np.degrees(row[3])))

# 车在 map 系 = odom_robot 经 map->odom 逆变换（若无 map->odom 则跳过）
# 简化: 若 map->odom 为 yaw=θ, t=(tx,ty)（map→odom 含义：p_odom = R(θ) p_map + t）
# 则 p_map = R(-θ)(p_odom - t)。但 bag 里若存在多条取最近的。
import bisect
def nearest_map_odom(sec):
    if not map_odom:
        return None
    ts = [m[0] for m in map_odom]
    i = bisect.bisect_left(ts, sec)
    cand = []
    if i < len(ts): cand.append(map_odom[i])
    if i > 0: cand.append(map_odom[i-1])
    return min(cand, key=lambda c: abs(c[0]-sec))

if map_odom:
    t_hist, d_hist = [], []
    for sec, (x, y) in sorted(odom_robot.items()):
        mo = nearest_map_odom(sec)
        if mo is None:
            continue
        tx, ty, th = mo[1], mo[2], mo[3]
        ct, st = np.cos(th), np.sin(th)
        # p_odom = R(th) p_map + t  →  p_map = R(-th)(p_odom - t)
        pm = np.array([ct*(x-tx) + st*(y-ty), -st*(x-tx) + ct*(y-ty)])
        d = np.linalg.norm(pm - B1_MAP)
        t_hist.append(sec); d_hist.append(d)
    print('\n=== 车(map)到 B1 距离（全时段, 1s 步进降采样）===')
    prev_bucket = -1
    for sec, d in zip(t_hist, d_hist):
        b = int(sec)
        if b != prev_bucket:
            prev_bucket = b
            print(f'  t={sec:6.1f}s  d={d:.2f}m')
else:
    print('无 map->odom，改输出 robot odom 轨迹尾段:')
    for sec, (x, y) in sorted(odom_robot.items()):
        if sec >= 197.9 - 60:
            print(f'  t={sec:6.1f}s  odom=({x:.2f},{y:.2f})')
