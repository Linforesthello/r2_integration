#!/usr/bin/env python3
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

'''
Launch arguments (R2 2026-11-06):
- node_name / topic_name / frame_id / port_name: 多雷达实例区分
- z / yaw / pitch / roll: base_link -> frame_id 的静态 TF（角度单位：弧度）
- 默认值面向老车首期单雷达；双雷达用参数覆盖（见 doc/old-car/ld06-dual-lidar.md）
'''

def generate_launch_description():
  node_name     = LaunchConfiguration('node_name')
  topic_name    = LaunchConfiguration('topic_name')
  frame_id      = LaunchConfiguration('frame_id')
  port_name     = LaunchConfiguration('port_name')
  port_baudrate = LaunchConfiguration('port_baudrate')
  z             = LaunchConfiguration('z')
  yaw           = LaunchConfiguration('yaw')
  pitch         = LaunchConfiguration('pitch')
  roll          = LaunchConfiguration('roll')

  args = [
    DeclareLaunchArgument('node_name',     default_value='LD06',
                          description='ROS2 node name'),
    DeclareLaunchArgument('topic_name',    default_value='scan',
                          description='LaserScan topic name'),
    DeclareLaunchArgument('frame_id',      default_value='base_laser',
                          description='LaserScan frame_id / TF child frame'),
    DeclareLaunchArgument('port_name',     default_value='/dev/r2_ld06_a',
                          description='Serial port (udev symlink or by-id path)'),
    DeclareLaunchArgument('port_baudrate', default_value='230400',
                          description='Serial baudrate'),
    DeclareLaunchArgument('z',             default_value='0.18',
                          description='TF translation z (m), placeholder'),
    DeclareLaunchArgument('yaw',           default_value='0.0',
                          description='TF yaw (rad)'),
    DeclareLaunchArgument('pitch',         default_value='0.0',
                          description='TF pitch (rad)'),
    DeclareLaunchArgument('roll',          default_value='0.0',
                          description='TF roll (rad)'),
  ]

  # LDROBOT LiDAR publisher node
  ldlidar_node = Node(
      package='ldlidar_stl_ros2',
      executable='ldlidar_stl_ros2_node',
      name=node_name,
      output='screen',
      parameters=[{
        'product_name': 'LDLiDAR_LD06',
        'topic_name': topic_name,
        'frame_id': frame_id,
        'port_name': port_name,
        'port_baudrate': ParameterValue(port_baudrate, value_type=int),
        'laser_scan_dir': True,
        'enable_angle_crop_func': False,
        'angle_crop_min': 135.0,
        'angle_crop_max': 225.0,
      }]
  )

  # base_link to laser frame tf node (node name derived from frame_id)
  base_link_to_laser_tf_node = Node(
    package='tf2_ros',
    executable='static_transform_publisher',
    name=['base_link_to_', frame_id, '_ld06'],
    arguments=['0', '0', z, yaw, pitch, roll, 'base_link', frame_id]
  )

  # Define LaunchDescription variable
  ld = LaunchDescription(args)

  ld.add_action(ldlidar_node)
  ld.add_action(base_link_to_laser_tf_node)

  return ld
