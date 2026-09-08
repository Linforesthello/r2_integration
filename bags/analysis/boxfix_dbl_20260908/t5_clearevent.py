#!/usr/bin/env python3
"""boxfix_dbl_20260908_1836 t5：定位 t≈169.5~170.5 全局清除事件
逐帧 diff global costmap：值变化统计 + 变化格 bbox + 与箱区(mark 质心)关系"""
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

BAG = '/home/lin/Lin_workspace/r2_integration/bags/boxfix_dbl_20260908_1836'
T0 = 1788863802741155504

r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=BAG, storage_id='sqlite3'),
       rosbag2_py.ConverterOptions('', 'cdr'))
types = {t.name: get_message(t.type) for t in r.get_all_topics_and_types()}
frames = []
while r.has_next():
    topic, data, t = r.read_next()
    if topic != '/global_costmap/costmap_raw':
        continue
    sec = (t - T0) / 1e9
    if 165.0 <= sec <= 175.0:
        msg = deserialize_message(data, types[topic])
        meta = msg.metadata
        d = np.frombuffer(msg.data, dtype=np.uint8).reshape(meta.size_y, meta.size_x)
        frames.append((sec, d, meta.origin.position.x, meta.origin.position.y, meta.resolution))
frames.sort()
print(f'帧数 {len(frames)}')
prev = None
for sec, d, ox, oy, res in frames:
    line = f't={sec:6.2f}s  '
    n254, n253 = int((d == 254).sum()), int((d == 253).sum())
    n0, n255 = int((d == 0).sum()), int((d == 255).sum())
    line += f'254={n254}  253={n253}  0={n0}  255={n255}'
    if prev is not None:
        # 与前一帧 diff：上一帧有值→本帧变成更低值的格
        pd = prev[1]
        c254 = ((pd == 254) & (d != 254)).sum()   # 254 消失
        g254 = ((d == 254) & (pd != 254)).sum()   # 254 新增
        c253 = ((pd == 253) & (d != 253)).sum()
        g253 = ((d == 253) & (pd != 253)).sum()
        line += f'  |  Δ: 254消失{c254} 新增{g254}  253消失{c253} 新增{g253}'
        if c254 > 300:
            lost = (pd == 254) & (d != 254)
            ys, xs = np.nonzero(lost)
            gx0, gx1 = ox + xs.min() * res, ox + (xs.max() + 1) * res
            gy0, gy1 = oy + ys.min() * res, oy + (ys.max() + 1) * res
            line += f'  消失bbox x[{gx0:.1f},{gx1:.1f}] y[{gy0:.1f},{gy1:.1f}] 共{len(xs)}格'
            # 箱区窗口（map ~4.08,0.49 ±0.7）内消失数
            c_lo = int((4.08 - 0.7 - ox) / res); c_hi = int((4.08 + 0.7 - ox) / res)
            r_lo = int((0.49 - 0.7 - oy) / res); r_hi = int((0.49 + 0.7 - oy) / res)
            box_lost = int(lost[max(r_lo,0):min(r_hi, d.shape[0]), max(c_lo,0):min(c_hi, d.shape[1])].sum())
            box_now = int(((d == 254) & (pd == 254)).sum())  # 全图存活
            line += f'  箱窗(4.08,0.49±0.7)消失={box_lost}'
    print(line)
    prev = (sec, d)
