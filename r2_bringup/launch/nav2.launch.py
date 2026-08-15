# R2 Nav2 启动（Humble 1.1.20，独立节点方式，非 composition）
#
# 前置（须先跑起）：雷达 → KISS → 底盘(publish_tf:=false) → IMU → EKF → velodyne_laserscan(/scan)
# 用法：
#   ros2 launch r2_bringup nav2.launch.py map:=/home/lin/maps/nav_map/map.yaml
#   ros2 launch r2_bringup nav2.launch.py map:=... rviz:=true   # 带 rviz
# 关键适配：
#   - /odom remap → /odometry/filtered（EKF 里程计）
#   - AMCL 全向运动模型 + MPPI Omni 控制器（见 config/nav2_params.yaml）
#   - rviz 中须先 "2D Pose Estimate" 给定初始位姿（AMCL 收敛）再发 goal
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterFile
from nav2_common.launch import RewrittenYaml


def generate_launch_description():
    pkg_dir = get_package_share_directory('r2_bringup')
    default_params = os.path.join(pkg_dir, 'config', 'nav2_params.yaml')

    map_yaml = LaunchConfiguration('map')
    params_file = LaunchConfiguration('params_file')
    use_sim_time = LaunchConfiguration('use_sim_time')
    autostart = LaunchConfiguration('autostart')
    with_rviz = LaunchConfiguration('rviz')

    # map 路径注入 map_server 的 yaml_filename
    configured_params = ParameterFile(
        RewrittenYaml(
            source_file=params_file,
            root_key='',
            param_rewrites={'yaml_filename': map_yaml},
            convert_types=True),
        allow_substs=True)

    # EKF 里程计话题是 /odometry/filtered，Nav2 默认订阅 /odom → remap
    remappings = [('/odom', '/odometry/filtered'),
                  ('/tf', 'tf'),
                  ('/tf_static', 'tf_static')]

    nodes = [
        # ---- 定位：地图 + AMCL ----
        Node(package='nav2_map_server', executable='map_server',
             name='map_server', output='screen',
             parameters=[configured_params], remappings=remappings),
        Node(package='nav2_amcl', executable='amcl', name='amcl',
             output='screen', parameters=[configured_params], remappings=remappings),
        Node(package='nav2_lifecycle_manager', executable='lifecycle_manager',
             name='lifecycle_manager_localization', output='screen',
             parameters=[{'use_sim_time': use_sim_time,
                          'autostart': autostart,
                          'node_names': ['map_server', 'amcl']}]),

        # ---- 导航：规划 + 控制 + 行为 ----
        Node(package='nav2_planner', executable='planner_server',
             name='planner_server', output='screen',
             parameters=[configured_params], remappings=remappings),
        Node(package='nav2_controller', executable='controller_server',
             name='controller_server', output='screen',
             parameters=[configured_params], remappings=remappings),
        Node(package='nav2_smoother', executable='smoother_server',
             name='smoother_server', output='screen',
             parameters=[configured_params], remappings=remappings),
        Node(package='nav2_behaviors', executable='behavior_server',
             name='behavior_server', output='screen',
             parameters=[configured_params], remappings=remappings),
        Node(package='nav2_bt_navigator', executable='bt_navigator',
             name='bt_navigator', output='screen',
             parameters=[configured_params], remappings=remappings),
        Node(package='nav2_velocity_smoother', executable='velocity_smoother',
             name='velocity_smoother', output='screen',
             parameters=[configured_params], remappings=remappings),
        Node(package='nav2_lifecycle_manager', executable='lifecycle_manager',
             name='lifecycle_manager_navigation', output='screen',
             parameters=[{'use_sim_time': use_sim_time,
                          'autostart': autostart,
                          'node_names': ['planner_server', 'controller_server',
                                         'smoother_server', 'behavior_server',
                                         'bt_navigator', 'velocity_smoother']}]),
    ]

    rviz_node = Node(
        package='rviz2', executable='rviz2', name='rviz2', output='screen',
        arguments=['-d', os.path.join(pkg_dir, 'config', 'nav2.rviz')],
        condition=IfCondition(with_rviz))

    return LaunchDescription([
        DeclareLaunchArgument('map', description='地图 yaml 完整路径（必填）'),
        DeclareLaunchArgument('params_file', default_value=default_params,
                              description='Nav2 参数文件'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('autostart', default_value='true'),
        DeclareLaunchArgument('rviz', default_value='false'),
        *nodes, rviz_node,
    ])
