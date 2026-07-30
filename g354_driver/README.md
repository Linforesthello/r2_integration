# Epson M-G354 IMU · ROS2 驱动

> 上位机直控验证已完成
>
> 硬件: Epson M-G354 + JLink OB Mini（VCP 串口）
> 通信: UART burst mode, 460800 baud, 125 Sps, 36 字节帧
> 姿态解算: **Mahony 四元数滤波**

---

## 文件树

```
g354_test/
│
├── README.md                           ← 本文件，入口导航
│
├── doc/                                ← 文档
│   ├── completion-report.md           Phase 完成报告
│   ├── debug-log.md                   调试日志
│   └── test-flow.md                   测试流程（分步指南）
│
├── g354_imu_driver/                    ← ROS2 包
│   ├── __init__.py
│   ├── imu_node.py                    核心节点（Mahony 滤波）
│   └── ...
│
├── scripts/                            ← 工具脚本
│   ├── test_g354.py                   原始串口测试（不依赖 ROS2）
│   └── g354_imu_node.py               [旧] 独立脚本版（备用）
│
├── config/
│   └── g354_imu.rviz                  RViz2 可视化配置
│
├── launch/
│   └── g354_rviz.launch.py            一键启动（节点 + RViz2）
│
├── reference/                          ← 参考仓库
│   └── G354_Attitude-algorithm/        https://github.com/MTFTau-5/G354_Attitude-algorithm
│
├── package.xml                         ROS2 包定义
├── setup.py
└── setup.cfg
```

---

## 阅读顺序

```
首次阅读:  README.md → doc/test-flow.md
技术参考:  g354_imu_driver/imu_node.py
调试回溯:  doc/debug-log.md
完成记录:  doc/completion-report.md
```

---

## 快速开始

### 1. 确认设备

```bash
ls -la /dev/ttyACM*
# 应看到 /dev/ttyACM0 (SEGGER J-Link)
```

### 2. 原始串口测试（不依赖 ROS2）

```bash
cd ~/Lin_workspace/g354_test
python3 scripts/test_g354.py
```

预期输出（静止时）:
```
[TEMP]:  xx.x °C | [GYRO]: X: 0.00, Y: 0.00, Z: 0.00 °/s
                    [ACCL]: X: 0.000, Y: 0.000, Z: -1.000 G
```

### 3. ROS2 节点

```bash
source ~/Lin_workspace/g354_test/install/setup.bash
ros2 run g354_imu_driver imu_node
```

启动后自动执行:
1. 打开串口 → 配置 IMU（125 Sps）
2. **2 秒静态零偏校准**（保持 IMU 静止）
3. 进入 Mahony 姿态滤波，125 Hz 发布 `/imu/data`

### 4. RViz2 可视化

节点启动后，新开终端:

```bash
source ~/Lin_workspace/g354_test/install/setup.bash
rviz2 -d ~/Lin_workspace/g354_test/config/g354_imu.rviz
```

或一键启动:

```bash
source ~/Lin_workspace/g354_test/install/setup.bash
ros2 launch g354_imu_driver g354_rviz.launch.py
```

---

## 测试清单

详细分步测试见 [doc/test-flow.md](doc/test-flow.md)，包含:

| # | 测试项 | 命令 |
|:--|:-------|:------|
| 1 | 设备存在 | `ls /dev/ttyACM*` |
| 2 | 原始串口 | `python3 scripts/test_g354.py` |
| 3 | ROS2 启动 | `ros2 run g354_imu_driver imu_node` |
| 4 | 话题验证 | `ros2 topic echo /imu/data --once` |
| 5 | 帧率确认 | `ros2 topic hz /imu/data` |
| 6 | 静态噪声 | 静止观察 10s |
| 7 | 动态响应 | 手动翻转 IMU |

---

## 软件架构

### 姿态解算流程

```
timer_callback (8ms)
  │
  ├── ① 读串口 → 拆 36 字节帧（包头 0x80, 包尾 0x0D）
  │
  ├── ② 换算: LSB → °/s (陀螺) / G (加速度)
  │
  ├── ③ 状态机
  │     ├── 未校准 → 累积 250 帧 → 计算零偏
  │     │              → 加速度初始化姿态四元数
  │     └── 已校准 → 减零偏 → 运动检测 → Mahony 滤波
  │
  └── ④ 发布 /imu/data (sensor_msgs/Imu)
        orientation  = 四元数
        angular_vel  = 减零偏后的角速度
        linear_accel = 原始加速度 (G → m/s²)
```

### Mahony 滤波器公式

```
v = R(q) · [0, 0, 1]            ← 从四元数预测重力方向
e = a_measured × v               ← 叉积 = 姿态误差
ω += Kp · e                      ← PI 比例修正
dq/dt = 0.5 · q ⊗ [0, ω]        ← 四元数微分
q += dq/dt · dt                  ← 积分
q = q / |q|                      ← 归一化
```

| 参数 | 值 | 含义 |
|:-----|:---|:------|
| Kp | 1.0 | 加速度计修正强度 |
| 零偏校准 | 250 帧 | 启动时静态测量陀螺仪偏置 |

---

## 验证结果

### 零偏校准

```
bias (rad/s): X=-0.00027  Y=0.00037  Z=-0.00001
折合 °/s:     X=-0.015   Y=0.021    Z=-0.0006
```

### 帧率

```
average rate: 125.0 Hz ± 0.006s
```

### 静态稳定性

静止时姿态四元数变化在 ±0.001 以内，无累积漂移。

---

## 已知限制

| 限制 | 原因 | 缓解 |
|:-----|:------|:------|
| yaw 漂移 | 6 轴 IMU 无磁力计 | 融合轮速里程计（Phase 1） |
| 加速时姿态误差 | 加速度含线性分量 | 运动检测已降权 |
| 零偏仅静态校准 | 上电后温漂不跟踪 | 可用 Ki 项或切 EKF 版 |
