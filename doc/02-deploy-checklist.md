# R2 集成 · N97 Mini PC 部署清单

> 从 VMware 虚拟机迁移到 N97 Mini PC（实车工控机）
> N97 需安装 Ubuntu 22.04 + ROS2 Humble

---

## 一、前置条件（N97 上操作）

```bash
# 系统
sudo apt update && sudo apt upgrade -y

# ROS2 Humble（如未安装）
# 参照: https://docs.ros.org/en/humble/Installation/Ubuntu-Install.html

# 编译工具
sudo apt install -y python3-pip python3-colcon-common-extensions

# CAN 总线工具
sudo apt install -y can-utils
```

---

## 二、代码迁移

### 2.1 ROS2 工作区

```bash
# 在 N97 上
mkdir -p ~/Lin_workspace
cd ~/Lin_workspace

# 直接拷贝（U盘/网络/版本管理）
# 从 VMware 把以下目录拷贝过来:

# 核心工作区
r2_integration/           # → ~/Lin_workspace/r2_integration/
```

### 2.2 工具脚本

```bash
# CanCmd 工具
# 从 VMware 拷贝:
~/Lin_workspace/command/   # → ~/Lin_workspace/command/

# 其中 can_command.py 是 CAN 总线配置工具
```

### 2.3 SavvyCAN（可选，CAN 监控）

```bash
# SavvyCAN 是预编译的 Qt 应用，拷贝整个目录即可
~/SavvyCAN/                # → ~/SavvyCAN/

# 或从源码安装:
# https://github.com/collabora/SavvyCAN
```

---

## 三、系统依赖安装

```bash
# ROS2 包
sudo apt install -y \
  ros-humble-robot-localization \
  ros-humble-teleop-twist-keyboard \
  ros-humble-rviz2 \
  ros-humble-rqt-plot \
  ros-humble-plotjuggler-ros \
  ros-humble-tf2-ros

# Python 包
pip3 install \
  pyserial \
  python-can \
  rosbags
```

---

## 四、硬件配置

### 4.1 CAN 总线

```bash
# USB-CAN 适配器（slcan 协议）
# 使用 CanCmd 工具配置:
python3 ~/Lin_workspace/command/can_command.py

# 或手动:
sudo slcand -o -c -s8 /dev/ttyACM0 can0
sudo ip link set can0 up
```

**注意**: N97 上的串口设备路径可能与 VMware 不同，用以下命令确认:

```bash
ls -la /dev/ttyACM*
# 可能显示 /dev/ttyACM0（CANable2）或不同的编号
```

### 4.2 G354 IMU（串口）

```bash
# 接上 JLink OB Mini，确认设备路径:
ls -la /dev/ttyACM*
# 期望: /dev/ttyACM0 或 /dev/ttyACM1

# 如果设备路径不是 /dev/ttyACM0，启动时指定:
ros2 run g354_imu_driver imu_node --ros-args -p serial_port:=/dev/ttyACM1
```

---

## 五、构建

```bash
cd ~/Lin_workspace/r2_integration
source /opt/ros/humble/setup.bash
colcon build
```

---

## 六、启动顺序（实车完整流程）

```bash
# ① CAN 总线
sudo slcand -o -c -s8 /dev/ttyACM0 can0
sudo ip link set can0 up

# ② 底盘
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch r2_bringup chassis.launch.py

# ③ IMU
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 run g354_imu_driver imu_node

# ④ EKF 融合
source ~/Lin_workspace/r2_integration/install/setup.bash
ros2 launch r2_bringup ekf.launch.py

# ⑤ 键盘控制（测试用）
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

---

## 七、验证清单

启动后检查:

| 验证项 | 命令 | 预期 |
|:-------|:-----|:------|
| CAN 通信 | `candump can0` | 4 路 0x323~0x326 状态帧 |
| 底盘控制 | `ros2 topic list \| grep /cmd_vel` | 话题存在 |
| 轮速里程计 | `ros2 topic echo /odom_wheels --once` | 有位置/速度输出 |
| IMU 数据 | `ros2 topic echo /imu/data --once` | 有姿态/角速度/加速度 |
| EKF 输出 | `ros2 topic echo /odometry/filtered --once` | 有融合后的里程计 |
| 键盘控制 | 按 i/j/l/, 等键 | 车子响应运动 |
| IMU 帧率 | `ros2 topic hz /imu/data` | ~87 Hz |
| EKF 帧率 | `ros2 topic hz /odometry/filtered` | ~50 Hz |

---

## 八、可能遇到的问题

| 问题 | 排查方向 |
|:-----|:---------|
| CAN 不通 | USB-CAN 适配器是否插好，`slcand` 设备路径是否正确 |
| IMU 串口打不开 | 设备路径、权限（`sudo usermod -aG dialout $USER`）|
| colcon build 失败 | 缺依赖，`rosdep install -i --from-path src --rosdistro humble` |
| EKF 报 tf 相关错误 | 确保 chassis_node 已启动，/odom_wheels 正在发布 |

---

## 九、不需要迁移的内容

| 项目 | 原因 |
|:-----|:------|
| STM32 固件 | 烧录在芯片内，N97 不运行 |
| Obsidian 笔记 | 个人知识库，非运行时依赖 |
| `reference/G354_Attitude-algorithm` | 参考代码，非运行必需 |
| 旧的 build/install/log 目录 | 到 N97 上重新 colcon build |

---

## 十、附：需要确认的 N97 硬件接口

| 设备 | 接口 | 需确认 |
|:-----|:------|:--------|
| USB-CAN 适配器 | USB-A | 设备路径 `/dev/ttyACMx` |
| JLink OB Mini (G354) | USB-A | 设备路径 `/dev/ttyACMx` |
| MID70 LiDAR | USB-C/以太网 | Phase 2 才需要 |
| VLP16 LiDAR | 以太网 | Phase 3 才需要 |
| D435 相机 | USB-A | Phase 4 才需要 |
