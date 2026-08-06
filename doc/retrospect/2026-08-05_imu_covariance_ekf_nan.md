# IMU 协方差病态导致 EKF NaN 发散排障全记录

> 日期: 2026-08-05
> 机器: N97（192.168.1.210）+ 开发 VM（lin-virtual-machine，192.168.1.204）
> 场景: rviz2 同时开启三个 odom（/odom_wheels、/kiss/odometry、/odometry/filtered）→ 警告刷屏
> 状态: ✅ 已修复并实机验证，提交 `5424f3d`

---

## 一、背景

2026-08-05 完成 N97 远程桌面（TigerVNC）搭建后，在 rviz2 中同时启用三个 odom
显示进行联调，出现两类报错：`Negative eigenvalue found for position` 与
EKF 输出全 NaN。本记录完整存档现象、定位过程、根因、修复与验证。

---

## 二、问题总览

| # | 现象 | 根因 | 状态 |
|:--|:-----|:-----|:----:|
| 1 | rviz2 报 `Negative eigenvalue ... covariance matrix correct?` | `/odometry/filtered` 协方差全 `.nan` | ✅ |
| 2 | `/odometry/filtered` 位姿 + 协方差全 NaN | EKF 状态发散且无法自愈 | ✅ |
| 3 | rviz2 报 `Message Filter dropping ... queue is full` | NaN 变换被 tf2 拒收（`TF_NAN_INPUT`），TF 树无有效变换，过滤器干等 | ✅（随 1 修复消失） |
| 4 | EKF 日志 `NaNs detected ... poorly conditioned covariances` | IMU 协方差矩阵奇异（见根因） | ✅ |

---

## 三、详细记录

### 3.1 现象复现

rviz2 中启用三个 odom 显示后：

```
[rviz2]: Negative eigenvalue found for position.
         Is the covariance matrix correct (positive semidefinite)?
```

### 3.2 定位过程（逐层排查）

1. **三个 odom 协方差逐个对比**（`ros2 topic echo <topic> --once`）：

   | 话题 | 协方差 | 判定 |
   |:-----|:-------|:----:|
   | `/odom_wheels`（底盘） | 0.001 对角阵 | ✅ 正常 |
   | `/kiss/odometry`（KISS-ICP） | 0.1 对角阵 | ✅ 正常 |
   | `/odometry/filtered`（EKF 融合输出） | **全部 `.nan`** | ❌ 病源 |

2. **EKF 输出位姿本身也是 NaN**（x/y/z 全 `.nan`）——不是协方差单点问题，
   是 EKF 滤波器状态整体发散。

3. **EKF 日志自述**：

   ```
   Critical Error, NaNs were detected in the output state of the filter.
   This was likely due to poorly conditioned process, noise, or sensor covariances.
   ```

4. **检查两个输入源当时数据**：IMU 姿态/角速度/线加速度均无 NaN，轮速里程计正常
   ——NaN 是历史瞬态进入后 EKF 永久带病（robot_localization 无自愈能力）。

5. **查 IMU 消息协方差**，找到病根：

   ```
   orientation_covariance:       0.0022 0.0022 0.0022
                                 0.0022 0.0022 0.0022
                                 0.0022 0.0022 0.0220
   angular_velocity_covariance:  全部 0.0001
   ```

   **3×3 协方差矩阵的全部 9 个元素（含 6 个非对角项）填了同一个值**，
   非对角全相等的矩阵是**奇异矩阵**（存在 0 特征值）。

### 3.3 根因

`g354_driver/g354_imu_driver/imu_node.py`（发布 /imu/data）：

```python
# 原实现（错误）：[base] * 9 把 3×3 矩阵全部 9 个槽填同一个值
msg.orientation_covariance = [base] * 9
msg.orientation_covariance[8] = base * 10
msg.angular_velocity_covariance = [0.0001] * 9
msg.linear_acceleration_covariance = [0.0001] * 9
```

协方差矩阵只有对角线有意义，非对角项必须为 0（各轴独立假设）。
全填充导致矩阵奇异 → EKF 每次更新求逆时除零 → 数值爆炸 → NaN。
发散是慢性的（约 20 分钟），与"跑一会才爆"的现象吻合。

### 3.4 修复

改为对角阵，保留 ZUPT 动态置信度逻辑（静止置信高 → 协方差小）：

```python
# 修复后：非对角项填 0
msg.orientation_covariance = [base, 0.0, 0.0,
                              0.0, base, 0.0,
                              0.0, 0.0, base * 10]
msg.angular_velocity_covariance = [0.0001, 0.0, 0.0,
                                   0.0, 0.0001, 0.0,
                                   0.0, 0.0, 0.0001]
msg.linear_acceleration_covariance = [0.0001, 0.0, 0.0,
                                      0.0, 0.0001, 0.0,
                                      0.0, 0.0, 0.0001]
```

### 3.5 验证（实机）

- 车体多次运动后 `/odometry/filtered` 无 NaN，位姿为有效数值
- IMU 协方差对角化确认，且随运动动态变化（静止 ≈0.0011 ↔ 运动 ≈0.0028，ZUPT 生效）
- rviz2 负特征值警告消失

### 3.6 提交与同步

- 流程：N97 实机验证通过 → N97 提交（`5424f3d`）→ push → VM pull 同步
- 注：修复提交时排障文档未就绪，未按规范在 body 关联本 retrospect，以此文档补记

---

## 四、关联

- 远程桌面搭建与跨机 DDS 方案：见 [2026-08-05_n97_remote_desktop.md](2026-08-05_n97_remote_desktop.md)
- EKF 融合链路历史排障：见 [2026-08-02_ekf_tf_fusion_fix.md](2026-08-02_ekf_tf_fusion_fix.md)

---

## 五、遗留问题（待处理）

| # | 问题 | 现象 | 建议 |
|:--|:-----|:-----|:-----|
| 1 | z 方向漂移 | z 无任何测量但漂到 44m（当日从 10.8m 持续增长） | 收紧 z/vz 过程噪声，或排查 roll/pitch 耦合 |
| 2 | EKF `process_noise_covariance` 未显式配置 | 当前用 robot_localization 默认值 | 按实车特性显式配置 |
| 3 | EKF 无 NaN 自愈能力 | 输入一旦含 NaN 永久带病 | 驱动层（chassis/imu）发布前过滤 NaN |
