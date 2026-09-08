#!/usr/bin/env python3
"""VLP-16 ring 几何律标定（09-07 纯净数据系列配套）：
读本机校准文件 VLP16db.yaml 的 vert_correction → 得到 16 ring 仰角 →
对 0.35m 低箱（顶 h_top=0.35，雷达离地 H=0.775）计算每条向下 ring 的可见距离窗
[d_top, d_gnd]（d_top=打顶距离=(H-h)/tanθ，d_gnd=打到地面距离=H/tanθ）→ 输出理论表。
纯离线（只读 yaml + numpy），不开 ROS。
"""
import yaml, math, numpy as np

CAL = '/opt/ros/humble/share/velodyne_pointcloud/params/VLP16db.yaml'
H = 0.775   # 雷达光学中心离地（09-06 render_frames/逐帧实测 ground z=-0.775 定）
H_TOP = 0.35

lasers = yaml.safe_load(open(CAL))['lasers']
rows = []
for L in lasers:
    v = math.degrees(L['vert_correction'])
    rows.append((L['laser_id'], v))
rows.sort(key=lambda r: r[1])   # 按仰角升序 = ring 升序（09-04 §10.1-4 定）
print('校准文件 ring 仰角（升序）:')
for lid, v in rows:
    d = '↑' if v > 0 else '↓'
    print(f'  laser_id={lid:2d}  {v:+6.2f}° {d}')

print(f'\n0.35m 箱可见窗（H={H}m, 箱顶 {H_TOP}m）：d_top = (H-{H_TOP})/tanθ = 0.425/tanθ')
print(f'{"ring":>4} {"仰角":>6} {"打顶 d_top":>10} {"打地 d_gnd":>10} {"可见区间":>18}')
for lid, v in rows:
    if v >= 0:
        continue
    t = math.radians(-v)
    dt = 0.425 / math.tan(t)
    dg = H / math.tan(t)
    print(f'{lid:>4} {v:+6.2f} {dt:8.2f}m {dg:8.2f}m  [{dt:.2f}, {dg:.2f}]m')

# 关键边界：逐条 ring 打顶距离递减表（接近方向最先消失 = -15° @1.59m）
print('\n盲区边界（低于该距离 ring 即过顶不可见）: 最近消失 ring = -15° @ 1.59m（传感轴参照）')
print('逐帧实测验证点（TrendsParallel 20260907_1056）：face 2.10m → -15 打面 0.215 / -13 打面 0.295 / -11 顶面擦边 0.353')
print('  理论: -15: 0.775-2.10*tan15 = %.3f;  -13: %.3f;  -11 顶面擦边（d_top=2.19 在 [face 2.10, back 2.45] 内）'
      % (0.775-2.10*math.tan(math.radians(15)), 0.775-2.10*math.tan(math.radians(13))))
