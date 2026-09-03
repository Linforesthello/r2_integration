#!/usr/bin/env python3
"""逐帧对比 KISS-ICP 里程计 vs EKF 融合里程计，检测纯激光位姿漂移（旋转退化）

原理（2026-08-13 验证方法论）:
  - EKF(/odometry/filtered, IMU+轮速) 为可信基准；KISS(/kiss/odometry) 为纯激光估计
  - 时间对齐: EKF 线性插值到 KISS 帧时刻
  - 起点对齐: KISS 轨迹按起始 yaw 差旋转到 EKF 基准（两系仅差初始朝向）
  - 逐帧位置偏差 = |KISS_aligned - EKF|；偏差大 → 纯激光在该时刻漂移
  - 实测结论: 直行 <1cm；前进转弯(带平移约束) <10cm 无残留；
             原地旋转(纯旋转退化) 10-18cm 且结束残留 >10cm → 重影风险

用法: python3 analyze_kiss_vs_ekf.py <bag_dir> [输出CSV路径]
输出: 逐帧表（抽帧+偏差大帧全列）+ 每4s段偏差统计 + 结论
"""
import sys
import numpy as np
import rosbag2_py
import rclpy.serialization as s
from nav_msgs.msg import Odometry


def quat2yaw(q):
    return np.arctan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


def load(seg):
    dr = rosbag2_py.SequentialReader()
    dr.open(rosbag2_py.StorageOptions(uri=seg, storage_id='sqlite3'),
            rosbag2_py.ConverterOptions('', 'cdr'))
    k, e = [], []
    while dr.has_next():
        topic, data, t = dr.read_next()
        if topic == '/kiss/odometry':
            o = s.deserialize_message(data, Odometry())
            k.append((t / 1e9, o.pose.pose.position.x, o.pose.pose.position.y,
                      quat2yaw(o.pose.pose.orientation)))
        elif topic == '/odometry/filtered':
            o = s.deserialize_message(data, Odometry())
            e.append((t / 1e9, o.pose.pose.position.x, o.pose.pose.position.y,
                      quat2yaw(o.pose.pose.orientation)))
    return np.array(k), np.array(e)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    k, e = load(sys.argv[1])
    print(f"KISS {len(k)} 帧 {k[-1, 0] - k[0, 0]:.1f}s "
          f"({len(k) / (k[-1, 0] - k[0, 0]):.1f}Hz) | EKF {len(e)} 帧")
    print(f"KISS yaw: min={np.degrees(k[:, 3]).min():.1f}° max={np.degrees(k[:, 3]).max():.1f}° "
          f"范围{np.degrees(k[:, 3]).max() - np.degrees(k[:, 3]).min():.0f}° "
          f"净旋转{np.degrees(k[-1, 3] - k[0, 3]):.1f}°")
    print(f"EKF  yaw: min={np.degrees(e[:, 3]).min():.1f}° max={np.degrees(e[:, 3]).max():.1f}° "
          f"范围{np.degrees(e[:, 3]).max() - np.degrees(e[:, 3]).min():.0f}° "
          f"净旋转{np.degrees(e[-1, 3] - e[0, 3]):.1f}°")
    print(f"KISS 位移: 累计路径 {np.hypot(np.diff(k[:, 1]), np.diff(k[:, 2])).sum():.2f}m")
    print(f"EKF  位移: 累计路径 {np.hypot(np.diff(e[:, 1]), np.diff(e[:, 2])).sum():.2f}m")
    print()

    # 时间对齐（EKF 插值到 KISS 帧时刻）
    ex = np.interp(k[:, 0], e[:, 0], e[:, 1])
    ey = np.interp(k[:, 0], e[:, 0], e[:, 2])
    eyaw = np.interp(k[:, 0], e[:, 0], e[:, 3])
    # 起点对齐（KISS 旋转到 EKF 基准）
    yaw0 = k[0, 3] - e[0, 3]
    c, s_ = np.cos(yaw0), np.sin(yaw0)
    kx = (k[:, 1] - k[0, 1]) * c + (k[:, 2] - k[0, 2]) * s_
    ky = -(k[:, 1] - k[0, 1]) * s_ + (k[:, 2] - k[0, 2]) * c
    dist = np.hypot(kx - (ex - e[0, 1]), ky - (ey - e[0, 2]))
    kyaw = np.degrees(k[:, 3])
    t_rel = k[:, 0] - k[0, 0]

    # 逐帧表：抽帧（每3帧一行），偏差大帧全列
    print("帧 | 时间 | KISS_yaw | EKF_yaw | KISS位移 | EKF位移 | 偏差")
    for i in range(len(k)):
        turning = abs(kyaw[i] - np.degrees(eyaw[i])) > 10
        if i % 3 == 0 or turning:
            print(f"{i:3d}|{t_rel[i]:5.1f}s|{kyaw[i]:6.1f}°|{np.degrees(eyaw[i]):6.1f}°|"
                  f"{np.hypot(kx[i], ky[i]) * 100:5.1f}cm|"
                  f"{np.hypot(ex[i] - e[0, 1], ey[i] - e[0, 2]) * 100:5.1f}cm|"
                  f"{dist[i] * 100:5.1f}cm")
    print("\n=== 每 4s 段偏差统计 ===")
    for t0 in np.arange(0, t_rel[-1], 4):
        m = (t_rel >= t0) & (t_rel < t0 + 4)
        if m.sum():
            print(f"{t0:3.0f}-{t0 + 4:3.0f}s: max偏差={dist[m].max() * 100:5.1f}cm "
                  f"KISS位移max={np.hypot(kx[m], ky[m]).max() * 100:4.0f}cm "
                  f"EKF={np.hypot(ex[m] - e[0, 1], ey[m] - e[0, 2]).max() * 100:4.0f}cm")

    # 结论判定（2026-08-13 实测阈值）
    final = dist[-10:]
    peak = dist.max() * 100
    res = final.mean() * 100
    print(f"\n=== 结论 ===")
    print(f"峰值偏差 {peak:.1f}cm / 结束段残留 {res:.1f}cm")
    if res > 10:
        print("⚠️ 旋转退化严重（残留>10cm）→ 建图重影风险；录制避免原地旋转，用前进+转弯")
    elif peak < 10:
        print("✅ 位姿质量好（峰值<10cm）→ 可作建图录制")
    else:
        print("🟡 峰值偏差 10cm 级 → 检查是否含原地旋转段；前进转弯可接受，原地转不可")


if __name__ == '__main__':
    main()
