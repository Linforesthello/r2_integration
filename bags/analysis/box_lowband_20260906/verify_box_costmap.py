#!/usr/bin/env python3
"""收官验证：箱子 odom≈(2.33,0.20) 在 local vs global costmap_raw 的格值实锤"""
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

BAG = '/home/lin/Lin_workspace/r2_integration/bags/raw/box_lowband_20260906_091644'
BOX = (2.33, 0.20)

def open_bag():
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=BAG, storage_id='sqlite3'),
           rosbag2_py.ConverterOptions('', 'cdr'))
    t2t = {t.name: t.type for t in r.get_all_topics_and_types()}
    return r, {n: get_message(ty) for n, ty in t2t.items()}

# ① 采集 tf：map->odom（amcl）+ odom->base_link，取静止段任意时刻（读全量存最后值即可，静止段 tf 稳定）
r, types = open_bag()
map_odom = None  # (R2, t2) map 系->odom 系
while r.has_next():
    topic, data, t = r.read_next()
    if topic != '/tf':
        continue
    for tr in deserialize_message(data, types[topic]).transforms:
        if tr.header.frame_id == 'map' and tr.child_frame_id == 'odom':
            q = tr.transform.rotation
            yaw = 2*np.arctan2(q.z, q.w)  # 纯 yaw
            map_odom = (np.array([tr.transform.translation.x, tr.transform.translation.y]), yaw)
if map_odom is None:
    print('!! 无 map->odom tf'); raise SystemExit
t_mo, yaw_mo = map_odom
ct, st = np.cos(-yaw_mo), np.sin(-yaw_mo)
# odom -> map: (ox,oy) -> map = R(yaw_mo)@odom + t_mo
box_map = (t_mo[0] + BOX[0]*np.cos(yaw_mo) - BOX[1]*np.sin(yaw_mo),
           t_mo[1] + BOX[0]*np.sin(yaw_mo) + BOX[1]*np.cos(yaw_mo))
print(f'箱子 odom={BOX} -> map=({box_map[0]:.3f},{box_map[1]:.3f})  (map->odom yaw={np.degrees(yaw_mo):.1f}°, t=({t_mo[0]:.3f},{t_mo[1]:.3f}))')

# ② 读 local 与 global costmap_raw 静止段帧（t<100s），取箱区窗口
r2, types2 = open_bag()
res = {}
t0 = None
for topic_key, label in [('/local_costmap/costmap_raw', 'LOCAL (odom系)'),
                          ('/global_costmap/costmap_raw', 'GLOBAL (map系)')]:
    # 重新读每话题
    pass
# 简化：两次遍历
def collect(topic_key):
    r3 = rosbag2_py.SequentialReader()
    r3.open(rosbag2_py.StorageOptions(uri=BAG, storage_id='sqlite3'),
            rosbag2_py.ConverterOptions('', 'cdr'))
    frames = []
    t0 = None
    while r3.has_next():
        topic, data, t = r3.read_next()
        if topic != topic_key:
            continue
        if t0 is None:
            t0 = t
        sec = (t - t0) / 1e9
        if sec > 100:
            break
        frames.append((sec, deserialize_message(data, types2[topic_key])))
    return frames

WIN = 0.7  # 箱区窗口半径 (m)
for topic_key, label, center in [
    ('/local_costmap/costmap_raw', 'LOCAL costmap (odom)', BOX),
    ('/global_costmap/costmap_raw', 'GLOBAL costmap (map)', box_map),
]:
    frames = collect(topic_key)
    if not frames:
        print(f'{label}: 无帧'); continue
    # 取中间一帧（静止段中部 t~50s）
    best = min(frames, key=lambda f: abs(f[0] - 50))
    msg = best[1]
    meta = msg.metadata
    ox, oy = meta.origin.position.x, meta.origin.position.y
    res_ = meta.resolution
    d = np.frombuffer(msg.data, dtype=np.uint8).reshape(meta.size_y, meta.size_x)
    cx, cy = center
    # 格窗口
    r_lo, r_hi = int((cy - WIN - oy) / res_), int((cy + WIN - oy) / res_) + 1
    c_lo, c_hi = int((cx - WIN - ox) / res_), int((cx + WIN - ox) / res_) + 1
    r_lo, c_lo = max(r_lo, 0), max(c_lo, 0)
    r_hi, c_hi = min(r_hi, meta.size_y), min(c_hi, meta.size_x)
    win = d[r_lo:r_hi, c_lo:c_hi]
    u, cnt = np.unique(win, return_counts=True)
    hist = dict(zip(u.tolist(), cnt.tolist()))
    # 关键: 254(lethal)/253(inscribed)/0(free)/255(unknown)/1-252
    lethal = hist.get(254, 0); inscribed = hist.get(253, 0)
    free = hist.get(0, 0); unk = hist.get(255, 0)
    grad = sum(v for k, v in hist.items() if 1 <= k <= 252)
    print(f'\n=== {label} (t={best[0]:.1f}s, 帧 origin=({ox:.2f},{oy:.2f}) 箱心=({cx:.2f},{cy:.2f}) res={res_:.3f}) ===')
    print(f'  {win.shape[0]}x{win.shape[1]} 窗口直方图: {hist}')
    print(f'  结论: lethal(254)={lethal}  inscribed(253)={inscribed}  inflation(1-252)={grad}  free(0)={free}  unknown(255)={unk}')
    verdict = []
    if lethal > 0: verdict.append('有黑块(254)')
    elif inscribed > 0: verdict.append('只有内切圈(253)无黑块')
    else: verdict.append('无任何障碍标记')
    print(f'  -> {verdict[0]}')
