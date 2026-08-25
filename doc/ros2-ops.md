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

## 2. 构建与部署（改了要真的生效）

- **launch 加载 install 副本，不是源码**：改配置（yaml）后必须 `colcon build` 或手动 cp 同步 install 路径，
  否则测到的是旧配置（2026-08-09 ekf.yaml 教训）
- **验证新构建**：console_scripts 入口（`install/.../lib/<pkg>/<script>`）是 import 壳不含源码；
  应 grep `install/<pkg>/lib/python3*/site-packages/<pkg>/` 里的源码确认更新
- 改代码后验证前，先确认目标进程加载的是新构建：build + 重启进程，否则测到的是旧代码

## 3. 启动流程纪律（N97，顺序固定）

1. **CPU performance 治理器**（每次开机必做；powersave 恢复后 KISS 掉到 3.6Hz → 建图重影，见 [retrospect 08-11](retrospect/2026-08-11_kiss_frame_rate_fix.md)）
2. CAN 总线 → 雷达 → KISS-ICP（`visualize:=true`）→ 底盘（EKF 场景 `publish_tf:=false`）→ IMU → EKF → 键盘遥控
3. **IMU 启动后静止 3s 等校准，校准期不可动；EKF 必须在 IMU 校准完成后启动**
4. **重启 IMU 必须同时重启 EKF**（否则输出 NaN）
5. KISS-ICP 必须 `visualize:=true` 才发布点云话题（/kiss/frame 累积脚本依赖）
6. 完整命令与验证见 [w1-operation.md](minimal-loop/w1-operation.md) §1.1

## 4. bag 录制

- 路径：N97 `~/Lin_workspace/r2_integration/bags/`，开车前开始录
- 话题清单（建图/导航通用）：`/velodyne_points /kiss/frame /kiss/odometry /odom_wheels /odometry/filtered /tf /tf_static`
- 历史坑：08-06 after 系列 bag 未录 `/kiss/frame`，累积脚本无法回放

## 5. bag 分析（采样精度先行）

- **分析前先确认采样方式：精采样（时间等间隔/全序列）还是粗略（索引降采样）**；涉及运动/瞬态特征必须精采样，或先问用户
- 时间序列一律按时间戳等间隔切片/插值，**禁用均匀索引采样**（`arr[len//4]`、`arr[::N]` 会漏掉运动段，
  2026-08-12 误判教训：90°/190° 转弯全落在采样点之间，误判轮速 yaw 失真 5.6×）
- 分析工具用官方 `rosbag2_py`（零安装），不先用第三方库（2026-08-06 教训）
- **结论与用户亲历事实冲突时**（用户说车动了但数据说没动），优先怀疑自己的采样/解析，不要先怀疑硬件

## 6. 配置修改（EKF 等 yaml）

- 改 `ekf.yaml` → 同步 install 副本（§2）→ 重启 EKF；只加一个变量，记录改动前后数据
- 回滚：撤销该处改动 + 同步 install + 重启，或 `git revert`

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

---

## 相关

- 文档/git/Obsidian 规范：[standards.md](standards.md) ｜ [obsidian-tags.md](obsidian-tags.md)
- QoS/DDS 问题手册：[ros2-qos-dds.md](ros2-qos-dds.md)（hz 大消息假阴性/兼容矩阵/排查四步法）
- 启动手册：[w1-operation.md](minimal-loop/w1-operation.md)
- 排障记录：[retrospect/](retrospect/)
