# R2 Nav2 Explore 启动（Humble 1.1.20）——去定位层版本
#
# 与 nav2.launch.py 的唯一区别：不启动 map_server / amcl / lifecycle_manager_localization。
# 定位层由 slam_toolbox 提供（它发布 map→odom 与 /map），Nav2 只负责规划控制。
#
# 前置（须先跑起）：LD06 驱动(/scan) → 底盘(publish_tf:=false) → IMU → EKF → slam_toolbox
# 用法：
#   ros2 launch r2_bringup nav2_explore.launch.py
#   ros2 launch r2_bringup nav2_explore.launch.py rviz:=true
#   ros2 launch r2_bringup nav2_explore.launch.py params_file:=<老车参数文件>
#
# 关键适配：
#   - /odom remap → /odometry/filtered（EKF 里程计）
#   - 默认参数文件是**老车 LD06 版** nav2_params_ld06.yaml（安全默认，降额 + 已删低带源），
#     与 nav2.launch.py 不同。
#     原默认（2026-11-07 前）: 降额版 nav2_params_low.yaml —— 其 velodyne_low 源老车不可用（G4）
#   - 不要点 "2D Pose Estimate"：map→odom 由 slam_toolbox 提供，AMCL 未启动
#   - 参数文件里的 amcl / map_server 段不会被使用，不需要删
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterFile


def generate_launch_description():
    pkg_dir = get_package_share_directory('r2_bringup')
    # 安全默认：降额参数。nav2.launch.py 默认是全速版，explore 不沿用那个默认。
    # 2026-11-07 改默认：low 版含 velodyne_low 低带源（老车无 /velodyne_points，G4）→ 用 LD06 版
    # 原行（保留备查）：default_params = os.path.join(pkg_dir, 'config', 'nav2_params_low.yaml')
    default_params = os.path.join(pkg_dir, 'config', 'nav2_params_ld06.yaml')

    params_file = LaunchConfiguration('params_file')
    use_sim_time = LaunchConfiguration('use_sim_time')
    autostart = LaunchConfiguration('autostart')
    with_rviz = LaunchConfiguration('rviz')

    # 本 launch 不再改写 yaml_filename（无 map_server），直接加载参数文件
    configured_params = ParameterFile(params_file, allow_substs=True)

    # EKF 里程计话题是 /odometry/filtered，Nav2 默认订阅 /odom → remap
    remappings = [('/odom', '/odometry/filtered'),
                  ('/tf', 'tf'),
                  ('/tf_static', 'tf_static')]

    nodes = [
        # ---- 导航：规划 + 控制 + 行为（定位层已移除）----
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
        DeclareLaunchArgument('params_file', default_value=default_params,
                              description='Nav2 参数文件（默认 LD06 降额版 nav2_params_ld06.yaml）'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('autostart', default_value='true'),
        DeclareLaunchArgument('rviz', default_value='false'),
        *nodes, rviz_node,
    ])
