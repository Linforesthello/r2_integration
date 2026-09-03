# D0 系统现状审计结论（2026-08-06）

> 原始输出: [0status_list.md](0status_list.md)（节点/话题/TF）+ [0status_hz.md](0status_hz.md)（频率）
> TF 树快照: [frames_2026-08-06_21.40.43.pdf](frames_2026-08-06_21.40.43.pdf) / [.gv](frames_2026-08-06_21.40.43.gv) / [.png](frames_2026-08-06-1.png)
> 关联计划: [plan.md](plan.md) W1 D0

---

## 一、节点层 ✅

13 个核心节点全在（ekf/g354/kiss/chassis/teleop/robot_state_publisher/static_transform/velodyne×3/rviz + transform_listener×3 内部节点）。无幽灵发布者。少 rqt（可选）。

## 二、话题层 ✅（2 注意点）

| 话题 | 发布 → 订阅 | 结论 |
|:---|:---|:---|
| /velodyne_points | transform → laserscan + kiss_icp | ✅ 闭合；⚠️ QoS 混用（发 RELIABLE / KISS 订 BEST_EFFORT，能通降级匹配） |
| /kiss/odometry | kiss_icp → 仅 rviz | ⚠️ 孤儿数据（W2 map→odom 桥将消费） |
| /odom_wheels | chassis → ekf + rviz | ✅ |
| /imu/data | g354 → ekf + rviz | ✅ |
| /odometry/filtered | ekf → rviz | ✅（W2 planner 加入） |
| /cmd_vel | teleop → chassis | ✅ |

## 三、TF 层 ✅ 定案（本次审计最大成果）

**TF 树（定案后）**:
```
odom → base_link → velodyne (z=0.56) / imu_link
odom_lidar → velodyne（KISS 独立树）
```

| 项 | 定案值 | 说明 |
|:---|:---|:---|
| base_link 离地 | **13cm**（用户实测） | URDF base_joint 0.075→**0.13** |
| 雷达光学中心离地 | **69cm**（用户实测） | |
| base_link→velodyne | **0.56m**（69-13） | URDF velodyne_joint 0.695→**0.56** |
| base_footprint | **已删除** | 双父冲突（base_link 同时有 odom+base_footprint 两父，TF2 拒绝致孤立帧）；无人使用，最小修复删除 |

**验证**：`tf2_echo odom base_link` 正常（RPY 3.2°/2.6° 为 IMU 真实安装姿态）；`base_footprint` 不存在；frame 快照已存档。

## 四、频率层 ⚠️ 2 记录项

| 话题 | 实测 | 判定 |
|:---|:---|:---|
| /imu/data | 93.5Hz（std 0.002） | ✅ |
| /odom_wheels | 49.99Hz（std 0.001） | ✅ |
| /odometry/filtered | 49Hz，**max 0.332s 抖动** | ⚠️ EKF 偶发卡顿（update rate 问题，W2 前留意） |
| /velodyne_packets | **9.9Hz（std 0.001）** | ✅ 驱动完美 |
| /velodyne_points | **6.4Hz（max 1.007s）** | ⚠️ transform 层偶发丢帧（socket 层当前 0 drops，1809 次 buffer errors 为历史累计） |
| /kiss/odometry | 7.9Hz（跟随雷达） | ⚠️ 受上游掉帧影响 |

**CPU 画像**：kiss_icp 42.6% / rviz2 33.4% / imu 16.7% / gnome-shell 15.8% / chassis 13.5% / ekf 10.2% / transform 4.1%（不忙，排除处理慢假设）；负载 3.36。

## 五、遗留项（按"先端到端再优化"暂不深挖）

1. velodyne transform 偶发丢帧（驱动/网络/ socket 均健康——疑似负载高峰调度延迟；建图质量受影响再回来查）
2. EKF 输出偶发 332ms 抖动
3. /velodyne_points QoS RELIABLE 发布（可考虑改 BEST_EFFORT，后置）

## 六、定量基线（2026-08-08 录 bag：sys_audit_0808_2036，132.5s）

> 分析脚本: `~/Lin_workspace/r2_integration/bags/analysis/analyze_audit.py`（官方 rosbag2_py）

| 指标 | 结果 | 判定 |
|:---|:---|:---|
| 静止 30s 漂移 | 轮速/EKF 0.0cm、KISS 0.2cm（yaw ≤0.03°） | ✅ 零漂移 |
| EKF vs IMU yaw | 全程偏差 ≤0.2° | ✅ 融合正确（yaw 来自 IMU） |
| 轮速 vs IMU yaw | 恒偏置 2.3°（起点朝向差）；**快速转弯时滞后 5-7°**，转到位收敛 | ⚠️ 轮速 yaw 动态滞后（滑移物理现象；Nav2 用 EKF 不受影响） |
| EKF 位置跳变（>0.5m/帧） | **0 次** | ✅ |
| 闭环回起点 | 轮速 0.01m / EKF 0.01m / KISS 0.03m | ✅ <3cm，里程计健康 |

**结论**：位置层无异常。rviz2 中"odom 显示不对"的观感大概率来自 **KISS 的 odom_lidar 系与 EKF 的 odom 系同时叠加显示**（两套坐标系原点不同），非数据错误。

## 七、修改清单（本审计落地，暂未提交）

- N97 `~/.ros/r2_description/r2.urdf`：base_joint 0.13、velodyne_joint 0.56、删除 base_footprint、注释定案（备份 .bak_20260806）
- 待同步：sensor-mount.md（65/77 冲突 → 69/13/56 定案，已改本地）
