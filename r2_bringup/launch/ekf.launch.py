"""Launch robot_localization EKF for R2 chassis + G354 IMU fusion

Usage:
  ros2 launch r2_bringup ekf.launch.py      # EKF only (requires chassis + IMU running)
  ros2 launch r2_bringup ekf.launch.py ekf_only:=false  # Start all: chassis + IMU + EKF
"""
import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return LaunchDescription([
        # EKF 节点
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_filter_node',
            parameters=[os.path.join(pkg_dir, 'config', 'ekf.yaml')],
            output='screen',
        ),
    ])
