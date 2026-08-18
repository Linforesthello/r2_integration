# R2 Nav2 实机导航 bringup（D4 地图复用验证 + 首次闭环）

> 日期：2026-08-15
> 状态：✅ **已执行完成（08-15）**——首闭环跑通，见 [retrospect/2026-08-15_nav2_bringup.md](../retrospect/2026-08-15_nav2_bringup.md)
> 补充（08-17）：降额过缝验证通过（inflation_radius 0.30，实测无碰撞、能过过道），**全速验证暂缓，保持降额现状**，见 [retrospect 08-17](../retrospect/2026-08-17_nav2_initialpose_inflation_fix.md)
> 前置：08-15 干净 bag 重录 + 人形块过滤完成，清洗版导航图 `map_0815_clean` 就绪（见 [clean_bag_rerecord](../retrospect/2026-08-15_clean_bag_rerecord.md)）
> 关联：[w1-operation.md](w1-operation.md)（D1~D5 建图手册）、[plan.md](plan.md)（W2 里程碑）、[07-handover](../07-handover.md)

## Context

08-15 稳定链路重录干净建图 bag（165547：KISS 9.63Hz、0 空窗），经人形块过滤产出清洗版导航图 `map_0815_clean`（0.05m/格，origin [-9.67, -22.12]，occupied 0.65/free 0.25/未知 127）。用户决定**直接用 clean 图开始 Nav2**。

现状缺口：
- `/scan` 不存在 — [velodyne.launch.py](../../r2_sensors/launch/velodyne.launch.py) laserscan 节点被注释，而 Nav2 的 AMCL 与两层 costmap 全部订阅 `/scan`
- Nav2 三件套（nav2.launch.py / nav2_params.yaml / nav2.rviz）已写好但 **未 git 入库**
- N97 上 Nav2 安装状态未确认（VM 已装 1.1.20 全栈）
- D4 地图复用验证未做（W1 清单未勾选）

已确认决策：
1. **Nav2 测试期间不跑 KISS**（AMCL 定位不需要，省 N97 CPU）
2. **首次实机降额速度**：限幅降到底盘上限的 ~40~50%（0.2/0.15/0.4 m/s、rad/s）

流程遵循多机纪律（standards.md 1.10）：**VM 改代码 → git push → N97 pull + build → 实机跑**。

---

## 一、VM 侧改动（AI 执行）

### 1. 恢复 velodyne.launch.py 的 laserscan 节点（/scan）
- 取消注释原 L62-69，节点参数改为：
  ```python
  parameters=[laserscan_params, {'frame_id': 'velodyne'}]
  ```
  （包内默认参数只有 ring:-1/resolution:0.007，frame_id 显式指定更稳，与 TF 链 base_link→velodyne 一致）
- 把 `velodyne_laserscan_node` 加进 LaunchDescription 节点列表（RegisterEventHandler 之前，无依赖顺序）
- 更新文件头 docstring（"laserscan 已注释" → "含 laserscan(/scan)，Nav2 使用"）

### 2. 新建降额参数 `config/nav2_params_low.yaml`
- `cp nav2_params.yaml nav2_params_low.yaml`，改两处：
  - controller_server MPPI：`vx_max: 0.2 / vy_max: 0.15 / wz_max: 0.4`
  - velocity_smoother：`max_velocity: [0.2, 0.15, 0.4]`
- 文件头注释：降额用途（首次实机，安全前置纪律）、验证通过后切回全速版 nav2_params.yaml
- setup.py 的 `glob('config/*.yaml')` 自动打包，无需改 setup.py

### 3. git 提交 + push
- 提交内容：nav2 三件套 + velodyne.launch.py 恢复 + nav2_params_low.yaml
- 格式：`R2|Nav2 三件套入库 + /scan 恢复 + 降额参数（首次实机用）`，body 写改动/原因/影响
- 注意：三件套当前 `??` 未跟踪，一并 add

---

## 二、N97 侧操作（用户执行；AI 给命令 + 预期现象）

### 0. 前置检查（每次开机必做）
- `echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor`
- `env | grep -iE "rmw|fastrtps"` 应无输出（无残留跨机 DDS 配置）

### 1. Nav2 安装确认
```bash
dpkg -l | grep -E "nav2-(amcl|map_server|mppi_controller|planner|controller|bt_navigator|lifecycle_manager|velocity_smoother)"
```
预期：全部 `ii`；缺则 `sudo apt install ros-humble-nav2-*`

### 2. 同步代码
```bash
cd ~/Lin_workspace/r2_integration && git pull
source /opt/ros/humble/setup.bash && colcon build
```
预期：build 成功，`install/r2_bringup/share/r2_bringup/config/` 下出现 nav2_params_low.yaml

### 3. 地图部署（VM→N97 免密，AI 可代跑；也可用户自己跑）
```bash
scp ~/Lin_workspace/bags/maps/d4/map_0815_clean.{pgm,yaml} lin@192.168.1.210:~/maps/
```
预期：N97 `~/maps/` 出现 map_0815_clean.pgm/yaml（yaml 中 image 字段指向同目录 map_0815_clean.pgm，无路径问题）

### 4. 启动顺序（分终端）
| 终端 | 命令 | 验证 |
|:---|:---|:---|
| 1 | `python3 ~/Lin_workspace/command/can_command.py` | CAN 就绪 |
| 2 | `ros2 launch r2_sensors velodyne.launch.py` | **新验证：`ros2 topic hz /scan` ~10Hz** |
| 3 | `ros2 launch r2_bringup chassis.launch.py publish_tf:=false` | /odom_wheels 50Hz |
| 4 | `ros2 launch g354_imu_driver g354_rviz.launch.py rviz:=false serial_port:=/dev/ttyACM1 mount_axes:=y_front_x_left_z_down` | 静止 3s 等校准 |
| 5 | `ros2 launch r2_bringup ekf.launch.py` | /odometry/filtered 30Hz（IMU 校准后才可启动） |
| 6 | `ros2 launch r2_bringup nav2.launch.py map:=/home/lin/maps/map_0815_clean.yaml params_file:=/home/lin/Lin_workspace/r2_integration/install/r2_bringup/share/r2_bringup/config/nav2_params_low.yaml rviz:=true` | 见下 |

KISS **不启动**（本次决策）。Nav2 启动前可先 `ros2 bag record`（话题：`/scan /odometry/filtered /cmd_vel /tf /tf_static /map /amcl_pose`）留档首次闭环数据。

### 5. D4 验证（融入 bringup，替代独立 map_server 步骤）
- rviz 中地图应回显且与场地一致（墙角、路缘、空地形状目检对比）——AMCL 起来后 map frame 自动存在，无需临时 static TF（08-13 踩坑已规避）
- rviz 顶部 **2D Pose Estimate**：在车实际位置点一下，箭头朝向车头 → 粒子（绿箭头）5s 内收敛到车位置 = AMCL 定位成功

### 6. 首个 goal（降额验证）
- rviz **Navigation2 Goal**：发 3~5m 直行目标
- 预期：路径规划 → 车以 ~0.2 m/s 缓慢移动 → 到达后停稳；全程无急刹/碰撞
- 记录：到达误差、全程耗时（留档 + bag 复盘）

---

## 三、排障预案

| 症状 | 排查 |
|:---|:---|
| /scan 无数据 | `ros2 node list | grep laserscan`；`ros2 topic hz /scan`；velodyne 终端日志 |
| AMCL 不收敛 | 2D Pose Estimate 方向不对 → 重设；`laser_max_range: 100.0` 过大 → 降 30 重试 |
| 底盘不动 | `ros2 topic echo /cmd_vel`：有数据不动 → 底盘日志（cmd_timeout 0.5s 超时？）；无数据 → velocity_smoother/odom_topic 或 TF 问题 |
| MPPI CPU 吃紧（N97 历史性能瓶颈） | `htop` 看 CPU；MPPI `batch_size: 2000` → 500~1000；仍不行切 DWB（nav2_dwb_controller 已装，参数文件切 controller_server 插件） |
| 不绕近处障碍 | costmap obstacle_max_range/raytrace 5.0 是否过小；voxel_layer 配置 |

---

## 四、文档更新（测试完成后，AI 执行）

1. `retrospect/2026-08-15_nav2_bringup.md`：D4 验证结果 + 首次 goal 量化数据（到达误差/耗时/成功率）+ 排障记录
2. `07-handover.md`：D4 完成勾选、Phase 3 进度、启动命令清单加 Nav2 终端（注明 KISS 可省）
3. `minimal-loop/w1-operation.md`：D5 验收清单 D4 项勾选 + 地图路径更新
4. `02-progress.md`：Phase 3 进度更新
5. git 提交（`R2|` + 描述体）

---

## 验证（量化验收）

- `/scan` 恢复：N97 上 `ros2 topic hz /scan` ≈ 10Hz
- D4：rviz 地图回显与场地一致（用户目检）
- AMCL：2D Pose Estimate 后粒子 5s 内收敛
- 首次闭环：goal 到达误差实测记录（<0.5m 目标）、全程无碰撞；bag 留档（/scan /odometry/filtered /cmd_vel /tf /map /amcl_pose）
- 08-17 补充：降额参数下过道通过 + 基本无碰撞实测（inflation_radius 0.30），窄缝修复留档 [retrospect 08-17](../retrospect/2026-08-17_nav2_initialpose_inflation_fix.md)
- 遗留：全速参数（nav2_params.yaml）验证**暂缓（08-17 决策，保持降额现状）**——切回前先同步其膨胀参数（仍 0.55）；MPPI batch 调优视 N97 CPU 实测
