#!/usr/bin/env python3
"""空地散点分析：验证"建图时人跟在车后"是否为地图空地散点来源

方法（与 layer_map.py 完全一致的空间参考）:
  1. 载入 ply, 每段减自己的地面 z0
  2. 机体带 [0.10,0.90) 用 cum_100_900 占用格做参考, 躯干带 [0.90,1.40) 用 layer_090_140
  3. 散点 = 各带内不在参考占用格的点; 统计 z 分布 / 连通块 / 到轨迹距离
  4. 同时统计最终地图里的小占用块 (2~16 格) — 即人短暂停留留下的可见斑点

用法: python3 analyze_stray_points.py
"""
import sys
import numpy as np
from PIL import Image

sys.path.insert(0, '/home/lin/.local/lib/python3.10/site-packages')
sys.path.insert(0, '/home/lin/Lin_workspace/r2_integration/bags/maps/map_final_0813')
from layer_map import load_ply, floor_z0, rasterize

try:
    from scipy import ndimage
    HAVE_SCIPY = True
except Exception:
    HAVE_SCIPY = False

from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from nav_msgs.msg import Odometry

RES = 0.05
BODY = (0.10, 0.90)   # 机体带（与 cum_100_900 一致）
TORSO = (0.90, 1.40)  # 躯干带（人形 0.9~1.4m）


def read_path(bag_dir):
    """/kiss/odometry 轨迹 (N,2)"""
    r = SequentialReader()
    r.open(StorageOptions(uri=bag_dir, storage_id='sqlite3'),
           ConverterOptions(input_serialization_format='cdr',
                            output_serialization_format='cdr'))
    path = []
    while r.has_next():
        t, data, _ = r.read_next()
        if t != '/kiss/odometry':
            continue
        m = deserialize_message(data, Odometry)
        p = m.pose.pose.position
        path.append((p.x, p.y))
    return np.asarray(path)


def cell_dist_map(occ_mask, path_xy, origin):
    """路径栅格化 → 距离变换: 每个栅格到最近路径格的距离(米)"""
    shape = occ_mask.shape
    j, i = rasterize(path_xy, RES, origin, shape)
    path_cells = np.zeros(shape, dtype=bool)
    path_cells[j, i] = True
    d = ndimage.distance_transform_edt(~path_cells) * RES
    return d


def analyze(name, ply_paths, layers_dir, yaml_origin, bag_dir):
    print(f'\n===== {name} =====')
    # ---- 1. 载点 + 地面 z0 ----
    segs = []
    for p in ply_paths:
        pts = load_ply(p)
        z0 = floor_z0(pts)
        pts[:, 2] -= z0
        segs.append(pts)
    pts = np.concatenate(segs)
    print(f'  总点数 {len(pts)}')

    # ---- 2. 参考占用格 ----
    # 注意: layer_map.py 写 PGM 时做了 pgm[::-1] (P5 首行=图顶), 读回须 flipud 还原网格方向
    occ_cum = np.flipud(np.array(Image.open(f'{layers_dir}/cum_100_900_tristate.pgm')) == 0)
    occ_torso = np.flipud(np.array(Image.open(f'{layers_dir}/layer_900_1400.pgm')) == 0)
    H, W = occ_cum.shape
    origin = yaml_origin
    print(f'  栅格 {H}x{W} origin={origin}')

    # ---- 3. 散点提取 ----
    def strays_in(zlo, zhi, occ_ref):
        sel = pts[(pts[:, 2] >= zlo) & (pts[:, 2] < zhi)]
        j, i = rasterize(sel[:, :2], RES, origin, occ_ref.shape)
        keep = ~occ_ref[j, i]
        return sel[keep], j[keep], i[keep]

    stray_all, j_all, i_all = [], [], []
    for zlo, zhi, occ_ref in [(BODY[0], BODY[1], occ_cum), (TORSO[0], TORSO[1], occ_torso)]:
        s, j, i = strays_in(zlo, zhi, occ_ref)
        stray_all.append(s)
        j_all.append(j)
        i_all.append(i)
        print(f'  带 [{zlo:.2f},{zhi:.2f}): {len(s)} 散点')
    spts = np.concatenate(stray_all)
    sj = np.concatenate(j_all)
    si = np.concatenate(i_all)
    n_body = int(np.sum((pts[:, 2] >= BODY[0]) & (pts[:, 2] < BODY[1])))
    print(f'  散点合计 {len(spts)} (机体带点 {n_body} 的 {100*len(spts)/max(n_body,1):.2f}%)')

    # ---- 4. 散点 z 分布 ----
    z = spts[:, 2]
    hist = np.histogram(z, bins=[0.10, 0.25, 0.50, 0.90, 1.40])[0]
    print(f'  散点 z 分布: [0.10,0.25) {hist[0]} ({100*hist[0]/len(z):.1f}%) | '
          f'[0.25,0.50) {hist[1]} ({100*hist[1]/len(z):.1f}%) | '
          f'[0.50,0.90) {hist[2]} ({100*hist[2]/len(z):.1f}%) | '
          f'[0.90,1.40) {hist[3]} ({100*hist[3]/len(z):.1f}%)')

    # ---- 5. 散点连通块 ----
    if HAVE_SCIPY:
        cellmap = np.zeros((H, W), dtype=bool)
        cellmap[sj, si] = True
        lbl, n = ndimage.label(cellmap)
        if n == 0:
            print('  散点连通块: 0')
        else:
            sizes = ndimage.sum(cellmap, lbl, range(1, n + 1))
            print(f'  散点连通块 {n} 个 | 块大小 p50={np.percentile(sizes,50):.0f} '
                  f'p90={np.percentile(sizes,90):.0f} max={sizes.max():.0f}格')

    # ---- 6. 到轨迹距离 ----
    path = read_path(bag_dir)
    print(f'  轨迹点 {len(path)}')
    dmap = cell_dist_map(occ_cum, path, origin)
    dst = dmap[sj, si]
    bins = [np.sum(dst < 1.5), np.sum((dst >= 1.5) & (dst < 3.0)), np.sum(dst >= 3.0)]
    print(f'  散点离轨迹: <1.5m {bins[0]} ({100*bins[0]/len(dst):.1f}%) | '
          f'1.5~3m {bins[1]} ({100*bins[1]/len(dst):.1f}%) | >3m {bins[2]} ({100*bins[2]/len(dst):.1f}%)')
    # 基线: 全部机体带点
    base = pts[(pts[:, 2] >= BODY[0]) & (pts[:, 2] < BODY[1])]
    bj, bi = rasterize(base[:, :2], RES, origin, occ_cum.shape)
    bd = dmap[bj, bi]
    bb = [np.sum(bd < 1.5), np.sum((bd >= 1.5) & (bd < 3.0)), np.sum(bd >= 3.0)]
    print(f'  (基线: 全部机体带点 <1.5m {100*bb[0]/len(bd):.1f}% | 1.5~3m {100*bb[1]/len(bd):.1f}% | '
          f'>3m {100*bb[2]/len(bd):.1f}%)')

    # ---- 7. 地图里可见的小占用块 (2~16 格) ----
    if HAVE_SCIPY:
        lbl2, n2 = ndimage.label(occ_cum)
        sizes2 = ndimage.sum(occ_cum, lbl2, range(1, n2 + 1))
        small = [i for i in range(1, n2 + 1) if 2 <= sizes2[i - 1] <= 16]
        print(f'  小占用块(2~16格): {len(small)} 个 (总块数 {n2})')
        if small:
            # 小块的质心与到轨迹距离
            dists = []
            for s in small:
                ys, xs = np.where(lbl2 == s)
                dists.append(dmap[ys.mean().astype(int), xs.mean().astype(int)])
            dists = np.array(dists)
            db = [np.sum(dists < 1.5), np.sum((dists >= 1.5) & (dists < 3.0)), np.sum(dists >= 3.0)]
            print(f'    小块质心离轨迹: <1.5m {db[0]} | 1.5~3m {db[1]} | >3m {db[2]}')
    print()


if __name__ == '__main__':
    B = '/home/lin/Lin_workspace/bags'
    analyze('新图 0815 (单段)',
            [f'{B}/maps/map_0815_clean/seg1_raw.ply'],
            f'{B}/maps/map_0815_clean/layers',
            (-9.672808647155762, -22.123647689819336),
            f'{B}/raw/map_run_20260815_165547')
    analyze('旧图 0813 (seg1+seg2)',
            [f'{B}/maps/map_final_0813/seg1_raw.ply',
             f'{B}/maps/map_final_0813/seg2_raw.ply'],
            f'{B}/maps/map_final_0813/layers_v2',
            (-9.491463661193848, -9.44810962677002),
            f'{B}/raw/map_run_0811_1925')
