#!/usr/bin/env python3
"""人形块过滤: 从 ply 中删除"人形小占用块"的点, 输出清洗后的 ply 供 layer_map.py 重建

背景 (2026-08-15): 建图时操作员跟在车后, 人在空地上留下小占用块
(2~16 格, z 跨度 0.1~2m 人形, 点密度 5~50/格 远低于真结构 300+/格)

判据 (对 cum_100_900 与 layer_900_1400 占用格的连通块, 2~16 格):
  1. 块内点 z 跨度 >= 0.8m        (人站立高度, 腿→躯干→头)
  2. 块内点密度 < --max-dens 点/格 (默认 100; 真结构 300+ 不受影响)

用法:
  python3 filter_person_blobs.py <ply...> --layers <层目录> --out <clean.ply>
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, '/home/lin/.local/lib/python3.10/site-packages')
sys.path.insert(0, '/home/lin/Lin_workspace/r2_integration/bags/maps/map_final_0813')
from layer_map import load_ply, floor_z0, rasterize

try:
    from scipy import ndimage
    HAVE_SCIPY = True
except Exception:
    HAVE_SCIPY = False

from PIL import Image

RES = 0.05
Z_MEAS = (0.0, 2.2)   # 密度/z跨度测量用 z 范围


def parse_origin_yaml(yaml_path):
    """从 tristate yaml 读栅格 origin"""
    origin = None
    with open(yaml_path) as f:
        for line in f:
            if line.startswith('origin:'):
                vals = [float(x) for x in line.split('[')[1].split(']')[0].split(',')]
                origin = (vals[0], vals[1])
    return origin


def person_blob_cells(pts, occ_cum, occ_torso, origin, max_dens):
    """返回被判为"人形块"的栅格集 (cells 集合)"""
    H, W = occ_cum.shape
    sel = pts[(pts[:, 2] >= Z_MEAS[0]) & (pts[:, 2] < Z_MEAS[1])]
    j, i = rasterize(sel[:, :2], RES, origin, (H, W))
    # 每格点数
    cnt = np.zeros((H, W), dtype=np.int32)
    np.add.at(cnt, (j, i), 1)
    # 每格 z 跨度
    zmin = np.full((H, W), 9e9, dtype=np.float32)
    zmax = np.full((H, W), -9e9, dtype=np.float32)
    np.minimum.at(zmin, (j, i), sel[:, 2])   # 重复格须用 .at 才能取到全局最小
    np.maximum.at(zmax, (j, i), sel[:, 2])

    remove = set()
    for occ in (occ_cum, occ_torso):
        lbl, n = ndimage.label(occ, structure=np.ones((3, 3)))
        sizes = ndimage.sum(occ, lbl, range(1, n + 1))
        for k in range(1, n + 1):
            sz = int(sizes[k - 1])
            if not (2 <= sz <= 16):
                continue
            ys, xs = np.where(lbl == k)
            if (zmax[ys, xs] - zmin[ys, xs]).max() < 0.8:
                continue          # 不满足人形 z 跨度
            dens = cnt[ys, xs].sum() / sz
            if dens >= max_dens:
                continue          # 密度高 = 真结构
            remove.update(zip(ys.tolist(), xs.tolist()))
    return remove


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('plys', nargs='+')
    ap.add_argument('--layers', required=True, help='layer_map.py 输出目录(含 cum_100_900_tristate.pgm/yaml)')
    ap.add_argument('--out', required=True, help='清洗后 ply 输出路径')
    ap.add_argument('--max-dens', type=float, default=100.0, help='人形块点密度上限(点/格)')
    args = ap.parse_args()

    if not HAVE_SCIPY:
        raise SystemExit('需要 scipy')

    # 1. 载点 + 地面 z0
    segs = []
    for p in args.plys:
        pts = load_ply(p)
        z0 = floor_z0(pts)
        pts[:, 2] -= z0
        segs.append(pts)
    pts = np.concatenate(segs)
    print(f'载入 {len(pts)} 点')

    # 2. 参考占用格 (注意 layer_map 写 PGM 时上下翻转, 读回须 flipud)
    cum = os.path.join(args.layers, 'cum_100_900_tristate.pgm')
    torso = os.path.join(args.layers, 'layer_900_1400.pgm')
    yaml_path = os.path.join(args.layers, 'cum_100_900_tristate.yaml')
    occ_cum = np.flipud(np.array(Image.open(cum)) == 0)
    occ_torso = np.flipud(np.array(Image.open(torso)) == 0)
    origin = parse_origin_yaml(yaml_path)
    if origin is None:
        raise SystemExit(f'{yaml_path} 无 origin')
    print(f'栅格 {occ_cum.shape} origin={origin}')

    # 3. 判定人形块
    cells = person_blob_cells(pts, occ_cum, occ_torso, origin, args.max_dens)
    print(f'人形块栅格: {len(cells)} 格')
    if not cells:
        print('未发现人形块, 直接复制原 ply')
        os.system(f'cp {args.plys[0]} {args.out}')
        raise SystemExit(0)

    # 4. 删除这些格的所有点 (全 z)
    sel = pts[:, :2]
    j, i = rasterize(sel, RES, origin, occ_cum.shape)
    is_person = np.array([(a, b) in cells for a, b in zip(j.tolist(), i.tolist())])
    keep = ~is_person
    print(f'删除 {is_person.sum()} 点 ({100*is_person.sum()/len(pts):.2f}%), 保留 {keep.sum()} 点')

    # 5. 输出清洗后 ply (binary LE, 与 layer_map 同格式)
    out = np.ascontiguousarray(pts[keep].astype('<f4'))
    with open(args.out, 'wb') as f:
        header = (f'ply\nformat binary_little_endian 1.0\n'
                  f'element vertex {len(out)}\n'
                  f'property float x\nproperty float y\nproperty float z\nend_header\n').encode()
        f.write(header)
        f.write(out.tobytes())
    print(f'已保存 {args.out}')


if __name__ == '__main__':
    main()
