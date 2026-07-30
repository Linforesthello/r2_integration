"""R2 底盘 CAN 控制节点启动

用法:
  ros2 launch r2_bringup chassis.launch.py
"""
import os
from launch import LaunchDescription
from launch.actions import ExecuteProcess


def generate_launch_description():
    pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    node_script = os.path.join(pkg_dir, 'r2_bringup', 'chassis_node.py')
    config_path = os.path.join(pkg_dir, 'config', 'r2_params.yaml')

    return LaunchDescription([
        ExecuteProcess(
            cmd=['python3', node_script,
                 '--ros-args', '--params-file', config_path],
            name='r2_chassis_node',
            output='screen',
        ),
    ])
