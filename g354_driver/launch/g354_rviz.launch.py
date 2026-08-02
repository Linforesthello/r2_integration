"""启动 Epson M-G354 IMU 驱动节点 + 可选 RViz2 可视化

用法:
  ros2 launch g354_imu_driver g354_rviz.launch.py              # 节点 + RViz2
  ros2 launch g354_imu_driver g354_rviz.launch.py rviz:=false   # 仅节点（SSH/无显示器）
  ros2 launch g354_imu_driver g354_rviz.launch.py serial_port:=/dev/ttyACM1
"""
import os
from ament_index_python.packages import get_package_prefix, get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.conditions import IfCondition
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
    pkg_dir = get_package_share_directory('g354_imu_driver')

    return LaunchDescription([
        # 启动参数
        DeclareLaunchArgument('serial_port', default_value='/dev/ttyACM1',
                              description='G354 串口设备路径'),
        DeclareLaunchArgument('rviz', default_value='true',
                              description='是否启动 RViz2 可视化（SSH 下设为 false）'),

        # IMU 驱动节点
        Node(
            executable=_find_node_executable('g354_imu_driver', 'imu_node'),
            name='g354_imu_node',
            output='screen',
            parameters=[{'serial_port': LaunchConfiguration('serial_port')}],
        ),

        # RViz2 可视化（可选）
        ExecuteProcess(
            cmd=['rviz2', '-d', os.path.join(pkg_dir, 'config', 'g354_imu.rviz')],
            name='rviz2',
            output='screen',
            condition=IfCondition(LaunchConfiguration('rviz')),
        ),
    ])
