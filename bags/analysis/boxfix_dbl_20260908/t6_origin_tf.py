#!/usr/bin/env python3
"""boxfix_dbl_20260908_1836 t6：确认清除事件类型
1) global/local costmap_raw 每帧 origin(x,y)+size → 是否重定位/重初始化
2) map->odom tf 时序 167-172s → AMCL 是否跳变"""
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

BAG = '/home/lin/Lin_workspace/r2_integration/bags/boxfix_dbl_20260908_1836'
T0 = 1788863802741155504

def open_bag():
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=BAG, storage_id='sqlite3'),
           rosbag2_py.ConverterOptions('', 'cdr'))
    types = {t.name: get_message(t.type) for t in r.get_all_topics_and_types()}
    return r, types

r, types = open_bag()
print('=== costmap origin/size 逐帧（165-175s）===')
for topic in ['/global_costmap/costmap_raw', '/local_costmap/costmap_raw']:
    print(f'-- {topic} --')
    r2, types2 = open_bag()
    while r2.has_next():
        tpc, data, t = r2.read_next()
        if tpc != topic:
            continue
        sec = (t - T0) / 1e9
        if sec < 165:
            continue
        if sec > 175.5:
            break
        msg = deserialize_message(data, types2[tpc])
        meta = msg.metadata
        d = np.frombuffer(msg.data, dtype=np.uint8).reshape(meta.size_y, meta.size_x)
        n254 = int((d == 254).sum()); n253 = int((d == 253).sum())
        n0 = int((d == 0).sum()); n255 = int((d == 255).sum())
        print(f'  t={sec:6.2f}s origin=({meta.origin.position.x:7.2f},{meta.origin.position.y:7.2f}) '
              f'size={meta.size_x}x{meta.size_y} res={meta.resolution:.2f} | '
              f'254={n254} 253={n253} 0={n0} 255={n255}')

print('=== map->odom tf 167-172s（0.1s 步，显示变化点）===')
r2, types2 = open_bag()
tf_m2o = []
while r2.has_next():
    tpc, data, t = r2.read_next()
    if tpc != '/tf':
        continue
    sec = (t - T0) / 1e9
    if sec < 167:
        continue
    if sec > 172:
        break
    msg = deserialize_message(data, types2[tpc])
    for tr in msg.transforms:
        if tr.header.frame_id == 'map' and tr.child_frame_id == 'odom':
            q = tr.transform.rotation
            yaw = np.arctan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
            tf_m2o.append((sec, tr.transform.translation.x, tr.transform.translation.y, yaw))
last = None
for v in tf_m2o:
    cur = (v[1], v[2], v[3])
    if last is None or abs(cur[0]-last[0]) > 0.002 or abs(cur[1]-last[1]) > 0.002 or abs(cur[2]-last[2]) > 0.0005:
        print(f'  t={v[0]:7.2f}s  map->odom=({v[1]:.4f},{v[2]:.4f}) yaw={np.degrees(v[3]):.2f}°')
        last = cur
print(f'  （共 {len(tf_m2o)} 条 ≈ {len(tf_m2o)/5.0:.1f}Hz）')
