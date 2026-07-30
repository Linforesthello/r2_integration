"""启动 Epson M-G354 IMU 驱动节点 + RViz2 可视化"""
import os
from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return LaunchDescription([
        # IMU 驱动节点 (使用安装后的包节点)
        Node(
            package='g354_imu_driver',
            executable='imu_node',
            name='g354_imu_node',
            output='screen',
        ),

        # RViz2 可视化
        ExecuteProcess(
            cmd=['rviz2', '-d', os.path.join(pkg_dir, 'config', 'g354_imu.rviz')],
            name='rviz2',
            output='screen',
        ),
    ])
