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

- 设备路径: `/dev/ttyACM0`
- 波特率: 460800
- 数据位: 8
- 停止位: 1
- 流控: 无

## 验证

```bash
# 1. 原始数据测试
cd ~/Lin_workspace/g354_test
python3 test_g354.py
# 应看到: [TEMP] 温度  [GYRO] 陀螺仪  [ACCL] 加速度

# 2. ROS2 节点
source ~/Lin_workspace/g354_test/install/setup.bash
ros2 run g354_imu_driver imu_node
# 应看到: ✓ 串口已打开 + ✓ IMU 配置完成

# 3. 查看话题
ros2 topic echo /imu/data --once
# 应看到: orientation / angular_velocity / linear_acceleration

# 4. 检查帧率（应为 125 Hz）
ros2 topic hz /imu/data
```

## 注意事项

- JLink 插上后可能出现 `/dev/ttyACM0` 和 `/dev/ttyACM1`，取决于其他 USB 串口设备
- 若与其他设备冲突，修改 `imu_node.py` 中的 `serial_port` 参数
- 5V 供电不要接错到 JLink 的 VTref（VTref 是 3.3V 参考电压，非供电）
