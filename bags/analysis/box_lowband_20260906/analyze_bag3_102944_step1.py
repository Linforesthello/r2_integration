#!/usr/bin/env python3
"""bag3 (102944) step1：体检 + 时间线（goal/运动）+ 3 箱子定位"""
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

BAG = '/home/lin/Lin_workspace/r2_integration/bags/raw/box_lowband_20260906_102944'

def open_bag():
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=BAG, storage_id='sqlite3'),
           rosbag2_py.ConverterOptions('', 'cdr'))
    t2t = {t.name: t.type for t in r.get_all_topics_and_types()}
    return r, {n: get_message(ty) for n, ty in t2t.items()}

# ---------- A. 时间线 ----------
r, types = open_bag()
t0 = None
goals, plans, cmds, traj = [], [], [], []
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
    elif topic == '/cmd_vel':
        tw = msg.twist if hasattr(msg, 'twist') else msg
        cmds.append((sec, tw.linear.x, tw.angular.z))
    elif topic == '/tf':
        for tr in msg.transforms:
            if tr.header.frame_id == 'odom' and tr.child_frame_id == 'base_link':
                tt = tr.transform.translation
                q = tr.transform.rotation
                yaw = np.degrees(np.arctan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z)))
                traj.append((sec, tt.x, tt.y, yaw))

print(f'=== A. 时间线（总时长 {len(traj) and traj[-1][0]:.1f}s）===')
if goals:
    print('-- goal_pose --')
    for g in goals:
        print(f'  t={g[0]:7.1f}s  pos=({g[1]:.2f},{g[2]:.2f})  yaw_z={g[3]:.3f}')
if plans:
    print(f'-- /plan {len(plans)} 条，末点：')
    for p in plans[::max(1, len(plans)//8)]:
        print(f'  t={p[0]:7.1f}s  n={p[1]}  end=({p[2]:.2f},{p[3]:.2f})')
print('-- 车轨迹 --')
if traj:
    print(f'  起点 t={traj[0][0]:.1f} ({traj[0][1]:.2f},{traj[0][2]:.2f}) yaw={traj[0][3]:.1f}°')
    print(f'  终点 t={traj[-1][0]:.1f} ({traj[-1][1]:.2f},{traj[-1][2]:.2f}) yaw={traj[-1][3]:.1f}°')
    for i in range(0, len(traj), max(1, len(traj)//10)):
        print(f'    t={traj[i][0]:6.1f}s ({traj[i][1]:.2f},{traj[i][2]:.2f}) yaw={traj[i][3]:.1f}°')
c_on = [c for c in cmds if abs(c[1]) > 0.001 or abs(c[2]) > 0.001]
print(f'-- cmd_vel 非零 {len(c_on)}/{len(cmds)}，首个 t={c_on[0][0] if c_on else "-"}s')

# ---------- B. 找箱（点云聚类）----------
r2, types2 = open_bag()
# velodyne 系地面 -0.775；箱子离地高度：low 0.05-0.35，high 0.5-0.72
def try_find(win_name, a, b, z_lo, z_hi):
    global t0
    acc = []
    cnt = 0
    while r2.has_next():
        topic, data, t = r2.read_next()
        if topic != '/velodyne_points':
            continue
        if t0 is None:
            t0 = t
        sec = (t - t0) / 1e9
        if sec > b:
            break
        if sec < a:
            continue
        cnt += 1
        if cnt % 3 != 0:
            continue
        msg = deserialize_message(data, types2[topic])
        W = msg.point_step
        raw = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.width*msg.height, W)
        off = {f.name: f.offset for f in msg.fields}
        x = raw[:, off['x']:off['x']+4].copy().view(np.float32).ravel()
        y = raw[:, off['y']:off['y']+4].copy().view(np.float32).ravel()
        z = raw[:, off['z']:off['z']+4].copy().view(np.float32).ravel()
        # 候选：正前方 ±40°（大概率沿 +x），高度带内，滤地
        az = np.degrees(np.arctan2(y, x))
        rxy = np.hypot(x, y)
        m = (np.abs(az) < 40) & (rxy > 0.5) & (rxy < 4.5) & (z > -0.775 + z_lo) & (z < -0.775 + z_hi)
        if m.any():
            acc.append(np.stack([x[m], y[m], z[m]], axis=1))
    if not acc:
        print(f'  [{win_name}] 无数据'); return
    P = np.vstack(acc)
    # 0.1m 格密度
    gx = np.floor(P[:, 0] / 0.1).astype(int); gy = np.floor(P[:, 1] / 0.1).astype(int)
    keys = gx * 100000 + gy
    u, inv, cnt2 = np.unique(keys, return_inverse=True, return_counts=True)
    order = np.argsort(-cnt2)
    print(f'  [{win_name}] 高度带{round(z_lo,2)}-{round(z_hi,2)}m 正前±40°：点 {len(P)}，0.1m 格 top 6:')
    for idx in order[:6]:
        msk = inv == idx
        xs, ys, zs = P[msk, 0], P[msk, 1], P[msk, 2]
        print(f'    中心=({xs.mean():.2f},{ys.mean():.2f}) 顶高={-(np.percentile(zs,95)+0.775):.2f}m n={cnt2[idx]}')

print('\n=== B. 找箱（velodyne 系，车头方位假设 ±40°）===')
print('-- 低箱候选（0.05-0.42m 带）--')
try_find('低箱-初始静止', 0, 5, 0.05, 0.42)
print('-- 高箱候选（0.45-0.75m 带）--')
try_find('高箱-初始静止', 0, 5, 0.45, 0.75)
