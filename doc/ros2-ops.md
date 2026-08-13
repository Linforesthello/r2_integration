# ROS/ROS2 操作规范（R2 项目）

> 范围：ROS/ROS2 特有操作纪律（构建/启动/录包/分析/部署/配置/排障）。
> 通用规范不在此重复，一律引用：[文档标准](standards.md)（git 提交 1.10 / 文档 1.1-1.8 / Obsidian 1.9）、[Obsidian 标签](obsidian-tags.md)、全局工作偏好 `~/.claude/CLAUDE.md`。
> 维护：每条规则来自实车/实机教训（标注出处），随项目演进补充。

---

## 1. 多机环境：先确认对象机器

| 机器 | 角色 | 说明 |
|:-----|:-----|:-----|
| VM (lin-virtual-machine) | 开发机 | 代码/文档/bag 分析；AI 工具（Bash/Edit）运行在此 |
| N97 (192.168.1.210) | 实车工控机 | 采集/控制/本地 rviz2；ROS 运行、apt 安装在此 |

- **源码工作区 VM 与 N97 各一份独立副本**：改代码在 VM，同步走 `git push` → N97 `git pull`，不 scp 拷贝
- **不要用 VM 的 install/build 状态解释 N97 行为**（2026-08-11 教训：在 VM 诊断 N97 构建产物全对不上，白排查一圈）
- 用户贴出的运行/实车反馈来自 N97——排障前先问清"当前对象是哪台机器"

## 2. 构建与部署（改了要真的生效）

- **launch 加载 install 副本，不是源码**：改配置（yaml）后必须 `colcon build` 或手动 cp 同步 install 路径，
  否则测到的是旧配置（2026-08-09 ekf.yaml 教训）
- **验证新构建**：console_scripts 入口（`install/.../lib/<pkg>/<script>`）是 import 壳不含源码；
  应 grep `install/<pkg>/lib/python3*/site-packages/<pkg>/` 里的源码确认更新
- 改代码后验证前，先确认目标进程加载的是新构建：build + 重启进程，否则测到的是旧代码

## 3. 启动流程纪律（N97，顺序固定）

1. **CPU performance 治理器**（每次开机必做；powersave 恢复后 KISS 掉到 3.6Hz → 建图重影，见 [retrospect 08-11](retrospect/2026-08-11_kiss_frame_rate_fix.md)）
2. CAN 总线 → 雷达 → KISS-ICP（`visualize:=true`）→ 底盘（EKF 场景 `publish_tf:=false`）→ IMU → EKF → 键盘遥控
3. **IMU 启动后静止 3s 等校准，校准期不可动；EKF 必须在 IMU 校准完成后启动**
4. **重启 IMU 必须同时重启 EKF**（否则输出 NaN）
5. KISS-ICP 必须 `visualize:=true` 才发布点云话题（/kiss/frame 累积脚本依赖）
6. 完整命令与验证见 [w1-operation.md](minimal-loop/w1-operation.md) §1.1

## 4. bag 录制

- 路径：N97 `~/Lin_workspace/r2_integration/bags/`，开车前开始录
- 话题清单（建图/导航通用）：`/velodyne_points /kiss/frame /kiss/odometry /odom_wheels /odometry/filtered /tf /tf_static`
- 历史坑：08-06 after 系列 bag 未录 `/kiss/frame`，累积脚本无法回放

## 5. bag 分析（采样精度先行）

- **分析前先确认采样方式：精采样（时间等间隔/全序列）还是粗略（索引降采样）**；涉及运动/瞬态特征必须精采样，或先问用户
- 时间序列一律按时间戳等间隔切片/插值，**禁用均匀索引采样**（`arr[len//4]`、`arr[::N]` 会漏掉运动段，
  2026-08-12 误判教训：90°/190° 转弯全落在采样点之间，误判轮速 yaw 失真 5.6×）
- 分析工具用官方 `rosbag2_py`（零安装），不先用第三方库（2026-08-06 教训）
- **结论与用户亲历事实冲突时**（用户说车动了但数据说没动），优先怀疑自己的采样/解析，不要先怀疑硬件

## 6. 配置修改（EKF 等 yaml）

- 改 `ekf.yaml` → 同步 install 副本（§2）→ 重启 EKF；只加一个变量，记录改动前后数据
- 回滚：撤销该处改动 + 同步 install + 重启，或 `git revert`

## 7. 排障纪律

- **每次只加一个变量**；记录期望/实际数据，出问题回溯数据而非盯现象
- 疑难问题先搜索核实（WebSearch/官方文档/社区），不凭猜测下结论
- 大转弯/加速等动作段分析时，先看用户描述的实车动作再对数据（防采样盲区）

## 8. 实机安全

- 首次实机测试用降额参数（速度 20%/力矩 30%），上电前检查清单，失控先拍急停，不赌运气

---

## 相关

- 文档/git/Obsidian 规范：[standards.md](standards.md) ｜ [obsidian-tags.md](obsidian-tags.md)
- 启动手册：[w1-operation.md](minimal-loop/w1-operation.md)
- 排障记录：[retrospect/](retrospect/)
