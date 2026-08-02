"""Launch robot_localization EKF for R2 chassis + G354 IMU fusion

Usage:
  ros2 launch r2_bringup ekf.launch.py      # EKF only (requires chassis + IMU running)
                                             # chassis 需带 publish_tf:=false（TF 由 EKF 发布）
                                             # 三合一启动见 scripts/r2_startup.sh
"""
import os
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return LaunchDescription([
        # base_link → imu_link 静态 TF（G354 安装在底盘中心、方向与 base_link 一致，单位变换）
        # EKF 需要 IMU frame 在 TF 树中可达，否则报 "Could not obtain transform"
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            arguments=['0', '0', '0', '0', '0', '0', 'base_link', 'imu_link'],
        ),

        # EKF 节点
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_filter_node',
            parameters=[os.path.join(pkg_dir, 'config', 'ekf.yaml')],
            output='screen',
        ),
    ])
