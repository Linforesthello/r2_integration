#!/usr/bin/env python3
# VM 验收 reader：订阅 standalone costmap raw（nav2_msgs/msg/Costmap），记录 lethal(254→int8 -2) 格
# 世界坐标 (x,y, t) → jsonl。判据见分析脚本。
import rclpy, json
from rclpy.node import Node
from nav2_msgs.msg import Costmap

class Reader(Node):
    def __init__(self):
        super().__init__('vm_mark_reader')
        self.create_subscription(Costmap, '/costmap/costmap_raw', self.cb, 10)
        self.out = open('/tmp/vm_new_marks.jsonl', 'w')
    def cb(self, msg):
        meta = msg.metadata
        w, h, res = meta.size_x, meta.size_y, meta.resolution
        ox, oy = meta.origin.position.x, meta.origin.position.y
        marks = []
        for i, v in enumerate(msg.data):
            if v == 254:  # raw 实测 lethal 存 254 原值（08-25 文档 + 判别轮实证；非 -2）
                marks.append([round(ox + (i % w + 0.5) * res, 3), round(oy + (i // w + 0.5) * res, 3)])
        if marks:
            st = msg.header.stamp
            rec = {"t": round(st.sec + st.nanosec * 1e-9, 3), "frame": msg.header.frame_id, "n": len(marks), "marks": marks}
            self.out.write(json.dumps(rec) + "\n")
            self.out.flush()
            self.get_logger().info(f"t={rec['t']:.2f} n254={len(marks)}")

rclpy.init()
r = Reader()
try:
    rclpy.spin(r)
except KeyboardInterrupt:
    pass
r.out.close()
