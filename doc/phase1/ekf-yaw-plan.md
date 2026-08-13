# EKF yaw 融合问题预案（2026-08-09）

> 状态：✅ **已实施并验证通过（2026-08-12）**。z 漂移已修复（见 [retrospect/2026-08-09_ekf_z_drift_fix.md](../retrospect/2026-08-09_ekf_z_drift_fix.md)）。
> 方案①（odom0 开放 yaw）于 08-12 实施（commit 5c46c58），实车验证数据见文末「验证结果」。

## 问题现状（bag 实测 `ekf_yaw_test_0809`）

- **f-i 恒 ≈ 0**：`/odometry/filtered` 的 yaw 100% 跟随 IMU 纯积分 yaw（G354 无磁力计）
- **起点偏置随机**：与 `/odom_wheels` 起点差 -6.6°（上次录制 +10.5°）→ 每次上电的零点差异，非固定安装角
- **运动偏差**：净转角 370° 测试中峰值 -14°（左转 90° 后），终点差 -5.7°
- 根因：[ekf.yaml](../r2_bringup/config/ekf.yaml) `odom0_config` yaw=false（原注释"轮速 yaw 打滑误差大"），
  yaw 唯一来源 = IMU 纯积分

## 目标

1. 消除起点偏置（每次上电随机 ±10°）
2. 运动中 yaw 偏差收敛到打滑允许范围（目标 <3°）

## 方案对比

| 方案 | 改动 | 优点 | 代价/风险 |
|:--|:--|:--|:--|
| **① odom0 开放 yaw**（推荐） | `odom0_config` yaw: false→true | yaw 以轮速编码器为绝对基准，无漂移、无起点偏置；EKF 内与 IMU wz 平滑 | 打滑时 yaw 短期失真（全向轮打滑是慢漂移，可接受） |
| ② imu0 yaw 改 differential | `imu0_differential: true` | 起点偏置消失（yaw 零点跟随 EKF） | IMU 积分漂移仍通过差分累积，运动中偏差改善有限 |
| ③ 保持现状 | — | 无需改动 | 每次上电偏置随机，建图/导航起点朝向错 6~10°，运动中再漂 |

## 方案① 具体改动（已实施 08-12）

```yaml
# ekf.yaml odom0 段
odom0_config: [true, true, false,      # x, y, z
               false, false, true,     # roll, pitch, yaw ← 轮速开放 yaw
               true, true, false,      # vx, vy, vz
               false, false, false,    # vroll, vpitch, vyaw
               false, false, false]    # ax, ay, az
```

同步 install 副本（坑：launch 加载 install 路径，见 retrospect）后重启。

## 验证方法（录包动作序列）

```bash
ros2 bag record /odometry/filtered /odom_wheels /tf /imu/data /cmd_vel -o ~/bags/ekf_yaw_v2_0809
# ① 静止 10s  ② 直线前进 2m 停  ③ 原地左转 90° 停
# ④ 直线前进 1m 停  ⑤ 原地右转 180° 停  ⑥ 直线后退 2m 停  ⑦ 静止 10s
```

**验收指标**：
- 起点 f-w < 2°（原 6.6~10.5°）
- 全称 |f-w| < 5°（原峰值 14°）
- z 保持 0.000000（回归项）
- 每步转弯后 f-w 回落（不累计）

## 回滚

- 撤销 ekf.yaml 一处改动（yaw true→false），同步 install，重启即可
- 已提交历史可 `git revert`（若已提交）

---

## 验证结果（2026-08-12 实施并验证通过）

**实施**：`odom0_config` yaw false→true（[commit 5c46c58](https://github.com/Linforesthello/r2_integration/commit/5c46c58)）+ N97 install 副本手动同步 + 重启 EKF。

**验证 bag**：`ekf_yaw_v2_0812`（N97 录制，223s，含 90° 左转 + >180° 右转 + 直行/后退，动作序列比预案更完整）

| 指标 | 实测 | 验收 | 结果 |
|:--|:--|:--|:--|
| 起点 f-w（前 8s 静止） | 0.00° | < 2°（原 6.6~10.5°） | ✅ |
| 全程 \|f-w\| 峰值（等间隔采样，含 90°/190° 转弯段） | 0.07° | < 5°（原峰值 14°） | ✅ |
| 终段 f-w | 0.02° | 不累计 | ✅ |
| filtered z（全程含转弯） | 0.00000000 | 恒 0（two_d_mode） | ✅ |

**附加验证**：转弯段 IMU wz vs odom twist wz 比例 1.02~1.03（角速度一致）；轮速里程计 yaw 积分本身正确
（90° 左转 +12.9°→+64°、190° 右转 -17.4°→+169.7° 跨 wrap）——EKF 现在锚定的是正确轮速。

**结论**：方案①达标，EKF yaw 起点偏置与运动偏差均消除，z 保持 0。可回滚项保留以上参数。

