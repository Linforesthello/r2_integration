# 重录操作卡：问题①「costmap 远端不刷新」全话题复录

> 日期：2026-08-25
> 背景：W3 避障 3 bag（1357/1401/1405）仅录 9 话题，**漏录 /velodyne_points（底层点云）与 costmap 系列（核心证据）**——
> 按 ros2-ops.md §9 先验原则（核心输入缺失 → 重录），补录全链路数据。
> 目标：拿到 points→scan→costmap 三层同框数据，一次闭环定位问题①断点。
> 执行机：N97（192.168.1.210）；分析机：VM。关联：[costmap_experiment.md](costmap_experiment.md)、[ros2-ops.md §9](../ros2-ops.md)

---

## 0. 前置（07-handover §三顺序）

```bash
# 0.1 CPU performance（每次开机必做）
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# 0.2 全栈启动（分终端，顺序固定）：
#    CAN → 雷达(r2_sensors velodyne.launch.py) → 底盘(publish_tf:=false)
#    → IMU(静止 3s 校准) → EKF → Nav2(降额参数) → rviz
# 0.3 rviz 设初始位姿（只设一次，设完先动一下确认收敛）
```

⚠️ 确认 `/scan` 在跑（Nav2 依赖 velodyne_laserscan，08-15 曾停用，Nav2 场景须恢复）。

## 1. 核实话题（录制前必做，以 N97 实际输出为准）

```bash
ros2 topic list | grep -E "velodyne|scan|costmap|odom"
# 预期至少出现：
#   /velodyne_points /scan
#   /local_costmap/costmap /local_costmap/costmap_raw /local_costmap/voxel_grid
#   /local_costmap/clearing_endpoints /local_costmap/published_footprint
#   /global_costmap/costmap /global_costmap/costmap_raw /global_costmap/clearing_endpoints
#   /odometry/filtered /odom_wheels
```

## 2. 录制命令

```bash
ros2 bag record -o ~/Lin_workspace/r2_integration/bags/relog_$(date +%m%d_%H%M) \
  /velodyne_points /scan \
  /local_costmap/costmap /local_costmap/costmap_raw /local_costmap/voxel_grid \
  /local_costmap/clearing_endpoints /local_costmap/published_footprint \
  /global_costmap/costmap /global_costmap/costmap_raw /global_costmap/clearing_endpoints \
  /odometry/filtered /odom_wheels /cmd_vel /cmd_vel_smoothed /goal_pose /amcl_pose \
  /map /tf /tf_static
```

## 3. 场景流程（车全程静止，~2 分钟）

| 步骤 | 动作 | 时长 | 目的 |
|:---|:---|:---|:---|
| ① | 车静止，开始录 bag | — | 基准帧 |
| ② | 箱子放车头正前方 **2m**（对准雷达 +x 方向） | 20s | 近端基线（应 mark） |
| ③ | 移箱到 **4m**（人经过车头属正常） | 20s | **问题①关键判定点** |
| ④ | 移箱到 **6m**（< obstacle_max_range 8.0 边界内） | 20s | 远端判定点 |
| ⑤ | 移箱出视野，人站车头 **3m** 停留 | 10s | 远端 mark + 移走清除验证 |
| ⑥ | 人走开，结束录 bag | 5s | 收尾 |

> 障碍用**高箱**（≥0.3m³，别用矮物——避免③低矮盲区干扰判定）。
> 箱子每次放好后稍等 1~2s 让 costmap 刷新（update 5Hz）再进入下一段。

## 4. 预期现象（rviz 现场看）

- 2m：黑色格出现 ✓（近端已知正常）
- 4m / 6m：**问题①判定点**——出现 → costmap 侧排除，疑点转向显示/MPPI 前瞻；不出现 → 现场复现
- 移箱后：原位置黑色格消失（clearing 生效）
- 全程留意：黑色格出现的位置是否精确对应箱子实际位置（偏移 = 另一类线索）

## 5. 事后分析（VM，三层断点判定表）

| 层 | 话题 | 有障碍数据 → | 无 → |
|:---|:---|:---|:---|
| 感知 | /velodyne_points | 雷达 OK | **雷达物理盲区**（高度/角度/供电） |
| 转换 | /scan | 转换 OK | velodyne→scan 层（min/max_range 过滤） |
| 代价地图 | /local_costmap/costmap_raw（254/253 计数）+ voxel_grid | mark 管线 OK | costmap 处理层（QoS/过滤/plugin） |

**断点 = 从上往下第一处断的层**。三层全有 → 问题①归「显示层/MPPI 前瞻」（与问题②同根因）。

## 6. 收尾

```bash
# bag 拷 VM（不入 git，直接 scp）
scp -r ~/Lin_workspace/r2_integration/bags/relog_* lin@192.168.1.204:~/Lin_workspace/bags/raw/
# 记录：障碍实际距离、现场 rviz 观察现象（文字/截图）→ 发给 VM 侧留档
```

> 录制后核对 metadata.yaml 话题数与帧率（ros2-ops.md §9.3 预防措施）。
