#!/usr/bin/env bash
# net_diag.sh — 网络可达性分层诊断（只读，单文件执行）
#
# 用途：
#   - 判断「外网 / 某站点不通」是路由、DNS、ICMP、TCP、TLS 还是应用层问题；
#   - 识别本机代理 TUN（fake-ip）接管，避免把本地回环 RTT 当成真实连通；
#   - 同一台机多次运行做控制变量对照（代理开 / 关）。
#
# 典型用法（VM 或 N97 本地执行均可，无需 ROS 环境）：
#   bash scripts/net_diag.sh                     # 默认目标 github.com
#   bash scripts/net_diag.sh github.com --git    # 追加应用层 git ls-remote 探测
#   bash scripts/net_diag.sh example.com         # 换目标站点
#   GIT_URL=https://github.com/foo/bar bash scripts/net_diag.sh --git   # 指定仓库
#
# 为什么做成脚本：多行命令块直接粘贴到终端会**丢换行**（表现为
# `curl: (6) Could not resolve host: echo`、`tail: 无法以读模式打开 'echo'`），
# 把命令落成文件再执行可彻底绕开该问题（2026-11-07 实测踩坑）。
#
# 验收背景（2026-11-07 VM / N97 三次对照实测）：
#   - 未开代理：github 解析真实 IP（20.205.243.166），TCP 可连，curl 卡到超时，git exit=124；
#   - 开代理后（Meta 198.18.0.1/30，解析为 fake-ip 198.18.x.x）：http=200，git exit=0；
#   - 两台机结论一致 → 根因是「代理未开」，不是网络故障。
#   经验条目见 doc/analysis-methods.md 主题 L。
#
# 只读保证：不修改任何配置、不启动常驻进程、不写仓库文件（仅 /tmp 下临时日志）。
#
# 退出码：0 = 执行完成（不代表网络通）；2 = 参数错误。

set -uo pipefail

TARGET=""
DO_GIT=0
for arg in "$@"; do
  case "$arg" in
    --git) DO_GIT=1 ;;
    -h|--help) sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "未知参数: $arg（可用: --git, -h）" >&2; exit 2 ;;
    *) TARGET="$arg" ;;
  esac
done
TARGET="${TARGET:-github.com}"

sec() { printf '\n===== %s =====\n' "$1"; }

printf 'net_diag: 目标=%s  git探测=%s\n' "$TARGET" "$([ "$DO_GIT" = 1 ] && echo on || echo off)"

# ---------------------------------------------------------------- 0 环境
sec "0 机器 / 网络环境"
date '+%F %T %Z'; hostname
ip -4 addr show | awk '/inet /{print "  "$NF" "$2}'

echo "-- 默认路由 --"
ip route | grep -E '^default' | sed 's/^/  /' || echo "  !! 无默认路由（先修网关，与目标站无关）"

echo "-- DNS --"
grep -vE '^\s*#|^$' /etc/resolv.conf | sed 's/^/  /'

echo "-- 代理环境变量 --"
env | grep -i proxy | sed 's/^/  /' || echo "  (无)"

echo "-- 虚拟网卡（代理 TUN 指纹）--"
ip -br link | grep -Ei 'meta|tun|tap|utun|wg' | sed 's/^/  /' || echo "  (无 tun/tap/meta/wg 接口)"

# ---------------------------------------------------------------- 1 DNS
sec "1 DNS 解析"
IPS="$(getent hosts "$TARGET" | awk '{print $1}')"
if [ -z "$IPS" ]; then
  echo "  !! $TARGET 解析失败（DNS 不转发外网 / 域名错）"
else
  echo "$IPS" | sed 's/^/  /'
  if echo "$IPS" | grep -qE '^198\.(18|19)\.'; then
    echo "  → 命中 198.18.0.0/15：代理 TUN fake-ip 池，本机代理接管了该域名"
  fi
fi

# ---------------------------------------------------------------- 2 ICMP
sec "2 ICMP（仅作辅证，部分网络禁 ping）"
for h in 223.5.5.5 "$TARGET"; do
  out="$(ping -c 3 -W 2 "$h" 2>&1 | tail -2 | tr '\n' ' ')"
  printf '  %-18s %s\n' "$h" "${out:-（无输出）}"
done

# ---------------------------------------------------------------- 3 TCP
sec "3 TCP 443（/dev/tcp，免装 nc）"
if timeout 8 bash -c "cat < /dev/null > /dev/tcp/$TARGET/443" 2>/dev/null; then
  echo "  $TARGET:443 可连"
else
  echo "  !! $TARGET:443 连不上 / 超时（端口级阻断或目标不可达）"
fi

# ---------------------------------------------------------------- 4 HTTPS
sec "4 HTTPS 分段耗时（dns / conn / tls / total）"
timeout 20 curl -sS -o /dev/null \
  -w "  http=%{http_code} dns=%{time_namelookup}s conn=%{time_connect}s tls=%{time_appconnect}s total=%{time_total}s\n" \
  "https://$TARGET" 2>&1 || echo "  !! curl 超时或失败（无输出 = 连接未完成，通常在 TLS 阶段）"

# ---------------------------------------------------------------- 5 基线
sec "5 国内基线对照（区分「定向阻断」与「整网不通」）"
for h in www.baidu.com gitee.com; do
  timeout 15 curl -sS -o /dev/null \
    -w "  $h http=%{http_code} total=%{time_total}s\n" \
    "https://$h" 2>&1 || echo "  !! $h 超时 / 失败"
done

# ---------------------------------------------------------------- 6 应用层
if [ "$DO_GIT" = 1 ]; then
  sec "6 应用层 git ls-remote（卡在哪一步）"
  GIT_URL="${GIT_URL:-}"
  if [ -z "$GIT_URL" ]; then
    if [ "$TARGET" = "github.com" ]; then
      GIT_URL="https://github.com/ros2/ros2"
    else
      GIT_URL="https://$TARGET/"
    fi
  fi
  echo "  仓库: $GIT_URL"
  GIT_CURL_VERBOSE=1 GIT_TERMINAL_PROMPT=0 timeout 30 \
    git ls-remote "$GIT_URL" >/tmp/net_diag_git.log 2>&1
  rc=$?
  echo "  exit=$rc"
  if [ "$rc" -eq 0 ]; then
    echo "  → 全链路通（应用层无阻）"
  else
    echo "  → 失败；日志尾部（停在 Trying = TCP 卡住，停在 SSL = TLS 层）："
    tail -5 /tmp/net_diag_git.log | sed 's/^/    /'
  fi
fi

# ---------------------------------------------------------------- 判读
sec "判读提示"
cat <<'EOF'
  国内基线通 + 目标不通        → 定向阻断（多为 TLS/SNI 层），不是整网故障
  国内基线也不通              → 本机没出网：查默认路由 / WiFi / 网关 / 防火墙
  有 Meta/tun 且解析 198.18.x  → 代理接管；此时 ICMP RTT 亚毫秒是 TUN 本地回环，
                                不能当真实网络 RTT，连通性只认 curl 的 http_code 与 git exit
  curl 有 conn 但 tls 空/total 超时 → TCP 放行、TLS 层被干扰
  git exit=0                  → 该仓库全链路通
  push 报 kex_exchange_identification → 代理常不放行 GitHub 22 端口；
                                改用 ssh.github.com:443（见 doc/analysis-methods.md 主题 L5）
EOF
