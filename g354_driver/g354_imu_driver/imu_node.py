#!/usr/bin/env python3
"""
Epson M-G354 IMU ROS 2 Driver Node

Matches reference implementation:
  https://github.com/MTFTau-5/G354_Attitude-algorithm

Key differences from earlier versions:
  - 38-byte frame format (0xF007/0x7000 burst config, verified by readback)
  - Polling mode: send 0x80 trigger, read exactly 38 bytes back
  - Target 100 Hz loop rate (matches reference)
  - MAHONY_KI = 0.005 (online gyro bias tracking)
  - dt clamped with fallback to TARGET_DT

Publishes:
  /imu/data (sensor_msgs/Imu)
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
import serial
import time
import struct
import math

DEG2RAD = math.pi / 180.0
RAD2DEG = 180.0 / math.pi
G_TO_MS2 = 9.80665

# Reference scale factors (32-bit burst format)
SF_GYRO = 0.016         # (deg/s)/LSB, 16-bit scale
SF_ACC  = 0.2           # mG/LSB, 16-bit scale
SCALE_DIV = 65536.0     # 32-bit correction

FRAME_LEN = 38

# Mahony gains (matching reference main.cpp)
MAHONY_KP = 1.0
MAHONY_KI = 0.005

# Target rate (matching reference: 100 Hz)
TARGET_HZ = 100.0
TARGET_DT = 1.0 / TARGET_HZ
DT_MIN = 0.001
DT_MAX = 0.050

CALIB_SAMPLES = 250
ACC_INIT_SAMPLES = 50


# ------------------------------------------------------------------
# Mahony filter
# ------------------------------------------------------------------

def mahony_update(q, gx_dps, gy_dps, gz_dps,
                  ax_mg, ay_mg, az_mg, dt,
                  kp=MAHONY_KP, ki=MAHONY_KI, integral_error=None):
    """
    Mahony filter update.
    Input: gyro in deg/s, accel in mg, dt in seconds.
    """
    qw, qx, qy, qz = q

    # deg/s to rad/s
    gx_rad = gx_dps * DEG2RAD
    gy_rad = gy_dps * DEG2RAD
    gz_rad = gz_dps * DEG2RAD

    # mg to G
    ax_g = ax_mg / 1000.0
    ay_g = ay_mg / 1000.0
    az_g = az_mg / 1000.0

    acc_norm = math.sqrt(ax_g*ax_g + ay_g*ay_g + az_g*az_g)

    ex = ey = ez = 0.0
    if 0.85 < acc_norm < 1.15 and acc_norm > 1e-12:
        inv = 1.0 / acc_norm
        # Real gravity direction = -specific_force
        ax_n = -ax_g * inv
        ay_n = -ay_g * inv
        az_n = -az_g * inv

        # Predicted gravity in body frame
        vx = 2.0 * (qx * qz - qw * qy)
        vy = 2.0 * (qw * qx + qy * qz)
        vz = qw*qw - qx*qx - qy*qy + qz*qz

        # Cross product error
        ex = ay_n * vz - az_n * vy
        ey = az_n * vx - ax_n * vz
        ez = ax_n * vy - ay_n * vx

        if ki > 0.0 and integral_error is not None:
            integral_error[0] += ki * ex * dt
            integral_error[1] += ki * ey * dt
            integral_error[2] += ki * ez * dt

    bias = integral_error if integral_error is not None else [0.0, 0.0, 0.0]

    wx = gx_rad + kp * ex + bias[0]
    wy = gy_rad + kp * ey + bias[1]
    wz = gz_rad + kp * ez + bias[2]

    dqw = -0.5 * (qx * wx + qy * wy + qz * wz)
    dqx =  0.5 * (qw * wx + qy * wz - qz * wy)
    dqy =  0.5 * (qw * wy + qz * wx - qx * wz)
    dqz =  0.5 * (qw * wz + qx * wy - qy * wx)

    qw += dqw * dt
    qx += dqx * dt
    qy += dqy * dt
    qz += dqz * dt

    norm = math.sqrt(qw*qw + qx*qx + qy*qy + qz*qz)
    if norm < 1e-18:
        return (1.0, 0.0, 0.0, 0.0)
    inv = 1.0 / norm
    return (qw*inv, qx*inv, qy*inv, qz*inv)


def init_from_accelerometer(ax_mg, ay_mg, az_mg, yaw_deg=0.0):
    """Initialize quaternion from accelerometer (input in mg)."""
    ax_g = ax_mg / 1000.0
    ay_g = ay_mg / 1000.0
    az_g = az_mg / 1000.0

    norm = math.sqrt(ax_g*ax_g + ay_g*ay_g + az_g*az_g)
    if norm < 1e-12:
        return (1.0, 0.0, 0.0, 0.0)

    gx = -ax_g / norm
    gy = -ay_g / norm
    gz = -az_g / norm

    roll = math.atan2(gy, gz)
    pitch = math.atan2(-gx, math.sqrt(gy*gy + gz*gz))
    yaw = yaw_deg * DEG2RAD

    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)

    q = (cy*cp*cr + sy*sp*sr,
         cy*cp*sr - sy*sp*cr,
         sy*cp*sr + cy*sp*cr,
         sy*cp*cr - cy*sp*sr)

    norm = math.sqrt(q[0]**2 + q[1]**2 + q[2]**2 + q[3]**2)
    if norm < 1e-18:
        return (1.0, 0.0, 0.0, 0.0)
    inv = 1.0 / norm
    return (q[0]*inv, q[1]*inv, q[2]*inv, q[3]*inv)


# ------------------------------------------------------------------
# G354 register-level helpers
# ------------------------------------------------------------------

def g354_write_reg(ser, addr, value):
    """Write one byte to a G354 register."""
    ser.write(bytes([0x80 | (addr & 0x7F), value & 0xFF, 0x0D]))
    ser.flush()
    time.sleep(0.002)


def g354_write_reg16(ser, addr_lo, value):
    """Write 16-bit value to a G354 register pair (LO, LO+1)."""
    g354_write_reg(ser, addr_lo, value & 0xFF)
    g354_write_reg(ser, addr_lo + 1, (value >> 8) & 0xFF)


def g354_read_reg16(ser, addr_even):
    """Read 16-bit value from a G354 register pair."""
    ser.reset_input_buffer()
    ser.write(bytes([addr_even & 0x7E, 0x00, 0x0D]))
    ser.flush()
    resp = ser.read(4)
    if len(resp) != 4 or resp[0] != (addr_even & 0x7E) or resp[3] != 0x0D:
        raise RuntimeError(f"G354 reg read failed: addr=0x{addr_even:02X}")
    return (resp[1] << 8) | resp[2]


def configure_g354(ser, logger=None):
    """Configure G354 for 38-byte burst mode (matching reference).
    Returns True if burst registers verified, False if skipped/failed.
    """
    def log(msg):
        if logger:
            logger.info(msg)

    def warn(msg):
        if logger:
            logger.warning(msg)

    # Stop sampling, Window 0
    g354_write_reg(ser, 0x7E, 0x00)
    g354_write_reg(ser, 0x03, 0x02)
    time.sleep(0.2)
    ser.reset_input_buffer()

    # Window 1: configure burst
    g354_write_reg(ser, 0x7E, 0x01)
    g354_write_reg(ser, 0x08, 0x00)

    g354_write_reg16(ser, 0x0C, 0xF007)
    g354_write_reg16(ser, 0x0E, 0x7000)

    # Readback verification
    verified = False
    try:
        ctrl1 = g354_read_reg16(ser, 0x0C)
        ctrl2 = g354_read_reg16(ser, 0x0E)
        if ctrl1 == 0xF007 and ctrl2 == 0x7000:
            log('Burst registers verified (CTRL1=0xF007, CTRL2=0x7000)')
            verified = True
        else:
            warn(f'Burst mismatch: CTRL1=0x{ctrl1:04X} CTRL2=0x{ctrl2:04X}')
    except Exception as e:
        warn(f'Burst readback skipped: {e}')

    # Window 0, start sampling
    g354_write_reg(ser, 0x7E, 0x00)
    g354_write_reg(ser, 0x03, 0x01)

    time.sleep(0.1)
    ser.reset_input_buffer()
    return verified


def read_g354_frame(ser):
    """
    Poll one frame from G354 (matching reference).
    Send trigger 0x80 0x00 0x0D, read exactly 38 bytes.
    """
    try:
        ser.reset_input_buffer()
        ser.write(bytes([0x80, 0x00, 0x0D]))
        ser.flush()

        frame = bytearray()
        deadline = time.monotonic() + 0.1
        while len(frame) < FRAME_LEN and time.monotonic() < deadline:
            chunk = ser.read(FRAME_LEN - len(frame))
            if chunk:
                frame.extend(chunk)
        if len(frame) != FRAME_LEN:
            return None
        if frame[0] != 0x80 or frame[FRAME_LEN-1] != 0x0D:
            return None
        return bytes(frame)
    except serial.SerialException:
        return None


def parse_g354_frame(frame):
    """
    Parse 38-byte G354 frame.
    Returns (gx_dps, gy_dps, gz_dps, ax_mg, ay_mg, az_mg).
    """
    def i32(start):
        return struct.unpack('>i', frame[start:start+4])[0]

    gx = i32(7) * (SF_GYRO / SCALE_DIV)   # deg/s
    gy = i32(11) * (SF_GYRO / SCALE_DIV)
    gz = i32(15) * (SF_GYRO / SCALE_DIV)
    ax = i32(19) * (SF_ACC / SCALE_DIV)    # mG
    ay = i32(23) * (SF_ACC / SCALE_DIV)
    az = i32(27) * (SF_ACC / SCALE_DIV)

    return (gx, gy, gz, ax, ay, az)


# ------------------------------------------------------------------
# ROS2 Node
# ------------------------------------------------------------------

class G354IMUNode(Node):
    def __init__(self):
        super().__init__('g354_imu_node')

        self.declare_parameter('serial_port', '/dev/ttyACM0')
        self.declare_parameter('baudrate', 460800)
        self.declare_parameter('frame_id', 'imu_link')

        port = self.get_parameter('serial_port').value
        baud = self.get_parameter('baudrate').value
        self.frame_id_ = self.get_parameter('frame_id').value

        self.imu_pub_ = self.create_publisher(Imu, '/imu/data', 10)

        # Serial
        try:
            self.ser_ = serial.Serial(
                port, baud, timeout=0.5, rtscts=False, dsrdtr=False)
            self.get_logger().info(f'Serial {port} ({baud} baud)')
        except Exception as e:
            self.get_logger().fatal(f'Cannot open {port}: {e}')
            raise

        # Configure G354 (38-byte burst mode)
        verified = configure_g354(self.ser_, self.get_logger())
        self.get_logger().info(
            f'G354 38-byte burst mode configured'
            f'{" and verified" if verified else ""}')

        # Sensor specific force bias for linear acceleration
        self.acc_bias_mg_ = (0.0, 0.0)

        # Mahony state
        self.q_ = (1.0, 0.0, 0.0, 0.0)
        self.integral_error_ = [0.0, 0.0, 0.0]
        self.last_t_ = None

        # Gyro bias (static calibration + online ZUPT tracking)
        self.gyro_bias_ = [0.0, 0.0, 0.0]
        self.calib_done_ = False
        self.calib_samples_ = []

        # Stationary detection for online bias tracking (ZUPT)
        # When IMU is stationary, the gyro should read 0 → any residual IS bias
        # We slowly track it and subtract it from future readings
        self.stationary_count_ = 0
        self.STATIONARY_CONFIRM = 10    # frames to confirm stationary
        self.STATIONARY_GYRO_DPS = 1.0  # deg/s max gyro norm for stationary
        self.STATIONARY_ACC_ERR = 0.05  # |acc_norm - 1g| max for stationary
        self.ZUPT_ALPHA = 0.01          # bias tracking rate (slow)

        # Loop control: target 100 Hz
        self.timer_ = self.create_timer(0.01, self.timer_callback)

    # ------------------------------------------------------------------
    def _finish_calibration(self):
        """Compute gyro bias and init orientation from acc."""
        n = len(self.calib_samples_)
        sx = sy = sz = 0.0
        ax_sum = ay_sum = az_sum = 0.0
        for gx, gy, gz, ax, ay, az in self.calib_samples_:
            sx += gx; sy += gy; sz += gz
            ax_sum += ax; ay_sum += ay; az_sum += az

        self.gyro_bias_ = [sx/n, sy/n, sz/n]
        self.get_logger().info(
            f'Gyro bias (dps): X={self.gyro_bias_[0]:.4f} '
            f'Y={self.gyro_bias_[1]:.4f} Z={self.gyro_bias_[2]:.4f}')

        # Init attitude from accel (last ACC_INIT_SAMPLES frames)
        acc_init = self.calib_samples_[-ACC_INIT_SAMPLES:]
        ax_m = sum(a[3] for a in acc_init) / len(acc_init)
        ay_m = sum(a[4] for a in acc_init) / len(acc_init)
        az_m = sum(a[5] for a in acc_init) / len(acc_init)

        self.q_ = init_from_accelerometer(ax_m, ay_m, az_m)
        self.get_logger().info(
            f'Init quat: qw={self.q_[0]:.4f} qx={self.q_[1]:.4f} '
            f'qy={self.q_[2]:.4f} qz={self.q_[3]:.4f}')

        self.calib_done_ = True
        self.calib_samples_ = None
        self.last_t_ = None
        self.integral_error_ = [0.0, 0.0, 0.0]

    # ------------------------------------------------------------------
    def timer_callback(self):
        """Poll one frame, process, publish. Target 100 Hz."""
        frame = read_g354_frame(self.ser_)
        if frame is None:
            return

        gx, gy, gz, ax, ay, az = parse_g354_frame(frame)

        # dt from loop timing (clamped)
        now = time.monotonic()
        if self.last_t_ is None:
            dt = TARGET_DT
        else:
            dt = now - self.last_t_
            if dt < DT_MIN or dt > DT_MAX:
                dt = TARGET_DT
        self.last_t_ = now

        # Calibration state machine
        if not self.calib_done_:
            # Store in deg/s and mg (matching reference units)
            self.calib_samples_.append((gx, gy, gz, ax, ay, az))
            if len(self.calib_samples_) >= CALIB_SAMPLES:
                self._finish_calibration()
            elif len(self.calib_samples_) % 50 == 0:
                self.get_logger().info(
                    f'Calib {len(self.calib_samples_)}/{CALIB_SAMPLES}')
            return

        # Running: apply gyro bias
        gx_cal = gx - self.gyro_bias_[0]
        gy_cal = gy - self.gyro_bias_[1]
        gz_cal = gz - self.gyro_bias_[2]

        # Mahony update (Ki=0.005 for online bias tracking)
        self.q_ = mahony_update(
            self.q_, gx_cal, gy_cal, gz_cal,
            ax, ay, az, dt,
            integral_error=self.integral_error_)

        # ---- Stationary detection + ZUPT bias tracking ----
        # When IMU is confirmed stationary, any non-zero gyro IS residual bias.
        # Slowly blend it into gyro_bias_ to cancel Z-axis drift during static periods.
        acc_norm_g = math.sqrt(ax*ax + ay*ay + az*az) / 1000.0
        gyro_norm_dps = math.sqrt(gx_cal*gx_cal + gy_cal*gy_cal + gz_cal*gz_cal)

        is_stationary = (abs(acc_norm_g - 1.0) < self.STATIONARY_ACC_ERR and
                         gyro_norm_dps < self.STATIONARY_GYRO_DPS)

        if is_stationary:
            self.stationary_count_ += 1
            if self.stationary_count_ >= self.STATIONARY_CONFIRM:
                # Blend residual gyro into bias (slow, alpha=0.01)
                self.gyro_bias_[0] += self.ZUPT_ALPHA * gx_cal
                self.gyro_bias_[1] += self.ZUPT_ALPHA * gy_cal
                self.gyro_bias_[2] += self.ZUPT_ALPHA * gz_cal
        else:
            self.stationary_count_ = 0

        # Publish
        msg = Imu()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id_

        msg.orientation.w = self.q_[0]
        msg.orientation.x = self.q_[1]
        msg.orientation.y = self.q_[2]
        msg.orientation.z = self.q_[3]

        # Covariance (confidence from ZUPT's acc_norm_g)
        confidence = max(0.0, 1.0 - abs(acc_norm_g - 1.0) / 0.15)
        base = 0.001 + (1.0 - confidence) * 0.05
        msg.orientation_covariance = [base] * 9
        msg.orientation_covariance[8] = base * 10

        # Angular velocity in rad/s (with bias removed)
        msg.angular_velocity.x = gx_cal * DEG2RAD
        msg.angular_velocity.y = gy_cal * DEG2RAD
        msg.angular_velocity.z = gz_cal * DEG2RAD
        msg.angular_velocity_covariance = [0.0001] * 9

        # Linear acceleration (mg to m/s²)
        msg.linear_acceleration.x = ax / 1000.0 * G_TO_MS2
        msg.linear_acceleration.y = ay / 1000.0 * G_TO_MS2
        msg.linear_acceleration.z = az / 1000.0 * G_TO_MS2
        msg.linear_acceleration_covariance = [0.0001] * 9

        self.imu_pub_.publish(msg)

    # ------------------------------------------------------------------
    def destroy_node(self):
        try:
            # Stop sampling
            self.ser_.write(bytes([0x83, 0x02, 0x0D]))
            self.ser_.close()
            self.get_logger().info('Serial closed')
        except Exception:
            pass
        super().destroy_node()


# ------------------------------------------------------------------
def main(args=None):
    rclpy.init(args=args)
    node = G354IMUNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Interrupted')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
