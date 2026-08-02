#!/usr/bin/env python3
"""
R2 全向轮底盘 WASD 键盘遥控节点

为什么不用官方 teleop_twist_keyboard:
  官方的按键布局 (i/j/k/l + u/o/m/. 组合键) 与 R2 原有的 WASD 肌肉记忆冲突:
    - w/e/q/z/x/c 在官方布局里是"调速键"，按下去车不动，只改速度档位
    - u/o/m/. 一个按键同时产生"平移+旋转"两个状态
    - 横移 (linear.y) 必须按住 Shift + 大写键才有
  本节点:
    - 一键一状态，无组合键
    - w/s/a/d/q/e 与旧版 control/R2.py 完全一致
    - 任何未定义键 → 显式停车（不会静默）

按键布局（用户坐标系，chassis_node 内部已做 90° 变换）:
    w = 前进      s = 后退
    a = 左平移    d = 右平移
    q = 左转      e = 右转
    k / 空格 / 其他键 = 停车
    + / - = 加速 / 减速
    Ctrl-C = 退出并停车
"""

import sys
import threading
import termios
import tty

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


# 按键 → (linear.x, linear.y, angular.z)  单位：m/s, m/s, rad/s
# 每个键只改一个分量，保证"一键一状态"
KEY_MAP = {
    'w': ( 1,  0,  0),   # 前进
    's': (-1,  0,  0),   # 后退
    'a': ( 0,  1,  0),   # 左平移
    'd': ( 0, -1,  0),   # 右平移
    'q': ( 0,  0,  1),   # 左转 (CCW)
    'e': ( 0,  0, -1),   # 右转 (CW)
}

# 默认速度（用户坐标系，低于 chassis_node 限速 vx=0.5 vy=0.3 ω=0.8）
DEFAULT_VX = 0.3
DEFAULT_VY = 0.2
DEFAULT_WZ = 0.6
SPEED_STEP = 0.05      # +/- 调速步长

HELP = """
R2 WASD 键盘遥控
----------------
  w 前进    s 后退
  a 左移    d 右移
  q 左转    e 右转
  k / 空格 / 其他键  停车
  + / -    加速 / 减速
  Ctrl-C   退出并停车
"""


def get_key(settings):
    """从终端读一个字符（raw 模式）"""
    tty.setraw(sys.stdin.fileno())
    key = sys.stdin.read(1)
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    return key


class R2TeleopNode(Node):
    """WASD 键盘遥控节点：发布用户坐标系 /cmd_vel"""

    def __init__(self):
        super().__init__('r2_teleop_keyboard')

        self._pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # 当前目标速度
        self._vx = DEFAULT_VX
        self._vy = DEFAULT_VY
        self._wz = DEFAULT_WZ

        # 当前按键状态（无按键 → 停车）
        self._key_state = (0, 0, 0)
        self._key_lock = threading.Lock()
        self._running = True

        # 10Hz 持续发布：按住按键期间命令不中断，
        # 松开后由 chassis_node 的 0.5s cmd 超时兜底停车
        self._pub_timer = self.create_timer(0.1, self._publish_speed)

        # 终端原始设置（退出时恢复，防止 shell 残留 raw 模式）
        self._term_settings = termios.tcgetattr(sys.stdin.fileno())

        self.get_logger().info(HELP)
        self.get_logger().info(
            f'当前速度: vx={self._vx:.2f} vy={self._vy:.2f} ω={self._wz:.2f}')

    # ────────────────────────────────────────────────
    # 按键处理
    # ────────────────────────────────────────────────

    def handle_key(self, key):
        with self._key_lock:
            if key == '\x03':
                # Ctrl-C：raw 模式下不产生 SIGINT，作为 0x03 字节到达，
                # 必须显式识别并退出（与官方 teleop 行为一致）
                self._key_state = (0, 0, 0)
                self._running = False
            elif key in KEY_MAP:
                dx, dy, dz = KEY_MAP[key]
                # 按下即设定对应分量的目标速度（一键一状态，无组合）
                self._key_state = (dx, dy, dz)
            elif key in ('k', ' '):
                # 显式停车
                self._key_state = (0, 0, 0)
            elif key in ('+', '='):
                # 加速（整体比例，不超过底盘限速）
                self._scale_speed(1.0 + SPEED_STEP)
            elif key in ('-', '_'):
                self._scale_speed(1.0 - SPEED_STEP)
            else:
                # 任何未定义键 → 停车（与官方版"其他键=停止"一致，但按键表无歧义）
                self._key_state = (0, 0, 0)

    def _scale_speed(self, factor):
        self._vx = min(0.5, self._vx * factor)
        self._vy = min(0.3, self._vy * factor)
        self._wz = min(0.8, self._wz * factor)
        self.get_logger().info(
            f'调速 → vx={self._vx:.2f} vy={self._vy:.2f} ω={self._wz:.2f}')

    # ────────────────────────────────────────────────
    # 发布
    # ────────────────────────────────────────────────

    def _publish_speed(self):
        with self._key_lock:
            dx, dy, dz = self._key_state
            msg = Twist()
            msg.linear.x = dx * self._vx
            msg.linear.y = dy * self._vy
            msg.angular.z = dz * self._wz
            self._pub.publish(msg)

    def stop_and_exit(self):
        """退出前发停车命令"""
        with self._key_lock:
            self._key_state = (0, 0, 0)
        self._publish_speed()
        self._running = False

    # ────────────────────────────────────────────────
    # 主循环
    # ────────────────────────────────────────────────

    def run(self):
        try:
            while self._running and rclpy.ok():
                try:
                    key = get_key(self._term_settings)
                except Exception:
                    break
                # 多字节转义序列（方向键等）逐字节读入，各字节都会落入
                # 未定义键分支 → 停车，行为安全
                if key:
                    self.handle_key(key)
        except KeyboardInterrupt:
            pass
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._term_settings)


def main(args=None):
    rclpy.init(args=args)
    node = R2TeleopNode()

    # 键盘读取阻塞，用线程驱动
    thread = threading.Thread(target=node.run, daemon=True)
    thread.start()

    try:
        # 不用 rclpy.spin：Ctrl-C 在 raw 模式下作为 0x03 字节由键盘线程处理，
        # 主线程必须轮询 _running 才能感知退出
        while node._running and rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.1)
    except KeyboardInterrupt:
        # 兜底：终端处于正常模式的瞬间按 Ctrl-C 会走 SIGINT 路径
        pass
    finally:
        node.stop_and_exit()
        # 双保险恢复终端（键盘线程可能已被强杀，finally 未执行）
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, node._term_settings)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
