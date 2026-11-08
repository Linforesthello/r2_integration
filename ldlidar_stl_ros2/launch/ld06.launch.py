#!/usr/bin/env python3
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

'''
Launch arguments (R2 2026-11-06):
- node_name / topic_name / frame_id / port_name: 多雷达实例区分
- x / y / z / yaw / pitch / roll: base_link -> frame_id 的静态 TF（平移单位 m，角度单位弧度）
- 默认值面向老车首期单雷达；双雷达用参数覆盖（见 doc/old-car/ld06-dual-lidar.md）
- filtered_topic_name（2026-11-08 新增）：自车回波过滤链的输出话题名，默认 scan

安装几何（2026-11-08 实车量测，G10，见 doc/phase0/sensor-mount.md §六）：
- 平移 (x, y, z) = (+0.275, +0.290, +0.040) m（base_link = 底盘正中心、离地 0.12 m；
  雷达光学中心离地 16 cm → z = 0.16 − 0.12）
- yaw = −π/2：LD06 手册 §4 定义 0° = 模块顶部 △ 标记方向、角度顺时针增大；实测 △ 指向车体 −y，
  故 base_laser 的 +x 对齐车体 −y。车头物体在雷达原始角为 270°，驱动发布角 = 360°−原始角
  → /scan 读 +90°，与 yaw = −π/2 一致（推导见 doc/old-car/ld06-dual-lidar.md §三 P7）
- pitch / roll = 0：按水平安装（未单独量测）
- ✅ yaw 已于 2026-11-08 实物复核通过（350mm 箱 @≈1m：箱面倾角 −2.1°、中心 +94°）；
  复核口径：+90° 仅对「雷达光心正前方」成立，车体中线目标读 ≈73°（见 sensor-mount §6.1）

自车回波过滤链（2026-11-08，方案 B，见 doc/phase0/sensor-mount.md §6.1.2）：
- 驱动默认改发 scan_raw，经 laser_filters 的 scan_to_scan_filter_chain 过滤后发 scan；
  下游（slam_toolbox / Nav2 costmap / explore）继续读 scan，配置零改动
- 过滤规则见 config/ld06_scan_filter.yaml：端点落在车体矩形内的波束置 NaN
- 原始数据仍可从 /scan_raw 取（诊断用），过滤后数据从 /scan 取
- 依赖系统包 ros-humble-laser-filters（VM 已装 2.0.9；N97 需 sudo apt install）
'''

def generate_launch_description():
  node_name           = LaunchConfiguration('node_name')
  topic_name          = LaunchConfiguration('topic_name')
  filtered_topic_name = LaunchConfiguration('filtered_topic_name')
  frame_id            = LaunchConfiguration('frame_id')
  port_name           = LaunchConfiguration('port_name')
  port_baudrate       = LaunchConfiguration('port_baudrate')
  x                   = LaunchConfiguration('x')
  y                   = LaunchConfiguration('y')
  z                   = LaunchConfiguration('z')
  yaw                 = LaunchConfiguration('yaw')
  pitch               = LaunchConfiguration('pitch')
  roll                = LaunchConfiguration('roll')

  args = [
    DeclareLaunchArgument('node_name',     default_value='LD06',
                          description='ROS2 node name'),
    DeclareLaunchArgument('topic_name',    default_value='scan_raw',
                          description='Driver LaserScan topic (raw, self-returns included)'),
    DeclareLaunchArgument('filtered_topic_name', default_value='scan',
                          description='Filtered LaserScan topic (consumed by slam_toolbox/Nav2)'),
    DeclareLaunchArgument('frame_id',      default_value='base_laser',
                          description='LaserScan frame_id / TF child frame'),
    DeclareLaunchArgument('port_name',     default_value='/dev/r2_ld06_a',
                          description='Serial port (udev symlink or by-id path)'),
    DeclareLaunchArgument('port_baudrate', default_value='230400',
                          description='Serial baudrate'),
    DeclareLaunchArgument('x',             default_value='0.275',
                          description='TF translation x (m), measured 2026-11-08'),
    DeclareLaunchArgument('y',             default_value='0.29',
                          description='TF translation y (m), measured 2026-11-08'),
    DeclareLaunchArgument('z',             default_value='0.04',
                          description='TF translation z (m), measured 2026-11-08'),
    DeclareLaunchArgument('yaw',           default_value='-1.5708',
                          description='TF yaw (rad), measured 2026-11-08'),
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
    arguments=[x, y, z, yaw, pitch, roll, 'base_link', frame_id]
  )

  # 自车回波过滤链（2026-11-08）：scan_raw -> 车体多边形内波束置 NaN -> scan
  # 配置 config/ld06_scan_filter.yaml；节点名必须与 yaml 顶层键一致
  scan_filter_config = os.path.join(
      get_package_share_directory('ldlidar_stl_ros2'),
      'config',
      'ld06_scan_filter.yaml'
  )
  scan_filter_node = Node(
      package='laser_filters',
      executable='scan_to_scan_filter_chain',
      name='scan_to_scan_filter_chain',
      output='screen',
      parameters=[scan_filter_config],
      remappings=[
          ('scan', topic_name),
          ('scan_filtered', filtered_topic_name),
      ],
  )

  # Define LaunchDescription variable
  ld = LaunchDescription(args)

  ld.add_action(ldlidar_node)
  ld.add_action(base_link_to_laser_tf_node)
  ld.add_action(scan_filter_node)

  return ld
