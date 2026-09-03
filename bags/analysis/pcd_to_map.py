#!/usr/bin/env python3
"""PLY → 2D 占用网格（PGM+YAML，Nav2 map_server 格式）

流程: 读点云 → z 高度滤波(0.3<z<1.5m) → xy 栅格化 → 占用阈值 → map.pgm/map.yaml
用法: python3 pcd_to_map.py <input.ply> [输出.pgm] [分辨率=0.05] [z_min=0.3] [z_max=1.5] [占用阈值=3]
注: z_min 默认 0.3（2026-08-13 修正）：雷达装高 0.56m，z<0.3 为下射环地面点，
    投影产生"地面雾"（0811 地图 28% 占用格来自地面），z_min=0.1 时雾严重
"""
import sys
import numpy as np


def read_ply_bin(path):
    with open(path, 'rb') as f:
        header = b''
        while True:
            line = f.readline()
            header += line
            if line.startswith(b'end_header'):
                break
        n = int([l for l in header.decode().splitlines()
                 if l.startswith('element vertex')][0].split()[-1])
        data = f.read(n * 12)
    return np.frombuffer(data, dtype='<f4').reshape(n, 3)


def to_map(xyz, res=0.05, z_min=0.3, z_max=1.5, occ_thresh=3):
    """z 高度滤波后 xy 栅格化，命中 >=occ_thresh 的格为占用(100)"""
    mask = (xyz[:, 2] > z_min) & (xyz[:, 2] < z_max)
    pts = xyz[mask][:, :2]
    if len(pts) == 0:
        raise SystemExit('滤波后无点')
    x_min, y_min = pts.min(axis=0) - 1.0
    x_max, y_max = pts.max(axis=0) + 1.0
    w = int((x_max - x_min) / res)
    h = int((y_max - y_min) / res)
    grid = np.zeros((h, w), dtype=np.int32)
    ix = ((pts[:, 0] - x_min) / res).astype(int)
    iy = ((pts[:, 1] - y_min) / res).astype(int)
    np.add.at(grid, (iy, ix), 1)
    occ = np.where(grid >= occ_thresh, 100, 0).astype(np.uint8)
    return occ, x_min, y_min, res


def save_pgm(path, occ):
    with open(path, 'wb') as f:
        f.write(b'P5\n%d %d\n255\n' % (occ.shape[1], occ.shape[0]))
        f.write(occ.tobytes())


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    ply = sys.argv[1]
    pgm = sys.argv[2] if len(sys.argv) > 2 else 'map.pgm'
    res = float(sys.argv[3]) if len(sys.argv) > 3 else 0.05
    z_min = float(sys.argv[4]) if len(sys.argv) > 4 else 0.3
    z_max = float(sys.argv[5]) if len(sys.argv) > 5 else 1.5
    thr = int(sys.argv[6]) if len(sys.argv) > 6 else 3

    occ, ox, oy, res = to_map(read_ply_bin(ply), res, z_min, z_max, thr)
    save_pgm(pgm, occ)
    yaml = (f"image: {pgm}\n"
            f"resolution: {res}\n"
            f"origin: [{ox}, {oy}, 0.0]\n"
            f"negate: 0\n"
            f"occupied_thresh: 0.65\n"
            f"free_thresh: 0.25\n")
    open('map.yaml', 'w').write(yaml)
    print(f'地图 {occ.shape[1]}x{occ.shape[0]} 格，原点 ({ox:.2f},{oy:.2f})，分辨率 {res}')
    print(f'输出: {pgm} + map.yaml')
