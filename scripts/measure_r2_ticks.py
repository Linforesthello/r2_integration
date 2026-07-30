#!/usr/bin/env python3
"""
R2 全向轮编码器 ticks/圈 测量工具

用法:
  python3 measure_r2_ticks.py              # 交互式选择电机
  python3 measure_r2_ticks.py --motor 2    # 直接测 2 号电机
  python3 measure_r2_ticks.py --speed 15   # 用更慢的速度测

流程:
  1. 选要测的电机 (1~4)
  2. 在轮子上做个标记
  3. 脚本发速度=20 让电机转
  4. 轮子转一圈回到标记时按 Ctrl+C
  5. 脚本输出 ticks/圈

CAN 协议:
  命令帧: 0x123~0x126  [0x11, speed, 0,0,0,0,0,0]
  状态帧: 0x323~0x326  [current_speed(2), accum_ticks(2), pwm(2), target, flags]
"""

import struct
import time
import argparse
import can as python_can


# R2 CAN ID 定义
#   物理布局（逆时针）: 0x123(FL) → 0x124(RL) → 0x125(RR) → 0x126(FR)
R2_MOTORS = [
    {'name': 'FL (左前)', 'cmd_id': 0x123, 'status_id': 0x323},
    {'name': 'FR (右前)', 'cmd_id': 0x126, 'status_id': 0x326},
    {'name': 'RL (左后)', 'cmd_id': 0x124, 'status_id': 0x324},
    {'name': 'RR (右后)', 'cmd_id': 0x125, 'status_id': 0x325},
]

CMD_SET_SPEED = 0x11
CMD_STOP = 0x08


def build_speed_cmd(speed: int) -> bytes:
    """构建速度命令帧: [0x11, speed, 0,0,0,0,0,0]"""
    s = max(-100, min(100, speed)) & 0xFF
    return bytes([CMD_SET_SPEED, s, 0, 0, 0, 0, 0, 0])


def build_stop_cmd() -> bytes:
    """构建停止命令帧: [0x08, 0,0,0,0,0,0,0]"""
    return bytes([CMD_STOP, 0, 0, 0, 0, 0, 0, 0])


def decode_status(data: bytes) -> dict:
    """解析状态帧 → speed, ticks, pwm, flags"""
    speed = struct.unpack_from('<h', data, 0)[0]
    ticks = struct.unpack_from('<H', data, 2)[0]
    pwm   = struct.unpack_from('<h', data, 4)[0]
    target = struct.unpack_from('<b', data, 6)[0]
    flags = data[7]
    return {
        'speed': speed,
        'ticks': ticks,
        'pwm': pwm,
        'target': target,
        'stall': bool(flags & 0x01),
        'saturated': bool(flags & 0x02),
    }


def measure_motor(bus, motor_idx: int, test_speed: int = 20) -> int:
    """
    测量单个电机的 ticks/圈

    流程:
      发速度命令 → 监听状态帧 → 用户按 Ctrl+C → 算 ticks 变化

    返回: ticks_per_rev
    """
    motor = R2_MOTORS[motor_idx]
    cmd_id = motor['cmd_id']
    status_id = motor['status_id']
    name = motor['name']

    print(f"\n{'=' * 60}")
    print(f"电机 {motor_idx+1}: {name}")
    print(f"  命令 ID: 0x{cmd_id:03X}")
    print(f"  状态 ID: 0x{status_id:03X}")
    print(f"  测试速度: {test_speed}")
    print(f"{'=' * 60}")

    # Step 1: 静止确认
    print("\n[1/4]  等待状态帧确认通信...")
    init_ticks = None
    t0 = time.time()
    while time.time() - t0 < 3.0:
        msg = bus.recv(timeout=0.3)
        if msg and msg.arbitration_id == status_id:
            s = decode_status(msg.data)
            if init_ticks is None:
                init_ticks = s['ticks']
                print(f"  初始 ticks = {init_ticks}  speed={s['speed']}  ✅ 通信正常")
                break

    if init_ticks is None:
        print(f"  ❌ 3 秒内没收到状态帧！检查 CAN 连接")
        return 0

    # Step 2: 提示做标记
    print(f"\n[2/4]  在 {name} 轮子上做个可见标记")
    print(f"        发速度 = {test_speed} 让它转")
    input(f"        按 Enter 开始转动... 然后观察轮子转一圈时按 Ctrl+C\n")

    # Step 3: 发速度命令
    bus.send(python_can.Message(
        arbitration_id=cmd_id, data=build_speed_cmd(test_speed),
        is_extended_id=False))

    # Step 4: 实时监听 ticks
    print(f"\n[3/4]  正在转动... 实时数据:")
    print(f"{'─' * 60}")
    print(f"  {'时间':>8s}  {'ticks':>6s}  {'差值':>6s}  {'speed':>5s}  {'pwm':>4s}")
    print(f"{'─' * 60}")

    last_ticks = init_ticks
    samples = []
    last_print = time.time()

    try:
        while True:
            msg = bus.recv(timeout=0.1)
            if msg is None:
                continue
            if msg.arbitration_id != status_id:
                continue

            s = decode_status(msg.data)
            now = time.time()

            diff = s['ticks'] - last_ticks
            if diff > 32767:  diff -= 65536   # uint16 回绕
            if diff < -32767: diff += 65536

            samples.append((now, s['ticks']))

            if now - last_print >= 0.2:  # 5Hz 刷新
                t_rel = now - t0
                print(f"  {t_rel:>6.1f}s  {s['ticks']:>6d}  {diff:+6d}  {s['speed']:>+4d}  {s['pwm']:>4d}")
                last_print = now

            last_ticks = s['ticks']

    except KeyboardInterrupt:
        pass

    # 停止电机
    bus.send(python_can.Message(
        arbitration_id=cmd_id, data=build_stop_cmd(),
        is_extended_id=False))
    time.sleep(0.2)

    print(f"{'─' * 60}")

    # Step 5: 计算结果
    if len(samples) < 2:
        print("  ❌ 数据点不足")
        return 0

    start_ticks = samples[0][1]
    end_ticks   = samples[-1][1]

    total = end_ticks - start_ticks
    if total > 32767:  total -= 65536
    if total < -32767: total += 65536
    total = abs(total)

    elapsed = samples[-1][0] - samples[0][0]

    print(f"\n[4/4]  结果")
    print(f"{'=' * 60}")
    print(f"  电机:      {name} (0x{cmd_id:03X})")
    print(f"  测试时长:  {elapsed:.1f} 秒")
    print(f"  初值:      {start_ticks}")
    print(f"  末值:      {end_ticks}")
    print(f"  变化:      {total} ticks")
    print(f"  平均速率:  {total/elapsed:.0f} ticks/秒")

    print(f"\n  ⬆  如果轮子正好转了一圈:")
    print(f"      每圈 = {total} ticks")
    print(f"      配到 config/r2_params.yaml:")
    print(f"        ticks_per_rev: {total}")

    return total


def show_all_status(bus):
    """显示所有电机当前状态"""
    print(f"\n各电机实时状态:")
    print(f"{'─' * 60}")
    print(f"  {'电机':>10s}  {'CMD_ID':>7s}  {'speed':>5s}  {'ticks':>5s}  {'pwm':>4s}")
    print(f"{'─' * 60}")

    t0 = time.time()
    seen = {}
    while time.time() - t0 < 2.0:
        msg = bus.recv(timeout=0.3)
        if msg is None:
            continue
        for i, m in enumerate(R2_MOTORS):
            if msg.arbitration_id == m['status_id']:
                s = decode_status(msg.data)
                if i not in seen:
                    seen[i] = s
                    print(f"  {m['name']:>10s}  0x{m['cmd_id']:03X}  {s['speed']:>+4d}  {s['ticks']:>5d}  {s['pwm']:>4d}")

    if len(seen) < 4:
        missing = [m['name'] for i, m in enumerate(R2_MOTORS) if i not in seen]
        print(f"  未收到: {', '.join(missing)}")
    else:
        print(f"  ✅ 4 个电机全部在线")


def main():
    parser = argparse.ArgumentParser(description='R2 编码器 ticks/圈 测量')
    parser.add_argument('--motor', type=int, default=0,
                        help='电机编号 1~4 (默认: 交互式选择)')
    parser.add_argument('--speed', type=int, default=20,
                        help='测试速度 (默认: 20, 建议 10~30)')
    parser.add_argument('--channel', default='can0',
                        help='CAN 接口 (默认: can0)')
    parser.add_argument('--status', action='store_true',
                        help='只查看状态，不测量')
    args = parser.parse_args()

    # 连接 CAN
    print(f"连接 CAN: {args.channel} @ 1Mbps ...")
    bus = python_can.interface.Bus(
        channel=args.channel, interface='socketcan', bitrate=1000000)
    print("✅ CAN 已连接\n")

    try:
        if args.status:
            show_all_status(bus)
            return

        # 选择电机
        motor_idx = args.motor - 1  # 转 0-based
        if motor_idx < 0 or motor_idx > 3:
            # 交互式选择
            print("选择要测量的电机:")
            for i, m in enumerate(R2_MOTORS):
                print(f"  {i+1}. {m['name']} (0x{m['cmd_id']:03X} / 0x{m['status_id']:03X})")
            print()
            while True:
                try:
                    choice = int(input(f"输入编号 (1~4): ").strip())
                    if 1 <= choice <= 4:
                        motor_idx = choice - 1
                        break
                except (ValueError, IndexError):
                    pass
                print("无效输入，请重新输入")

        # 测量
        result = measure_motor(bus, motor_idx, test_speed=args.speed)

        if result > 0:
            print(f"\n✅ 测量完成: 电机 {motor_idx+1} 每圈 = {result} ticks")

    except KeyboardInterrupt:
        print("\n\n用户中断")
    finally:
        # 确保所有电机停止
        for m in R2_MOTORS:
            try:
                bus.send(python_can.Message(
                    arbitration_id=m['cmd_id'], data=build_stop_cmd(),
                    is_extended_id=False))
            except:
                pass
        bus.shutdown()
        print("CAN 已关闭")


if __name__ == '__main__':
    main()
