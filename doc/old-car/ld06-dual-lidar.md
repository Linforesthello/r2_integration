# LD06 单/双雷达执行计划（老车）

> 日期：2026-11-06
> 任务：老车平替 S1/S2 的 LD06 接入——**先在 VM 完成双雷达基本功能与串口固定**，再交 N97 部署
> 状态：✅ VM 阶段验收完成（2026-11-06，V1~V6 通过）；✅ N97 交接前置完成（udev 四路固定 + 构建，2026-11-06）；✅ N97 双实例运行实测 10Hz（2026-11-06 19:21，`/scan_a` 10.000 Hz / `/scan_b` 10.002 Hz）；✅ N97 重启复验（2026-11-07 11:25，udev 四路仍指向正确 serial）；✅ LD06 `/scan` 规格与 angle crop 实测（2026-11-07，见 P7）；⏳ N97 供电长跑待测
> 回填：2026-11-06（VM 执行结果、参数快照、已知限制；N97 udev/构建实测）；2026-11-07（N97 重启复验 + `/scan` 规格/crop 实测，见 P7）
> 上位文档：[two-car-architecture.md §三/§八](../two-car-architecture.md)
> 事件记录：[2026-11-06 LD06 VM 接入与冒烟](../retrospect/2026-11-06_ld06_vm_bringup_smoke.md)
> 原始数据：`doc/raw_data/raw_ld06_*`（本地，不入 git）

---

## 一、定位与边界

**VM 先行只验证「与机器无关的软件契约」**：双节点参数化、双路并发、串口固定、TF/话题隔离、
双雷达互扰初筛。它**不构成 S1 验收**——供电长跑、N97 端口组合、实车几何、EKF 基线对照
仍必须在 N97/实车完成（判据口径见 [standards §1.15](../standards.md)）。

| 项 | VM 可做 | VM 不可替代 |
|:---|:---|:---|
| 双节点参数化 / 话题 / frame | ✅ | — |
| 双路并发、数据不串 | ✅ | — |
| udev 规则机制（按 J-Link serial） | ✅（同一批 J-Link 规则可复用到 N97） | N97 上 G354/CAN 的 serial 组合需另加 |
| 双雷达光学互扰 | ✅ 初筛 | 真实间距/角度/环境光需实车 |
| 供电/接触长跑 | ⚠️ 仅 USB 侧 | 车体 5V 来源、接头、PSV 压降需实车测 |
| 安装几何 / 盲区 / 地面杂波 | ❌ | 实车安装后实测 |
| EKF 基线对照、5×5m 探索验收 | ❌ | N97 + 实车底盘 |

---

## 二、已验证基线（2026-11-06 16:20，VM）

| 设备 | tty（16:20 快照） | J-Link serial | USB 路径 |
|:---|:---|:---|:---|
| LD06-A | `/dev/ttyACM0` | `000063728672` | Bus3 Port2（根口） |
| LD06-B | `/dev/ttyACM1` | `000063728647` | Bus3 → 12M Hub → Port1 |

已核对事实：

- 两个 J-Link 均为 `1366:0105`，**serial 不同**；均 12 Mbps，`bMaxPower=100mA`。
- 当前用户 `lin` 在 `dialout` 组，`/dev/ttyACM*` 权限正常；无进程占用端口。
- `ros2 pkg prefix ldlidar_stl_ros2` → `~/Lin_workspace/r2_integration/install/ldlidar_stl_ros2`（r2 仓内包，非外部旧工作区）。
- **枚举顺序已漂移**：`...8647` 在 11-06 14:06 首测时是 `ACM0`，本次变为 `ACM1`——坐实不能按 ttyACM 编号写死，必须 by-id/udev。
- 历史事件：单雷达运行 18m36s 后掉电（蓝灯灭/停转，重插恢复），判定为供电/接触侧，非驱动/波特率；
  2026-11-06 用户确认根因为**接线端子松动掉出**（[事件记录 §五](../retrospect/2026-11-06_ld06_vm_bringup_smoke.md)）。
- **已确认（2026-11-06，udev 固定）**：A = serial `000063728672`，B = serial `000063728647`；
  单颗拔插不串号（P0.5）。

**N97 实测基线（2026-11-06 18:49~18:52）**：

| 设备 | tty（N97 当时） | serial | udev 固定名 |
|:---|:---|:---|:---|
| G354 IMU | `/dev/ttyACM0` | `000063728613` | `/dev/r2_g354` |
| CANable2（USB-CAN/slcan） | `/dev/ttyACM1` | `208C37AF4845` | `/dev/r2_can` |
| LD06-A | `/dev/ttyACM2` | `000063728672` | `/dev/r2_ld06_a` |
| LD06-B | `/dev/ttyACM3` | `000063728647` | `/dev/r2_ld06_b` |

- N97 的 ACM 编号与 VM 完全不同（VM 为 ACM0/ACM1），**再次实锤不能按 tty 编号写死**；四条链接均经
  `readlink -f` + `udevadm info` 核对到正确 serial。
- CANable2 不是 J-Link：VID:PID `16d0:117e`，规则单独按该 VID/PID + serial 匹配。

---

## 三、执行步骤

### P0 基线核对（✅ 已完成）

- [x] 两路 J-Link 同时识别，serial 唯一
- [x] ttyACM 权限、无进程占用
- [x] r2 仓内包可解析
- [x] 枚举顺序漂移证据留档

### P0.5 物理标签与 serial 映射（✅ 已完成，2026-11-06）

1. 只保留一颗上电，运行 P2 中的单实例命令，确认 `/scan` 有数据；
2. 遮住该颗，确认数据消失——确认当前 serial 对应的物理雷达；
3. 把 `serial → A/B` 记入本文件下表；物理外壳贴 `A` / `B` 标签（建议补贴，防换线搞混）：

| 物理标签 | J-Link serial | udev 符号链接 | 用途 |
|:---|:---|:---|:---|
| A | `000063728672` | `/dev/r2_ld06_a` | `/scan_a` + `laser_a` |
| B | `000063728647` | `/dev/r2_ld06_b` | `/scan_b` + `laser_b` |

> 目的：udev 规则与 launch 参数按「物理角色」而不是「当前 tty」绑定；换机器/重插不串。
> ttyACM 编号会漂移，仅以 udev 名为准；建议在 J-Link 外壳补贴 A/B 标签。

### P1 launch 参数化（✅ 已完成，2026-11-06）

**动机**：原 [`ld06.launch.py`](../../ldlidar_stl_ros2/launch/ld06.launch.py) 写死
节点名 `LD06`、话题 `scan`、frame `base_laser`、端口 `/dev/ttyACM0`、TF z `0.18`。
两个实例直接跑会**节点重名 + `/scan` 双发布者混流**。

**改动点（实际落地）**：

- 新增 9 个 `DeclareLaunchArgument`：`node_name` / `topic_name` / `frame_id` / `port_name` /
  `port_baudrate` / `z` / `yaw` / `pitch` / `roll`；**2026-11-08 补 `x` / `y`（共 11 个）**——
  此前平移 x/y 在 `arguments` 里写死 `'0','0'`，G10 实测后必须可传；
- 静态 TF 节点名随 `frame_id` 派生（`base_link_to_<frame>_ld06`），避免两个 static TF 节点重名；
- `port_baudrate` 用 `ParameterValue(..., value_type=int)` 传，避免 LaunchConfiguration
  的字符串类型不匹配；
- **默认端口改为 `/dev/r2_ld06_a`**（原 `/dev/ttyACM0`），依赖 udev 符号链接；节点名/话题/frame
  的默认值保留。

**参数默认值（以 launch 文件为准）**：

| 参数 | 默认值 | 说明 |
|:---|:---|:---|
| `node_name` | `LD06` | 多实例必须覆盖 |
| `topic_name` | `scan` | 多实例必须覆盖 |
| `frame_id` | `base_laser` | 多实例必须覆盖 |
| `port_name` | `/dev/r2_ld06_a` | udev 符号链接；B 实例需覆盖 |
| `port_baudrate` | `230400` | int |
| `x` | `0.275` | 2026-11-08 实车实测（G10） |
| `y` | `0.29` | 2026-11-08 实车实测（G10） |
| `z` | `0.04` | 2026-11-08 实车实测（光学中心离地 16cm − base_link 12cm）；原占位 `0.18` |
| `yaw` | `-1.5708` | 2026-11-08 实测（模块 0° 指向车体 −y）；原占位 `0.0` |
| `pitch` / `roll` | `0.0` | 按水平安装，未单独量测 |

**验收结果（2026-11-06）**：

- [x] `colcon build --packages-select ldlidar_stl_ros2` 通过，install 副本含 9 个 launch 参数；
- [x] 单实例默认启动：`/scan`、`base_laser`、rviz2 正常（V6）；
- [x] 双实例覆盖后 topic/frame/port 均生效（P2）。
- 已知限制：`ros2 param get/list/set` 不可用（驱动主循环不 spin 参数服务）；参数验证以启动日志
  的 9 行 `<port_name>` 等为准，详见 §五。

> 改 launch 后必须 `colcon build --packages-select ldlidar_stl_ros2` 再 `source install/setup.bash`
> （launch 装在 install 副本，[ros2-ops §2](../ros2-ops.md)）。

### P2 双实例冒烟（✅ 已完成，2026-11-06）

```bash
source /opt/ros/humble/setup.bash
source ~/Lin_workspace/r2_integration/install/setup.bash

# 终端 1：A（使用默认 /dev/r2_ld06_a）
ros2 launch ldlidar_stl_ros2 ld06.launch.py \
  node_name:=ld06_a topic_name:=scan_a frame_id:=laser_a

# 终端 2：B（显式指定 udev 符号链接）
ros2 launch ldlidar_stl_ros2 ld06.launch.py \
  node_name:=ld06_b topic_name:=scan_b frame_id:=laser_b \
  port_name:=/dev/r2_ld06_b
```

验证：

```bash
ros2 topic hz /scan_a                  # 预期 ~10Hz
ros2 topic hz /scan_b                  # 预期 ~10Hz
ros2 topic info -v /scan_a             # Publisher 1；frame_id=laser_a
ros2 topic info -v /scan_b
ros2 topic echo /scan_a --field header.frame_id --once
```

隔离性：遮住 A，观察 `/scan_b` 的距离分布/频率不变；反向再测一次。
数据不串：两路 `ranges`/`intensities` 长度与内容独立，`/scan_a` 无 B 的数据。

**实测结果（2026-11-06）**：

- 节点：`/ld06_a`、`/ld06_b`、`/base_link_to_laser_a_ld06`、`/base_link_to_laser_b_ld06`
  各 1 个，无重名；
- 话题/frame：`/scan_a`→`laser_a`、`/scan_b`→`laser_b`；`ros2 topic info -v` 各 Publisher 1
  （RELIABLE / VOLATILE）；
- 频率：两路约 10Hz；6s 稳态探针 A 10.01Hz、B 9.76Hz（B 偶发单帧缺口）；
- 隔离：遮挡 A 不影响 B，反向同样（用户实测 PASS）；
- 数据不串：两路独立（用户实测 PASS）；
- 长跑：≥30 min 不掉电（用户实测；历史掉电根因见 §五）。

> 注：`ros2 topic hz` 的 min/max/std 是启动以来累计窗口，启动瞬态会一直留在统计里；
> 判稳态用独立探针或看 window 增长后的增量。

### P3 udev 固定名（✅ 已完成，2026-11-06）

```bash
sudo tee /etc/udev/rules.d/99-r2-serial.rules >/dev/null <<'EOF'
# J-Link VCOM（1366:0105），按 serial 固定物理角色
SUBSYSTEM=="tty", ATTRS{idVendor}=="1366", ATTRS{idProduct}=="0105", ATTRS{serial}=="000063728672", SYMLINK+="r2_ld06_a", MODE="0666", GROUP="dialout"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1366", ATTRS{idProduct}=="0105", ATTRS{serial}=="000063728647", SYMLINK+="r2_ld06_b", MODE="0666", GROUP="dialout"
# N97 一并追加（S1 起固定）：
# SUBSYSTEM=="tty", ATTRS{serial}=="<G354_SERIAL>", SYMLINK+="r2_g354", ...
# SUBSYSTEM=="tty", ATTRS{serial}=="<CAN_SERIAL>",  SYMLINK+="r2_can",  ...
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=tty
ls -l /dev/r2_ld06_a /dev/r2_ld06_b
```

**验收**：重插拔 + 重启后符号链接仍指向正确物理雷达；launch 改用 `r2_ld06_a/b` 后两路正常。

**实测结果（2026-11-06）**：

- [x] `ls -l /dev/r2_ld06_a /dev/r2_ld06_b` 符号链接存在，分别指向 serial `...8672` / `...8647`；
- [x] 单颗拔插后不串号（用户实测 PASS）；
- [x] launch 使用 `r2_ld06_a/b` 双路正常（P2）；
- [ ] 重启复验未单独记录（规则已落盘，可补一次 reboot 验证）；**N97 已复验（2026-11-07，见下），VM 未单独复验**。

**N97 实测（2026-11-06）**：

- [x] `/etc/udev/rules.d/99-r2-serial.rules` 已装，含 4 条规则（G354 / CANable2 / LD06 A / LD06 B）；
- [x] `ls -l /dev/r2_*` 四条链接均存在，指向正确 serial（对照表见 §二）；
- [x] 规则按本机 serial 重写，未直接照搬 VM 文件（N97 的 G354/CAN serial 与 VM 不同）；
- [x] **N97 重启复验（2026-11-07 11:25）**：重启后四条链接仍存在且指向正确 serial（G354 `...8613`、
  CAN `208C37AF4845`、LD06-A `...8672`、LD06-B `...8647`）；ACM 编号再次变化——G354=ACM2、CAN=ACM3、
  LD06-A=ACM0、LD06-B=ACM1（与 2026-11-06 的 ACM0/1/2/3 完全不同）→ **固定名方案有效，禁止按 ttyACM 编号写死**。

**坑位**：

- 克隆 J-Link 可能 serial 相同（本批不相同）；若遇到，改用 `ENV{ID_PATH}` 按 USB 物理口固定。
- J-Link 换机器后 serial 不变，**规则可复用到 N97**；但 N97 的 G354/CAN 是另外的 J-Link，须补 serial。

### P4 TF 与 rviz 双显示（✅ 已完成，2026-11-06）

- 每颗雷达一个 `base_link → laser_a/laser_b` 静态 TF，z 先用 `0.18` 占位；
- 两个 static TF 节点名必须不同（随 frame 派生）；
- rviz：Fixed Frame `base_link`，两个 LaserScan display 分别订阅 `/scan_a`、`/scan_b`，颜色区分；
- 注：包内 `rviz2/ldlidar.rviz` 的 `Yaw≈179.6°`、Intensity/彩虹色、Size 3 px 均为**显示配置**，
  不是数据反向（[事件记录 §六](../retrospect/2026-11-06_ld06_vm_bringup_smoke.md)）。

**验收**：TF 树只有一个父、无重复 `base_link→laser_*`；两路点云/扫描同时可见。

**实测结果（2026-11-06）**：`tf2_echo base_link laser_a/laser_b` 均输出 Translation
`[0, 0, 0.180]`、RPY `[0, 0, 0]`；rviz2 两路 LaserScan 同时可见（用户实测）。
`tf2_echo` 开头 `Invalid frame ID "base_link"` 是 tf_static 发现前的正常等待，不是错误。

### P5 双雷达互扰初筛（✅ 已完成，2026-11-06）

方法：两颗同高度、扫描平面相交放置，对同一墙面；

1. 单开 A 60s，记录 `ranges` 分布/最小值；
2. 单开 B 60s；
3. 双开 60s，对比三组分布。

**判据**：双开相对单开无系统性鬼影簇、无距离整体偏移、无频繁丢帧/超时。
若出现互扰：记录现象与摆位，优先改高度/角度错开；LD06 无软件分时参数，不能靠改驱动解决。

**实测结果（2026-11-06）**：双开实测无异常（用户结论）；未留三组量化分布数据。
VM 摆位不代表实车，实车安装后按同法复验（或标注为 VM 初筛结论）。

### P6 交接 N97（⏳ 进行中，2026-11-06）

1. [x] N97 `git pull` 到 `4860c2c`；`colcon build --packages-select ldlidar_stl_ros2` 通过
   （install 副本含 9 参数 launch 与可执行节点）；
   - 构建 stderr 有 CMake 弃用警告（上游 `cmake_minimum_required(VERSION 3.5)`，N97 CMake 3.22.1），
     **非错误、不影响产物**；保持 vendor 原样，未来 CMake 4 报错再评估改 3.10（见 §五）；
2. [x] 写 udev：G354 + CAN + 两颗 LD06 四路固定（serial 见 §二；规则内容见 P3）；
3. [x] 接线后 N97 双实例运行实测（2026-11-06 19:21，进程已连续运行 8m35s）：
   - `/scan_a` **10.000 Hz**（min/max 0.100s，std 0.00010s，window 65）
   - `/scan_b` **10.002 Hz**（min/max 0.099~0.100s，std 0.00020s，window 65）
   - frame：`laser_a` / `laser_b`；`ros2 topic info -v` 各 Publisher 1（RELIABLE / VOLATILE）
   - 节点：`/ld06_a`、`/ld06_b`、两个 `base_link_to_laser_*_ld06` 静态 TF 节点各 1，无重名
   - 对应 VM 侧 B 路 9.76Hz 的单帧缺口在 N97 未复现（两侧摆位/线材不同，仅记录不归因）；
4. [ ] **供电长跑 ≥30 min**：带载测 PSV 4.5~5.5V、查 GND/接头/5V 来源；不要依赖 J-Link 的 5V 给雷达供电，
   建议雷达独立 5V + 共地；
5. [ ] 通过后再进 S1（slam_toolbox + Nav2 + explore_lite）。

### P7 LD06 `/scan` 规格与 angle crop 实测（✅ 已完成，2026-11-07，N97）

**动机**：S1 的 `slam_toolbox` / Nav2 / 覆盖率脚本需要真实波束数、角分辨率与量程边界；此前只有驱动消息字段
（`range_max=25`），不能当传感器规格（[standards §1.8](../standards.md)）。

**方法**：N97 本地直接 `ros2 run ldlidar_stl_ros2 ldlidar_stl_ros2_node`（不带 launch 静态 TF），
探针抓 3 帧；工具已入仓 [scripts/probe_laserscan.py](../../scripts/probe_laserscan.py)。
原始数据：`doc/raw_data/raw_ld06_scan_spec_2026-11-07_1133.txt`、`raw_ld06_crop_2026-11-07_1141.txt`（本地，不入 git）。

```bash
# 终端 1：起驱动（crop 关闭；测 crop 时改 enable_angle_crop_func:=true 并加 angle_crop_min/max，单位度）
ros2 run ldlidar_stl_ros2 ldlidar_stl_ros2_node --ros-args \
  -p product_name:=LDLiDAR_LD06 -p topic_name:=scan -p frame_id:=base_laser \
  -p port_name:=/dev/r2_ld06_a -p port_baudrate:=230400 \
  -p laser_scan_dir:=true -p enable_angle_crop_func:=false
# 终端 2：抓 3 帧（外层加 timeout -k 兜底，见下）
timeout -k 5 30 python3 scripts/probe_laserscan.py --topic /scan --count 3
```

**规格实测（crop 关闭）**：

| 项 | 实测（3 帧） | 说明 |
|:---|:---|:---|
| beam 数/圈 | **455 / 452 / 454** | **逐帧变化**；452~455 点/圈 × 10 Hz ≈ 4.5k 点/s |
| 角分辨率（消息字段） | **0.7930° / 0.7982° / 0.7947°** | 驱动按 `360/(beam_size−1)` 逐帧反推，不是固定常数 |
| 帧率 | `scan_time` 99.97/99.99/100.02 ms；stamp 间隔 99.99/100.02 ms | 10 Hz 确认（N97） |
| angle_min / angle_max | 0° / 360° | 0° 与 360° 方向重复 → 唯一角格 = `beam_size−1` |
| range_min / range_max | 0.02 / 25.0 m | **25 是驱动常量**（[demo.cpp:166-167](../../ldlidar_stl_ros2/src/demo.cpp#L166-L167)），不是 LD06 规格 |
| 室内有效回波最大 | 5.94~6.08 m（3 帧） | 室内环境限制，**不构成量程结论**；空旷场地量程仍待测 |
| NaN | 80~85 个/圈（≈18%） | 无回波 bin（crop 关闭时） |
| `distance=0 且 intensity≠0` | 以 `range=0.0` 发布 | 驱动只过滤 `distance==0 && intensity==0`（[L194](../../ldlidar_stl_ros2/src/demo.cpp#L194)）；下游需容忍 0 距离点 |

**angle crop 实测（两用例，验证掩盖行为与坐标约定）**：

| 用例（crop 原始角，度） | 发布角下的连续 NaN 带 | 宽度 |
|:---|:---|:---|
| 关闭（基线） | 无 ~90° 连续带；散点 NaN 80~85 个/圈 | — |
| `[135, 225]` | 134.3~225.7° | 89.2~90.6°（112~114 bin） |
| `[0, 90]` | 269.4~360.8° | 90.6~91.4°（114~115 bin） |

- crop 参数按**雷达原始角**（度、闭区间）计算；`laser_scan_dir=true` 时**发布角 = 360° − 原始角**
  （驱动反向填数组，[demo.cpp:214-225](../../ldlidar_stl_ros2/src/demo.cpp#L214-L225)）→ 非对称带在发布侧镜像。
- crop 只把 `ranges/intensities` 置 NaN，**消息长度与 `angle_min/angle_max` 不变**；下游按"无回波"处理。
- 换算：要掩盖发布角 `[α1, α2]`，设 crop `[360−α2, 360−α1]`；对称于 180° 的带两种写法一致。
- 与 S1 的关系：`向内的 90° 不扫` 可用该机制实现，但**区间需按实车安装朝向确定**（车体系 ↔ 雷达原始角）；
  ✅ 安装几何已于 2026-11-08 实测（[sensor-mount §6.1](../phase0/sensor-mount.md)），
  车体方向 ↔ 原始角/发布角对照（含 `laser_scan_dir=false`、其他安装朝向、crop 实例）见
  [sensor-mount §6.1.1](../phase0/sensor-mount.md)。

---

## 四、验收汇总（VM 阶段）

| 编号 | 判据 | 对应步骤 | 结果（2026-11-06） |
|:---|:---|:---|:---|
| V1 | 双路各 ~10Hz，连续 ≥20 min 无 `time out` | P2 | ✅ 长跑 ≥30 min 不掉电（用户实测） |
| V2 | 遮挡 A 不影响 B，反向同样 | P2 | ✅ PASS（用户实测） |
| V3 | 两路 topic/frame 独立，无混流 | P2 | ✅ Publisher 各 1，frame 独立 |
| V4 | 重插拔/重启后 `/dev/r2_ld06_a/b` 指向正确 | P3 | ✅ 重插拔 PASS；重启未单独记录 |
| V5 | 双开 vs 单开互扰有明确结论（无系统性鬼影或已记录） | P5 | ✅ 初筛无异常（VM 摆位） |
| V6 | 单雷达旧命令（默认参数）仍可用 | P1 | ✅ `/scan` + `base_laser` + rviz 正常 |

> V1 判据由原 10 min 调整为 ≥20 min：历史掉电发生在 18m36s，10 min 跨不过该点；本次实际 ≥30 min。
> 以上只证明 VM 软件契约；**不证明** S1 的供电、EKF 基线、地图质量与探索覆盖率。

---

## 五、风险与失败处理

| 风险 | 现象 | 处理 |
|:---|:---|:---|
| USB/hub 供电不足 | 双开后 `time out`、单开正常 | 换供电 hub / 雷达独立 5V；不要用 J-Link 5V 带载 |
| 18m36s 掉电不复现 | 根因已确认 = 接线端子松动掉出（用户 11-06 实测）；VM 长跑 ≥30 min 通过 | 不以 VM 结论关闭供电项；N97 按 P6 长跑并检查端子/接头 |
| launch 参数类型错 | `port_baudrate` 传字符串报类型错 | `ParameterValue(..., value_type=int)` |
| CMake 弃用警告（上游 VERSION 3.5） | 构建 stderr 出现 "Compatibility with CMake < 3.10 will be removed" | 非错误，N97 CMake 3.22.1 下构建成功；保持 vendor 原样，未来 CMake 4 报错再改 `3.10`（并同步 README_R2 本地改动） |
| `ros2 param` 不可用 | `param get` 超时、`param list` 报服务异常 | 驱动主循环不 spin 参数服务；参数以启动日志 9 行为准；如需运行时查看再评估补 `spin_some`（本次跳过） |
| launch 残留进程 | `ros2 node list` 同名节点重复 | 停 launch 用 Ctrl-C/SIGINT；清理须含 launch 父进程 + `static_transform_publisher`；重名先 `ros2 daemon stop` |
| 节点/静态 TF 重名 | 两实例互相覆盖、TF 断 | node_name、TF 节点名随实例参数化 |
| ttyACM 枚举漂移 | 重启后 A/B 互换 | 只用 by-id 或 udev 符号链接 |
| 双雷达光学互扰 | 鬼影/噪点/距离跳变 | P5 初筛；摆位错开高度/角度，记录结论 |
| VM 与 N97 差异 | VM 正常、N97 异常 | 按 P6 在 N97 重验，不用 VM 状态解释 N97 |

---

## 六、待用户定夺

1. ✅ 已定：A = serial `000063728672`，B = serial `000063728647`（udev 固定；物理外壳标签建议补贴）；
2. ✅ 已定：采用 `scan_a` / `scan_b`；
3. ✅ **已回填（2026-11-08，G10）**：x/y/z/yaw 实测值见 P1 参数表，推导与量测记录见
   [sensor-mount §6.1](../phase0/sensor-mount.md)；**yaw 已于 2026-11-08 实物复核通过**（350mm 箱 @≈1m：
   箱面倾角 −2.1°、中心 +94°；注意 +90° 仅对"雷达光心正前方"成立，车体中线目标读 ≈73°）；
4. ⏳ 未做（可选：VM 离线 slam_toolbox 验证，只验 launch/参数）；
5. ✅ 已定：本轮由用户执行、AI 给指令与判据；
6. ✅ 已收齐（2026-11-06 N97）：G354 `000063728613`、CANable2 `208C37AF4845`、LD06 A/B 同 VM
   （`...8672` / `...8647`），已写入 `/etc/udev/rules.d/99-r2-serial.rules`。

---

## 七、来源

- 事件与冒烟判据：[2026-11-06 LD06 VM 接入与冒烟](../retrospect/2026-11-06_ld06_vm_bringup_smoke.md)
- 两车架构与 S1/S2 边界：[two-car-architecture.md §三/§八](../two-car-architecture.md)
- 构建/部署/进程纪律：[ros2-ops.md §2/§7/§10](../ros2-ops.md)
- 验收边界：[standards.md §1.15](../standards.md)
- 驱动与 launch：[ldlidar_stl_ros2/launch/ld06.launch.py](../../ldlidar_stl_ros2/launch/ld06.launch.py)、[README_R2.md](../../ldlidar_stl_ros2/README_R2.md)
- 设备基线：2026-11-06 16:20 VM `lsusb` / `udevadm info` 实测；2026-11-06 18:49~18:52 N97 实测（本文件 §二）
- LD06 `/scan` 规格与 crop：2026-11-07 N97 实测（本文件 P7），原始数据 `doc/raw_data/raw_ld06_scan_spec_2026-11-07_1133.txt` / `raw_ld06_crop_2026-11-07_1141.txt`（本地，不入 git）；探针工具 [scripts/probe_laserscan.py](../../scripts/probe_laserscan.py)
- N97 重启复验：2026-11-07 11:25 重启后 `ls -l /dev/r2_*` + `udevadm info` 核对（本文件 P3）
