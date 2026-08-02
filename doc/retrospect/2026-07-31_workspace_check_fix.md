# r2_integration 工作区全面检查与修复记录

> 日期: 2026-07-31
> 关联: `retrospect/2026-07-31_chassis_launch_fix.md`（chassis 路径修复，同日上午）
> 机器: 本地 VM + N97（192.168.1.210）

---

## 一、背景

chassis.launch.py 修复完成后，对 `~/Lin_workspace/r2_integration` 做了全面检查：
代码正确性（launch 文件、启动脚本）+ 文档一致性（README、doc 结构），
并更新工作区至与实际状态一致。

---

## 二、发现的问题与修复

### 1. g354_rviz.launch.py（3 个问题）

| 问题 | 说明 | 修复 |
|:--|:--|:--|
| `Node(executable=)` 布局脆弱 | 与 chassis 同款潜伏坑：入口脚本在 `bin/` 时找不到 | 双查找 `_find_node_executable()`（`lib/<pkg>/` + `bin/`） |
| 强制启动 RViz2 | SSH 无显示器环境直接失败 | 新增 `rviz:=false` 开关（`IfCondition`） |
| 串口路径不可配 | G354 设备路径硬编码 | 新增 `serial_port` 参数（默认 `/dev/ttyACM1`） |

用法:
```bash
ros2 launch g354_imu_driver g354_rviz.launch.py                  # 节点 + RViz2
ros2 launch g354_imu_driver g354_rviz.launch.py rviz:=false       # 仅节点（SSH）
ros2 launch g354_imu_driver g354_rviz.launch.py serial_port:=/dev/ttyACM0 rviz:=false
```

### 2. 布局差异新发现（重要）

同一 colcon、同一次构建，两个包入口脚本位置不同:

```
install/g354_imu_driver/lib/g354_imu_driver/imu_node   ← 标准布局
install/r2_bringup/bin/chassis_node                    ← bin/ 布局
```

原因：r2_bringup 包目录内留有历史 `build/ install/ log/`（曾在包内直接 colcon build），
构建缓存导致 scripts 安装位置不同。**这验证了双查找设计的必要性** —— 不能假设
某个包一定是哪种布局，`ros2 run` 在此环境一律不可靠。

### 3. scripts/r2_startup.sh

- 用法注释路径拼写错误（`r2_brigup_start.sh` → `r2_startup.sh`）
- 底盘/EKF 用源码文件路径方式启动 → 改包名方式（不依赖源码树位置）
- IMU 用 `ros2 run g354_imu_driver imu_node`（布局脆弱）→ `ros2 launch ... rviz:=false`
- 各子终端补充显式 `source install/setup.bash`

### 4. README.md（工作区入口导航）

- 文件树补全：`doc/retrospect/`、`doc/phase1/g354-wiring.md`、`g354_driver/launch/`、`scripts/r2_startup.sh`
- "当前阶段"按 03-current_state 更新（Phase 2 VLP16+KISS-ICP 已 ✅，非 FAST-LIO2）
- 部署环境改为"已部署 N97"；LiDAR 改为 VLP-16（设备 IP 10.10.3.6）
- 快速启动：IMU 命令修正包名（`g354_driver` → `g354_imu_driver`）并改 launch 方式；
  注明本机 `ros2 run` 不可用，一律用 `ros2 launch`
- 新增一键启动脚本说明

### 5. g354_driver/README.md

- 路径仍指向旧工作区 `~/Lin_workspace/g354_test/` → 更新为 `r2_integration`
- `ros2 run` → launch 方式 + rviz 开关 + serial_port 参数说明

### 6. N97 ~/.bashrc 自动 source（chassis 复盘根因 3 的收尾）

```bash
# === ROS2 Humble + R2 工作区（2026-07-31 添加）===
[ -f /opt/ros/humble/setup.bash ] && source /opt/ros/humble/setup.bash
[ -f ~/Lin_workspace/r2_integration/install/setup.bash ] && source ~/Lin_workspace/r2_integration/install/setup.bash
```

- 交互登录 shell 即用，已实测 `ros2 pkg prefix g354_imu_driver` 直接命中
- 注意：非交互 shell（脚本、单条 ssh 命令）不加载 `.bashrc` 末尾代码，脚本内仍须显式 source

---

## 三、验证

N97 实测 `ros2 launch g354_imu_driver g354_rviz.launch.py rviz:=false`（6s 超时）：

```text
Serial /dev/ttyACM1 (460800 baud)
Burst registers verified (CTRL1=0xF007, CTRL2=0x7000)
G354 38-byte burst mode configured and verified
Calib 50/250 ... 200/250
Gyro bias (dps): X=0.0009 Y=0.0500 Z=0.0082   ← 零偏很小，IMU 硬件正常
```

IMU 连接、burst 模式、零偏校准全通；`rviz:=false` 生效（无 DISPLAY 不报错）。

---

## 四、同步状态

| 位置 | 内容 | 状态 |
|:--|:--|:--|
| N97（192.168.1.210） | g354_rviz.launch.py、r2_startup.sh、README.md、g354 README、chassis.launch.py | ✅ 已同步 + 重建 |
| Obsidian vault | R2_Integration/README.md、retrospect 镜像 | ✅ 已同步 |
| git（origin: Linforesthello/ros-） | 全部改动 | ⏳ 未提交 |

---

## 五、教训

1. **文档会过时，且过时方向多样**：路径（g354_test→r2_integration）、阶段状态（FAST-LIO2→KISS-ICP）、包名（g354_driver→g354_imu_driver）、启动方式 —— 全面检查时逐项对照代码实际
2. **同一环境下包布局可能不一致**（包内历史构建缓存）→ launch 文件双查找兜底，`ros2 run` 不可依赖
3. **新环境的"能用"可能只是旧构建巧合**：g354 当前 `ros2 run` 能跑，但重建后布局可能变 `bin/` 而突然挂掉 —— 预先修复胜过事后排查
