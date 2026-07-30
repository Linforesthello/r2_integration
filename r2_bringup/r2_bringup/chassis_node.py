#!/usr/bin/env python3
"""
R2 全向轮底盘 CAN 控制节点

架构:
  ROS2 /cmd_vel → 运动学逆解 → CAN 命令 → MCLM 电机
  CAN 状态帧 ← MCLM 电机 → 运动学正解 → /odom_wheels + TF

坐标系:
  vx⁺ = 前进方向 (车头)
  vy⁺ = 左侧方向
  ω⁺  = 逆时针旋转 (从上方看)

运动学:
  已由 Lin_workspace/control/R2.py 实测验证
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster
import math
import threading
import struct


# ═══════════════════════════════════════════════════════════
# 运动学常量
# ═══════════════════════════════════════════════════════════

INV_SQRT2 = 1.0 / math.sqrt(2)

# R2 CAN ID 映射
#   物理布局（逆时针）: 0x123(FL) → 0x124(RL) → 0x125(RR) → 0x126(FR)
#   在配置 MCLM 固件时: 0x123(FL) 和 0x124(RL) 用 CAN_ID_GROUP=2
#                       0x125(RR) 和 0x126(FR) 用 CAN_ID_GROUP=1
R2_MOTOR_IDS    = [0x123, 0x126, 0x124, 0x125]  # FL, FR, RL, RR
R2_STATUS_IDS   = [0x323, 0x326, 0x324, 0x325]  # 状态 ID = 命令 ID + 0x200
R2_MOTOR_NAMES  = ['FL', 'FR', 'RL', 'RR']

# CAN 状态帧字节索引
IDX_CURRENT_SPEED_L  = 0    # [0-1] current_logic_speed  (int16 LE)
IDX_ACCUM_TICKS_L    = 2    # [2-3] accumulated_ticks    (uint16 LE)
IDX_PWM_OUTPUT_L     = 4    # [4-5] pwm_output           (int16 LE)
IDX_TARGET_SPEED     = 6    # [6]   target_logic_speed   (int8)
IDX_FLAGS            = 7    # [7]   flags                (uint8)

# CAN 命令字节
CMD_SET_SPEED = 0x11
CMD_STOP      = 0x08

# 状态帧标志位
FLAG_STALL     = 0x01
FLAG_SATURATED = 0x02

# ── 默认物理参数（会被 yaml 覆盖）──
DEFAULT_HALF_DIAGONAL = 0.33      # R (m) — 车体中心到轮子的半对角线长
DEFAULT_TICKS_PER_REV = 4241      # ticks/圈 — 实测均值
DEFAULT_WHEEL_DIAMETER = 0.152     # 轮径 (m)
# speed_scale: 逻辑速度 → m/s 的换算系数
# 实测: speed=10 → 940 ticks/s → 0.1058 m/s → 10/0.1058 = 94.5
# 含义: 按 MCLM 固件的映射，1 m/s 轮速度 = 94.5 逻辑速度单位
DEFAULT_SPEED_SCALE = 94.5


# ═══════════════════════════════════════════════════════════
# 运动学函数（无状态，纯数学）
# ═══════════════════════════════════════════════════════════

def omni_inverse(vx: float, vy: float, omega: float, R: float) -> list:
    """
    R2 四全向轮逆解：车体速度 → 4 轮逻辑速度

    参数:
      vx: 前进速度 (m/s, +前)
      vy: 侧向速度 (m/s, +左)
      omega: 旋转角速度 (rad/s, +逆时针)
      R: 半对角线长 (m)

    返回:
      [FL, FR, RL, RR] 逻辑速度 (-100~100 范围，未限幅)

    公式来源:
      R2.py 已实测验证
    """
    return [
        ( vx + vy) * INV_SQRT2 - R * omega,   # FL
        ( vx - vy) * INV_SQRT2 - R * omega,   # FR
        (-vx + vy) * INV_SQRT2 - R * omega,   # RL
        (-vx - vy) * INV_SQRT2 - R * omega,   # RR
    ]


def omni_forward(fl: float, fr: float, rl: float, rr: float, R: float):
    """
    R2 四全向轮正解：4 轮速度 → 车体速度

    参数:
      fl/fr/rl/rr: 四轮逻辑速度（与逆解同量纲）
      R: 半对角线长 (m)

    返回:
      (vx, vy, omega) — 车体速度

    推导:
      从逆解公式反推的线性方程组解
    """
    vx = (fl + fr - rl - rr) / (4.0 * INV_SQRT2)
    vy = (fl - fr + rl - rr) / (4.0 * INV_SQRT2)
    omega = -(fl + fr + rl + rr) / (4.0 * R)
    return vx, vy, omega


# ═══════════════════════════════════════════════════════════
# CAN 协议解析
# ═══════════════════════════════════════════════════════════

def decode_status_frame(data: bytes) -> dict:
    """
    解析 MCLM_t2 状态帧（8 字节）

    帧格式:
      [0-1] current_logic_speed  (int16 LE)  -100~100
      [2-3] accumulated_ticks    (uint16 LE)
      [4-5] pwm_output           (int16 LE)
      [6]   target_logic_speed   (int8)
      [7]   flags                (uint8)
    """
    if len(data) < 8:
        return None

    current_speed = struct.unpack_from('<h', data, IDX_CURRENT_SPEED_L)[0]
    accum_ticks   = struct.unpack_from('<H', data, IDX_ACCUM_TICKS_L)[0]
    pwm_output    = struct.unpack_from('<h', data, IDX_PWM_OUTPUT_L)[0]
    target_speed  = struct.unpack_from('<b', data, IDX_TARGET_SPEED)[0]
    flags         = data[IDX_FLAGS]

    return {
        'current_speed': current_speed,
        'accum_ticks':   accum_ticks,
        'pwm_output':    pwm_output,
        'target_speed':  target_speed,
        'stall':         bool(flags & FLAG_STALL),
        'saturated':     bool(flags & FLAG_SATURATED),
    }


def build_speed_cmd(speed: int) -> bytes:
    """
    构建速度命令帧

    [0] = 0x11 (CMD_SET_SPEED)
    [1] = speed_clamped (int8, -100~+100)
    [2~7] = 0x00
    """
    speed_clamped = max(-100, min(100, speed))
    return bytes([CMD_SET_SPEED, speed_clamped & 0xFF, 0, 0, 0, 0, 0, 0])


# ═══════════════════════════════════════════════════════════
# ROS2 节点
# ═══════════════════════════════════════════════════════════

class R2ChassisNode(Node):
    """
    R2 全向轮底盘 CAN 控制节点

    职责:
      /cmd_vel → 运动学逆解 → CAN 命令 → MCLM 电机控制器
      CAN 状态帧 → 运动学正解 → 里程计 → /odom_wheels + TF
    """

    def __init__(self):
        super().__init__('r2_chassis_node')

        # ── 参数 ──
        self.declare_parameter('can_channel', 'can0')
        self.declare_parameter('wheel_half_diagonal', DEFAULT_HALF_DIAGONAL)
        self.declare_parameter('ticks_per_rev', DEFAULT_TICKS_PER_REV)
        self.declare_parameter('wheel_diameter', DEFAULT_WHEEL_DIAMETER)
        self.declare_parameter('speed_scale', DEFAULT_SPEED_SCALE)
        self.declare_parameter('cmd_timeout', 0.5)           # 无 cmd_vel 多久后停 (s)
        self.declare_parameter('odom_publish_rate', 50.0)    # odom 发布频率 (Hz)
        self.declare_parameter('max_vx', 0.5)                # m/s
        self.declare_parameter('max_vy', 0.3)                # m/s
        self.declare_parameter('max_omega', 0.8)             # rad/s

        self._R = self.get_parameter('wheel_half_diagonal').value
        self._ticks_per_rev = self.get_parameter('ticks_per_rev').value
        self._wheel_diameter = self.get_parameter('wheel_diameter').value
        # 逻辑速度 → m/s 换算系数
        self._speed_scale = self.get_parameter('speed_scale').value
        self._cmd_timeout = self.get_parameter('cmd_timeout').value
        self._max_vx = self.get_parameter('max_vx').value
        self._max_vy = self.get_parameter('max_vy').value
        self._max_omega = self.get_parameter('max_omega').value

        # CAN 接口
        self._can_channel = self.get_parameter('can_channel').value
        self._can_bus = None
        self._can_lock = threading.Lock()

        # ── 状态 ──
        # 最新状态帧（key = CAN ID）
        self._motor_status: dict[int, dict] = {}
        self._status_lock = threading.Lock()

        # 上次 CAN 状态帧时间（用于超时检测）
        self._last_status_time: dict[int, float] = {}
        for sid in R2_STATUS_IDS:
            self._last_status_time[sid] = 0.0

        # 里程计状态
        self._odom_x = 0.0
        self._odom_y = 0.0
        self._odom_yaw = 0.0
        self._odom_last_time = None

        # cmd_vel 超时
        self._last_cmd_time = 0.0

        # 里程计刻度: 每 tick = 多少米轮子前进距离
        self._m_per_tick = math.pi * self._wheel_diameter / self._ticks_per_rev

        # ── ROS2 接口 ──
        # 订阅 /cmd_vel
        self._cmd_sub = self.create_subscription(
            Twist, '/cmd_vel', self._cmd_callback, 10)

        # 发布 /odom_wheels
        self._odom_pub = self.create_publisher(Odometry, '/odom_wheels', 10)

        # TF 广播 (odom → base_link)
        self._tf_broadcaster = TransformBroadcaster(self)

        # odom 发布定时器
        odom_period = 1.0 / self.get_parameter('odom_publish_rate').value
        self._odom_timer = self.create_timer(odom_period, self._publish_odom)

        # 状态帧超时检测定时器（1Hz）
        self._diag_timer = self.create_timer(1.0, self._check_motor_health)

        # ── 初始化 CAN ──
        self._init_can()

        self.get_logger().info('R2 底盘节点已启动')
        self.get_logger().info(f'  半对角线 R = {self._R:.3f} m')
        self.get_logger().info(f'  wheel_diameter = {self._wheel_diameter:.3f} m')
        self.get_logger().info(f'  ticks_per_rev = {self._ticks_per_rev}')
        self.get_logger().info(f'  m_per_tick = {self._m_per_tick:.6f} m')
        self.get_logger().info(f'  speed_scale = {self._speed_scale:.1f} (逻辑速度→m/s)')
        self.get_logger().info(f'  限速: vx={self._max_vx}, vy={self._max_vy}, ω={self._max_omega}')

    # ────────────────────────────────────────────────
    # CAN 总线
    # ────────────────────────────────────────────────

    def _init_can(self):
        """初始化 CAN 总线并启动接收线程"""
        try:
            import can
            self._can_bus = can.interface.Bus(
                channel=self._can_channel,
                interface='socketcan',
                bitrate=1000000,
            )
            self.get_logger().info(f'CAN 接口已打开: {self._can_channel}')

            # 后台接收线程
            self._rx_running = True
            self._rx_thread = threading.Thread(target=self._can_rx_loop, daemon=True)
            self._rx_thread.start()

        except Exception as e:
            self.get_logger().error(f'CAN 初始化失败: {e}')
            self.get_logger().error('请确认: sudo ip link set can0 up type can bitrate 1000000')
            raise

    def _can_rx_loop(self):
        """后台 CAN 接收线程"""
        while self._rx_running and self._can_bus:
            try:
                msg = self._can_bus.recv(timeout=0.1)
                if msg is None:
                    continue

                can_id = msg.arbitration_id
                # 只处理状态帧 (0x323~0x326)
                if can_id in R2_STATUS_IDS and len(msg.data) >= 8:
                    status = decode_status_frame(msg.data)
                    if status:
                        with self._status_lock:
                            self._motor_status[can_id] = status
                        self._last_status_time[can_id] = self.get_clock().now().nanoseconds * 1e-9

            except Exception as e:
                if self._rx_running:
                    self.get_logger().warn(f'CAN 接收异常: {e}')

    # ────────────────────────────────────────────────
    # /cmd_vel 处理
    # ────────────────────────────────────────────────

    def _cmd_callback(self, msg: Twist):
        """/cmd_vel 回调 → 运动学逆解 → CAN 命令"""
        # ── 坐标变换 ──
        # 实测校准（8 组轮速组合验证）:
        #   公式 vx+ → 实际右移     公式 vy+ → 实际前进
        #   公式 vx- → 实际左移     公式 vy- → 实际后退
        #   公式 ω+  → 实际左旋 ✅  (omega 方向正确，无需变换)
        # 结论: kin_vx = -user_vy,  kin_vy = user_vx
        vx = max(-self._max_vy, min(self._max_vy, -msg.linear.y))
        vy = max(-self._max_vx, min(self._max_vx, msg.linear.x))
        omega = max(-self._max_omega, min(self._max_omega, msg.angular.z))

        # 逆解 → 各轮速度 (m/s)
        speeds_mps = omni_inverse(vx, vy, omega, self._R)

        # 映射到 CAN 逻辑速度 (-100~100)
        speeds_logic = []
        for s in speeds_mps:
            logic = int(round(s * self._speed_scale))
            logic = max(-100, min(100, logic))
            speeds_logic.append(logic)

        # 发送 CAN 命令
        self._send_speeds(speeds_logic)
        self._last_cmd_time = self.get_clock().now().nanoseconds * 1e-9

    def _send_speeds(self, speeds: list):
        """向 4 个电机发送速度命令（带锁）"""
        if self._can_bus is None:
            return

        import can
        msgs = []
        for i, can_id in enumerate(R2_MOTOR_IDS):
            speed_raw = int(speeds[i])
            msgs.append(can.Message(
                arbitration_id=can_id,
                data=build_speed_cmd(speed_raw),
                is_extended_id=False,
            ))

        with self._can_lock:
            for m in msgs:
                try:
                    self._can_bus.send(m)
                except Exception as e:
                    self.get_logger().warn(f'CAN 发送失败 [{hex(m.arbitration_id)}]: {e}')

    # ────────────────────────────────────────────────
    # 里程计
    # ────────────────────────────────────────────────

    def _compute_chassis_speed(self):
        """
        从最新状态帧计算车体速度

        用 logic_speed 直接做正解（线性，量纲一致即可），
        再通过物理参数换算为 m/s 和 rad/s。
        """
        with self._status_lock:
            statuses = dict(self._motor_status)

        if len(statuses) < 4:
            return None

        # 提取逻辑速度（正解只关心速度比例，不关心量纲）
        # 因此直接用 logic_speed 做正解，再换算为物理量
        speed_map = {}
        for can_id, s in statuses.items():
            speed_map[can_id] = s['current_speed']

        # 确保 4 个 ID 都有数据
        try:
            fl_logic = speed_map[R2_STATUS_IDS[0]]   # 0x323 → FL
            fr_logic = speed_map[R2_STATUS_IDS[1]]   # 0x326 → FR
            rl_logic = speed_map[R2_STATUS_IDS[2]]   # 0x324 → RL
            rr_logic = speed_map[R2_STATUS_IDS[3]]   # 0x325 → RR
        except KeyError:
            return None

        # 用逻辑速度做正解，得到"逻辑车体速度"（公式坐标系）
        vx_f, vy_f, omega_f = omni_forward(fl_logic, fr_logic, rl_logic, rr_logic, self._R)

        # 物理量换算
        vx_f = vx_f / self._speed_scale
        vy_f = vy_f / self._speed_scale
        omega_f = omega_f / self._speed_scale / (self._wheel_diameter / 2.0)

        # 公式坐标系 → 用户坐标系（与 _cmd_callback 的变换互逆）
        # _cmd_callback: kin_vx = -user_vy,  kin_vy = user_vx
        # 逆变换:       user_vx = kin_vy,   user_vy = -kin_vx
        vx = vy_f
        vy = -vx_f
        omega = omega_f

        return vx, vy, omega

    def _publish_odom(self):
        """定时发布里程计 + TF"""
        now = self.get_clock().now()

        # cmd_vel 超时检测
        if self._last_cmd_time > 0:
            dt_cmd = (now.nanoseconds * 1e-9) - self._last_cmd_time
            if dt_cmd > self._cmd_timeout:
                # 发停止命令
                self._send_speeds([0, 0, 0, 0])

        # 计算车体速度
        chassis_speed = self._compute_chassis_speed()
        if chassis_speed is None:
            return

        vx, vy, omega = chassis_speed

        # 里程计积分
        if self._odom_last_time is not None:
            dt = (now - self._odom_last_time).nanoseconds * 1e-9
        else:
            dt = 0.02  # 首次默认 50Hz

        self._odom_last_time = now
        dt = max(0.001, min(dt, 0.1))  # 限幅 [1ms, 100ms]

        # 积分
        if abs(omega) > 0.001:
            # 圆弧运动
            radius = math.hypot(vx, vy) / omega
            dtheta = omega * dt
            self._odom_x += radius * (math.sin(self._odom_yaw + dtheta) - math.sin(self._odom_yaw))
            self._odom_y += radius * (math.cos(self._odom_yaw) - math.cos(self._odom_yaw + dtheta))
            self._odom_yaw += dtheta
        else:
            # 直线运动
            self._odom_x += vx * dt
            self._odom_y += vy * dt

        # 规范化 yaw
        self._odom_yaw = math.atan2(math.sin(self._odom_yaw), math.cos(self._odom_yaw))

        # ── 发布 Odometry ──
        q = self._yaw_to_quaternion(self._odom_yaw)

        odom = Odometry()
        odom.header.stamp = now.to_msg()
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'

        odom.pose.pose.position.x = self._odom_x
        odom.pose.pose.position.y = self._odom_y
        odom.pose.pose.orientation.w = q[0]
        odom.pose.pose.orientation.x = q[1]
        odom.pose.pose.orientation.y = q[2]
        odom.pose.pose.orientation.z = q[3]

        odom.twist.twist.linear.x = vx
        odom.twist.twist.linear.y = vy
        odom.twist.twist.angular.z = omega

        self._odom_pub.publish(odom)

        # ── 广播 TF ──
        t = TransformStamped()
        t.header.stamp = now.to_msg()
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_link'

        t.transform.translation.x = self._odom_x
        t.transform.translation.y = self._odom_y
        t.transform.translation.z = 0.0
        t.transform.rotation.w = q[0]
        t.transform.rotation.x = q[1]
        t.transform.rotation.y = q[2]
        t.transform.rotation.z = q[3]

        self._tf_broadcaster.sendTransform(t)

    # ────────────────────────────────────────────────
    # 诊断
    # ────────────────────────────────────────────────

    def _check_motor_health(self):
        """检查所有电机状态帧是否超时（1Hz）"""
        now = self.get_clock().now().nanoseconds * 1e-9
        for i, can_id in enumerate(R2_STATUS_IDS):
            last = self._last_status_time.get(can_id, 0.0)
            dt = now - last
            if dt > 0.3:  # 超过 300ms 没收状态帧
                self.get_logger().warn(
                    f'MOTOR_LOST [{R2_MOTOR_NAMES[i]}] '
                    f'ID=0x{can_id:x} last={dt:.1f}s ago')

            # 检查堵转
            with self._status_lock:
                status = self._motor_status.get(can_id)
            if status and status['stall']:
                self.get_logger().warn(
                    f'STALL [{R2_MOTOR_NAMES[i]}] '
                    f'ID=0x{can_id:x} speed={status["current_speed"]} '
                    f'pwm={status["pwm_output"]}')

    # ────────────────────────────────────────────────
    # 工具
    # ────────────────────────────────────────────────

    @staticmethod
    def _yaw_to_quaternion(yaw):
        """偏航角 → 四元数 (w, x, y, z)"""
        return (math.cos(yaw / 2.0), 0.0, 0.0, math.sin(yaw / 2.0))

    # ────────────────────────────────────────────────
    # 生命周期
    # ────────────────────────────────────────────────

    def destroy_node(self):
        self._rx_running = False
        if self._rx_thread and self._rx_thread.is_alive():
            self._rx_thread.join(timeout=1.0)
        if self._can_bus:
            self._can_bus.shutdown()
        super().destroy_node()


# ═══════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════

def main(args=None):
    rclpy.init(args=args)
    node = R2ChassisNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('用户中断')
    finally:
        node.destroy_node()
        rclpy.shutdown()


# ═══════════════════════════════════════════════════════════
# 独立测试入口（不依赖 ROS2，直接测 CAN 通信）
# ═══════════════════════════════════════════════════════════

def test_main():
    """CAN 通信测试：逐个转动每个电机，验证 ID 和方向"""
    import can
    import time
    import sys

    channel = sys.argv[1] if len(sys.argv) > 1 else 'can0'

    print(f'=== R2 CAN 通信测试 ===')
    print(f'CAN 接口: {channel}')
    print(f'\n测试流程: 每个电机正转 2s → 停 1s → 反转 2s → 停')

    bus = can.interface.Bus(channel=channel, interface='socketcan', bitrate=1000000)

    try:
        for can_id, name in zip(R2_MOTOR_IDS, R2_MOTOR_NAMES):
            print(f'\n--- {name} (0x{can_id:x}) ---')

            # 正转 speed=50
            print(f'  +50 (正转)')
            bus.send(can.Message(arbitration_id=can_id,
                                 data=bytes([0x11, 50, 0,0,0,0,0,0]),
                                 is_extended_id=False))
            time.sleep(2.0)

            # 读取状态帧
            status_data = None
            status_id = can_id + 0x200  # 状态 ID = 命令 ID + 0x200
            timeout = time.time() + 0.5
            while time.time() < timeout:
                msg = bus.recv(timeout=0.1)
                if msg and msg.arbitration_id == status_id:
                    status_data = msg.data
                    break

            if status_data:
                s = decode_status_frame(status_data)
                if s:
                    print(f'  → speed={s["current_speed"]}, '
                          f'ticks={s["accum_ticks"]}, '
                          f'pwm={s["pwm_output"]}, '
                          f'flags=0x{s["flags"]:02x}')

            # 停止
            print(f'  停止')
            bus.send(can.Message(arbitration_id=can_id,
                                 data=bytes([0x08, 0,0,0,0,0,0,0]),
                                 is_extended_id=False))
            time.sleep(1.0)

            # 反转 speed=-50
            print(f'  -50 (反转)')
            bus.send(can.Message(arbitration_id=can_id,
                                 data=bytes([0x11, 0xCE, 0,0,0,0,0,0]),  # -50 = 0xCE
                                 is_extended_id=False))
            time.sleep(2.0)

            # 停止
            bus.send(can.Message(arbitration_id=can_id,
                                 data=bytes([0x08, 0,0,0,0,0,0,0]),
                                 is_extended_id=False))
            time.sleep(0.5)

        print(f'\n=== 测试完成 ===')

    finally:
        bus.shutdown()


if __name__ == '__main__':
    import sys
    # 用 --test 启动测试模式（不带 ROS2，直接 CAN 逐一转轮子）
    if '--test' in sys.argv:
        # 提取 --test 之后的参数作为测试脚本的参数
        test_args = [a for a in sys.argv[1:] if a != '--test']
        sys.argv = [sys.argv[0]] + test_args
        test_main()
    else:
        main()
