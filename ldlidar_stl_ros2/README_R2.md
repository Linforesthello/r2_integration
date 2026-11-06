# ldlidar_stl_ros2 · R2 Vendor 说明

> 本目录是上游 LDROBOT 驱动的 **vendor 副本**，用于 R2-OLD S1 单 LD06 链路，随 `r2_integration` 一起进 GitHub。
> 上游源码不保留 `.git`；上游更新需手动 diff/合并，不要在本目录内 `git pull`。

## 来源

- 上游仓库：<https://github.com/ldrobotSensorTeam/ldlidar_stl_ros2>
- 上游 commit：`bf668a89baf722a787dadc442860dcbf33a82f5a`（2023-05-08）
- 包版本：`3.0.0`
- License：MIT（见 [LICENSE](LICENSE)）

## 本地改动

- `launch/ld06.launch.py`：`port_name` 由 `/dev/ttyUSB0` 改为 `/dev/ttyACM0`（当前 VM 用 J-Link VCOM；上游默认是 CP2102 套件的 `ttyUSB0`）。
- 其余文件未改。

## 显示配置说明（VM 首测 2026-11-06）

- 包内 `rviz2/ldlidar.rviz` 是上游保存的显示配置：`Fixed Frame: base_laser`、`Color Transformer: Intensity` + 彩虹着色（Min 22 / Max 245）、`Flat Squares` 3 px / 0.03 m，以及保存的 Orbit 相机 `Yaw≈3.1354`（约 179.6°）、`Pitch≈1.5698`、`Distance≈6.454`。
- 因此用 `rviz2 -d .../ldlidar.rviz` 启动时画面可能像「转了 180°/颜色变了」——这是**相机视角与着色配置**，不是 `/scan` 数据方向反转；TF 旋转为单位四元数，方向由安装朝向与 `laser_scan_dir` 决定。
- 首次跑通与冒烟记录见 [2026-11-06 LD06 VM 接入与冒烟](../doc/retrospect/2026-11-06_ld06_vm_bringup_smoke.md)。

## 使用与待办

- 构建：`colcon build --packages-select ldlidar_stl_ros2`
- 当前 launch 仍硬编码 `/dev/ttyACM0`；**上 N97 前**应改为固定符号链接（如 `/dev/r2_ld06`）或另建 R2 项目 launch，避免与 G354 的 ACM 设备互换。
- 上游 `scripts/ldlidar.rules` 仅匹配 CP210x 的 `ttyUSB*`，不适用于 J-Link；R2 的 G354/LD06 固定名需另建 udev 规则（按 serial 区分）。
- 静态 TF `base_link→base_laser` 的 `z=0.18` 是占位值，实车必须按安装高度重标。
- 原始外部工作区：`~/ldlidar_ros2_ws`（保留作参考，不随 r2 同步）。
