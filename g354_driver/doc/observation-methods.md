# IMU 观测与诊断方法

> 适用于 Epson M-G354，通用 IMU 调试
> 更新: 2026-07-30

---

## 一、快速索引

| 方法 | 工具 | 用处 | 上手难度 |
|:-----|:------|:------|:---------|
| RViz2 3D 可视化 | `rviz2` | 看实时姿态 | ⭐ |
| rqt_plot 折线 | `rqt_plot` | 多分量历史趋势 | ⭐ |
| PlotJuggler | `plotjuggler` | 综合调试（推荐） | ⭐⭐ |
| Foxglove | `foxglove-studio` | 现代版 RViz | ⭐⭐ |
| topic echo | `ros2 topic echo` | 终端数值 | ⭐ |
| topic hz | `ros2 topic hz` | 帧率稳定性 | ⭐ |
| ros2 bag | `ros2 bag` | 录数据回放 | ⭐⭐ |
| CSV 导出 | `rosbags` + Python | 外部工具分析 | ⭐⭐⭐ |
| 零偏稳定性 | `topic echo angular_velocity` | 看校准质量 | ⭐ |
| 纯陀螺仪对比 | 改 `KP=0` 重启 | 看漂移本质 | ⭐⭐ |
| Allan 方差 | Python 脚本 | 噪声特性分析 | ⭐⭐⭐⭐ |

---

## 二、实时可视化

### 2.1 RViz2

```bash
source ~/Lin_workspace/g354_test/install/setup.bash
rviz2 -d ~/Lin_workspace/g354_test/config/g354_imu.rviz
```

- Fixed Frame: `imu_link`
- 黄色箭头: 姿态方向
- 红色箭头: 加速度
- 绿色箭头: 角速度

### 2.2 rqt_plot

```bash
# 安装
sudo apt install ros-humble-rqt-plot

# 启动图形界面
ros2 run rqt_plot rqt_plot

# 或命令行直接拉曲线
ros2 run rqt_plot rqt_plot \
  /imu/data/orientation/x \
  /imu/data/orientation/y \
  /imu/data/orientation/z \
  /imu/data/orientation/w
```

左侧勾选字段，右侧实时出图。适合看：
- 四元数各轴是否有缓慢漂移
- 静止时抖动幅度
- 翻转时曲线是否平滑

### 2.3 PlotJuggler（推荐）

```bash
# 安装
sudo apt install ros-humble-plotjuggler-ros

# 启动，自动加载 ROS2 话题
ros2 run plotjuggler plotjuggler
```

优势：
- 多轴同图对比（例如 acc Z vs 1.0g 参考线）
- 拖拽任意字段到画布
- 内置计算功能: 差、积、FFT（看噪声频谱）
- 可加载 ros2 bag 做离线分析
- 可导出 CSV

使用步骤:
1. 启动后左侧 `ROS2 Topic Subscriber` 拖出
2. 勾选 `/imu/data` → 展开各字段
3. 拖拽字段到右侧画布
4. 右键添加 `Timeseries` 或 `Scatter` 视图

### 2.4 Foxglove Studio

```bash
sudo snap install foxglove-studio
foxglove-studio
```

通过 WebSocket 连接 ROS2，支持 3D + 折线图 + 表格同时看。

---

## 三、终端数值监控

### 3.1 topic echo

```bash
# 只看四元数
ros2 topic echo /imu/data --field orientation

# 监控角速度（用于判断零偏）
ros2 topic echo /imu/data --field angular_velocity

# 监控加速度
ros2 topic echo /imu/data --field linear_acceleration

# 持续刷新
watch -n 1 "ros2 topic echo /imu/data --once | \
  grep -E 'orientation|angular|linear'"
```

### 3.2 帧率与带宽

```bash
# 帧率 + 抖动（标准差越小越好）
ros2 topic hz /imu/data

# 带宽
ros2 topic bw /imu/data
```

---

## 四、数据记录与回放

### 4.1 ros2 bag

```bash
# 录制（Ctrl+C 停止）
ros2 bag record /imu/data -o imu_test.bag

# 录制指定时长（如 30 秒）
ros2 bag record /imu/data -o imu_calib.bag -d 30

# 查看 bag 信息
ros2 bag info imu_test.bag

# 回放（配合 PlotJuggler 分析）
ros2 bag play imu_test.bag
```

可以用来对比不同版本滤波器的效果：录一段 motion 数据，在两个版本下分别回放，看姿态差异。

### 4.2 导出 CSV

```bash
pip3 install rosbags

python3 << 'SCRIPT'
from rosbags.rosbag2 import Reader
from rosbags.serde import deserialize_cdr
import csv

with Reader('imu_calib.bag') as reader:
    with open('imu_data.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['time_ns','qw','qx','qy','qz',
                     'gx_rad','gy_rad','gz_rad',
                     'ax_ms2','ay_ms2','az_ms2'])
        for conn, ts, raw in reader.messages():
            if conn.topic != '/imu/data':
                continue
            msg = deserialize_cdr(raw, conn.msgtype)
            w.writerow([
                ts,
                msg.orientation.w, msg.orientation.x,
                msg.orientation.y, msg.orientation.z,
                msg.angular_velocity.x, msg.angular_velocity.y,
                msg.angular_velocity.z,
                msg.linear_acceleration.x, msg.linear_acceleration.y,
                msg.linear_acceleration.z
            ])
print('imu_data.csv exported')
SCRIPT
```

导出的 CSV 可以用 Excel、MATLAB、Python (numpy/scipy) 做频谱分析、漂移分析、Allan 方差计算。

---

## 五、诊断性测试

### 5.1 陀螺仪零偏稳定性

**目的**: 判断静态校准的质量

```bash
# 启动节点，IMU 完全静止
ros2 run g354_imu_driver imu_node

# 另一终端观察 60 秒
ros2 topic echo /imu/data --field angular_velocity
```

| 结果 | 判断 |
|:-----|:------|
| 三轴稳定在 ±0.02 rad/s 以内 | ✅ 零偏校准良好 |
| 缓慢单向漂移 | ⚠️ 残留零偏未被完全消除 |
| 噪声幅度大 | ⚠️ 增大校准采样数 |

### 5.2 纯陀螺仪模式（对比 Mahony）

**目的**: 区分陀螺仪零偏问题和滤波器问题

```bash
# 修改 imu_node.py:
# MAHONY_KP = 1.0 → MAHONY_KP = 0.0
# 重启节点，观察 yaw 漂移速率
```

KP=0 时 Mahony 完全不用加速度计修正，只靠陀螺仪积分。此时 yaw 的漂移速率 = 陀螺仪 Z 轴残余零偏。如果这个漂移很大（> 2°/s），说明静态校准不够。

### 5.3 加速度计置信度

**目的**: 看滤波器对加速度计的信任程度

```bash
# orientation_covariance[0] 反推置信度
ros2 topic echo /imu/data --field orientation_covariance
```

- `cov[0] ≈ 0.001` → 高置信度（静止）
- `cov[0] ≈ 0.05` → 低置信度（运动中）
- 静止时 cov 不稳定 → 加速度计噪声大或有振动干扰

### 5.4 翻转响应测试

**目的**: 检查滤波器动态响应

手动将 IMU 分别绕 X/Y/Z 轴快速翻转 90°，观察:

| 观察项 | 正常 | 异常 |
|:-------|:-----|:------|
| 响应速度 | 0.2s 内跟上 | 滞后 > 0.5s |
| 回位精度 | 回到原位 ±1° | 偏离 > 5° |
| 是否有过冲 | 无 | 超过目标后又弹回 |

---

## 六、专业噪声分析: Allan 方差

**目的**: 获取 IMU 噪声特性的完整画像。最不直观但最专业的 IMU 指标。

### 原理

Allan 方差曲线横轴为积分时间 τ，纵轴为 Allan 标准差，不同 τ 区间反映不同噪声源:

```
log(σ)
  ↑
  │ ╲
  │  ╲  角度随机游走 (ARW)  ← 斜率 -0.5
  │   ╲
  │    ╲
  │     ─────────────────── 零偏稳定性 (bias instability) ← 谷底
  │                        ╱
  │                       ╱  速率随机游走 (RRW) ← 斜率 +0.5
  │                      ╱
  └──────────────────────────→ log(τ)
```

### 脚本

```python
import numpy as np
import matplotlib.pyplot as plt

# 加载 CSV（从 4.2 节导出）
data = np.genfromtxt('imu_data.csv', delimiter=',', skip_header=1)
gyro_z = data[:, 6]            # gz 列 (rad/s)
fs = 100.0                      # 采样率 (Hz)

tau = np.logspace(0, 3, 100)    # 1s 到 1000s
avar = []

for t in tau:
    n = int(t * fs)
    if n >= len(gyro_z) // 2:
        break
    diff = gyro_z[::n][1:] - gyro_z[::n][:-1]
    avar.append(0.5 * np.mean(diff**2))

plt.figure(figsize=(10, 6))
plt.loglog(tau[:len(avar)], np.sqrt(avar), 'b-', linewidth=2)
plt.xlabel('Integration Time τ (s)', fontsize=12)
plt.ylabel('Allan Deviation σ(τ) (rad/s)', fontsize=12)
plt.title('Gyroscope Z-Axis Allan Variance', fontsize=14)
plt.grid(True, which='both', alpha=0.3)
plt.savefig('allan_variance.png', dpi=150)
print('Saved allan_variance.png')
```

### 指标解读

| 指标 | 含义 | 好 IMU | 普通 IMU |
|:-----|:------|:-------|:---------|
| 角度随机游走 | 高频噪声 | < 0.1°/√h | > 0.5°/√h |
| 零偏稳定性 | 长时间漂移 | < 1°/h | > 10°/h |
| 谷底位置 | 最优积分时间 | > 100s | < 10s |

---

## 七、快速对比清单

改前改后对比，按这个清单测试:

```bash
# 1. 录制基准
ros2 bag record /imu/data -o baseline.bag -d 30

# 2. 看帧率
ros2 topic hz /imu/data

# 3. 静态稳定性（终端观察 10s）
ros2 topic echo /imu/data --field angular_velocity

# 4. 动态响应（手动翻转 IMU，观察 RViz）

# 5. 导出 CSV
# python3 << 'SCRIPT' ...（见 4.2）

# 6. 计算 Allan 方差
# python3 allan_variance.py

# 7. 改版本后重复 1-6，对比差异
```

## 八、文件清单

```
doc/
├── completion-report.md    Phase 完成报告
├── debug-log.md            调试日志
└── test-flow.md            基础测试流程（硬件检查/启动/ROS2）
└── observation-methods.md  ← 本文件（观测与诊断方法）
```
