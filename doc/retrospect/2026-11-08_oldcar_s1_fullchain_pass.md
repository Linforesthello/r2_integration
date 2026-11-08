# 老车 S1 全链实车首跑：底盘 + IMU + EKF + slam_toolbox + Nav2 目标导航 39/39 成功

> **日期**：2026-11-08（21:01:00 ~ 21:26:25，N97 本机时间）
> **任务**：老车 S1 首次带**真实里程计**的全链实跑——LD06（过滤链）→ 底盘 → IMU → EKF →
> slam_toolbox → Nav2（`nav2_explore.launch.py`，无 map_server/AMCL）→ RViz 发目标导航。
> **不含** explore_lite（用户本轮明确不需要自动探索）。
> **状态**：✅ 全链起身；✅ **39 个导航目标 39 成功、0 失败**；🟡 覆盖率/行驶质量未量化（见 §八）
> **关联**：[11-08 链路由遮挡根因](2026-11-08_oldcar_s1_chain_rerun_selfocclusion.md)（前序：静态 TF 顶替里程计 + explore 零前沿根因）｜
> [11-08 静态联调](2026-11-08_oldcar_s1_static_bringup.md)（更早一轮，其「规划全败未定因」本轮已不再复现）｜
> [sensor-mount §6.1.2](../phase0/sensor-mount.md)（自车遮挡实测）｜
> [old-car/startup.md](../old-car/startup.md)（启动权威，本轮为其首次整链验证）｜
> [s1-readiness-gap G24](../old-car/s1-readiness-gap.md)
> **证据落位**（本地，不入 git）：`doc/raw_data/raw_s1_fullchain_pass_n97_2026-11-08_2101.md`
> （由 N97 `~/.ros/log/` 只读采集的原始日志节选 + 时间线反推）。

---

## 一、结论先行

1. **老车 S1 全链首次跑通，且是真实里程计下的跑通**——此前 11-08 两轮都用
   `static_transform_publisher 0 0 0 0 0 0 odom base_link` 顶替里程计，只证明了「节点起得来」；
   本轮底盘 + IMU + EKF 全部在链，`/odometry/filtered` 真实输出，Nav2 用它做局部控制。
2. **导航目标 39 发 39 成，0 失败/中止/取消**（`bt_navigator` 日志全量统计），
   且 `current location` 在连续目标间持续变化（−1.03 → +1.17 → … → 0.14），
   证明是真移动而非静止空转。
3. **11-08 静态联调那轮的「规划全败」本轮未复现**。但本轮相对该轮**同时改了两个变量**
   （真实 EKF 里程计 上线 + 过滤 polygon 由 ±0.30 放宽到 ±0.34 并覆盖左侧漏点），
   **未做单变量拆分**——因此「规划恢复」不能唯一归因于过滤修复，见 §五。
4. **21:18 的「电机中断」是用户主动注入的测试，不是故障**（用户 11-08 说明）：目的是验证
   **电机中断后上层是否受影响**。结果 = **上层未受影响**——中断期间（21:18:06~21:21:00）
   5 个导航目标仍全部 `Reached the goal!`，车继续按 Nav2 指令行驶。这是本轮的一条**正向结论**，详见 §4.1。
5. **另有两处非阻断异常**（详见 §四）：一次 FR 堵转告警、RViz 两次崩溃（−6 / −11）。均未中断导航。

---

## 二、全链验收表

| # | 判据 | 实测 | 判 |
|:--|:---|:---|:--:|
| 1 | LD06 驱动起身 | `ldlidar communication is normal` / `Publish topic message`；`/dev/r2_ld06_a`、`scan_raw`、`base_laser` | ✅ |
| 2 | 静态 TF `base_link→base_laser` | `(0.275, 0.290, 0.040)` + `z=−0.707108 w=0.707105`（−90°） | ✅ |
| 3 | 自车过滤链加载 | `scan_to_scan_filter_chain` 无报错，仅两条已知提示（rosout 重名 / 无 HW_ID） | ✅ |
| 4 | 底盘 CAN | `CAN 接口已打开: can0` + 参数打印（R=0.330 / 4241 ticks / 限速 vx=0.5 vy=0.3 ω=0.8） | ✅ |
| 5 | IMU 校准 | `Calib 50/250 → 200/250`；`Gyro bias (dps): X=0.0716 Y=-0.0018 Z=-0.0311` | ✅ |
| 6 | EKF 起身 | `ekf_node` 正常起停；静态 TF `base_link→imu_link` 恒等 | ✅ |
| 7 | slam_toolbox 建图 | `CeresSolver` + `SCHUR_JACOBI` 初始化正常；正式运行段无 Message Filter 丢弃 | ✅ |
| 8 | Nav2 七节点 lifecycle | 七节点全部起、全部 clean 退出 | ✅ |
| 9 | **导航目标成功率** | `Begin navigating` 39 次 / `Goal succeeded` 39 次 / 失败类关键词 0 次 | ✅ |
| 10 | 真实移动 | `current location` 连续变化（跨目标重新定位），非静止 | ✅ |
| 11 | 收尾干净 | 全部节点 `finished cleanly`（除 `imu_node` exit 1 与 rviz2 崩溃） | 🟡 |
| 12 | 覆盖率 >80% / 行驶质量 | **未量化**（未存地图、未录 bag、未测 hz） | ⬜ |

---

## 三、导航结果明细

| 项 | 值 |
|:---|:---|
| 运行窗口（导航） | 21:07:28 ~ 21:21:00（约 13.5 min） |
| 目标总数 | 39 |
| 成功 | 39 |
| 失败 / 中止 / 取消 | 0 |
| 目标跨度 | x 约 −1.03 ~ +1.40 m、y 约 0.11 ~ 0.56 m（map 系，单场地小型往复） |
| 典型耗时 | 1.0 ~ 7.1 s/目标（多数 2~4 s） |
| 控制器 | `Reached the goal!` 逐目标出现，无 abort |

> 目标由 RViz 的 **Nav2 Goal** 工具发出（`nav2_explore.launch.py rviz:=true` 加载 `nav2.rviz`，
> 工具栏含 `nav2_rviz_plugins/GoalTool`）。未点 "2D Pose Estimate"——`map→odom` 由 slam_toolbox 提供。

---

## 四、异常与告警（均未阻断导航）

### 4.1 人为注入：电机中断测试（MOTOR_LOST ×848）——**上层未受影响**

> **性质**：用户主动注入的测试（2026-11-08 用户说明），**不是故障**。
> **目的**：验证电机中断后，上层（EKF / Nav2 / 规划控制）是否会受影响。

| 项 | 值 |
|:---|:---|
| 注入时刻 | 21:18:06 |
| 告警数 | 848（1 Hz 检查 × 4 电机 × 499 s；命中率约 **42%**） |
| 形态 | **间歇性**——`last=` 值先 0.7 s 后持续增长，说明是断续丢失而非一次性断链 |
| 末帧反推 | 最后一条 `last=186.1s ago`（21:26:25）→ 末帧约 21:23:19，此后彻底无状态帧 |
| **上层表现** | **21:18:06 ~ 21:21:00 期间 5 个目标仍全部 `Reached the goal!`**，车按指令继续行驶 |

**结论（正向）**：**电机中断不影响上层运行**。`_check_motor_health` 只看状态帧（CAN 反馈），
与指令下发是两条独立路径（[chassis_node.py:507-518](../../r2_bringup/r2_bringup/chassis_node.py#L507-L518)）；
反馈消失只在日志侧产生 WARN，Nav2 / EKF / 规划控制链路照常闭环。

**这条对后续排障有直接价值**：看到成片 `MOTOR_LOST` 不等于失控、不等于必须停车，
先分清「反馈链路」与「指令链路」——本轮实测已给出「反馈断了、控制仍在」的样本。

### 4.2 STALL 告警 1 次

```text
[WARN] [1794143395.336857593] [r2_chassis_node]: STALL [FR] ID=0x326 speed=0 pwm=720
```

21:09:55，前进右轮 speed=0 但 PWM 已给到 720。与后续目标成功不矛盾（下一目标照常完成）。
是否偶发打滑/顶墙未知，本轮未追。

### 4.3 RViz2 两次崩溃

| 时刻 | 退出码 | 场景 |
|:---|:---|:---|
| 21:02:45 | −6（SIGABRT） | Nav2 首次启动窗口（该轮 5 s 后即被 Ctrl-C） |
| 21:26:17 | −11（SIGSEGV） | 正式运行末（Ctrl-C 前 1.4 s，目标已全部完成） |

均未影响 Nav2 主体（rviz2 与 Nav2 节点同为 launch 子进程，崩溃不连带）。
**但意味着「RViz 看得到地图」不是稳定前提**——长时间跑或重启 Nav2 时留意 RViz 是否还活着。
根因未查（Humble rviz2 已知有退出期崩溃报告，未核实）。

### 4.4 启动失败 1 次（拼写）

```text
invalid condition expression, expected one of [true, 1, false, 0] but got 'ture'
```

`rviz:=ture`（应为 `true`）使整个 launch 在加载期异常退出，**所有 Nav2 节点一个都没起**。
21:05:33 失败 → 21:06:10 改正后成功。

### 4.5 已知配置告警（非本轮新增）

```text
[ERROR] [global_costmap]: configured inflation radius (0.300) is smaller than the computed inscribed radius (0.340) …
[ERROR] [local_costmap]:  （同上）
```

这是 08-17 为过窄缝主动把 `inflation_radius` 降到 0.30 带来的已知代价，ERROR 级别但不阻断。
**代价**：0.30 < 0.34 意味着膨胀带全在内切圈内 → **没有渐变带**，离障碍 0.34 m 内一律硬墙。
本轮目标都在开阔区，未暴露该代价；窄处导航仍可能「看得到但过不去」。

---

## 五、与「规划全败」那一轮的关系（重要，勿过度归因）

| 轮次 | 里程计 | filter polygon | 规划结果 |
|:---|:---|:---|:---|
| 11-08 17:27/17:51（静态联调） | 静态 TF `odom→base_link` 恒等 | ±0.40/±0.30（生效 ±0.43/±0.33） | **全败**（未定因） |
| 11-08 19:12（过滤验收） | 同上静态 TF | 同上 | 未发目标，仅验 explore |
| **11-08 21:01（本轮）** | **真实 EKF `/odometry/filtered`** | **±0.45/±0.34（生效 ±0.48/±0.37）** | **39/39 成功** |

**两处变量同时变化，未做单变量拆分。** 因此：

- ✅ 可以说：**老车 S1 在真实里程计 + 放宽过滤的配置下，端到端导航可用**
- ❌ 不可以说：「规划全败是自车遮挡造成的」——静态 TF 顶替里程计本身也可能是主因
  （局部 costmap 与 `/odom` 全静止，控制器拿不到有效速度反馈）

若需归因，最小实验 = **保持真实里程计、把 polygon 回退到 ±0.30**，重跑同批目标看是否复现失败。
**本轮不做**（用户目标已达成，不为归因重开实车）。

---

## 六、方法模板（可复用操作卡）

### 卡①：实车运行「黑匣子」反推法——无从现场记录时用 `~/.ros/log` 重建全部事实

适用：实跑已结束、没有现场笔记，只有系统日志。**不依赖用户回忆，不依赖 bag。**

1. `ls -d ~/.ros/log/<YYYY-MM-DD>-*` —— 目录名 = `日期-时分秒-微秒-主机名-pid`，**目录名本身就是启动时刻**
2. 逐目录 `cat launch.log` —— 拿到该轮**起了哪些节点、pid、是否 clean 退出、崩溃退出码**
3. 用节点名反推 launch 文件（如 `chassis_node-1` → `chassis.launch.py`；八进程含 rviz2 → `nav2_explore.launch.py rviz:=true`）
4. 用 `<节点>_<pid>_<时间戳>.log` 抓各节点细节（`bt_navigator` 的 Begin/Goal succeeded、`planner_server` 的 error/warn）
5. **时间线交叉**：把 launch 目录名（起跑时刻）+ 各日志内的 `[epoch.纳秒]` 换算成本机时间，拼出完整时序
6. 统计用 `grep -c`，不要目测；失败类用 `grep -iE "fail|abort|reject|cancel|error"` **且要看输出为空**

**本轮实证**：完全靠日志反推出 9 个 launch 轮次、1 次拼写失败、2 次 RViz 崩溃、39/39 目标成功、
848 条 MOTOR_LOST 的起止窗口——现场无任何记录。

### 卡②：导航成功率验收的正确统计口径

**只统计 `bt_navigator` 的 `Begin navigating` 与 `Goal succeeded` 计数，不算「看到车走了」。**

1. `Begin navigating` 数 = 实际接收的目标数
2. `Goal succeeded` 数 = 到达数（`controller_server` 的 `Reached the goal!` 是同类旁证）
3. **必须另外 `grep` 失败类关键词并确认输出为空**——只看成功计数会漏掉「发了 40 次成功 39 次」
4. **必须校验 `current location` 是否变化**——恒定不变 = 里程计冻结，此时的「成功」是假的
5. 不能替代覆盖率 / 碰撞 / 行驶质量——目标成功只说明 planner+controller 走完了 BT

### 卡③：启动失败的第一现场判定（launch 条件表达式类）

launch 在**加载期**就抛异常时，所有节点一个都不会起，日志只有一行
`Caught exception in launch … invalid condition expression, expected one of [true, 1, false, 0] but got 'ture'`
→ 先查**参数拼写**（`rviz:=ture` / `autostart:=ture` 这类），不是 ROS 环境问题、不是包缺失。

---

## 七、经验点层次标注

> 去向说明：**draft** = `analysis-methods.md`（新经验先落此）｜**规则层** = `ros2-ops.md` / `standards.md` 等
> ｜**事件层** = 只留本文（偶发、未复现、不具迁移价值）

| # | 经验点 | 类型 | 建议去向 |
|:--|:---|:---|:---|
| E1 | `~/.ros/log/` 的目录名 = 启动时刻，`launch.log` + 各节点 log 足以完整重建一次实跑（起停顺序/命令/退出码/目标统计），无需 bag 或现场笔记 | 方法 | **draft**（卡①，跨场景可复用） |
| E2 | 导航成功率的正确口径 = `Begin navigating` / `Goal succeeded` 计数 **+ 失败关键词为空 + current location 有变化**；只看成功数会误判 | 方法 | **draft**（卡②） |
| E3 | **状态帧丢失 ≠ 控制失效**：CAN 反馈断了（MOTOR_LOST）但指令下发照常，导航继续（本轮**人为注入实测**：42% 告警期间 5 目标全成功）；排查时先分清「反馈链路」与「指令链路」 | 判据（已实证） | **规则层**（ros2-ops §7 排障纪律）——已有实车实证，建议直接抽取 |
| E4 | launch 加载期异常（条件表达式）先查参数拼写，此时所有节点未起 | 判据 | **规则层**（ros2-ops §7「启动/构建失败先看 launch.log」可增一句子例） |
| E5 | `inflation_radius < inscribed_radius` 的 ERROR 可跑通但**膨胀带全在内切圈内、无渐变**；开阔区不暴露、窄处会「可见不可过」 | 判据 | **draft**（与 ros2-ops §11 costmap 判据衔接） |
| E6 | RViz2 崩溃不影响 Nav2 主体，但会让操作者失去可视化——长跑/重启 Nav2 时须单独确认 RViz 存活 | 事件 | 事件层（Humble rviz2 已知问题，未核实） |
| E7 | 单场景 PASS ≠ 场景闭环（standards §1.15）：39/39 只覆盖「开阔区目标导航」，不含低物、不含窄缝、不含 explore | 纪律 | **规则层已存在**（§1.15），本文为其新增一例 |

---

## 八、遗留与下一步

| # | 项 | 现状 | 归属 |
|:--|:---|:---|:---|
| 1 | **S1 验收「覆盖率 >80%」未判定** | 未存地图、未采 `/map`、未录 bag | [explore-plan §3.5](../minimal-loop2/explore-plan.md) / G19 |
| 2 | **explore_lite 仍未在实车验证** | 本轮明确不跑；上一轮（19:12）报 `No frontiers found`，过滤放宽后**尚未复测** | G24 后半段 |
| 3 | **电机中断测试的覆盖边界** | 本轮验证了「中断后上层不受影响」；测试方式（断反馈 / 断供电）与恢复行为未在档内细化 | 如需扩展可补一轮并回填 §4.1 |
| 4 | **RViz2 崩溃未查** | 两次（−6 / −11） | 事件层 |
| 5 | **过滤器 polygon 与 Nav2 footprint 未对齐** | filter `x[−0.45,+0.40] y±0.34` vs footprint `±0.42/±0.33`（后边界差 3 cm） | [ld06_scan_filter.yaml 头注](../../ldlidar_stl_ros2/config/ld06_scan_filter.yaml) |
| 6 | 「规划全败」归因 | 本轮两变量同改，未拆分 | §五，可选最小实验 |

> 状态与待办同步见 [07-handover §五](../07-handover.md)、[pending-tasks](../pending-tasks.md)、
> [s1-readiness-gap G24](../old-car/s1-readiness-gap.md)；状态板同步按 doc-engineering §十一 核对卡执行。
