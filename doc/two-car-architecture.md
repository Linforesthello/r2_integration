# 两车架构与接口（老车平替 · 新车升级）

> 日期: 2026-11-06
> 状态: **架构定稿（方案层）/ 未实施**——接口契约先冻结，老车平替先行；安装尺寸、参数与验收阈值待实车标定后回填
> 定位: 跨阶段顶层文档——把「老车低成本平替」与「新车结构/传感器升级」放在同一张图上，先定共用接口，再分头实现；下层专题文档按 §九 再拆
> 关联: [决策记录](retrospect/2026-11-06_platform_split_old_retrofit.md)｜[07-handover.md](07-handover.md)（状态交接）｜[pending-tasks.md](pending-tasks.md)（待办入口）｜[explore-plan.md](minimal-loop2/explore-plan.md)（2D 探索实施稿）｜[planning-control-roadmap.md](roadmaps/planning-control-roadmap.md)（规划控制路线）
> 原则: **接口稳定、实现可替换**；老车先端到端，新车再升级；VLP-16 3D 线不在老车复活；旧文档不删不改写，按历史基线保留并在头部加注

---

## 一、决策摘要

> 用户 2026-11-06 定：老车结构上无法进一步升级，但必须做传感器低成本平替；新车在本项目基础上做结构、上层安装与传感器升级。本文是两车的共同上位文档。

| 项 | 老车（R2-OLD，工作代号） | 新车（R2-NEW，工作代号） |
|:---|:---|:---|
| 定位 | **低成本平替验证车**：把现有 R2 的四全向轮、CAN、EKF、Nav2 资产继续用起来 | **结构/传感器升级车**：新底盘运动结构、上层安装、3D/视觉传感器 |
| 主雷达 | LD06 串口 2D 单线 ×1（首期）→ ×2 低装（二期） | MID-70（首期）；后续可能 MID-360；D435 |
| IMU | STM32 + MPU6050（替代 G354；**S1/S2 保留 G354，S3 再替换**） | 待定（可复用 G354 或新 IMU） |
| 任务执行器 | Unitree GO-M8010-6 击球机构（打排球） | 待定 |
| 定位/建图 | 2D：slam_toolbox（建图）/ AMCL（定位） | 3D：FAST-LIO2 / Point-LIO 一类 LIO |
| 导航 | Nav2 + explore_lite 前沿探索 | Nav2 + 3D/视觉感知 |
| 算力 | N97（现有） | 待定（N97 或新平台） |
| 当前动作 | **先行实施**（先单 LD06 跑通 explore） | 设计/选型中，不阻塞老车 |

**边界声明**：

1. 老车不再跑 KISS-ICP / FAST-LIO2 / 3D 建图；VLP-16 撤下并挪作他用（具体去向待定，不默认装回老车）。
2. 新车不是老车的复制品：底盘结构、传感器布置、算力都可能不同；**只在 ROS 接口与算法层共用**，硬件配置分叉。
3. 本文只定架构与接口，不替代启动手册与执行卡；启动命令仍以 [startup.md](startup.md) 为准，2D 探索细节见 [explore-plan.md](minimal-loop2/explore-plan.md)。
4. 本文不编造安装尺寸/量程/角度：所有待实测项标 `TBD`，实车标定后回填。

---

## 二、为什么分叉（背景与判断）

| 事实 | 影响 |
|:---|:---|
| 老车结构上无法进一步升级（用户判断） | 老车不再承担 3D/大传感器升级；改为低成本平替，保留可运行性 |
| VLP-16 要从老车撤下、腾空间并挪作他用 | 老车的 3D SLAM/低物低带源链路全部退役；2D 雷达成为唯一导航感知源 |
| 新车要做底盘运动结构、上层安装、传感器升级 | 新车是 3D/视觉主线的承载平台；老车的 2D 探索只作为低成本验证 |
| 两车并行但节奏不同 | 先冻结接口，老车先端到端；新车设计与老车实施可并行，不互相阻塞 |

> 这是对「先端到端，再优化」的落地：老车用最便宜的 2D 方案把建图→导航→探索闭环跑通；新车再承担 3D、视觉、复杂结构。

---

## 三、老车平替方案

### 3.1 不改的东西（接口冻结的前提）

| 保留项 | 说明 |
|:---|:---|
| 四全向轮底盘 + CAN 控制 | 运动学、CAN ID、`/cmd_vel` 契约不变 |
| EKF 融合链路 | `/odom_wheels` + `/imu/data` → `/odometry/filtered`，`odom→base_link` 仍由 EKF 发布 |
| **G354 IMU（首期保留）** | S1/S2 继续用 G354 + 现有 EKF；`/imu/data`、`imu_link`、`odom→base_link` 不变，作为 S1 的对照基线；S3 才换 STM32 |
| Nav2 | 规划/控制/行为树/速度平滑器继续用；只换感知源与参数 |
| TF 约定 | `map→odom→base_link→sensor`；继续不使用 `base_footprint`（R2 已删，防双父冲突） |
| 文档/操作纪律 | 启动顺序、QoS、bag、降额、急停纪律不变 |

### 3.2 传感器平替

| 原传感器 | 平替 | ROS 接口 | 关键差异 / 风险 |
|:---|:---|:---|:---|
| VLP-16（3D，网口） | **LD06 ×1**（首期，正常高度）→ **LD06 ×2**（二期，低装） | `/scan`（首期）；二期可加 `/scan_low` | 只有单线 2D，无高度维；低装减少低物盲区但引入地面杂波；双雷达需解决串口区分与扫描平面几何 |
| G354（串口 IMU） | **STM32 + MPU6050** | `/imu/data`（`sensor_msgs/Imu`） | MPU6050 无磁力计，yaw 只能靠陀螺积分 + 轮速修正，漂移需实测；协方差/时间戳必须正确填充；**S1/S2 保留 G354，S3 才替换** |
| 无 | **GO-M8010-6 击球机构** | `/striker/trigger`、`/striker/state` | 新增执行器；控制时序与安全见 §七 |

**LD06 现有资产**：VM 外部 `~/ldlidar_ros2_ws`（参考，不随 r2 同步）；r2 仓内 [ldlidar_stl_ros2/](../ldlidar_stl_ros2/) 为上游 `bf668a8` vendor 入仓版本（去掉内层 `.git`，来源/本地改动见包内 [README_R2.md](../ldlidar_stl_ros2/README_R2.md)）。2026-11-06 launch 已参数化（9 个参数：`node_name` / `topic_name` / `frame_id` / `port_name` / `port_baudrate` / `z` / `yaw` / `pitch` / `roll`）：单雷达默认 `topic_name=scan`、`frame_id=base_laser`、`port_name=/dev/r2_ld06_a`（udev 符号链接）、`port_baudrate=230400`、`z=0.18`（**占位值**，实车按安装高度重标）；双实例用 `/scan_a` + `laser_a`、`/scan_b` + `laser_b` + `/dev/r2_ld06_a/b`；驱动参数 `product_name=LDLiDAR_LD06`、`laser_scan_dir=True` 不变。VM 已验收 V1–V6（双实例各 ~10Hz、数据隔离、udev 插拔不穿号、互扰初筛；详见 [old-car/ld06-dual-lidar.md](old-car/ld06-dual-lidar.md)）；首测 18m36s 掉电根因已确认 = **接线端子松动掉出**（用户 2026-11-06 实测）。N97 侧已完成 2026-11-06 交接前置：`git pull` 4860c2c + `colcon build` 通过，udev 四路固定（`r2_g354` / `r2_can` / `r2_ld06_a` / `r2_ld06_b`，serial 见 [执行计划 §二](old-car/ld06-dual-lidar.md)）；双实例运行 2026-11-06 19:21 实测通过（`/scan_a` 10.000 Hz、`/scan_b` 10.002 Hz，frame `laser_a`/`laser_b`，各 Publisher 1），**供电长跑仍待实测**；2026-11-07 补测 `/scan` 规格（beam 452~455/圈、角分辨率 0.793~0.798°、10 Hz）与 angle crop 掩盖（90° 带实测通过，发布角 = 360°−雷达原始角），详见 [执行计划 P7](old-car/ld06-dual-lidar.md)。

**STM32 IMU 的传输方式未定**（见 §十）：无论 micro-ROS 还是「STM32 串口帧 + 主机桥接」，ROS 侧都必须稳定产出 `sensor_msgs/Imu`，且 `frame_id=imu_link`、协方差非零、时间戳可用。IMU 固件细节不在本文展开。

### 3.3 软件栈（老车 2D）

```text
LD06 #1 ──→ /scan ──┬──→ slam_toolbox（建图/探索）──→ /map + TF map→odom
                    └──→ Nav2 global/local costmap 的 scan 源
LD06 #2 ──→ /scan_low ──→ Nav2 低带障碍层（二期，仅障碍不建图）
底盘 ──→ /odom_wheels ─┐
G354（S1/S2）/ STM32（S3 后）──→ /imu/data ┴──→ EKF ──→ /odometry/filtered + TF odom→base_link
Nav2 ──→ /cmd_vel ──→ 底盘
explore_lite ──→ NavigateToPose ──→ Nav2
```

| 模式 | 地图来源 | `map→odom` 发布者 | 说明 |
|:---|:---|:---|:---|
| 建图 | `slam_toolbox` 实时 `/map` | `slam_toolbox` | 不启动 AMCL/map_server |
| 定位导航 | `map_server` 加载离线地图 | AMCL | 现有 `nav2.launch.py` 模式 |
| 探索 | `slam_toolbox` 实时 `/map` | `slam_toolbox` | `nav2_explore.launch.py` + `explore_lite` |

**TF 唯一发布者**：

| TF | 发布者 | 备注 |
|:---|:---|:---|
| `map→odom` | `slam_toolbox` 或 AMCL（二选一） | 同时启动必跳变 |
| `odom→base_link` | EKF | 不变 |
| `base_link→base_laser`（单）/ `base_link→laser_a`、`base_link→laser_b`（双） | LD06 launch / `robot_state_publisher` | VM 双实例已用 `laser_a`/`laser_b`（2026-11-06）；二期低装再加 `base_link→laser_low` |
| `base_link→imu_link` | G354 现有静态 TF（S1/S2）/ STM32 桥或 URDF（S3 后） | 静态变换 |

**3D 线退役**：老车不启动 `velodyne_driver`、`velodyne_laserscan`、KISS-ICP、FAST-LIO2；相关代码/配置/文档保留，供新车或 VLP-16 其他用途复用。`nav2_params_low.yaml` 中的 `velodyne_low` 源在老车不可用，**老车必须另建参数文件**（不要直接改现有全速/降额文件，防污染历史基线）。

### 3.4 分阶段实施（老车）

| 阶段 | 内容 | 验收闸门 |
|:---|:---|:---|
| **S0 接口冻结** | 确认 `/scan`、`/imu/data`、`/odometry/filtered`、`/cmd_vel`、TF 树；确定 LD06 首期安装高度与串口 | 本文 §六 契约评审通过；不写代码 |
| **S1 单 LD06 + explore** | 正常高度单雷达；**保留 G354 + 现有 EKF**；`slam_toolbox` 建图 + `nav2_explore.launch.py` + `explore_lite`；5×5m 空地首测 | `/scan` 稳定；地图无重影；Nav2 Goal 可达；覆盖率 >80%；无碰撞；**EKF 输出与现有 G354/EKF 基线一致（Phase 1 验证）** |
| **S2 低装 + 双 LD06** | 低高度安装；**保留 G354 + 现有 EKF**；第二颗 LD06 接 `/scan_low`（或按 §十 选合并方案）；低带障碍层 | 目标低物可见；SLAM 地图质量不显著下降；地面杂波可控；双串口不掉线 |
| **S3 STM32 IMU 替换** | **替换 G354**；`/imu/data` 由 STM32 桥发布；EKF 重标 | 100~200Hz；协方差合理；EKF 无 NaN；静态/动态 yaw 漂移达标（阈值实测定） |
| **S4 G8010 击球** | 台架 → 装车；触发→爆发→停→慢回 | 角度重复性、回位误差、温升/过流保护、急停有效；详见 §七 |

> 顺序建议：**S1 先跑通**（用户已明确先单 LD06 跑 explore）；**S1/S2 保留 G354 + 现有 EKF，S3 才换 STM32**；S3/S4 可在 S1 期间做台架准备；S2 必须在 S1 有基线数据后做，便于对比「单雷达 vs 双雷达/低装」的收益与代价；G8010 台架与 S1 并行，装车放在 S4。

### 3.5 低物盲区：不要把旧数字直接搬过来

- VLP-16 时代的 `1.59m` 盲区是「0.775m 光心高 + −15° 最低环 + 0.35m 箱顶」的几何结果；换 LD06 后**光心高度、扫描平面、目标高度全变**，旧数字不再适用。
- 2D 单线雷达只有**一个扫描平面**：低装能扫到更低的目标，但扫不到「平面以上/以下」的完整轮廓；双雷达不同高度 = 两个平面，不是连续 3D 覆盖。
- 低装到接近地面会引入地面回波、桌腿/线缆/反光杂波；安装高度、俯仰、盲区、地面过滤要用实车数据定，不能纸面拍。
- 低物兜底仍归行为层（限速/停车/plan cost 惩罚）；是否实施见 [ros2-ops.md §12.2](ros2-ops.md) 的待决策项。

### 3.6 老车风险

| 风险 | 影响 | 缓解 |
|:---|:---|:---|
| LD06 串口设备名漂移（`/dev/ttyACM0`/`ttyUSB0`） | 重启后读错设备/两颗雷达互换 | udev 按 J-Link serial 固定符号链接：VM 已落 `/dev/r2_ld06_a`、`/dev/r2_ld06_b`（2026-11-06，[执行计划 P3](old-car/ld06-dual-lidar.md)），二期低装可加 `/dev/r2_ld06_low`；G354 用 `/dev/r2_g354`；**G354 与 LD06 同时占 ACM，S1 起必须固定名** |
| 低装地面杂波 | costmap 假障碍、建图脏 | 调整安装高度/俯仰；驱动角度裁剪；地面点过滤；先静态标定 |
| 双雷达同频互扰 | 偶发噪点/丢帧 | 错开安装/遮挡；实测同开与单开差异；必要时分时/分区 |
| MPU6050 yaw 漂移 | EKF 航向退化、Nav2 定位差 | 陀螺零偏标定 + 轮速 yaw 融合 + 静止 ZUPT；验收设漂移阈值 |
| STM32 传输/时间戳 | IMU 数据抖动、EKF 发散 | 固定周期采样；主机接收时间戳；协方差按实测填；先台架后装车 |
| 2D 探索在低矮/复杂场地退化 | 前沿误判、碰撞 | 首测空地；低物场景先人工急停；S2 后再进复杂场地 |

---

## 四、新车升级方案

### 4.1 升级维度

| 维度 | 内容 | 状态 |
|:---|:---|:---|
| 底盘运动结构 | 新构型/新轮系/新 CAN 协议（待定） | 设计中 |
| 上层安装 | 标准载荷板/传感器支架/供电与网络布线 | 设计中 |
| 传感器 | D435、MID-70；后续 MID-360、单点激光测距 | 选型/装法部分定档 |
| 算力 | N97 或新平台 | 待定 |
| 软件 | 复用 ROS2/Nav2/EKF/explore；3D LIO + 视觉为新主线 | 复用 + 新建 |

### 4.2 传感器角色

| 传感器 | 角色 | 关键约束 |
|:---|:---|:---|
| **D435** | 视觉导航/检测/彩色点云；**不承担低物检测**（装法已按此定档） | USB3 带宽；光照/纹理；内外参标定 |
| **MID-70** | 3D 主雷达：建图/定位/近距细节 | 70° 非全景；装 VLP-16 下方、离地 0.55~0.65m、前倾 15~20° 为 09-16 纸面方案，未实测；外参含倾角旋转 |
| **MID-360（后续）** | 360° 3D 补充/替代 | 选型与装法待定；不阻塞 MID-70 首期 |
| **单点激光测距** | 近距/高度/贴地补盲 | 量程/安装位置待定；与 2D/3D 雷达的分工待定 |
| VLP-16 | 已从老车撤下，挪作他用 | 不默认装新车；去向待定 |

> 装法依据：[sensor-mounting-layout-survey.md](surveys/sensor-mounting-layout-survey.md)。该 survey 的几何数值是纸面评价，**未实测**；新车实车必须重新标定。

### 4.3 软件栈（新车）

```text
MID-70 / MID-360 ──→ 3D 点云 ──→ FAST-LIO2 / Point-LIO ──→ odom + TF
D435 ──→ 视觉检测/深度 ──→ 目标/障碍 ──→ Nav2 / 行为层
2D 雷达（可选）──→ /scan ──→ Nav2 局部避障
Nav2 ──→ /cmd_vel ──→ 新底盘
```

- 3D LIO 与 2D Nav2 的分工沿用现有结论：3D 负责里程计/建图，2D 负责导航决策；不要让 3D 点云直接替代 Nav2 的 2D 代价地图。
- 新车若沿用 N97，算力边界仍适用：不并行跑多套 3D SLAM；MID-70 与 MID-360 的取舍按实测。
- 视觉链路（D435）与激光链路解耦：视觉失败时 Nav2 仍可降级运行。

### 4.4 新车尚未冻结的事项

- 底盘运动结构、轮系、CAN 协议与 `/cmd_vel` 语义（是否仍为全向三轮/四轮）。
- MID-70 的最终安装位置/倾角、是否加 MID-360、单点激光的位置。
- 算力平台（N97 / 新工控机 / Jetson 协同）。
- 上层安装的机械/供电/网络标准（载荷板尺寸、接插件、线束）。
- 新车是否复用老车的 2D 雷达作为近距补盲。

> 这些事项不影响老车先行；但会影响新车 `URDF`、launch、参数与标定文件，需在 S1 之后逐项定。

---

## 五、共用 / 分叉清单

> 判定规则：**硬件相关 → 分叉配置；算法/接口 → 共用代码**。禁止把老车参数直接复制到新车（反之亦然），避免「一份配置两车漂移」。

| 层 | 共用 | 分叉 | 说明 |
|:---|:---|:---|:---|
| ROS2 版本/QoS/DDS | ✅ Humble、QoS 约定、DDS 配置 | — | 跨机/单机 DDS 纪律沿用 [ros2-ops.md](ros2-ops.md) |
| 话题/坐标系契约 | ✅ §六 契约 | — | 两车都按同一话题名/类型/帧名对接 |
| 底盘控制 | ✅ `r2_bringup` 核心代码（若 CAN 协议兼容） | ⚙️ CAN ID、轮径、减速比、运动学参数 | 新车底盘不同则 fork 节点/参数 |
| Nav2 | ✅ launch 骨架、BT、插件选型 | ⚙️ footprint、速度、膨胀、传感器源 | 每车一份 `nav2_params_*.yaml` |
| EKF | ✅ `robot_localization` 配置骨架 | ⚙️ IMU 噪声/协方差、轮速参数 | 每车一份 `ekf_*.yaml` |
| 2D SLAM/探索 | ✅ slam_toolbox、explore_lite、map_saver | ⚙️ 雷达参数、场地阈值 | 老车用；新车可选 |
| 3D LIO | ✅ FAST-LIO2/Point-LIO 代码与部署经验 | ⚙️ 雷达外参、点云参数 | 新车用；老车不跑 |
| 传感器驱动 | ✅ 驱动包本身 | ⚙️ 端口、frame、安装外参、launch | LD06 / MID-70 / D435 各自 fork launch/config |
| URDF/TF | ✅ 约定与检查方法 | ⚙️ 整车 URDF、静态变换 | 每车一份 |
| 地图 | — | ⚙️ 每车独立地图 | 不跨车复用地图 |
| 标定 | ✅ 方法/工具 | ⚙️ 外参、IMU 零偏、轮径 | 每车独立标定文件 |
| 启动 | ✅ 脚本骨架/纪律 | ⚙️ 每车 bringup launch | `startup.md` 增补两车分节 |
| 文档 | ✅ 规范/事件/方法 | ⚙️ 每车专题文档 | 本文为上位；下层按 §九 拆 |
| G8010 击球 | ✅ 驱动/控制栈可复用 | ⚙️ 机构角度/限位/触发源 | 老车先做；新车若用同一机构再复用 |

---

## 六、接口契约（两车共同遵守）

### 6.1 话题契约

| 话题 | 类型 | frame | 期望频率 | 发布者 | 主要订阅者 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|
| `/scan` | `sensor_msgs/LaserScan` | `base_laser`（老车首期） | ~10Hz（VM 2026-11-06 验证；N97 2026-11-07 实测 10.00Hz，beam 452~455/圈、角分辨率 ~0.795°） | LD06 驱动 | slam_toolbox、Nav2 | 老车 2D 主感知；QoS 以驱动实际为准，启动后 `ros2 topic info -v` 核对 |
| `/scan_low` | `sensor_msgs/LaserScan` | `laser_low`（待定） | ~10Hz | 第二颗 LD06（二期） | Nav2 低带障碍层 | 不喂 slam_toolbox；避免低平面污染建图 |
| `/imu/data` | `sensor_msgs/Imu` | `imu_link` | 100~200Hz | G354（S1/S2）/ STM32 桥（S3 后） | EKF | 协方差必须非零；时间戳可用；orientation 可信度按传感器标 |
| `/odom_wheels` | `nav_msgs/Odometry` | `odom` | ~50Hz | 底盘 | EKF | 现有契约不变 |
| `/odometry/filtered` | `nav_msgs/Odometry` | `odom` | 30~50Hz | EKF | Nav2、explore_lite | 现有契约不变 |
| `/cmd_vel` | `geometry_msgs/Twist` | `base_link` | ~20Hz | Nav2 / teleop | 底盘 | 超时 0.5s 停车（现有） |
| `/map` | `nav_msgs/OccupancyGrid` | `map` | 0.5~1Hz | slam_toolbox / map_server | Nav2、RViz | `transient_local`；RViz 需设 Durability |
| `/tf`、`/tf_static` | `tf2_msgs/TFMessage` | — | — | 各自唯一发布者 | 全栈 | 禁止双发；见 6.2 |
| `/striker/trigger` | `std_srvs/Trigger` | — | 按需 | 任务层/操作员 | `g8010_striker` | 首版；稳定后可升级 Action |
| `/striker/state` | `std_msgs/String` | — | 10Hz 或状态变化 | `g8010_striker` | 任务层/RViz | 状态机阶段/错误码 |
| `/explore/resume` | `std_msgs/Bool` | — | 按需 | 操作员 | explore_lite | 暂停/恢复探索 |

### 6.2 TF 契约

```text
map ──→ odom ──→ base_link ──┬──→ base_laser        (老车首期)
                             ├──→ laser_low         (老车二期，待定)
                             ├──→ imu_link
                             └──→ <新车各传感器>
```

- `map→odom`：`slam_toolbox`（建图/探索）或 AMCL（定位）**二选一**，禁止同时发布。
- `odom→base_link`：EKF 唯一发布。
- `base_link→sensor`：`robot_state_publisher` 或 `static_transform_publisher`；老车 LD06 的 `z=0.18` 必须按实车改。
- 继续不使用 `base_footprint`（R2 历史双父冲突，见 [sensor-mount.md §四](phase0/sensor-mount.md)）。
- 新车的 MID-70 倾角必须作为旋转写入外参，不能只写平移。

### 6.3 参数与命名契约

- **每车一份配置**：计划采用 `r2_bringup/config/old_car/`、`r2_bringup/config/new_car/`（目录名待实施时定），launch 用 `car:=old|new` 或显式 `params_file` 选择；不要在同一文件里混两车参数。
- **设备路径不用硬编码**：LD06 用 udev 符号链接 `/dev/r2_ld06_a` / `/dev/r2_ld06_b`（2026-11-06 VM+N97 已落，二期低装可加 `/dev/r2_ld06_low`）；G354 用 `/dev/r2_g354`；CAN 用 `/dev/r2_can`；G8010 用 `/dev/r2_g8010`；S3 换 STM32 后可另立 `/dev/r2_imu`。启动前 `ls -l /dev/r2_*` 核对。
- **frame 名不随驱动默认值漂移**：LD06 单雷达默认 `base_laser`，双雷达用 `laser_a` / `laser_b`（2026-11-06 已用），二期低装可加 `laser_low`；IMU 固定 `imu_link`；G8010 不发布 TF（击球臂如需可视化，单独加 `striker_link`）。
- **QoS 不靠猜**：新驱动接入后先 `ros2 topic info -v` 记录发布/订阅两端，再写进配置；大消息/瞬态话题按 [ros2-qos-dds.md](ros2-qos-dds.md) 处理。

### 6.4 安全契约

| 项 | 要求 |
|:---|:---|
| 底盘失控 | 硬件急停优先；`/cmd_vel` 超时 0.5s 自动停（现有） |
| 首次实机 | 降额参数（速度 20%/力矩 30%）；场地清空；一人持急停 |
| LD06 低装 | 先静态测地面杂波与最小距离；盲区/近距保护写入验收 |
| STM32 IMU | 协方差/时间戳异常时 EKF 必须能停机，不静默 NaN |
| G8010 | 角度限位、温度/过流（`merror`）监控、触发超时、急停；台架先于装车 |
| 启动顺序 | 传感器 → EKF → 定位/建图 → Nav2 → 任务层；IMU 校准完成后再起 EKF |

---

## 七、GO-M8010-6 击球执行器（老车）

### 7.1 角色与动作时序

G8010 在老车上是**任务执行器**，不参与底盘驱动。动作需求（用户 2026-11-06 描述）：触发后快速爆发转动一定角度 → 停下 → 慢速回到初始位置，用于击打排球。

```text
IDLE ──trigger──→ BURST（快速到击球角）──→ HOLD（短停）──→ RETURN（慢速回 q0）──→ IDLE
  ↑                                                                                   │
  └──────────────────────── abort / fault ←──────────────────────────────────────────┘
```

- **BURST**：位置模式，目标角 = `strike_angle`，用较大的步进/刚度快速逼近；必须从当前 `q` 出发，不能从 0 突跳。
- **HOLD**：保持在击球角 `hold_ms`，让机构/球接触稳定。
- **RETURN**：目标 = 启动时捕获的 `q0`（不是 0），用更小步进/更低刚度慢速回位，避免甩回冲击。
- **abort/fault**：任何阶段触发急停/超时/过流/超温 → 渐进卸力 → `mode=0` → 报错。

### 7.2 本机可复用栈（已核对）

| 资产 | 路径 | 用途 |
|:---|:---|:---|
| 本地 C++ 工程 | `~/Lin_workspace/unitree_goM80106` | `include/`（SerialPort、unitreeMotor、CRC）+ `src/` 示例 + `lib/libUnitreeMotorSDK_Linux64.so` |
| 官方 SDK | `~/Lin_workspace/unitree_actuator_sdk` | 官方 README/示例/Python；GO-M8010-6 支持 |
| 位置模式示例 | `unitree_goM80106/src/locationMode_8010t1.cpp` | 缓变位置闭环、启动读当前位置、退出渐进卸力 |
| 速度模式示例 | `unitree_goM80106/src/example_goM8010_6_motor.cpp` | 仅作协议参考；**不是**击球时序 |
| 调试记录 | `unitree_goM80106/src/doc/locationMode_8010t1.md`、`260511.md` | 参数解释、过流/停机/信号处理教训 |

**协议事实（来自本地代码/头文件）**：

- `SerialPort` 默认 `baudrate = 4000000`、`recvLength = 16`、`timeOutUs = 20000`；示例端口 `/dev/ttyACM0`。
- `MotorType::GO_M8010_6`；`MotorMode::FOC`；示例 `id = 0`。
- `queryGearRatio(GO_M8010_6)` = `6.33`；输出端→电机轴用 `gearRatio = -queryGearRatio(...)`（含方向符号）。
- 控制律：`tau = kp*(q_target - q) + kd*(dq_target - dq) + tau_ff`。
- `cmd.q` / `data.q` 为**电机轴**弧度；输出端角度 = `data.q / gearRatio * 180/π`（本地示例的换算）。
- `data.temp` 温度、`data.merror` 错误码；本地记录 `merror=3` 为过流保护。
- 本地 `locationMode_8010t1.cpp` 的 `stepSize` 源码值为 `10.00f`，而同目录文档示例写 `0.10f`——**两者不一致，实车必须重新标定**；示例 `targetDeg=1000°` 只是多圈演示，不是击球角。
- 本地 `260511.md` 的结论：信号处理函数只设标志位，停止指令回到主循环后发送；不要在 SIGINT 里做串口 I/O。

### 7.3 ROS2 封装方案（首版）

- 新建 C++ ROS2 包（工作名 `g8010_striker`），链接 `libUnitreeMotorSDK_Linux64.so`，复用 `SerialPort`/`MotorCmd`/`MotorData` 头文件。
- **串口线程与 ROS executor 分离**：控制循环 200µs~1ms 在独立线程；ROS 回调只投递触发/中止命令，避免阻塞。
- 首版接口：`/striker/trigger`（`std_srvs/Trigger`）+ `/striker/state`（`std_msgs/String`）；参数化击球角/回位速度/保持时间。稳定后再评估 Action（带反馈/可取消）。
- 参数（初值全部 `TBD`，台架标定）：串口符号链接、`motor_id`、`gear_ratio`、`strike_angle_deg`、`burst_step_rotor_rad`、`return_step_rotor_rad`、`kp_burst`、`kd_burst`、`kp_return`、`kd_return`、`hold_ms`、`timeout_ms`、`max_temp`、`max_angle_deg`。
- 启动时先发一帧零力矩指令读 `data.q` 作为 `q0`；确认 `merror==0`、温度正常后再使能。
- 退出：渐进降 `kp`、升 `kd`，再 `mode=0`；不要在带载时直接切 `mode=0`。

### 7.4 安全与标定

| 项 | 要求 |
|:---|:---|
| 台架 | 先空载/假负载，机械限位+急停；人手远离击球臂 |
| 过流 | `merror=3` 立即卸力停机；检查 `kp` 过大/初始误差过大/机械卡死 |
| 角度 | `strike_angle` 与 `q0` 用输出端角度标定；软件限位 + 机械限位双保险 |
| 温度 | 连续击球看 `data.temp`；设 `max_temp` 停机阈值 |
| 触发 | 超时未完成 → abort；重复触发在非 IDLE 时拒绝 |
| 回位 | 慢速回 `q0`；回位到位判据 = 输出角度误差 + 速度接近 0 |
| 验收 | 角度重复性、回位误差、单次时序、连续 N 次温升、急停响应；数值台架后回填 |

### 7.5 待定

- 击球角、回位速度、保持时间、`kp/kd`：台架标定。
- 触发源：ROS service / 硬件 GPIO / 上层任务状态机；首版建议 ROS，硬件触发作为后续。
- 供电、驱动器安装、击球臂结构、排球供球联锁：机械/电气设计待定。
- 是否需要在 `striker_link` 上做 RViz 可视化：可选。

---

## 八、实施顺序（两车并行）

| 序 | 老车 | 新车 | 闸门 |
|:--|:---|:---|:---|
| P0 | 本文 + 决策记录 + 接口冻结 | 同左 | 文档评审通过 |
| P1 | S1 单 LD06 + explore（**G354 + EKF 不变**） | 底盘/传感器方案设计 | 5×5m 探索闭环 + EKF 基线对照 |
| P2 | S2 低装 + 双 LD06 | MID-70/D435 装法与算力核算 | 低物可见 + SLAM 质量不降 |
| P3 | S3 STM32 IMU | 3D LIO 选型/部署 | EKF 无 NaN、yaw 漂移达标 |
| P4 | S4 G8010 击球 | 视觉/3D 融合 | 台架 + 装车验收 |
| P5 | 老车收口/作品集素材 | 新车端到端 | 两车各自闭环 |

> 老车 S1 是当前最短路径；新车设计可在 P1 期间并行，但**不要用新车的未定参数反推老车**。**S1/S2 保留 G354，S3 才换 IMU**；G8010 台架可与 S1 并行，装车放在 S4（IMU 稳定后再加执行器扰动）。

---

## 九、后续拆分（本文不展开）

按「先顶层、再专题」的原则，下一步可拆：

| 文档（计划） | 内容 |
|:---|:---|
| [doc/old-car/ld06-dual-lidar.md](old-car/ld06-dual-lidar.md) | LD06 单/双雷达安装、串口、TF、扫描平面几何、低物实测；**VM 阶段已验收 V1–V6（2026-11-06）→ N97 交接（P6）待执行** |
| `doc/old-car/stm32-imu.md` | STM32+MPU6050 固件接口、传输方案、协方差/时间戳、EKF 重标 |
| `doc/old-car/g8010-striker.md` | 击球机构、控制时序、参数、台架/装车验收 |
| `doc/new-car/sensor-suite.md` | MID-70/MID-360/D435/单点激光装法、外参、标定 |
| `doc/new-car/chassis-interface.md` | 新底盘运动学、CAN/`/cmd_vel` 契约、URDF |

代码落点（计划）：

- `g8010_striker`：新 ROS2 包（C++），链接本机 Unitree SDK。
- `stm32_imu_bridge`：新包（名称待定），串口/micro-ROS → `/imu/data`。
- `r2_bringup`：新增老车/新车参数目录与 bringup launch；**不改**现有 `nav2.launch.py`/`nav2_params_low.yaml` 的历史基线。
- `ldlidar_stl_ros2`：复用 `~/ldlidar_ros2_ws`，N97 本机构建；不要直接把 VM 的 install 拷到 N97。2026-11-06 已 vendor 入仓 `ldlidar_stl_ros2/`（去内层 `.git`），N97 从 r2 仓构建；外部工作区保留参考。

---

## 十、开放决策（待用户定夺）

| 事项 | 选项 | 影响 |
|:---|:---|:---|
| LD06 数量/布置 | 单颗正常高度 / 单颗低装 / 双颗低装 / 一颗正常+一颗低装 | 单颗最简单；双颗低装低物覆盖好但建图平面低、杂波多；一高一低可兼顾建图与低物但需两套 TF/参数 |
| 双雷达融合拓扑 | 分开 `/scan` + `/scan_low` / 合并成单 `/scan` | 分开保留几何语义、Nav2 分层清晰；合并简单但不同高度的点混在一个平面，建图/避障都可能失真 |
| STM32 IMU 传输 | micro-ROS / 串口帧 + 主机桥接 | micro-ROS 链路标准但 STM32 资源/移植成本；串口桥简单可控但需自己定协议/时间戳 |
| G8010 触发接口 | ROS service（首版）/ 硬件 GPIO / 上层状态机 | ROS 易集成、有日志；硬件触发延迟低但布线/隔离复杂 |
| G8010 接口形态 | `std_srvs/Trigger`（首版）/ 自定义 Action | Trigger 简单；Action 可反馈/取消，适合连续击球与故障处理 |
| 新车 360° 覆盖 | MID-70 + 2D 补盲 / 等 MID-360 / 旋转机构 | MID-70 只有 70°；无 360° 时 Nav2 避障需补盲或降速 |
| 新车算力 | N97 / 新工控机 / Jetson 协同 | 决定 3D LIO + 视觉能否并行；N97 余量有限 |
| VLP-16 去向 | 新车 / 其他项目 / 备用 | 影响新车是否还有 360° 3D；不默认装回老车 |

> 以上不在本文替选；确定后回填本文对应小节，并在决策记录追加一行。

---

## 十一、来源

> 本文为架构文档，不引入 WebSearch 结论；事实来自用户决策、本机代码/驱动与项目既有文档。未实测项已标 `TBD`/`待实测`。

| 结论 | 来源 |
|:---|:---|
| 老车结构无法进一步升级、必须低成本平替；VLP-16 撤下挪作他用；新车升级底盘/上层/传感器 | 用户 2026-11-06 会话原话（见 [决策记录](retrospect/2026-11-06_platform_split_old_retrofit.md) §四） |
| 老车先单 LD06 跑 explore，再考虑低装/双雷达 | 用户 2026-11-06 会话原话（同上） |
| G8010 击球动作：触发→快速爆发转角→停→慢速回初始位 | 用户 2026-11-06 会话原话（同上） |
| LD06 驱动参数/端口/frame/静态 TF 占位值 | r2 仓内 [ldlidar_stl_ros2/launch/ld06.launch.py](../ldlidar_stl_ros2/launch/ld06.launch.py)（2026-11-06 参数化；外部 `~/ldlidar_ros2_ws` 仅参考） |
| G8010 串口 4Mbaud、FOC、id 0、gear ratio 6.33、控制律、过流/停机教训 | 本机 `~/Lin_workspace/unitree_goM80106/include/...`、`src/locationMode_8010t1.cpp`、`src/doc/*.md`；`~/Lin_workspace/unitree_actuator_sdk/README.md`（已读） |
| 2D 探索链路/参数/风险 | [explore-plan.md](minimal-loop2/explore-plan.md)（2026-11-05，未实测） |
| 低物盲区旧几何 1.59m 的来源与边界 | [3d-lidar-2d-navigation-survey.md §三B](surveys/3d-lidar-2d-navigation-survey.md)；[ros2-ops.md §12](ros2-ops.md) |
| MID-70/D435 装法与纸面几何 | [sensor-mounting-layout-survey.md](surveys/sensor-mounting-layout-survey.md)（2026-09-16，未实测） |
| TF/URDF 双父冲突与 `base_footprint` 删除 | [sensor-mount.md §四](phase0/sensor-mount.md) |
| 启动/QoS/bag/实机安全纪律 | [startup.md](startup.md)、[ros2-ops.md](ros2-ops.md)、[ros2-qos-dds.md](ros2-qos-dds.md) |

---

## 十二、变更记录

| 日期 | 变更 | 说明 |
|:---|:---|:---|
| 2026-11-06 | 初稿 | 两车架构/接口冻结；老车平替（LD06、STM32 IMU、G8010）+ 新车升级；共用/分叉清单；G8010 时序与复用栈 |
| 2026-11-06 | 回填 | LD06 双实例 VM 验收 V1–V6 通过：launch 9 参数、`/dev/r2_ld06_a/b` udev 固定名、`scan_a/scan_b` + `laser_a/laser_b`；掉电根因 = 接线端子松动；N97 交接待执行 |
