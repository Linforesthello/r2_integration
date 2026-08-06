

## 第一次的静置
lin@lin-Default-string:~$ ros2 run tf2_ros tf2_echo odom base_link
[INFO] [1785847780.063458449] [tf2_echo]: Waiting for transform odom ->  base_link: Invalid frame ID "odom" passed to canTransform argument target_frame - frame does not exist
At time 1785847782.27970209
- Translation: [-0.130, -0.291, 0.272]
- Rotation: in Quaternion (xyzw) [0.031, 0.022, -0.000, 0.999]
- Rotation: in RPY (radian) [0.062, 0.043, 0.001]
- Rotation: in RPY (degree) [3.579, 2.466, 0.074]
- Matrix:
  0.999  0.001  0.043 -0.130
  0.001  0.998 -0.062 -0.291
 -0.043  0.062  0.997  0.272
  0.000  0.000  0.000  1.000
At time 1785847783.31726842
- Translation: [-0.130, -0.291, 0.272]
- Rotation: in Quaternion (xyzw) [0.031, 0.022, -0.000, 0.999]
- Rotation: in RPY (radian) [0.062, 0.043, 0.001]
- Rotation: in RPY (degree) [3.553, 2.486, 0.068]
- Matrix:
  0.999  0.002  0.043 -0.130
  0.001  0.998 -0.062 -0.291
 -0.043  0.062  0.997  0.272
  0.000  0.000  0.000  1.000
At time 1785847784.31704842
- Translation: [-0.130, -0.291, 0.272]
- Rotation: in Quaternion (xyzw) [0.031, 0.022, -0.000, 0.999]
- Rotation: in RPY (radian) [0.062, 0.043, 0.001]
- Rotation: in RPY (degree) [3.543, 2.476, 0.070]
- Matrix:
  0.999  0.001  0.043 -0.130
  0.001  0.998 -0.062 -0.291
 -0.043  0.062  0.997  0.272
  0.000  0.000  0.000  1.000
At time 1785847785.28223444






- Rotation: in RPY (radian) [0.062, 0.043, 0.001]
- Rotation: in RPY (degree) [3.549, 2.453, 0.071]
- Matrix:
  0.999  0.001  0.043 -0.130
  0.001  0.998 -0.062 -0.291
 -0.043  0.062  0.997  0.272
  0.000  0.000  0.000  1.000
At time 1785847922.28060559
- Translation: [-0.130, -0.291, 0.272]
- Rotation: in Quaternion (xyzw) [0.031, 0.022, -0.000, 0.999]
- Rotation: in RPY (radian) [0.062, 0.043, 0.001]
- Rotation: in RPY (degree) [3.567, 2.468, 0.073]
- Matrix:
  0.999  0.001  0.043 -0.130
  0.001  0.998 -0.062 -0.291
 -0.043  0.062  0.997  0.272
  0.000  0.000  0.000  1.000
At time 1785847923.28422893
- Translation: [-0.130, -0.291, 0.272]
- Rotation: in Quaternion (xyzw) [0.031, 0.022, -0.000, 0.999]
- Rotation: in RPY (radian) [0.062, 0.043, 0.001]
- Rotation: in RPY (degree) [3.544, 2.478, 0.069]
- Matrix:
  0.999  0.001  0.043 -0.130
  0.001  0.998 -0.062 -0.291
 -0.043  0.062  0.997  0.272
  0.000  0.000  0.000  1.000
^C[INFO] [1785847923.256677654] [rclcpp]: signal_handler(SIGINT/SIGTERM)
lin@lin-Default-string:~$ 



## 作废
lin@lin-Default-string:~$ ros2 topic echo /odometry/filtered --once --field pose.pose.position
x: -0.5594028772248906
y: -0.40426625353286766
z: 4.900458445371629
---
lin@lin-Default-string:~$ ros2 topic echo /odometry/filtered --once --field pose.pose.position
x: 1.9941051064526647
y: -2.4152493601324236
z: 24.179572800892846
---
lin@lin-Default-string:~$ ros2 topic echo /odom_wheels --once --field pose.pose.position
x: 1.9942455932419552
y: -2.41539100600197
z: 0.0
---
lin@lin-Default-string:~$ 

## 第二次的3m直线
lin@lin-Default-string:~$ ros2 topic echo /odometry/filtered --once --field pose.pose.position
x: 2.565059375767621
y: -4.189956919709462
z: 76.19367278851082
---
lin@lin-Default-string:~$ ros2 topic echo /odom_wheels --once --field pose.pose.position
x: 2.565059702385792
y: -4.189957274112781
z: 0.0
---
lin@lin-Default-string:~$ ros2 topic echo /odometry/filtered --once --field pose.pose.position
x: 4.637026923255944
y: -6.151763542506312
z: 89.35596305934695
---
lin@lin-Default-string:~$ ros2 topic echo /odom_wheels --once --field pose.pose.position
x: 4.637092230078136
y: -6.15182760782283
z: 0.0
---
lin@lin-Default-string:~$ 

lin@lin-Default-string:~$ ros2 bag record /odom_wheels /odometry/filtered /imu/data /cmd_vel -o ~/ekf_02_line
[INFO] [1785848808.580638416] [rosbag2_recorder]: Press SPACE for pausing/resuming
[INFO] [1785848808.582292563] [rosbag2_storage]: Opened database '/home/lin/ekf_02_line/ekf_02_line_0.db3' for READ_WRITE.
[INFO] [1785848808.583127701] [rosbag2_recorder]: Listening for topics...
[INFO] [1785848808.583169316] [rosbag2_recorder]: Event publisher thread: Starting
[INFO] [1785848808.583299990] [rosbag2_recorder]: Recording...
[INFO] [1785848809.587778628] [rosbag2_recorder]: Subscribed to topic '/imu/data'
[INFO] [1785848809.690361928] [rosbag2_recorder]: Subscribed to topic '/odom_wheels'
[INFO] [1785848809.994282078] [rosbag2_recorder]: Subscribed to topic '/cmd_vel'
[INFO] [1785848810.804409248] [rosbag2_recorder]: Subscribed to topic '/odometry/filtered'
[INFO] [1785848810.804583335] [rosbag2_recorder]: All requested topics are subscribed. Stopping discovery...
[INFO] [1785848887.663186436] [rosbag2_cpp]: Writing remaining messages from cache to the bag. It may take a while
[INFO] [1785848887.673615759] [rosbag2_recorder]: Event publisher thread: Exiting
[INFO] [1785848887.674388438] [rosbag2_recorder]: Recording stopped
lin@lin-Default-string:~$ ros2 bag info ~/ekf_02_line
 
Files:             ekf_02_line_0.db3
Bag size:          8.6 MiB
Storage id:        sqlite3
Duration:          78.059139796s
Start:             Aug  4 2026 21:06:49.594267508 (1785848809.594267508)
End:               Aug  4 2026 21:08:07.653407304 (1785848887.653407304)
Messages:          15668
Topic information: Topic: /cmd_vel | Type: geometry_msgs/msg/Twist | Count: 777 | Serialization Format: cdr
                   Topic: /odometry/filtered | Type: nav_msgs/msg/Odometry | Count: 3843 | Serialization Format: cdr
                   Topic: /odom_wheels | Type: nav_msgs/msg/Odometry | Count: 3892 | Serialization Format: cdr
                   Topic: /imu/data | Type: sensor_msgs/msg/Imu | Count: 7156 | Serialization Format: cdr

lin@lin-Default-string:~$ 


## 第三次

这次走了直线3m
lin@lin-Default-string:~$ ros2 topic echo /odometry/filtered --once --field pose.pose.position
x: 0.0
y: 0.0
z: 0.0
---
lin@lin-Default-string:~$ ros2 topic echo /odom_wheels --once --field pose.pose.position
x: 0.0
y: 0.0
z: 0.0
---
lin@lin-Default-string:~$ ros2 topic echo /odometry/filtered --once --field pose.pose.position
x: 3.0380963722319914
y: 0.08360033488187044
z: -1.9107944640305936
---
lin@lin-Default-string:~$ ros2 topic echo /odom_wheels --once --field pose.pose.position
x: 3.0380883260793916
y: 0.08360831448329172
z: 0.0
---
lin@lin-Default-string:~$ 
