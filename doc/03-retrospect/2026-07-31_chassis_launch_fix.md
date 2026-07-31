# chassis.launch.py 启动失败修复全记录

> 日期: 2026-07-31
> 机器: 本地 VM（lin-virtual-machine）+ N97（192.168.1.210）
> 关联: `doc/02-deploy-checklist.md`

---

## 一、现象（三个连续报错）

在 N97 上 `ros2 launch r2_bringup chassis.launch.py` 连续失败：

```text
① python3: can't open file
   '.../install/r2_bringup/share/r2_bringup/r2_bringup/chassis_node.py': [Errno 2]
   (exit code 2)

② Package 'r2_bringup' not found, searching: ['/opt/ros/humble']
   （新 SSH 会话没 source，属操作问题，非代码问题）

③ package 'r2_bringup' found at '.../install/r2_bringup',
   but libexec directory '.../install/r2_bringup/lib/r2_bringup' does not exist
```

---

## 二、根因分析

### 根因 1（主因）：旧 launch 文件用 `__file__` 推导路径，依赖"从源码树启动"这个巧合

旧版 `chassis.launch.py`：

```python
pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
node_script = os.path.join(pkg_dir, 'r2_bringup', 'chassis_node.py')
```

推导结果是 `pkg_dir + /r2_bringup/chassis_node.py`，只有**源码树**里才有这个
`r2_bringup/r2_bringup/chassis_node.py`；安装布局（`share/r2_bringup/`）里不存在。

| 启动方式 | `__file__` 指向 | 推导结果 | 结果 |
|:--|:--|:--|:--|
| `ros2 launch ~/Lin_workspace/.../launch/chassis.launch.py`（文件路径）| 源码树 | `r2_bringup/r2_bringup/chassis_node.py` ✅ | 能用 |
| `ros2 launch r2_bringup chassis.launch.py`（包名）| `install/.../share/r2_bringup/launch/` | `share/r2_bringup/r2_bringup/chassis_node.py` ❌ | 报错 ① |

**为什么之前一直好的**：VM 上的习惯是文件路径方式启动（`~/.bash_history` 1606/1842/1844/1850
行；`~/.ros/log/2026-07-29-*` 的 launch.log 里 `cmd 'python3 .../r2_integration/r2_bringup/r2_bringup/chassis_node.py'`
可见当时 `__file__` 确实解析到源码树）。这次在 N97 上改用**包名**方式启动，launch 文件从
install 目录加载，脆弱推导立即暴露。

### 根因 2（潜伏）：本环境 colcon 把 console_script 装到 `bin/`，launch_ros 只搜 `lib/<pkg>/`

- 标准 ament_python 布局：`install/<pkg>/lib/<pkg>/<exec>`
  （对照 `/opt/ros/humble/lib/demo_nodes_py/`，apt 装的包都是这个布局）
- 本机（VM 和 N97 一致）colcon 行为：`install/<pkg>/bin/<exec>`
- launch_ros 的 `ExecutableInPackage` 替换硬编码：
  `package_libexec = os.path.join(package_prefix, 'lib', package)` —— **只搜 `lib/<pkg>/`**

后果：`Node(package=..., executable=...)` 和 `ros2 run` 在本环境都会报 ③。
旧 launch 用 `ExecuteProcess + python3 + 源码路径`，从不走入口脚本，所以这个坑一直被掩盖，
直到改成 `Node(executable=...)` 才暴露。

### 根因 3（次要）：新 SSH 会话未 source 工作区

报错 ② 只是 `AMENT_PREFIX_PATH` 里没有工作区，`~/.bashrc` 未配置，
每个新终端需手动 `source ~/Lin_workspace/r2_integration/install/setup.bash`。

---

## 三、修复方案

新版 `chassis.launch.py` 核心：

```python
def _find_node_executable(pkg: str, name: str) -> str:
    """console_script 入口安装位置两种环境不一致：
    标准布局在 lib/<pkg>/，本机 colcon 装在 bin/，两种都找。"""
    prefix = get_package_prefix(pkg)
    for rel in (os.path.join('lib', pkg, name), os.path.join('bin', name)):
        path = os.path.join(prefix, rel)
        if os.path.exists(path):
            return path
    raise FileNotFoundError(...)

# 配置路径: get_package_share_directory('r2_bringup') + config/r2_params.yaml
# Node(executable=<绝对路径>, parameters=[config_path])
```

要点：
- 不再用 `__file__` 推导，改用 ament_index 的 `get_package_prefix` / `get_package_share_directory`
- 入口脚本两种布局（`lib/<pkg>/` 和 `bin/`）都兼容，跨环境不挑 colcon 行为
- `ekf.launch.py` 无此问题：它推导的 `config/ekf.yaml` 确实装在 `share/r2_bringup/config/` 下，路径成立

---

## 四、验证

N97 上 `timeout 6 ros2 launch r2_bringup chassis.launch.py` 实测输出：

```text
[chassis_node-1] CAN 接口已打开: can0
[chassis_node-1] R2 底盘节点已启动
[chassis_node-1] 半对角线 R = 0.330 m
[chassis_node-1] wheel_diameter = 0.152 m
[chassis_node-1] ticks_per_rev = 4241
[chassis_node-1] m_per_tick = 0.000113 m
[chassis_node-1] speed_scale = 94.5
[chassis_node-1] 限速: vx=0.5, vy=0.3, ω=0.8
```

节点完整启动、CAN 打开、参数全部加载。（6 秒后被 timeout 正常终止，属测试手段。）

---

## 五、教训 / 最佳实践

1. **launch 文件永远不要用 `__file__` 做相对路径推导** → 用 `get_package_share_directory` / `get_package_prefix`
2. **跨机器启动统一用包名方式** `ros2 launch r2_bringup chassis.launch.py`；文件路径方式会掩盖安装布局差异
3. **本环境 `ros2 run r2_bringup chassis_node` 同样会报 libexec 错**（只搜 `lib/<pkg>/`），一律走 launch 文件
4. **新 SSH 会话记得 source** `install/setup.bash`（或写入 `~/.bashrc`）
5. **老机器"能用"不等于代码正确**：可能是启动方式巧合（源码树路径）或 install 残留文件掩盖；
   新机器全新构建是最佳体检
6. **排查启动问题先看 ros log**：`~/.ros/log/<时间戳>/launch.log` 里有完整 cmd 和 exit code

---

## 六、当前状态与待办

| 项目 | 状态 |
|:--|:--|
| 本地 VM launch 文件修复 | ✅ 已改（未提交 git） |
| N97 同步 + 重建 | ✅ 已完成 |
| 启动验证 | ✅ 通过 |
| git 提交修复 | ⏳ 待办（origin: github.com/Linforesthello/ros-） |
| N97 .bashrc 自动 source | ⏳ 可选 |
