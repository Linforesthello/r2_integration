# 2026-08-15 · velodyne 外设抽包 r2_sensors + g354 包完整性补全

> 事件：一次"包结构整理"任务——补全 g354_imu_driver 的包完整性，并把 VLP-16 运行物从
> r2_bringup 抽出为独立包 r2_sensors。VM 改码 → 提交推送 → N97 pull 实测，全链路闭环。
> 提交：`ae55384`（g354 补全）、`f2e9a38`（抽包），已推 origin/main。

---

## 一、背景与目标

1. **g354_imu_driver 补全**：全量构建长期打印警告
   `Package 'g354_imu_driver' doesn't explicitly install a marker in the package index`
2. **velodyne 外设抽包**：VLP-16 的 launch/URDF 原本塞在底盘包 r2_bringup 里（08-14 入库时
   的历史归置），与底盘职责混在一起，也不利于后续 D435/MID70 等外设扩展

---

## 二、做了什么

### 1. g354_imu_driver 补全（提交 `ae55384`）

| 文件 | 改动 |
|:---|:---|
| `g354_driver/resource/g354_imu_driver` | 新建 ament index marker 空文件（包索引标识） |
| `g354_driver/setup.py` | data_files 补 `share/ament_index/resource_index/packages` 安装行 |
| `g354_driver/package.xml` | 补 `<depend>launch_ros</depend>` `<depend>ament_index_python</depend>` |
| `r2_bringup/package.xml` | 同上补依赖（两包保持一致） |
| `g354_driver/README.md` | 文件树修正：旧 `g354_test/` 目录名、reference/ 已删、补 resource/ |

### 2. velodyne 抽包 r2_sensors（提交 `f2e9a38`）

```
r2_sensors/
├── package.xml            # 新写（format 3，depend: launch_ros + ament_index_python）
├── setup.py               # 标准模板（带 marker，吸取 g354 教训）
├── resource/r2_sensors    # marker 空文件
├── launch/velodyne.launch.py   # 自 r2_bringup 移入，改 1 行包名引用
└── config/r2.urdf              # 自 r2_bringup 移入（内容不变）
```

- r2_bringup 侧：删除上述 2 文件，setup.py 去掉 config glob 里的 `*.urdf`
- **config/dds 留在 r2_bringup**：它是全系统跨机通信配置（N97 每个 ROS 终端 export），
  不是 velodyne 外设物。留原地则 bashrc、ros2-ops、project_status 的路径全部不用动
- 文档 6 处同步（grep 逐一确认）：README 文件树、07-handover ×3、w1-operation、
  01-plan ×2、minimal-loop/plan、sensor-mount ×2；**retrospect 历史留档一律不改**

### 3. 验证

| 环境 | 验证内容 | 结果 |
|:---|:---|:---|
| VM | `rm -rf build install` + 全量构建 | 3 包通过，**g354 警告消失**，r2_bringup install 零残留 |
| VM | `ros2 launch r2_sensors velodyne.launch.py` 冒烟 | 三节点正常启动，包路径解析正确 |
| N97 | pull + 构建 + `ros2 launch r2_sensors velodyne.launch.py` | 实车雷达跑通，KISS-ICP 9.53Hz 正常 |

---

## 三、踩坑与错误（按严重度）

### 坑 1（技术债）：g354 缺 ament index marker

- **现象**：每次全量构建打印警告，colcon 隐式补装 marker
- **根因**：g354 的 setup.py data_files 缺
  `('share/ament_index/resource_index/packages', ['resource/' + package_name])`
  （r2_bringup 有，g354 没有——标准模板的坑没继承全）
- **后果**：当前无害（colcon 隐式补装），但未来 colcon 移除隐式行为后，
  `ros2 pkg`/`ros2 launch` 将无法发现 g354 包
- **教训**：新包必须带 marker（r2_sensors 新包直接用标准模板，没重蹈覆辙）

### 坑 2（操作）：git mv 自动暂存 → 提交内容混入

- **现象**：提交①（g354 marker）的提交内容里混进了 r2_sensors 的 rename
- **根因**：`git mv` 会自动把移动加入暂存区，commit 时未检查暂存区全貌
- **处理**：`git reset --soft HEAD~1` + `git restore --staged .` 拆开重组（本地未 push，零风险）
- **教训**：**git mv 之后、commit 之前，必须先 `git status` 看清暂存区**；
  用显式文件列表 `git add`，不要 `git add .`

### 坑 3（概念）：install 残留——colcon build 不删已装文件

- **现象**：抽包后若不清理，`ros2 launch r2_bringup velodyne.launch.py` 旧命令仍"生效"
- **根因**：colcon 的 install 是**增量拷贝**，源文件消失不会删 install 里已装的文件
- **处理**：`rm -rf build install` 全量重编（或手动删旧文件）
- **验证**：N97 上旧命令报 "file was not found in the share directory" = 残留已清，是预期现象

### 坑 4（环境）：AMENT_PREFIX_PATH 陈旧路径警告

- **现象**：删 install 重建后构建，报
  `The path '.../install/r2_bringup' in AMENT_PREFIX_PATH doesn't exist`
- **根因**：当前 shell 的 AMENT_PREFIX_PATH 还是**旧版** `source install/setup.bash`
  留下的路径（旧 install 已删）
- **处理**：无害；新开终端重新 source 即消失。**但旧环境终端不能用来启动新包**
  （不知道 r2_sensors 的存在）

### 坑 5（概念）：仓库 ≠ 包

- **误区**：把 r2_integration 仓库当"一个包"
- **正解**：colcon 构建单位是**包**（package.xml 定义），仓库可含多包；
  `--packages-select` 只构建指定包是**日常正确姿势**（增量构建），
  `--packages-up-to` 连依赖一起构建，pull 后不确定先全量

---

## 四、方向决策（含理由）

| 决策 | 选项对比 | 结论 |
|:---|:---|:---|
| 新包名 | `r2_sensors`（预留多外设）vs `r2_velodyne`（单外设） | **r2_sensors**：后续 D435/MID70 的 launch 都归入，避免包数量膨胀 |
| dds 归属 | 留 r2_bringup vs 随外设走 | **留 r2_bringup**：全系统通信配置，非外设物；同步改 3 处文档 + 机器 bashrc 的成本不值得 |
| 提交划分 | 一次大提交 vs 两次语义提交 | **两次**：① 补全类 ② 抽包类，符合"阶段完成即提交"，git log 可回溯 |

---

## 五、经验教训（沉淀）

1. **包完整性**：ament_python 包必须显式安装 index marker，别依赖 colcon 隐式行为
   （警告就是债，今天不还明天还）
2. **操作纪律**：任何 `git mv`/批量操作后先 `git status`；提交用显式文件列表
3. **动刀前先摸引用**：抽包前 grep 全部引用点（文档 6 处 + launch 内部），
   一次改全，不留"改了个寂寞"的隐藏路径
4. **install 副本 ≠ 源码**（ros2-ops.md §2 再次印证）：改配置/launch 必须构建或手动同步，
   删文件必须清 install 残留
5. **旧环境终端不可信**：构建后新开终端再 source，否则可能测到旧环境
6. **概念澄清即效率**：搞清"仓库/包/构建粒度"三个概念，`--packages-select` 用起来才有底气

---

## 六、相关文件与提交

- 提交：`ae55384`（g354 补全）｜`f2e9a38`（抽包）——已推 origin/main
- 新包：[r2_sensors/](../../r2_sensors/)
- 改动文档：README.md、doc/07-handover.md、doc/minimal-loop/w1-operation.md、
  doc/01-plan.md、doc/minimal-loop/plan.md、doc/phase0/sensor-mount.md、g354_driver/README.md
- 关联规范：[standards.md 1.10 提交规范](../standards.md)、[ros2-ops.md §2 构建部署](../ros2-ops.md)
- 未入库遗留：`doc/retrospect/2026-08-13_layer_map_3d2d.md` + r2_bringup nav2 三件套
  （nav2.launch.py/nav2.rviz/nav2_params.yaml），与本次无关，待单独提交
