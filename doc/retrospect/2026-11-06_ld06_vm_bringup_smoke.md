# LD06 VM 接入、冒烟验证与掉电事件（2026-11-06）

> 日期: 2026-11-06
> 任务: LD06 串口 2D 雷达 vendor 入仓 `r2_integration` + VM 首次跑通 + 冒烟验证 + 掉电定位 + RViz 显示差异解释
> 状态: ✅ 冒烟 PASS（启动 → 串口 → `/scan` → TF 最小链路）；⚠️ 供电/接触问题仅短窗观察，未长跑复测；N97/SLAM/Nav2 未验证
> 关联: [平台分叉决策](2026-11-06_platform_split_old_retrofit.md)｜[两车架构](../two-car-architecture.md)｜[sensor-mount §六](../phase0/sensor-mount.md)｜[vendor 说明](../../ldlidar_stl_ros2/README_R2.md)
> 证据落位: `doc/raw_data/raw_ld06_jlink_port_2026-11-06_1357.txt`、`raw_ld06_first_run_2026-11-06_1406.txt`、`raw_ld06_power_loss_2026-11-06_1424.txt`、`raw_ld06_smoke_2026-11-06_1505.txt`（本地留档，均不入 git）

---

## 一、结论先行

1. **LD06 已在 VM 跑通**：J-Link VCOM → `/dev/ttyACM0`，230400，`/scan` 约 10 Hz，frame `base_laser`；首跑持续 **18 min 36 s**（14:06:07 → 14:24:43）。
2. **18m36s 后发生过一次掉电/停转**：蓝灯灭、雷达停转；驱动连续报 `get ldlidar data is time out`；重启后串口能开、`Actual BaudRate reported:230400`，但 3 s 内无有效帧 → `ldlidar communication is abnormal`（exit 1）；重新插拔供电后恢复。判定为 **LD06 本体供电/接触瞬断**，不是驱动/波特率/QoS/TF 问题。
3. **驱动包已 vendor 入仓** `r2_integration/ldlidar_stl_ros2/`（31 文件、276K、无内层 `.git`），构建成功；冒烟时运行中进程的可执行文件路径确认在 **r2 install**，不是外部 `~/ldlidar_ros2_ws`。
4. **冒烟 ≠ 验收**：本次只证明「新包能启动 → 串口能开 → `/scan` 能发 → TF 能查」；未证明安装方向、测距精度、供电长跑、N97 实机、SLAM/Nav2。

---

## 二、环境与对象

| 项 | 值 | 说明 |
|:---|:---|:---|
| 机器 | VM `lin-virtual-machine` | 开发机；AI 工具运行在此 |
| 雷达 | LD06，DTOF 2D 单线 | 手册标称 4500 点/s、10 Hz 内部调速、UART 230400 8N1 |
| 连接 | J-Link VCOM | `lsusb`：`1366:0105 SEGGER J-Link`，serial `000063728647` |
| 设备 | `/dev/serial/by-id/usb-SEGGER_J-Link_000063728647-if00 → ../../ttyACM0` | 无 `/dev/ttyUSB*`；当前只有 LD06 一路 |
| 驱动包 | `ldlidar_stl_ros2`，上游 `bf668a8`（3.0.0，MIT） | vendor 副本在 r2 仓根 |
| launch 参数 | `product_name=LDLiDAR_LD06`、`topic_name=scan`、`frame_id=base_laser`、`port_name=/dev/ttyACM0`、`port_baudrate=230400`、`laser_scan_dir=True` | 见 [ld06.launch.py](../../ldlidar_stl_ros2/launch/ld06.launch.py) |
| 静态 TF | `base_link → base_laser`，平移 `(0,0,0.18)`，旋转单位四元数 | **`z=0.18` 是占位值**，实车必须按安装高度重标 |
| 串口冲突风险 | 实车 G354 占 `/dev/ttyACM1`，LD06 占 ACM | 两设备同为 ACM，S1 起必须用 udev 固定名（如 `/dev/r2_g354`、`/dev/r2_ld06`） |

> 上游 launch 的默认 `port_name` 是 `/dev/ttyUSB0`（CP2102 套件）；本仓副本已改为 `/dev/ttyACM0` 以适配当前 J-Link VCOM。

---

## 三、时间线与现象

| 时间（2026-11-06） | 事件 | 证据 |
|:---|:---|:---|
| 13:52 | J-Link VCOM 枚举为 `/dev/ttyACM0`；`lsusb` 与 udev 均确认 `1366:0105` | `raw_ld06_jlink_port_..._1357.txt` |
| 14:06:07 | 首次 launch 成功：`ldlidar communication is normal.`、`Publish topic message:ldlidar scan data.`、`Actual BaudRate reported:230400` | `raw_ld06_first_run_..._1406.txt` |
| 14:06–14:24 | `/scan` 稳定约 10 Hz；`tf2_echo` 可查到 z=0.180、RPY 0 | 同上 |
| 14:24:43 起 | 雷达蓝灯灭/停转；驱动每约 100 ms 报 `get ldlidar data is time out`，持续约 1 s 后用户 Ctrl-C | `raw_ld06_power_loss_..._1424.txt` |
| 14:24:46 | 重启 launch：串口打开、230400 设置成功，但 3 s 内无有效帧 → `ldlidar communication is abnormal`，exit 1 | 同上 |
| 14:25:15 | 再次重启，仍同样失败 | 同上 |
| 之后 | 用户重新插拔供电，雷达恢复；后续启动如常 | 用户现场观察 + 本文件 §五 |
| 14:52:33 | 从 **r2 内新包** 启动 `ld06.launch.py`（PID 15887 / 节点 15888） | `raw_ld06_smoke_..._1505.txt` |
| 15:00–15:02 | 冒烟检查：`/scan` 9.996–10.001 Hz、单发布者、frame `base_laser`、TF 可查 | 同上 |

> 包来源说明：首跑阶段使用的是外部工作区（当时 r2 内尚未 vendor）；14:24/14:25 失败重启日志中的节点路径明确为 `~/ldlidar_ros2_ws/install/...`；14:52 起启动的才是 r2 内 vendor 包（PID 15888 路径在 r2 install）。硬件串口链路相同，包来源不同。

---

## 四、冒烟判据与结果

冒烟测试 = **最小闭环自检**：新包能否启动、串口能否打开、话题能否发布、TF 能否解析、短窗内会不会崩。它不替代安装标定与 S1 验收。

| # | 判据 | 结果 | 证据 |
|:--|:---|:---|:---|
| 1 | 运行的是 r2 内的新包 | ✅ PID 15888 可执行文件在 `/home/lin/Lin_workspace/r2_integration/install/ldlidar_stl_ros2/lib/.../ldlidar_stl_ros2_node` | `ps` + `raw_ld06_smoke_..._1505.txt` |
| 2 | 串口打开、有数据 | ✅ 首跑 `ldlidar communication is normal.`；当前 `/scan` 持续出数 | 首跑日志 + `/scan` |
| 3 | `/scan` 频率 | ✅ 9.996 / 10.001 / 9.999 / 10.000 Hz；min 0.098 s、max 0.103 s | `ros2 topic hz /scan` |
| 4 | 发布者唯一 | ✅ Publisher count: 1（节点 `LD06`） | `ros2 topic info /scan -v` |
| 5 | frame_id | ✅ `base_laser` | `ros2 topic echo /scan --once --field header` |
| 6 | `/scan` QoS | ✅ RELIABLE / VOLATILE | `ros2 topic info -v` |
| 7 | 静态 TF | ✅ `/tf_static` 发布者 `base_link_to_base_laser_ld06`，RELIABLE + TRANSIENT_LOCAL；`base_link → base_laser` z=0.180、旋转单位四元数 | `ros2 topic echo /tf_static --once` |
| 8 | TF 可解析 | ✅ `tf2_echo` 输出 z=0.180、RPY 0 | `ros2 run tf2_ros tf2_echo base_link base_laser` |
| 9 | 短窗无超时/退出 | ✅ 15:00–15:02 观察窗内无 `communication is abnormal`、进程未退出 | `ps` 时间戳 + 日志 |

> 备注：显式 `ros2 topic echo /tf_static --once --qos-durability transient_local` 本次未输出；普通 `--once` 可读，且 `ros2 topic info /tf_static -v` 已确认发布端为 RELIABLE + TRANSIENT_LOCAL。该 CLI 差异不影响 TF 判定，原因未深究。

**不能由本次冒烟推出的结论**：

- `z=0.18` 不是实测安装高度；
- 未验证 LD06 的 0° 是否朝车头、安装 yaw/pitch；
- 未验证测距精度、量程、地面杂波；
- 未验证 18m36s 掉电是否会复发（本次只做了约 10 分钟短窗）；
- 未在 N97 上构建/运行；
- 未接 slam_toolbox / Nav2 / explore。

---

## 五、掉电事件：判定与边界

### 5.1 证据链

| 观察 | 含义 |
|:---|:---|
| 首跑稳定 18m36s 后突然停止 | 不是启动配置问题；是运行中掉链路 |
| 蓝灯灭、雷达停转（用户现场观察） | 指向**雷达本体供电/转动停止**，不是 ROS 侧订阅断开 |
| 驱动连续 `get ldlidar data is time out` | 串口读不到有效帧；与本体停转一致 |
| 重启后 `Actual BaudRate reported:230400`，但 3 s 无帧 | **波特率设置成功 ≠ 有数据流**；tty 配置成功不能证明雷达在发 |
| 重插供电后恢复 | 供电/接触路径是变量；软件/驱动未改动 |

### 5.2 排除项

- **不是驱动/波特率**：同一驱动、同一 230400 配置，重插后即恢复；
- **不是 QoS/TF**：`/scan` 与 TF 在首跑中正常工作；超时发生在数据源侧；
- **不是 `stty speed 0`**：驱动用 `termios2` BOTHER 设置自定义速率，老式 `stty` 读不到；实际速率以驱动日志为准（首跑日志已注明）。

### 5.3 未确定项与 S1 前动作

仍不能区分：PSV 供电跌落、ZH1.5T-4P 接头接触不良、5V 来源带载不足、共地问题。S1 前按 [sensor-mount §六](../phase0/sensor-mount.md) 执行：

1. 带载测 PSV 对 GND 电压（手册 4.5~5.5 V），观察雷达转动时的跌落；
2. 检查 ZH1.5T-4P 的 PSV/GND 接触与共地；
3. 确认 5V 来源的带载能力；
4. 装车后做 **≥30 min** 长跑复现；若复发，先换供电/接头，再怀疑雷达本体。

> 本次不把「18m36s」当作可靠性指标；它只说明掉电发生在运行中，不能推出平均无故障时间。

---

## 六、RViz 显示差异：180°、颜色、大小

用包内配置启动：

```bash
rviz2 -d $(ros2 pkg prefix ldlidar_stl_ros2)/share/ldlidar_stl_ros2/rviz2/ldlidar.rviz
```

与裸 `rviz2` 的差异来自**包内保存的显示配置**，不是数据方向变了：

| 配置项 | 包内 `ldlidar.rviz` | 裸 `rviz2` 默认 |
|:---|:---|:---|
| Fixed Frame | `base_laser` | `map`（默认） |
| LaserScan 颜色 | `Intensity` + `Use rainbow: true`，Min 22 / Max 245 | 默认颜色变换器 |
| 点大小/样式 | `Size (Pixels): 3`、`Size (m): 0.03`、`Flat Squares` | 默认值 |
| 相机 | 保存的 Orbit：`Yaw ≈ 3.135397`（约 179.6°）、`Pitch ≈ 1.569796`、`Distance ≈ 6.454` | 默认视角 |

**180° 的来源**：保存的相机 `Yaw ≈ 179.6°` 把观察视角转了半圈；`base_link → base_laser` 的 TF 旋转是**单位四元数**，launch 的 `laser_scan_dir=True` 也是 ROS 逆时针约定。因此：

- 画面「正反不一致」= **相机视角**不同，不是 `/scan` 角度被反转；
- 颜色/大小 = Intensity 彩虹着色 + 3 px 扁平方块，不是数据质量变化。

**判方向的方法**：不要看默认视角；用已知非对称场景（例如车前方放一个偏左的物体），或直接看 `/scan` 的 `angle_min/angle_max` 与 `ranges` 索引，确认 0° 对应车头。

---

## 七、vendor 入仓记录

| 项 | 内容 |
|:---|:---|
| 来源 | `https://github.com/ldrobotSensorTeam/ldlidar_stl_ros2`，commit `bf668a89baf722a787dadc442860dcbf33a82f5a`（2023-05-08），3.0.0，MIT |
| 入仓位置 | `r2_integration/ldlidar_stl_ros2/`（仓根，与 `r2_sensors`/`g354_driver` 平级） |
| 复制方式 | `rsync -a --exclude='.git' --exclude='build' --exclude='install' --exclude='log'` |
| 规模 | 31 文件、276K；确认**无内层 `.git`** |
| 本地改动 | `launch/ld06.launch.py` 的 `port_name`：`/dev/ttyUSB0 → /dev/ttyACM0`；其余未改 |
| 构建 | `colcon build --packages-select ldlidar_stl_ros2`，成功 |
| 溯源说明 | [README_R2.md](../../ldlidar_stl_ros2/README_R2.md) |

**为什么必须去掉内层 `.git`**：带 `.git` 复制会让外层 git 把该目录记成 gitlink（类似子模块的引用），GitHub 上只显示一个目录条目、不展开源码；去掉后才是普通文件，能随 r2 正常同步。

**验证口径备注**：`ros2 pkg prefix` 的结果取决于当前 shell 的 `AMENT_PREFIX_PATH` 顺序。本次在未 source r2 的 shell 里它命中了外层 `~/ldlidar_ros2_ws`；显式 source r2 install 后返回 r2 路径。**运行中的进程可执行文件路径才是权威证据**——PID 15888 在 r2 install，说明用户启动该 launch 的环境里 r2 install 优先。不要只用 `pkg prefix` 判断“跑的是哪份包”。

---

## 八、未覆盖 / 下一步

| 事项 | 状态 |
|:---|:---|
| 供电/接触长跑复测（≥30 min） | 待做；S1 前置 |
| 安装高度/俯仰/前后位置实测，替换 `z=0.18` | 待做；S1 前置 |
| 0° 朝向与 `laser_scan_dir` 实车确认 | 待做 |
| G354 + LD06 的 udev 固定名 | 待做；S1 起必须 |
| N97 `git pull` + 本机构建 + `/scan` 验证 | 待做 |
| slam_toolbox + Nav2 + explore_lite（S1 软件） | 待做 |
| 提交/推送 | **未执行**，等用户授权 |

---

## 九、方法模板节（可复用操作卡）

### 卡① 第三方 ROS2 包 vendor 入仓卡

1. 从外部工作区复制时排除 `.git`、`build`、`install`、`log`（`rsync -a --exclude=...`）。
2. 复制后确认目标目录**没有** `.git`：`test -d <pkg>/.git && echo HAS_GIT || echo NO_GIT`。
3. 包放仓根（与其它 ROS2 包平级），不要塞进 `doc/` 或另一个包内部。
4. 在包内写 `README_R2.md`：上游仓库、commit、版本、License、本地改动、构建命令、已知坑。
5. `colcon build --packages-select <pkg>`；构建后**新开终端**再 source，避免旧 `AMENT_PREFIX_PATH`。
6. 验证运行态：`ps` 看进程可执行文件路径是否在新 install；`ros2 pkg prefix` 只作辅助（受 shell 环境影响）。

### 卡② 新传感器驱动冒烟卡

1. 进程来源：可执行文件路径是否为目标 install。
2. 数据源：驱动日志是否报 `communication is normal` / 等价成功标志。
3. 话题频率：`ros2 topic hz <topic>`，与手册标称对比（短窗即可）。
4. 发布者数量：`ros2 topic info <topic> -v`，必须为 1（排除双发布者）。
5. frame：`ros2 topic echo <topic> --once --field header`。
6. TF：`ros2 topic echo /tf_static --once` + `ros2 run tf2_ros tf2_echo <parent> <child>`。
7. 短窗稳定性：几分钟内无 timeout/退出。
8. **显式列出未覆盖项**：精度、方向、长跑、目标机、下游算法——避免把冒烟 PASS 误读成验收 PASS。

### 卡③ 串口传感器掉电/接触判定卡

1. 先看本体现象：LED、转动、发热（用户现场观察优先于日志）。
2. 日志形态：连续 timeout（约 100 ms 一条）= 无有效帧，不是偶发丢包。
3. 重启时区分「串口打开成功」与「有数据」：`Actual BaudRate reported` 只证明 tty 配置，不证明数据流。
4. 3 s 内无帧 → `communication is abnormal` / exit 1，说明数据源侧未恢复。
5. 重插供电测试：若恢复，优先判供电/接触，不先改驱动。
6. 再用带载电压、接头、共地、5V 来源逐项定位；最后才怀疑雷达本体。

### 卡④ RViz 配置差异判读卡

1. 先比 `Fixed Frame`、颜色变换器、点大小/样式、相机位姿，不要先怀疑数据。
2. 看 TF 的旋转是否为单位四元数；看驱动 `laser_scan_dir` 是否与 ROS 约定一致。
3. 用已知非对称场景或 `/scan` 的 `angle_min/angle_max + ranges` 验证 0° 方向。
4. 结论写成「显示配置差异」或「数据方向问题」，两者不要混。

---

## 十、经验点层次标注节

> 去向按四层制：**draft 层** = [analysis-methods.md](../analysis-methods.md)（新经验先完整展开）；**规则层** = [ros2-ops.md](../ros2-ops.md)/[standards.md](../standards.md)/[doc-engineering.md](../doc-engineering.md)；**事件层** = 本文留存。单事件新经验不直写规则层（[doc-engineering.md §十二](../doc-engineering.md)）。

| # | 经验点 | 类型 | 建议去向 |
|:--|:---|:---|:---|
| E1 | vendor 第三方 ROS2 包必须去掉内层 `.git`，否则外层 git 记成 gitlink、GitHub 不展开源码 | 操作 | draft（主题 J1）→ 成熟后 doc-engineering |
| E2 | `ros2 pkg prefix` 受 shell 的 `AMENT_PREFIX_PATH` 顺序影响；判断运行态以进程可执行文件路径为准 | 排障判据 | draft（主题 J2）→ ros2-ops §2 邻域 |
| E3 | 新传感器驱动冒烟 = 进程来源/频率/单发布者/frame/TF/短窗稳定；冒烟 PASS ≠ 验收 PASS | 方法 | draft（主题 J2）→ ros2-ops §2/§7 邻域 |
| E4 | `Actual BaudRate reported` 只证明 tty 配置成功，不证明雷达有数据流 | 排障判据 | draft（主题 J3）→ ros2-ops §7 邻域 |
| E5 | 串口传感器掉电/接触判定：看本体 LED/转动 + 连续 timeout + 重插恢复，先查供电/接头再改驱动 | 方法 | draft（主题 J3）→ ros2-ops §7 邻域 |
| E6 | 包内 RViz 配置的保存相机 yaw/Intensity 着色会造成「看起来 180°/变色」，不是数据方向 | 显示判读 | draft（主题 J4）→ 各传感器手册 |
| E7 | raw_data 不入 git，文档里不能写 markdown 链接指向它（GitHub 会 404）；用纯文本路径 | 文档纪律 | 事件层 + [doc-engineering.md §八](../doc-engineering.md) 邻域（已有“不入库内容”上下文） |
| E8 | 首跑 18m36s 不是可靠性指标；掉电问题必须用长跑与带载测量复现，不能用单次 uptime 下结论 | 验收纪律 | 事件层 + [pending-tasks.md](../pending-tasks.md) 的 S1 前置项 |

---

## 十一、来源

> 本文未使用 WebSearch/WebFetch；事实来自用户会话原始输出、本机命令输出与仓库文件。未实测项已标“待做/未验证”。

| 结论 | 来源 |
|:---|:---|
| J-Link VCOM 枚举、`1366:0105`、serial `000063728647` | `raw_ld06_jlink_port_2026-11-06_1357.txt` |
| 首跑 `/scan` 约 10 Hz、TF z=0.18、230400 | `raw_ld06_first_run_2026-11-06_1406.txt` |
| 18m36s 后超时、重启失败、exit 1 | `raw_ld06_power_loss_2026-11-06_1424.txt` |
| 冒烟时进程路径、`/scan` 频率、QoS、TF | `raw_ld06_smoke_2026-11-06_1505.txt` |
| launch 参数与静态 TF 占位值 | [ld06.launch.py](../../ldlidar_stl_ros2/launch/ld06.launch.py) |
| RViz 配置项（Fixed Frame/Intensity/Yaw 等） | [ldlidar.rviz](../../ldlidar_stl_ros2/rviz2/ldlidar.rviz) |
| 上游 commit/版本/本地改动 | [README_R2.md](../../ldlidar_stl_ros2/README_R2.md) |
| 文档结构/经验分层规范 | [standards.md §2.8](../standards.md)、[doc-engineering.md §十二](../doc-engineering.md) |
