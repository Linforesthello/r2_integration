# R2 r2_integration 仓库修复全记录

> 日期: 2026-08-03
> 机器: N97（192.168.1.210，lin-Default-string）+ 开发 VM（lin-virtual-machine）
> 场景: r2_integration 仓库状态混乱检查与修复，GitHub/VM/N97 三端同步
> 状态: ✅ 全部解决，三端一致（详见第五节）

---

## 一、背景

2026-08-03 发现 r2_integration 仓库"有问题"。线索是 N97 上残留的历史操作：
GitHub https 直连失败（曾用 curl 检查连通性）、曾用 `/tmp/r2_bundle.bundle`
恢复仓库、`rm -rf .git` 后 `git init` 重建、origin 曾指向
`Linforesthello/Lin_workspace.git`（与最终仓库名 `r2_integration.git` 不一致）。
仓库经过多轮折腾后状态不可信，以 GitHub 为权威源统一三端。

---

## 二、问题总览

| # | 问题 | 根因 | 状态 |
|:--|:-----|:-----|:----:|
| 1 | GitHub 仓库混入 22 个 bag 测试文件（4 组） | 顶层缺 .gitignore，`*.bag` 规则缺失 | ✅ |
| 2 | N97 上 r2_integration 无独立 .git，只是 ~/Lin_workspace 大仓库的子目录 | 曾把整个 workspace 初始化为 git 仓库 | ✅ |
| 3 | N97 大仓库历史与 GitHub hash 全不同、落后 2 个提交 | 历史被重建/重写过，内容旧 | ✅ |
| 4 | N97 clone 失败 Permission denied (publickey) | 未配 GitHub SSH key | ✅ |
| 5 | ~/Lin_workspace 大仓库已暂存 r2_integration/ 全部删除（未提交），状态悬空 | 中途放弃的 `git rm --cached` | ✅ 仓库已撤销 |

---

## 三、详细记录

### 3.1 确认 GitHub 端仓库并 clone（VM）

VM 上 `git clone git@github.com:Linforesthello/r2_integration.git` 成功
（154 objects / 10.82 MiB）。验证：6 个提交、`main` 分支、工作区干净、72 个跟踪文件。

### 3.2 内容核对与 bag 混入确认

`git ls-tree` 逐项核对，内容本身完整：

- `doc/` 结构齐全（01-plan、02-progress、03-current_state、07-handover、
  standards、obsidian-tags、phase0×3、phase1×2、retrospect×6）
- `r2_bringup`、`g354_driver` 两个 ROS2 包完整；`scripts/` 4 个标定脚本
- ❌ 混入 4 组 bag 共 22 个文件：`r2_eKF_test.bag`(10)、`r2_square_test.bag`(3)、
  `r2_turn_test.bag`(3)、`g354_driver/imu_zupt_test.bag`(6)；单个 db3 最大 6.7MB，
  占仓库体积大头
- 顶层无 .gitignore（bag 混入的根源；仅 g354_driver/ 内有一个局部 .gitignore）

### 3.3 清理并推送（VM）

```bash
git rm -r --cached r2_eKF_test.bag r2_square_test.bag r2_turn_test.bag g354_driver/imu_zupt_test.bag
# 仅移除跟踪，本地文件保留
cat > .gitignore <<'EOF'
# Python
__pycache__/
*.py[cod]
*.egg-info/
# Build artifacts
build/
install/
log/
# 测试数据
*.bag
EOF
git add .gitignore
git commit -m 'R2|清理误入库的测试bag数据，*.bag不入库'
git push origin main
```

结果：提交 `fc3ca70`，推送 `00c2933..fc3ca70`，剩余跟踪文件 51 个。

### 3.4 N97 侦察：r2_integration 不是独立仓库

SSH 侦察 N97（192.168.1.210）：

- `~/Lin_workspace/r2_integration` **无独立 .git**——`git -C` 命令实际命中的是
  `~/Lin_workspace/.git`（git 会向上查找父目录的 .git）
- `~/Lin_workspace` 大仓库跟踪 177 个文件，历史 `c8b62ef` 系列，与 GitHub
  `00c2933` 系列 hash 全不同且**落后 2 个提交**（缺 kiss-icp、EKF/TF 修复）
- 工作区已暂存 `r2_integration/` 全部删除（`D` 状态，未提交）
- 无大型独有数据，旧内容均可从 GitHub 重建

### 3.5 N97 配 SSH key 并重新 clone

```bash
cd ~/Lin_workspace
mv r2_integration r2_integration_old_bak      # 先备份再替换
git clone git@github.com:Linforesthello/r2_integration.git r2_integration
# → Permission denied (publickey)：未配 SSH key
ssh-keygen -t ed25519 -C "lin@192.168.1.210" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub                     # 复制到 GitHub → Settings → SSH and GPG keys
ssh -T git@github.com                         # Hi Linforesthello! 验证通过
git clone git@github.com:Linforesthello/r2_integration.git r2_integration
# → 成功：fc3ca70、51 文件、工作区干净
```

### 3.6 撤销 ~/Lin_workspace 大仓库

```bash
rm -rf ~/Lin_workspace/.git    # 仅撤销 git 状态，所有文件保留
```

验证：`~/Lin_workspace` 不再是 git 仓库（普通目录）；`r2_integration/` 独立仓库不受影响。
此后 workspace 内唯一 git 仓库为 r2_integration。

### 3.7 bag 归集到仓库内 bags/（gitignore 过滤）

- **N97**：顶层 4 组 bag（r2_eKF/r2_square/r2_turn/r2_slip_test.bag）+ old_bak 内的
  imu_zupt_test.bag → `r2_integration/bags/`
- **VM**：同法归集 4 组（r2_eKF/r2_square/r2_turn + g354_driver/imu_zupt_test.bag）

`.gitignore` 的 `*.bag` 规则自动忽略，`git check-ignore bags/r2_eKF_test.bag` 验证生效，
bag 留在仓库目录内随数据集中管理，但不上传。

---

## 四、修改文件清单

| 位置 | 改动 |
|:-----|:-----|
| GitHub 仓库（VM 提交推送） | 顶层新增 `.gitignore`（含 `*.bag`）；移除 22 个 bag 跟踪文件；提交 `fc3ca70` |
| N97 | 配置 GitHub SSH key（ed25519） |
| N97 | `rm -rf ~/Lin_workspace/.git`（撤销大仓库，文件保留） |
| N97 | bag 归集 → `r2_integration/bags/`（5 组） |
| VM | bag 归集 → `r2_integration/bags/`（4 组） |

---

## 五、当前状态（2026-08-03）

| 位置 | 状态 |
|:-----|:-----|
| GitHub `Linforesthello/r2_integration.git` | `main`、51 文件、HEAD `fc3ca70`、无 bag |
| 开发 VM | clone 同步、工作区干净、`bags/` 归集完成 |
| N97（192.168.1.210） | `~/Lin_workspace` 普通目录（无 git）；`r2_integration` 独立仓库同步；SSH key 就绪 |

---

## 六、遗留与待办

- [ ] `r2_integration_old_bak/` 备份目录：确认新仓库可正常编译/启动后删除
      （内含旧代码、build/install/log；imu_zupt_test.bag 已移出）

---

## 七、教训总结

1. **判断"某目录是不是独立仓库"必须 `ls -d .git` 实锤**：git 会在父目录向上查找
   `.git`，`git -C` 子目录的输出可能来自外层仓库，易误判
2. **二进制/测试数据（bag）必须靠顶层 .gitignore 保护**：顶层 .gitignore 缺失是
   本次 bag 混入的根源
3. **一个项目一个仓库**：把整个 workspace 初始化为 git 仓库，会把 build/install/log、
   杂项数据全卷进去，是混乱的根源
4. **多机协作以 GitHub 为唯一权威源**：各机配好 SSH key，避免 publickey 失败
5. **历史被重写后 hash 全变，跨机无法对账**：不要反复 `rm -rf .git` 重建，
   先确认权威源再动手
6. **破坏性操作先改名备份**（`mv` → `*_old_bak`）再替换，确认无误后再清理
