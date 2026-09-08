#!/usr/bin/env python3
"""boxfix_dbl_20260908_1836 t1：时间线全览（goal/plan/速度/车轨），锁定运动段与减速停车窗"""
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

BAG = '/home/lin/Lin_workspace/r2_integration/bags/boxfix_dbl_20260908_1836'

def open_bag():
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=BAG, storage_id='sqlite3'),
           rosbag2_py.ConverterOptions('', 'cdr'))
    t2t = {t.name: t.type for t in r.get_all_topics_and_types()}
    return r, {n: get_message(ty) for n, ty in t2t.items()}

r, types = open_bag()
t0 = None
goals, plans, cmds, traj, odom_v = [], [], [], [], []
while r.has_next():
    topic, data, t = r.read_next()
    if t0 is None:
        t0 = t
    sec = (t - t0) / 1e9
    msg = deserialize_message(data, types[topic])
    if topic == '/goal_pose':
        inner = msg.pose.pose if hasattr(msg.pose, 'pose') else msg.pose
        goals.append((sec, inner.position.x, inner.position.y, inner.orientation.z))
    elif topic == '/plan':
        ps = msg.poses
        if ps:
            plans.append((sec, len(ps), ps[-1].pose.position.x, ps[-1].pose.position.y))
    elif topic == '/cmd_vel_smoothed':
        tw = msg.twist if hasattr(msg, 'twist') else msg
        cmds.append((sec, tw.linear.x, tw.angular.z))
    elif topic == '/odometry/filtered':
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        yaw = np.arctan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
        odom_v.append((sec, p.x, p.y, yaw, msg.twist.twist.linear.x))
print(f'=== t0={t0/1e9:.1f}  odom/filtered {len(odom_v)} 条 ≈ {len(odom_v)/229.9:.1f}Hz ===')

if goals:
    print('\n-- goal_pose (6) --')
    for g in goals:
        print(f'  t={g[0]:7.1f}s  ({g[1]:.2f},{g[2]:.2f})  yaw_z={g[3]:.3f}')
if plans:
    print(f'\n-- /plan {len(plans)} 条 --')
    for p in plans:
        print(f'  t={p[0]:7.1f}s  n={p[1]}  end=({p[2]:.2f},{p[3]:.2f})')

# 车轨迹降采样 ~2Hz（odometry/filtered 30Hz）
arr = np.array(odom_v)
tgrid = np.arange(0, arr[-1, 0], 0.5)
pos = np.stack([np.interp(tgrid, arr[:, 0], arr[:, 1]),
                np.interp(tgrid, arr[:, 0], arr[:, 2]),
                np.interp(tgrid, arr[:, 0], arr[:, 4])], axis=1)
moved = pos[:, 2] > 0.01   # |v|>0.01 视为运动
print(f'\n=== 运动/静止段（0.5s 网格，|v|>0.01 = 运动）===')
# 段分组：间隙 >2s
segs = []
cur = None
for i, mv in enumerate(moved):
    if mv and cur is None:
        cur = [tgrid[i], None]
    elif not mv and cur is not None:
        cur[1] = tgrid[i]
        if cur[1] - cur[0] > 0.5:
            segs.append(cur)
        cur = None
if cur is not None:
    cur[1] = tgrid[-1]
    segs.append(cur)
for s, e in segs:
    m = (tgrid >= s) & (tgrid <= e)
    vmax = pos[m, 2].max()
    # 减速子段：后 20% 内 v 从 40%vmax 降到 <0.03
    sub = pos[m]
    seg_len = sub.shape[0]
    tail = sub[max(0, seg_len-10):]
    # 末 5s 内的最低点与减速起点
    decel_start, decel_end = None, None
    # 简化：找末次 v>0.6*vmax 到首个 v<0.03
    idx_hi = None
    for j in range(len(sub) - 1, -1, -1):
        if sub[j, 2] > 0.6 * vmax:
            idx_hi = j
            break
    if idx_hi is not None:
        decel_start = tgrid[m][idx_hi]
        decel_end = e
    x0, y0 = pos[m][0, 0], pos[m][0, 1]
    x1, y1 = pos[m][-1, 0], pos[m][-1, 1]
    print(f'  运动段 [{s:6.1f} ~ {e:6.1f}]s  时长{e-s:4.1f}s  vmax={vmax:.3f}  起点({x0:.2f},{y0:.2f}) → 终点({x1:.2f},{y1:.2f})  末段减速窗: {decel_start:.1f}~{decel_end:.1f}s')

# cmd_vel 摘要
c_on = [(c[0], abs(c[1]), abs(c[2])) for c in cmds if abs(c[1]) > 0.005 or abs(c[2]) > 0.005]
print(f'\n-- cmd_vel_smoothed 非零 {len(c_on)}/{len(cmds)} 条; |v|max={max(c[1] for c in c_on):.2f} m/s')
print(f'   输出 {len(tgrid)} 行 x 轨迹列 = 上面已含（含静止）。\n-- 车全程点位(2Hz) --')
for i in range(0, len(tgrid), 20):
    print(f'  t={tgrid[i]:6.1f}s  x={pos[i,0]:6.2f} y={pos[i,1]:6.2f}  v={pos[i,2]:.3f}')
