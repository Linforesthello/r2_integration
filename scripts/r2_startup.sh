#!/bin/bash
# R2 底盘 + IMU + EKF 一键启动
# 用法: bash ~/Lin_workspace/r2_integration/scripts/r2_startup.sh
# 依赖: gnome-terminal、CAN 适配器在 /dev/ttyACM0、G354 在 /dev/ttyACM1

set -e

echo "=== [1/3] CAN 总线 ==="
sudo slcand -o -c -s8 /dev/ttyACM0 can0 2>/dev/null
sudo ip link set can0 up
echo "  can0 已启动"

echo "=== [2/3] 底盘 + IMU + EKF ==="
source ~/Lin_workspace/r2_integration/install/setup.bash

# 开三个终端（需要 gnome-terminal）
# 底盘带 publish_tf:=false：TF 由 EKF 统一发布，避免双发布者冲突
gnome-terminal --tab --title="底盘" -- bash -c "
  source ~/Lin_workspace/r2_integration/install/setup.bash
  ros2 launch r2_bringup chassis.launch.py publish_tf:=false; exec bash"

gnome-terminal --tab --title="IMU" -- bash -c "
  source ~/Lin_workspace/r2_integration/install/setup.bash
  ros2 launch g354_imu_driver g354_rviz.launch.py rviz:=false serial_port:=/dev/ttyACM1; exec bash"

gnome-terminal --tab --title="EKF" -- bash -c "
  source ~/Lin_workspace/r2_integration/install/setup.bash
  ros2 launch r2_bringup ekf.launch.py; exec bash"

echo "=== 全部启动完成 ==="
