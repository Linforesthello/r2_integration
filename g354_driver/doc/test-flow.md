# G354 IMU 测试流程

> 适用: 上位机直控验证
> 硬件: Epson M-G354 + JLink OB Mini（VCP 串口）

---

## 一、硬件就绪检查

```bash
# 1. 确认串口设备存在（JLink 应为 /dev/ttyACM0）
ls -la /dev/ttyACM*

# 2. 确认权限（用户需在 dialout 组）
groups

# 3. 确认设备厂商（应为 SEGGER J-Link）
udevadm info --name=/dev/ttyACM0 | grep ID_VENDOR
```

**预期结果**:
- 设备路径: `/dev/ttyACM0`
- 厂商: `SEGGER`
- 可读写权限

---

## 二、原始串口通信测试

验证 IMU 底层通信是否正常，不依赖 ROS2。

```bash
cd ~/Lin_workspace/g354_test
python3 scripts/test_g354.py
```

**预期结果**（15 秒内）:

```
成功打开串口 /dev/ttyACM0，开始发送唤醒序列...
--- 配置指令发送完毕 ---
[TEMP]: xx.xx °C | [GYRO]: X: x.xx, Y: x.xx, Z: x.xx °/s | [ACCL]: X: x.xxx, Y: x.xxx, Z: x.xxx G
```

**判断依据**:

| 数据 | 静止时正常范围 | 含义 |
|:-----|:--------------|:------|
| TEMP | 25~35 °C | 室温正常 |
| GYRO X/Y/Z | ±2 °/s 以内 | 静止时应接近 0 |
| ACCL X/Y | ±0.1 G | 水平放置时接近 0 |
| ACCL Z | -0.8 ~ -1.2 G | 重力方向，约 -1 G |

**如果失败**:

| 现象 | 可能原因 |
|:-----|:---------|
| 串口打不开 | 设备路径不对/权限不足 |
| 无数据输出 | TX/RX 接反/GND 未共地 |
| 数据乱码 | 波特率不匹配/电平不匹配 |
| 温度异常高 | 供电电压不稳 |

**操作**: 拿起 IMU 晃动/翻转，观察陀螺仪和加速度数值是否随之变化，确认数据不是假固定的。

```
按 Ctrl+C 退出
```

---

## 三、ROS2 节点测试

### 3.1 启动节点

```bash
source ~/Lin_workspace/g354_test/install/setup.bash
ros2 run g354_imu_driver imu_node
```

**预期输出**:

```
[INFO] [xxx] [g354_imu_node]: ✓ 串口 /dev/ttyACM0 已打开 (460800 baud)
[INFO] [xxx] [g354_imu_node]: ✓ IMU 配置完成，已进入采样模式
```

保持运行，新开终端做后续测试。

---

### 3.2 话题验证

```bash
# 查看话题列表
ros2 topic list

# 查看一次消息内容
ros2 topic echo /imu/data --once
```

**预期结果**:
- 话题列表包含 `/imu/data`
- 消息结构完整: `header` / `orientation` / `angular_velocity` / `linear_acceleration`
- frame_id: `imu_link`

---

### 3.3 帧率验证

```bash
ros2 topic hz /imu/data
```

**预期结果**:

```
average rate: 125.000
```

允许 ±5 Hz 波动。如果远低于 125 Hz（如 10 Hz），说明串口有丢包。

---

### 3.4 姿态验证

拿起 IMU 分别做以下动作，观察四元数变化：

| 动作 | 应看到 |
|:-----|:-------|
| 水平静止 | roll ≈ 0, pitch ≈ 0 |
| 绕 X 轴转 90° | roll 变化 |
| 绕 Y 轴转 90° | pitch 变化 |
| 快速旋转 | 陀螺仪数值跟随 |

**命令**:

```bash
# 连续观察姿态变化
ros2 topic echo /imu/data | grep -E "orientation|---"
```

---

### 3.5 停止节点

```bash
# 在节点终端按 Ctrl+C
# 应看到:
[INFO] [xxx] [g354_imu_node]: 用户中断，正在退出...
[INFO] [xxx] [g354_imu_node]: ✓ 串口已安全关闭
```

---

## 四、RViz 可视化（可选）

```bash
ros2 launch g354_imu_driver g354_rviz.launch.py
```

RViz 中应看到:
- IMU 模型在 3D 视图中显示姿态
- 随 IMU 翻转而实时旋转

---

## 五、完整测试清单

| # | 测试项 | 命令 | 期望 | 结果 |
|:--|:-------|:-----|:-----|:----:|
| 1 | 设备存在 | `ls /dev/ttyACM*` | ACM0 | ⬜ |
| 2 | 原始串口 | `python3 scripts/test_g354.py` | 温/陀/加速度数据 | ⬜ |
| 3 | ROS2 启动 | `ros2 run g354_imu_driver imu_node` | 串口打开+配置完成 | ⬜ |
| 4 | 话题列表 | `ros2 topic list` | 含 `/imu/data` | ⬜ |
| 5 | 消息内容 | `ros2 topic echo /imu/data --once` | 完整 IMU 消息 | ⬜ |
| 6 | 帧率 | `ros2 topic hz /imu/data` | ~125 Hz | ⬜ |
| 7 | 静态噪声 | 静止观察 10s | 陀螺仪 ±2°/s | ⬜ |
| 8 | 动态响应 | 手动翻转 IMU | 数值跟随变化 | ⬜ |
| 9 | 安全退出 | Ctrl+C | 串口关闭 | ⬜ |
