#!/usr/bin/env python3
"""
R2 方向标定 — 测试不同轮速组合对应的车体运动方向

流程:
  1. 把车放地上（轮子着地）
  2. 逐一测试预定义的轮速组合
  3. 观察车体运动方向并输入
  4. 输出正确的运动学变换系数

用法:
  python3 calibrate_direction.py
"""

import can as python_can
import time
import sys

# ── 用户已确定的 CAN ID → 位置映射 ──
CAN_FL = 0x123  # Unit1 = 左前
CAN_RL = 0x124  # Unit2 = 左后
CAN_RR = 0x125  # Unit3 = 右后
CAN_FR = 0x126  # Unit4 = 右前

ALL_IDS = [CAN_FL, CAN_FR, CAN_RL, CAN_RR]  # FL, FR, RL, RR

# ── 测试模式 (FL, FR, RL, RR) 每个轮的速度 ──
TEST_PATTERNS = [
    {
        'name': 'P1: 前进理论',
        'speeds': [+20, +20, -20, -20],
        'desc': 'FL=+20 FR=+20 RL=-20 RR=-20',
    },
    {
        'name': 'P2: 左移理论',
        'speeds': [+20, -20, +20, -20],
        'desc': 'FL=+20 FR=-20 RL=+20 RR=-20',
    },
    {
        'name': 'P3: 右移理论',
        'speeds': [-20, +20, -20, +20],
        'desc': 'FL=-20 FR=+20 RL=-20 RR=+20',
    },
    {
        'name': 'P4: 后退理论',
        'speeds': [-20, -20, +20, +20],
        'desc': 'FL=-20 FR=-20 RL=+20 RR=+20',
    },
    {
        'name': 'P5: 自转理论',
        'speeds': [-20, -20, -20, -20],
        'desc': '全部 -20 (4轮同向)',
    },
    {
        'name': 'P6: 全正向',
        'speeds': [+20, +20, +20, +20],
        'desc': '全部 +20 (4轮同向)',
    },
    {
        'name': 'P7: 交叉',
        'speeds': [+20, -20, -20, +20],
        'desc': 'FL=+20 FR=-20 RL=-20 RR=+20',
    },
    {
        'name': 'P8: 交叉反',
        'speeds': [-20, +20, +20, -20],
        'desc': 'FL=-20 FR=+20 RL=+20 RR=-20',
    },
]

DIR_OPTIONS = ['前进', '后退', '左移', '右移', '左旋', '右旋', '不动', '其他']


def send_speeds(bus, speeds):
    for can_id, speed in zip(ALL_IDS, speeds):
        bus.send(python_can.Message(
            arbitration_id=can_id,
            data=bytes([0x11, max(-100, min(100, speed)) & 0xFF, 0, 0, 0, 0, 0, 0]),
            is_extended_id=False))


def stop_all(bus):
    for can_id in ALL_IDS:
        bus.send(python_can.Message(
            arbitration_id=can_id,
            data=bytes([0x08, 0, 0, 0, 0, 0, 0, 0]),
            is_extended_id=False))


def main():
    channel = sys.argv[1] if len(sys.argv) > 1 else 'can0'
    bus = python_can.interface.Bus(channel=channel, interface='socketcan', bitrate=1000000)

    print("=" * 70)
    print("R2 方向标定 — 测试轮速组合与车体运动的关系")
    print("=" * 70)
    print()
    print(f"映射确认: FL=0x{CAN_FL:03X}  FR=0x{CAN_FR:03X}  RL=0x{CAN_RL:03X}  RR=0x{CAN_RR:03X}")
    print()
    print("【准备】车放地上，周围有足够空间")
    input("准备好后按 Enter 开始...")
    print()

    for pattern in TEST_PATTERNS:
        print("-" * 70)
        print(f"测试: {pattern['name']}")
        print(f"  {pattern['desc']}")
        print("-" * 70)
        print()
        input("  按 Enter 发送（车会动 1.5 秒）...")

        send_speeds(bus, pattern['speeds'])
        time.sleep(1.5)
        stop_all(bus)

        print()
        print("  车体运动方向? 输入编号:")
        for i, opt in enumerate(DIR_OPTIONS):
            print(f"    {i+1}) {opt}")
        choice = input("  编号: ").strip()

        try:
            idx = int(choice) - 1
            direction = DIR_OPTIONS[idx] if 0 <= idx < len(DIR_OPTIONS) else '未知'
        except:
            direction = choice

        pattern['result'] = direction
        print(f"  记录: {pattern['name']} → {direction}")
        print()
        time.sleep(1)

    # 分析结果
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)
    print()

    # 找哪个模式产生了"前进"
    forward_pattern = None
    for p in TEST_PATTERNS:
        r = p.get('result', '')
        if '前进' in r:
            forward_pattern = p
            print(f"✅ 发现前进模式: {p['name']}")
            print(f"   轮速: {p['desc']}")
            print()

    if forward_pattern:
        print("该模式的轮速组合就是正确的运动学输出。")
        print("需要在 chassis_node.py 的 _cmd_callback 中")
        print("调整 vx/vy 变换使得理论前进→实际前进。")
    else:
        print("❌ 没有找到纯粹的前进模式。可能需要更复杂的变换。")

    stop_all(bus)
    bus.shutdown()


if __name__ == '__main__':
    main()
