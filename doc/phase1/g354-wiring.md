# G354 IMU → JLink OB Mini 接线记录

> 2026-07-30 实测验证通过

## 接线

| G354 IMU 端 | JLink OB Mini 端 | 备注 |
|:------------|:-----------------|:------|
| VCC (5V) | — | JLink 不供电，**需独立 5V 供电** |
| GND | GND | 共地 |
| TX | VCP RX（JLink 接收） | 具体针脚见下方 JLink pinout |
| RX | VCP TX（JLink 发送） | 具体针脚见下方 JLink pinout |

## JLink OB Mini 10-pin Pinout（VCP 相关）

```
 2   4   6   8  10
┌─┬─┬─┬─┬─┬─┬─┬─┬─┬─┐
└─┴─┴─┴─┴─┴─┴─┴─┴─┴─┘
 1   3   5   7   9

 1  VTREF     (参考电压)
 2  SWDIO     (SWD 数据)
 3  GND
 4  SWCLK     (SWD 时钟)
 5  GND
 6  SWO       ← VCP TX (JLink 发 → G354 RX)
 7  NC
 8  TDI       ← VCP RX (JLink 收 ← G354 TX)  [视具体版本而定]
 9  GND       (检测)
10  RESET
```

> **注意**：VCP RX 引脚因 JLink 固件版本可能不同。实测用示波器/万用表确认哪个引脚有 3.3V 跳变信号最可靠。

## 串口参数

- 设备路径: `/dev/ttyACM1`（N97 上固定；CANable2 占 ttyACM0，launch 默认即 ttyACM1）
- 波特率: 460800
- 数据位: 8
- 停止位: 1
- 流控: 无

## 验证

```bash
# 1. 原始数据测试
cd ~/Lin_workspace/r2_integration/g354_driver
python3 scripts/test_g354.py
# 应看到: [TEMP] 温度  [GYRO] 陀螺仪  [ACCL] 加速度

# 2. ROS2 节点
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch g354_imu_driver g354_rviz.launch.py rviz:=false serial_port:=/dev/ttyACM1
# 应看到: ✓ 串口已打开 + ✓ IMU 配置完成

# 3. 查看话题
ros2 topic echo /imu/data --once
# 应看到: orientation / angular_velocity / linear_acceleration

# 4. 检查帧率（应为 125 Hz）
ros2 topic hz /imu/data
```

## 注意事项

- 设备对应关系固定：`/dev/ttyACM0` = CANable2（CAN 总线）、`/dev/ttyACM1` = G354（JLink OB Mini）
- 若设备路径变化，用 launch 参数覆盖：`ros2 launch g354_imu_driver g354_rviz.launch.py serial_port:=/dev/ttyACM0 rviz:=false`（`imu_node.py` 代码默认值仍是 ttyACM0，无需改代码）
- 5V 供电不要接错到 JLink 的 VTref（VTref 是 3.3V 参考电压，非供电）
