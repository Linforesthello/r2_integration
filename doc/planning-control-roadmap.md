# R2 规划控制与视觉集成路线（08-18 调研）

> 状态：调研结论定稿（2026-08-18）；来源 = 官方仓库/README + WebSearch 社区核实，未实测项标注
> 定位：01-plan 第四章（集成路线图）的补充引用，视觉/规划控制的选型依据
> 关联：[01-plan.md](01-plan.md)｜[fastlio2-n97-deploy.md](fastlio2-n97-deploy.md)（FAST-LIO2 部署）

---

## 一、视觉-雷达标定工具线（hku-mars + 第三方）与集成时机

### 1.1 工具线

| 工具 | 特点 | 限制（对 R2 关键） |
|:---|:---|:---|
| [livox_camera_calib](https://github.com/hku-mars/livox_camera_calib)（hku-mars 官方主推） | targetless 无标定板，场景边缘自动标定，像素级精度，多场景联合更稳；官方示例 Avia + D435i | 核心是"高分辨率点云边缘提取"——**VLP-16 16 线稀疏，边缘质量存疑**；⚠️ ROS1（Kinetic/Melodic） |
| [joint-lidar-camera-calib](https://github.com/hku-mars/joint-lidar-camera-calib)（IROS 2023） | 内参+外参联合标定（平面约束 BA），0.12°/2.44cm，支持机械式 | 需纹理平面场景 + 初始外参（<5°/<0.5m）；⚠️ ROS1 catkin |
| [FAST-Calib](https://github.com/hku-mars/FAST-Calib) | 1s 快速标定，无需初值 | 需定制圆形孔标定板 |
| [direct_visual_lidar_calibration](https://github.com/koide3/direct_visual_lidar_calibration)（koide3，第三方） | 全型号雷达（机械式友好），SLAM 稠密点云 + 视觉配准 | 需相机内参先验（D435 出厂标定自带 ✅） |

### 1.2 关键判断（D435 是 RGB-D）

- D435 内参 + RGB-depth 外参**出厂已标好**，缺的只是 **lidar-camera 外参**
- VLP-16 稀疏点云不是 hku-mars 工具的主场（为高分辨率 Livox 设计）：
  - VLP-16 + D435 标定 → 走 koide3 路线（机械雷达友好）
  - MID-70 + D435 标定 → livox_camera_calib 对口组合（官方示例同类）

### 1.3 集成时机（Phase 4 前置，不阻塞当前主线）

```
Phase 3 收尾（全速验证 + 避障实测）→ FAST-LIO2 决策
        ↓
   [现在不必做] 标定属于 Phase 4（D435+Jetson）前置任务：
   触发条件 = 视觉有明确用途：彩色点云建图（R3LIVE 式演示）/
            目标检测动态避障（Robocon 人形障碍）/ 任务对接
   成本认知：hku-mars 标定工具全 ROS1，N97 是 Humble——
            需容器或 ROS2 移植，不是一个晚上的成本
```

规划控制主线（§二）纯激光即可闭环，**视觉不阻塞它**——这就是"何时集成"的答案：
Phase 3 收尾后、进视觉前，做一次标定专项。

---

## 二、R2 分阶段规划控制方案（离线先验地图 vs 实时建图导航）

### 2.1 两大阵营对比

| 维度 | A. 离线先验地图导航 | B. 实时建图导航（探索） |
|:---|:---|:---|
| 地图 | 录 bag 离线建图 → 存文件 → 加载（KISS 现有 / FAST-LIO2 升级） | 运行中实时建（2D: SLAM Toolbox / 3D: FAST-LIO2 ikd-Tree） |
| 定位 | AMCL 2D（现有闭环）→ 升级 FAST-LIO-Localization 3D 重定位 | 无需独立定位：里程计即地图系（代价：无回环，长距离累积漂移） |
| 规划 | Nav2 全套（全局 NavFn/Smac + 局部 MPPI 现有） | Nav2 + frontier 探索循环 |
| 探索实现 | — | [explore_lite](https://github.com/robo-friends/m-explore-ros2)（ROS2 移植最成熟：前沿检测+黑名单+NavigateToPose 循环，有 RPi5 嵌入式基准）；备选 [frontier_exploration](https://github.com/adrian-soch/frontier_exploration) |
| 适用场景 | 比赛场地已知（**Robocon 主场景 ✅ 当前路线正确**） | 未知/临时场地、场地变更、搜救 |
| 资源成本 | 低（AMCL+Nav2，已跑通） | 高（SLAM+Nav2 同跑；N97 CPU 瓶颈下 3D 方案尤其吃力——[基准论文结论：轻量 2D SLAM 远优于 3D 于嵌入式](https://xplorestaging.ieee.org/document/11365146)） |

### 2.2 R2 分阶段落点

```
Phase 3（当前 25%）: A 阵营收尾 —— 全速验证（先同步膨胀参数 0.55→0.30）→ 避障实测 → 设位姿纪律
Phase 3+（决策点）:   FAST-LIO2 vs KISS 决策 → 若替代：建图质量升级（A 阵营地图源）；FAST-LIO-Localization 定位试验（可选）
Phase 3.5（探索，可插队）: B 阵营轻量版 —— SLAM Toolbox 2D + explore_lite（N97 可承受）；3D 探索（FAST-LIO2 实时地图）仅演示用
Phase 4（视觉）:     lidar-camera 标定 → 彩色点云 → 目标检测动态避障（为 Robocon 人形障碍）
Phase 5（编排）:     waypoint 任务队列（已有待办）+ 气动 + 异常处理
```

### 2.3 Robocon 视角决策

- 比赛场地是规则场地（已知）→ **A 阵营是主力，Phase 3 路线正确，继续收尾**
- B 阵营作为"场地临时变更/未知区"兜底，用 2D 轻量方案即可，不必上 3D 探索
- 视觉标定排 Phase 4 前置，不抢主线时间

---

## 三、传感器选型：VLP-16 vs MID-70（室内三方案对比，实机 A/B 定夺）

### 3.1 核心矛盾（08-18 用户实测反馈）

**VLP-16 16 线稀疏，近距小物体表现非常差**——比赛场地（室内）与实验室（室内）场景下是主要短板。
（原"全景优先 + MID-70 价值被 D435 覆盖"的判断已修正：D435 视场小/5m 内/依赖光照，
**替代不了主雷达的空间密度**——建图/里程计的数据源。）

### 3.2 两雷达特性对比（含易误判点）

| 维度 | VLP-16（现役） | MID-70（闲置） |
|:---|:---|:---|
| FOV | 360° 水平全景（16 线，±15° 垂直） | 70.4° 圆形视场（非全景，朝前安装才可用） |
| 总点率 | 300k/s（总量高，⚠️ **易误判为"更密"**） | 100k/s（总量低，但…） |
| 空间分布 | 集中在 16 条线带，层间 2° 空洞 | 视场内**均匀分布**、无层间空洞 → **有效空间密度远高** |
| 近距小物体 | 1~2 层命中、点稀少（室内柱子/细杆/物料块表现差） | 视场内多点命中（0.2° 级角分辨） |
| FAST-LIO 适配 | PointCloud2 分支（time 字段可用） | **Livox CustomMsg 原生**：每点时间戳、运动畸变处理更好（直击 KISS 旋转漂移痛点） |
| 集成状态 | 驱动/建图/FAST-LIO/Nav2 全跑通 | 无驱动、无集成（livox_ros_driver2 已在 FAST-LIO 工作区装好） |
| 物理成本 | 供电已验证紧张（08-15 供电不足教训） | 供电 + 网口 + 车顶空间 |

### 3.3 三方案对比（不预设结论，A/B 实测定夺）

| 方案 | 结构 | 优点 | 代价/风险 |
|:---|:---|:---|:---|
| **a. MID-70 换装主雷达** | MID-70 全职责（建图+里程计+避障），VLP-16 拆下 | 建图质量/近距细节最优；FAST-LIO 原生适配（每点时间戳） | 70° 非全景：室内避障需转向弥补；新集成工作量 |
| **b. 双雷达组合** | VLP-16 360° 喂 Nav2 避障 + MID-70 高密度喂 FAST-LIO（**各喂一个消费者，不同时跑两份 SLAM**） | 全景避障 + 高密度建图兼得 | 供电/网口/车顶空间；两链路都要维护；N97 CPU 需实测（两链非并行 SLAM，预估可承受） |
| **c. VLP-16 + D435 补近距** | VLP-16 主雷达 + D435 近距感知（原案） | 零新增雷达成本；D435 已在 Phase 4 计划内 | 近距仅 5m 内/依赖光照；**建图密度短板未解决** |

### 3.4 定夺方法（A/B 实机对比，FAST-LIO2 验证必做环节）

同一段室内场景（场地放柱子/物料块），VLP-16 vs MID-70 分别跑 FAST-LIO2：

1. **建图密度/细节**：同一场景视觉对比 + 点数统计
2. **小物体表现**：Nav2 底图是否检出柱子/物料块
3. **里程计质量**：旋转漂移对比（KISS 163° 教训基线）
4. **避障实测**：2D scan 表现

半天成本，数据定夺方案 a/b/c。触发点 = **FAST-LIO2 实车验证阶段**（见
[fastlio2-n97-deploy.md](fastlio2-n97-deploy.md) §六），不必等"质量不达标"才做。

---

## 四、ROS1/跨版本包 Docker 部署与通信协作

**核心区分：离线批处理 vs 在线融合**——hku-mars 标定工具（livox_camera_calib / joint-lidar-camera-calib /
FAST-Calib）都是**离线批处理**：容器里读 bag、输出 yaml，**无需与宿主机实时通信**，挂载数据卷即可。

| 方案 | 做法 | 适用 |
|:---|:---|:---|
| **离线容器**（首选） | `docker run -v <bag目录>:/data`，容器内跑标定，结果写挂载卷 | hku-mars 标定工具 ✅ |
| **--network=host + ros1_bridge** | 容器复用宿主网络栈；[ros1_bridge](https://github.com/ros2/ros1_bridge)（官方）双向话题/服务桥，`dynamic_bridge` 自动映射 | 在线 ROS1 节点 ↔ 宿主机 ROS2 |
| **现成一体镜像** | [Dsobh/Humble-Noetic](https://github.com/Dsobh/Humble-Noetic)（内置 bridge + conf.yaml 配话题）、[li9i/ros1_humble_bridge_template](https://github.com/li9i/ros1_humble_bridge_template)（自定义消息） | 不想自己搭 |

**坑（社区实测）**：
- [ros1_bridge /rosout 桥在 Humble 损坏](https://github.com/ros2/ros1_bridge/issues/391)（Log 消息无法映射）；不支持 actions；自定义消息需同工作区编译
- 容器间 DDS 走 UDP（共享内存不跨容器）——复用 R2 既有跨机 FASTRTPS 经验（N97↔VM，见 [ros2-ops.md](ros2-ops.md) §1）
- 容器访问硬件（如 D435）需 `--device` 或 `--privileged` 透传 USB

**R2 落地**：标定走"离线容器"（唯一刚需）；在线融合（R3LIVE/LVISAM 等 ROS1）在 N97 CPU 瓶颈下性价比低，
除非 FAST-LIO2 决策后有强动机，否则不引入。

---

## 相关

- [01-plan.md](01-plan.md)（集成计划总纲，第四章路线图）｜[fastlio2-n97-deploy.md](fastlio2-n97-deploy.md)（FAST-LIO2 部署手册）
