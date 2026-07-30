#!/usr/bin/env python3
"""
R2 底盘映射测试 — 确定每个 CAN ID 的物理位置和方向

流程:
  1. 发送正速度到单个电机，观察哪个轮子转、往哪个方向转
  2. 重复 4 次，记录结果
  3. 输出正确的 CAN ID → 物理位置映射

用法:
  python3 map_chassis.py

操作:
  - 把车架起来（轮子离地）
  - 每步发 speed=+30 让一个电机转 2 秒
  - 观察哪个轮子转、是逆时针还是顺时针
  - 输入观察结果
"""

import can as python_can
import time
import sys

# 所有 CAN ID（按从小到大排列，无任何预设位置）
CAN_IDS = [0x123, 0x124, 0x125, 0x126]
UNIT_NAMES = {0x123: 'Unit1', 0x124: 'Unit2', 0x125: 'Unit3', 0x126: 'Unit4'}

RESULTS = {}

def main():
    channel = sys.argv[1] if len(sys.argv) > 1 else 'can0'

    bus = python_can.interface.Bus(channel=channel, interface='socketcan', bitrate=1000000)

    print("=" * 70)
    print("R2 底盘映射测试")
    print("=" * 70)
    print()
    print("【准备】把车架起来，4 个轮子离地悬空")
    print()
    input("准备好后按 Enter 开始...")
    print()

    for can_id in CAN_IDS:
        print("-" * 70)
        print(f"测试: {can_id:#x} ({UNIT_NAMES[can_id]})")
        print("-" * 70)
        print(f"发送 speed = +30 持续 3 秒...")
        print()

        # 发正速度
        bus.send(python_can.Message(
            arbitration_id=can_id,
            data=bytes([0x11, 30, 0,0,0,0,0,0]),
            is_extended_id=False))

        time.sleep(3)

        # 停止
        bus.send(python_can.Message(
            arbitration_id=can_id,
            data=bytes([0x08, 0,0,0,0,0,0,0]),
            is_extended_id=False))

        print()
        print("观察结果（请输入编号）:")
        print("  1) 轮子逆时针旋转")
        print("  2) 轮子顺时针旋转")
        print("  3) 轮子不转（或不确定）")
        direction = input("  编号: ").strip()
        print()

        print("这个轮子在哪个位置？（请输入编号）:")
        print("  1) 左前 (FL)")
        print("  2) 右前 (FR)")
        print("  3) 左后 (RL)")
        print("  4) 右后 (RR)")
        position = input("  编号: ").strip()

        dir_map = {'1': '逆时针', '2': '顺时针', '3': '不确定'}
        pos_map = {'1': 'FL', '2': 'FR', '3': 'RL', '4': 'RR'}

        RESULTS[can_id] = {
            'name': UNIT_NAMES[can_id],
            'direction': dir_map.get(direction, '未知'),
            'position': pos_map.get(position, '未知'),
        }

        print(f"  记录: {can_id:#x} ({UNIT_NAMES[can_id]}) = {RESULTS[can_id]['position']}, 正转{RESULTS[can_id]['direction']}")
        print()
        time.sleep(1)

    # 输出结果
    print("=" * 70)
    print("测试结果")
    print("=" * 70)
    print()
    print(f"{'CAN ID':>8s}  {'标签':>6s}  {'位置':>4s}  {'正转方向':>8s}")
    print("-" * 40)
    for can_id in CAN_IDS:
        r = RESULTS[can_id]
        print(f"  {can_id:#06x}  {r['name']:>5s}  {r['position']:>4s}  {r['direction']}")

    print()
    print("根据以上结果，正确的运动学映射应如下：")
    print()
    print("以下填入 chassis_node.py 的 R2_MOTOR_IDS:")

    # 按位置排序输出建议
    pos_order = ['FL', 'FR', 'RL', 'RR']
    id_map = {}
    for can_id, r in RESULTS.items():
        pos = r['position']
        if pos in pos_order:
            id_map[pos] = can_id

    if len(id_map) == 4:
        ids = [id_map[p] for p in pos_order]
        ids_hex = [f'0x{i:03X}' for i in ids]
        sids_hex = [f'0x{i+0x200:03X}' for i in ids]
        print(f"  R2_MOTOR_IDS  = [{', '.join(ids_hex)}]  # FL, FR, RL, RR")
        print(f"  R2_STATUS_IDS = [{', '.join(sids_hex)}]")
    else:
        print("  (位置数据不完整，无法生成建议)")

    print()
    print("方向修正（如需）: 如果某个轮子正转方向与预期相反")
    print("  在 config 中 motor_dir 对应位置填 -1")

    bus.shutdown()


if __name__ == '__main__':
    main()
