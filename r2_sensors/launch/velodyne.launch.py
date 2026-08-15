"""Velodyne VLP-16 启动：driver + transform + robot_state_publisher + laserscan(/scan)。

- 两机通用（VM/N97 同用一份，git 管理，消灭拷贝漂移；2026-08-14 入库）
- device_ip 可通过启动参数覆盖（默认 10.18.18.6）
- robot_state_publisher 发布 base_link→velodyne TF（urdf 随包安装，config/r2.urdf）

用法：
    ros2 launch r2_sensors velodyne.launch.py
    ros2 launch r2_sensors velodyne.launch.py device_ip:=10.18.18.6
"""

import os

import ament_index_python.packages
import launch
import launch_ros.actions
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    # --- Robot State Publisher（发布 TF，读包内 urdf） ---
    pkg_share = ament_index_python.packages.get_package_share_directory('r2_sensors')
    urdf_path = os.path.join(pkg_share, 'config', 'r2.urdf')
    with open(urdf_path, 'r') as f:
        robot_desc = f.read()

    robot_state_publisher = launch_ros.actions.Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='both',
        parameters=[{'robot_description': robot_desc}])

    # --- Velodyne Driver ---
    driver_share = ament_index_python.packages.get_package_share_directory('velodyne_driver')
    driver_params = os.path.join(driver_share, 'config', 'VLP16-velodyne_driver_node-params.yaml')
    velodyne_driver_node = launch_ros.actions.Node(
        package='velodyne_driver',
        executable='velodyne_driver_node',
        output='both',
        parameters=[driver_params,
                    {'device_ip': LaunchConfiguration('device_ip'), 'frame_id': 'velodyne'}])

    # --- PointCloud Transform ---
    convert_share = ament_index_python.packages.get_package_share_directory('velodyne_pointcloud')
    convert_params_file = os.path.join(convert_share, 'config', 'VLP16-velodyne_transform_node-params.yaml')
    with open(convert_params_file, 'r') as f:
        import yaml
        convert_params = yaml.safe_load(f)['velodyne_transform_node']['ros__parameters']
    convert_params['calibration'] = os.path.join(convert_share, 'params', 'VLP16db.yaml')
    convert_params['frame_id'] = 'velodyne'
    # 08-15 性能调优：organize_cloud 无序紧凑容器（省转换 CPU/话题带宽，KISS/Nav2 均不需要 organized）
    convert_params['organize_cloud'] = False
    # 08-15 性能调优：max_range 130→40m，转换层提前裁剪，与 KISS max_range 30 两级过滤对齐
    convert_params['max_range'] = 40.0
    # 08-15 盲区修复：min_range 0.9→0.5（VLP-16 规格最小测距）。
    # 0.9m 裁剪导致车头前方(0.4~0.9m)障碍对 /scan 不可见，叠加 local_costmap 3×3 时有效避障窗口仅 ~0.2m
    convert_params['min_range'] = 0.5
    velodyne_transform_node = launch_ros.actions.Node(
        package='velodyne_pointcloud',
        executable='velodyne_transform_node',
        output='both',
        parameters=[convert_params])

    # --- 2D LaserScan（08-15 恢复：Nav2 接入，AMCL 与 costmap 订阅 /scan；frame_id 显式指定与 TF 链一致） ---
    laserscan_share = ament_index_python.packages.get_package_share_directory('velodyne_laserscan')
    laserscan_params = os.path.join(laserscan_share, 'config', 'default-velodyne_laserscan_node-params.yaml')
    velodyne_laserscan_node = launch_ros.actions.Node(
        package='velodyne_laserscan',
        executable='velodyne_laserscan_node',
        output='both',
        parameters=[laserscan_params, {'frame_id': 'velodyne'}])

    return launch.LaunchDescription([
        DeclareLaunchArgument('device_ip', default_value='10.18.18.6',
                              description='VLP-16 雷达 IP'),
        robot_state_publisher,
        velodyne_driver_node,
        velodyne_transform_node,
        velodyne_laserscan_node,
        launch.actions.RegisterEventHandler(
            event_handler=launch.event_handlers.OnProcessExit(
                target_action=velodyne_driver_node,
                on_exit=[launch.actions.EmitEvent(event=launch.events.Shutdown())]),
        ),
    ])
