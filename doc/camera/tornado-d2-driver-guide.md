# Tornado D2 兼容性测试与驱动手册

> 日期：2026-11-17（初版）
> 适用：Tornado D2（深度 USB `2bc5:060d`）+ Ubuntu 22.04 + ROS2 Humble + x86_64；Astra Pro 的驱动与实机记录见 [astra-pro-driver-guide.md](astra-pro-driver-guide.md)
> 定位：D2 兼容性工程的**测试记录 + 使用手册 + 迁移清单**，覆盖两套环境、可执行文件、运行接口、启动与验收。
> 依据：`ros2_ws/src/ros2_astra_camera`、`ros2_ws/src/d2_toy_mapper` 源码逐项核对；2026-11-17 实机终端记录（原始输出本地留档于 `doc/raw_data/raw_tornado_d2_*`，不入 git）。
> 关联：[astra_ws 迁移部署手册](astra-ws-migration-guide.md)（同机 Astra 工作区的换机方法）｜[厂商环境搭建记录](1、环境搭建.md)｜[ROS2 操作规范](../ros2-ops.md)｜[QoS/DDS 问题手册](../ros2-qos-dds.md)
> 状态：深度、点云、低分辨率、QoS 已实测；彩色多流、彩色点云、玩具建图有文档记录，本轮未复测；**迁移到其他机器/架构未实测**。
> 可信度：✅ 本次实机或静态核实　⚠️ 源码/既有文档依据、本次未复测　❓ 待核实

---

## 一、结论摘要

1. 本项目是 **Tornado D2 在 Linux/x86_64 + ROS2 Humble 下的兼容性工程**：用打过 VID/PID 补丁的官方 Orbbec 驱动打开 D2，并提供最小 SDK、ROS2 点云、彩色点云和玩具级 ICP 建图。
2. **两套环境不要混用**：
   - **默认环境** `~/astra_ws`：官方 `astra_camera`，Debug 构建、未打补丁的 `liborbbec.so`、640×480 默认 ini → 用于 **Astra Pro**。
   - **项目环境** `~/Desktop/tornado_d2_driver`：补丁版 `liborbbec.so`、D2 专用 `orbbec.ini`、Release 构建 → 用于 **Tornado D2**。
3. D2 启动入口（脚本按自身位置定位工作区，项目目录可整体搬移）：

   ```bash
   cd ~/Desktop/tornado_d2_driver
   bash ./run_ros2_depth.sh
   ```

4. 点云卡顿的根因是 **1280×800 点云 16.38 MB/帧 + 默认 Reliable QoS + RViz 订阅**；低分辨率 + Best Effort 后用户确认“点云明显快一些”。性能问题本轮闭环，不再继续压分辨率。
5. 所有 `.sh` 脚本当前没有执行位（`-rw-rw-r--`），统一用 `bash <脚本>`；直接 `./xxx.sh` 会报“权限不够”。
6. **迁移的最小正确单位是源码 + 补丁文件 + 脚本 + 配置**；`build/`、`install/`、`local/`、`sdk/build/` 都是本机架构产物，目标机必须重建。

---

## 二、硬件与设备

### 2.1 两个 USB 端点

| 功能 | VID:PID | 总线 | 说明 |
|:---|:---|:---|:---|
| 深度 | `2bc5:060d` | USB3（5000M）⚠️ | vendor-specific bulk interface；D2 的深度/IR 走这里 |
| 彩色 | `2bc5:0505` | USB2（480M）⚠️ | 独立 UVC 彩色相机；默认关闭，`run_multistream.sh` 才启用 |

> 彩色不是深度设备的一部分，深度/彩色同步只能是软件近似同步。
> **Astra Pro 是另一套拓扑**：`2bc5:0403`（深度/IR）+ `2bc5:0501`（彩色），两个端点均为 USB 2.0（`bcdUSB=2.00`、480M）；不要拿 D2 的 USB3 判据检查 Astra Pro。

### 2.2 深度规格

| 项目 | 值 | 备注 |
|:---|:---|:---|
| 请求模式 | `800×1280@30` | `orbbec.ini` 的 `[Depth] Resolution=-26` |
| ROS 实际发布 | `1280×800@30`，`16UC1`（毫米） | 项目未做 90° 旋转；下游以消息里的 `width/height/step` 为准 |
| 低分辨率模式 | 请求 `400×640@30` → ROS 实际 `640×400` | 服务返回写法是 `400x640@30`（宽×高） |
| 深度范围 | 约 `0.3–1.3 m` | 项目按此范围做滤波与显示 |
| FOV | `67.63° × 53.34°` | SDK 30 帧冒烟测试记录 |
| 深度单位 | 1 mm | `16UC1`，不是浮点米 |

### 2.3 udev 权限

包内规则 `ros2_ws/src/ros2_astra_camera/astra_camera/scripts/56-orbbec-usb.rules` 包含：

```text
2bc5:060d  -> astra pro plus
2bc5:060e  -> astradepth
2bc5:0401  -> astra
2bc5:0403  -> astra_pro
2bc5:0501  -> astrauvc
```

安装一次即可，不应每次 `sudo` 运行 ROS 节点：

```bash
sudo install -m 0644 \
  ~/Desktop/tornado_d2_driver/ros2_ws/src/ros2_astra_camera/astra_camera/scripts/56-orbbec-usb.rules \
  /etc/udev/rules.d/56-orbbec-usb.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=usb --attr-match=idVendor=2bc5
```

> ⚠️ 换机时先检查目标机是否已有该规则及哈希，不要无条件覆盖；规则内容与 Astra Pro 共用，D2 只是多了 `060d` 一行。

---

## 三、两套环境（最重要）

### 3.1 对比表

| 维度 | 默认环境 `~/astra_ws` | 项目环境 `~/Desktop/tornado_d2_driver` |
|:---|:---|:---|
| 用途 | 驱动 **Astra Pro**（官方默认） | 驱动 **Tornado D2** |
| 源码 | 官方 `ros2_astra_camera` | 同一官方仓库 + 本地补丁 |
| 构建类型 | **Debug**（`CMakeLists.txt` 强制） | **Release**（改为“未指定时才 Release”） |
| `liborbbec.so` | 官方未打补丁（SHA-256 `2ea32306...`）✅ | 补丁版（SHA-256 `7fa4586e...`，`060e → 060d`）✅ |
| `orbbec.ini` | 640×480 默认（`Resolution=1`）⚠️ | D2 专用（`Resolution=-26 / FPS=30 / InputFormat=2`）✅ |
| 启动文件 | `astra_pro.launch.xml` | `astro_pro_plus.launch.xml`（少一个 a，不是笔误） |
| 默认深度 | 640×480@30 | 请求 800×1280@30 → ROS 1280×800@30 |
| 默认彩色 | UVC `0x0501` 640×480@30，开启 | 默认关闭；`run_multistream.sh` 用 UVC `0x0505` 1024×768@30 |
| 点云 | `/camera/depth/points`；默认还开彩色点云 | `/camera/depth/points`；彩色点云默认关 |
| 能否驱动对方 | **不能**驱动 D2（白名单无 `060d`） | 不建议驱动 Astra Pro（D2 专用 ini 模式不匹配，未验证） |

> Astra Pro 的启动、四路视图、RGB-D 融合、内参与 USB 掉线崩溃，见 [astra-pro-driver-guide.md](astra-pro-driver-guide.md)；本文不重复。

### 3.2 当前 shell 属于哪套环境

`astra_camera` 同时存在于 `~/astra_ws` 和项目 `ros2_ws/install`。后 source 的工作区排在 `AMENT_PREFIX_PATH` / `LD_LIBRARY_PATH` 前面，因此**以当前 shell 的 `ros2 pkg prefix` 为准**：

```bash
ros2 pkg prefix astra_camera
echo "${OPENNI2_REDIST:-<unset>}"
printenv LD_LIBRARY_PATH | tr ':' '\n' | grep -E 'astra_ws|tornado_d2_driver' | head
```

| 输出 | 含义 |
|:---|:---|
| 指向 `~/astra_ws/install/astra_camera` | 默认环境（Astra Pro） |
| 指向项目 `ros2_ws/install/astra_camera` | 项目环境（D2） |

`run_ros2_depth.sh` 内部会再 source 一次项目 install，所以**脚本本身不依赖当前 shell 的包顺序**；手工执行 `ros2 launch` 时才会受顺序影响。

### 3.3 干净 shell 配方

排障或切换设备时，用干净 shell 最稳：

```bash
# D2 项目环境
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH LD_LIBRARY_PATH PYTHONPATH
source /opt/ros/humble/setup.bash
source ~/Desktop/tornado_d2_driver/ros2_ws/install/setup.bash
export LD_LIBRARY_PATH="$HOME/Desktop/tornado_d2_driver/local/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export OPENNI2_REDIST="$HOME/Desktop/tornado_d2_driver/ros2_ws/install/astra_camera/lib"
export OPENNI2_DRIVERS_PATH="$OPENNI2_REDIST/OpenNI2/Drivers"
```

```bash
# 默认环境（Astra Pro）
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH LD_LIBRARY_PATH PYTHONPATH
source /opt/ros/humble/setup.bash
source ~/astra_ws/install/setup.bash
```

> 迁移到其他目录时，把 `~/Desktop/tornado_d2_driver` 换成目标路径即可；**不要**把本机 `.bashrc` 整份拷过去（还含其他工作区路径）。

---

## 四、项目构成与可执行文件

### 4.1 关键路径（只列相关项）

| 路径 | 作用 |
|:---|:---|
| `ros2_ws/src/ros2_astra_camera/` | 官方驱动仓库的嵌套 git 副本（`.git` 在这一层） |
| `ros2_ws/src/d2_toy_mapper/` | 玩具 ICP + 彩色点云节点 |
| `ros2_ws/src/d2_camera/` | 空占位（无 `package.xml`），不产生可执行文件 |
| `ros2_ws/install/` | 构建产物；launch/参数从这里加载 |
| `local/` | 项目内 libuvc 0.0.7 安装前缀 |
| `sdk/` | 最小 SDK（`build/` 产物 + `runtime/` OpenNI2） |
| `config/` | `cloud_tuning.yaml`、`toy_mapping.rviz`、`colored_cloud.rviz` |
| `tools/` | `depth_colormap.py` |
| `*.sh` | 启动与调参脚本（见 4.3） |
| `*_bak_20261117_163813/` | 重建前的备份，不要 source / 运行 |

> ⚠️ `ros2_ws/src/ros2_astra_camera/.git` 是嵌套仓库；在外层项目做 git 操作前先确认层级，不要用破坏性命令。

### 4.2 编译产物（6 个）

| # | 路径 | 类型 | 作用 |
|:--|:---|:---|:---|
| 1 | `ros2_ws/install/astra_camera/lib/astra_camera/astra_camera_node` | ROS2 节点 | D2/Astra 驱动主节点 |
| 2 | `ros2_ws/install/astra_camera/lib/astra_camera/list_devices_node` | 命令行工具（非 ROS 节点） | 枚举 OpenNI2 设备并打印 URI/序列号 |
| 3 | `ros2_ws/install/astra_camera/lib/astra_camera/clean_shm_node` | 命令行工具（非 ROS 节点） | 清理多设备模式遗留的信号量/共享内存 |
| 4 | `ros2_ws/install/d2_toy_mapper/lib/d2_toy_mapper/toy_mapper_node` | ROS2 节点 | 玩具 ICP 累积点云 |
| 5 | `ros2_ws/install/d2_toy_mapper/lib/d2_toy_mapper/calibrated_colored_cloud_node` | ROS2 节点 | 用 D2 机内参数生成 RGB 点云 |
| 6 | `sdk/build/d2_capture` | 命令行工具 | 不依赖 ROS 的 30 帧深度冒烟测试 |

**节点要点**：

- `astra_camera_node`：最终节点名 `/camera/camera`；深度设备按 OpenNI2 枚举 + `serial_number` 选择，**`vendor_id`/`product_id` 在深度路径中未被读取**；彩色 UVC 才使用 `uvc_*`。
- `toy_mapper_node`：节点 `/d2_toy_mapper`；订阅 `/camera/depth/points`（SensorDataQoS），发布 `/toy_cloud_map` 与 TF `toy_map -> <点云 frame>`；参数 `frame_skip=6`、`voxel_size=0.035`、`max_correspondence=0.12`、`max_fitness=0.015`；z 滤波 `0.30–1.30 m`，过滤后少于 60 点不建图。
- `calibrated_colored_cloud_node`：节点 `/d2_calibrated_colored_cloud`；订阅深度/彩色图与 `camera_info`（SensorDataQoS，ApproximateTime），每 500 ms 调 `/camera/get_camera_params`，发布 `/camera/depth/color/points_calibrated`（`x/y/z/rgb`，`point_step=16`）。
- `list_devices_node` / `clean_shm_node`：**不是 ROS 节点**，是直接调用 OpenNI2 的 CLI；运行前需要 `OPENNI2_REDIST` / `OPENNI2_DRIVERS_PATH`。
- `d2_capture`：静态链接 `libtornado_d2.a`，通过 RPATH + `sdk/run_capture.sh` 找 `sdk/runtime`；输出设备 URI、`depth=WxH`、`received=30/30`、时间戳跨度、FOV。

### 4.3 Shell 脚本（12 个）

| # | 脚本 | 起相机 | 作用 / 关键参数 |
|:--|:---|:---:|:---|
| 1 | `run_ros2_depth.sh` | ✅ | **D2 主入口**：source ROS + 项目 install，设 `local/lib`、`OPENNI2_REDIST`，`ros2 launch astra_camera astro_pro_plus.launch.xml "$@"` |
| 2 | `run_multistream.sh` | ✅ | 深度 + IR 1280×800@5 + UVC 彩色 `0x0505` 1024×768@30；`flip_color:=true`、彩色点云关、软同步关 |
| 3 | `run_colored_cloud.sh` | ✅ | 起 `run_multistream.sh` + `calibrated_colored_cloud_node --params-file config/cloud_tuning.yaml` + RViz |
| 4 | `run_toy_mapping.sh` | ✅ | **自己起相机**（默认 1280×800）+ toy mapper + RViz；相机已在跑时不要用 |
| 5 | `run_demo_all.sh` | ✅ | 多流 + toy mapper + `depth_colormap.py` + `rqt_image_view` + RViz |
| 6 | `run_depth_to_scan.sh` | ❌ | `depthimage_to_laserscan_node`：`/camera/depth/image_raw` → `/scan`，`output_frame=camera_depth_frame`，`scan_height=20`，`range 0.3–1.3 m` |
| 7 | `run_depth_colormap.sh` | ❌ | 运行 `tools/depth_colormap.py`，红近蓝远伪彩色窗口 |
| 8 | `run_sdk_depth_test.sh` | ❌ | 单行 `sdk/run_capture.sh` |
| 9 | `sdk/run_capture.sh` | ❌ | 设 SDK 的 `OPENNI2_REDIST`/`LD_LIBRARY_PATH`，执行 `d2_capture` |
| 10 | `set_cloud_offset.sh X Y` | ❌ | 改 `cloud_tuning.yaml` 全局像素偏移；节点在跑时同时 `ros2 param set` |
| 11 | `set_cloud_stride.sh N` | ❌ | 改 `point_stride`（1/2）；节点在跑时同时 `ros2 param set` |
| 12 | `set_cloud_alignment.sh 近距m 近X 近Y 远距m 远X 远Y X缩放 Y缩放` | ❌ | 改近/远偏移与投影缩放；节点在跑时同时 `ros2 param set` |

> ⚠️ 12 个脚本当前都是 `-rw-rw-r--`，没有执行位。用 `bash ./脚本.sh`；如需直接执行，先 `chmod +x *.sh`。

### 4.4 Python 工具与库

| 文件 | 说明 |
|:---|:---|
| `tools/depth_colormap.py` | 节点 `d2_depth_colour_viewer`；订阅 `/camera/depth/image_raw`，TURBO 伪彩色；`min_depth_mm=300`、`max_depth_mm=1300`、`display_decimation=2` |
| `ros2_ws/install/astra_camera/lib/libastra_camera.so` | 驱动核心库 |
| `ros2_ws/install/astra_camera/lib/libOpenNI2.so` | OpenNI2 2.3.0 build 85 |
| `ros2_ws/install/astra_camera/lib/OpenNI2/Drivers/liborbbec.so` | 补丁版 Orbbec 驱动（含 `060d`） |
| `ros2_ws/install/astra_camera/lib/OpenNI2/Drivers/libOniFile.so` | `.oni` 回放驱动；实时相机不用 |
| `local/lib/libuvc.so.0.0.7` | 项目内编译的 libuvc |
| `sdk/build/libtornado_d2.a` | 最小 SDK 静态库（不是可执行文件） |

---

## 五、运行接口

### 5.1 话题（D2 默认 launch）

| 话题 | 类型 | QoS | 说明 |
|:---|:---|:---|:---|
| `/camera/depth/image_raw` | `sensor_msgs/Image` | `default`（Reliable） | `16UC1` 毫米；1280×800@30 |
| `/camera/depth/camera_info` | `sensor_msgs/CameraInfo` | `default` | 1280×800 |
| `/camera/depth/points` | `sensor_msgs/PointCloud2` | `default`（Reliable）；可设 `sensor_data` | 1,024,000 点，16 B/点 |
| `/camera/ir/image_raw` | `sensor_msgs/Image` | `default` | 仅在 `enable_ir:=true` |
| `/camera/color/image_raw` | `sensor_msgs/Image` | `default` | 仅在 UVC 彩色开启 |
| `/camera/depth/color/points` | `sensor_msgs/PointCloud2` | `default` | `enable_colored_point_cloud:=true`；D2 launch remap 到 `/camera/depth_registered/points` |
| `/camera/depth/color/points_calibrated` | `sensor_msgs/PointCloud2` | SensorData | 自定义节点输出，`x/y/z/rgb` |
| `/camera/extrinsic/depth_to_color` | `astra_camera_msgs/Extrinsics` | Transient Local | `enable_publish_extrinsic:=true` |
| `/toy_cloud_map` | `sensor_msgs/PointCloud2` | Reliable，depth 1 | 玩具 ICP 地图 |
| `/scan` | `sensor_msgs/LaserScan` | 默认 | `run_depth_to_scan.sh` 生成 |
| `/tf`、`/tf_static` | `tf2_msgs/TFMessage` | — | 见 5.4 |

### 5.2 服务（命名空间 `/camera`）

| 服务 | 类型 | 说明 |
|:---|:---|:---|
| `get_depth_supported_video_modes` | `GetString` | 返回 JSON 字符串数组，如 `["400x640@30","800x1280@5"]` |
| `get_depth_exposure` / `set_depth_exposure` | `GetInt32` / `SetInt32` | 深度曝光 |
| `get_depth_gain` / `set_depth_gain` | `GetInt32` / `SetInt32` | 深度增益 |
| `set_depth_auto_exposure` / `toggle_depth` / `set_depth_mirror` | `SetBool` | 自动曝光 / 开关流 / 镜像 |
| `get_camera_params` | `GetCameraParams` | 机内左右目内参、畸变、`r2l_r/r2l_t` |
| `get_camera_info` / `get_device_info` / `get_sdk_version` | 对应服务 | 相机信息 / 设备信息 / SDK 版本 |
| `set_fan_mode` / `set_laser_enable` / `set_ldp_enable` | `SetBool` | 设备相关；D2 上可能返回失败 |

> 彩色/IR 开启时，同名模式的 `get_<stream>_*` / `set_<stream>_*` 服务也会出现。

### 5.3 关键 launch 参数（`astro_pro_plus.launch.xml`）

| 参数 | 默认 | 说明 |
|:---|:---|:---|
| `camera_name` | `camera` | 命名空间/话题前缀 |
| `depth_registration` | `false` | 深度对齐到彩色；D2 默认关 |
| `serial_number` | `""` | 多设备时按序列号选设备 |
| `vendor_id` / `product_id` | `0x2bc5` / `0x060d` | ⚠️ 深度路径未读取，不用于选设备 |
| `enable_depth` | `true` | 深度流 |
| `depth_width` / `depth_height` / `depth_fps` | `800` / `1280` / `30` | 请求模式；实际发布可能变 1280×800 |
| `depth_qos` / `depth_camera_info_qos` | `default` | 图像/信息 QoS |
| `enable_point_cloud` | `true` | 生成 `/camera/depth/points` |
| `point_cloud_qos` | `default` | `default`=Reliable；`sensor_data`=Best Effort |
| `enable_ir` | `false` | IR 流 |
| `ir_width` / `ir_height` / `ir_fps` | `640` / `480` / `30` | `run_multistream.sh` 用 1280/800/5 |
| `enable_color` | `false` | 彩色流 |
| `color_width` / `color_height` / `color_fps` | `640` / `480` / `30` | 彩色请求 |
| `use_uvc_camera` | `false` | 用独立 UVC 彩色 |
| `uvc_vendor_id` / `uvc_product_id` | `0x2bc5` / `0x050f` | D2 彩色实际是 `0x0505`（`run_multistream.sh` 覆盖） |
| `uvc_camera_format` | `mjpeg` | UVC 格式 |
| `flip_color` / `flip_depth` / `flip_ir` | `false` | 水平镜像 |
| `enable_colored_point_cloud` | `false` | 为 true 会强制 `depth_registration=true` |
| `color_depth_synchronization` | `false` | OpenNI2 软同步 |
| `publish_tf` | `true` | 发布相机 TF |
| `tf_publish_rate` | `10.0` | 见 5.4 |
| `ir_info_uri` / `color_info_uri` | `""` | ⚠️ 节点实际读 `ir_info_url` / `color_info_url`；默认空所以无影响 |
| `depth_scale` | `1` | 深度缩放 |
| `enable_publish_extrinsic` | `false` | 发布深度→彩色外参 |

### 5.4 TF

D2 默认只开深度时：

```text
camera_link
  └── camera_depth_frame
        └── camera_depth_optical_frame
```

开彩色/IR 时额外有 `camera_color_frame`、`camera_color_optical_frame`、`camera_ir_frame`、`camera_ir_optical_frame`。

> ⚠️ 源码行为：`tf_publish_rate > 0`（默认 10）时，节点把同一组“静态”变换按 10 Hz 发到 `/tf`，不是只发一次 `/tf_static`；`tf_publish_rate:=0` 才走 `/tf_static`。录包时 `/tf` 必须录。
> 玩具建图额外发布 `toy_map -> camera_depth_optical_frame`（子 frame 取输入点云的 `header.frame_id`）。

---

## 六、启动与验证

### 6.1 前置检查

| 项 | 检查方法 | 期望 |
|:---|:---|:---|
| D2 已接 | `lsusb` | 出现 `2bc5:060d`（彩色可选 `2bc5:0505`） |
| USB3 | `lsusb -t` | 深度端点挂在 5000M 总线 |
| 权限 | 不以 `sudo` 运行也能打开 | udev 规则已安装 |
| ROS2 | `test -f /opt/ros/humble/setup.bash` | 存在 |
| 已构建 | `ls ros2_ws/install/astra_camera/lib/astra_camera/astra_camera_node` | 存在 |
| libuvc | `ls local/lib/libuvc.so.0.0.7` | 存在 |
| OpenNI2 | `ls ros2_ws/install/astra_camera/lib/libOpenNI2.so` | 存在 |
| 补丁驱动 | `sha256sum .../liborbbec.so` | 同版本同架构应为 `7fa4586e...` |
| D2 ini | `grep -A3 '\[Depth\]' .../orbbec.ini` | `Resolution=-26`、`FPS=30`、`InputFormat=2` |
| 环境变量 | `echo $OPENNI2_REDIST` | 指向项目 install 的 `lib` |

> 本表是 D2 的检查；Astra Pro 为 USB 2.0（480M），按 [astra-pro-driver-guide.md](astra-pro-driver-guide.md) 检查。

### 6.2 项目环境启动 D2

```bash
cd ~/Desktop/tornado_d2_driver

# 默认高分辨率：请求 800×1280 → ROS 1280×800，30 Hz
bash ./run_ros2_depth.sh

# 低分辨率 + Best Effort：性能优先（已验证更流畅）
bash ./run_ros2_depth.sh \
  depth_width:=400 depth_height:=640 \
  point_cloud_qos:=sensor_data
```

脚本内部等价于：

```bash
source /opt/ros/humble/setup.bash
source ~/Desktop/tornado_d2_driver/ros2_ws/install/setup.bash
export LD_LIBRARY_PATH="$HOME/Desktop/tornado_d2_driver/local/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export OPENNI2_REDIST="$HOME/Desktop/tornado_d2_driver/ros2_ws/install/astra_camera/lib"
export OPENNI2_DRIVERS_PATH="$OPENNI2_REDIST/OpenNI2/Drivers"
ros2 launch astra_camera astro_pro_plus.launch.xml "$@"
```

**验证**：

```bash
ros2 node list | grep -E '/camera/camera'
ros2 topic list | grep camera
ros2 topic hz /camera/depth/image_raw
ros2 topic echo /camera/depth/camera_info --once --field width     # 1280（低分辨率时 640）
ros2 topic echo /camera/depth/camera_info --once --field height    # 800（低分辨率时 400）
ros2 topic echo /camera/depth/points --once --qos-reliability best_effort --field width
```

### 6.3 默认环境启动 Astra Pro

新开终端（`.bashrc` 已 source `~/astra_ws`），先确认：

```bash
ros2 pkg prefix astra_camera
# 期望指向 ~/astra_ws/install/astra_camera
```

启动与验证见 [astra-pro-driver-guide.md §四](astra-pro-driver-guide.md)（推荐 `color_info_url:=""` 消除内参文件缺失 ERROR）。

### 6.4 SDK 冒烟（不经过 ROS）

```bash
cd ~/Desktop/tornado_d2_driver
bash ./run_sdk_depth_test.sh
# 或
bash sdk/run_capture.sh
```

期望输出包含：

```text
device=2bc5/060d@...
depth=1280x800
received=30/30
FOV=67.63° x 53.34°
```

---

## 七、构建与迁移部署

> 本节面向**换机/换目录**。源机事实来自 2026-11-17 本机；目标机全流程未实测（❓），按 7.7 验收。

### 7.1 拷什么、不拷什么

| 对象 | 拷贝 | 说明 |
|:---|:---:|:---|
| `ros2_ws/src/` | ✅ | 含 `ros2_astra_camera`（嵌套 git）、`d2_toy_mapper`、空占位 `d2_camera` |
| `sdk/` 源码与 `sdk/runtime/` | ✅/⚠️ | 源码必拷；`runtime` 是架构相关 OpenNI2，同架构可拷，跨架构需换匹配版本 |
| `config/`、`tools/`、`*.sh`、`docs/` | ✅ | 配置、工具、脚本、文档 |
| 补丁版 `liborbbec.so` + D2 `orbbec.ini` | ✅/⚠️ | 同架构 x86_64 可直接用；ARM64 必须换对应架构的库并重新打补丁 |
| `build/`、`install/`、`log/` | ❌ | 含源机绝对路径与 x86_64 产物，目标机重建 |
| `local/`、`libuvc_build/` | ❌ | 项目内 libuvc 构建产物，目标机重新编译 |
| `sdk/build/` | ❌ | 重新编译 |
| `*_bak_20261117_163813/` | ❌ | 旧备份 |
| 整份 `~/.bashrc` | ❌ | 含其他工作区路径；只保留目标机需要的那一行 |

> **迁移单位 = 源码快照**。若 `ros2_ws/src/ros2_astra_camera` 的嵌套仓有远端，优先 `git clone` + 应用本地改动；无远端则整目录打包（`git -C ... remote -v` 先确认）。
> 补丁文件位于 `ros2_ws/src/ros2_astra_camera/astra_camera/openni2_redist/x64/OpenNI2/Drivers/`（x86_64）；构建时安装到 `install/astra_camera/lib/OpenNI2/Drivers/`。换架构时该目录要换成对应架构的 `openni2_redist/<arch>/`。

### 7.2 依赖基线

| 依赖 | 用途 | 核对口径 |
|:---|:---|:---|
| ROS2 Humble | 基础 | ✅ `/opt/ros/humble` |
| OpenNI2 2.3.0 build 85 | 深度设备 | ✅ 包内 `libOpenNI2.so` |
| 补丁版 `liborbbec.so` | D2 枚举 | ✅ x86_64，哈希见 7.6 |
| libuvc 0.0.7 | UVC 彩色 | ✅ 项目内 `local/` |
| glog / OpenCV / Eigen3 / libusb-1.0 / nlohmann-json / libjpeg | `astra_camera` 构建 | ⚠️ 与 `~/astra_ws` 同源；迁移前用 `dpkg -l` 核对 |
| PCL | `d2_toy_mapper`（ICP/VoxelGrid/PassThrough） | ⚠️ 常见包名 `libpcl-dev`，以目标机构建为准 |
| `depthimage_to_laserscan` | `run_depth_to_scan.sh` | ⚠️ `ros-humble-depthimage-to-laserscan` |
| `python3-opencv` / `python3-numpy` | `depth_colormap.py` | ⚠️ 以 `python3 -c "import cv2, numpy"` 为准 |
| `rviz2` / `rqt_image_view` | 演示脚本 | 可选 |

核对命令示例：

```bash
dpkg -l | grep -E 'libgflags-dev|libgoogle-glog-dev|libusb-1.0-0-dev|libeigen3-dev|nlohmann-json3-dev|libopencv-dev|libjpeg-dev|libpcl-dev'
ros2 pkg prefix depthimage_to_laserscan
python3 -c "import cv2, numpy; print(cv2.__version__, numpy.__version__)"
```

> 包名与版本以 Ubuntu 22.04 / ROS2 Humble 为准；不要照搬源机版本号，构建通过即可。

### 7.3 构建 libuvc（`local/` 缺失或换架构时）

```bash
cd ~/Desktop/tornado_d2_driver
cmake -S libuvc -B libuvc_build \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$HOME/Desktop/tornado_d2_driver/local"
cmake --build libuvc_build --parallel 8
cmake --install libuvc_build
```

验证：`ls local/lib/libuvc.so.0.0.7`，且 `pkg-config --variable=libdir libuvc`（设好 `PKG_CONFIG_PATH`）指向 `local/lib`。

### 7.4 构建 ROS2 包

```bash
cd ~/Desktop/tornado_d2_driver/ros2_ws
source /opt/ros/humble/setup.bash

export PKG_CONFIG_PATH="$HOME/Desktop/tornado_d2_driver/local/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export LD_LIBRARY_PATH="$HOME/Desktop/tornado_d2_driver/local/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export MAKEFLAGS=-j8
export CMAKE_BUILD_PARALLEL_LEVEL=1

colcon --log-base log build \
  --executor sequential \
  --base-paths src \
  --build-base build \
  --install-base install \
  --event-handlers console_cohesion+ \
  --cmake-args -DCMAKE_BUILD_TYPE=Release
```

> 项目版 `astra_camera/CMakeLists.txt` 已改为“未指定才默认 Release”；`~/astra_ws` 那份仍是强制 Debug。
> 只构建 astra 两包时可用 `--packages-up-to astra_camera`；全量（含 `d2_toy_mapper`）用 `--base-paths src`。

### 7.5 构建 SDK

```bash
cd ~/Desktop/tornado_d2_driver/sdk
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel 8
```

### 7.6 udev、环境与补丁校验

```bash
# udev（规则与 Astra Pro 共用；已装则先比对哈希）
sudo install -m 0644 \
  ~/Desktop/tornado_d2_driver/ros2_ws/src/ros2_astra_camera/astra_camera/scripts/56-orbbec-usb.rules \
  /etc/udev/rules.d/56-orbbec-usb.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=usb --attr-match=idVendor=2bc5

# 补丁校验（同版本同架构）
sha256sum ros2_ws/install/astra_camera/lib/OpenNI2/Drivers/liborbbec.so
# 期望 7fa4586e...（前缀）

# 若与官方库对比：应只有文件位置 1060459 一处差异（八进制 016 → 015）
cmp -l ~/astra_ws/install/astra_camera/lib/OpenNI2/Drivers/liborbbec.so \
       ros2_ws/install/astra_camera/lib/OpenNI2/Drivers/liborbbec.so
```

> **架构限制**：`liborbbec.so` 的补丁是**二进制级**的，偏移 `1060459` 只对当前 x86_64 版本成立。ARM64 或换官方版本时，必须重新定位唯一字节序列 `c5 2b 0e 06`（`0x060e`）并改为 `c5 2b 0d 06`（`0x060d`），不能照抄偏移；`libOpenNI2.so`、`libuvc.so`、各节点二进制同样按架构重建。

### 7.7 目标机验收清单

- [ ] `lsusb` 出现 `2bc5:060d`（彩色可选 `2bc5:0505`）
- [ ] `ros2 pkg prefix astra_camera` 指向目标机项目 `install`
- [ ] `list_devices_node` 能枚举到 D2（URI/Serial）
- [ ] `bash ./run_ros2_depth.sh` 启动成功，节点 `/camera/camera` 在列
- [ ] `camera_info` 的 `width/height` = 1280/800（默认）或 640/400（低分辨率）
- [ ] `/camera/depth/image_raw` 约 30 Hz
- [ ] `/camera/depth/points` 用 `--qos-reliability best_effort` 能收到
- [ ] `bash ./run_sdk_depth_test.sh` 输出 `received=30/30`
- [ ] `ros2 topic echo /camera/depth/camera_info --once` 内参与源机一致（见第九节第 9 条）

---

## 八、测试记录（2026-11-17）

| 测试 | 配置 | 结果 | 证据 |
|:---|:---|:---|:---|
| 深度默认模式 | `800×1280@30` 请求 | ROS `1280×800`，约 30 Hz | 实机 `ros2 topic hz` 记录 |
| 深度低分辨率 | `depth_width:=400 depth_height:=640` | ROS `640×400`，29.3–30.3 Hz | `raw_tornado_d2_lowres_verify_2026-11-17_1823.txt` |
| 非法分辨率 | `640×480` / `640×460` | 模式不支持，depth 流被驱动关闭 | `raw_tornado_d2_depth_mode_2026-11-17_1812.txt` |
| 点云 QoS | `point_cloud_qos:=sensor_data` + RViz Best Effort | 发布/订阅两端均 BEST_EFFORT，订阅数 1 | `raw_tornado_d2_qos_supported_modes_2026-11-17_1820.txt` |
| 点云性能 | 低分辨率 + Best Effort | 用户确认“点云明显快一些” | 同上 + 会话记录 |
| 玩具建图“看不到点云” | `toy_mapping.rviz` + toy mapper | RViz 只显示 `/toy_cloud_map`；不足 60 点不建图 → 空白属预期 | `raw_tornado_d2_toymapper_no_cloud_2026-11-17_1837.txt` |
| SDK 冒烟 | `d2_capture` 30 帧 | `received=30/30`、30.16 FPS、FOV 67.63°×53.34° | 项目 `docs/SDK与ROS.md`（⚠️ 未在本轮复跑） |

性能量级：

| 配置 | 点云/帧 | 说明 |
|:---|:---|:---|
| ROS 1280×800 | 16.38 MB（1,024,000 点 × 16 B） | 默认 Reliable；`ros2 topic bw` 约 160 MB/s ≈ 9.8 Hz 到订阅端 |
| ROS 640×400 | 4.10 MB（256,000 点 × 16 B） | 低分辨率 + Best Effort 后明显更轻 |
| 彩色点云 stride=2 | 640×400 | 文档记录平均 25.26 Hz / 中位瞬时 29.30 Hz |
| 彩色点云 stride=1 | 1280×800 | 文档记录平均 20.60 Hz / 中位瞬时 24.95 Hz |

> 大消息用 `ros2 topic hz` 可能“假阴性”：该工具默认 Best Effort，16 MB 级消息容易丢片。优先用 `ros2 topic echo --field header.stamp`、`ros2 bag record` 后查 `metadata.yaml`，或 `ros2 topic info -v` 看两端 QoS。
> 原始输出文件在 `doc/raw_data/`，本地留档、不入 git；换机后不随仓库迁移。

---

## 九、已知限制与不一致

1. **脚本无执行位**：12 个 `.sh` 均为 `-rw-rw-r--`；用 `bash`，或自行 `chmod +x`。
2. **`vendor_id` / `product_id` 对深度设备无效**：深度路径不读这两个参数，只按 OpenNI2 枚举 + `serial_number` 选设备；彩色 UVC 才用 `uvc_*`。
3. **`ir_info_uri` / `color_info_uri` 是无效参数**：节点读的是 `ir_info_url` / `color_info_url`；D2 launch 传 `_uri`，默认空所以无影响。
4. **`orbbec.ini` 哈希与旧文档不一致**：旧文档 `7764e6...`，当前 `32d11c45...`；以当前文件为准（D2 的 `Resolution=-26 / FPS=30 / InputFormat=2`）。
5. **旧项目文档路径是通用写法**：`docs/驱动修改.md` / `docs/建图入门.md` 里的 `${HOME}/tornado_d2_driver` 在本机实际是 `~/Desktop/tornado_d2_driver`；复制命令时替换。
6. **`d2_camera/` 是空占位**：无 `package.xml`，不产生可执行文件；不是漏构建。
7. **`ros2_ws/src/ros2_astra_camera/.git` 是嵌套仓库**：外层项目 git 不会自动跟踪内层改动；提交前确认层级。
8. **Astra Pro 的细节不在本文范围**：其驱动、四路视图、内参、USB 掉线崩溃见 [astra-pro-driver-guide.md](astra-pro-driver-guide.md)。
9. **CameraInfo 内参**：补丁后深度/IR 文档记录为 `fx=fy=955.51855`、`cx=394.36121`、`cy=642.20270`，`D=[0.00602509,-0.06529367,-0.00022497,0.00006898,0]`；使用前建议 `ros2 topic echo /camera/depth/camera_info --once` 复核（⚠️ 本次未重新打印）。
10. **`colored_cloud.rviz` 固定坐标系**为 `camera_depth_optical_frame`，只适合看相机系点云；与底盘/地图联看需另加 TF。
11. **玩具建图不是 SLAM**：无回环/全局优化/轮速或 IMU，会漂移；仅用于验证深度尺度与帧间一致性。
12. **迁移未实测**：本文第七节是方案；目标机按 7.7 验收，尤其注意 `liborbbec.so` 的架构绑定。

---

## 十、故障排查

| 现象 | 可能原因 | 检查/处理 |
|:---|:---|:---|
| `./run_ros2_depth.sh: 权限不够` | 脚本无执行位 | `bash ./run_ros2_depth.sh`，或 `chmod +x *.sh` |
| `sudo cd` 报“找不到命令” | `cd` 是 shell 内建 | 不要 `sudo`；ROS 节点用普通用户跑 |
| `lsusb` 有 `2bc5:060d`，节点一直 `Waiting for device connection...` | 未打补丁的 `liborbbec.so`，或 `OPENNI2_REDIST` 指错 | `ros2 pkg prefix astra_camera`、`echo $OPENNI2_REDIST`、核对库哈希 |
| `Video mode ... is not supported`，随后 depth 流关闭 | 请求了不支持的分辨率（如 640×480） | 查 `get_depth_supported_video_modes`；用 `400×640` 或 `800×1280` |
| `ros2 topic list` 全空 | DDS 环境被跨机配置污染，或 daemon 缓存 | `env \| grep -iE 'rmw\|fastrtps'`；`ros2 daemon stop`；`ros2 topic list --no-daemon` |
| `ros2 topic hz /camera/depth/points` 一直等 | 大消息 + hz 默认 Best Effort 的假阴性 | 用 `ros2 topic echo --field header.stamp`、`ros2 bag record` 或 `ros2 topic info -v` |
| RViz 点云很卡 | 16.38 MB/帧 + Reliable + 订阅慢 | 低分辨率 + `point_cloud_qos:=sensor_data` + RViz PointCloud2 设 Best Effort |
| `toy_mapping.rviz` 看不到点云 | 只显示 `/toy_cloud_map`；不足 60 点不建图 | 看日志：`Map initialized` = 已发；`Too few filtered depth points` = 目标不在 0.3–1.3 m；`ICP rejected` = 移动太快 |
| 彩色流没有 | 未开 UVC 彩色，或 PID 不对 | `bash ./run_multistream.sh`；`lsusb` 确认 `2bc5:0505` |
| 节点“杀不掉” | 节点在另一台机器（FastDDS 多播发现） | 本机 `ps` 查不到却 `ros2 node list` 有 → 去另一台机器杀 |
| `clean_shm_node` 后仍设备忙 | 还有 `astra_camera_node` 在跑 | `pgrep -af astra_camera_node`，按 PID 精确结束 |

---

## 十一、相关文档与来源

| 文档 | 内容 |
|:---|:---|
| [astra-pro-driver-guide.md](astra-pro-driver-guide.md) | Astra Pro 驱动：启动、四路视图、RGB-D 融合、内参、USB 掉线崩溃 |
| [astra-ws-migration-guide.md](astra-ws-migration-guide.md) | `~/astra_ws` 换机/换架构：依赖、编译、udev、验收 |
| [1、环境搭建.md](1、环境搭建.md) | 厂商原始环境搭建记录（迁移手册已逐条核验） |
| [../ros2-ops.md](../ros2-ops.md) | ROS2 构建/启动/录包/分析/排障纪律 |
| [../ros2-qos-dds.md](../ros2-qos-dds.md) | QoS/DDS 问题手册（大消息 hz 假阴性等） |
| 项目内 `docs/驱动修改.md` | D2 兼容补丁、orbbec.ini、CameraInfo/UVC 修改（最详细） |
| 项目内 `docs/SDK与ROS.md` | 最小 SDK 的 API、构建、实测数据与限制 |
| 项目内 `docs/多流演示.md` | 多流、彩色点云、玩具 ICP、深度伪彩色 |
| 项目内 `docs/建图入门.md` | 深度图 → `/scan` → TF → SLAM 的流程 |

**来源与核验方式（2026-11-17）**：

- 源码核对：`ros2_ws/src/ros2_astra_camera/astra_camera`（launch、`ob_camera_node.cpp`、`ob_camera_node_factory.cpp`、`ros_service.cpp`、点云节点）、`ros2_ws/src/d2_toy_mapper`。
- 实机记录：2026-11-17 终端输出，原始文件 `doc/raw_data/raw_tornado_d2_depth_mode_2026-11-17_1812.txt`、`..._qos_supported_modes_2026-11-17_1820.txt`、`..._lowres_verify_2026-11-17_1823.txt`、`..._toymapper_no_cloud_2026-11-17_1837.txt`（本地留档、不入 git）。
- 产物哈希与构建类型：本机 `sha256sum` / `file` / `CMakeLists.txt` 核对。
- 未实测：目标机迁移全流程、ARM64 方案、彩色多流与彩色点云的本轮复跑；文中已用 ⚠️/❓ 标注。
