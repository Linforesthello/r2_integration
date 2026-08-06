# 底盘彻查 + EKF 过程噪声 bug 排障（进行中存档）

> 日期: 2026-08-05
> 机器: N97（192.168.1.210）+ 开发 VM（192.168.1.204）
> 状态: ⏸ **进行中，用户临时离开**。代码修复已就位、EKF 已验证；底盘重启验证未做。
> 本文件为本地存档，**未提交 git**，回来确认后提交。

---

## 一、问题脉络（三条线汇合）

### 线 1：/odometry/filtered 与 KISS-ICP 位置差 5 米（闭环测试发现）

车开回原点后三家对照：

| 来源 | x/y | yaw | 判定 |
|:-----|:-----|:-----|:-----|
| IMU/EKF | - | -1.27° | ✅ 与 KISS 吻合 |
| KISS-ICP | 0.55m | -0.95° | ✅ 独立验证 IMU |
| 轮速 | 5.5m | **-57.7°** | ❌ 唯一 outlier |

### 线 2：底盘代码彻查 → 两个 bug

| Bug | 位置 | 影响 |
|:----|:-----|:-----|
| **omega 单位多除轮半径** | chassis_node.py:394 | omega 放大 13.2 倍 → 轮速 yaw 虚高 → 圆弧半径缩小 → 位置积分雪上加霜 |
| **odom 积分非全向模型** | chassis_node.py:433-447 | 直线分支不旋转到 odom 系 + 圆弧分支为差速车模型 |

**修复已应用**（chassis_node.py，N97 源码 + 已编译）：
- omega 换算去掉 `/ (wheel_diameter/2)`
- 积分统一为全向轮标准式（车体系速度经 yaw 旋转）

### 线 3：EKF 重启即 NaN（显式 process_noise 触发）

**现象**：任何显式 `process_noise_covariance`（15 值对角）→ 启动 0.15s 即 NaN；
不设置 → 正常（但 z 长期漂移 10→44→85m）。

**根因（debug_out_file 抓到）**：robot_localization **3.5.4** 加载 15 值参数时
**只填了 15×15 矩阵的第一行，其余 14 行是未初始化内存垃圾**（1.6e-322 等非正规数）
→ 矩阵奇异 → 求逆 → NaN。**必须用完整 225 值矩阵（行优先展开）**。

**社区佐证**：[robotics.stackexchange 112603](https://robotics.stackexchange.com/questions/112603/robot-localization-getting-nan-fusing-odometry)
报告同类现象（初始协方差加载成垃圾值），判定为版本相关初始化 bug。

**修复已应用并验证**（ekf.yaml，225 值矩阵，对角：
x/y=0.01, z=1e-6, roll/pitch=0.001, yaw=0.005, vx/vy=0.01, vz=1e-6,
vroll/vpitch/vyaw=0.01, ax/ay/az=0.1）：
✅ EKF 启动无 NaN，z 从 ~0 起步（不再漂）

---

## 二、当前状态

| 项 | 状态 |
|:---|:---|
| chassis_node.py 修复（omega + 全向积分） | ✅ 源码+编译，**未实车验证** |
| ekf.yaml 225 值过程噪声 | ✅ 已验证（NaN=0，z≈0） |
| 运行中的 chassis 进程 | ❌ 仍是旧代码（20:38 启动），**需重启** |
| 自转/闭环实车验证 | ⏸ 未做 |
| git 提交 | ⏸ 未提交（N97 工作区有 chassis_node.py + ekf.yaml 两处改动） |
| 文档更新（chassis_definition.md / 本存档） | ⏸ 未提交 |

---

## 三、续传步骤（回来后按此执行）

### 1. 重启 chassis（让修复生效）

```bash
# N97，Ctrl-C 旧 chassis launch 后：
ros2 launch r2_bringup chassis.launch.py publish_tf:=false &
```

### 2. 自转验证（VM 发指令）

```bash
# VM（DDS 已通）：
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export FASTRTPS_DEFAULT_PROFILES_FILE=/home/lin/Lin_workspace/fastdds_peer_n97.xml
source /opt/ros/humble/setup.bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/msg/Twist "{angular: {z: 0.5}}"  # 跑 2 秒后 Ctrl-C
```

判定：`/odom_wheels` yaw 应 ≈ +1.0 rad（修复前虚高 13 倍）。

### 3. 闭环回原点

开车绕一圈回原点 → 轮速 x/y 与 KISS-ICP 误差应 <1m（修复前 5m）。

### 4. z 漂移观察

EKF 跑一段时间（开车）后看 `/odometry/filtered` 的 z 是否还涨（应稳定 ~0）。

### 5. 提交

```bash
cd /home/lin/Lin_workspace/r2_integration
git add r2_bringup/config/ekf.yaml r2_bringup/r2_bringup/chassis_node.py
git commit  # 标题建议: R2|底盘里程计修复+EKF过程噪声225值矩阵，详见本 retrospect
git push
```

VM 侧 `git pull` 同步；文档更新：
- `doc/phase0/chassis_definition.md` 补 odom 积分公式
- 本存档同步 Obsidian 镜像

---

## 四、关键知识点（防再踩）

1. **robot_localization 3.5.4**：`process_noise_covariance` 必须给**完整 225 值**（15×15 行优先），15 值对角格式会触发加载 bug → 启动即 NaN
2. **chassis omega 正解**单位是 `逻辑速度/R`，转 rad/s 只除 speed_scale，**不能除轮半径**
3. **全向轮里程计积分**：车体系速度必须经 yaw 旋转到 odom 系，不能套差速车圆弧模型
4. **EKF 排障工具**：`debug: true` + `debug_out_file: "/tmp/xxx.txt"`（无默认路径，必须手动填）
