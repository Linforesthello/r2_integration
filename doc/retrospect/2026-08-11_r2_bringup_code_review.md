# R2 上层代码审查与修改方案（r2_bringup 全包）

> 日期: 2026-08-11
> 范围: `r2_bringup/` 全部代码（chassis_node.py、teleop_keyboard.py、launch ×2、config ×2、setup.py、package.xml）
> 状态: ✅ P1~P10 全部实施并验证（mock + 实车）；P4 实车拔线验证待做
> 关联: [2026-07-31_teleop_keyboard_fix.md](2026-07-31_teleop_keyboard_fix.md)（同包历史排障）
> 事实来源: 仅依据包内源码本身（本机 `~/Lin_workspace/r2_integration/r2_bringup/`），行号以 2026-08-11 当日为准

---

## 一、结论摘要

| 级别 | 数量 | 条目 |
|:--|:--:|:--|
| 🔴 确定 bug（会崩/行为错） | 3 | P1 test_main KeyError；P2 超时后 50Hz 停发垃圾帧；P3 setup.cfg 缺失 |
| 🟡 设计缺陷/边界 | 3 | P4 缺轮 odom/TF 冻结；P5 teleop EOF 空转；P6 dt 钳位丢时间 |
| 🟢 轻微 | 4 | P7 注释与实现不符；P8 启动 MOTOR_LOST 误报；P9 destroy_node 边缘路径；P10 python-can rosdep 键待验证 |

另：运动学逆解/正解互为反演、四轮 ID 映射、90° 坐标变换自洽、ekf.yaml 225 值矩阵、话题/帧名三方一致——均已逐一核对，**无需修改**（见第四节）。

---

## 二、问题与修改方案（含预期）

### P1 🔴 `--test` 模式必崩：`KeyError: 'flags'`

- **现象**：[chassis_node.py:606](../r2_bringup/r2_bringup/chassis_node.py#L606) 打印 `s["flags"]`，但 [decode_status_frame 返回值](../r2_bringup/r2_bringup/chassis_node.py#L140-L147) 没有 `'flags'` 键（只有 `stall`/`saturated` 两个解析后布尔）
- **影响**：`chassis_node --test` 读到第一帧状态帧即 KeyError 崩溃，CAN 测试模式不可用
- **修改方案**：方案 A（推荐）——在返回值中补 `'flags': flags` 原始字节，`--test` 打印它；方案 B——把 `--test` 打印改为 `'stall'`/`'saturated'` 两个布尔。A 保留了原始信息
- **预期**：`python3 r2_bringup/chassis_node.py --test can0` 完整跑完 4 电机「正转→停→反转→停」循环不崩，每轮打印 `flags=0x..`

### P2 🔴 cmd 超时后以 50Hz 无限重发停止帧

- **现象**：[chassis_node.py:412-416](../r2_bringup/r2_bringup/chassis_node.py#L412-L416) 超时分支每周期（50Hz）都调 `_send_speeds([0,0,0,0])`，`_last_cmd_time` 不复位 → 4 电机 × 50Hz = **200 帧/s 永不停歇**（CAN 1Mbps 下约 2.6% 总线占用，且无意义）
- **修改方案**：超时后只发一次停止帧，并用标志位（如 `self._stop_sent = True`）阻止重复；收到新 cmd_vel 时复位标志
- **预期**：`candump can0` 统计：超时后仅出现 4 帧停止帧，后续无新帧；新 cmd_vel 到达后恢复正常发送

### P3 🔴 缺少 `setup.cfg` → 入口脚本装错位置

- **现象**：包根目录无 setup.cfg（标准 ament_python 必须有 `[develop] script_dir=$base/lib/<pkg>` + `[install] install_scripts=$base/lib/<pkg>`）；console_scripts 落进 `bin/` 而非 `lib/r2_bringup/`，导致 `ros2 run r2_bringup chassis_node` 失败（ros2 run 只在 `lib/<pkg>/` 找）
- **佐证**：[chassis.launch.py:15-23](../r2_bringup/launch/chassis.launch.py#L15-L23) 的 `_find_node_executable` 双路径兜底正是为此打的补丁（注释自述"本机 colcon 行为装在 bin/"）；[2026-07-31 排障记录](2026-07-31_teleop_keyboard_fix.md) 也记载了"ros2 run 会报 libexec 错，绕开 python3 源码路径启动"
- **修改方案**：新增 `setup.cfg`（标准两段式）；`_find_node_executable` 的 bin 兜底分支保留或移除（若 build 后确认 lib/ 布局生效，可删除兜底，恢复正常 launch 写法）
- **预期**：`colcon build` 后 `install/r2_bringup/lib/r2_bringup/` 出现 `chassis_node`、`chassis_test`、`teleop_keyboard` 三个入口；`ros2 run r2_bringup chassis_node --help` 可启动（注：`--help` 会正常进入 spin，需 Ctrl-C 退出）；`ros2 pkg executables r2_bringup` 列出 3 个

### P4 🟡 单电机状态帧丢失 → odom 与 TF 整体冻结

- **现象**：[chassis_node.py:370-371](../r2_bringup/r2_bringup/chassis_node.py#L370-L371) `len(statuses) < 4` 直接 `return None`，[420-421](../r2_bringup/r2_bringup/chassis_node.py#L420-L421) 随之停止发布 → 一轮 CAN 掉线，独立场景 TF 僵死、EKF 场景位置只剩 IMU 航向
- **修改方案**：缺轮时降级——缺哪轮就把哪轮速度按 0 参与正解（或直接丢弃正解输出、odom 置零速发布），同时 `MOTOR_LOST` 日志保持；保证 odom/TF 持续 50Hz
- **预期**：拔掉一轮 CAN（或屏蔽其状态 ID）后 `ros2 topic hz /odom_wheels` 仍稳定 50Hz；日志持续报 MOTOR_LOST；接回后自动恢复

### P5 🟡 teleop 终端 EOF 时 CPU 空转

- **现象**：[teleop_keyboard.py:167-168](../r2_bringup/r2_bringup/teleop_keyboard.py#L167-L168) `sys.stdin.read(1)` 在 EOF 时立即返回 `''`，`if key:` 跳过但循环不退出 → SSH 断开/终端关闭后单核 100% 空转
- **修改方案**：`if not key: break`（EOF 即退出），退出路径仍走 finally 恢复终端
- **预期**：SSH 断开后进程自动退出，`top` 观察无空转进程残留

### P6 🟡 里程计 dt 钳位丢弃真实时间

- **现象**：[chassis_node.py:432](../r2_bringup/r2_bringup/chassis_node.py#L432) `min(dt, 0.1)`：定时器被阻塞（日志风暴等）时真实间隔被截断 → 里程计**系统性低估路程**
- **修改方案**：去掉 0.1s 上限（仅保留 ≥1ms 下限防除零），或改用单调时钟差值而非钳位
- **预期**：人为阻塞节点 0.3s 后，里程计路程与 `dt` 实测值吻合（对照 candump/秒表），不再低估

### P7 🟢 注释与实现不符（teleop 超时兜底描述）

- **现象**：[teleop_keyboard.py:90](../r2_bringup/r2_bringup/teleop_keyboard.py#L90) 注释称"松开后由 chassis_node 的 0.5s cmd 超时兜底停车"，实际 10Hz 零命令持续发布使超时**永不触发**（停车靠的是显式零命令本身）
- **修改方案**：改注释为实际行为（零命令持续发布 = 主动停车；0.5s 超时仅在 teleop 整体死亡时兜底）
- **预期**：注释与实现一致，无行为改动

### P8 🟢 启动必刷 MOTOR_LOST 误报

- **现象**：[chassis_node.py:213-215](../r2_bringup/r2_bringup/chassis_node.py#L213-L215) `_last_status_time` 初值 0 → 每次启动头 1 秒必刷 4 条 MOTOR_LOST warn
- **修改方案**：初值改为 `None`，`_check_motor_health` 对 `None` 跳过（直到收过首帧才开始超时计时）
- **预期**：正常启动（CAN 连接完好）无 MOTOR_LOST 日志；真正断线后才报

### P9 🟢 `_init_can` 失败后 `destroy_node` 二次异常（边缘）

- **现象**：[chassis_node.py:536-542](../r2_bringup/r2_bringup/chassis_node.py#L536-L542) `_init_can` 抛异常时 `_rx_thread` 属性不存在；当前主流程（构造即抛、不进 destroy）碰不到，但任何走 destroy 的路径都会 AttributeError
- **修改方案**：`destroy_node` 全量 `getattr` 保护——**首行 `self._rx_running = False`（537）也须保护**（`_init_can` 失败时该属性同样不存在），`_rx_thread`、`_can_bus` 同理
- **预期**：CAN 初始化失败场景下进程干净退出（traceback 只有原始错误，无二次异常）

### P10 🟢 `<depend>python-can</depend>` rosdep 键修正（2026-08-11 实机验证）

- **现象**：[package.xml:16](../r2_bringup/package.xml#L16) 依赖键 `python-can`；实测 `rosdep resolve python-can` 在 ubuntu jammy **不可解析**（rosdep 数据仅覆盖到 bionic）；`python3-can` 可解析（`#apt python3-can`）
- **修改方案**：`<depend>python-can</depend>` → `<depend>python3-can</depend>`（已改）
- **验证**：`rosdep install --from-paths r2_bringup -i -s` dry-run 通过（仅剩 `ament_python` 报错 = ROS 自带 buildtool，rosdep 数据不含该键属正常，不影响真机）

---

## 三、实施顺序与验收

| 步骤 | 内容 | 验收（量化） | 实施结果（2026-08-11） |
|:--:|:--|:--|:--|
| 1 | P1 补 `flags` 键 | `--test` 跑完 4 电机循环不崩 | ✅ 假帧单测通过，打印路径无 KeyError |
| 2 | P2 超时停发只发一次 | candump 统计超时后 ≤4 帧 | ✅ mock + 实车：杀 teleop 后 0.5s 仅一组 4 帧停止帧（123/126/124/125 各 1），之后总线静默（旧代码会 50Hz 无限刷） |
| 3 | P3 新增 setup.cfg | `ros2 run r2_bringup chassis_node` 可启动 | ✅ colcon build 后 3 入口落位 `lib/r2_bringup/`，`bin/` 消失；launch 标准写法解析正常 |
| 4 | P4 缺轮降级 | 拔 1 轮后 odom 仍 50Hz | ✅ mock 三场景通过（4 轮正常/缺 1 轮降级/全无冻结） |
| 5 | P5 EOF break | 断开 stdin 进程退出 | ✅ mock 通过（EOF 只读 1 次即退出） |
| 6 | P6 去 dt 上限 | 阻塞 0.3s 后里程计不低估 | ✅ mock 通过（0.15s 阻塞 dt 保留，路程不低估） |
| 7 | P7~P9 小改 | 各自预期项（见上表） | ✅ P7 注释按实测修正（raw 模式检测不到松开，停车靠显式按键）；P8 mock + 实车（今天启动日志 0 条 MOTOR_LOST，旧代码刷 4 条）；P9 空壳节点 3 属性安全降级 |
| 8 | P10 rosdep 验证 | `rosdep install` 通过 | ✅ `python-can` jammy 不可解析 → 改 `python3-can`，dry-run 通过 |

实施方式：按项目惯例，**改代码前询问用户**——由 AI 直接改，还是给指令用户亲手改（学习性操作优先用户动手）。
全部改完在 N97 实车冒烟（速度 20% 降额）后，按 git 规范提交（body 关联本文档）。

---

## 四、核对无误、不修改的部分

| 项 | 核对结果 |
|:--|:--|
| 逆解/正解公式 | 互为反演（代入验证一致）；车轮序 FL/FR/RL/RR 与 `R2_MOTOR_IDS=[0x123,0x126,0x124,0x125]`、`R2_STATUS_IDS=[0x323,0x326,0x324,0x325]`、正解索引全部一致 |
| 90° 坐标变换 | cmd（`kin_vx=-user_vy, kin_vy=user_vx`）与 odom（`user_vx=kin_vy, user_vy=-kin_vx`）互为逆变换，ω 无变换，符号自洽 |
| ekf.yaml 过程噪声 | 225 值矩阵 = 15×15 对角，对角值 15 个逐一核对（0.01/0.01/1e-06/0.001/0.001/0.005/0.01/0.01/1e-06/0.01/0.01/0.01/0.1/0.1/1e-06） |
| odom0/imu0 config | 各 15 项，two_d_mode 与注释自洽 |
| 话题/帧名三方一致 | `/odom_wheels`（chassis）↔ ekf.yaml `odom0`；`/imu/data`（g354_imu_driver，frame_id=imu_link）↔ ekf.yaml `imu0` ↔ ekf.launch.py 静态 TF `base_link→imu_link` |
| 参数声明 | r2_params.yaml 全部 9 项均有 `declare_parameter`，无多余项 |
| 安全设计 | teleop 未定义键→停车、chassis 限幅、超时停、EKF 场景 publish_tf:=false 单发布者——保持不动 |

---

## 五、相关文件

- [chassis_node.py](../r2_bringup/r2_bringup/chassis_node.py)
- [teleop_keyboard.py](../r2_bringup/r2_bringup/teleop_keyboard.py)
- [chassis.launch.py](../r2_bringup/launch/chassis.launch.py)、[ekf.launch.py](../r2_bringup/launch/ekf.launch.py)
- [setup.py](../r2_bringup/setup.py)、[package.xml](../r2_bringup/package.xml)（新增 setup.cfg 同层）
- [ekf.yaml](../r2_bringup/config/ekf.yaml)、[r2_params.yaml](../r2_bringup/config/r2_params.yaml)
