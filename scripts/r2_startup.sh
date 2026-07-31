#!/bin/bash
# R2 底盘 + IMU + EKF 一键启动
# 用法: bash ~/Lin_workspace/r2_brigup_start.sh

set -e

echo "=== [1/3] CAN 总线 ==="
sudo slcand -o -c -s8 /dev/ttyACM0 can0 2>/dev/null
sudo ip link set can0 up
echo "  can0 已启动"

echo "=== [2/3] 底盘 + IMU + EKF ==="
source ~/Lin_workspace/r2_integration/install/setup.bash

# 开三个终端（需要 gnome-terminal）
gnome-terminal --tab --title="底盘" -- bash -c "
  ros2 launch ~/Lin_workspace/r2_integration/r2_bringup/launch/chassis.launch.py; exec bash"

gnome-terminal --tab --title="IMU" -- bash -c "
  source ~/Lin_workspace/r2_integration/install/setup.bash
  ros2 run g354_imu_driver imu_node --ros-args -p serial_port:=/dev/ttyACM1; exec bash"

gnome-terminal --tab --title="EKF" -- bash -c "
  source ~/Lin_workspace/r2_integration/install/setup.bash
  ros2 launch ~/Lin_workspace/r2_integration/r2_bringup/launch/ekf.launch.py; exec bash"

echo "=== 全部启动完成 ==="