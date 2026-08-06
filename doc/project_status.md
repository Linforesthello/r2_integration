# R2 全项目现状总结

> 生成日期: 2026-08-06
> 基线: r2_integration `main` = 162a3ef；Obsidian 库 `main` = fb376d0
> 内容: 全项目现状快照（进度/架构/子系统/环境/待办/下一步）

---

## 一、项目概况

R2 全向轮底盘从"串口键盘遥控"升级为"ROS2 自主导航 + 感知 + AI"的完整机器人系统。
五阶段路线图（见 [01-plan.md](01-plan.md)）。

| Phase | 内容 | 进度 | 状态 |
|:------|:-----|:----:|:----:|
| 0 | 底盘 CAN 控制 | 100% | ✅ |
| 1 | IMU + EKF 融合 | 85% | ✅ 实车验证完成（08-06） |
| 2 | VLP16 + KISS-ICP SLAM | 100% | ✅ |
| 3 | Nav2 导航 | 0% | ⏳ 建图方案缺口待定 |
| 4 | D435 + Jetson 视觉 AI | 0% | ⏳ |
| 5 | 系统集成与硬化 | 0% | ⏳ |
| | **总计** | **57%** | |

---

## 二、系统架构现状

```
VLP-16 雷达 ──10.18.18.6──→ N97 (机器人电脑) ──WiFi 192.168.1.210──→ VM (开发机)
                                    │                                  │
                              CAN 1M (can0)                        FastDDS 7410+Peer
                                    │                                  │
                              G354 IMU ←── MCLM 电机 ×4 ── 四全向轮底盘
```

| 层 | 组件 | 状态 |
|:---|:-----|:-----|
| 感知 | VLP-16（10.18.18.6，PoE）、G354 IMU（USB 串口 /dev/ttyACM1） | ✅ |
| 定位 | KISS-ICP（/velodyne_points → odom_lidar） | ✅ |
| 融合 | robot_localization EKF（/odometry/filtered，50Hz） | ✅ |
| 执行 | r2_chassis_node（/cmd_vel → CAN → MCLM ×4） | ✅ |
| 远程 | TigerVNC（:2/5902）+ 跨机 DDS（低带宽） | ✅ 见五 |

---

## 三、关键子系统现状

### 3.1 底盘（Phase 0）

- 四全向轮（45° 布局），CAN 1M，MCLM 电机（ID 0x123/124/125/126）
- 运动学：正解/逆解已验证；90° 坐标变换实测校准
- **08-06 修复**：omega 单位多除轮半径（放大 13.2×）+ 非全向积分模型
  - 实车验证（bag 对比）：yaw 偏差 179°→4-14°，方形闭环 1.8m→0.27m（KISS 交叉验证一致）
  - 详见 [chassis_ekf_debug](retrospect/2026-08-05_chassis_ekf_debug.md)
- 安全机制：0.5s 无指令自动停、限幅、堵转检测

### 3.2 IMU / EKF（Phase 1，85%）

- G354：Mahony + ZUPT 在线零偏跟踪，安装轴映射 `y_front_x_left_z_down`
- **08-05 修复**：imu_node 协方差对角化（原 `[base]*9` 填满非对角项 → 矩阵奇异 → EKF NaN）
- **08-05 修复**：EKF `process_noise_covariance` 必须用**完整 225 值矩阵**
  （robot_localization 3.5.4 的 15 值对角格式加载 bug → 启动即 NaN），z/vz=1e-6 防漂
- 验证：EKF z 漂移 85m → 亚米级；**遗留：slip 场景剧烈加减速 z 漂 +2.5m**
- 详见 [imu_covariance_ekf_nan](retrospect/2026-08-05_imu_covariance_ekf_nan.md)

### 3.3 雷达 / SLAM（Phase 2）

- VLP-16 驱动 ✅，KISS-ICP 建图/里程计 ✅
- slam_toolbox 已否决（不适合 VLP-16，见 [vlp16_slam_exploration](retrospect/vlp16_slam_exploration.md)）
- **缺口**：Phase 3 建图方案未落地（候选：KISS-ICP PCD 累积 → 2D 投影）

---

## 四、部署环境与网络拓扑

| 机器 | 角色 | 网络 | 说明 |
|:-----|:-----|:-----|:-----|
| N97 | 实车工控机（Ubuntu 22.04 + Humble） | WiFi 192.168.1.210；有线 enp1s0 10.18.18.20 | 采集/控制/本地 rviz2 |
| VM (lin-virtual-machine) | 开发机（VMware NAT） | ens33 192.168.1.204；ens37 10.18.18.30 | 代码/文档/bag 分析 |
| Windows | VMware 宿主 | — | VNC 客户端等 |

- **跨机 DDS**：FastDDS 固定端口 7410（N97 需带 `FASTRTPS_DEFAULT_PROFILES_FILE=~/fastdds_wellknown.xml` 启动）
  + VM 单播 Peer（`~/Lin_workspace/fastdds_peer_n97.xml`）
- **适用边界（08-06 实测）**：低带宽调试 ✅（命令行/echo/bag 控制）；
  **rviz2 实时可视化 ❌**（WiFi 带宽瓶颈 → 掉帧 + 反向拖慢 N97 EKF）——**rviz2 留在 N97 本地**
- VMware NAT 不通组播 → 必须单播 Peer

---

## 五、远程访问

| 方案 | 状态 | 说明 |
|:-----|:-----|:-----|
| TigerVNC | ✅ 使用中 | :2/5902，xfce4 虚拟会话；**未配开机自启**（重启需手动 `tigervncserver :2 ...`） |
| NoMachine / RealVNC | ❌ 弃用 | 商业授权墙（详见 [n97_remote_desktop](retrospect/2026-08-05_n97_remote_desktop.md)） |
| 操作手册 | ✅ | `STM32_Now/doc/02-deploy/n97_remote_desktop.md` |

---

## 六、数据与文档管理

| 项 | 位置 | 说明 |
|:---|:-----|:-----|
| bag 仓库 | `~/Lin_workspace/bags/`（VM） | raw（07-30 修复前 / 08-06 修复后 / IMU 测试）+ csv 全帧导出 + analysis 脚本（官方 rosbag2_py） |
| 原始 bag | N97 `r2_integration/bags/` | 采集机保留 |
| 文档权威源 | `~/Lin_workspace/r2_integration/doc/` | 规范见 standards.md |
| Obsidian 镜像 | `~/Lin_note/.../R2_Integration/doc/` | 单向 cp + git 提交 |

---

## 七、待办与遗留问题

| # | 事项 | 类型 | 优先级 |
|:--|:-----|:-----|:------|
| 1 | VNC 开机自启（N97 重启后远程桌面不丢） | 收尾 | 高（机器人电脑标配） |
| 2 | z 漂移 slip 场景 +2.5m（剧烈加减速数值积累） | Phase 1 收尾 | 中 |
| 3 | Phase 3 建图方案落地（KISS-ICP PCD → 2D 地图） | 主线 | 高 |
| 4 | Nav2 启动 + 参数调优（3.4/3.5） | 主线 | 高 |
| 5 | N97 上 NoMachine（/usr/NX，端口 4000）清理 | 清理 | 低 |
| 6 | `:1` VNC 历史占用来源未查明 | 排查 | 低 |

---

## 八、下一步计划

```
短期（半小时）：VNC 开机自启
主线：          建图方案（KISS-ICP PCD 累积 → 2D 占用网格）→ Nav2 启动 → 调优
并行：          z 漂移 slip 场景跟进
之后：          Phase 4 视觉 AI（D435 + Jetson）→ Phase 5 系统集成
```

---

## 九、相关文档索引

- 计划总纲：[01-plan.md](01-plan.md) ｜ 进度看板：[02-progress.md](02-progress.md)
- 当前状态：[03-current_state.md](03-current_state.md) ｜ 交接：[07-handover.md](07-handover.md)
- 底盘定义：[phase0/chassis_definition.md](phase0/chassis_definition.md)
- 排障记录：[retrospect/](retrospect/)（08-05 底盘/EKF、08-05 IMU 协方差、08-06 Git 教训等）
- 文档规范：[standards.md](standards.md)
