# explore_lite 参数声明假阴性：P1 复核与根因定位

> 日期：2026-11-07（复测 20:10；原结论产生于同日 12:53 冒烟）
> 任务：裁定「`return_to_init` 是否存在 / 另 7 项参数是否未声明」的文档结论真伪
> 状态：✅ 已结案（上游正确、本地文档错误；文档已按翻案留痕订正）
> 关联：[explore-plan §3.1.3](../minimal-loop2/explore-plan.md)｜[s1-readiness-gap G3](../old-car/s1-readiness-gap.md)｜[survey §2.3 复测结果](../surveys/exploration-prior-map-survey.md)
> 证据落位：`doc/raw_data/raw_explore_p1_retest_n97_2026-11-07_2010.txt`（本地，不入 git）；
> 前序 `doc/raw_data/raw_explore_smoke_n97_2026-11-07_1253.txt`
> 机器：N97（lin-Default-string / 192.168.1.210），commit `326cf8a`

---

## 〇、事件全景（一眼看懂）

### 0.1 时间线

| 时刻 | 事件 | 结果 |
|:---|:---|:---|
| 11-07 12:53 | 首次冒烟：裸环境起 explore_lite + `param list` | 9 项、无 `return_to_init` → 据此记为"未声明"（**错误**） |
| 11-07 13:21 | 另一 session 产出 [survey](../surveys/exploration-prior-map-survey.md)，核上游源码后判 P1 冲突 | 指出上游 `explore.cpp:65-72` 有 8 个 `declare_parameter` |
| 11-07 下午 | 用户指令：**先在 N97 做 P1 干净复测，确认后再改文档**（改文档只增不删、先给 diff） | 定下"先证伪、后落笔"的顺序 |
| 11-07 傍晚 | N97 关机，复测暂停 | — |
| 11-07 ~19:50 | N97 开机，复测开始 | — |
| 11-07 20:05 | A/B 两腿跑完，`param get` 与 YAML 全对账 | 上游正确、本地文档错误 |
| 11-07 20:10 | 原始输出落盘 | `raw_data/raw_explore_p1_retest_n97_2026-11-07_2010.txt` |
| 11-07 20:30+ | 按翻案留痕订正 11 份文档 + 新建本篇 | 链接校验 1345 条全存在、致坏 0 |

### 0.2 构造链示意（根因一图）

```text
Explore::Explore()
  │
  ├─ 成员初始化列表（先执行）
  │    └─ costmap_client_(*this, &tf_buffer_)          ← explore.cpp:59
  │         └─ Costmap2DClient::Costmap2DClient()
  │              ├─ declare_parameter × 4              ← costmap_client.cpp:55-59
  │              ├─ 【阻塞①】while(!costmap_received_)  ← costmap_client.cpp:89   无超时
  │              └─ 【阻塞②】while(等 map→base_link TF) ← costmap_client.cpp:118+ 无超时
  │
  └─ 构造函数体（①②都通过后才轮到这里）
       ├─ declare_parameter × 8（含 return_to_init）   ← explore.cpp:65-72
       ├─ get_parameter × 8                            ← explore.cpp:74-81
       └─ 【阻塞③】move_base_client_->wait_for_action_server()  ← explore.cpp:112
            └─ 无超时且不 spin ⇒ 参数服务不响应 ⇒ param list 报异常 / param get 挂死
```

**一句话**：`param list` 缺的不是"参数不存在"，是"声明那段代码还没轮到执行"。

---

## 一、结论先行

1. 上游 `326cf8a` 的 `explore.cpp:65-72` **确实** `declare_parameter` 8 项（含 `return_to_init`），
   `explore.cpp:74-81` 用 `get_parameter` 读取。**本地文档的「不存在 / 未声明」结论错误。**
2. 12:53 冒烟不是"随机异常"，是**结构性假阴性**：节点构造函数有三段串行阻塞，当时只有雷达、
   没有 Nav2，参数声明代码**根本没被执行到**。
3. 因此另一 session 给的复测步骤（只起节点 + `param list`）**不足以下结论**——照跑会得到同样的
   5 项，并被误读成"上游说法不成立"。必须补三件套：costmap + TF + action server。
4. 这是本项目**第一次遇到"被观测对象尚未完成初始化"这一类假阴性**；既往假阴性都在
   "观测工具自身"这一侧（`hz` 的 QoS 限制、记录器崩、判据写错，见 ros2-ops §5）。两类要分开归因。

---

## 二、完整思路链（从矛盾到定论）

### 2.1 起点：矛盾是什么

另一 session 核对上游源码，指出 `explore.cpp:65-72` 是 `declare_parameter` 8 项；
而本仓三处文档称「`return_to_init` 不存在」「另 7 项未声明，代码用 `get_parameter_or`」。
两者不可能同时为真 → 必须裁定。

它同时给了三个候选解释（同名残留节点 / overlay 串台 / daemon 缓存）和一套复测步骤。
**这三个假设后来全部被证伪**，但它们把排查方向限定在"环境串台"，这是第一个需要跳出的框。

**三个候选解释的排除证据**（否定证据与肯定证据同等重要，一并留档）：

| # | 候选解释 | 排除证据 | 结论 |
|:--:|:---|:---|:---|
| H1 | 同名残留节点（另一个 explore 也在跑，读数张冠李戴） | `ros2 node list` 只有 `/explore_node` + 一个 `transform_listener_impl_*`（后者是 tf 监听器自动生成的节点）；`pgrep` 无双实例 | ❌ 不成立 |
| H2 | overlay / install 串台（source 了错的工作区，跑的是旧二进制） | A 腿已显式 `source ~/Lin_workspace/explore_ws/install/setup.bash`；`ros2 pkg prefix explore_lite` 指向该工作区 | ❌ 不成立 |
| H3 | daemon 缓存（CLI 记着旧拓扑） | 复测前已 `ros2 daemon stop`；现象不变 | ❌ 不成立 |

**为什么三个假设会全错**：它们都在回答"**我们是不是连错了节点 / 连到了旧世界**"，
而真实原因是"**节点就在那儿，只是它还没走到声明那一步**"——问题出在对象的时间维度，
不在环境的空间维度。这是本次最值得记住的一次"框错了方向"：假设越多越具体，
越容易让人以为排查面已经铺开，实际却全挤在同一个维度里。

### 2.2 第一层排查：先看自己的原始数据

重读 `raw_explore_smoke_n97_2026-11-07_1253.txt`，注意到两个细节：

- 终端 2 只 `source /opt/ros/humble/setup.bash`，**没有** source explore_ws。
  这会影响 CLI 找到包，但 `param list` 是通过 DDS 问活节点，理论上不受影响 → 不是主因，但记为混杂因素。
- 节点日志全程只有一行：`Waiting for costmap to become available, topic: /global_costmap/costmap`。

**关键判断**：这行日志是"卡住"的指纹，不是"正常启动"的指纹。把注意力从"环境串台"转到
"节点当时处于什么状态"。

### 2.3 第二层排查：读源码定初始化顺序（只读，不改）

到 N97 上 grep/sed 读 `explore.cpp` / `explore.h` / `costmap_client.cpp`，得到三段事实：

```cpp
// explore.cpp:54-63
Explore::Explore()
  : Node("explore_node")
  , ...
  , costmap_client_(*this, &tf_buffer_)   // ← 成员初始化列表：先于构造函数体执行
  , ...
{
  // 构造函数体
  this->declare_parameter<float>("planner_frequency", 1.0);   // L65
  ... 8 项，含 return_to_init                                    // L72
```

```cpp
// costmap_client.cpp:86-93（这是 costmap_client_ 自己的构造函数）
RCLCPP_INFO(..., "Waiting for costmap to become available, topic: %s", ...);
while (!costmap_received_) {
  rclcpp::spin_some(node_.get_node_base_interface());
  usleep(1000000);            // 无超时
}
```

**推理**：C++ 成员初始化列表在构造函数体之前执行 → `Costmap2DClient` 构造函数先跑 →
它卡在 while 里 → `Explore` 构造函数体（含 8 个 declare）**永远等不到**。

这正好解释观测：`param list` 只有 costmap_client 自己声明的 4 项
（`costmap_topic` / `costmap_updates_topic` / `robot_base_frame` / `transform_tolerance`）
+ `use_sim_time`（Node 基类自动声明）+ `qos_overrides`×4。**一项不多、一项不少。**

到这里，假阴性的机制已经在纸面成立；但按 ros2-ops §5.1「机制核查双钉法」，
源码链只算一条证据链，必须再有行为侧独立观测才能钉死。

### 2.4 第三层：设计能证伪的复测（而不是重跑原步骤）

原步骤的问题：它只复现"没有 costmap"的状态，必然再得 5 项。
**如果照着跑，会得到与假设一致的错误结论**——这是最危险的一步。

因此改成**同进程 A/B 对照 + 逐层解锁**：

| 阶段 | 操作 | 预期（若假设成立） |
|:---|:---|:---|
| A | 只起节点 | 9 项，无 `return_to_init`（= 复现原现象） |
| ① | 发一条 costmap | 节点日志前进到 TF 等待 |
| ② | 发静态 TF `map→base_link` | 节点日志前进到 `Waiting to connect to move_base nav2 server` |
| ③ | 起假 `NavigateToPose` action server | 构造函数完成、节点开始 spin → `param list` 出现 8 项 |

每一层都对应一个阻塞点，**任何一层不前进都足以推翻假设**。

### 2.5 执行中的两个意外与处置

**意外 1：`ros2 topic pub --once` 没生效。**
第一发之后节点毫无反应。判断为 DDS 发现竞态：`--once` 在 discovery 完成前就发完并退出，
volatile QoS 下消息直接丢弃。改为 `-r 1` 连续发 20 秒后立刻生效。
（这一条独立于 P1，是个可复用的操作坑。）

**意外 2：解锁到 ③ 之前，`param list` 报 `Exception while calling service ... None`，
`param get` 直接挂死。**
原因不是节点死了，而是节点阻塞在 `explore.cpp:112` 的
`move_base_client_->wait_for_action_server()`（无超时）——**不 spin，参数服务就不响应**。
此时参数其实已经声明，只是问不出来。补假 action server 后立即恢复正常。

### 2.6 定论与取证

B 腿结果：`param list` 17 项，8 项全部出现；`param get` 取值与 `params_costmap.yaml` 一致：

```text
return_to_init     → False
planner_frequency  → 0.15
visualize          → True
potential_scale    → 3.0
```

**两条证据链交叉闭环**：源码链（declare 位置 + 初始化顺序）+ 行为链（A/B 跳变）。
按 ros2-ops §5.1，这才算钉死。

### 2.7 收尾

- 清理：kill 三个测试进程（explore / static_transform_publisher / 假 action server），
  `ps -p` 复核"全部已退出"，`ros2 daemon stop`。
- 文档：按 [doc-engineering §十](../doc-engineering.md) 翻案留痕订正
  （原文保留 + 订正块 + 互指），不静默改写。

### 2.8 反事实：如果当时没查（这次错误本来会付出什么）

不是"记错一个参数"这么轻。如果照 12:53 的结论走下去：

- `explore_params.yaml` 里那 8 项会被当成"写了也不生效"的无效配置，**甚至被删掉**；
- 实跑时 `planner_frequency` 取代码默认值 **1.0**，而不是 YAML 里的 **0.15**——7× 的计算量；
- 而 N97 恰好是 **CPU 受限**平台（[07-handover §三](../07-handover.md)："CPU 余量优先于功能扩展"），
  这个错误会以"探索时机器卡、帧率掉"的面目出现，被归因到别处（历史先例：
  [08-11 KISS 3.6Hz](2026-08-11_kiss_frame_rate_fix.md) 的 powersave 误判）；
- 更贵的是：我们会带着"上游文档不实"的印象，继续在错误前提上做 S1 验收。

**所以这次复测的价值不在"改对几行字"，而在拦住了一条会把算力和排障时间一起烧掉的错误前提。**

---

## 三、工具与操作全清单（本次实际用到）

> 用途分类：①定位 ②读证 ③改环境 ④观测 ⑤清理。全部命令均可在同类问题复用。

| # | 工具/命令 | 用途 | 本次具体用法与结果 |
|:--:|:---|:--:|:---|
| 1 | `find -mmin -2880` + `ls -lt` | ① | 在 doc/ 里按修改时间定位"另一 session 的产出"→ `doc/surveys/exploration-prior-map-survey.md`（13:21） |
| 2 | `git status --short` / `git log --oneline` | ① | 确认工作区 WIP、最近提交、未跟踪文件，划定改动边界 |
| 3 | `grep -n '^#\{1,4\} '` | ① | 取 survey 标题结构，直接跳到 §2.3 P1 |
| 4 | `grep -n 'P1\|冲突\|矛盾\|推翻'` | ① | 一次性捞出所有冲突相关行，避免通读 4.5 万字 |
| 5 | Read（分页 offset/limit） | ② | 精读 §〇 结论表、§2.3、附录 A，只读需要段落 |
| 6 | `cat doc/raw_data/...smoke...txt` | ② | 重读 12:53 原始输出——发现"只 source humble"与"日志只有等待行"两个线索 |
| 7 | `ping -c 2` + `ssh -o ConnectTimeout=8` | ①⑤ | 确认 N97 可达/关机、建立只读通道 |
| 8 | `ip route` | ① | 本机路由（排查是否本机网络问题） |
| 9 | `ssh ... grep -n` | ② | 在 N97 源码里定位 `declare_parameter` / `Waiting for costmap` / `wait_for_action_server` |
| 10 | `ssh ... sed -n 'a,bp'` | ② | 读构造函数初始化列表、阻塞循环上下文 |
| 11 | `ssh ... ros2 daemon stop` | ③ | 排除 CLI 缓存（另一 session 假设之一），本次证明与故障无关 |
| 12 | `setsid nohup <cmd> > /tmp/x.log 2>&1 < /dev/null &` | ③ | SSH 会话结束后仍存活地起测试进程；日志落 /tmp 便于 `tail` |
| 13 | `ros2 run explore_lite explore --ros-args --params-file ...` | ③ | 起被测节点（官方 launch 写死 params.yaml，不可用） |
| 14 | `ros2 node list` | ④ | 确认节点已出现在图中（说明 Node 基类已构造） |
| 15 | `ros2 param list <node>` | ④ | **核心观测量**：A 腿 9 项 / B 腿 17 项 |
| 16 | `ros2 param get <node> <param>` | ④ | **核心判据**：取值与 YAML 对账 |
| 17 | `ros2 topic pub --once` | ③ | 首次尝试注入 costmap —— **失败**（发现竞态） |
| 18 | `ros2 topic pub -r 1` + `timeout 20` | ③ | 改连续发布后成功注入 |
| 19 | `ros2 run tf2_ros static_transform_publisher --x..--child-frame-id` | ③ | 伪造 `map→base_link`，解锁阻塞点② |
| 20 | `python3 -c "..."`（rclpy `ActionServer` + `nav2_msgs/NavigateToPose`） | ③ | 内联假 action server，解锁阻塞点③；不落文件、跑完即弃 |
| 21 | `tail -n` 日志 | ④ | 按日志行判断"走到第几个阻塞点"（最有信息量的观测量） |
| 22 | `pgrep -af` / `pgrep -f` | ⑤ | 起进程前查残留、获取 PID 列表 |
| 23 | `ps -p <pid列表>` | ⑤ | kill 后复核，输出"全部已退出" |
| 24 | `kill -TERM <显式 PID>` | ⑤ | **按 PID 杀**，不用宽泛 `pkill -f`（避免自匹配，见 ros2-ops §10） |
| 25 | `date '+%Y-%m-%d %H:%M'` | — | 原始数据文件命名时间戳 |
| 26 | Write / Edit | — | 原始数据落盘、文档订正、本复盘 |

**未使用**：WebSearch / WebFetch。事实源全部来自 N97 本机源码与实测（本地优先，
符合全局"信息检索：本地知识库优先"），无需外搜。

**一度失败/走弯路的操作（留档以免重蹈）**：
- `ros2 topic pub --once`（#17）→ 改 `-r 1`；
- 在节点未解锁时执行 `param list`/`param get`（#15/#16）→ 报异常/挂死，误以为节点崩溃；
- 差点按另一 session 的步骤直接重跑（那会得到同样的假阴性）。

---

## 四、方法模板（可复用操作卡）

### 卡① 构造期阻塞型假阴性排查（六步）

> 适用：**源码明明有声明/发布，但运行时 `param list` / `topic list` 看不到**。

1. **先读源码定位置**：确认目标调用（`declare_parameter` / `create_publisher` 等）写在哪个函数。
2. **查初始化链**：若是类构造函数体，检查该类的**成员初始化列表**里有没有对象先构造。
3. **找阻塞点**：沿链 grep `while (` / `wait_for_` / `sleep` / `spin_some`，列出全部无超时等待。
4. **逐层解锁**：从最外层依赖开始，每补一项看日志是否前进一步；不前进 = 假设有误。
5. **全解锁后再观测**：此时读数才有效，与源码逐条对账（本例 8 项全中）。
6. **双链闭环**：源码链 + 行为链都要有；只有一条不算钉死（ros2-ops §5.1）。

### 卡② 同进程 A/B 观测法

> 适用：怀疑"某状态导致观测缺失"，但拿不准是环境还是对象本身。

- 在**同一个进程生命周期内**先取基线 A，注入一个变量后取 B；
- 不跨进程/跨次运行对比——环境变量、overlay、daemon、残留进程都可能变；
- A→B 出现**跳变**即因果；A、B 相同则假设不成立，回头改假设而不是改结论。

### 卡③ 伪造依赖件解锁法（ROS2 版）

| 依赖件 | 最小伪造手段 | 注意 |
|:---|:---|:---|
| 话题输入 | `ros2 topic pub -r 1 <topic> <type> "{...}"` | **`--once` 有发现竞态**，对已在等待的订阅者不可靠 |
| 静态 TF | `ros2 run tf2_ros static_transform_publisher ...` | 命名参数式（`--frame-id/--child-frame-id`） |
| Action server | `python3 -c` 内联 rclpy `ActionServer` + `spin` | 不落文件、跑完即弃；本例用 `nav2_msgs/action/NavigateToPose` |

纪律：全部临时进程，结束后按 PID kill + `ps -p` 复核（进程卫生，ros2-ops §10）。

### 卡④ 复测方案本身要先评审

> 适用：别人（或上一轮的自己）给了一套"复测步骤"，准备照跑之前。

先问：**这套步骤能否区分"假设成立"与"假设不成立"？**
若无论真相如何都会得到同一个结果（本例：只起节点必得 5 项），则它**不是复测，只是重放**。
补足能产生分叉的条件（本例：三件套）后再跑。

---

## 五、经验点层次标注

> 每条标建议去向：draft = [analysis-methods.md](../analysis-methods.md)；规则层 = ros2-ops / ros2-qos-dds / standards / doc-engineering；事件层 = 本档留存。
> 按四层制（[2026-09-04 决策档](2026-09-04_experience-layer-decision.md)）：**单事件新经验先落 draft**，不直写规则层。

| 编号 | 经验点 | 类型 | 建议去向 | 备注 |
|:---|:---|:---|:---|:---|
| E1 | 构造期阻塞导致参数声明未执行 → `param list` 缺项是假阴性，不是"参数不存在" | 方法 | **draft：主题 M** | 本次核心 |
| E2 | 假阴性归因三分法：观测工具侧 / 观测时机侧（对象未就绪）/ 事实侧 | 方法 | **draft：主题 M** | 与既有 ros2-ops §5「空结果先自查观测链」互补，其只覆盖工具侧 |
| E3 | 同进程 A/B 观测定因（卡②） | 方法 | **draft：主题 M** | 与 analysis-methods L3「控制变量对照」同族，成熟后可并入 ros2-ops §7 |
| E4 | 伪造依赖件三件套解锁（卡③） | 方法 | **draft：主题 M** | 复用潜力高 |
| E5 | `ros2 topic pub --once` 在 DDS 发现完成前会丢消息（volatile）；对已等待的订阅者用 `-r 1` | 工具坑 | **draft：主题 M**（成熟后 candidate → ros2-qos-dds §三） | 单事件，暂不直写规则层 |
| E6 | 复测方案本身要先评审"能否证伪"（卡④） | 方法 | **draft：主题 M** | 与"排障纪律"同源 |
| E7 | 别人给的根因假设要独立证伪，不因"看起来合理"而采信 | 纪律 | **draft：主题 M** | 本例三个假设全错 |
| E8 | 翻案留痕三件套（原文保留 + 订正块 + 互指）本次执行顺利 | 流程 | **事件层留存** | 已有规则 doc-engineering §十，无需重复 |
| E9 | 测试进程按 PID kill + `ps -p` 复核 | 纪律 | **事件层留存** | 已有规则 ros2-ops §10 |

---

## 六、遗留

- `explore_params.yaml` 已放开 `return_to_init: false`，但**尚未随三份配置做过联合起跑**——
  该项归 S1 首跑验收（[s1-readiness-gap](../old-car/s1-readiness-gap.md)）。
- 裸环境无法验证参数的结论已写入 [explore-plan §3.1.3](../minimal-loop2/explore-plan.md)；
  首跑时须在 slam_toolbox + Nav2 起齐后再做一次 `param get` 复核。

---

## 七、附录：可复现材料

> 目的：让后来者**不必登 N97、不必重跑**也能核对全部事实；需要重跑时照 7.2 逐条执行即可复现。

### 7.1 A/B 两腿参数全量对照（17 项逐条）

| # | 参数 | A 腿（裸环境） | B 腿（三件套齐） | 声明来源 |
|:--:|:---|:--:|:--:|:---|
| 1 | `costmap_topic` | ✅ | ✅ | `Costmap2DClient` 构造函数 `costmap_client.cpp:55` |
| 2 | `costmap_updates_topic` | ✅ | ✅ | 同上 `:56` |
| 3 | `robot_base_frame` | ✅ | ✅ | 同上 `:58` |
| 4 | `transform_tolerance` | ✅ | ✅ | 同上 `:59` |
| 5 | `use_sim_time` | ✅ | ✅ | `rclcpp::Node` 基类自动声明 |
| 6-9 | `qos_overrides./parameter_events.publisher.{depth,durability,history,reliability}` | ✅ ×4 | ✅ ×4 | `parameter_events` 发布者自动声明 |
| 10 | `planner_frequency` | ❌ | ✅ | `Explore` 构造函数体 `explore.cpp:65` |
| 11 | `progress_timeout` | ❌ | ✅ | 同上 `:66` |
| 12 | `visualize` | ❌ | ✅ | 同上 `:67` |
| 13 | `potential_scale` | ❌ | ✅ | 同上 `:68` |
| 14 | `orientation_scale` | ❌ | ✅ | 同上 `:69` |
| 15 | `gain_scale` | ❌ | ✅ | 同上 `:70` |
| 16 | `min_frontier_size` | ❌ | ✅ | 同上 `:71` |
| 17 | `return_to_init` | ❌ | ✅ | 同上 `:72` |

**9 → 17，增量恰好是 `Explore` 构造函数体的那 8 项，一项不多一项不少**——这就是"卡点精确落在
初始化列表与构造函数体之间"的直接读数证据。

`param get` 实测取值（B 腿，与 `params_costmap.yaml` 对账）：

| 参数 | 实测 | YAML | 代码默认 | 一致 |
|:---|:---|:---|:---|:--:|
| `return_to_init` | False | false | false | ✅ |
| `planner_frequency` | 0.15 | 0.15 | 1.0 | ✅ |
| `visualize` | True | true | false | ✅ |
| `potential_scale` | 3.0 | 3.0 | 1e-3 | ✅ |

> 后两项最能说明问题：**实测值等于 YAML 值、且都不同于代码默认值** ⇒ 参数不仅"存在"，
> 而且"真的从 YAML 读进去了"。只核"存在"不够，取值对账才排除了"声明了但没生效"。

### 7.2 可复现命令清单（N97，copy-paste）

> 说明：下面是实际命令的**补全版**——原始记录中 costmap 的 `data` 段简写为 `16×0`、
> action server 段简写为 `...`。逐字复跑以本清单为准。

```bash
############ N97 ############
# 0) 环境：只 source 目标工作区（排除 overlay 干扰 = 排除 H2）
source /opt/ros/humble/setup.bash
source ~/Lin_workspace/explore_ws/install/setup.bash
ros2 daemon stop                          # 排除 CLI 缓存（排除 H3）

# 1) A 腿：只起节点（官方 launch 写死 params.yaml，故直接 run）
setsid nohup ros2 run explore_lite explore --ros-args \
  --params-file ~/Lin_workspace/explore_ws/install/explore_lite/share/explore_lite/config/params_costmap.yaml \
  > /tmp/p1_A.log 2>&1 < /dev/null &
sleep 3
tail -n 5 /tmp/p1_A.log                   # 预期：停在 "Waiting for costmap to become available"
ros2 param list /explore_node             # 预期：9 项，无 return_to_init ← 复现原现象

# 2) 解锁①：连续发 costmap（关键：-r 1，--once 会被 DDS 发现竞态吞掉）
timeout 20 ros2 topic pub -r 1 /global_costmap/costmap nav_msgs/msg/OccupancyGrid \
  "{header: {frame_id: map}, info: {resolution: 0.05, width: 4, height: 4, origin: {position: {x: -0.1, y: -0.1}}}, data: [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]}"
# 预期：/tmp/p1_A.log 出现 "Timed out waiting for transform from base_link to map ..."（每 5s 重复）

# 3) 解锁②：静态 TF
setsid nohup ros2 run tf2_ros static_transform_publisher --x 0 --y 0 --z 0 \
  --yaw 0 --pitch 0 --roll 0 --frame-id map --child-frame-id base_link \
  > /tmp/p1_tf.log 2>&1 < /dev/null &
sleep 2
# 预期：/tmp/p1_A.log 出现 "Waiting to connect to move_base nav2 server"
#       （该行在 8 个 declare 之后 ⇒ 声明代码已执行；此时 param list 仍会报异常/挂死，属正常）

# 4) 解锁③：假 NavigateToPose action server
setsid nohup python3 -c '
import rclpy
from rclpy.action import ActionServer
from nav2_msgs.action import NavigateToPose
rclpy.init()
n = rclpy.create_node("fake_nav2")
def cb(goal_handle):
    goal_handle.succeed()
    return NavigateToPose.Result()
srv = ActionServer(n, NavigateToPose, "navigate_to_pose", cb)
rclpy.spin(n)
' > /tmp/p1_as.log 2>&1 < /dev/null &
sleep 3
tail -n 5 /tmp/p1_A.log                   # 预期："No frontiers found, stopping." / "Exploration stopped."
ros2 param list /explore_node             # 预期：17 项，含 return_to_init
ros2 param get /explore_node return_to_init   # 预期：Boolean value is: False

# 5) 清理（按 PID；不要用 pkill -f 宽泛匹配，见 ros2-ops §10）
pgrep -af 'explore_lite|static_transform_publisher|fake_nav2'
kill -TERM <PID1> <PID2> <PID3>
ps -p <PID1>,<PID2>,<PID3>                # 预期：全部已退出
ros2 daemon stop
```

**失败模式对照**（照跑时最容易卡在哪）：

| 现象 | 原因 | 处置 |
|:---|:---|:---|
| 发 `--once` 后节点毫无反应 | DDS 发现未完成 + volatile，消息被丢 | 改 `-r 1` 连续发 |
| `param list` 报 `Exception while calling service ... None` | 节点阻塞在③、不 spin，参数服务不响应 | **不是崩溃**，补 action server 即恢复 |
| `param get` 挂死到超时 | 同上 | 同上；服务端日志会写 `failed to send response ... (timeout)` |
| 报 TF `Invalid frame ID "map"` | 静态 TF 还没起 | 先做第 3 步 |

### 7.3 源码摘录（判定依据，N97 实机 `326cf8a`）

```cpp
// ── explore.h ──
120:  Costmap2DClient costmap_client_;                 // ← 成员对象

// ── explore.cpp:54-72 ──
54: Explore::Explore()
55:   : Node("explore_node")
56:   , logger_(this->get_logger())
57:   , tf_buffer_(this->get_clock())
58:   , tf_listener_(tf_buffer_)
59:   , costmap_client_(*this, &tf_buffer_)          // ← 成员初始化：先于构造函数体
...
65:   this->declare_parameter<float>("planner_frequency", 1.0);
66:   this->declare_parameter<float>("progress_timeout", 30.0);
67:   this->declare_parameter<bool> ("visualize", false);
68:   this->declare_parameter<float>("potential_scale", 1e-3);
69:   this->declare_parameter<float>("orientation_scale", 0.0);
70:   this->declare_parameter<float>("gain_scale", 1.0);
71:   this->declare_parameter<float>("min_frontier_size", 0.5);
72:   this->declare_parameter<bool> ("return_to_init", false);
74-81: this->get_parameter(...) 逐项读取上述 8 项
111:  RCLCPP_INFO(logger_, "Waiting to connect to move_base nav2 server");
112:  move_base_client_->wait_for_action_server();   // ← 阻塞③：无超时、不 spin

// ── costmap_client.cpp（Costmap2DClient 自己的构造函数）──
55-59: declare_parameter costmap_topic / costmap_updates_topic /
       robot_base_frame / transform_tolerance                      // 共 4 项
69-72: create_subscription<nav_msgs::msg::OccupancyGrid>(costmap_topic, 1000, ...)
       // 默认 QoS：reliable / volatile / keep_last 1000
86-88: RCLCPP_INFO "Waiting for costmap to become available, topic: %s"
89-93: while (!costmap_received_) { spin_some(...); usleep(1000000); }   // ← 阻塞①：无超时
118+:  while (...) 等 map→base_link TF                                    // ← 阻塞②：无超时
```

> 行号以 N97 实机 `326cf8a` 为准；`118+` 为 grep 定位到的段落起点（未逐行摘录）。
> 关键不是具体行号，而是**三类事实**：① 声明在构造函数体里；② 构造函数体的前置成员会阻塞；
> ③ 构造函数体内部还有一个不 spin 的等待。

---

## 八、一页纸快速诊断卡

> 适用：源码里明明有 `declare_parameter` / `create_publisher`，运行时 `param list` / `topic list` 却看不到。

```text
观测缺失（param list 少项 / topic 没人发）
│
├─ ① 节点在 ros2 node list 里吗？
│    └─ 否 → 节点根本没起来：查 launch.log / 包路径 / 崩溃栈。到此为止。
│
└─ 是 → ② 节点日志**最后一行**是什么？
     │
     ├─ 停在某个 "Waiting for ..." / "Timed out waiting for ..."
     │    └─ 【观测时机侧】对象在等依赖。列出该等待项，逐层伪造（卡③）：
     │         话题 → static TF → action server → 其它
     │       每补一项看日志是否前进；不前进 = 假设错，改假设。
     │
     └─ 日志看起来正常 / 无等待行
          │
          ├─ ③ 目标代码写在哪个函数里？
          │    └─ 构造函数体 → 查**成员初始化列表**：有没有更早构造的重对象？
          │         （典型：Costmap2DClient / TF listener / 同步器）
          │         有 → 去读那个成员的构造函数，找 while/wait_for_/sleep
          │
          └─ ④ 以上都排除，且全解锁后仍缺 → 才接受【事实侧】"确实没有"
```

**三个"不要"**（本次踩过或差点踩的）：

1. **不要把"服务调用挂死/报异常"当成"节点死了"**——可能是它还活着、只是没 spin；
2. **不要用 `--once` 给已在等待的订阅者喂消息**——用 `-r 1`；
3. **不要照跑别人给的复测步骤**——先问它能否区分"假设成立"与"不成立"（卡④），
   否则只是把同一个假阴性重放一遍，还多了一份"复测过"的虚假信心。

**一句话定律**：

> `param list` 少项 ≠ 参数不存在。先问"声明那行代码，跑到过没有？"

