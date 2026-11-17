# Astra Pro 深度相机驱动手册（ros2_astra_camera）

> 日期：2026-11-17（初版）
> 适用：VM `~/astra_ws` 工作区；`astra_camera` 1.1.0；Astra Pro（SN `17122220437`）；ROS2 Humble
> 依据：源码逐项核对（`~/astra_ws/src/ros2_astra_camera/astra_camera`）+ 2026-11-17 18:45 实机启动日志
> 包内副本：`~/astra_ws/src/ros2_astra_camera/astra_camera/README_R2.md`（跟包走；两处同内容维护）
> 状态：启动、四路视图（RGB / Depth / IR / RGB-D 融合）已实测可用；USB 掉线后的进程崩溃未解决（见 §九）

---

## 一、结论摘要

1. **用 `astra_pro.launch.xml`**，不要用 `astra.launch.xml`：后者是 OpenNI 彩色版（没有 `use_uvc_camera` 等参数），Astra Pro 的彩色走 UVC，不要用错。
2. **推荐启动**：`ros2 launch astra_camera astra_pro.launch.xml color_info_url:=""`。默认 `color_info_url` 指向一个**未安装**的 yaml，每启动一次报一次 ERROR；置空后使用设备出厂内参，功能不受影响。
3. **四路视图**：RGB、Depth、IR、RGB-D 融合。融合是**硬件 D2C**（depth-to-color registration），由 `enable_colored_point_cloud=true` 强制开启，与内参 yaml 无关。
4. **内参 ERROR ≠ 没标定**：文件缺失是 CMake 没有安装 `config/`；驱动回退到设备出厂参数。`virtual_camera_info.yaml` 本身是估算值，不是标定结果。
5. **最大风险是 USB 链路**：2026-11-17 日志中启动 89.3 s 后设备断开，随后 libusb 断言崩溃，Ctrl-C 也退不出（SIGKILL 才结束）。掉线根因在 USB/VM/供电/带宽，崩溃是驱动 teardown 竞态；排查顺序见 §九。

---

## 二、基线

| 项 | 值 | 说明 |
|:---|:---|:---|
| 工作区 | `~/astra_ws` | 本文命令均以此为准；`~/Desktop/tornado_d2_driver` 是另一份副本，不在本文范围 |
| 包 | `astra_camera` 1.1.0 + `astra_camera_msgs` | `ros2_astra_camera` 上游工程 |
| 相机 | Astra Pro，SN `17122220437` | 2026-11-17 日志实测 |
| USB 节点 | `2bc5:0403`（深度/IR，OpenNI）+ `2bc5:0501`（彩色，UVC） | 两个节点都要在 |
| 启动文件 | `launch/astra_pro.launch.xml` | Astra Pro 专用（UVC 彩色） |
| 默认流 | 彩色 / 深度 / IR 均 640×480@30 | `color_depth_synchronization=true` |
| 融合 | `depth_registration=true`、彩色点云 `true` | 彩色点云会强制打开配准 |
| TF | `publish_tf=true`，10 Hz | `camera_link` → 各 frame |
| 内参文件 | 默认 `file://$(find-pkg-share astra_camera)/config/virtual_camera_info.yaml` | **未安装**，见 §七 |

---

## 三、一次性准备

### 3.1 udev 规则（首次 / 换机）

包内 `scripts/install.sh` 会把 `56-orbbec-usb.rules` 安装到 `/etc/udev/rules.d/`：

```bash
cd ~/astra_ws/src/ros2_astra_camera/astra_camera
sudo ./scripts/install.sh
sudo udevadm control --reload-rules
sudo udevadm trigger
# 重新插拔相机
```

预期：无报错，`/etc/udev/rules.d/56-orbbec-usb.rules` 存在。若脚本不可执行，先看内容再手动 `sudo cp scripts/56-orbbec-usb.rules /etc/udev/rules.d/`。

### 3.2 构建

```bash
cd ~/astra_ws
source /opt/ros/humble/setup.bash
colcon build --packages-up-to astra_camera
source install/setup.bash
```

预期：`Summary: 2 packages finished`（`astra_camera_msgs` + `astra_camera`）。

注意：launch 加载的是 `install/<pkg>/share/...` 副本；改 launch / 源码后要重新 build（或使用 `--symlink-install`）。

### 3.3 设备确认

```bash
lsusb | grep -i 2bc5
```

预期两行（Bus/Device 号随插口变化）：

```text
Bus 003 Device 008: ID 2bc5:0403 Orbbec 3D Technology, Inc. ...
Bus 003 Device 009: ID 2bc5:0501 Orbbec 3D Technology, Inc. ...
```

- 只有 `0403`：彩色 UVC 没枚举 → 查线/口/VM USB 直通。
- 一个都没有：VM 菜单里确认 USB 设备已连接到虚拟机；再查线、供电。

### 3.4 权限

若日志出现 `Permission denied opening /dev/bus/usb/...`，按 3.1 的 udev 规则处理；临时 `sudo` 只用于定位，不推荐长期。

---

## 四、启动与验证

### 4.1 推荐命令

```bash
source /opt/ros/humble/setup.bash
source ~/astra_ws/install/setup.bash

# 默认四路全开（RGB + Depth + IR + RGB-D 点云）
ros2 launch astra_camera astra_pro.launch.xml color_info_url:=""
```

按需变体：

```bash
# 不需要 IR：少一路 USB 带宽和 CPU
ros2 launch astra_camera astra_pro.launch.xml color_info_url:="" enable_ir:=false

# 多相机：显式指定序列号，防止 UVC 抓错设备
ros2 launch astra_camera astra_pro.launch.xml color_info_url:="" serial_number:=17122220437

# 只要 RGB：关深度 / IR / 点云，同时关掉配准
ros2 launch astra_camera astra_pro.launch.xml color_info_url:="" \
  enable_depth:=false enable_ir:=false \
  enable_point_cloud:=false enable_colored_point_cloud:=false depth_registration:=false
```

> 若 shell 对 `color_info_url:=""` 处理异常，可写成 `color_info_url:=''`。

### 4.2 启动成功的日志特征

2026-11-17 实测（节选）：

```text
[camera.camera]: init done.
[device_listener]: Found 1 devices
[camera.camera]: Trying to open device: 2bc5/0403@3/8
[camera.camera]: Device connected: Astra serial number: 17122220437
[camera.camera]: starting device
[camera.camera]: set depth video mode Resolution :640x480@30Hz
[camera.camera]: open uvc camera
[camera.camera]: open camera success
[camera.camera]: Publishing dynamic camera transforms (/tf) at 10 Hz
[camera.camera]: depth is started
[camera.camera]: ir is started          # enable_ir:=false 时没有这一行
[camera.camera]: Start UVC camera
[camera.camera]: device  started.
```

以下日志是已知噪音，不影响使用：

- `class_loader.impl: SEVERE WARNING!!! A namespace collision has occurred...`：插件工厂被直接链进可执行文件，上游已知告警。
- `USB events thread - failed to set priority. This might cause loss of data...`：libuvc 线程优先级告警；VM 上常见，只有伴随掉帧时才需要追。
- 默认 `color_info_url` 下的 `Unable to open camera calibration file [...]`：见 §七。

### 4.3 四路视图与话题

| 视图 | 话题 | 消息类型 | 说明 |
|:---|:---|:---|:---|
| RGB | `/camera/color/image_raw` | `sensor_msgs/Image`，`RGB8` | 彩色相机（UVC / MJPEG） |
| Depth | `/camera/depth/image_raw` | `sensor_msgs/Image`，`16UC1`（mm） | **默认已配准到彩色**，见下 |
| IR | `/camera/ir/image_raw` | `sensor_msgs/Image`，`MONO8` | 红外 |
| RGB-D 点云 | `/camera/depth_registered/points` | `sensor_msgs/PointCloud2`（XYZRGB） | 彩色点云；launch 里由 `depth/color/points` remap 而来 |
| 2D 叠加 demo | `/camera/depth_to_color/image_raw` | `sensor_msgs/Image` | 仅运行 `scripts/depth_to_color.py` 时存在；是 2D `bitwise_or`，不是度量融合 |

**重要**：`depth_registration=true`（默认）时，`/camera/depth/image_raw` 发布的是**配准到彩色相机视角**的深度图，`header.frame_id` = `camera_color_optical_frame`，不是原始深度视角。要原始深度视角需 `depth_registration:=false`，但彩色点云会强制把配准打开（§五）。

### 4.4 验证命令

```bash
# 话题清单
ros2 topic list | grep '^/camera'

# 图像编码
ros2 topic echo /camera/depth/image_raw --once --field encoding     # 16UC1
ros2 topic echo /camera/color/image_raw --once --field encoding     # rgb8
ros2 topic echo /camera/ir/image_raw --once --field encoding        # mono8

# 点云帧与尺寸
ros2 topic echo /camera/depth_registered/points --once --field header.frame_id
ros2 topic echo /camera/depth_registered/points --once --field width

# 彩色内参（K）
ros2 topic echo /camera/color/camera_info --once --field k

# TF
ros2 run tf2_ros tf2_echo camera_link camera_color_optical_frame
```

预期：点云 `frame_id` = `camera_color_optical_frame`、`width` = 640；`K` 的前四项非零。

> 图像 / 点云是大消息，`ros2 topic hz` 默认 best_effort，可能"一直等"。这属于工具假阴性，先用 `echo --field header.stamp`、RViz 或 bag metadata 复核，不要直接判链路断（见 [QoS 手册](../ros2-qos-dds.md) §二/§三）。

### 4.5 RViz 配置

- **Fixed Frame**：`camera_link`（或 `camera_color_optical_frame`）。
- **Image**：分别加 `/camera/color/image_raw`、`/camera/depth/image_raw`、`/camera/ir/image_raw`。
- **PointCloud2**：`/camera/depth_registered/points`，Color Transformer 选 `RGB8`。
- 要显示 TF 就保持 `publish_tf=true`；外部已有同名 TF 时改 `publish_tf:=false`（§八-9）。
- VM 上 640×480×30 彩色点云很重；RViz 卡顿先关点云或降 fps。

---

## 五、RGB-D 融合链路（为什么能融合）

1. `enable_colored_point_cloud=true` → `getParameters()` 强制 `depth_registration_ = true`（`ob_camera_node.cpp:362-364`）。launch 里把 `depth_registration` 设成 `false` 也无效。
2. `startStreams()` → `setImageRegistrationMode(true)` → OpenNI `IMAGE_REGISTRATION_DEPTH_TO_COLOR`（`ob_camera_node.cpp:245-253` 调用）；随后 `setDepthToColorResolution(color_width, color_height)`。
3. 配准后，深度图 `header.frame_id` 改为 `depth_aligned_frame_id_`，其值 = `camera_color_optical_frame`（`ob_camera_node.cpp:336-338`、`528-529`、`550-551`）。
4. 彩色点云节点订阅 `depth/image_raw` + `color/image_raw` + `color/camera_info`（`point_cloud_xyzrgb.cpp:127-132`）；回调先检查两图 `frame_id` 是否一致（`139`），再用彩色 `CameraInfo` 的 K 反投影并上色。
5. 深度→彩色的外参来自设备出厂参数 `r2l_r` / `r2l_t`（`ob_camera_info.cpp:22-32`；静态 TF 见 `ob_camera_node.cpp:421-457`）；`enable_publish_extrinsic:=true` 时额外发布 `extrinsic/depth_to_color`。

**结论**：融合由硬件 D2C + 出厂外参完成，不依赖 `color_info_url` 指向的 yaml。yaml 只影响彩色 `CameraInfo` 的 K/D（2D 投影、点云上色用的相机模型），不影响深度图与彩色的对齐。

**注意**：`depth_registration=true` 时驱动把**所有图像流**（含 IR）的 `frame_id` 都写成 `camera_color_optical_frame`（`ob_camera_node.cpp:528-529`），但硬件配准主要作用于 depth；IR 的几何解释不要直接当作已配准（源码行为，IR 实际对齐未实测）。

---

## 六、参数速查

| 参数 | 默认（`astra_pro.launch.xml`） | 作用 / 建议 |
|:---|:---|:---|
| `camera_name` | `camera` | 命名空间；多相机时改 |
| `serial_number` | `""` | 空 = 按 `device_num` 取第一台；多相机显式指定 |
| `depth_registration` | `true` | 硬件 D2C；彩色点云开启时强制 true |
| `enable_colored_point_cloud` | `true` | 彩色点云；会强制打开配准 |
| `enable_point_cloud` | `true` | 非彩色点云 `/camera/depth/points` |
| `enable_color` / `enable_depth` / `enable_ir` | `true` / `true` / `true` | 按需关，省 USB 带宽 |
| `color_width/height/fps` | 640 / 480 / 30 | 降分辨率/帧率可减带宽 |
| `depth_width/height/fps` | 640 / 480 / 30 | 同上 |
| `ir_width/height/fps` | 640 / 480 / 30 | 同上 |
| `color_depth_synchronization` | `true` | 深度-彩色硬件同步；启动卡住时可试 false |
| `publish_tf` | `true` | 驱动发静态 TF；外部发 TF 时关 |
| `tf_publish_rate` | `10.0` | 动态 TF 刷新率 |
| `color_info_url` | 指向未安装的 `config/virtual_camera_info.yaml` | **建议 `""`**（§七） |
| `ir_info_url` | `""` | 空 = 用设备参数 |
| `depth_scale` | `1` | **保持 1**（§八-5） |
| `use_uvc_camera` | `true` | Astra Pro 必须 true |
| `uvc_vendor_id` / `uvc_product_id` | `0x2bc5` / `0x0501` | 彩色 UVC 的 VID/PID |
| `uvc_camera_format` | `mjpeg` | UVC 彩色格式 |
| `uvc_retry_count` | `100` | UVC 查找重试次数 |
| `point_cloud_qos` | `default` | 带宽紧张可改 `sensor_data` |
| `enable_d2c_viewer` | `false` | **当前源码未读取，无效**（§八-13） |
| `enable_publish_extrinsic` | `false` | 发布 `extrinsic/depth_to_color` |

常用组合：

| 目标 | 参数 |
|:---|:---|
| 四路全开（默认） | `color_info_url:=""` |
| 省带宽 | `color_info_url:="" enable_ir:=false` |
| 只要 RGB | `color_info_url:="" enable_depth:=false enable_ir:=false enable_point_cloud:=false enable_colored_point_cloud:=false depth_registration:=false` |
| 多相机 | 追加 `camera_name:=camera2 serial_number:=<第二台 SN>` |

---

## 七、内参 / 标定

### 7.1 为什么默认报 `Unable to open camera calibration file`

- launch 默认 `color_info_url=file://$(find-pkg-share astra_camera)/config/virtual_camera_info.yaml`（`astra_pro.launch.xml:38`）。
- `$(find-pkg-share astra_camera)` 解析到 `install/astra_camera/share/astra_camera`。
- `CMakeLists.txt` 只安装 `include/` 与 `launch/`（`install(DIRECTORY include/...)`、`install(DIRECTORY launch ...)`），**没有安装 `config/`** → install share 下没有这个 yaml → `camera_calibration_parsers` 报 ERROR。
- 源码目录里的 `config/virtual_camera_info.yaml` 是存在的，只是没被安装。

### 7.2 报错后还能用吗

能。默认路径下 UVC 驱动会创建 `CameraInfoManager`，加载失败 → `isCalibrated() == false` → `getCameraInfo()` 回退到构造时传入的 `camera_info_`（`uvc_camera_driver.cpp:85-89`、`163-168`）。这个 `camera_info_` 来自 `getColorCameraInfo()`（`ob_camera_node.cpp:234-239`）：

1. 若 `color_info_manager_` 已标定 → 用 yaml（**UVC 模式下 `getColorCameraInfo()` 不创建这个 manager，本分支不生效**；yaml 由 UVC 驱动自己的 manager 处理，见上）；
2. 否则若设备出厂参数有效（`l_intr_p` 非 NaN）→ 用出厂参数（`ob_camera_info.cpp:254-288`）；
3. 否则用默认 FOV 估算（`ob_camera_info.cpp:290-293`）。

所以 Astra Pro（UVC）实际走的是第 2 步：设备出厂参数。

深度 / IR 的 `CameraInfo` 走 `getDepthCameraInfo()` / `getIRCameraInfo()`，同样优先用设备参数（`ob_camera_info.cpp:130-200`、`202-235`）。

### 7.3 到底缺不缺标定

- **缺的不是"标定"，是"标定文件"**：驱动本来就用设备出厂内参；`virtual_camera_info.yaml` 是通用估算文件（fx=fy=525、cx=319.5、cy=239.5、畸变全 0），文件头自己写明"并非精确值"。
- 对"能看四路图、能出彩色点云"——不需要额外标定。
- 对"高精度测量 / 投影 / 多传感器外参"——需要真实标定（彩色内参 + 深度内参 + 深度→彩色外参），出厂值只能作初值。

### 7.4 推荐处理

| 做法 | 命令 / 改动 | 说明 |
|:---|:---|:---|
| 日常使用（推荐） | `color_info_url:=""` | 不再创建 UVC 的 `CameraInfoManager`，直接用出厂参数，ERROR 消失 |
| 使用虚拟 yaml | `color_info_url:=file:///home/lin/astra_ws/src/ros2_astra_camera/astra_camera/config/virtual_camera_info.yaml` | 会覆盖出厂参数；不建议用于测量 |
| 让默认值可找到 | 在 `CMakeLists.txt` 增加 `install(DIRECTORY config DESTINATION share/${PROJECT_NAME}/)` 后重编译 | 改了包，按需做 |
| 真实标定 | 按 ROS `camera_calibration` 流程生成 `camera_info` yaml，再传 `color_info_url:=file:///...` | 本步骤未实测 |

---

## 八、注意事项（按踩坑概率排序）

1. **别用错 launch**：Astra Pro 必须 `astra_pro.launch.xml`；`astra.launch.xml` 是 OpenNI 彩色版（`depth_registration=false`、`enable_colored_point_cloud=false`、无 UVC 参数），从参数结构看没有 UVC 彩色路径（未实测其在 Astra Pro 上的实际表现，但不要用）。
2. **彩色点云会强制配准**：只要 `enable_colored_point_cloud=true`，`depth_registration` 一定是 true；想关配准必须同时关彩色点云。
3. **`color_info_url` 默认值必报错**：见 §七；推荐置空。
4. **`virtual_camera_info.yaml` 不是标定**：估算值，不要拿它当精确内参。
5. **`depth_scale` 保持 1**：改它只缩放深度图尺寸，`CameraInfo` 的 K 不会同步缩放（`ob_camera_node.cpp:517-521`、`544-548` 只改 width/height），点云 / 投影会错位。
6. **彩色点云节点构造即订阅**：`connectCb()` 在构造函数里调用，且"按需订阅"的 TODO 未实现（`point_cloud_xyzrgb.cpp:85-97`、`119-133`）；没人看点云也照样计算 / 占带宽。不用就关。
7. **IR 多一路带宽**：`enable_ir:=true` 多一路 640×480@30；USB 紧张时先关 IR。
8. **两个 USB 节点都要在**：`2bc5:0403` + `2bc5:0501`；UVC 找不到指定 SN 时会退回任意同 VID/PID 设备（`uvc_camera_driver.cpp:118-121`），多相机时可能抓错 → 显式传 `serial_number`。
9. **TF 双发风险**：`publish_tf=true` 时驱动自己发 `camera_link` / 各 frame；外部 URDF / `robot_state_publisher` 也发同名 TF 会冲突 → 二选一（外部发就设 `publish_tf:=false`）。
10. **点云话题名**：实际是 `/camera/depth_registered/points`（launch 把 `depth/color/points` remap 了，`astra_pro.launch.xml:120`）；找 `/camera/depth/color/points` 会找不到。非彩色点云是 `/camera/depth/points`。
11. **已知噪音**：`class_loader` 的 SEVERE WARNING、`USB events thread - failed to set priority` 是上游已知噪音；后者若伴随掉帧，才需要查线程优先级 / USB 负载。
12. **VM USB 稳定性**：相机在 VMware 里直通，宿主机 USB 控制器 / 线材 / 供电 / 自动挂起都可能造成掉线；长时间采集优先直连后置 USB 口、避免 Hub（见 §九）。
13. **`enable_d2c_viewer` 当前无效**：launch 里有这个参数，但源码没有读取（只在 launch 文件出现）；不要指望它出 D2C 可视化。
14. **服务名**：常用 `get_camera_params` / `get_camera_info` 等，`ros2 service list | grep camera` 查实际名字；`scripts/format_output_camera_params.py` 是现成的 `get_camera_params` 调用示例。

---

## 九、已知问题：USB 掉线 → libusb 断言 → 只能 SIGKILL

### 9.1 现象（2026-11-17 18:45 实测）

- 18:45:19 启动，`device started.` 正常；
- 18:46:48.353（启动后 89.3 s）`[device_listener]: onDeviceDisconnected`；
- 1.57 s 后 `Stopped stream depth` / `Stopped stream ir` / `stop uvc streaming`；
- 随后 `astra_camera_node: ../../libusb/os/threads_posix.h:58: usbi_mutex_destroy: Assertion 'pthread_mutex_destroy(mutex) == 0' failed.`；
- Ctrl-C：SIGINT 5 s 未退 → SIGTERM，再 10 s 未退 → SIGKILL，`exit code -9`；
- 关键缺失日志：`onDeviceDisconnected done.` 始终没打印 → 断开回调没有返回。

完整原始日志：[raw_astra_camera_disconnect_2026-11-17_1845.txt](../raw_data/raw_astra_camera_disconnect_2026-11-17_1845.txt)（本地留档，不入 git）。

### 9.2 代码链（为什么回调回不来）

- `OBContext::onDeviceDisconnected()` 持锁调用 `disconnected_cb_`，返回后才打印 `onDeviceDisconnected done.`（`ob_context.cpp:69-74`）。
- 回调是 `OBCameraNodeFactory::onDeviceDisconnected()`：清 URI → `ob_camera_node_.reset()` → `device_->close()` → `device_.reset()`（`ob_camera_node_factory.cpp:199-213`）。
- `ob_camera_node_.reset()` 触发 `OBCameraNode` 析构：停流（日志的三行）→ UVC 驱动析构（`uvc_close` / `uvc_unref_device` / `uvc_exit`，`uvc_camera_driver.cpp:100-111`）。
- libusb 断言发生在 teardown 阶段：有线程仍持有 / 使用 USB 上下文或其 mutex，`pthread_mutex_destroy` 失败后 `abort()`；进程进入不可正常退出状态，所以 SIGINT / SIGTERM 都无效。

**定性**：掉线本身是外部事件（USB / VM / 供电 / 带宽）；断言崩溃是驱动的 teardown 竞态（断开回调线程里做整节点销毁，流 / 回调线程未先确认退出）。两者是"触发 + 放大"关系，不是 launch 参数问题。

### 9.3 排查顺序（先查掉线，再谈崩溃）

1. **看内核 USB 日志**：`dmesg -T | tail -80`，找 `usb ... disconnect`、`reset`、`over-current`、`device descriptor read` 等。记录掉线前是否有大流量操作（RViz 点云、录包、同时开 IR + 彩色 + 深度）。
2. **换物理链路**：换 USB 口（优先主板后置直连）、换线、去掉 Hub；VM 里确认 USB 控制器是直通而非共享。
3. **降带宽**：`enable_ir:=false`；再不行降 fps / 分辨率、关彩色点云。若降带宽后不再掉线，指向带宽 / 供电。
4. **查 VM / 宿主设置**：VMware 的 USB 自动连接 / 自动挂起；宿主 `lsusb -t` 看是否跑在 USB 2.0 速率；必要时在宿主侧禁用该设备自动挂起（具体命令随宿主而定，未实测）。
5. **复现与计时**：固定场景跑空载（只启动、不看点云）vs 满载（RViz 点云 + 录包），对比掉线时间；若空载也 90 s 掉，优先怀疑线 / 口 / 供电，而不是 CPU。
6. **崩溃兜底**：掉线后进程已不可控，`ps aux | grep astra_camera` 确认后用 `kill -9 <pid>`；长跑用外部 supervisor 重启节点（重启前确认 USB 设备已重新枚举，`lsusb | grep 2bc5`）。

### 9.4 代码级修复方向（未实施，仅记录）

- 断开回调里不要直接 `reset()` 整个节点：先置 `device_connected_=false`，停流并 join UVC / OpenNI 回调线程，再销毁对象；或把销毁投递到主线程 / 定时器，避免在 libusb 回调线程里做重活。
- 析构顺序复核：`uvc_close` → `uvc_unref_device` → `uvc_exit` → `uvc_free_frame` 的顺序是否安全（`frame_buffer_` 在 `uvc_exit` 之后才释放，`uvc_camera_driver.cpp:100-111`）；按 libuvc 生命周期文档调整。
- 加超时 / 看门狗：断开后 N 秒未完成清理则强制退出，避免僵尸进程。
- 以上均需在设备上复现验证，未改代码。

---

## 十、故障速查

| 现象 | 可能原因 | 处理 |
|:---|:---|:---|
| `Unable to open camera calibration file` | `config/` 未安装（§七） | `color_info_url:=""` |
| `Found 0 devices` / `Waiting for device connection...` 不动 | USB 未直通 / 线 / 供电 / udev | `lsusb` 查两节点；换口换线；装 udev |
| 彩色打不开 / 只有深度 | 用了 `astra.launch.xml`，或 `2bc5:0501` 不在 | 换 `astra_pro.launch.xml`；查 UVC 节点 |
| `Permission denied opening /dev/bus/usb/...` | udev 权限 | 按包内 udev 规则处理 |
| 深度全 0 / 噪点大 | IR 遮挡、曝光、超出量程、反光 | 换场景 / 调曝光；查 `depth` 图像 |
| 点云无颜色 / 全黑 | `enable_colored_point_cloud=false`，或 frame_id 不一致，或彩色 `CameraInfo` 缺失 | 开彩色点云；查 `/camera/color/camera_info`；查日志 frame id 警告 |
| 点云 / 深度错位 | `depth_scale≠1`；或分辨率与内参不匹配 | 保持 `depth_scale=1`；用匹配分辨率的内参 |
| 启动即崩 / 掉线后崩 | USB 带宽 / 供电；teardown 竞态 | §九 |
| Ctrl-C 退不出 | 同上 | `kill -9`；查 `ps` |

---

## 相关文件

- 包内副本：`~/astra_ws/src/ros2_astra_camera/astra_camera/README_R2.md`
- 启动文件：`~/astra_ws/src/ros2_astra_camera/astra_camera/launch/astra_pro.launch.xml`
- 核心节点：`src/ob_camera_node.cpp`；内参：`src/ob_camera_info.cpp`；点云：`src/point_cloud_proc/point_cloud_xyzrgb.cpp`；UVC：`src/uvc_camera_driver.cpp`
- 虚拟内参：`config/virtual_camera_info.yaml`（未安装，见 §七）
- 原始日志：[raw_astra_camera_disconnect_2026-11-17_1845.txt](../raw_data/raw_astra_camera_disconnect_2026-11-17_1845.txt)（本地，不入 git）
- 项目规范：[standards.md](../standards.md) ｜ [ros2-ops.md](../ros2-ops.md) ｜ [ros2-qos-dds.md](../ros2-qos-dds.md)

---

## 变更记录

| 日期 | 变更 |
|:---|:---|
| 2026-11-17 | 初版：启动 / 四路视图 / RGB-D 融合 / 内参 / USB 掉线崩溃 |
