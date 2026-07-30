#!/usr/bin/env python3
"""
Epson M-G354 IMU ROS 2 Driver Node — 顶层入口
可直接 python3 运行，也可 ros2 run 运行

使用方法:
  python3 g354_imu_node.py                      # 直接运行
  rviz2 -d config/g354_imu.rviz                 # 另开终端启动 RViz2
"""
from g354_imu_driver.imu_node import main

if __name__ == '__main__':
    main()
