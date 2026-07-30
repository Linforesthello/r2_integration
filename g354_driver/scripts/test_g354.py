import serial
import time
import struct

SERIAL_PORT = '/dev/ttyACM0'
BAUDRATE = 460800  # 默认波特率

def parse_and_display(packet):
    if len(packet) < 36:
        return
    try:
        # 提取高16位数据进行快速结算 (大端模式 >h)
        temp_raw = struct.unpack('>h', packet[3:5])[0]    # TEMP_HIGH
        gx_raw   = struct.unpack('>h', packet[7:9])[0]    # X_GYRO_HIGH
        gy_raw   = struct.unpack('>h', packet[11:13])[0]  # Y_GYRO_HIGH
        gz_raw   = struct.unpack('>h', packet[15:17])[0]  # Z_GYRO_HIGH
        ax_raw   = struct.unpack('>h', packet[19:21])[0]  # X_ACCL_HIGH
        ay_raw   = struct.unpack('>h', packet[23:25])[0]  # Y_ACCL_HIGH
        az_raw   = struct.unpack('>h', packet[27:29])[0]  # Z_ACCL_HIGH

        # 执行标度因数换算
        temperature = 25.0 + (temp_raw - 2634) * (-0.0037918)
        gyro_x = gx_raw * 0.016
        gyro_y = gy_raw * 0.016
        gyro_z = gz_raw * 0.016
        acc_x  = ax_raw * 0.0002
        acc_y  = ay_raw * 0.0002
        acc_z  = az_raw * 0.0002

        print(f"\r[TEMP]: {temperature:6.2f} °C | "
              f"[GYRO]: X:{gyro_x:7.2f}, Y:{gyro_y:7.2f}, Z:{gyro_z:7.2f} °/s | "
              f"[ACCL]: X:{acc_x:6.3f}, Y:{acc_y:6.3f}, Z:{acc_z:6.3f} G", end='', flush=True)
    except Exception as e:
        pass

try:
    # 显式配置串口，防止虚拟机环境下流控引发死锁
    ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1, rtscts=False, dsrdtr=False)
    print(f"成功打开串口 {SERIAL_PORT}，开始发送唤醒序列...")

    # Epson M-G354 官方标准 UART 自动模式配置序列
    instructions = [
        "FE 01 0D",  # 切换到 Window 1
        "85 04 0D",  # 设置输出速率（04 为 125 Sps）
        "88 01 0D",  # 开启 UART 自动输出模式 (AUTO Mode)
        "8C 06 0D",  # 包含 GPIO, COUNT
        "8D F0 0D",  # 包含 FLAG, TEMP, GYRO, ACCL
        "8F 70 0D",  # 设置为 32-bit 分辨率输出
        "FE 00 0D",  # 切换回 Window 0
        "83 01 0D",  # 进入 Sampling 模式开始采样
    ]

    for cmd in instructions:
        ser.write(bytes.fromhex(cmd))
        time.sleep(0.06)

    print("\n--- 配置指令发送完毕 ---")
    print("正在等待数据... 如果解析失败，下方将直接显示原始十六进制流：\n")
    
    buffer = bytearray()
    raw_debug_counter = 0

    while True:
        try:
            if ser.in_waiting > 0:
                rx_data = ser.read(ser.in_waiting)
                if not rx_data:
                    continue  # CDC ACM 空读保护
                buffer.extend(rx_data)
        except serial.SerialException:
            continue  # 设备暂时不可读，重试

        # 调试逻辑：如果无法按帧对齐，前10次直接打印收到的原始数据片段
        if raw_debug_counter < 10:
            if len(buffer) > 0:
                print(f"[原始数据片段]: {buffer.hex().upper()[:72]}")
                raw_debug_counter += 1

        # 帧解析逻辑
        while len(buffer) >= 36:
            # 寻找标准包头 0x80 和包尾 0x0D
            if buffer[0] == 0x80 and buffer[35] == 0x0D:
                packet = buffer[:36]
                parse_and_display(packet)
                del buffer[:36]
            else:
                # 如果错位，剔除第一个字节继续对齐
                buffer.pop(0)

        time.sleep(0.001)
                    
except KeyboardInterrupt:
    print("\n\n正在停止采样并退出...")
    try:
        ser.write(bytes.fromhex("83 02 0D"))  # 退出时让 IMU 回到配置模式
        ser.close()
    except:
        pass
    print("已安全关闭串口。")
except Exception as e:
    print(f"\n运行错误: {e}")