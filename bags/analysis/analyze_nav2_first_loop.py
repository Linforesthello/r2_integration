#!/usr/bin/env python3
"""Nav2 首次闭环 bag 分析（2026-08-15 nav2_first_loop）

指标:
  1. AMCL 轨迹: 起点/终点/总位移/运动时长（/amcl_pose）
  2. 实际速度: /cmd_vel_smoothed vx/vy/wz 峰值与均值（验证降额 0.2/0.15/0.4 未超限）
  3. 规划: /plan 路径数
  4. 粒子收敛: /particle_cloud 首帧 vs 末帧粒子分布方差
官方 rosbag2_py，全序列读取（采样纪律：不降采样）。
"""
import sys, math
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from nav_msgs.msg import Path
from nav2_msgs.msg import ParticleCloud


def read_msgs(bag_dir):
    reader = SequentialReader()
    reader.open(StorageOptions(uri=bag_dir, storage_id='sqlite3'),
                ConverterOptions(input_serialization_format='cdr', output_serialization_format='cdr'))
    out = {'/amcl_pose': [], '/cmd_vel_smoothed': [], '/cmd_vel': [], '/plan': [], '/particle_cloud': []}
    while reader.has_next():
        topic, data, ts = reader.read_next()
        if topic not in out:
            continue
        m = deserialize_message(data, eval({'/amcl_pose': 'PoseWithCovarianceStamped',
                                            '/cmd_vel_smoothed': 'Twist', '/cmd_vel': 'Twist',
                                            '/plan': 'Path', '/particle_cloud': 'ParticleCloud'}[topic]))
        t = ts * 1e-9
        out[topic].append((t, m))
    return out


def main(bag_dir):
    msgs = read_msgs(bag_dir)
    # 1. AMCL 轨迹
    poses = msgs['/amcl_pose']
    p0 = poses[0][1].pose.pose.position
    p1 = poses[-1][1].pose.pose.position
    d = math.hypot(p1.x - p0.x, p1.y - p0.y)
    dist = 0.0
    for (t0, a), (t1, b) in zip(poses, poses[1:]):
        dist += math.hypot(b.pose.pose.position.x - a.pose.pose.position.x,
                           b.pose.pose.position.y - a.pose.pose.position.y)
    print(f"[AMCL 轨迹] {len(poses)} 帧  起点({p0.x:.2f},{p0.y:.2f}) → 终点({p1.x:.2f},{p1.y:.2f})")
    print(f"  直线位移 {d:.2f} m | 累计路程 {dist:.2f} m | 首末帧 {poses[-1][0]-poses[0][0]:.1f}s")
    # 2. 速度（smoothed = 实际下发底盘）
    for topic in ['/cmd_vel', '/cmd_vel_smoothed']:
        v = msgs[topic]
        vx = [abs(m.linear.x) for _, m in v]
        vy = [abs(m.linear.y) for _, m in v]
        wz = [abs(m.angular.z) for _, m in v]
        nz = sum(1 for x in vx if x > 1e-4)
        print(f"[{topic}] {len(v)} 条 | 非零指令 {nz} 条 | 峰值 vx {max(vx):.3f} vy {max(vy):.3f} "
              f"wz {max(wz):.3f} | 均值(非零) vx {sum(vx)/nz if nz else 0:.3f} vy {sum(vy)/nz if nz else 0:.3f} "
              f"wz {sum(wz)/nz if nz else 0:.3f} | 限幅 0.2/0.15/0.4")
    # 3. 规划次数
    print(f"[/plan] {len(msgs['/plan'])} 次路径发布")
    # 4. 粒子收敛: 首帧 vs 末帧 x/y 方差
    pc = msgs['/particle_cloud']
    if len(pc) >= 2:
        for label, i in [('首帧', 0), ('末帧', -1)]:
            ps = pc[i][1].particles
            xs = [p.pose.position.x for p in ps]
            ys = [p.pose.position.y for p in ps]
            mx, my = sum(xs)/len(xs), sum(ys)/len(ys)
            vx = sum((x-mx)**2 for x in xs)/len(xs)
            vy = sum((y-my)**2 for y in ys)/len(ys)
            print(f"[粒子 {label}] n={len(ps)} σx {math.sqrt(vx):.3f}m σy {math.sqrt(vy):.3f}m "
                  f"中心({mx:.2f},{my:.2f})")


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '/home/lin/Lin_workspace/r2_integration/bags/raw/nav2_first_loop')
