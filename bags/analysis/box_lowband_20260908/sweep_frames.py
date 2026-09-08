#!/usr/bin/env python3
"""TrendsParallel 扫掠 bag 逐帧精析（重渐变动态：逐帧全量，禁跳帧）：
每帧(10Hz 全量)输出箱面 x_front + 横向 az/宽 + 命中高度谱（线聚类 0.015m,≥3点）。
输出：stdout（每 2s 摘要）+ 同目录 sweep_frames_out.txt（全量逐帧）。
判据：正前 ±10° 锥、|y|<0.35、h(地面以上)=z+0.775 ∈ [0.10,0.50] 内最近前向点 = 箱面 x_front。
纯离线（rosbag2_py + numpy），不开 ROS。
"""
import numpy as np, rosbag2_py, yaml, sys, os
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

BAG = '/home/lin/Lin_workspace/r2_integration/bags/raw/box_TrendsParallel_20260908_1056'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sweep_frames_out.txt')

def parse_pc2(msg):
    W = msg.point_step
    raw = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.width*msg.height, W)
    off = {f.name: f.offset for f in msg.fields}
    x = raw[:, off['x']:off['x']+4].copy().view('<f4').ravel()
    y = raw[:, off['y']:off['y']+4].copy().view('<f4').ravel()
    z = raw[:, off['z']:off['z']+4].copy().view('<f4').ravel()
    return np.stack([x, y, z], axis=1)

r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=BAG, storage_id='sqlite3'), rosbag2_py.ConverterOptions('','cdr'))
t2t = {t.name: t.type for t in r.get_all_topics_and_types()}
types = {n: get_message(ty) for n, ty in t2t.items()}

fout = open(OUT, 'w')
fout.write('# t(s) x_front(m) az_center(deg) width(m) | 高度谱: h(m)×点数  (逐帧全量)\n')
t0 = None; n = 0; last_print = -1
while r.has_next():
    topic, data, tt = r.read_next()
    if topic != '/velodyne_points':
        continue
    if t0 is None:
        t0 = tt
    sec = (tt - t0) / 1e9
    msg = deserialize_message(data, types[topic])
    P = parse_pc2(msg)
    h = P[:, 2] + 0.775
    az = np.degrees(np.arctan2(P[:, 1], P[:, 0]))
    msk = (np.abs(az) < 10) & (P[:, 0] > 0.9) & (P[:, 0] < 3.6) & (h > 0.03) & (h < 0.6)
    S, hs, azs = P[msk], h[msk], az[msk]
    fm = (np.abs(S[:, 1]) < 0.35) & (hs > 0.10) & (hs < 0.50)
    if not fm.any():
        fout.write(f'{sec:6.1f}  --  盲区/无命中\n')
        continue
    xf = S[fm, 0].min()
    bm = np.abs(S[:, 0] - xf) < 0.45
    sel, sh = S[bm], hs[bm]
    hq = np.round(sh / 0.015).astype(int)
    lines = []
    for hh in np.unique(hq):
        cnt = (hq == hh).sum()
        if cnt >= 3:
            lines.append((sh[hq == hh].mean(), cnt))
    lines.sort(key=lambda e: e[1], reverse=True)
    if lines:
        yc = np.median(sel[:, 1])
        line_s = '  '.join(f'{h:.3f}×{c}' for h, c in lines)
        fout.write(f'{sec:6.1f}  {xf:5.2f}  {np.degrees(np.arctan2(yc, xf)):+5.1f}  {sel[:,1].max()-sel[:,1].min():4.2f} | {line_s}\n')
    n += 1
    if int(sec) != last_print and sec > 0:
        last_print = int(sec)
        if n % 20 == 0:
            print(f'  帧 {n} @ {sec:.0f}s ...', end='\r')
fout.close()
print(f'\n逐帧全量输出: {OUT}（{n} 帧命中）')
