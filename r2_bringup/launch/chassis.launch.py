"""R2 底盘 CAN 控制节点启动

用法:
  ros2 launch r2_bringup chassis.launch.py                      # 独立使用（发 TF）
  ros2 launch r2_bringup chassis.launch.py publish_tf:=false    # EKF 场景（TF 由 EKF 发布）
"""
import os
from ament_index_python.packages import get_package_prefix, get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _find_node_executable(pkg: str, name: str) -> str:
    """console_script 入口的安装位置两种环境不一致:
    标准 ament_python 布局在 lib/<pkg>/，本机 colcon 行为装在 bin/，这里两种都找。"""
    prefix = get_package_prefix(pkg)
    for rel in (os.path.join('lib', pkg, name), os.path.join('bin', name)):
        path = os.path.join(prefix, rel)
        if os.path.exists(path):
            return path
    raise FileNotFoundError(f'找不到 {pkg} 的入口脚本 {name}（已查找 lib/{pkg}/ 和 bin/）')


def generate_launch_description():
    pkg_dir = get_package_share_directory('r2_bringup')
    config_path = os.path.join(pkg_dir, 'config', 'r2_params.yaml')

    return LaunchDescription([
        DeclareLaunchArgument('publish_tf', default_value='true',
                              description='是否发布 odom→base_link TF（EKF 场景设 false）'),

        Node(
            executable=_find_node_executable('r2_bringup', 'chassis_node'),
            name='r2_chassis_node',
            output='screen',
            parameters=[config_path,
                        {'publish_tf': LaunchConfiguration('publish_tf')}],
        ),
    ])
