# ROS/ROS2 操作规范（R2 项目）

> 范围：ROS/ROS2 特有操作纪律（构建/启动/录包/分析/部署/配置/排障/感知覆盖判据）。
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

### 5.1 点云/scan 数值分析细则（2026-09-16 自 draft 层抽取；A1 收口盘点项 1）

> 来源：低物链事件档；展开版（背景/反例/验证）母本已收薄为状态回指，见 [analysis-methods.md 主题 A/E](analysis-methods.md)。

- **帧间/逐 bin diff 禁用裸 `max()` 聚合**：序列含 nan（inf−inf 产生）时 `max()` 保留首个 nan →
  阈值比较恒 False、**静默漏报**；改显式 list 收集 + `isfinite` 跳过双 nan/inf，inf↔finite 切换显式计为大变化
  （[09-04 断点复盘](retrospect/2026-09-04_lowobstacle_breakpoint.md)）
- **PointCloud2 解析按 field 提取，不整体 reshape**：`point_step` 含非 float32 字段（ring=uint16、time 等）时
  整体 numpy view 直接炸类型错；做法 = `np.frombuffer(uint8).reshape(n, point_step)` 后按 `msg.fields` 的
  offset/datatype 逐 field 切片——datatype 映射须用 `np.dtype(...)` **实例**（用 np 标量类型类会取到 getset_descriptor）
  （同上）
- **scan 方位符号先验校验**：ROS 约定 scan 正角 = 左（y>0）；动手前用同帧 points 的 `np.sign(y)`/`atan2(y,x)`
  与 scan `angle_min` 对齐一次并写进脚本头注释——勿等现场习惯反推（09-04 曾整批把负角当"车体左侧"报告，
  用户一句现场描述触发全量反转，见 [09-04 §二](retrospect/2026-09-04_lowobstacle_breakpoint.md)）
- **驻留聚类用距离跳变断段，不用角带平均**：1° 角带平均会把相邻驻留混成假 avg（平均距离掩盖真实边界）；
  做法 = 0.1m 距离档跳变 >0.3m 断段；事件表判据参数 = 带基准取带内全程最大距离（开阔参照），
  收窄 ≥0.5m 且驻留 ≥0.8s（容缺 ≤0.3s）记事件行（同上 §三 `scan_highres.py`）
- **环编号→仰角须实测标定，不读 db 表推断**：VLP16db.yaml 的 laser_id 是**交织发射序**（−15/+1/−13/+3…°），
  pointcloud `ring` 是 calibration.cpp 按仰角升序**重映射**后的索引（ring 0=−15° … ring 8=+1°）；
  要钉某条 scan 用哪根环 → 静止开阔段点云按 ring 聚合 `asin(z/R)` 中位角实测
  （[ring_angle_table.py](../bags/analysis/lowobstacle_0904/ring_angle_table.py)）——「偶数环向下」说的是发射序，
  不是 ring 序，曾致方向误判（同上 §10.1/10.2）
- **机制核查双钉法**（上条泛化）：钉死任何"源码声明 vs 运行行为"差异须**两条独立证据链交叉闭环**——
  源码链（declare/实现/映射处）+ 同 bag 实测（行为侧独立观测）；只一条链 = 未钉死（同上）
- **写 reader 前先 `ros2 interface show <type>` 定字段名**：一锤定音，省掉运行时 AttributeError 与改判据重跑
  （踩坑：`CostmapMetaData` 字段是 `metadata` 非 `meta`；`VoxelGrid` 是 `resolutions` 非 `resolution`，
  见 [costmap_experiment §六-5](minimal-loop2/costmap_experiment.md)）
- **下游 p50 ≈ 2× 输入周期 = 规律性隔帧丢帧**：单帧处理约 2 周期、逐帧排队 → 直查 CPU/算力（如 governor）；
  偶发卡顿表现为 p50 略升 + 长尾，**不呈精确倍数**（[08-11 帧率修复](retrospect/2026-08-11_kiss_frame_rate_fix.md) §2）
- **多段点云合并须 IoU 数值门槛**：先对齐（旋转粗搜 ±4° 步长 0.5° + FFT 互相关平移精搜，取重叠区 IoU 最大），
  **IoU ≥0.30 才合段**；<0.30 = 内容不一致 → 剔除，不靠目测判"像不像同一场地"
  （[08-13 分层建图](retrospect/2026-08-13_layer_map_3d2d.md) §一/§二：seg1+seg2 0.47 合、seg3 仅 0.20 剔除）
- **点云找箱法（已知障碍、未知位置）**：① velodyne 系筛高度带（离地 0.3~0.4m 平顶）→ 0.1m 密度簇 →
  平顶 z 固定范围即箱体；② odom 系定位 = 车初始位姿 + 箱相对方位/距离（静止段可靠，动段需 tf 全链路）；
  ③ 分层验证 = 箱世界坐标取 local(odom)/global(map) 两套 costmap_raw 各 ±0.7m 窗口直方图
  （[09-06 §三](retrospect/2026-09-06_lowobstacle_fixB_crashbox.md)；母版脚本
  [find_box_in_points.py](../bags/analysis/box_lowband_20260906/find_box_in_points.py)）
- **共享背景识别法**：同场景两包（不同被测物摆位）"远带/侧向物簇逐格等值" = 背景，差异带 = 被测物贡献——
  免人工辨认；兼作纯净数据判据（[09-08 ringlaw E8](retrospect/2026-09-08_lowobstacle_ringlaw_cleandata.md)）
- **判局部事件用定点 ROI 逐帧计数，禁全图 diff**：全图 diff 被环境变化淹没（手动推车段人腿 mark +
  箱格移动 → 全图 254 上涨盖掉箱格信号）；ROI 逐帧轨迹的 onset/归零与几何盲区预测对齐即因果实锤
  （[09-06 §八](retrospect/2026-09-06_lowobstacle_fixB_crashbox.md)：1.9m 起逐帧降 15→11→6→0）
- **数值分析优先，勿读渲染图**：高度谱/簇直方等数值形态优先；像素级读图不可靠，渲染仅作人工浏览辅助，
  数值与渲染冲突时以数值为准（[09-08 ringlaw E5](retrospect/2026-09-08_lowobstacle_ringlaw_cleandata.md)）
- **复用成熟脚本参数化，不每次重写**：写分析脚本前先借鉴既有母版（如 `find_box_in_points`/`render_frames`，
  见上条脚本目录）参数化改造——每次重写正确率差且低效（同上 E3）

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

### 7.1 无真车复现 / 对照验证法（2026-09-16 自 draft 层抽取；A1 收口盘点项 1）

> 详细操作卡（①~⑥ 步骤、判据参数、脚本）在各事件档；本处只存一行规则 + 来源回指。

- **VM 复现 costmap/感知行为用「静台 + 抽帧改 stamp 重发」，不用时间轴回放**：sim 轴本身就是问题源
  （known trouble，见上 §7 末）——wall 时间 + 静态 tf（odom→base_link 恒等 + base_link→velodyne z=0.655）
  + standalone nav2_costmap_2d（`use_sim_time: False`）+ rosbag2_py 抽决定性窗等间隔 N 帧（points+scan 成对）
  改 `header.stamp` 为当下 wall time 循环发，读 `costmap_raw` 254 判定；操作卡①~⑥见
  [09-05 复盘 §四](retrospect/2026-09-05_lowobstacle_fixB_vm_acceptance.md)
- **动态行为差异（mark→clear 竞争类）用「整包反转重放 A/B」**：录单方向完整渐变场景（静止车 + 目标物逐档
  移动停 3~5s）→ 离线定几何律 → 选停驻段(mark)/盲区段(clear)素材 → points/scan 帧逆序发、A/B 各跑一遍
  （顺带得"衰减 onset 与盲区边界对齐"因果自证）；**串行 + 残留守卫**（先 A 后 B 绝不并发；轮前 pgrep 守卫、
  轮后按命令行特征 pkill + 复验）；**A/B 首帧字节一致性**= 双发布者污染信号（数据作废）；ROI 判据 = 目标物
  可达区间 + |y| 半宽圈定，OLD 终态趋 0 vs NEW 保持 >0（[09-08 A/B 验收 §七](retrospect/2026-09-08_lowobstacle_fixB_ab_acceptance.md)）
- **双录对照隔离「内容 vs 链路/环境」**：同一条处理管线分别跑短直行段与长绕圈段——差异只出现在长录 =
  内容问题（如旋转段配准退化），两录同病 = 链路/环境问题（[08-15 kiss 漂移](retrospect/2026-08-15_kiss_drift_170058.md)：
  短录干净 vs 长绕 163° 漂移）
- **"配置像没生效"用源码插桩钉执行侧（注入 → 定位 → 还原）**：源码头加 `RCLCPP_INFO("[diag] …")` →
  `--packages-select` + symlink-install 重编译 → 按 diag 输出裁定事实（如 en=1 = 参数已加载 / 每秒触发 =
  timer 正常）→ **还原必做**（删插桩重编译重启，grep 日志不再出现 `[diag]` 后复跑原验证姿势）；与
  「param get → 执行 diag → 发布 echo」逐段隔离配合，每段一个验证动作
  （[08-18 Laser_map](retrospect/2026-08-18_fastlio_laser_map_debug.md)）
- **感知/行为问题先分「物理边界 vs 工程缺陷」**：边界（几何/能量/信息论不可参数化）与缺陷（可修）
  **分开列证据、各自实锤**后再判收手——同一现象可双因（盲区 1.59m = 物理边界；"第二次失效" = 工程 clear
  冲突），修复收益受边界封顶，避免在几何极限上无限打补丁
  （[09-08 pivot §五-1](retrospect/2026-09-08_lowobstacle_pivot_decision.md)）

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
- **单帧整层清空 vs 渐次衰减**（事件定位判据，2026-09-16 自 draft 层抽取）：**单帧全层归零**（伴随目标格 −52%）
  = 清除事件（ClearEntirely 特征）；**逐帧降** = 观测衰减。**plan 空窗 + 清除帧与首 plan 同刻** =
  planner-fail → clear → replan 恢复链指纹（不必等 BT 日志即可先钉时间窗）；时间线铁律 = 粗后细
  （速度/goal/plan 全览 → 统一 map 系几何 → 地图上下文 → ROI 定点帧级计数 → 同窗话题交叉）
  （[09-08 secondfail §五](retrospect/2026-09-08_lowobstacle_secondfail_clearevent.md)）
（来源：retrospect 09-05 E3 / 09-06 E1/E3 / costmap_experiment §二/§三 / 09-08 secondfail E4；排障录包话题全集见
[relog-operation.md](minimal-loop2/relog-operation.md)）

## 12. 感知覆盖 / 可观测性判据（2026-09-16 建，自 draft 层抽取 E5）

> 用途：判"传感器在几何上**能不能看见**某目标"——盲区/覆盖边界用公式算 + 实测对账，不靠观感猜。
> 定位：感知系统设计层的判据（不属雷达本体 / SLAM / 规划）；**数值唯一事实源** =
> [survey §三B](surveys/3d-lidar-2d-navigation-survey.md)（R2 实测定稿）。
> 本节为**长期承载位**：感知边界衍生的后续判据（L4 限速/停车一类兜底策略等）归此。

### 12.1 视锥临界公式（几何律标定）

- **公式**：`d = Δh / tan|θ|`——Δh = 雷达光心高 − 目标顶高（**须同一参考系**），θ = 环仰角（向下为负）。
  d = 该环**第一次打到目标顶面**的水平距离：**d 以内射线掠顶**，故**最小 |θ| 的环决定盲区半径**
- **R2 数值**：VLP-16 光心高 0.775m（地面系）+ 最低环 −15° → 0.35m 箱顶打顶临界
  `(0.655−0.23)/tan15° ≈ 1.59m`（base_link 系算式：0.655 = 光心 0.775 − base_link 高 0.12，
  见 [sensor-mount §3.2](phase0/sensor-mount.md)）；
  **d < 1.59m 时 16 环全掠顶，低带源无 mark 输入**（09-06 bag 定点曲线：254 随逼近 1.9m→1.4m 单调归零）
  ——数值以 [survey §三B.2](surveys/3d-lidar-2d-navigation-survey.md) 为准
- **对账门槛**：逐帧高度谱反推命中 ring（h = H − d·tanθ），**理论 ↔ 实测偏差 <1cm 才算对账**；
  未对账的"理论正确"不算数（[09-08 ringlaw E9](retrospect/2026-09-08_lowobstacle_ringlaw_cleandata.md)）
- **反向用法（选型/布站评价函数）**：同一公式反算需求——盲区要压到 x m 内 ⇒ 最低仰角 ≤ arctan(Δh/x)，
  或加线数 / 降安装高度 / 补近场传感器；多方案取舍用同式评分（[survey §三](surveys/3d-lidar-2d-navigation-survey.md)）

### 12.2 感知问题分层归因（L1~L4）

- **先分「物理边界 vs 工程缺陷」再谈收手**（同 §7.1 末条）：L1 几何/物理边界（不可参数化）
  ｜ L2 转换层（选环/合成 scan）｜ L3 costmap 层（同层 clear 冲突、local/global 不对称、update 节流）
  ｜ L4 规划/行为层（近距兜底）——四层分开列证据、各自实锤
  （分层表与各层实测状态见 [survey §三B.3](surveys/3d-lidar-2d-navigation-survey.md)）
- **待入项（未落地）**：L4 近距兜底策略（盲区锥 <1.6m 限速/停车/plan cost 惩罚）是否实施、与验收口径
  （感知解决 vs 感知+行为联合）**待用户决策**；L1 改布局/多模态属 roadmap §3 线
  （[survey §四](surveys/3d-lidar-2d-navigation-survey.md)）

---

## 相关

- 文档/git/Obsidian 规范：[standards.md](standards.md) ｜ [obsidian-tags.md](obsidian-tags.md)
- QoS/DDS 问题手册：[ros2-qos-dds.md](ros2-qos-dds.md)（hz 大消息假阴性/兼容矩阵/排查四步法）
- 启动手册：[w1-operation.md](minimal-loop/w1-operation.md)
- 排障记录：[retrospect/](retrospect/)
