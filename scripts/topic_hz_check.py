#!/usr/bin/env python3
"""全车话题 hz 达标检测（并发单窗口测量）

用法:
  python3 topic_hz_check.py                 # 默认清单 + 10s 测量窗
  python3 topic_hz_check.py --seconds 15    # 自定义窗口（大消息/低频话题建议加长）
  python3 topic_hz_check.py --all           # 自动发现全部周期话题（无期望值，只报实测）

设计要点（对应 ros2-qos-dds.md 手册）:
  - 单窗口并发订阅全部话题，一次出结果（CLI `ros2 topic hz` 逐话题 8s × N 太慢）
  - QoS 自动适配: 先 reliable 3s, 0 消息自动换 best_effort（大消息 reliable 发布端
    若用 best_effort 订阅会有损丢帧 → 假性掉 hz; 见 doc/ros2-qos-dds.md §二/§三）
  - 期望值容差: 实测/期望 ∈ [0.75, 1.6] 判达标; 事件性话题(goal/plan/transition)不测

期望表依据: 09-06 实测 bag 消息数/时长推算 (box_lowband_20260906_091644)
  odom_wheels 50Hz, odometry/filtered 30Hz, imu/data ~85Hz, tf ~40Hz,
  points/scan/packets 10Hz, local costmap_raw ~1.7Hz, voxel_grid 5Hz
"""
import sys
import time
import argparse

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy

# (话题, 期望Hz) —— 当前 R2 栈周期话题; 按需增删
# 注意:
#   - amcl_pose 车静止不发(事件性), tf_static 启动发一次(transient_local) → 均不入 hz 表
#   - costmap 类发布受 update 节流; global 大图实测 0.64Hz(名义 1.0) = 已知观察项(09-06)
DEFAULT_WATCH = [
    ('/velodyne_points', 10.0),
    ('/velodyne_packets', 10.0),
    ('/scan', 10.0),
    ('/odom_wheels', 50.0),
    ('/odometry/filtered', 30.0),
    ('/imu/data', 85.0),
    ('/tf', 40.0),
    ('/diagnostics', 18.0),   # greenwave 周期发布实测 ~18Hz
    ('/local_costmap/costmap_raw', 2.0),
    ('/local_costmap/voxel_grid', 5.0),
    ('/local_costmap/clearing_endpoints', 10.0),
    ('/global_costmap/costmap_raw', 1.0),
]

# transient_local 话题（只发一次/低频，需 TL 订阅才能收到当前值）: 发布端一般 reliable+transient_local
TRANSIENT_LOCAL_TOPICS = {'/tf_static', '/map', '/robot_description', '/global_costmap/costmap', '/local_costmap/costmap'}

class HZProbe(Node):
    def __init__(self, watch, window_s, discover_all=False):
        super().__init__('hz_probe')
        self.counts = {t: 0 for t, _ in watch}
        self.subs = {}
        topics = [t for t, _ in watch]
        if discover_all:
            known = set(topics)
            allt = self.get_topic_names_and_types()
            for name, _ in allt:
                if name in known or name.startswith('/rosout') or \
                   name == '/parameter_events' or name.endswith('/transition_event') or \
                   '/bond' in name:
                    continue
                topics.append(name)
                self.counts[name] = 0
        for t in topics:
            self._subscribe(t)
        self.window_s = window_s

    def _qos_reliable(self):
        q = QoSProfile(depth=20, durability=DurabilityPolicy.VOLATILE)
        return q

    def _subscribe(self, topic):
        # reliable 订阅（点云等大消息防丢帧; 若发布端 best_effort 会收不到 → 零消息后换 best_effort）
        # transient_local 话题（tf_static 等）须 TL 才能收到已发布值
        if topic in TRANSIENT_LOCAL_TOPICS:
            q = QoSProfile(reliability=ReliabilityPolicy.RELIABLE,
                           durability=DurabilityPolicy.TRANSIENT_LOCAL,
                           history=HistoryPolicy.KEEP_LAST, depth=5)
        else:
            q = QoSProfile(reliability=ReliabilityPolicy.RELIABLE,
                           history=HistoryPolicy.KEEP_LAST, depth=50)
        try:
            self.subs[topic] = self.create_subscription(
                self._type_of(topic), topic, lambda m, t=topic: self._cb(t), q)
        except Exception:
            self.counts.pop(topic, None)

    def _type_of(self, topic):
        for name, types in self.get_topic_names_and_types():
            if name == topic:
                for ty in types:
                    try:
                        from rosidl_runtime_py.utilities import get_message
                        return get_message(ty)
                    except Exception:
                        pass
        raise RuntimeError(f'no type for {topic}')

    def _cb(self, topic):
        self.counts[topic] = self.counts.get(topic, 0) + 1

    def run(self):
        t_start = time.time()
        while time.time() - t_start < self.window_s:
            rclpy.spin_once(self, timeout_sec=0.2)
        # 零消息话题换 best_effort 补测
        retry = [t for t, c in self.counts.items() if c == 0]
        for t in retry:
            try:
                q = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT,
                               history=HistoryPolicy.KEEP_LAST, depth=50)
                self.destroy_subscription(self.subs[t])
                self.subs[t] = self.create_subscription(
                    self._type_of(t), t, lambda m, t=t: self._cb(t), q)
            except Exception:
                pass
        t2 = time.time()
        while time.time() - t2 < 4.0:
            rclpy.spin_once(self, timeout_sec=0.2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=10.0)
    ap.add_argument('--all', action='store_true')
    args = ap.parse_args()

    rclpy.init()
    exp = dict(DEFAULT_WATCH)
    probe = HZProbe(DEFAULT_WATCH, args.seconds, discover_all=args.all)
    probe.run()
    t_meas = args.seconds + 4.0  # 含 best_effort 补测窗
    rclpy.shutdown()

    print(f'\n=== 话题 hz 检测（测量窗 ~{args.seconds:.0f}s）===')
    print(f'{"话题":<42}{"实测Hz":>8}{"期望":>7}  判定')
    print('-' * 72)
    n_ok = n_bad = n_na = 0
    for t, c in sorted(probe.counts.items()):
        hz = c / t_meas
        if t in exp:
            e = exp[t]
            if c == 0:
                verdict, n_na = '⚠️ 无数据(检查发布端/QoS)', n_na + 1
            elif 0.75 * e <= hz <= 1.6 * e:
                verdict, n_ok = '✅', n_ok + 1
            else:
                verdict, n_bad = '❌', n_bad + 1
            print(f'{t:<42}{hz:8.2f}{e:7.0f}  {verdict}')
        else:
            print(f'{t:<42}{hz:8.2f}{"-":>7}  {"⚠️" if c==0 else "–"}')
    print('-' * 72)
    print(f'达标 {n_ok} / 不达标 {n_bad} / 无数据 {n_na}')

if __name__ == '__main__':
    main()
