# W1 操作手册：TF 工程 + 建图落地

> 关联计划: [plan-minimal-loop.md](plan-minimal-loop.md) W1（08-06 ~ 08-12）
> 执行机器: N97（192.168.1.210，需开机）+ VM（调试/分析）
> 前置: 全栈节点可启动（r2_startup.sh 或手动 launch）

---

## D1：TF 树工程（先于建图，避免 W2 卡）

### 1.1 启动全栈（顺序与 07-handover 一致）

```bash
# N97，每个终端 source 后启动
export FASTRTPS_DEFAULT_PROFILES_FILE=/home/lin/fastdds_wellknown.xml
source /opt/ros/humble/setup.bash && source ~/Lin_workspace/r2_integration/install/setup.bash

# ⚠️ 前置: CPU 性能模式（每次开机必做；重启恢复 powersave 后 KISS 掉 3.6Hz 重影复现，见 retrospect 08-11）
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor   # 检查 → performance

# 终端 0: CAN 总线
python3 ~/Lin_workspace/command/can_command.py

# 终端 1: 雷达（~/.ros/velodyne_n97.launch.py 为三节点合一，device_ip 10.18.18.6）
ros2 launch ~/.ros/velodyne_n97.launch.py

# 终端 2: KISS-ICP（⚠️ 必须先 source kiss_icp_ws；visualize:=true 才发布点云话题）
source ~/kiss_icp_ws/install/setup.bash
ros2 launch kiss_icp odometry.launch.py \
  topic:=/velodyne_points base_frame:=velodyne \
  use_sim_time:=false visualize:=true
# ⚠️ 建图前需实机确认: /kiss/frame 是否依赖 visualize（false 时无点云话题则累积脚本无数据）

# 终端 3: 底盘（EKF 场景 publish_tf:=false）
ros2 launch r2_bringup chassis.launch.py publish_tf:=false

# 终端 4: IMU（启动后静止 3s 等校准，校准期不可动）
ros2 launch g354_imu_driver g354_rviz.launch.py rviz:=false serial_port:=/dev/ttyACM1 mount_axes:=y_front_x_left_z_down

# 终端 5: EKF（⚠️ 必须在 IMU 校准完成后启动，否则输出 NaN；重启 IMU 必须同时重启 EKF）
ros2 launch r2_bringup ekf.launch.py

# 终端 6: 键盘遥控（08-11 P3 setup.cfg 修复后 ros2 run 可直接启动，无需 python3 直启）
ros2 run r2_bringup teleop_keyboard
```

### 1.2 生成当前 TF 树（现状盘点）

```bash
# 装工具（如缺）
sudo apt install -y ros-humble-tf2-tools

# 生成 frames 图（pdf）
ros2 run tf2_ros view_frames
ls frames_*.pdf   # 转图片查看: pdftoppm frames.pdf frames -png

# 逐条链路验证（应全部有输出）
ros2 run tf2_ros tf2_echo odom base_link        # EKF 发布 ✅（已有）
ros2 run tf2_ros tf2_echo base_link imu_link    # 静态 ✅（已有）
ros2 run tf2_ros tf2_echo base_link velodyne    # 需确认是否存在
ros2 run tf2_ros tf2_echo odom_lidar velodyne   # KISS-ICP 自带
```

### 1.3 目标 TF 树（W1 验收标准）

```
map ←[桥，W1 可为单位静态]→ odom ←[EKF]→ base_link
                                    ├──→ imu_link（静态，ekf.launch.py 已含 ✅）
                                    └──→ velodyne（静态，✅ 已定案 z=0.56）
odom_lidar（KISS 自身系）──→ velodyne（KISS 发布）
```

**✅ 定案（2026-08-06 D0 审计）**：
- `base_link → velodyne` 静态 TF 由 robot_state_publisher 发布（URDF velodyne_joint）
- 实测定案: 雷达离地 **69cm**、base_link 离地 **13cm** → base_link→velodyne = **0.56m**
- URDF 已更新（base_joint 0.13 / velodyne_joint 0.56 / 删除 base_footprint，备份 .bak_20260806）
- 验证: `tf2_echo base_footprint velodyne` 报 frame 不存在（已删干净）；frame 快照存档 minimal_loop/

### 1.4 D1 验收

- [ ] view_frames 生成完整 TF 树图并存档（doc 留档）
- [ ] 四条 tf2_echo 链路全部有输出
- [ ] base_link→velodyne 实际高度量测并写入静态 TF

---

## D1b：KISS-ICP 点云累积流程固化（零依赖脚本）

### 2.1 录制（现场数据源）

```bash
# N97，开车前开始录（绕场 1-2 圈用）
mkdir -p ~/Lin_workspace/r2_integration/bags
ros2 bag record -o ~/Lin_workspace/r2_integration/bags/map_run_$(date +%m%d_%H%M) \
  /velodyne_points /kiss/frame /kiss/odometry /odom_wheels /odometry/filtered /tf /tf_static
# Ctrl-C 停止
```

### 2.2 离线累积脚本（方案B：逐帧位姿变换累积，标准 LiDAR 建图法）

> 脚本: `~/Lin_workspace/bags/analysis/build_map.py`（官方 rosbag2_py，零依赖）
> 原理: 每帧 `/kiss/frame`（velodyne 系全分辨率）× `/kiss/odometry` 位姿（时间对齐）
>       → 变换到 odom_lidar 世界系 → 逐帧累积
> 注意: 不用 `/kiss/local_map`（KISS 局部滑动窗口 + voxel 0.2m 过稀）

```bash
python3 ~/Lin_workspace/bags/analysis/build_map.py <bag_dir> <输出.ply> [抽稀间隔=5]
```
### 2.3 高度滤波 + 2D 占用网格（D2 也用到，一起固化）

```bash
# 脚本位置: ~/Lin_workspace/bags/analysis/pcd_to_map.py
```

```python
#!/usr/bin/env python3
"""PCD/PLY → 2D 占用网格（PGM+YAML，Nav2 map_server 格式）
流程: 读点云 → z 高度滤波(0.1<z<1.5) → xy 栅格化 → 占用阈值 → 输出 map.pgm/map.yaml
"""
import sys, struct
import numpy as np

def read_ply_bin(path):
    with open(path, 'rb') as f:
        header = b''
        while True:
            line = f.readline()
            header += line
            if line.startswith(b'end_header'):
                break
        n = int([l for l in header.decode().splitlines() if l.startswith('element vertex')][0].split()[-1])
        data = f.read(n * 12)
    return np.frombuffer(data, dtype='<f4').reshape(n, 3)

def to_map(xyz, res=0.05, z_min=0.1, z_max=1.5, occ_thresh=3):
    mask = (xyz[:, 2] > z_min) & (xyz[:, 2] < z_max)
    pts = xyz[mask][:, :2]
    if len(pts) == 0:
        raise SystemExit('滤波后无点')
    x_min, y_min = pts.min(axis=0) - 1.0
    x_max, y_max = pts.max(axis=0) + 1.0
    w = int((x_max - x_min) / res); h = int((y_max - y_min) / res)
    grid = np.zeros((h, w), dtype=np.int32)
    ix = ((pts[:, 0] - x_min) / res).astype(int)
    iy = ((pts[:, 1] - y_min) / res).astype(int)
    np.add.at(grid, (iy, ix), 1)
    occ = np.where(grid >= occ_thresh, 100, 0).astype(np.uint8)
    return occ, x_min, y_min, res

def save_pgm(path, occ):
    with open(path, 'wb') as f:
        f.write(b'P5\n%d %d\n255\n' % (occ.shape[1], occ.shape[0]))
        f.write(occ.tobytes())

if __name__ == '__main__':
    ply = sys.argv[1]
    occ, ox, oy, res = to_map(read_ply_bin(ply))
    save_pgm(sys.argv[2] if len(sys.argv) > 2 else 'map.pgm', occ)
    yaml = f"""image: {sys.argv[2] if len(sys.argv) > 2 else 'map.pgm'}
resolution: {res}
origin: [{ox}, {oy}, 0.0]
negate: 0
occupied_thresh: 0.65
free_thresh: 0.25
"""
    open('map.yaml', 'w').write(yaml)
    print(f'地图 {occ.shape[1]}x{occ.shape[0]} 格，原点 ({ox:.2f},{oy:.2f})，分辨率 {res}')
```

---

## D2：地图生成验证（离线）

> **执行记录（08-09）**：链路首次跑通（bag → 累积点云 → 占用网格），但产出**严重重影**不可用。
> **执行记录（08-11）**：重影根因实锤并修复——N97 CPU `powersave` 治理器低频导致 KISS 隔帧处理
> （3.6Hz，应 10Hz）；切 `performance` 后 KISS 恢复 9.5Hz，重录 bag（map_run_0811_1925，1634 帧）
> 重跑建图，地图结构清晰、重影消除。对比图 `bags/maps/compare_0809_vs_0811_final.png`。
> 详见 [retrospect/2026-08-11_kiss_frame_rate_fix.md](../retrospect/2026-08-11_kiss_frame_rate_fix.md)。
> **D2 状态：✅ 已通过（08-11）**，遗留 D4 地图复用验证 + performance 持久化。

```bash
# 1. bag → 累积点云
python3 ~/Lin_workspace/bags/analysis/build_map.py ~/bags/xxx.map_run_*.bag ~/bags/map_raw.ply

# 2. 滤波 + 投影 → 占用网格
python3 ~/Lin_workspace/bags/analysis/pcd_to_map.py ~/bags/map_raw.ply ~/bags/map.pgm

# 3. 可视化验证（rviz 加载 /map）
ros2 run nav2_map_server map_server map.yaml   # 需要先跑 lifecycle 或
# 简单验证: 直接看图（图片查看器打开 map.pgm）
```

---

## D3：场地实测建图

```bash
# 1. 全栈启动（1.1 步骤，含 CAN/键盘）
# 2. 静态 5s 让 KISS-ICP 初始化（车不动；IMU 校准纪律同样适用）
# 3. 开始录 bag（⚠️ 必须先确认 KISS 以 visualize:=true 启动，否则 /kiss/frame 无数据）
ros2 bag record -o ~/Lin_workspace/r2_integration/bags/map_run_$(date +%m%d_%H%M) \
  /velodyne_points /kiss/frame /kiss/odometry /odom_wheels /odometry/filtered /tf /tf_static
# 4. 键盘遥控绕场 1-2 圈（缓慢、匀速、覆盖全视野），回到起点
# 5. Ctrl-C 停止 → 离线生成地图（D2 脚本）

> 注意: 历史 bag（08-06 after 系列）未录 /kiss/frame——本步首次录制该话题，累积脚本依赖此数据。
```

**场地要求**：5-10m 室内开阔区，墙面/立柱/箱子等可识别特征；绕行时避免遮挡雷达正上方。

---

## D4：地图复用验证

```bash
# 1. 重启全栈（验证地图独立性）
# 2. 加载地图
ros2 run nav2_map_server map_server --ros-args -p yaml_filename:=~/bags/map.yaml
# 或后续 Nav2 bringup 直接引用 map.yaml

# 3. rviz 添加 /map 话题 → 应显示占用网格且与场地一致
# 4. 对比 PCD 与 PGM 轮廓
```

---

## D5：W1 验收清单

- [x] TF 树图存档（view_frames pdf/png → doc 留档）
- [x] base_link→velodyne 实际高度已量测并写入静态 TF（解决 65/77cm 冲突）
- [x] 一张可复用场地地图（**map_run_0811_1925.pgm + map.yaml + 源 PCD**，08-11 重影消除后 ✅）
- [ ] 地图重启后加载正确（rviz 回显）← D4 未做
- [x] 全程 bag 已录制归档（N97 bags/ 目录）
- [x] 流程文档化（本手册 + 脚本入 bags/analysis/）

---

## 相关

- 计划: [plan-minimal-loop.md](plan-minimal-loop.md)
- 传感器安装定义: [phase0/sensor-mount.md](phase0/sensor-mount.md)（velodyne 高度待确认项）
- 雷达网络: retrospect/vlp16_slam_exploration.md
