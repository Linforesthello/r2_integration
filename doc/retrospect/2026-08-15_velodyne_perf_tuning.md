# 2026-08-15 VLP-16 链路性能调优 + 供电不足根因

> 事件：/velodyne_points 帧率波动且严重不达标（CPU 高时 7Hz → 1Hz，目标 10Hz）
> 结论：① 根因一 = 雷达供电电池电压不足（硬件）；② 软件侧 = N97 转换节点 CPU 容量，经调优后稳定
> 关联：[startup.md §四 验证基线](../startup.md)（实测 hz 表）｜ commit `a0fb3bb`

---

## 一、排查过程（数据定位瓶颈）

| 环节 | 实测 | 结论 |
|:-----|:-----|:-----|
| `/velodyne_packets` | 9.915Hz 稳定 | 上游雷达/网络干净 |
| `/velodyne_points` | 7.7~8.5Hz 波动 | **转换节点 CPU 瓶颈**（丢 ~20% 帧） |
| `/kiss/odometry` | 随 points 变动且稳定 | KISS 跟随输入，不是瓶颈 |

**关键前提核实**：当前 driver/transform/laserscan 三个节点全是官方 `ros-humble-velodyne-*` 2.5.1 的 **C++ ELF 编译产物**（已验证 `file`），不存在"换 C++ 版本"的说法——掉帧是 N97（4C/4T 低功耗机）CPU 容量/负载竞争问题，不是语言问题。

**根因一（硬件，最先发现）**：雷达供电电池电压不足 → 全链路低 Hz 输出。
**教训**：低 Hz 排查顺序 = **先查供电/硬件 → 再查上游 packets → 再查转换节点 → 最后查下游**；不先怀疑软件。

## 二、调优改动（commit a0fb3bb，3 项一起改）

落点：[velodyne.launch.py](../../r2_sensors/launch/velodyne.launch.py)（参数在 apt 包 share 目录，launch 里 override，走 git 版本管理；08-15 抽包移入 r2_sensors 包，调优改动随包迁移，见 [r2_sensors_extract](2026-08-15_r2_sensors_extract.md)）

| # | 改动 | 原值 → 新值 | 原因 |
|:--|:-----|:-----|:-----|
| ① | `organize_cloud` | `true` → `False` | OrganizedCloudXYZIRT 网格容器（16×N 固定网格+NaN 填充）构建/传输/渲染都贵；PointcloudXYZIRT 紧凑无序容器。KISS/Nav2 均不需要 organized，无副作用 |
| ② | `max_range` | `130` → `40.0` | 转换层提前裁剪远点（130m 对 VLP-16 是无效区间）；与 KISS 配的 `max_range 30` 两级过滤对齐，远点算出来也是被 KISS 丢的 |
| ③ | laserscan 节点 | 启用 → 注释 | `/scan` 暂无消费者（Nav2 未接入）；**Nav2 接入时取消注释恢复** |

> ⚠️ launch 加载 **install 副本**（[ros2-ops §2](../ros2-ops.md) 的已知坑）：改后必须 `colcon build` 再重启，否则测到旧配置。
> ⚠️ 本批是 3 变量一起改（用户定的组合），恢复后无法归因单变量——三个都是安全方向，无副作用。

## 三、验证结果

| 指标 | 改前 | 改后 |
|:-----|:-----|:-----|
| `/velodyne_points` | 7.7~8.5Hz 波动 | **9.3~9.4Hz 稳定** |
| `/kiss/odometry` | 随 points | 稳定跟随 |

- 仍差 ~0.6Hz 到理论 10Hz（packets 9.915Hz），已够用（建图/导航链路正常）
- 剩余杠杆（不够时再用，每次一个变量）：`max_range` 40→30、KISS 调试时 `visualize:=false`（⚠️ 建图/录包依赖 `/kiss/frame` 须保持 true，见 [ros2-ops §3](../ros2-ops.md)）、chrt 实时优先级、component 单进程
- 雷达 return mode 已确认 **strongest 单回波**（非 dual），无数据量翻倍问题

## 四、顺带解释：transform 节点启动时的数字输出（非故障）

**现象**：启动日志里 transform 节点打印一串递增数字（0.000、2.304、4.608…）+ 警告 `No Azimuth Cache configured for model VLP16`。

**真相**（源码核实，ros-drivers/velodyne **2.5.1** tag，`velodyne_pointcloud/src/lib/rawdata.cpp`）：

1. **数字 = 每点时间偏移（µs），不是 azimuth**：`buildTimings()`（L110-137，VLP-16 手册常数：激光间隔 2.304µs、发射周期 55.296µs）+ L222-227 的调试残留 `printf`（2.3.0 加"每点时间戳"功能时留下的，旁边 RCLCPP_INFO 已注释、printf 忘了删）
2. **警告 = VLP-16 不需要该缓存**：`setupAzimuthCache()`（L252-264）只有 VLS-128 有硬编码方位缓存，其他型号一律打此警告，措辞有误导；VLP-16 走独立 `unpack_vlp16()` 路径
3. **两个输出都在 `RawData` 构造函数里（L59-69），每次启动无条件执行**，与 organize_cloud/max_range 改动无关——之前就有，只是启动滚动日志里没注意
4. 纯良性：启动一次性打印，**运行期零开销**

## 五、相关

- commit：`a0fb3bb R2|velodyne转换性能调优：organize_cloud关、max_range 40m、暂停laserscan`（同日 `f2e9a38` 抽包 r2_sensors，改动随包迁移）
- 实测 hz 现状表：[startup.md §四 验证基线](../startup.md)
- 上游源码：`ros-drivers/velodyne` tag `2.5.1`（VM `/tmp/velodyne-src-251/`）
