# N97 远程桌面方案（VNC）

> 记录日期：2026-08-05
> 适用范围：N97（192.168.1.210，x86_64 Ubuntu 22.04，机器人电脑）远程桌面访问
> 结论先行：**NoMachine / RealVNC 均因商业授权弃用，最终采用 TigerVNC（开源免费），已跑通**

---

## 1. 背景

需要从 Windows 远程访问 N97 桌面（机器人电脑，GNOME 桌面跑在 Wayland 上）。
尝试了三个方案，前两个都卡在授权墙上，第三个（TigerVNC）成功。

## 2. 最终方案：TigerVNC（现状可用）

N97 上 TigerVNC 已安装（Ubuntu 22.04 源自带，命令全部带 `tiger` 前缀）：

| 项 | 值 |
|:---|:---|
| 服务端 | `Xtigervnc`（`tigervncserver` 启动器） |
| 显示 | `:2`（**:1 被历史遗留占用，勿用**） |
| 端口 | **5902**（0.0.0.0，全网卡监听） |
| 桌面 | xfce4（独立虚拟会话，非本地 GNOME 镜像） |
| 认证 | VNC 密码（`tigervncpasswd` 设置，无用户名） |
| 客户端 | RealVNC Viewer / 任意 VNC 客户端 |

### 部署指令全集（N97 已验证，可整体复制）

```bash
# ── 1. 安装（如未安装；N97 上此前已装，跳过） ──
sudo apt install -y tigervnc-standalone-server tigervnc-common xfce4 xfce4-terminal

# ── 2. 设置 VNC 密码（≥6 位，连接要用；只读密码提示选 n） ──
tigervncpasswd

# ── 3. 配置 xstartup（关键：清掉 Wayland 环境变量，防 xfce4 段错误） ──
mkdir -p ~/.vnc
cat > ~/.vnc/xstartup <<'EOF'
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
unset WAYLAND_DISPLAY
unset WAYLAND_SOCKET
export XDG_SESSION_TYPE=x11
export GDK_BACKEND=x11
exec xfce4-session
EOF
chmod +x ~/.vnc/xstartup

# ── 4. 启动会话（显示 :2、端口 5902；:1 有历史占用勿用） ──
tigervncserver :2 -geometry 1920x1080 -depth 24 -localhost no

# ── 5. 验证 ──
tigervncserver -list          # 应列出 :2 会话
ss -tln | grep 5902           # 必须显示 0.0.0.0:5902（不是 127.0.0.1）

# ── 6. 连接（Windows 端） ──
# RealVNC Viewer → 地址 192.168.1.210:5902 → 输入第 2 步的 VNC 密码
# （无需用户名；若提示需要用户名，填 lin）

# ── 附：停止/清理 ──
tigervncserver -kill :2       # 停止会话
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1   # 清历史残留锁/僵尸 socket（仅 :1 冲突时用）
```

### 启动命令（N97 终端）

```bash
tigervncserver :2 -geometry 1920x1080 -depth 24 -localhost no
```

### 连接方法（Windows）

RealVNC Viewer → 地址 `192.168.1.210:5902` → 输入 VNC 密码。

### 会话管理

```bash
tigervncserver -list            # 查看会话
tigervncserver -kill :2         # 停止会话
```

## 3. 方案选型结论

| 方案 | 结论 | 原因摘要 |
|:---|:---|:---|
| NoMachine 10 Personal Edition | ❌ 弃用 | 订阅制，无授权直接拒连（`No subscription found on this server`） |
| RealVNC Server 7.13 | ❌ 弃用 | GNOME Wayland 下 Service Mode 不可用 + `Missing license` 授权墙 |
| TigerVNC | ✅ 采用 | 开源免费，Ubuntu 22.04 源自带 |

**完整排障路径（10 个坑的详细记录）**：见 `~/Lin_workspace/r2_integration/doc/retrospect/2026-08-05_n97_remote_desktop.md`

操作时需要记住的 3 条（详细原因见上述 retrospect）：

1. **显示号用 `:2`**，`:1` 有历史残留会冲突
2. **必须带 `-localhost no`**，否则只绑 127.0.0.1，Windows 连不上
3. **`xstartup` 必须 unset Wayland 变量**（全集第 3 步已含），否则 xfce4 段错误

## 4. 当前状态与遗留

- [x] TigerVNC 连接验证通过（xfce4 桌面可操作，rviz2 正常运行）
- [ ] **开机自启**：当前 VNC 重启后丢失，待配 systemd 服务（方案：`systemctl --user` 或 `/etc/systemd/system/` 单元，启动 `tigervncserver :2 ... -localhost no`）
- [ ] 清理：N97 上 NoMachine（`/usr/NX`，端口 4000）仍在，确认 VNC 稳定后可卸载
- [ ] N97 的 `/tmp/.X11-unix/X1` 历史占用来源未查明（疑似旧 VNC 会话残留），不影响使用

## 5. 其他说明

- VNC 虚拟桌面与本地 GNOME 桌面是**两个独立会话**，VNC 里看到的是 xfce4 而非本地屏幕内容（如需镜像本地桌面需另用 x11vnc + Xorg 会话）
- 调试 rviz2 时发现的 **EKF NaN 问题与本方案无关**（`g354_imu_node` 协方差非对角项填值致矩阵奇异 → `/odometry/filtered` 发散 NaN），修复进行中，另案留档

## 相关文件

- 排障全记录：`~/Lin_workspace/r2_integration/doc/retrospect/2026-08-05_n97_remote_desktop.md`
- N97 工作区：`~/Lin_workspace/r2_integration/`
- IMU 驱动源码（EKF NaN 修复点）：`~/Lin_workspace/r2_integration/g354_driver/g354_imu_driver/imu_node.py`
- 参考：[R1 树莓派控制操作手顺](raspi_r1_control.md)
