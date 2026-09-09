# ROS/ROS2 操作规范（R2 项目）

> 范围：ROS/ROS2 特有操作纪律（构建/启动/录包/分析/部署/配置/排障）。
> 通用规范不在此重复，一律引用：[文档标准](standards.md)（git 提交 1.10 / 文档 1.1-1.8 / Obsidian 1.9）、[Obsidian 标签](obsidian-tags.md)、全局工作偏好 `~/.claude/CLAUDE.md`。
> 维护：每条规则来自实车/实机教训（标注出处），随项目演进补充。

---

## 1. 多机环境：先确认对象机器

| 机器 | 角色 | 说明 |
|:-----|:-----|:-----|
| VM (lin-virtual-machine) | 开发机 | 代码/文档/bag 分析；AI 工具（Bash/Edit）运行在此 |
| N97 (192.168.1.210) | 实车工控机 | 采集/控制/本地 rviz2；ROS 运行、apt 安装在此 |

- **源码工作区 VM 与 N97 各一份独立副本**：改代码在 VM，同步走 `git push` → N97 `git pull`，不 scp 拷贝
- **不要用 VM 的 install/build 状态解释 N97 行为**（2026-08-11 教训：在 VM 诊断 N97 构建产物全对不上，白排查一圈）
- 用户贴出的运行/实车反馈来自 N97——排障前先问清"当前对象是哪台机器"
- **N97 git pull 报 "Network is unreachable" 先查默认路由**：`ip route` 无 default 行 =
  WiFi 网关丢失（2026-08-14 网络环境故障教训）；N97 是内网机，外网连通性不可想当然
- **VM 单机 ROS 与跨机的 DDS 环境不同**：单机跑须 `unset FASTRTPS_DEFAULT_PROFILES_FILE`
  （bashrc 已注释，2026-08-14）；跨机（VM↔N97）时手动 export
  `FASTRTPS_DEFAULT_PROFILES_FILE=~/Lin_workspace/r2_integration/r2_bringup/config/dds/fastdds_peer_n97.xml`。详见
  [retrospect 08-14](retrospect/2026-08-14_vm_vlp16_dds_fix.md)
- **跨机实时可视化限低带宽**（2026-08-05/06 实测）：rviz2 经 WiFi 拉实车点云/TF 掉帧 + queue-is-full
  反向拖慢实车端（EKF 掉频）——实车可视化留 N97 本机回环，跨机只做低带宽/离线数据，
  见 [retrospect 08-05](retrospect/2026-08-05_n97_remote_desktop.md)

## 2. 构建与部署（改了要真的生效）

- **launch 加载 install 副本，不是源码**：改配置（yaml）后必须 `colcon build` 或手动 cp 同步 install 路径，
  否则测到的是旧配置（2026-08-09 ekf.yaml 教训）
- **验证新构建**：console_scripts 入口（`install/.../lib/<pkg>/<script>`）是 import 壳不含源码；
  应 grep `install/<pkg>/lib/python3*/site-packages/<pkg>/` 里的源码确认更新
- 改代码后验证前，先确认目标进程加载的是新构建：build + 重启进程，否则测到的是旧代码
- **包目录内勿直接 `colcon build`**：包内历史 build/install 残留污染构建（install 布局与他包不一致）；
  老机器"能用" ≠ 代码正确（源码路径巧合/install 残留掩盖）——新机器干净构建是体检
  （2026-07-31，见 [retrospect 07-31](retrospect/2026-07-31_workspace_check_fix.md)）
- **launch 路径用 ament_index 不用 `__file__`**：`get_package_share_directory`/prefix 取包路径；
  双查找 lib/ + bin/ 是修复手段不是规范（2026-07-31，见 [retrospect 07-31](retrospect/2026-07-31_chassis_launch_fix.md)）
- **ament_python 包完整性**：`setup.cfg` script_dir + resource marker 须显式安装——不依赖 colcon
  隐式补装（缺 marker = 包不可发现，colcon 移除隐式补装即中招）
  （2026-08-11 代码审查 P3 + 08-15 抽包，见 [retrospect 08-15](retrospect/2026-08-15_r2_sensors_extract.md)）
- **colcon install 是增量拷贝，不删已装文件**：删源/抽包后必须 `rm -rf build install` 全量重建
  （08-15 实测：N97 旧命令报 share 缺失 = 残留已清）
- **旧 shell 的 AMENT_PREFIX_PATH 指向已删 install**（报警告无害），但旧终端起不了新包——
  构建后**新开终端再 source**
- **仓库 ≠ 包**：构建单位 = `package.xml`；日常增量用 `--packages-select`、带依赖 `--packages-up-to`、
  pull 后不确定先全量 build（08-15，同上）
- **第三方 C++ 包编译前先查 cmake 版本来源**：pip 装的 cmake 4.4 抢占 PATH（`~/.local/bin/cmake`）
  与旧 CMakeLists 不兼容 → `PATH=/usr/bin:$PATH colcon build` 绕开（N97 连踩两次：FAST-LIO/Greenwave，
  见 [fastlio2 manual §二](n97/fastlio2-n97-deploy.md)）

## 3. 启动流程纪律（N97，顺序固定）

1. **CPU performance 治理器**（每次开机必做；powersave 恢复后 KISS 掉到 3.6Hz → 建图重影，见 [retrospect 08-11](retrospect/2026-08-11_kiss_frame_rate_fix.md)）
2. CAN 总线 → 雷达 → KISS-ICP（`visualize:=true`）→ 底盘（EKF 场景 `publish_tf:=false`）→ IMU → EKF → 键盘遥控
3. **IMU 启动后静止 3s 等校准，校准期不可动；EKF 必须在 IMU 校准完成后启动**
4. **重启 IMU 必须同时重启 EKF**（否则输出 NaN）
5. KISS-ICP 必须 `visualize:=true` 才发布点云话题（/kiss/frame 累积脚本依赖）
6. 完整命令与验证见 [w1-operation.md](minimal-loop/w1-operation.md) §1.1

## 4. bag 录制

- 路径：N97 `~/Lin_workspace/r2_integration/bags/`，开车前开始录
- 话题清单（建图/导航通用）：`/velodyne_points /kiss/frame /kiss/odometry /odom_wheels /odometry/filtered /imu/data /tf /tf_static`
- **`/imu/data` 必录**：KISS vs EKF yaw 对比依赖它（analyze_bags.py 对比项），缺录则该项报废
  （2026-08-15 教训：两 bag 同缺，见 [retrospect 08-15](retrospect/2026-08-15_kiss_drift_170058.md)）
- **录制前先核实话题存在**：以目标机 `ros2 topic list` 实际输出为准，不按记忆/他机清单录；
  排障型录包先按话题全集铺（costmap 排障清单见 [relog-operation.md §1/§2](minimal-loop2/relog-operation.md)）
  （08-25 W3 漏录事故根治项，见 §9.3 案例）
- **`ros2 bag record` 覆盖 QoS 只认文件**：Humble 无内联参数，须 `--qos-profile-overrides-path <yaml>`；
  文件缺失即报错退出（2026-09-06，见 [retrospect 09-06](retrospect/2026-09-06_lowobstacle_fixB_crashbox.md)）
- 历史坑：08-06 after 系列 bag 未录 `/kiss/frame`，累积脚本无法回放

## 5. bag 分析（采样精度先行）

- **分析前先确认采样方式：精采样（时间等间隔/全序列）还是粗略（索引降采样）**；涉及运动/瞬态特征必须精采样，或先问用户
- 时间序列一律按时间戳等间隔切片/插值，**禁用均匀索引采样**（`arr[len//4]`、`arr[::N]` 会漏掉运动段，
  2026-08-12 误判教训：90°/190° 转弯全落在采样点之间，误判轮速 yaw 失真 5.6×）
- 分析工具用官方 `rosbag2_py`（零安装），不先用第三方库（2026-08-06 教训）
- **结论与用户亲历事实冲突时**（用户说车动了但数据说没动），优先怀疑自己的采样/解析，不要先怀疑硬件
- **空结果先自查观测/记录链**：判据错/记录器崩 → jsonl/日志空 ≠ 无事件——两次假阴性根因均在观测侧
  （2026-09-05，见 [retrospect 09-05](retrospect/2026-09-05_lowobstacle_fixB_vm_acceptance.md)）
- **口述/目测 = 佐证非定论**：先拿数据再互证，不要用现场提示反推结论
  （2026-09-08 ringlaw 教训，见 [retrospect 09-08](retrospect/2026-09-08_lowobstacle_ringlaw_cleandata.md)）
- **验证前先查现成 bag**：metadata.yaml 核对话题清单后直接复用，不为验证重录
  （2026-08-18 stage_0812_2111 复用，见 [retrospect 08-18](retrospect/2026-08-18_fast_lio2_deploy.md)；
  与 §9 漏录→重录互补：有合格现成包优先复用）

## 6. 配置修改（EKF 等 yaml）

- 改 `ekf.yaml` → 同步 install 副本（§2）→ 重启 EKF；只加一个变量，记录改动前后数据
- 回滚：撤销该处改动 + 同步 install + 重启，或 `git revert`
- **配置失效三查（不报错的隐形失效）**——症状像"配置错乱/没生效"时逐项核，核完 `ros2 param get`
  实测确认：
  1. **键名**：以源码 `get_parameter_or`/declare 为准——键名错 = 参数等于没加（`publish.map_en` ≠
     `map_pub_en`；launch 传未声明参数被 rclpy 静默忽略）
  2. **段名**：yaml 参数段名 = 节点全名（含命名空间）——不匹配静默跑默认参数（LifecycleNode 缺参无日志）
  3. **值形态**：长度/类型不符部分实现不报错直接跑偏（协方差 15 值 vs 225 值 → 启动 NaN；6 值 config
     → yaw 随机游走）
  （来源：retrospect 08-02 ekf_tf / 08-05 chassis_ekf / 08-13 map_chain / 08-18 laser_map / 09-06 costmap_experiment）

## 7. 排障纪律

- **每次只加一个变量**；记录期望/实际数据，出问题回溯数据而非盯现象
- 疑难问题先搜索核实（WebSearch/官方文档/社区），不凭猜测下结论
- 大转弯/加速等动作段分析时，先看用户描述的实车动作再对数据（防采样盲区）
- **话题/节点全空，先查本机持久环境，再查应用层**：`env | grep -iE "rmw|fastrtps|cyclone"`
  （bashrc 的 DDS 跨机配置会掐死本机发现，2026-08-14 教训，见
  [retrospect 08-14](retrospect/2026-08-14_vm_vlp16_dds_fix.md)）
- **ros2 CLI 查询异常先怀疑 daemon 缓存**：`ros2 daemon stop` 或 `ros2 topic list --no-daemon`；
  症状是 CLI 看不到话题但 rviz2/独立节点能看到（daemon 常驻旧环境，2026-08-14）
- **全链路低 Hz 先查供电/硬件，再查软件**：VLP-16 供电电池电压不足 → points 掉到 1Hz（2026-08-15
  教训，实测 packets 正常但转换节点全链路低 Hz，实为雷达自身输出降速）；排查顺序 = 供电 → 上游
  `/velodyne_packets` → 转换节点 `/velodyne_points` → 下游 KISS，逐环节 `ros2 topic hz` 定位，
  见 [retrospect 08-15](retrospect/2026-08-15_velodyne_perf_tuning.md)
- **启动/构建失败先看 launch.log**：`~/.ros/log/<时间戳>/launch.log`（完整 cmd + exit code）
  （2026-07-31，见 [retrospect 07-31](retrospect/2026-07-31_chassis_launch_fix.md)）
- **TF 双发看数据流不看发布者列表**：`tf2_echo` 谁在发/跳变定真凶——TransformBroadcaster 构造即注册
  "幽灵发布者"；静止全 0 会误导，**动车才横跳**（2026-08-02，见 [retrospect 08-02](retrospect/2026-08-02_ekf_tf_fusion_fix.md)）
- **URDF 一个 frame 只能一个父**（TF2 双父冲突，树直接断）：多 root 定义须删——R2 base_footprint
  案例见 [sensor-mount §四](phase0/sensor-mount.md)（跨机器人通用坑）
- **Lifecycle 节点未激活假象**：`ros2 topic list` 只见 `transition_event` = 未激活——activate 前读到的
  数据全作废（实车 0-mark 假象同型，见 [costmap_experiment.md](minimal-loop2/costmap_experiment.md)）
- **同名节点双进程竞争**：读数张冠李戴——`ros2 topic info -v` 看 Publisher count；起进程前
  pkill + ps 确认单实例（与 §10 跨机"杀不掉"互补：这是本机同名，同上）
- **编译通过 ≠ 运行正常**：消息字段类型/长度约束编译不查（covariance 36×float 等），launch 参数未声明
  也静默忽略——改完本机最小复现自检（2026-08-02，见 [retrospect 08-02](retrospect/2026-08-02_ekf_tf_fusion_fix.md)）
- **排障先查本仓既有结论**：retrospect/raw_data/实验记录可能已答过——查完再外搜
  （2026-09-05 E5：同一问题绕 4 轮才回本仓，见 [retrospect 09-05](retrospect/2026-09-05_lowobstacle_fixB_vm_acceptance.md)）
- **已知 trouble 勿绕**：sim-time bag 回放 + costmap 点云观察源 = Nav2 known trouble（ROS Index）
  ——绕行路线等于重启排障（2026-09-05 E2，同上）
- **坐标转换脚本先 print 中间量**：sanity check 在算完之前（tf yaw 被当 z 用的怪值 6.59/-10 即信号）
  （2026-09-06 E4，见 [retrospect 09-06](retrospect/2026-09-06_lowobstacle_fixB_crashbox.md)）

## 8. 实机安全

- 首次实机测试用降额参数（速度 20%/力矩 30%），上电前检查清单，失控先拍急停，不赌运气

## 9. 漏录数据决策：补偿 vs 重录（先验原则，2026-08-25 定）

> 定位：**调试/分析开始前的先验判断规则**——发现录制数据缺项（漏录/断录话题）时，
> 先对照本节定方案，再动手，不临时拍脑袋。
> 来源：2026-08-25 用户定稿（结合 W3 避障 bag 漏录案例）；前置知识见 §4 bag 录制、§5 bag 分析、§7 排障纪律。

### 9.1 两方案对比

| 方案 | 做法 | 优点 | 缺点 |
|:---|:---|:---|:---|
| 一：补偿 | 基于现有已录数据，时间域对齐/频域特征，用其余传感器推导补全缺失路 | 不要求复现原始场景；保留本次真实环境/轨迹/其余传感器原始数据；不重做整套实验流程，省外场/真机时间成本 | 推导估计非真实观测，引入额外误差；后续定位/建图/代价地图调试，难区分「算法问题 vs 补偿伪数据」；缺失信号与现有数据耦合弱时补偿不可控，埋隐性 bug，排查代价高 |
| 二：重录 | 放弃本版 bag，重新录制，把漏录数据源完整采集，拿真实原始数据交后端批量处理 | 全真实采集，无补偿虚拟误差；排障时数据源无疑点，问题直接定位到算法逻辑；对 costmap/bag 解析/分段标记类排障友好，减少无效调试 | 无法复刻完全相同原始工况（环境/轨迹存在差异）；需占用设备/场地/人力时间重跑一轮 |

### 9.2 选择判断原则（调试前先对照）

1. **缺失项是核心输入**（直接参与建图/代价地图生成/状态解算）→ **优先重录**：
   核心数据源做补偿，后续调试会被数据本身持续干扰，排障成本远高于重录成本
2. **缺失项是非核心辅助信号**，且与现有传感器**强物理耦合** → 可补偿；
   但文档必须明确标注「该段数据经过补偿」，所有分析结果注明数据局限性，不得当原生真实数据使用
3. **当前 bag 最有价值的是独一无二、无法复现的特殊场景** → 只能被迫走补偿；
   且必须单独隔离验证补偿算法本身的精度
4. **正处于数据链路疑点排查中**（bag 解析/静止运动段划分/代价地图排障）→
   只要条件允许**优先重录**：补偿会多出「补偿算法是否出错」的排查维度，
   混淆原本的问题定位；补偿只适合作为没有办法的备选兜底方案

### 9.3 案例（08-25 W3 避障）

- 3 个 bag（1357/1401/1405）仅录 9 话题（scan/odometry/cmd_vel/cmd_vel_smoothed/goal_pose/amcl_pose/tf/tf_static/map），
  **漏录 /velodyne_points（底层点云）与 costmap 系列（核心证据）**
- 判定：points 与 costmap 两层皆缺、无任何现有数据可推导 → 不满足补偿条件（§9.2-2/3）→
  按 §9.2-1/4 **重录**，补齐 points→scan→costmap 全链路，一次闭环
- 同类历史坑：08-06 after 系列 bag 未录 /kiss/frame，累积脚本无法回放（§4）——
  **预防优于补救：录制前核对 §4 话题清单，录制后查 metadata.yaml 核对话题与消息数**

## 10. 进程卫生：AI 启动的进程必须自清理（2026-08-25 定）

! AI 自行调用会启动长驻进程的命令（ros2 launch/run、后台节点、rosbag play、转换节点等），
  完成后必须自行关闭；禁止留下「关闭不自杀 / 带缓存」的孤儿进程

- **自启动自清理**：完成后主动杀自己启动的进程；确需保留须告知用户进程状态与关闭命令
- **缓存/常驻服务**（ros2 daemon、DDS 发现缓存等）用后清理：`ros2 daemon stop`
- **周期性自查**：每几个话题提醒用户跑
  `ps aux | grep -iE "ros|nav2|rviz|velodyne" | grep -v grep` 检查残留进程
- **「杀不掉的节点」判据**（2026-08-25 教训）：本机 `ps` 查无进程但 `ros2 node list`
  还有节点 = 节点在**另一台机器**——同网段 FastDDS **默认多播发现自动互通**（无需跨机 XML），
  不要在本机空杀；先 `ps aux | grep -iE "ros|nav2|rviz"` 定位来源机器，再回源机器杀
- 案例（2026-08-25）：VM 16:58 调试遗留 nav2_costmap_2d（/tmp/costmap_test.yaml）+
  static_transform_publisher ×2 未关闭 → N97 `ros2 node list` 看到 /costmap/costmap 等
  节点数小时，N97 上怎么杀都杀不掉（根源在 VM，`kill` VM 侧进程后立即消失）
- **杀进程用精确目标，禁宽泛匹配**（三条同源禁令）：
  ① `pkill "ros2 launch"` 杀不净子树（孤儿节点继续发话题，08-15）
  ② `pkill -x python3` 兜底误杀无关常驻（09-05 事故）
  ③ `pkill -f <模式>` 会匹配到自身命令行（模式在变量里）→ 自杀 Exit 144；规避 = 变量拼接 / 按 PID /
     分块执行
  （来源：retrospect 08-15 nav2_bringup §三2 / 09-05 E6 / [costmap_experiment.md §六-1](minimal-loop2/costmap_experiment.md)）

## 11. costmap 读数判据（Nav2 排障，2026-09-05/06 低物链沉淀）

> 用途：对 costmap_raw 直读格值/直方图判"有没有障碍、哪层有"，不靠 rviz 目测。
> 类型事实：raw = `nav2_msgs/Costmap`（RELIABLE+TRANSIENT_LOCAL，读不到先查类型不匹配）、
> master = `OccupancyGrid`——两套同发，别用错解析器（实车前缀 `/local_costmap/*`、单节点实验 `/costmap/*`，
> 见 [costmap_experiment.md](minimal-loop2/costmap_experiment.md)）。

| 读数 | 含义 | 判据 |
|:---|:---|:---|
| raw 254 | lethal 障碍格 | **判 254**（master 换算 100） |
| master 100 | lethal | 判据用 **==100 而非 >80**（膨胀圈 99 不是障碍） |
| 253 / 99 | 内切膨胀圈 | 非障碍，不作判据 |
| 灰阶 1-252 | 梯度膨胀 | 正常 map 应含 255 + 1-252 全灰阶 |

- **分层对照**：local 有 254 / global 无 = 结构性没源（该层没喂这个障碍）；"已发现还撞"先查
  planner 用哪层（09-06 撞箱实锤：local 254 / global 无 = 修法 A 未启）
- **直方图异常信号**：全 0 / 全 253 / 全 254 = 观察源覆盖异常（正常含 255 与灰阶）
- 单帧事件定位（整层清空 vs 渐次衰减判据）与空窗恢复指纹见
  [retrospect 09-08 secondfail](retrospect/2026-09-08_lowobstacle_secondfail_clearevent.md)
（来源：retrospect 09-05 E3 / 09-06 E1/E3 / costmap_experiment §二/§三；排障录包话题全集见
[relog-operation.md](minimal-loop2/relog-operation.md)）

---

## 相关

- 文档/git/Obsidian 规范：[standards.md](standards.md) ｜ [obsidian-tags.md](obsidian-tags.md)
- QoS/DDS 问题手册：[ros2-qos-dds.md](ros2-qos-dds.md)（hz 大消息假阴性/兼容矩阵/排查四步法）
- 启动手册：[w1-operation.md](minimal-loop/w1-operation.md)
- 排障记录：[retrospect/](retrospect/)
