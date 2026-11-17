# astra_ws 迁移部署手册（Astra Pro → 新设备）

> 日期：2026-11-17
> 适用：把源机（VM，`~/astra_ws`）的 Astra Pro 相机工作区迁移到另一台设备；目标为 Ubuntu 22.04 + ROS2 Humble，x86_64 / ARM64 均可。
> 基线：`astra_camera` 1.1.0 + `astra_camera_msgs` 1.0.1；Astra Pro（SN `17122220437`，**USB 2.0：`bcdUSB=2.00`、480M，非 USB 3.0**）；源机 libuvc 0.0.7、glog 0.4.0、OpenCV 4.5.4。
> 关联：[astra-pro-driver-guide.md](astra-pro-driver-guide.md)（驱动用法/话题/融合/内参/掉线崩溃）｜[1、环境搭建.md](1、环境搭建.md)（厂商原始环境文档；本手册 §8 逐条核验）｜包内 `~/astra_ws/src/ros2_astra_camera/astra_camera/README_R2.md`（包侧速查）。
> 核验方式：2026-11-17 读取源机构建产物（`CMakeCache.txt`、`flags.make`、install 日志）、udev 规则、`~/.bashrc`、`libuvc.pc` 与包源码；同日用户在源机终端补跑 `dpkg` / `pkg-config` / `lsusb` / udev 哈希（原始输出见 `doc/raw_data/raw_astra_ws_dep_check_2026-11-17_1951.txt`，不入 git），结果见 §1.2/§1.3/附录 B；AI 侧 Bash 仍受限，链接校验器尚未跑。
> 未实测：目标机全流程。本文为迁移方案，源机事实已核验；目标机步骤按 §9 验收。

---

## 结论先行

1. **迁移的最小正确单位 = `~/astra_ws/src` 的完整源码快照**，不是 `build/install/log`，也不是重新下载厂商压缩包。本机 `src/ros2_astra_camera` 未发现 `.git/HEAD`（与厂商文档“解压文件夹”一致），且含本地新增 `README_R2.md` 与当前已调通的 launch 状态——重新下载官方包会丢这些改动。
2. 目标机**重新编译**：`build/` 内是源机绝对路径（本机 `CMAKE_INSTALL_PREFIX=/home/lin/astra_ws/install/astra_camera`），`install/` 的 `libOpenNI2.so` 也按架构分发；拷过去在 ARM64 或不同路径下不可用。
3. 三个必踩点先处理：
   - `color_info_url` 默认指向**未安装**的 `config/virtual_camera_info.yaml`，首启会报 calibration ERROR（四路仍可用；加 `color_info_url:=""` 消掉）。
   - `.bashrc` 里 `source ~/astra_ws/install/setup.bash` 是硬编码路径，且本机还 source 了 5 个其他工作区——**不要整份拷贝**。
   - Astra Pro Plus 的 launch 文件名实际是 `astro_pro_plus.launch.xml`（少一个 a），厂商文档写的 `astra_pro_plus.launch.xml` 不存在。
4. 厂商《1、环境搭建.md》的**流程骨架可用**（依赖 → libuvc → 编译 → udev → `.bashrc` → launch），但有 4 处需修正：`sudo chmod 777 *` 多余且不安全、`sudo vim ~/.bashrc` 有属主风险、`-DCMAKE_BUILD_TYPE=Release` 被 CMakeLists 硬编码 Debug 覆盖、Astra Pro Plus launch 文件名笔误；另需补 OpenCV/完整 ROS 依赖、`libjpeg-dev`、libuvc 版本固定与 `color_info_url` 首启处理。详见 §8。

---

## 1. 迁移前：在源机固化“可复现快照”

### 1.1 源码快照（未发现 git 元数据）

2026-11-17 检查 `~/astra_ws/src/ros2_astra_camera/.git/HEAD` 不存在；厂商文档也写的是“解压文件夹”。因此**没有 commit 可回查**，必须按目录打包：

```bash
# 在源机执行：打包整个 src（含 astra_camera + astra_camera_msgs + 本地文件）
tar -czf ~/astra_ws_src_2026-11-17.tar.gz -C ~/astra_ws src
sha256sum ~/astra_ws_src_2026-11-17.tar.gz
```

记录：

| 项 | 命令 / 位置 | 源机实际（2026-11-17） |
|:---|:---|:---|
| 源码结构 | `find ~/astra_ws/src -maxdepth 3 -name package.xml -print` | `src/ros2_astra_camera/astra_camera/package.xml`、`.../astra_camera_msgs/package.xml` |
| 版本 | `grep -E '<name>|<version>' .../package.xml` | `astra_camera` 1.1.0；`astra_camera_msgs` 1.0.1 |
| 本地新增 | `ls .../astra_camera/README_R2.md` | 存在（本机补充说明） |
| 当前 launch | `grep -E 'depth_registration|enable_colored_point_cloud|color_info_url' .../launch/astra_pro.launch.xml` | `depth_registration=true`、`enable_colored_point_cloud=true`、`color_info_url=file://$(find-pkg-share astra_camera)/config/virtual_camera_info.yaml` |
| VCS | `ls ~/astra_ws/src/ros2_astra_camera/.git/HEAD` | 不存在（按“解压文件夹”现状打包） |

> 注意：当前 launch 已是 RGB-D 融合可用状态；由于没有 git 历史，无法还原“改动前”的版本，**按现状整目录打包**即可，不要用官方压缩包替换。

### 1.2 记录依赖与构建事实

```bash
# 依赖版本
pkg-config --modversion libuvc libglog
pkg-config --cflags --libs libuvc
dpkg -l | grep -E 'libgflags-dev|libgoogle-glog-dev|libusb-1.0-0-dev|libeigen3-dev|nlohmann-json3-dev|libopencv-dev|libjpeg-dev'

# 构建事实（源机已有 build 目录时）
grep -E '^(CMAKE_BUILD_TYPE|LIBUVC_VERSION|GLOG_VERSION|OpenCV_DIR|Eigen3_DIR|CMAKE_INSTALL_PREFIX):' \
  ~/astra_ws/build/astra_camera/CMakeCache.txt
grep '^CXX_FLAGS' ~/astra_ws/build/astra_camera/CMakeFiles/astra_camera.dir/flags.make
```

源机实际（用于目标机对照）：

| 项 | 值 | 证据 |
|:---|:---|:---|
| libuvc | **0.0.7**，`/usr/local/lib/libuvc.so` | `libuvc.pc`；`CMakeCache.txt:815` |
| glog | **0.4.0**，`/usr/lib/x86_64-linux-gnu/libglog.so` | `CMakeCache.txt:780` |
| OpenCV | **4.5.4**，`/usr/lib/x86_64-linux-gnu/cmake/opencv4` | `CMakeCache.txt:741`、`OpenCV_DIR` |
| Eigen3 | `/usr/include/eigen3`，`/usr/share/eigen3/cmake` | `flags.make`、`Eigen3_DIR` |
| libusb | `/usr/lib/x86_64-linux-gnu/libusb-1.0.so` | `CMakeCache.txt:425` |
| CMake / GCC / Python | 3.22.1 / gcc 11 / 3.10.12 | `CMakeCache.txt` |
| 实际构建类型 | **Debug**（`-O3` 仍在） | `flags.make: CXX_FLAGS = -fPIC -O3 -g ...`；install 日志（`~/astra_ws/log/latest_build/astra_camera/stdout_stderr.log`）`Install configuration: "Debug"`；`CMAKE_BUILD_TYPE:STRING=` 为空 |
| 安装前缀 | `/home/lin/astra_ws/install/astra_camera` | `CMakeCache.txt:127` |

> **2026-11-17 用户实跑补证（`dpkg -l`）**：`libopencv-dev` 4.5.4+dfsg-9ubuntu4、`libjpeg-dev` 8c-2ubuntu10、`libusb-1.0-0-dev` 2:1.0.25-1ubuntu2、`nlohmann-json3-dev` 3.10.5-2 均为 `ii`。**libuvc 无 dpkg 记录属预期**（源码装 `/usr/local`，以 `pkg-config` 为准）；`libgoogle-glog-dev` 本次未被 grep 命中（模式写的是 `libglog`，匹配不到包名 `libgoogle-glog`），glog 0.4.0 仍以 `CMakeCache.txt:780` 为准，需用附录 B 修正命令复核。

### 1.3 记录设备与 udev

```bash
lsusb | grep -i 2bc5
# 预期两行：2bc5:0403（深度/IR，OpenNI2） + 2bc5:0501（彩色，UVC）
ls -l /etc/udev/rules.d/56-orbbec-usb.rules
sha256sum /etc/udev/rules.d/56-orbbec-usb.rules
grep -n 'astra_ws' ~/.bashrc
```

源机实际：

- udev 规则已安装：`/etc/udev/rules.d/56-orbbec-usb.rules`；规则为 `MODE:="0666"`、`GROUP:="video"`，并为 `0403` 建 `astra_pro`、`0501` 建 `astrauvc` 符号链接。
- udev 规则哈希（2026-11-17 用户实跑）：`d853072e0ea92e6a134831ee9628e13916f8d7badcd6f1cd6a5bcc0c616f3818`；目标机安装后应与此一致，便于对照。
- `.bashrc` 第 133 行：`source ~/astra_ws/install/setup.bash`（另第 140/143/146/149/153 行还 source 了 5 个其他工作区）。
- `lsusb | grep -i 2bc5`（2026-11-17 19:51 首测）**无输出**：当时未匹配到 `2bc5` 设备（相机未接/未直通），不能据此判断设备缺失。
- **同日 20:48 插好相机后复测正常**：`2bc5:0403`（ASTRA Pro）+ `2bc5:0501`（Astra Pro HD Camera），Bus 003、480M；`dmesg` 仅正常枚举，无 `disconnect`/`reset`/`over-current`。两个接口 `bcdUSB=2.00`，即设备本身是 USB 2.0。

### 1.4 记录实际启动方式

把“你实际能跑通的那条命令”原样记下来，迁移后先照抄再改路径：

```bash
ros2 launch astra_camera astra_pro.launch.xml          # 当前默认（会报 color_info_url ERROR）
# 或
ros2 launch astra_camera astra_pro.launch.xml color_info_url:=""
```

同时记录是否覆盖过：`serial_number`、`camera_name`、`enable_ir`、`publish_tf`、`depth_registration`、`enable_colored_point_cloud`。

---

## 2. 拷什么、不拷什么

| 对象 | 是否拷贝 | 说明 |
|:---|:---:|:---|
| `~/astra_ws/src/` 整目录 | ✅ | 含 `ros2_astra_camera/{astra_camera,astra_camera_msgs}`、`openni2_redist/{x64,arm64,arm}`、`launch/`、`scripts/56-orbbec-usb.rules`、`README_R2.md`、当前 launch 改动 |
| 单独的标定 yaml（若后续做了） | ✅ | 源机目前未做真实标定；若做了，放在项目侧并单独记录 |
| `.bashrc` 中 `astra_ws` 那一行 | ✅ | **只拷这一行**，不要整份 `.bashrc` |
| `build/` | ❌ | 含源机绝对路径、x86_64 编译产物 |
| `install/` | ❌ | 同上；`libOpenNI2.so` 按架构分发，跨机/跨架构不可用 |
| `log/` | ❌ | 源机日志，对目标机无意义 |
| 整份 `~/.bashrc` | ❌ | 还含 `6_Mpu6050t1_ws`、`ldlidar_ros2_ws`、`imu_odom_ws`、`vlp16_slam_ws`、`apriltag_ws` 等目标机不存在的路径 |
| `/usr/local/lib/libuvc*` | ❌ | 目标机源码重装，避免 ABI/架构不匹配 |
| `/etc/udev/rules.d/56-orbbec-usb.rules` | ⚠️ | 可拷，但更推荐在目标机跑包内 `scripts/install.sh` 重新安装（见 §4.5） |

> 若目标机已有同名 `astra_camera`（例如 `~/Desktop/tornado_d2_driver` 的 D2 工作区），先做 §7 的“重复包”检查，不要直接覆盖。

---

## 3. 目标机前置条件

### 3.1 OS / ROS / 架构

| 项 | 要求 | 说明 |
|:---|:---|:---|
| OS | Ubuntu 22.04（Jammy） | 与源机一致；24.04 对应 ROS Jazzy，未验证 |
| ROS | ROS2 **Humble** | 源机 `/opt/ros/humble`；上游 README 写 Galactic，是旧版说明，不要照抄 |
| 架构 | x86_64 或 ARM64 | `openni2_redist/{x64,arm,arm64}` 三个目录在源码中均存在（源机 install 日志 + 二进制文件核验） |
| 构建方式 | **目标机原生编译** | CMake 用 `uname -m` + `getconf LONG_BIT` 选 OpenNI2 架构；交叉编译会选错 |

`HOST_PLATFORM` 选择规则（`CMakeLists.txt:55-68`）：

| `uname -m` | `getconf LONG_BIT` | HOST_PLATFORM | 目录 |
|:---|:---|:---|:---|
| `x86_64` | 64 | `x64` | `openni2_redist/x64` |
| `aarch64` | 64 | `arm64` | `openni2_redist/arm64` |
| `arm*` | 32 | `arm` | `openni2_redist/arm` |
| `aarch64` | 32 | `arm` | `openni2_redist/arm` |

### 3.2 系统依赖

源机实际构建链路要求（`CMakeLists.txt` + `flags.make` + `CMakeCache.txt`）：

| 依赖 | 用途 | 源机证据 | 目标机动作 |
|:---|:---|:---|:---|
| `libgoogle-glog-dev` | `pkg_search_module(GLOG REQUIRED libglog)` | glog 0.4.0，`/usr/lib/x86_64-linux-gnu/libglog.so` | 必装 |
| `libgflags-dev` | glog 配套；上游 README/厂商文档列出 | 链接行只出现 `-lglog`，未见 `-lgflags` | 建议装（无害） |
| `libusb-1.0-0-dev` | libuvc 依赖；`/usr/include/libusb-1.0` | `flags.make` 含该 include | 必装 |
| `libeigen3-dev` | `find_package(Eigen3 REQUIRED)` | `/usr/include/eigen3` | 必装 |
| `nlohmann-json3-dev` | `ob_camera_info.cpp:14` 使用 `<nlohmann/json.hpp>` | 源机构建成功；上游 README 漏列 | **必装**（厂商文档已列，正确） |
| `libopencv-dev` | `find_package(OpenCV REQUIRED)`（`CMakeLists.txt:30`） | OpenCV 4.5.4，`/usr` | 必装（或由 `ros-humble-cv-bridge` 带入） |
| `libjpeg-dev` | libuvc 的 MJPEG 支持（`Libs.private: ... -ljpeg`） | `libuvc.pc` | 编译 libuvc 前装 |
| `build-essential` / `cmake` / `pkg-config` | 编译链 | CMake 3.22.1、gcc 11 | 必装 |
| `python3-colcon-common-extensions` | `colcon build` | 源机已用 colcon | 必装 |
| `git` | 拉取 libuvc | — | 建议装 |

### 3.3 ROS 依赖

厂商文档只列了 4 个 ROS 包（`image-geometry`、`camera-info-manager`、`image-transport`、`image-publisher`），但 `package.xml` / `CMakeLists.txt` 实际还依赖：

```text
ament_index_cpp, astra_camera_msgs, builtin_interfaces, class_loader,
cv_bridge, image_geometry, image_publisher, image_transport,
message_filters, camera_info_manager, rclcpp, rclcpp_components,
rcutils, sensor_msgs, std_msgs, std_srvs, tf2, tf2_eigen,
tf2_msgs, tf2_ros, tf2_sensor_msgs
```

推荐二选一：

```bash
# 方案 A：桌面版（含 rviz2/rqt，最省心）
sudo apt install ros-humble-desktop

# 方案 B：先装 base + rosdep 补齐
sudo apt install ros-humble-ros-base python3-rosdep
sudo rosdep init   # 只需一次；已初始化会报错，可忽略
rosdep update
cd ~/astra_ws
rosdep install --from-paths src --ignore-src -r -y
```

若目标机没有 `rqt_image_view`，补 `sudo apt install ros-humble-rqt-image-view`；RViz 用 `ros-humble-rviz2`。

### 3.4 网络

- libuvc 需要从 GitHub 拉取；实验室机器（如 N97）访问 GitHub 可能需代理（项目内已有“代理 TUN 未开导致 clone 超时”的记录）。
- 目标机不能联网时：在源机预先下载 libuvc 源码（含 `.git` 以便 checkout 固定 commit），或准备同版本 tarball，随迁移包一起带过去。
- `rosdep` 需要能访问 ROS 软件源；离线目标机改为手动装 §3.2/§3.3 的包。

---

## 4. 目标机部署步骤

### 4.1 解包源码

```bash
mkdir -p ~/astra_ws
tar -xzf astra_ws_src_2026-11-17.tar.gz -C ~/astra_ws
# 结果：~/astra_ws/src/ros2_astra_camera/...
```

确认两个包都在：

```bash
ls ~/astra_ws/src/ros2_astra_camera
# astra_camera  astra_camera_msgs  README.MD
```

### 4.2 安装系统 / ROS 依赖

```bash
sudo apt update
sudo apt install -y \
  ros-humble-desktop \
  build-essential cmake pkg-config git python3-colcon-common-extensions \
  libgflags-dev libgoogle-glog-dev libusb-1.0-0-dev libeigen3-dev \
  nlohmann-json3-dev libopencv-dev libjpeg-dev
source /opt/ros/humble/setup.bash

# 可选：rosdep 补齐（方案 B 时）
# cd ~/astra_ws && rosdep install --from-paths src --ignore-src -r -y
```

> 厂商文档的 `ros-$ROS_DISTRO-*` 依赖 `ROS_DISTRO` 已设置；新终端先 `source /opt/ros/humble/setup.bash`，或直接把变量写成 `humble`。

### 4.3 编译安装 libuvc（固定版本）

源机是 **0.0.7**。先在源机记录 libuvc 源码的 commit（若源码还在）：

```bash
# 源机
git -C ~/libuvc rev-parse HEAD   # 路径按实际改
```

目标机：

```bash
mkdir -p ~/src && cd ~/src
git clone https://github.com/libuvc/libuvc.git
cd libuvc
git checkout <源机记录的 commit>   # 若上游有 v0.0.7 tag 也可用 tag；以源机版本为准
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j"$(nproc)"
sudo make install
sudo ldconfig

pkg-config --modversion libuvc    # 期望 0.0.7
```

> `make -j2` 是保守写法；目标机核数足够时用 `-j$(nproc)`。
> libuvc 编译需要 `libjpeg`/`libusb` 开发包（§4.2 已装）。

### 4.4 编译工作区

```bash
cd ~/astra_ws
source /opt/ros/humble/setup.bash
colcon build --event-handlers console_direct+ --cmake-args -DCMAKE_BUILD_TYPE=Release
source install/setup.bash
```

**关于 `-DCMAKE_BUILD_TYPE=Release`**：`astra_camera/CMakeLists.txt:10` 无条件 `set(CMAKE_BUILD_TYPE "Debug")`，普通变量会遮蔽命令行传入的 cache 值；源机 `flags.make` 实际是 `-fPIC -O3 -g`、install 日志是 `Install configuration: "Debug"`。因此：

- 该参数**不会**得到真正的 Release；
- `-O3` 仍在基础 flags 里，性能影响有限；
- 迁移优先保持与源机一致（Debug + -O3）；若确实要 Release，需把 CMakeLists 改为 `if(NOT CMAKE_BUILD_TYPE) set(CMAKE_BUILD_TYPE Release) endif()`（这是改上游代码，非迁移必需）。

只编相机包（更快，自动先编 msgs）：

```bash
colcon build --packages-up-to astra_camera
```

### 4.5 安装 udev 规则

```bash
cd ~/astra_ws/src/ros2_astra_camera/astra_camera
sudo bash scripts/install.sh
sudo udevadm control --reload-rules && sudo udevadm trigger
# 重新插拔相机
```

`install.sh` 只做两件事：检查 root、把 `scripts/56-orbbec-usb.rules` 拷到 `/etc/udev/rules.d/56-orbbec-usb.rules`。**不需要**厂商文档里的 `sudo chmod 777 *`——它只会把脚本改成所有人可写，不解决任何权限问题。

规则内容（源机实测）：`MODE:="0666"`、`GROUP:="video"`，`0403` → `astra_pro`，`0501` → `astrauvc`。`0666` 意味着普通用户可直接访问；若目标机策略要求 `0660`，才需要把用户加入 `video` 组。源机规则 sha256 = `d853072e0ea92e6a134831ee9628e13916f8d7badcd6f1cd6a5bcc0c616f3818`（11-17）；目标机装同版本后可比对。

### 4.6 环境变量

首次测试建议**只在当前终端 source**，不要先写 `.bashrc`：

```bash
source /opt/ros/humble/setup.bash
source ~/astra_ws/install/setup.bash
```

确认无误后再写入（注意用 `[ -f ]` 守卫，避免未编译时每个终端报错）：

```bash
# 追加到 ~/.bashrc（不要用 sudo vim，避免把文件属主改成 root）
echo '[ -f ~/astra_ws/install/setup.bash ] && source ~/astra_ws/install/setup.bash' >> ~/.bashrc
```

**不要整份拷贝源机 `.bashrc`**：源机还 source 了 5 个其他工作区，目标机不存在这些路径。若目标机也有多个工作区，先确认 source 顺序；不同工作区若含同名 `astra_camera`，后 source 的会覆盖前面的（§7）。

### 4.7 设备枚举

```bash
lsusb | grep -i 2bc5
# 期望两行：
# Bus ... ID 2bc5:0403 ...   （深度/IR，OpenNI2）
# Bus ... ID 2bc5:0501 ...   （彩色，UVC）
```

只有一行 = 另一个 USB 接口没枚举（线/口/Hub/VM 直通）；两行都没有 = 供电/线/udev/VM 直通问题。

> 2026-11-17 源机实测：两个接口 `bcdUSB=2.00`、`speed=480`（`/sys/bus/usb/devices/3-2/version`、`3-4.1/version`），即本机 Astra Pro 本身是 **USB 2.0**，`lsusb -t` 显示 480M 属正常；不要以 Bus 04 的 5000M/20000M 作为验收判据。

可选：

```bash
ros2 run astra_camera list_devices_node
```

### 4.8 首次启动

标准启动命令就是原厂这条：

```bash
source /opt/ros/humble/setup.bash
source ~/astra_ws/install/setup.bash
ros2 launch astra_camera astra_pro.launch.xml
```

`color_info_url:=""` 不是另一个 launch 文件，只是**可选的参数覆盖**，用来消掉首启的 calibration ERROR：

```bash
ros2 launch astra_camera astra_pro.launch.xml color_info_url:=""
```

为什么加 `color_info_url:=""`：默认值指向 `file://$(find-pkg-share astra_camera)/config/virtual_camera_info.yaml`，但 `CMakeLists.txt` 只安装 `include/` 与 `launch/`（`CMakeLists.txt:237-245`），**没有安装 `config/`**；源机 install 树中该文件确实不存在。启动会打印：

```text
[ERROR] [camera_calibration_parsers]: Unable to open camera calibration file [...]
```

四路图像仍能正常出（驱动回退到设备出厂内参）；置空 `color_info_url` 即消掉 ERROR。需要真实标定时，按 ROS `camera_calibration` 生成 yaml 再传 `file:///绝对路径`。

Astra Pro Plus 用：

```bash
ros2 launch astra_camera astro_pro_plus.launch.xml
```

> 实际文件名是 `astro_pro_plus.launch.xml`（`astro`，少一个 a）；厂商文档的 `astra_pro_plus.launch.xml` 在包内不存在（源机已核验，install 日志也只列出 `astro_pro_plus.launch.xml`）。

### 4.9 基础验收

```bash
ros2 topic list | grep '^/camera'

ros2 topic echo /camera/depth/image_raw --once --field encoding          # 16UC1
ros2 topic echo /camera/color/image_raw --once --field encoding          # RGB8
ros2 topic echo /camera/ir/image_raw --once --field encoding             # MONO8

ros2 topic echo /camera/depth_registered/points --once --field header.frame_id
# 期望 camera_color_optical_frame
ros2 topic echo /camera/depth_registered/points --once --field width
# 期望 640
ros2 topic echo /camera/color/camera_info --once --field k
# 期望前四项非零（K[0] fx、K[4] fy、K[2] cx、K[5] cy）

ros2 run tf2_ros tf2_echo camera_link camera_color_optical_frame
```

> 图像/点云是大消息，`ros2 topic hz` 默认 best_effort，可能“一直等”或假阴性；先用 `echo --field header.stamp` / RViz / 短 bag 的 `metadata.yaml` 复核，判据见 [ros2-qos-dds.md](../ros2-qos-dds.md)。完整话题/融合链路见 [astra-pro-driver-guide.md](astra-pro-driver-guide.md)。

---

## 5. 参数与设备适配

`astra_pro.launch.xml` 的关键默认值与迁移处理：

| 参数 | 默认 | 迁移时怎么处理 |
|:---|:---|:---|
| `camera_name` | `camera` | 单相机保持默认；改它会改话题命名空间（`/foo/...`）和大部分 frame 前缀（`foo_color_frame` 等）。注意 `camera_link_frame_id` 参数默认固定为 `camera_link`（`constants.h:67`，launch 未暴露），多相机时 `camera_link` 会重名 → 需改 launch/参数或外部 TF 接管 |
| `serial_number` | 空 | 单相机可不填；多相机必须显式填。UVC 驱动找不到指定 SN 时会退回任意同 VID/PID 设备（`uvc_camera_driver.cpp:118-121`），多相机不填会认错 |
| `depth_registration` | `true` | 保持；`enable_colored_point_cloud=true` 会在源码里强制置 true（`ob_camera_node.cpp:362-364`），想关配准必须同时关彩色点云 |
| `enable_colored_point_cloud` | `true` | 需要 RGB-D 点云就保持；不需要可关，省带宽/CPU |
| `enable_ir` | `true` | USB 带宽紧张（Hub/VM/长线）时先关 IR（`enable_ir:=false`） |
| `publish_tf` | `true` | 若目标机器人已有 URDF/TF 发布相机 frame，设 `publish_tf:=false`，避免同名 TF 双发 |
| `color_info_url` | 指向未安装的 `config/virtual_camera_info.yaml` | **首启置空** `color_info_url:=""`；有真实标定再传文件 URL |
| `depth_scale` | `1` | 保持 1；改它只缩放深度图尺寸，`CameraInfo` 的 K 不同步缩放（`ob_camera_node.cpp:517-521`、`544-548`） |
| `use_uvc_camera` | `true` | Astra Pro 保持 true（彩色走 UVC `2bc5:0501`） |
| `uvc_vendor_id` / `uvc_product_id` | `0x2bc5` / `0x0501` | Astra Pro 固定；不要改成深度口 `0403` |
| `uvc_camera_format` | `mjpeg` | 保持；改格式可能不被设备支持 |
| `uvc_retry_count` | `100` | 保持；启动时相机枚举慢可增大 |
| `color_width/height/fps`、`depth_*`、`ir_*` | 640×480@30 | 带宽/算力不足时先降 fps 或关 IR，不要先改分辨率（会影响内参与点云尺寸） |
| `color_depth_synchronization` | `true` | 保持；关掉可能加剧彩色/深度时间错位 |
| `connection_delay` | `100` | 保持 |

---

## 6. 硬件 / USB 注意事项

1. **两个 USB 接口都要在**：`2bc5:0403`（深度/IR） + `2bc5:0501`（彩色）。只看到 `0403` 时彩色不出；只看到 `0501` 时深度不出。
2. **本机 Astra Pro 是 USB 2.0，不是 USB 3.0**：2026-11-17 实测两个接口 `bcdUSB=2.00`、`speed=480`（`/sys/bus/usb/devices/3-2/version`、`3-4.1/version`），`lsusb -t` 显示 480M 属正常，不会以 5000M 枚举。厂商文档“虚拟机需保证 USB3.0 连接”按“控制器兼容/供电”理解，不要按设备速率理解；VM 仍建议启用 USB 3.0 控制器并把两个 Orbbec 接口直通，物理机优先直连主板口、避免无源 Hub。验收看 480M 下稳定出流，不以 5000M 为判据。
3. **带宽**：彩色 MJPEG 640×480@30 + 深度 + IR 同时开，对 Hub/长线/VM 直通压力大；不稳定时按 `enable_ir:=false` → 降 fps → 关彩色点云的顺序减负。
4. **掉线是已知问题**：源机 2026-11-17 实测启动 89.3 s 后 `onDeviceDisconnected`，随后 libusb 断言、Ctrl-C/SIGTERM 均无效、只能 SIGKILL。掉线是外部事件（USB/VM/供电/带宽），崩溃是驱动 teardown 竞态；排查顺序与代码链见 [astra-pro-driver-guide.md](astra-pro-driver-guide.md) §8/§9。迁移验收应包含至少 10 分钟连续运行；若复现，先查 `dmesg -T | tail -80` 的 USB disconnect/reset/over-current，不要先怀疑迁移步骤。
5. **udev 权限**：规则是 `MODE 0666`，普通用户可用；如果目标机已有其他 Orbbec SDK 的 udev 规则，先备份再安装，避免重复/冲突。
6. **相机 SN**：本机 Astra Pro SN `17122220437`；单相机 launch 默认不填 SN 也能用。换机后若同时接多台，必须用 `serial_number:=...` 区分。

---

## 7. 目标场景差异矩阵

| 场景 | 要注意什么 |
|:---|:---|
| x86_64 Ubuntu 22.04 + Humble | 与源机最接近；按 §4 直接做 |
| ARM64（N97 / Jetson） | `openni2_redist/arm64` 存在；目标机原生编译；确认 `uname -m=aarch64` 且 `getconf LONG_BIT=64`；OpenCV/libuvc 用 arm64 包/源码；CPU 性能与 USB 带宽需实测 |
| ARM32 | `openni2_redist/arm` 存在；ROS Humble 的 arm32 支持有限，不作为首选 |
| Docker | 直通 `/dev/bus/usb`（或具体设备 cgroup）；容器内 `lsusb` 确认两个接口；udev 规则在宿主机装；`--privileged` 不是长久方案 |
| WSL | 需 usbipd 把两个 USB 接口转发进 WSL；`lsusb` 确认；不作为首选 |
| 目标机已有 D2 工作区（`~/Desktop/tornado_d2_driver`） | 该工作区也有 `astra_camera` / `astra_camera_msgs`；两个工作区都 source 时 `ros2 launch astra_camera` 可能命中错的那份。先 `ros2 pkg prefix astra_camera` 确认；只 source 一个，或在另一个包的目录放 `COLCON_IGNORE` |
| 工作区路径不是 `~/astra_ws` | 全部命令按实际路径改；`.bashrc` 的 source 行同步改；`build/install` 在目标机重新生成，不要拷 |
| ROS 发行版不是 Humble | 本工作区按 Humble 验证；换 Foxy/Galactic/Jazzy 需另做 API/依赖兼容评估（未实测），不要直接套本文 |
| 目标机无 GitHub 访问 | 预先把 libuvc 源码/固定 commit 的 tarball 带过去；不要在目标机现场 clone 赌网络 |

---

## 8. 对《1、环境搭建.md》的逐条核验（2026-11-17，本机）

> 核验对象：`doc/camera/1、环境搭建.md`（厂商原始环境文档）。证据来自源机文件/构建产物 + 2026-11-17 用户终端实跑（附录 B）；仍未核实项见附录 B。

| # | 文档位置 / 说法 | 本机实际 / 证据 | 判定 | 迁移处理 |
|:--|:---|:---|:---:|:---|
| 1 | §1.1 安装 `nlohmann-json3-dev` | `ob_camera_info.cpp:14` 使用 `<nlohmann/json.hpp>`；源机构建成功 | ✅ **必要且正确**（上游 README 漏列） | 目标机必装 |
| 2 | §1.1 只列 4 个 ROS 包 | `package.xml`/`CMakeLists.txt` 还需要 `cv_bridge`、`message_filters`、`tf2*`、`rclcpp*`、`class_loader`、`rclcpp_components`、`std_srvs`、`sensor_msgs`、`builtin_interfaces`、`ament_index_cpp` 等；源机 `/opt/ros/humble/share/...` 均有 | ⚠️ **列表不完整** | 装 `ros-humble-desktop` 或用 rosdep 补齐 |
| 3 | §1.1 未列 OpenCV | `CMakeLists.txt:30` `find_package(OpenCV REQUIRED)`；源机 OpenCV 4.5.4（`/usr`） | ⚠️ **缺** | 装 `libopencv-dev`（或由 `cv_bridge` 带入） |
| 4 | §1.1 安装 `libgflags-dev` | glog 0.4.0；链接行只有 `-lglog`，未见 `-lgflags` | ✅ **无害** | 保留安装即可，不是显式链接必需 |
| 5 | §1.2 `git clone libuvc` 未固定版本 | 源机 `libuvc.pc`/`CMakeCache.txt` = **0.0.7**，装在 `/usr/local` | ⚠️ **需固定** | 记录源机 commit，目标机 checkout 同一版本；用 `-j$(nproc)` |
| 6 | §1.2 未提 libjpeg | `libuvc.pc` 的 `Libs.private` 含 `-ljpeg` | ⚠️ **需补** | 编译 libuvc 前装 `libjpeg-dev` |
| 7 | §1.3 `--cmake-args -DCMAKE_BUILD_TYPE=Release` | `CMakeLists.txt:10` 无条件 `set(CMAKE_BUILD_TYPE "Debug")`；源机 `CMAKE_BUILD_TYPE:STRING=` 为空、`flags.make` 为 `-fPIC -O3 -g`、install 日志 `Install configuration: "Debug"` | ❌ **该参数不产生 Release** | 迁移保持与源机一致即可；要真 Release 需改 CMakeLists（非必需） |
| 8 | §1.3 `cd ~/astra_ws` | 源机路径确为 `~/astra_ws`；源码在 `src/ros2_astra_camera` | ✅ **本机属实** | 目标机路径不同则全命令替换 |
| 9 | §1.4 `sudo chmod 777 *` | `scripts/install.sh` 只检查 root 并 `cp` 规则文件；udev 规则本身是 `MODE 0666` | ❌ **多余且不安全** | 删掉；只跑 `sudo bash scripts/install.sh` |
| 10 | §1.4 `sudo bash install.sh` + `udevadm reload/trigger` | 源机 `/etc/udev/rules.d/56-orbbec-usb.rules` 已安装；规则含 `0403→astra_pro`、`0501→astrauvc`；11-17 实跑 sha256 = `d853072e...` | ✅ **正确** | 目标机照做，装完重插相机 |
| 11 | §1.5 `sudo vim ~/.bashrc` + 末尾 `source ~/astra_ws/install/setup.bash` | 源机 `.bashrc:133` 确为该行；但同文件还 source 了 5 个其他工作区（140/143/146/149/153） | ⚠️ **sudo 有属主风险；整份拷贝会坏** | 用 `vim ~/.bashrc`（无 sudo）；只追加 astra 一行，并用 `[ -f ]` 守卫 |
| 12 | §1.6 `ros2 launch astra_camera astra_pro.launch.xml` | 文件存在；默认 `color_info_url` 指向 `share/astra_camera/config/virtual_camera_info.yaml`，但 `CMakeLists.txt` 只安装 `include/` 与 `launch/`，源机 install 树无该文件 | ⚠️ **首启必报 calibration ERROR** | 加 `color_info_url:=""`；四路仍可用 |
| 13 | §1.6 `astra_pro_plus.launch.xml`（Astra Pro Plus） | 包内实际是 `astro_pro_plus.launch.xml`；`astra_pro_plus.launch.xml` 不存在；install 日志也只列 `astro_pro_plus.launch.xml` | ❌ **文件名笔误** | Astra Pro Plus 用 `astro_pro_plus.launch.xml`（其功能未实测） |
| 14 | §1.6 “虚拟机需保证 USB3.0 连接” | 源机为 VMware VM，相机可正常出四路；11-17 19:51 首测无输出（当时未接/未直通），20:48 复测两接口正常（`2bc5:0403` + `2bc5:0501`，Bus 003、480M，`bcdUSB=2.00`），`dmesg` 无 disconnect/reset/over-current | ✅ **与实测不冲突；本机设备为 USB 2.0** | 目标机确保 USB3 控制器 + 两个接口直通；480M 属正常，不以 5000M 为判据 |
| 15 | §1.6 引用 `image-20230301095857909.png` 等 | `doc/camera/` 下该图片不存在（其余 `image-*` 同按相对路径引用，未逐一核） | ⚠️ **文档图片缺失** | 迁移时按文字/话题验证，不要依赖图 |
| 16 | §1.3 “解压文件夹” | `src/ros2_astra_camera/.git/HEAD` 未发现，与“解压文件夹”描述一致 | ✅ **属实** | 整目录 tar 打包；不要重新下载官方包 |
| 17 | §1.1 `ros-$ROS_DISTRO-*` | 依赖 `ROS_DISTRO` 已设置；新终端未 source ROS 时变量为空 | ⚠️ **有前提** | 先 `source /opt/ros/humble/setup.bash`，或直接写 `humble` |
| 18 | 文档未提 `rosdep` / `colcon` / `build-essential` | 源机构建用 CMake 3.22.1 + gcc 11 + colcon；这些不在文档 apt 行里 | ⚠️ **缺前置** | 按 §3.2/§3.3 补 |

**核验结论**：

- 流程骨架（依赖 → libuvc → 编译 → udev → `.bashrc` → launch）与源机实际一致，可作为迁移主线。
- **必须修正的 4 处**：① `sudo chmod 777 *`；② `sudo vim ~/.bashrc`；③ `-DCMAKE_BUILD_TYPE=Release` 实际不生效；④ Astra Pro Plus 的 `astra_pro_plus.launch.xml` 文件名。
- **必须补充的 4 类**：OpenCV + 完整 ROS 依赖；`libjpeg-dev`；libuvc 版本/commit 固定；`color_info_url` 首启处理。
- **已补证（2026-11-17 用户实跑）**：`libopencv-dev` 4.5.4、`libjpeg-dev` 8c、`libusb-1.0-0-dev` 1.0.25、`nlohmann-json3-dev` 3.10.5 的 dpkg 版本；udev 规则哈希 `d853072e...`。
- **仍未核实**：glog 的 `pkg-config` 版本（本次模块名写错，应为 `libglog`）、libuvc 的 `pkg-config` 输出（同一次命令被 glog 报错打断）、`lsusb` 枚举（执行时相机未接）、sysfs USB 速率；修正命令见附录 B。

---

## 9. 目标机验收清单

- [ ] `pkg-config --modversion libuvc` 与源机一致（0.0.7）
- [ ] `pkg-config --modversion libglog` = 0.4.0（模块名是 `libglog`，不是 `glog`）
- [ ] `colcon build --packages-up-to astra_camera` 成功，无 missing dependency
- [ ] `lsusb | grep -i 2bc5` 两个接口都在（`0403` + `0501`）
- [ ] `lsusb -t` 显示 Astra Pro 为 480M 属正常（本机 `bcdUSB=2.00`）；不以 5000M 为判据
- [ ] `/etc/udev/rules.d/56-orbbec-usb.rules` 已安装，普通用户可启动（无需 sudo）；sha256 与源机 `d853072e...` 一致（同版本规则时）
- [ ] 启动无 fatal；若未置空 `color_info_url`，仅 calibration ERROR，四路仍出
- [ ] `/camera/color/image_raw` = `RGB8`；`/camera/depth/image_raw` = `16UC1`；`/camera/ir/image_raw` = `MONO8`
- [ ] `/camera/depth_registered/points` frame = `camera_color_optical_frame`、width = 640
- [ ] `/camera/color/camera_info` 的 K 前四项非零
- [ ] `tf2_echo camera_link camera_color_optical_frame` 有完整链
- [ ] 连续运行 ≥10 分钟，无 USB 掉线；若掉线，按驱动手册 §8 定位（USB/供电/带宽/VM）
- [ ] 拔插相机后重新枚举、重启 launch 可恢复
- [ ] 重启目标机后 udev 规则仍生效、`.bashrc` 不报错
- [ ] `ros2 pkg prefix astra_camera` 指向本次迁移的工作区（排除重复包）
- [ ] 如需集成到机器人：`publish_tf:=false` 与外部 TF 不冲突；`camera_name`/frame 无重名

---

## 10. 回滚

| 失败点 | 回滚动作 |
|:---|:---|
| 工作区编译失败 | 保留 `src` 快照；`rm -rf build install log` 后重编（先确认没有其他工作区共用） |
| libuvc 装坏/版本不符 | 在 libuvc build 目录 `sudo make uninstall`；或删除 `/usr/local/lib/libuvc*`、`/usr/local/include/libuvc*`、`/usr/local/lib/pkgconfig/libuvc.pc` 后 `sudo ldconfig`，再按 §4.3 重装 |
| udev 规则冲突 | 备份并删除 `/etc/udev/rules.d/56-orbbec-usb.rules`，`sudo udevadm control --reload-rules && sudo udevadm trigger`，恢复原规则 |
| `.bashrc` 写坏 | 删除追加的 astra 行；不要整份覆盖，手工恢复 |
| 目标机已有 `astra_camera` 被覆盖 | 迁移前备份原工作区；用 `ros2 pkg prefix` 确认；必要时恢复原目录并重新 `colcon build` |

---

## 11. 相关文档

- 驱动用法/话题/RGB-D 融合/内参/USB 掉线崩溃：[astra-pro-driver-guide.md](astra-pro-driver-guide.md)
- 厂商原始环境文档：[1、环境搭建.md](1、环境搭建.md)
- 包内速查（源机路径）：`~/astra_ws/src/ros2_astra_camera/astra_camera/README_R2.md`
- QoS/DDS 与大消息验证：[ros2-qos-dds.md](../ros2-qos-dds.md)
- ROS2 构建/部署/进程卫生：[ros2-ops.md](../ros2-ops.md)

---

## 附录 A：源机事实快照（2026-11-17）

| 项 | 值 | 证据 |
|:---|:---|:---|
| OS | Ubuntu 22.04.5 LTS（Jammy） | `/etc/os-release` |
| 机器 | VMware VM（CMake `SITE=lin-virtual-machine`） | `CMakeCache.txt:275` |
| ROS | Humble，`/opt/ros/humble` | 构建 cache 路径 |
| 包版本 | `astra_camera` 1.1.0；`astra_camera_msgs` 1.0.1 | 两个 `package.xml` |
| 相机 | Astra Pro，SN `17122220437`；USB `2bc5:0403` + `2bc5:0501` | 运行日志/驱动手册 |
| libuvc | 0.0.7，`/usr/local` | `libuvc.pc`；`CMakeCache.txt:815` |
| glog | 0.4.0 | `CMakeCache.txt:780`（`pkg-config` 模块名 `libglog`，11-17 待复核） |
| libjpeg | `libjpeg-dev` 8c-2ubuntu10 | `dpkg -l`（11-17） |
| libusb | `libusb-1.0-0-dev` 2:1.0.25-1ubuntu2 | `dpkg -l`（11-17） |
| nlohmann-json | `nlohmann-json3-dev` 3.10.5-2 | `dpkg -l`（11-17） |
| OpenCV | 4.5.4（`libopencv-dev` 4.5.4+dfsg-9ubuntu4） | `CMakeCache.txt:741`；`dpkg -l`（11-17） |
| Eigen3 | `/usr/include/eigen3` | `flags.make` |
| CMake/GCC/Python | 3.22.1 / gcc 11 / 3.10.12 | `CMakeCache.txt` |
| 实际构建 | Debug + `-O3`（`-fPIC -O3 -g`） | `flags.make`；install 日志 |
| 安装前缀 | `/home/lin/astra_ws/install/astra_camera` | `CMakeCache.txt:127` |
| OpenNI2 分发 | `openni2_redist/{x64,arm64,arm}` 均存在 | install 日志；二进制文件核验 |
| udev | `/etc/udev/rules.d/56-orbbec-usb.rules`，MODE 0666；sha256 `d853072e0ea92e6a134831ee9628e13916f8d7badcd6f1cd6a5bcc0c616f3818` | 规则文件；`sha256sum`（11-17） |
| lsusb（11-17） | 19:51 首测无输出（未接/未直通）；20:48 复测正常：`2bc5:0403`（ASTRA Pro）+ `2bc5:0501`（Astra Pro HD Camera），Bus 003、480M | 用户终端输出；`dmesg -T` |
| USB 速率 | 两个接口 `bcdUSB=2.00`、`speed=480`；`authorized=1`；颜色 `3-2`、深度 `3-4.1` | `/sys/bus/usb/devices/...`（11-17） |
| `.bashrc` | 第 133 行 `source ~/astra_ws/install/setup.bash` | `~/.bashrc` |
| 源码 VCS | 未发现 `.git/HEAD`（按“解压文件夹”） | `.git/HEAD` 不存在 |

## 附录 B：检查命令与 2026-11-17 实跑结果

以下命令用于补齐 §8 的核验项。**`pkg-config` 的 glog 模块名是 `libglog`**（`CMakeLists.txt:48` 为 `pkg_search_module(GLOG REQUIRED libglog)`），写成 `glog` 会误报 “not found”；`libuvc` 是源码安装，`dpkg -l` 查不到属预期。

```bash
# 源机：逐包版本（§8 #2/#3/#4/#6）
dpkg -l | grep -E 'libgflags-dev|libgoogle-glog-dev|libusb-1.0-0-dev|libeigen3-dev|nlohmann-json3-dev|libopencv-dev|libjpeg-dev'

# 逐个查，避免一个模块缺失导致整条命令无输出
for m in libuvc libglog opencv4; do
  printf '%s: ' "$m"
  pkg-config --modversion "$m" || echo MISSING
done

# 源机：当前设备枚举（§8 #14；必须先插相机）
lsusb | grep -i 2bc5
# 若要看速率（USB3 证据）：
# 先 lsusb -t 找到 Bus/Port，再 cat /sys/bus/usb/devices/<bus>-<port>/speed

# 源机：udev 规则哈希（迁移前后对照）
sha256sum /etc/udev/rules.d/56-orbbec-usb.rules

# 文档链接校验（仓库根；不要在 ~ 下执行）
cd ~/Lin_workspace/r2_integration && python3 scripts/check_doc_links.py .
```

**2026-11-17 用户实跑结果（原始输出见 `doc/raw_data/raw_astra_ws_dep_check_2026-11-17_1951.txt`）**：

| 检查 | 结果 | 判定 |
|:---|:---|:---|
| `libopencv-dev` | `4.5.4+dfsg-9ubuntu4`（`ii`） | ✅ 与源机构建一致 |
| `libjpeg-dev` | `8c-2ubuntu10`（`ii`） | ✅ |
| `libusb-1.0-0-dev` | `2:1.0.25-1ubuntu2`（`ii`） | ✅ |
| `nlohmann-json3-dev` | `3.10.5-2`（`ii`） | ✅ |
| `libuvc` | `dpkg` 无记录 | ✅ 预期（源码装 `/usr/local`）；以 `pkg-config --modversion libuvc` 复核 |
| glog | `pkg-config glog` 报 not found | ⚠️ **模块名写错**；应查 `libglog`（源机构建 cache 为 0.4.0） |
| udev 规则 | `d853072e0ea92e6a134831ee9628e13916f8d7badcd6f1cd6a5bcc0c616f3818` | ✅ 规则文件存在；目标机装同版本应一致 |
| `lsusb` + `grep -i 2bc5` | 19:51 无输出；20:48 复测两行 | ✅ 复测正常（`0403` + `0501`，Bus 003、480M） |
| 文档链接校验 | `python3: can't open file '/home/lin/scripts/...'` | ⚠️ 在 `~` 下执行；按上面 `cd` 到仓库根重跑 |
