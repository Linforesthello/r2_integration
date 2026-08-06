# N97 远程桌面方案排障全记录（NoMachine → RealVNC → TigerVNC）

> 日期: 2026-08-05
> 机器: N97（192.168.1.210，x86_64 Ubuntu 22.04，GNOME Wayland）+ Windows 控制端
> 场景: 需要从 Windows 远程桌面访问 N97（机器人电脑），先后尝试三个方案
> 状态: ✅ TigerVNC 方案跑通（显示 :2，端口 5902），详见第五节

---

## 一、背景

N97 是机器人电脑（GNOME 桌面，Wayland 会话），需要远程桌面访问。
依次尝试 NoMachine 10 → RealVNC Server 7.13 → TigerVNC，前两个卡在商业授权墙，第三个成功。
本记录按时间线存档三个方案的全部踩坑与结论。

---

## 二、问题总览

| # | 方案 | 问题 | 根因 | 状态 |
|:--|:-----|:-----|:-----|:----:|
| 1 | NoMachine | `No subscription found on this server`，拒绝连接 | NoMachine 10 订阅商业化，试用密钥未内置 | ❌ 弃用 |
| 2 | RealVNC | Service Mode 不监听端口 | Wayland 无 X server，`Cannot find a running X server on vt2` | 换 Virtual Mode |
| 3 | RealVNC | 密码错误 `username was not recognised` | 默认认证是系统账户（PAM），非 VNC 密码 | 用系统凭据 |
| 4 | RealVNC | `no authentication schemes configured` | 配 `Authentication=VncAuth` 但 virtuald 无密码 | 删配置 |
| 5 | RealVNC | `Missing license`，连接被拒 | 无授权，试用需官网邮箱注册 | ❌ 弃用 |
| 6 | TigerVNC | `vncpasswd` 命令不存在 | Ubuntu 22.04 命令带 `tiger` 前缀；RealVNC 卸载带走同名文件 | 用 `tigervncpasswd` |
| 7 | TigerVNC | `server already running` 绑不上 :1 | 历史遗留锁 + 僵尸 socket（`/tmp/.X1-lock`、`/tmp/.X11-unix/X1`） | 换用 `:2` |
| 8 | TigerVNC | 只监听 127.0.0.1，Windows 连不上 | 启动器默认 `-localhost yes` | 加 `-localhost no` |
| 9 | TigerVNC | xfce4 启动即段错误 | 终端环境 `WAYLAND_DISPLAY` 泄漏，GTK 组件去连 Wayland 失败 | xstartup 里 unset |
| 10 | TigerVNC | 手动 Xtigervnc 桌面起不来 | 绕过了启动器的 X 认证（xauth）处理 | 用官方 `tigervncserver` |

---

## 三、详细记录

### 3.1 NoMachine 10 Personal Edition —— 订阅墙

**现象**：客户端连接报 `No subscription found on this server`；`nxserver --subscription` 显示
`Subscription type: PE` 但 `expiry: Unknown`。

**根因**：README 声称"包内自带试用密钥"，实际 10.0.57 装完无有效订阅。
安装日志明确指向官网生成试用许可（`nomachine.com/enterprise/enterprise-evaluation`）；
官网下载页也只剩 Personal Edition，免费档需邮箱注册试用且会过期。

**结论**：NoMachine 10 已订阅商业化，弃用。

### 3.2 RealVNC Server 7.13.1 —— Wayland 不兼容 + 授权墙

**现象链**：
1. Service Mode（`vncserver-x11-serviced`）日志 `Cannot find a running X server on vt2`，
   不监听端口 —— GNOME Wayland 下没有可抓的 X 会话；
2. Virtual Mode（`vncserver-virtuald`）监听 **5999**（虚拟显示 `:99`），但认证失败：
   默认认证是**系统账户（PAM）**而非 VNC 密码，报 `username was not recognised`；
3. 改配 `Authentication=VncAuth` 后，virtuald 没有自己的密码文件，报
   `no authentication schemes configured`（VNC 密码只存在于 Service 模式配置里）；
4. 最终 `Missing license` —— 无授权直接拒绝连接，试用需官网注册。

**结论**：商业化授权，弃用（`sudo dpkg -r realvnc-vnc-server`）。

### 3.3 TigerVNC —— 逐个排坑后成功

| # | 现象 | 根因 | 解决 |
|:--|:-----|:-----|:-----|
| 6 | `vncpasswd` 不存在 | Ubuntu 22.04 命令带 `tiger` 前缀；RealVNC 卸载时带走同名文件 | 用 `tigervncpasswd`/`tigervncserver`；`sudo apt install --reinstall tigervnc-common` 可恢复 |
| 7 | `server already running` 绑不上 :1 | 历史残留 `/tmp/.X1-lock` + `/tmp/.X11-unix/X1` 僵尸 socket（17:15 创建，占用来源未查明） | **换用 `:2` 绕开**（本地 GNOME 是 :0，不冲突） |
| 8 | 只监听 127.0.0.1 | 启动器默认 `-localhost yes` | 加 `-localhost no` |
| 9 | xfce4 段错误崩溃 | 从本地 GNOME 终端启动时 `WAYLAND_DISPLAY` 环境变量泄漏，GTK 组件去连 Wayland 显示失败 | `~/.vnc/xstartup` 里 `unset WAYLAND_DISPLAY` + `export GDK_BACKEND=x11` |
| 10 | 手动 Xtigervnc 桌面起不来 | 绕过启动器的 xauth 处理，客户端无授权 cookie | 改用官方 `tigervncserver` 启动器 |

**关键命令**（完整指令集见操作手册 `~/ProjectRequirement/MCU/Lin_STM32/STM32_F103C8T6/STM32_Now/doc/02-deploy/n97_remote_desktop.md`）：

```bash
tigervncpasswd                                # 设置 VNC 密码（≥6 位，只读密码选 n）
tigervncserver :2 -geometry 1920x1080 -depth 24 -localhost no   # 启动
```

**xstartup 最终版**（`~/.vnc/xstartup`）：

```sh
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
unset WAYLAND_DISPLAY
unset WAYLAND_SOCKET
export XDG_SESSION_TYPE=x11
export GDK_BACKEND=x11
exec xfce4-session
```

---

## 四、最终方案与验证

- TigerVNC（`tigervncserver :2 -geometry 1920x1080 -depth 24 -localhost no`），xfce4 虚拟会话
- 验证：Windows RealVNC Viewer 连 `192.168.1.210:5902` 成功，桌面可操作，rviz2 正常运行
- 备注：VNC 虚拟桌面与本地 GNOME 桌面是两个独立会话，VNC 里看到的是 xfce4 而非本地屏幕

---

## 四点五、跨机 DDS（VM rviz2）适用边界修正（2026-08-06 实测）

**背景**：曾计划把 rviz2 从 N97 挪到 VM（理由：N97 CPU 被 rviz2 吃满导致
`Message Filter dropping ... queue is full`），并完成了 FastDDS 固定端口 7410 +
单播 Peer 的跨机配置（VM 可列出 N97 全部话题、echo 实时数据）。

**实测结论（推翻原方案）**：

| 场景 | 结果 |
|:-----|:-----|
| VM 命令行查看（topic list / echo / bag 录制控制） | ✅ 正常，低带宽无压力 |
| **VM rviz2 实时可视化（含点云）** | ❌ **掉帧严重 + queue-is-full 刷屏**；且反向拖慢 N97（EKF `Failed to meet update rate`，WiFi 发送阻塞） |

**根因修正**：queue-is-full 不是 N97 CPU（当时 6.35 负载含 N97 本地 rviz2+建图），
而是 **WiFi 跨机链路带宽/延迟抖动**——VM 的 rviz2 经 WiFi 收点云/TF 时，
消息过滤器等 TF 超时 → 丢消息；N97 往 WiFi 发数据 → DDS 发送队列阻塞 → EKF 掉频率。

**最终方案**：**rviz2 留在 N97 本地**（回环，不占 WiFi）。跨机 DDS 保留用于
低带宽调试（命令行、bag 回放控制、数据导出）。

---

## 五、遗留问题

- [ ] VNC 开机自启未配置（重启后需手动 `tigervncserver`）
- [ ] N97 上 NoMachine（`/usr/NX`，端口 4000）未清理
- [ ] `:1` 历史占用来源未查明（疑似旧 VNC 会话残留）

---

## 相关文件

- 操作手册（含完整部署指令）：`STM32_Now/doc/02-deploy/n97_remote_desktop.md`
- 顺带发现（另案处理中）：`g354_imu_node` 协方差非对角项填值致矩阵奇异 → `/odometry/filtered` 发散 NaN，修复点在 `~/Lin_workspace/r2_integration/g354_driver/g354_imu_driver/imu_node.py`
