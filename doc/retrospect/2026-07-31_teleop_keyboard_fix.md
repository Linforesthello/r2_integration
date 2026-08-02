# 键盘控制修复全记录（teleop_twist_keyboard → R2 专用 WASD 遥控）

> 日期: 2026-07-31
> 机器: N97（192.168.1.210，SSH 操作）+ 本地 VM（lin-virtual-machine）
> 关联: `02-deploy-checklist.md` ⑤ 键盘控制、`control/R2.py`（旧 WASD 布局）
> 状态: ✅ 已修复，N97 实车验证通过

---

## 一、现象

在 N97 上运行 `ros2 run teleop_twist_keyboard teleop_twist_keyboard` 遥控 R2 时：

1. **按键对应动作不一致**：按 `w/s/a/d/q/e` 车子不动甚至停车（按 R2.py 的 WASD 肌肉记忆，这些键应分别对应前/后/左/右平移与旋转）
2. **按键疑似被复用**：同一键在不同语境下行为不同（`q/e/w` 实际是调速，不是运动）
3. **一键多状态**：`u/o/m/.` 一个键同时产生"平移+旋转"两个动作

---

## 二、根因

### 根因 1（主因）：官方 teleop_twist_keyboard 按键布局与 R2 的 WASD 习惯冲突

官方 apt 版（ros-humble-teleop-twist-keyboard 2.4.1）默认布局是 VI 风格，面向**差速底盘**：

| 按键 | 官方实际行为 | R2.py 用户预期 |
|:----:|:------------|:--------------|
| `w` / `e` / `q` | **调速**（±10% 速度档），车不动 | 前进 / 右转 / 左转 |
| `a` / `s` / `d` | 未定义键 → **发停车** | 左移 / 后退 / 右移 |
| `i` / `,` / `j` / `l` | 前 / 后 / 左转 / 右转 | 无对应 |
| `u` / `o` / `m` / `.` | **一键 = 平移+旋转组合** | 单状态 |
| `t` / `b` | 竖直上下（R2 无意义） | — |
| Shift+`J`/`L` | 横移（linear.y）| 普通键即可横移 |

要点：
- 官方版默认**不发布 `linear.y`**（横移），全向底盘的平移能力被锁在 Shift 组合里
- `u/o/m/.` 的"一键两状态"正是"一个按键代表多个状态"的来源

### 根因 2（初版自定义节点的坑）：raw 模式读终端时 Ctrl-C 无法退出

`tty.setraw()` 关闭终端 ISIG 标志后，**Ctrl-C 不再产生 SIGINT**，而是作为 `0x03` 字节被 `read()` 读走。若代码未显式识别 `0x03`，按 Ctrl-C 只会落入"未定义键 → 停车"分支，程序永远退不出。官方实现正是靠 `if key == '\x03': break` 处理。

### 排查插曲（教训 3）：本机 VM 网络配置误判

排查过程中曾误将本机 VM 的 `~/cyclonedds.xml`（绑定 ens37）当作关联问题：
- 现象：本机 `ros2 topic list` 报 `ens37: does not match an available interface`（当时 ens37 无 IP，CycloneDDS 建域失败）
- 结论：该问题只影响**本机 VM** 的 ROS2，与 N97（SSH 过去跑 teleop/chassis）**无关**；且 ens37 后来获得 IP（10.10.3.30，VLP-16 网段）后原配置即有效
- 处理：恢复原配置，未做任何改动

---

## 三、修复

新增 `r2_bringup/r2_bringup/teleop_keyboard.py`（R2 专用 WASD 遥控节点）：

```
按键布局（用户坐标系，chassis_node 内部已做 90° 变换）:
    w = 前进      s = 后退
    a = 左平移    d = 右平移
    q = 左转      e = 右转
    k / 空格 / 其他键 = 停车
    + / - = 加速 / 减速
    Ctrl-C = 退出并停车
```

设计要点：
- **一键一状态**：每个键只改一个速度分量，无组合键（消除"一键多状态"）
- 未定义键**显式停车**（官方行为，但按键表无歧义）
- **10Hz 持续发布**：按住按键期间命令不中断，松开后由 chassis_node 的 0.5s cmd 超时兜底停车
- **Ctrl-C 显式识别 `0x03`** → 停车并退出；主循环用 `spin_once` 轮询 `_running` 感知线程退出
- **终端恢复双保险**：键盘线程 finally + main finally 都恢复（SIGINT 兜底路径下线程可能被强杀）
- 速度默认 vx=0.3 / vy=0.2 / ω=0.6，低于 chassis 限速（0.5/0.3/0.8），`+`/`-` 可调
- 直接发用户坐标系速度，与 `calibrate_direction.py` 标定方向一致

配套改动：
- `setup.py` 注册 entry point `teleop_keyboard`

### 启动方式（N97）

```bash
# 绕开本环境 colcon libexec 布局问题（ros2 run 会报 libexec 错，与 chassis_node 同坑），
# 直接 python3 源码路径启动；SSH 交互登录 .bashrc 已自动 source ROS2
python3 ~/Lin_workspace/r2_integration/r2_bringup/r2_bringup/teleop_keyboard.py
```

---

## 四、验证

N97 实车测试（用户确认）：**"键盘控制很完美"**
- 各按键方向与动作一致（前/后/左移/右移/左转/右转）
- 横移可用（官方 teleop 做不到）
- Ctrl-C 正常退出，shell 无 raw 模式残留

---

## 五、教训 / 最佳实践

1. **官方 teleop_twist_keyboard 面向差速底盘 + VI 键位习惯**：全向底盘横移需要 Shift，且按键语义与国内车队常见 WASD 习惯冲突 → 全向底盘应自定义遥操节点（本项目做法：与 `control/R2.py` 保持一致）
2. **raw 模式读终端的程序，Ctrl-C 必须显式处理 `0x03` 字节**（官方实现即为参考），且退出时恢复终端设置
3. **排查先确认操作场景**：本机 VM 与 SSH 远程（N97）是两个独立 ROS2 域，本机 DDS 配置故障不代表远端问题；不要因本机观察到报错就认定与用户问题相关

---

## 六、当前状态与待办

| 项目 | 状态 |
|:--|:--|
| 新增 teleop_keyboard.py（VM 源码） | ✅ |
| N97 同步 + 实车验证 | ✅ |
| setup.py entry point | ✅（下次 colcon build 生效） |
| git 提交 | ⏳ 待办（r2_integration 仓库；注意 chassis_node.py、r2_params.yaml 也有此前未提交改动） |
| 部署清单 ⑤ 命令更新 | ⏳ 待办（可改为新节点启动命令） |
| launch 集成（可选） | ⏳ 待办（如需一键启动，注意本环境 libexec 布局） |
