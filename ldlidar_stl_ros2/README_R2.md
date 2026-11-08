# ldlidar_stl_ros2 · R2 Vendor 说明

> 本目录是上游 LDROBOT 驱动的 **vendor 副本**，用于 R2-OLD S1 单 LD06 链路，随 `r2_integration` 一起进 GitHub。
> 上游源码不保留 `.git`；上游更新需手动 diff/合并，不要在本目录内 `git pull`。

## 来源

- 上游仓库：<https://github.com/ldrobotSensorTeam/ldlidar_stl_ros2>
- 上游 commit：`bf668a89baf722a787dadc442860dcbf33a82f5a`（2023-05-08）
- 包版本：`3.0.0`
- License：MIT（见 [LICENSE](LICENSE)）

## 本地改动

- `launch/ld06.launch.py`：**参数化重写（2026-11-06，R2 双雷达）**——新增 9 个 `DeclareLaunchArgument`：
  `node_name` / `topic_name` / `frame_id` / `port_name` / `port_baudrate` / `z` / `yaw` / `pitch` / `roll`；
  **2026-11-08 再补 `x` / `y`（共 11 个）**——平移原本写死 `'0','0'`，实车安装几何回填后必须可传；
  静态 TF 节点名随 `frame_id` 派生（`base_link_to_<frame_id>_ld06`）；`port_baudrate` 用
  `ParameterValue(..., value_type=int)` 显式转 int。**默认端口改为 `/dev/r2_ld06_a`**（udev 符号链接；
  上游默认 CP2102 套件的 `/dev/ttyUSB0`，R2 首版曾改 `/dev/ttyACM0`）。
- 其余文件未改。

**默认参数**：`node_name=LD06`、`topic_name=scan`、`frame_id=base_laser`、`port_name=/dev/r2_ld06_a`、
`port_baudrate=230400`；静态 TF `x=0.275`、`y=0.29`、`z=0.04`、`yaw=-1.5708`、`pitch/roll=0.0`
（2026-11-08 实车实测，见 [sensor-mount §6.1](../doc/phase0/sensor-mount.md)）；驱动参数 `product_name=LDLiDAR_LD06`、
`laser_scan_dir=True`（ROS 逆时针）保持不变。

**双实例启动**（2026-11-06 VM 验收用）：

```bash
# A（默认端口 /dev/r2_ld06_a）
ros2 launch ldlidar_stl_ros2 ld06.launch.py \
  node_name:=ld06_a topic_name:=scan_a frame_id:=laser_a

# B（显式 udev 符号链接）
ros2 launch ldlidar_stl_ros2 ld06.launch.py \
  node_name:=ld06_b topic_name:=scan_b frame_id:=laser_b \
  port_name:=/dev/r2_ld06_b
```

完整验收记录（双实例 10Hz、udev 固定名、互扰初筛）见
[doc/old-car/ld06-dual-lidar.md](../doc/old-car/ld06-dual-lidar.md)。

**已知限制**：`src/demo.cpp` 主循环不调用 `rclcpp::spin*`，参数服务只创建不响应——
`ros2 param get/list/set` 会超时/报 `Exception while calling service`；参数在启动时已生效，
以启动日志（`<port_name>` 等行）为准。未打补丁（参数本就只读一次，`param set` 无法动态生效）。

## 显示配置说明（VM 首测 2026-11-06）

- 包内 `rviz2/ldlidar.rviz` 是上游保存的显示配置：`Fixed Frame: base_laser`、`Color Transformer: Intensity` + 彩虹着色（Min 22 / Max 245）、`Flat Squares` 3 px / 0.03 m，以及保存的 Orbit 相机 `Yaw≈3.1354`（约 179.6°）、`Pitch≈1.5698`、`Distance≈6.454`。
- 因此用 `rviz2 -d .../ldlidar.rviz` 启动时画面可能像「转了 180°/颜色变了」——这是**相机视角与着色配置**，不是 `/scan` 数据方向反转；TF 旋转为单位四元数，方向由安装朝向与 `laser_scan_dir` 决定。
- 首次跑通与冒烟记录见 [2026-11-06 LD06 VM 接入与冒烟](../doc/retrospect/2026-11-06_ld06_vm_bringup_smoke.md)。

## 使用与待办

- 构建：`colcon build --packages-select ldlidar_stl_ros2`
- launch 默认端口 `/dev/r2_ld06_a`，由 udev 按 J-Link serial 固定（VM 已建 `r2_ld06_a` / `r2_ld06_b`；N97 2026-11-06 已建四路 `r2_g354` / `r2_can` / `r2_ld06_a` / `r2_ld06_b`，避免与 G354/CAN 的 ACM 设备互换）。
- 构建告警：上游 `CMakeLists.txt` 的 `cmake_minimum_required(VERSION 3.5)` 在 CMake 3.22 下产生弃用警告（stderr），**非错误**；保持 vendor 原样，未来 CMake 4 报错再评估改为 `3.10`。
- 上游 `scripts/ldlidar.rules` 仅匹配 CP210x 的 `ttyUSB*`，不适用于 J-Link；R2 已按 serial 另建规则（`MODE="0666"`、`GROUP="dialout"`，见 [执行计划 P3](../doc/old-car/ld06-dual-lidar.md)），N97 侧待补。
- ~~静态 TF `base_link→base_laser` 的 `z=0.18` 是占位值，实车必须按安装高度重标。~~
  ✅ **已完成（2026-11-08，G10）**：x/y/z/yaw 全部按实车量测回填，见 [sensor-mount §6.1](../doc/phase0/sensor-mount.md)；
  yaw 由手册 0° 定义 + 实车 △ 朝向推导，**已于 2026-11-08 实物复核通过**（350mm 箱 @≈1m：箱面倾角 −2.1°、
  中心 +94°；注意 +90° 仅对"雷达光心正前方"成立，车体中线目标读 ≈73°）。
  **角度约定**（手册原始角顺时针 ↔ `/scan` 发布角逆时针、`laser_scan_dir` 语义、其他安装朝向与
  错误配置对照、crop 的原始角口径）详见 [sensor-mount §6.1.1](../doc/phase0/sensor-mount.md)。
- 原始外部工作区：`~/ldlidar_ros2_ws`（保留作参考，不随 r2 同步）。
