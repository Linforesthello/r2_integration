lin@lin-Default-string:~$ ros2 node list
/ekf_filter_node
/g354_imu_node
/kiss_icp_node
/r2_chassis_node
/r2_teleop_keyboard
/robot_state_publisher
/rviz
/static_transform_publisher_A0Bsvyylj5E4yWG0
/transform_listener_impl_5dbbf6029b90
/transform_listener_impl_5e78c1d235b0
/transform_listener_impl_5f73e86d7d20
/velodyne_driver_node
/velodyne_laserscan_node
/velodyne_transform_node
lin@lin-Default-string:~$ for t in /velodyne_points /kiss/odometry /odom_wheels /imu/data /odometry/filtered /cmd_vel; do
  echo "== $t =="
  ros2 topic info -v $t
done
== /velodyne_points ==
Type: sensor_msgs/msg/PointCloud2

Publisher count: 1

Node name: velodyne_transform_node
Node namespace: /
Topic type: sensor_msgs/msg/PointCloud2
Endpoint type: PUBLISHER
GID: 01.0f.e5.f8.5d.12.0c.3e.00.00.00.00.00.00.13.03.00.00.00.00.00.00.00.00
QoS profile:
  Reliability: RELIABLE
  History (Depth): UNKNOWN
  Durability: VOLATILE
  Lifespan: Infinite
  Deadline: Infinite
  Liveliness: AUTOMATIC
  Liveliness lease duration: Infinite

Subscription count: 2

Node name: velodyne_laserscan_node
Node namespace: /
Topic type: sensor_msgs/msg/PointCloud2
Endpoint type: SUBSCRIPTION
GID: 01.0f.e5.f8.5f.12.92.f0.00.00.00.00.00.00.12.04.00.00.00.00.00.00.00.00
QoS profile:
  Reliability: RELIABLE
  History (Depth): UNKNOWN
  Durability: VOLATILE
  Lifespan: Infinite
  Deadline: Infinite
  Liveliness: AUTOMATIC
  Liveliness lease duration: Infinite

Node name: kiss_icp_node
Node namespace: /
Topic type: sensor_msgs/msg/PointCloud2
Endpoint type: SUBSCRIPTION
GID: 01.0f.e5.f8.e6.13.a7.94.00.00.00.00.00.00.12.04.00.00.00.00.00.00.00.00
QoS profile:
  Reliability: BEST_EFFORT
  History (Depth): UNKNOWN
  Durability: VOLATILE
  Lifespan: Infinite
  Deadline: Infinite
  Liveliness: AUTOMATIC
  Liveliness lease duration: Infinite

== /kiss/odometry ==
Type: nav_msgs/msg/Odometry

Publisher count: 1

Node name: kiss_icp_node
Node namespace: /
Topic type: nav_msgs/msg/Odometry
Endpoint type: PUBLISHER
GID: 01.0f.e5.f8.e6.13.a7.94.00.00.00.00.00.00.13.03.00.00.00.00.00.00.00.00
QoS profile:
  Reliability: RELIABLE
  History (Depth): UNKNOWN
  Durability: VOLATILE
  Lifespan: Infinite
  Deadline: Infinite
  Liveliness: AUTOMATIC
  Liveliness lease duration: Infinite

Subscription count: 1

Node name: rviz
Node namespace: /
Topic type: nav_msgs/msg/Odometry
Endpoint type: SUBSCRIPTION
GID: 01.0f.e5.f8.e6.19.53.89.00.00.00.00.00.00.1d.04.00.00.00.00.00.00.00.00
QoS profile:
  Reliability: RELIABLE
  History (Depth): UNKNOWN
  Durability: VOLATILE
  Lifespan: Infinite
  Deadline: Infinite
  Liveliness: AUTOMATIC
  Liveliness lease duration: Infinite

== /odom_wheels ==
Type: nav_msgs/msg/Odometry

Publisher count: 1

Node name: r2_chassis_node
Node namespace: /
Topic type: nav_msgs/msg/Odometry
Endpoint type: PUBLISHER
GID: 01.0f.e5.f8.af.14.e9.98.00.00.00.00.00.00.12.03.00.00.00.00.00.00.00.00
QoS profile:
  Reliability: RELIABLE
  History (Depth): UNKNOWN
  Durability: VOLATILE
  Lifespan: Infinite
  Deadline: Infinite
  Liveliness: AUTOMATIC
  Liveliness lease duration: Infinite

Subscription count: 2

Node name: ekf_filter_node
Node namespace: /
Topic type: nav_msgs/msg/Odometry
Endpoint type: SUBSCRIPTION
GID: 01.0f.e5.f8.96.16.f5.67.00.00.00.00.00.00.1f.04.00.00.00.00.00.00.00.00
QoS profile:
  Reliability: BEST_EFFORT
  History (Depth): UNKNOWN
  Durability: VOLATILE
  Lifespan: Infinite
  Deadline: Infinite
  Liveliness: AUTOMATIC
  Liveliness lease duration: Infinite

Node name: rviz
Node namespace: /
Topic type: nav_msgs/msg/Odometry
Endpoint type: SUBSCRIPTION
GID: 01.0f.e5.f8.e6.19.53.89.00.00.00.00.00.00.1e.04.00.00.00.00.00.00.00.00
QoS profile:
  Reliability: RELIABLE
  History (Depth): UNKNOWN
  Durability: VOLATILE
  Lifespan: Infinite
  Deadline: Infinite
  Liveliness: AUTOMATIC
  Liveliness lease duration: Infinite

== /imu/data ==
Type: sensor_msgs/msg/Imu

Publisher count: 1

Node name: g354_imu_node
Node namespace: /
Topic type: sensor_msgs/msg/Imu
Endpoint type: PUBLISHER
GID: 01.0f.e5.f8.b5.15.7c.3b.00.00.00.00.00.00.11.03.00.00.00.00.00.00.00.00
QoS profile:
  Reliability: RELIABLE
  History (Depth): UNKNOWN
  Durability: VOLATILE
  Lifespan: Infinite
  Deadline: Infinite
  Liveliness: AUTOMATIC
  Liveliness lease duration: Infinite

Subscription count: 2

Node name: ekf_filter_node
Node namespace: /
Topic type: sensor_msgs/msg/Imu
Endpoint type: SUBSCRIPTION
GID: 01.0f.e5.f8.96.16.f5.67.00.00.00.00.00.00.20.04.00.00.00.00.00.00.00.00
QoS profile:
  Reliability: BEST_EFFORT
  History (Depth): UNKNOWN
  Durability: VOLATILE
  Lifespan: Infinite
  Deadline: Infinite
  Liveliness: AUTOMATIC
  Liveliness lease duration: Infinite

Node name: rviz
Node namespace: /
Topic type: sensor_msgs/msg/Imu
Endpoint type: SUBSCRIPTION
GID: 01.0f.e5.f8.e6.19.53.89.00.00.00.00.00.00.1b.04.00.00.00.00.00.00.00.00
QoS profile:
  Reliability: RELIABLE
  History (Depth): UNKNOWN
  Durability: VOLATILE
  Lifespan: Infinite
  Deadline: Infinite
  Liveliness: AUTOMATIC
  Liveliness lease duration: Infinite

== /odometry/filtered ==
Type: nav_msgs/msg/Odometry

Publisher count: 1

Node name: ekf_filter_node
Node namespace: /
Topic type: nav_msgs/msg/Odometry
Endpoint type: PUBLISHER
GID: 01.0f.e5.f8.96.16.f5.67.00.00.00.00.00.00.21.03.00.00.00.00.00.00.00.00
QoS profile:
  Reliability: RELIABLE
  History (Depth): UNKNOWN
  Durability: VOLATILE
  Lifespan: Infinite
  Deadline: Infinite
  Liveliness: AUTOMATIC
  Liveliness lease duration: Infinite

Subscription count: 1

Node name: rviz
Node namespace: /
Topic type: nav_msgs/msg/Odometry
Endpoint type: SUBSCRIPTION
GID: 01.0f.e5.f8.e6.19.53.89.00.00.00.00.00.00.1f.04.00.00.00.00.00.00.00.00
QoS profile:
  Reliability: RELIABLE
  History (Depth): UNKNOWN
  Durability: VOLATILE
  Lifespan: Infinite
  Deadline: Infinite
  Liveliness: AUTOMATIC
  Liveliness lease duration: Infinite

== /cmd_vel ==
Type: geometry_msgs/msg/Twist

Publisher count: 1

Node name: r2_teleop_keyboard
Node namespace: /
Topic type: geometry_msgs/msg/Twist
Endpoint type: PUBLISHER
GID: 01.0f.e5.f8.33.17.4d.fc.00.00.00.00.00.00.11.03.00.00.00.00.00.00.00.00
QoS profile:
  Reliability: RELIABLE
  History (Depth): UNKNOWN
  Durability: VOLATILE
  Lifespan: Infinite
  Deadline: Infinite
  Liveliness: AUTOMATIC
  Liveliness lease duration: Infinite

Subscription count: 1

Node name: r2_chassis_node
Node namespace: /
Topic type: geometry_msgs/msg/Twist
Endpoint type: SUBSCRIPTION
GID: 01.0f.e5.f8.af.14.e9.98.00.00.00.00.00.00.11.04.00.00.00.00.00.00.00.00
QoS profile:
  Reliability: RELIABLE
  History (Depth): UNKNOWN
  Durability: VOLATILE
  Lifespan: Infinite
  Deadline: Infinite
  Liveliness: AUTOMATIC
  Liveliness lease duration: Infinite

lin@lin-Default-string:~$ 
lin@lin-Default-string:~$ ros2 run tf2_ros tf2_echo odom base_link
[INFO] [1786019680.871238830] [tf2_echo]: Waiting for transform odom ->  base_link: Invalid frame ID "odom" passed to canTransform argument target_frame - frame does not exist
At time 1786019681.444338412
- Translation: [0.000, 0.000, 0.000]
- Rotation: in Quaternion (xyzw) [0.030, 0.020, 0.000, 0.999]
- Rotation: in RPY (radian) [0.060, 0.040, 0.001]
- Rotation: in RPY (degree) [3.427, 2.284, 0.069]
- Matrix:
  0.999  0.001  0.040  0.000
  0.001  0.998 -0.060  0.000
 -0.040  0.060  0.997  0.000
  0.000  0.000  0.000  1.000
At time 1786019682.442171646
- Translation: [0.000, 0.000, 0.000]
- Rotation: in Quaternion (xyzw) [0.030, 0.020, 0.000, 0.999]
- Rotation: in RPY (radian) [0.060, 0.041, 0.001]
- Rotation: in RPY (degree) [3.426, 2.344, 0.073]
- Matrix:
  0.999  0.001  0.041  0.000
  0.001  0.998 -0.060  0.000
 -0.041  0.060  0.997  0.000
  0.000  0.000  0.000  1.000
At time 1786019683.446949588
- Translation: [0.000, 0.000, 0.000]
- Rotation: in Quaternion (xyzw) [0.030, 0.020, 0.000, 0.999]
- Rotation: in RPY (radian) [0.060, 0.041, 0.001]
- Rotation: in RPY (degree) [3.420, 2.334, 0.071]
- Matrix:
  0.999  0.001  0.041  0.000
  0.001  0.998 -0.060  0.000
 -0.041  0.060  0.997  0.000
  0.000  0.000  0.000  1.000
At time 1786019684.441685475
- Translation: [0.000, 0.000, 0.000]
- Rotation: in Quaternion (xyzw) [0.030, 0.021, -0.000, 0.999]
- Rotation: in RPY (radian) [0.060, 0.041, 0.001]
- Rotation: in RPY (degree) [3.426, 2.365, 0.068]
- Matrix:
  0.999  0.001  0.041  0.000
  0.001  0.998 -0.060  0.000
 -0.041  0.060  0.997  0.000
  0.000  0.000  0.000  1.000
At time 1786019685.446581221
- Translation: [0.000, 0.000, 0.000]
- Rotation: in Quaternion (xyzw) [0.030, 0.020, 0.000, 0.999]
- Rotation: in RPY (radian) [0.060, 0.041, 0.001]
- Rotation: in RPY (degree) [3.433, 2.338, 0.071]
- Matrix:
  0.999  0.001  0.041  0.000
  0.001  0.998 -0.060  0.000
 -0.041  0.060  0.997  0.000
  0.000  0.000  0.000  1.000
^C[INFO] [1786019686.029174774] [rclcpp]: signal_handler(SIGINT/SIGTERM)
lin@lin-Default-string:~$ ros2 run tf2_ros tf2_echo base_link imu_link
[INFO] [1786019692.245081339] [tf2_echo]: Waiting for transform base_link ->  imu_link: Invalid frame ID "base_link" passed to canTransform argument target_frame - frame does not exist
At time 0.0
- Translation: [0.000, 0.000, 0.000]
- Rotation: in Quaternion (xyzw) [0.000, 0.000, 0.000, 1.000]
- Rotation: in RPY (radian) [0.000, -0.000, 0.000]
- Rotation: in RPY (degree) [0.000, -0.000, 0.000]
- Matrix:
  1.000  0.000  0.000  0.000
  0.000  1.000  0.000  0.000
  0.000  0.000  1.000  0.000
  0.000  0.000  0.000  1.000
At time 0.0
- Translation: [0.000, 0.000, 0.000]
- Rotation: in Quaternion (xyzw) [0.000, 0.000, 0.000, 1.000]
- Rotation: in RPY (radian) [0.000, -0.000, 0.000]
- Rotation: in RPY (degree) [0.000, -0.000, 0.000]
- Matrix:
  1.000  0.000  0.000  0.000
  0.000  1.000  0.000  0.000
  0.000  0.000  1.000  0.000
  0.000  0.000  0.000  1.000
At time 0.0
- Translation: [0.000, 0.000, 0.000]
- Rotation: in Quaternion (xyzw) [0.000, 0.000, 0.000, 1.000]
- Rotation: in RPY (radian) [0.000, -0.000, 0.000]
- Rotation: in RPY (degree) [0.000, -0.000, 0.000]
- Matrix:
  1.000  0.000  0.000  0.000
  0.000  1.000  0.000  0.000
  0.000  0.000  1.000  0.000
  0.000  0.000  0.000  1.000
^C[INFO] [1786019695.349122324] [rclcpp]: signal_handler(SIGINT/SIGTERM)
lin@lin-Default-string:~$ ros2 run tf2_ros tf2_echo base_link velodyne
[INFO] [1786019702.060621604] [tf2_echo]: Waiting for transform base_link ->  velodyne: Invalid frame ID "base_link" passed to canTransform argument target_frame - frame does not exist
At time 0.0
- Translation: [0.000, 0.000, 0.695]
- Rotation: in Quaternion (xyzw) [0.000, 0.000, 0.000, 1.000]
- Rotation: in RPY (radian) [0.000, -0.000, 0.000]
- Rotation: in RPY (degree) [0.000, -0.000, 0.000]
- Matrix:
  1.000  0.000  0.000  0.000
  0.000  1.000  0.000  0.000
  0.000  0.000  1.000  0.695
  0.000  0.000  0.000  1.000
At time 0.0
- Translation: [0.000, 0.000, 0.695]
- Rotation: in Quaternion (xyzw) [0.000, 0.000, 0.000, 1.000]
- Rotation: in RPY (radian) [0.000, -0.000, 0.000]
- Rotation: in RPY (degree) [0.000, -0.000, 0.000]
- Matrix:
  1.000  0.000  0.000  0.000
  0.000  1.000  0.000  0.000
  0.000  0.000  1.000  0.695
  0.000  0.000  0.000  1.000
At time 0.0
- Translation: [0.000, 0.000, 0.695]
- Rotation: in Quaternion (xyzw) [0.000, 0.000, 0.000, 1.000]
- Rotation: in RPY (radian) [0.000, -0.000, 0.000]
- Rotation: in RPY (degree) [0.000, -0.000, 0.000]
- Matrix:
  1.000  0.000  0.000  0.000
  0.000  1.000  0.000  0.000
  0.000  0.000  1.000  0.695
  0.000  0.000  0.000  1.000
^C[INFO] [1786019705.633590194] [rclcpp]: signal_handler(SIGINT/SIGTERM)
lin@lin-Default-string:~$ ros2 run tf2_ros tf2_echo odom_lidar velodyne
[INFO] [1786019720.117239520] [tf2_echo]: Waiting for transform odom_lidar ->  velodyne: Invalid frame ID "odom_lidar" passed to canTransform argument target_frame - frame does not exist
At time 1786019720.978271744
- Translation: [0.000, 0.001, -0.000]
- Rotation: in Quaternion (xyzw) [0.000, 0.000, 0.000, 1.000]
- Rotation: in RPY (radian) [0.000, 0.000, 0.000]
- Rotation: in RPY (degree) [0.001, 0.001, 0.007]
- Matrix:
  1.000 -0.000  0.000  0.000
  0.000  1.000 -0.000  0.001
 -0.000  0.000  1.000 -0.000
  0.000  0.000  0.000  1.000
At time 1786019721.986870784
- Translation: [0.001, 0.000, 0.000]
- Rotation: in Quaternion (xyzw) [0.000, 0.000, 0.000, 1.000]
- Rotation: in RPY (radian) [0.000, 0.000, 0.000]
- Rotation: in RPY (degree) [0.001, 0.002, 0.011]
- Matrix:
  1.000 -0.000  0.000  0.001
  0.000  1.000 -0.000  0.000
 -0.000  0.000  1.000  0.000
  0.000  0.000  0.000  1.000
At time 1786019722.995748864
- Translation: [0.002, -0.001, 0.000]
- Rotation: in Quaternion (xyzw) [-0.000, -0.000, 0.001, 1.000]
- Rotation: in RPY (radian) [-0.000, -0.000, 0.001]
- Rotation: in RPY (degree) [-0.002, -0.001, 0.058]
- Matrix:
  1.000 -0.001 -0.000  0.002
  0.001  1.000  0.000 -0.001
  0.000 -0.000  1.000  0.000
  0.000  0.000  0.000  1.000
At time 1786019724.4410368
- Translation: [0.000, 0.001, 0.000]
- Rotation: in Quaternion (xyzw) [0.000, 0.000, 0.000, 1.000]
- Rotation: in RPY (radian) [0.000, 0.000, 0.000]
- Rotation: in RPY (degree) [0.001, 0.002, 0.008]
- Matrix:
  1.000 -0.000  0.000  0.000
  0.000  1.000 -0.000  0.001
 -0.000  0.000  1.000  0.000
  0.000  0.000  0.000  1.000
^C[INFO] [1786019724.409450863] [rclcpp]: signal_handler(SIGINT/SIGTERM)
lin@lin-Default-string:~$ 


lin@lin-Default-string:~$ ros2 topic hz /imu/data /odom_wheels /odometry/filtered /velodyne_points /kiss/odometry
usage: ros2 [-h] [--use-python-default-buffering]
            Call `ros2 <command> -h` for more
            detailed usage. ...
ros2: error: unrecognized arguments: /odom_wheels /odometry/filtered /velodyne_points /kiss/odometry
lin@lin-Default-string:~$ 