# Astra Pro 核验与 Tornado D2 资产评估：R2 不纳入决策（2026-11-17）

> 日期：2026-11-17
> 任务：核验 Astra Pro / `astra_ws` 环境；评估 `~/Desktop/tornado_d2_driver` 的文档与代码是否迁入 R2
> 状态：✅ 决策关闭——**R2 不纳入 Astra Pro / Tornado D2；不迁移文档或代码；现有文件保持现状**
> 关联：[Astra Pro 驱动手册](../camera/astra-pro-driver-guide.md)｜[astra_ws 迁移手册](../camera/astra-ws-migration-guide.md)｜[两车架构](../two-car-architecture.md)｜[厂商环境文档](../camera/1、环境搭建.md)
> 证据落位：`doc/raw_data/raw_astra_ws_dep_check_2026-11-17_1951.txt`、`doc/raw_data/raw_astra_usb_enum_2026-11-17_2048.txt`（本地，不入 git）
> 外部项目：`~/Desktop/tornado_d2_driver`（Tornado D2 兼容工程，独立于 R2；本文只评价，不复制其文件）

---

## 一、结论先行

1. **用户 2026-11-17 拍板**：原话“r2不考虑astrapro,tornado ，保持现状即可”——Astra Pro 与 Tornado D2 不进入 R2 的架构、文档主线、代码仓或迁移计划。
2. **Astra Pro 硬件事实已核验**：本机两个接口都是 **USB 2.0**（`bcdUSB=2.00`、`speed=480`），ID `2bc5:0403`（深度/IR）+ `2bc5:0501`（彩色 UVC）；`lsusb -t` 显示 480M 属正常，不是“USB 3.0 未接好”。
3. **首测无枚举不是 tornado 程序破坏**：19:51 首测 `lsusb` 为空时相机尚未接入/直通；20:48 插好后正常枚举。系统侧 `uvcvideo` 已加载、无 blacklist、`authorized=1`，当前无 tornado/astra/ros 进程；`dmesg` 只有正常枚举，无 disconnect/reset/over-current。
4. **Tornado 资产不迁移**：其五篇文档与代码中，只有少量 Astra Pro/通用相机经验可参考；D2 补丁驱动、SDK、闭源 `.so`、玩具 ICP、build/install/log、备份均不迁入 R2。R2 现有 `doc/camera/` 文档保持原样。
5. **R2 主线不变**：仍按 [two-car-architecture.md](../two-car-architecture.md) 的“老车 LD06 2D / 新车 MID-70 + D435”推进；Astra/Tornado 仅作为外部独立项目留存。

---

## 二、Astra Pro 核验事实

### 2.1 USB 枚举与设备属性

| 项 | 实测 | 证据 |
|:---|:---|:---|
| 彩色 | `2bc5:0501`，`Astra Pro HD Camera`，Bus 003、480M | `lsusb`；`dmesg -T` 20:48:25 |
| 深度/IR | `2bc5:0403`，`ASTRA Pro`，Bus 003、480M，挂在虚拟 Hub 下（`3-4.1`） | `lsusb`；`dmesg -T` 20:48:27 |
| 设备 USB 代际 | 两个接口均 `bcdUSB=2.00`、`speed=480` | `/sys/bus/usb/devices/3-2/version`、`3-4.1/version` |
| 授权状态 | 两个接口 `authorized=1` | 同名目录下 `authorized` |
| 内核驱动 | 彩色 `uvcvideo`；深度为 vendor-specific（OpenNI2 路径，无内核驱动属正常） | `lsusb -t`；`/proc/modules` |
| 掉线/错误 | 本次 `dmesg` 仅正常枚举，无 disconnect/reset/over-current | `dmesg -T` |

时间线：

- 19:51 首测：`lsusb | grep -i 2bc5` 无输出，`lsusb -t` 只有 root hub；当时不能据此判断设备坏或驱动坏。
- 20:30：本次开机。
- 20:48：插好/直通后正常枚举，两接口都在。

> 结论：**480M 是 Astra Pro 的设备上限，不是接线错误**。厂商文档里“虚拟机需保证 USB3.0 连接”应按控制器兼容/供电理解，不能按设备速率理解；不要以 Bus 004 的 5000M/20000M 作为验收判据。

### 2.2 tornado 嫌疑排查

| 检查 | 结果 |
|:---|:---|
| 运行进程 | 当前用户会话无 `tornado`/`astra`/`ros` 进程：tilix 三个 shell 均无子进程，VSCode 子进程为 `code` 自身/扩展宿主；PID 1 子进程均为系统服务 |
| 内核模块 | `uvcvideo` 已加载、引用计数 0；无 USB 相关异常模块 |
| 内核 cmdline | 无 `nousb`、无 `module_blacklist` |
| modprobe | `blacklist.conf` 未黑名单 `uvcvideo`；`uvcvideo.conf` 不存在 |
| udev | `56-orbbec-usb.rules` 为正常 `MODE 0666` 规则，无 `authorized=0`/`RUN` 干扰 |
| USB 授权 | 两接口 `authorized=1` |
| `dmesg` | 无 disconnect/reset/over-current；仅正常枚举 |

**判断**：普通用户态程序（ROS 节点、libusb 程序）即使占用相机，最多导致 `astra_camera` 打开时报“设备忙”，**不会让已枚举设备从 `lsusb -t` 消失**；若程序反复 reset 设备，`dmesg` 会留下 disconnect/reset 记录，本次没有。因此没有证据指向 tornado 程序；更符合“当时未接/未直通 + 中间重启”的解释。

### 2.3 环境文档核验结论

对 [1、环境搭建.md](../camera/1、环境搭建.md) 的逐条核验详见 [迁移手册 §8](../camera/astra-ws-migration-guide.md)；本次结论摘要：

- **须修正 4 处**：`sudo chmod 777 *` 多余且不安全；`sudo vim ~/.bashrc` 有属主风险；`-DCMAKE_BUILD_TYPE=Release` 被 `CMakeLists.txt` 强制 Debug 覆盖；Astra Pro Plus 文件名应为 `astro_pro_plus.launch.xml`。
- **须补充 4 类**：OpenCV/完整 ROS 依赖；`libjpeg-dev`；libuvc 版本固定（0.0.7）；首启 `color_info_url:=""`（默认 `config/` 未安装，会报 calibration ERROR，四路仍可用）。
- **链接校验残留（2026-11-17）**：全仓 1549 条链接、缺失 7 条，全部是 `1、环境搭建.md` 引用的厂商原图（`image-20230301*.png`）未随文档提供；属既有坏链，迁移手册 §8 已记录，按“最小干预”保留原文，不伪造图片。

---

## 三、Tornado D2 资产评价（不迁移）

### 3.1 文档

| 文档 | 有用内容 | 判断 |
|:---|:---|:---|
| `~/Desktop/tornado_d2_driver/docs/项目梳理与相机启动指南.md` | 两套环境隔离、D2/Astra 启动前置、话题/TF/参数、排障 | 部分可参考；D2 专属内容保持外部 |
| `~/Desktop/tornado_d2_driver/docs/驱动修改.md` | 闭源 `liborbbec.so` 的 VID/PID 字节补丁、`orbbec.ini`、CameraInfo 修正 | D2 专属，不迁；仅补丁方法可作外部参考 |
| `~/Desktop/tornado_d2_driver/docs/SDK与ROS.md` | D2 SDK API、量程/标定限制、D2 vs D435 对比 | 少量通用经验可参考；代码不迁 |
| `~/Desktop/tornado_d2_driver/docs/多流演示.md` | D2 多流、玩具 ICP、深度伪彩色 | 不迁 |
| `~/Desktop/tornado_d2_driver/docs/建图入门.md` | depth→scan→TF→slam_toolbox 链路 | 不迁；R2 已有同类文档 |

> 文档自身存在阶段差异（如 `orbbec.ini` 哈希、CameraInfo 数值、Astra Pro“未复测”表述），整篇复制会把历史矛盾带进 R2；应保持外部项目原貌。

### 3.2 代码/资产

| 资产 | 性质 | 判断 |
|:---|:---|:---|
| `ros2_ws/src/ros2_astra_camera`（补丁版） | 官方驱动 + D2 本地修改；含嵌套 `.git`、闭源 `liborbbec.so` | 不 vendor 整树；需要时用上游 + `.patch` |
| `ros2_ws/src/d2_toy_mapper` | 玩具 ICP，无回环/IMU | 不迁；R2 已有 LIO/SLAM |
| `sdk/` | D2 最小 C++ SDK，含 OpenNI2/`liborbbec.so` 二进制 | 不迁 |
| `tools/depth_colormap.py` | 通用 `16UC1` 深度伪彩色显示 | 可选；R2 当前无深度相机主线，暂不迁 |
| `run_depth_to_scan.sh` | 通用 depth→`/scan` 桥接 | 可选/低优先；R2 老车用 LD06 |
| `config/`、`*.rviz` | D2 专用点云调参/RViz | 不迁 |
| `libuvc/`、`libuvc_build/`、`local/` | 第三方源码 + 构建 + 本地安装前缀 | 不迁；只记录版本 |
| `official_ros2_astra_camera/` | 未修改官方对照副本 | 不迁 |
| `build/`、`install/`、`log/`、`*_bak_*` | 构建产物/日志/备份 | 绝不迁 |

### 3.3 不迁入 R2 的理由

1. **架构范围**：当前两车架构未列入 Astra Pro/D2；整包迁入等于新增第三条硬件支线，违背“先端到端、一超多强”。
2. **仓库结构**：R2 的 ROS2 包在工区根目录平铺；tornado 是 `ros2_ws/src/...` 嵌套结构并含嵌套 `.git`，迁入需拆目录/去 `.git`，破坏上游 diff。
3. **重名包**：`astra_camera` 已存在于 `~/astra_ws` 与 tornado `ros2_ws`；再入 R2 会加剧 `ros2 pkg prefix` / `.bashrc` source 顺序歧义。
4. **许可证**：`liborbbec.so`、OpenNI2 头文件/运行库为闭源或第三方；tornado 文档已提醒公开前核对再分发权，R2 不入库这类二进制。
5. **构建产物/可移植性**：`build/install/log`、`local/`、备份均为 x86_64/本机路径产物，跨机/跨架构不可用。
6. **文档单一事实源**：R2 已有 Astra Pro 手册 + 迁移手册；复制 tornado 五篇会形成第二套说法，且导入 D2 专属/历史阶段内容。
7. **维护成本**：D2 补丁绑定官方二进制版本/偏移，上游一换就要重做；R2 没有 D2 硬件时是纯负债。

---

## 四、决策与边界（用户拍板）

> 用户原话：**“r2不考虑astrapro,tornado ，保持现状即可”**（2026-11-17）。

| 方案 | 内容 | 影响 | 本次选择 |
|:---|:---|:---|:---:|
| A. 仅外链/不迁移 | 不复制任何 tornado 文件；R2 现有相机文档保持原样 | 最低风险、零维护 | ✅ **采用**（按“保持现状”） |
| B. 文档提炼 | 把 Astra/通用经验并入 R2 现有 `doc/camera/` | 需改 R2 文档、有双源风险 | — |
| C. B + 通用工具 | 迁移 `depth_colormap.py` 等 | 需测试/许可头 | — |
| D. 整包 vendor | 驱动/SDK/配置/文档全搬 | 架构/许可/仓库结构风险高 | — |

**成果保留清单**：

- R2 现有 [Astra Pro 驱动手册](../camera/astra-pro-driver-guide.md)、[astra_ws 迁移手册](../camera/astra-ws-migration-guide.md)、[厂商环境文档](../camera/1、环境搭建.md) **原样保留**，不删除、不改写。
- `tornado_d2_driver` 继续保留在外部，不复制、不移动；本次不再改其文件。
- `doc/camera/tornado-d2-driver-guide.md` 为 11-17 既有本地留档，**保留不等于 R2 架构纳入 D2**；其代码仍不迁移。
- 两份 raw_data 原样保留在 `doc/raw_data/`（不入 git）。
- 不执行 git add/commit/push。

---

## 五、方法模板（可复用）

### 5.1 USB 设备在 VM 中未被识别：分层诊断卡

```text
① 先看全局：lsusb / lsusb -t
   - 只有 root hub、无子节点 → 先判“设备未接入/未直通”，不要先改 udev/驱动
② 看主机：Windows 设备管理器 / 主机 Linux lsusb
   - 主机能看到、VM 看不到 → VMware Removable Devices 直通问题
③ 看 VM 设置：USB Controller 启用；必要时 USB 3.0；改后重启 VM
④ 插拔看内核：sudo dmesg -T | tail -80
   - 无 "new ... USB device" = 物理/直通层；有 idVendor=2bc5 = 已枚举
⑤ 看设备代际：/sys/bus/usb/devices/<dev>/version + speed
   - 设备 bcdUSB=2.00/480M ≠ 端口/根 hub 的 5000M；不要以端口速率判设备
⑥ 排查“程序搞坏”嫌疑：
   - ps 看进程；/proc/modules 看 uvcvideo；/proc/cmdline 看 nousb/module_blacklist
   - dmesg 看 disconnect/reset/over-current；用户态程序不能让已枚举设备从 lsusb 消失
```

### 5.2 外部项目资产迁移评价卡

```text
① 先问架构：目标项目真的用这个硬件/功能吗？在哪个阶段、哪台设备？
② 三分资产：文档 / 源码 / 二进制与构建产物（三者风险不同）
③ 查许可：闭源 .so、第三方头文件/运行库是否允许再分发
④ 查仓库结构：嵌套 git、重名包、构建产物、备份目录、包布局是否兼容
⑤ 算价值/风险：只迁移“目标项目需要且能维护”的部分；文档优先提炼，代码优先外部引用
⑥ 用户拍板后再动：不在未定架构时做投机性 vendor；变更后同步 README/索引/校验器
```

---

## 六、经验点清单（层次已标注）

| # | 经验点 | 建议去向 |
|:--|:---|:---|
| E1 | **USB 设备代际看设备自身 `bcdUSB`/`speed`，不看端口/root hub 速率**；Astra Pro 实测 2.00/480M，避免把“没挂 5000M”误判为接线错误 | draft 层（USB/设备核验主题）；规则层候选 → [ros2-ops.md §7](../ros2-ops.md) 邻域 |
| E2 | **`lsusb -t` 只有 root hub = 上游接入/直通层问题**，不是 udev/驱动/ROS；先查主机与 VM 直通，再查内核 | draft 层；规则层候选 → [ros2-ops.md §7](../ros2-ops.md) |
| E3 | **用户态程序不能让已枚举 USB 设备从 `lsusb` 消失**；怀疑程序干扰需 `dmesg` 的 disconnect/reset/over-current 证据 | draft 层；规则层候选 → [ros2-ops.md §7](../ros2-ops.md) |
| E4 | **跨项目资产迁移先做文档/源码/二进制三分**，再按架构、许可、仓库结构、重名包评估；不整包 vendor | draft 层（迁移方法主题）；规则层候选 → [doc-engineering.md §八](../doc-engineering.md) 邻域 |
| E5 | **R2 不纳入 Astra Pro/Tornado，保持外部项目与现有文档原样**；避免双源与投机性集成 | 事件层留存（本文）；项目决策已由用户拍板 |
| E6 | **Bash 权限受限时可用只读 `/proc` 进程树 + `/sys` 设备属性取证**（进程名字、模块、cmdline、USB 版本/速率/授权） | draft 层（工具/排障方法）；跨项目复用 2+ 次后再抽规则层 |

> 按 [doc-engineering §十二](../doc-engineering.md) 四层制：本表做事件层留档与去向标注；单事件经验不直接写规则层，成熟候选在后续盘点时再落 draft/规则层（本次不改 `analysis-methods.md`）。

---

## 七、状态同步与限制

### 7.1 状态文档核对

- [07-handover.md](../07-handover.md)：无 Astra Pro/Tornado 条目，**无需改**。
- [pending-tasks.md](../pending-tasks.md)：无 Astra Pro/Tornado 待办，**无需改**。
- [two-car-architecture.md](../two-car-architecture.md)：仍为老车 LD06 / 新车 MID-70 + D435，**无需改**。
- `02-progress.md` / `03-current-state.md`：不涉及 Phase 进度，**本次不改**。
- 根 [README.md](../../README.md) 文件树 + [retrospect/README.md](README.md) 索引：已登记本文。

### 7.2 限制

- 目标机迁移全流程未实测；本文只记录源机 VM 事实。
- Bash 权限受限：未能执行 `du`/`find`/`git`/链接校验器；进程与 USB 事实通过 `/proc`、`/sys`、`dmesg` 用户输出与已读文档核对。
- 未复制、未移动 tornado 文件，也未提交任何改动；本次仅新增本事件档并同步两处索引；R2 现有相机文档未改，tornado 文件未再改动。
