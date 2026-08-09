# 2026-08-09 EKF z 漂移修复记录（two_d_mode）

## 问题现象

- rviz2（Fixed Frame=odom）中车体前后运动时，IMU 模型"空中前进+升起/后退+降落"
- bag 实测（`ekf_pure_0809_2013`）：`/odometry/filtered` 与 TF `odom→base_link` 的 **z 从 0 漂到 55.7m**（5 分钟录制）
- 漂移规律：**仅运动时上涨，静止时完全冻结**（六位小数不动）
- 另发现 EKF 终端持续 `Failed to meet update rate!`（单次更新 26~46ms > 20ms 周期，实际 22~38Hz）

## 根因

1. **z/vz/az 无测量约束**：ekf.yaml 中 odom0/imu0 均不给 z/vz/az（平面底盘合理），但 15 维 EKF 预测步中
   姿态（roll/pitch）变化与水平速度存在耦合，可经无约束的 vz 状态积分出 z 漂移
   （社区佐证：robot_localization Troubleshooting；姿态-速度耦合是已知行为）
2. **az 过程噪声过大**：`process_noise_covariance` 第 14 个对角元 az=0.1，协方差持续膨胀
3. **性能积压放大**：100Hz imu + 50Hz odom = 150 测量/秒，超过 50Hz 处理能力 → 测量积压 →
   预测 dt 拉大 → 漂移放大（"仅运动时涨"与积压+残差驱动耦合吻合）

## 修复（ekf.yaml）

| 改动 | 值 |
|:--|:--|
| `two_d_mode` | `true`（锁死 z/roll/pitch 及其速度，官方标准做法） |
| `frequency` | 50 → 30（消除 update rate 积压） |
| az 过程噪声 | 0.1 → 1e-06 |

## ⚠️ 关键坑：ros2 launch 加载的是 install 副本

`ekf.launch.py` 的 `pkg_dir` 取自 launch 文件位置（`os.path.dirname(os.path.dirname(abspath(__file__)))`），
`ros2 launch` 实际加载 **`install/r2_bringup/share/r2_bringup/config/ekf.yaml`**，而非源码
`r2_bringup/config/ekf.yaml`。

**后果**：改源码配置后不 build/不同步 install，EKF 仍跑旧配置 → 首次验证"还是会飞"，
实际是配置根本没加载（md5 对比实锤：install=旧版 80bc0573，源码=新版 d286b81f）。

**对策**：改配置后执行 `colcon build --packages-select r2_bringup`，或手动 `cp` 到 install 副本；
验证前用 `ps` 看 `--params-file` 实际路径 + `md5sum` 对比两处文件。

## 验证结果

- 2026-08-09 实车：two_d_mode 生效后 z 锁死为 0，rviz2 不再升天 ✅
- 遗留：**yaw 偏差问题未处理**——filtered yaw 完全跟随 IMU 纯积分 yaw（f-i 恒为 0），
  与轮速里程计起点差 ~10.5°、运动中差 13~30°（独立问题，见主对话分析）

## 相关文件

- `r2_bringup/config/ekf.yaml`（修复点）
- `g354_driver/g354_imu_driver/imu_node.py`（IMU/Mahony，未改动）
- `r2_bringup/launch/ekf.launch.py`（install 路径来源）
