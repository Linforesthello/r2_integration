"""R2 底盘 CAN 控制节点启动

用法:
  ros2 launch r2_bringup chassis.launch.py                      # 独立使用（发 TF）
  ros2 launch r2_bringup chassis.launch.py publish_tf:=false    # EKF 场景（TF 由 EKF 发布）
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory('r2_bringup')
    config_path = os.path.join(pkg_dir, 'config', 'r2_params.yaml')

    return LaunchDescription([
        DeclareLaunchArgument('publish_tf', default_value='true',
                              description='是否发布 odom→base_link TF（EKF 场景设 false）'),

        Node(
            package='r2_bringup',
            executable='chassis_node',
            name='r2_chassis_node',
            output='screen',
            parameters=[config_path,
                        {'publish_tf': LaunchConfiguration('publish_tf')}],
        ),
    ])
