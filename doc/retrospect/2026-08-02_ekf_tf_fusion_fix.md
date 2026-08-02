# R2 EKF/TF 融合排障全记录

> 日期: 2026-08-02
> 机器: N97（192.168.1.210，enp1s0: 10.18.18.20）+ 开发 VM（lin-virtual-machine，192.168.1.204）
> 场景: 键盘+雷达建图展示 → 开启 EKF 看 IMU 姿态 → 全链路联调
> 状态: ✅ 全部解决，当前系统正常（详见第五节）

---

## 一、背景

2026-08-02 完成 VLP-16 雷达+KISS-ICP+键盘控制的"车在点云地图中跑动"展示后，
开启 IMU(EKF) 融合链路，期间连续出现 7 个问题，逐一排查解决。
本记录按时间线完整存档现象、根因、解决方法和验证结果。

---

## 二、问题总览

| # | 问题 | 根因 | 状态 |
|:--|:-----|:-----|:----:|
| 1 | 雷达/N97 网段迁移（10.10.3.x → 10.18.18.x） | 网络规划调整 | ✅ |
| 2 | KISS-ICP 里程计不走 | launch 默认 `use_sim_time=true` | ✅ |
| 3 | RViz 里 imu_link 标红 | TF 树无 imu_link（驱动不发 TF） | ✅ |
| 4 | RViz 里 /imu/data 灰色不可选 | N97 未装 rviz_imu_plugin + QoS 不匹配 | ✅ |
| 5 | 点云与 IMU 显示"打架"、不断震动 | odom→base_link 双发布者（chassis + EKF） | ✅ |
| 6 | chassis_node 启动崩溃 | 协方差列表用了 int（`0`）而非 float | ✅ |
| 7 | EKF yaw 每秒跳 10°+、z 漂到 12m | N97 上 ekf.yaml 是坏配置（6 值 vs 15 值，IMU 全 false） | ✅ |

---

## 三、详细记录

### 3.1 网络迁移：10.10.3.x → 10.18.18.x

**现象**：N97 enp1s0 改为 10.18.18.20/24；雷达经 VMware 网页配置改 IP 为 10.18.18.6。

**影响**：`~/.ros/velodyne_n97.launch.py` 中 `device_ip: '10.10.3.6'` 过时。
点云仍能收到（VLP-16 单向 UDP 流发往目标 host，N97 监听 2368 端口即可），
但驱动与雷达的交互通道断开（配置/错误检测不可用），日志持续告警。

**解决**：
```bash
sed -i 's/10\.10\.3\.6/10.18.18.6/' ~/.ros/velodyne_n97.launch.py
# 改完重启雷达驱动生效
```

**验证**：`ping 10.18.18.6` 通，点云正常。

**文档同步**：vlp16_slam_exploration.md / 02-progress.md / 03-current_state.md /
02-deploy-checklist.md / 01-plan.md / README.md 中所有旧网段已更新
（历史记录类文档保留旧值）。

---

### 3.2 KISS-ICP 里程计不走：use_sim_time 坑

**现象**：按文档命令启动 KISS-ICP 后 `/kiss_icp/odometry` 无输出/不走。

**根因**（实测 launch 源码）：`odometry.launch.py` 中
`use_sim_time = LaunchConfiguration("use_sim_time", default="true")` —— **默认 true**！
实车没有 `/clock` 发布者，KISS-ICP 一直等待 sim time。

**解决**：启动命令显式加 `use_sim_time:=false`：
```bash
ros2 launch kiss_icp odometry.launch.py \
  topic:=/velodyne_points base_frame:=velodyne \
  use_sim_time:=false visualize:=false
```

**教训**：第三方 launch 的默认值必须实测确认，不能照抄回顾文档
（vlp16_slam_exploration.md 的启动命令同样漏了这个参数，已修正）。

---

### 3.3 RViz 里 imu_link 标红

**现象**：Fixed Frame 设为 `imu_link` 时 RViz 标红。

**根因**：TF 树中没有 `imu_link`。G354 驱动（imu_node.py）只发布 `/imu/data` 话题，
从不广播 TF；且 EKF 未运行（无 `base_link→imu_link` 静态 TF）。

**解决**（方案二选一）：
- 方案 A（最快）：Fixed Frame 改为 TF 树中存在的 frame（如 `base_link`）——
  rviz_imu_plugin/Imu 显示纯读话题，不依赖 TF
- 方案 B（根治）：发布单位静态 TF
  ```bash
  ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 base_link imu_link
  ```
  并已固化进 `ekf.launch.py`（static_transform_publisher 节点，EKF 启动即带）

**验证**：imu_link 不再标红。

---

### 3.4 RViz 里 /imu/data 灰色不可选

**现象**：Add → By topic 中 `/imu/data` 灰色；数据链路本身正常
（`ros2 topic list` 有该话题，驱动日志正常）。

**根因**（两个）：
1. **N97 未装 `rviz_imu_plugin`**——Add → By display type 中搜不到 Imu
2. **QoS 不匹配**：驱动发布器默认 QoS（Reliable），RViz 显示插件默认
   Sensor Data（Best Effort），Reliable 发布者不兼容 Best Effort 订阅者

**检测命令**（先确认数据链路本身正常，排除话题层问题）：
```bash
ros2 topic info /imu/data -v | grep -E "Publisher|Subscriber"   # Publisher 应为 1
ros2 topic echo /imu/data --once                                 # 能收到数据
ros2 topic hz /imu/data                                          # ≈100Hz
```

**解决**：
```bash
sudo apt install ros-humble-rviz-imu-plugin
```
然后 Add → **By display type** → Imu → Topic 填 `/imu/data` → QoS Policy 改 **Reliable**。

**验证**：IMU 姿态箭头出现，随 IMU 移动实时跟随。

---

### 3.5 点云与 IMU 显示"打架"、不断震动

**现象**：加入 EKF 后，KISS-ICP 点云和 IMU 箭头在 RViz 中不断震动；
点云转换话题与 EKF 话题"打架"。

**排查**（`ros2 topic info /tf -v`）：**4 个发布者**——
`kiss_icp_node`、`r2_chassis_node`、`ekf_filter_node`、`robot_state_publisher`。
其中 chassis 和 EKF **同时发布 `odom→base_link`**。

**根因**：TF 双发布者。两个发布者以不同位姿（chassis 纯轮速积分 vs EKF 融合值）
轮流刷新同一变换，RViz 中所有挂在 base_link 系下的显示（点云、IMU 箭头）
在两个值之间横跳 → 表现为"打架"和"震动"。
（静态时两路都是 0 看不出，一动车立刻横跳——`tf2_echo` 静止时全为 0 曾误导判断）

**检测命令**：
```bash
# ① /tf 发布者清单——双发实锤：chassis 与 EKF 同时出现
ros2 topic info /tf -v | grep "Node name"

# ② 确认底盘参数已生效（False = 新代码在跑）
ros2 param get /r2_chassis_node publish_tf

# ③ 数据流判读（区分"双发横跳"与"单源异常"）：
#    双发 = x/y/z/yaw 整体横跳；单源 = x/y/z 平滑、仅个别通道异常
ros2 run tf2_ros tf2_echo odom base_link
```

**解决**：chassis_node 增加 `publish_tf` 参数（默认 true，保持单独使用兼容）：
- `chassis.launch.py` 声明并透传参数
- EKF 场景启动：`ros2 launch r2_bringup chassis.launch.py publish_tf:=false`
- `r2_startup.sh` 同步修改
- TF 由 EKF 统一发布

**验证**：`ros2 topic info /tf -v` 中 chassis 仍是发布者但**从不 sendTransform**
（TransformBroadcaster 构造即注册 publisher，"幽灵发布者"），
实际数据流中 `odom→base_link` 只有 EKF。tf2_echo 中 x/y/z 平滑连续
（单发布者特征），不再整体横跳。

**注意事项**：`/tf` 发布者列表中的 "幽灵发布者"（不 send 但注册）不算冲突，
判断依据是数据流（tf2_echo）而非列表。

---

### 3.6 chassis_node 启动崩溃：协方差 int 而非 float

**现象**：新增协方差后 chassis_node 启动即崩：
```
AssertionError: The 'covariance' field must be a set or sequence with length 36
and each value of type 'float'
```

**根因**：协方差列表写的是 `[1e-3, 0, 0, ...]`——`0` 是 int。
geometry_msgs 的 covariance 字段要求**每个元素都是 float**。
编译期（colcon build）不检查，运行时断言才触发。

**解决**：所有 `0` → `0.0`。

**运行时自检**（改消息字段后、同步前，本机最小复现）：
```bash
source /opt/ros/humble/setup.bash
python3 -c "
from nav_msgs.msg import Odometry
o = Odometry()
o.pose.covariance = [1e-3, 0.0]*18    # 36 个元素，必须全 float
o.twist.covariance = [1e-2, 0.0]*18
print('covariance 赋值通过')"
```

**验证**：自检通过 → 同步 N97 重编译 → 底盘正常启动。

**教训**：消息字段赋值必须考虑类型要求；"编译通过 ≠ 运行正常"，
涉及消息字段的修改要在目标环境跑一次（或本机最小复现自检）。

---

### 3.7 EKF yaw 每秒跳 10°+、z 漂到 12m：ekf.yaml 坏配置

**现象**（EKF 重启后仍存在）：
- `tf2_echo odom base_link` 中 yaw 在 -27°~+1.5° 间每秒跳 10°+
- `/odometry/filtered` 的 position.z 漂到 12.4m（静止时恒定）
- 静止时 yaw 稳定、动车时跳——模式为"运动触发跳变"

**排查路径**：
1. x/y/z 平滑、只有 yaw 跳 → 排除 TF 双发布（单源特征）
2. ekf.yaml 设计：yaw 100% 来自 IMU（odom0 yaw=false）→ 怀疑 IMU
3. 重启 IMU+EKF（对齐 yaw）→ 无效（时间戳证实 tf2_echo 数据在重启之后采集）
4. SSH 拉取 **N97 上的 ekf.yaml 对比** → 实锤：

| 配置项 | VM（正确） | N97（坏） |
|:-------|:-----------|:----------|
| odom0_config | 15 值：x,y + vx,vy（yaw false） | **6 值**：[true,true,false,false,false,false] |
| imu0_config | 15 值：roll,pitch,yaw + 角速度 | **6 值**：全 false |

**根因**：N97 上 ekf.yaml 是旧版坏配置——robot_localization 要求 config
**15 个值**（x,y,z,roll,pitch,yaw,vx,vy,vz,vroll,vpitch,vyaw,ax,ay,az），
N97 上只有 6 个且 imu0 全 false → **IMU 完全没参与融合** →
EKF 的 yaw 无任何观测 → 状态在 process noise 下随机游走 → yaw 大跳 + z 漂移。
（配置不合法但节点不报错，属隐式故障）

**检测命令**：
```bash
# ① 三路姿态对比（定位跳变源头：IMU 跳 → 数据问题；IMU 平、EKF 跳 → 融合配置问题）
ros2 topic echo /imu/data --field orientation
ros2 topic echo /odometry/filtered --field pose.pose.orientation

# ② 两端配置对比（重点：config 值个数应为 15，IMU 不应全 false）
#    VM 侧
grep -E "odom0_config|imu0_config" ~/Lin_workspace/r2_integration/r2_bringup/config/ekf.yaml
#    N97 侧（SSH）
ssh lin@192.168.1.210 'grep -E "odom0_config|imu0_config" ~/Lin_workspace/r2_integration/r2_bringup/config/ekf.yaml'
```

**修改命令**：
```bash
# ① 同步配置到 N97
scp ~/Lin_workspace/r2_integration/r2_bringup/config/ekf.yaml \
  lin@192.168.1.210:~/Lin_workspace/r2_integration/r2_bringup/config/

# ② N97 重编译（launch 从 install/share 读配置，必须 build 更新 install）
ssh lin@192.168.1.210 'source /opt/ros/humble/setup.bash && \
  cd ~/Lin_workspace/r2_integration && colcon build --packages-select r2_bringup'

# ③ 校验 install 里的配置已更新
ssh lin@192.168.1.210 'grep -A3 "odom0_config" \
  ~/Lin_workspace/r2_integration/install/r2_bringup/share/r2_bringup/config/ekf.yaml'

# ④ 重启 EKF
ros2 launch r2_bringup ekf.launch.py
```

**验证**：
- EKF 姿态与 IMU 姿态几乎完全一致（0.0226, 0.0283, 0.0172, 0.9992）→ 融合正确
- 静止时 EKF 姿态稳定（组间变化 ~1e-5）
- z 回到 -0.185m（process noise 缓慢漂移，无观测，无害，不参与 2D 导航）
- 帧率：IMU ~100Hz、EKF ~50Hz

**教训**：
1. 配置文件也是代码，跨机器同步时**必须覆盖**（本次只同步了 .py，漏了 .yaml）
2. 配置不合法时 robot_localization 不报错，行为异常要查配置
3. 排查顺序：先确认两端配置一致，再怀疑硬件/数据

---

### 3.8 运行规范：IMU 重启需与 EKF 对齐

**规则**（排障中确认）：
- IMU 重启后 yaw 归零（G354 校准完成后从加速度计重新初始化，yaw=0）
- **重启 IMU 必须同时重启 EKF**，否则两者 yaw 脱节
- IMU 启动后有约 2.5s 校准期（250 帧），**期间不可移动**（动了会污染零偏）

**启动顺序**：
```bash
# ① IMU（静止等待 "Init quat: qw=..." 出现）
ros2 launch g354_imu_driver g354_rviz.launch.py rviz:=false serial_port:=/dev/ttyACM1
# ② 校准完成后才启动 EKF
ros2 launch r2_bringup ekf.launch.py
```

---

## 四、修改文件清单

| 文件 | 改动 |
|:-----|:-----|
| `~/.ros/velodyne_n97.launch.py` | device_ip 10.10.3.6 → 10.18.18.6 |
| `r2_bringup/r2_bringup/chassis_node.py` | +publish_tf 参数（默认 true）；TF 广播加开关；+pose/twist 协方差（float） |
| `r2_bringup/launch/chassis.launch.py` | +publish_tf 参数声明与透传 |
| `r2_bringup/launch/ekf.launch.py` | +base_link→imu_link 静态 TF；修正 docstring（删去不存在的 ekf_only 参数） |
| `r2_bringup/config/ekf.yaml` | 修正为 15 值完整配置（N97 上原为 6 值坏配置） |
| `scripts/r2_startup.sh` | 底盘启动加 publish_tf:=false |
| `doc/phase1/ekf-verification.md` | 新增：EKF 实车验证清单（前置修复 4 项已全部落地） |
| `doc/retrospect/vlp16_slam_exploration.md` | 网段更新、use_sim_time 参数、键盘建图完成状态 |
| `doc/02-progress.md` / `doc/03-current_state.md` | IP 更新、Phase 2 键盘建图 ✅、待办更新 |
| `doc/02-deploy-checklist.md` / `doc/01-plan.md` / `README.md` | 旧网段批量更新（含 eth0→enp1s0、use_sim_time 参数） |

VM 与 N97 同步方式：scp（SSH 免密 192.168.1.210）+ N97 `colcon build`
（注意：launch/config 从 **install/share** 读取，同步源码后必须重编译才生效）。

---

## 五、当前状态（2026-08-02 检查通过）

全套节点运行中：IMU / EKF / 底盘(publish_tf:=false) / KISS-ICP / 键盘 / RViz / static TF。

| 检查项 | 结果 |
|:-------|:-----|
| EKF 姿态跟随 IMU | ✅ 几乎一致 |
| 静止时 EKF yaw 稳定 | ✅ 组间变化 ~1e-5 |
| EKF 帧率 | ✅ ~50Hz |
| IMU 帧率 | ✅ ~100Hz |
| odom→base_link 单一发布者 | ✅ |
| position.z | -0.185m（process noise 漂移，无害） |

---

## 六、遗留与待办

- [ ] EKF 实车验证（静态 3min / 直线 5m / 旋转 / 矩形闭环）— 清单见 [ekf-verification.md](../phase1/ekf-verification.md)
- [ ] waypoint 雷达闭环（基于 /kiss_icp/odometry 的自主行走节点）
- [ ] git 提交本日全部改动（VM 工作区积压未提交）
- [ ] z 轴 process noise 漂移（如需 3D 数据再处理，2D 导航无影响）

---

## 七、教训总结

1. **启动命令的默认值必须实测**：第三方 launch 的 `use_sim_time` 默认 true，
   照抄回顾文档会踩坑（文档已修正）
2. **配置文件也是代码**：跨机器同步必须全覆盖（.py/.yaml/.launch 一个不能漏），
   且 launch/config 从 install 目录读取，改完必须重编译
3. **"编译通过 ≠ 运行正常"**：消息字段有类型约束（如 covariance 必须 float），
   改动后要在目标环境跑一次或本机最小复现自检
4. **TF 双发布者判断**：看数据流（tf2_echo）而不是发布者列表——
   TransformBroadcaster 构造即注册 publisher，不 send 是"幽灵发布者"
5. **配置不合法可能不报错**：robot_localization 的 6 值 config 不拒绝、不告警，
   表现为 yaw 随机游走等隐式故障——异常先查两端配置一致性
6. **排障不要凭记忆/文档，要实测**：本日两次踩坑都是"照抄旧文档"
   （kiss_icp_ws 路径、use_sim_time、ekf.yaml 配置），实测后全部定位
7. **IMU 重启纪律**：校准期不可动、重启后必须同步重启 EKF
