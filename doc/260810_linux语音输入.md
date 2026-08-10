# Vocalinux 本地语音输入系统调试总结

> 日期：2026-08-10
> 状态：**Vocalinux + whisper.cpp + small 模型 + 中文专业语料增强方案已基本跑通，进入优化阶段**
> 环境：VMware Ubuntu 22.04（glibc 2.35）、i7-12700H、32GB 内存
> 原始对话记录（ChatGPT）：[最后部署版本 · GLIBC版本问题解决方案](https://chatgpt.com/c/6a7982b5-0840-83ee-a734-08cc35d76cb5) · [GLIBC版本问题解决方案](https://chatgpt.com/c/6a7970f5-c918-83e8-b595-3395ccb60e9f)

---

## 一、项目背景与目标

目标不是普通语音输入，而是**面向机器人研发场景的本地 AI 语音输入系统**：

```text
语音 → Whisper.cpp 本地 ASR → 专业术语增强 → 文本输入 → LLM → 机器人开发辅助
```

即"语音 → 文字 → AI 理解 → 生成代码 / 方案"，应用场景：

- ROS2 开发、STM32 / CAN / FreeRTOS 调试
- SLAM / LiDAR / IMU 讨论、强化学习机器人
- 代码辅助、技术笔记快速记录

本质上已经接近未来机器人领域的人机交互入口。

---

## 二、选型与试错过程

### 1. 模型选型：tiny → small

| 模型 | 定位 | 中文 / 专业词表现 |
|:---|:---|:---|
| tiny（约 3900 万参数） | 英语、简短命令 | 中文差、专业词错误严重 |
| base | 日常中文输入 | 中 |
| **small（当前使用）** | 技术写作 | 高、长句稳定 |
| medium | 高质量 | 很高、速度慢 |

实测例子（tiny）：说 "ONNX MuJoCo APPO" → 输出 "嗯叉 木角 APP哦"，ROS、SLAM、ONNX 等专业词基本无法识别。切到 small 后中文准确率、长句稳定性、技术词汇表现明显提升。

机器配置（i7-12700H + 32GB）完全支持 small 甚至 medium，无需迁就性能降级。日常中文输入可用 base，技术写作用 small，高质量场景用 medium。

### 2. 开机自动启动退回 tiny（已解决）

现象：手动启动是 small，开机自动启动却变成 tiny，专业词识别下降、prompt 效果消失。

排查：`~/.config/vocalinux/config.json` 中 `"model_size": "small"` 配置正确，但程序实际运行的代码不在源码目录——同一项目存在 `~/vocalinux/vocalinux/src`、`build/lib`、`venv/site-packages` 多处副本（Vocalinux 不是直接运行源码），自动启动流程某处用默认值（tiny）覆盖了配置。

解决：**固定 ModelSize 强制启动使用 small**，比依赖 GUI 选择更可靠。这是本轮最重要修复。

---

## 三、主要报错与解决过程

### 1. AppImage 运行报 GLIBC_2.38 not found（已绕开）

报错：

```text
python3: /lib/x86_64-linux-gnu/libm.so.6: version 'GLIBC_2.38' not found
python3: /lib/x86_64-linux-gnu/libc.so.6: version 'GLIBC_2.38' not found
```

原因：Vocalinux AppImage 内嵌的 Python 是在 glibc ≥ 2.38 的系统上打包的；AppImage 虽自带 Python 但不带 glibc，仍依赖宿主系统 libc，而 Ubuntu 22.04 只有 glibc 2.35。

排查第一步是确认系统版本：`lsb_release -a` 看发行版，`ldd --version` 看 glibc 版本——本次为 Ubuntu 22.04 + glibc 2.35，低于 Vocalinux 要求的 2.38。

**明确禁止直接升级 glibc**（`sudo apt upgrade libc6` 或手动替换 libc.so.6）——升级失败会导致 bash 无法启动、apt 损坏、SSH 失效、系统无法启动；且环境里还有 ROS2 Humble / Docker，不值得冒险。

| 可选方案 | 说明 | 评价 |
|:---|:---|:---|
| 升级 Ubuntu 24.04 | 自带 glibc 2.39，直接可跑 | 适合普通软件 / AI 工具 |
| Docker 跑 ubuntu:24.04 | 容器内 glibc 满足要求，挂载后运行 | 机器人开发场景推荐 |
| 找 Vocalinux 旧版 | 针对 22.04 / glibc 2.35 编译的版本 | 看官方是否提供 |
| 解包 AppImage（`--appimage-extract`） | 内嵌 python 仍依赖系统 glibc | 大概率仍失败 |

Docker 具体操作：

```bash
docker run -it ubuntu:24.04          # 容器内 apt update && apt install python3，glibc 满足
docker run --rm -it -v ~/Downloads:/data ubuntu:24.04   # 挂载 Downloads 目录运行 AppImage
```

建议的隔离布局：22.04 保持 ROS2 Humble + VLP-16 + D435i + FAST-LIO + Nav2 不动，24.04 跑 Vocalinux + 新 AI 工具，两 VM 互不影响。

> 注：最终绕开了 AppImage（当前实际运行于 `~/vocalinux/vocalinux` 的 src / venv 环境），具体安装步骤未留档，待补充。

### 2. 中文输出繁体（已解决）

原因：Whisper 对中文只有 `zh` 一个语言类别，不区分 zh-CN 简体 / zh-TW 繁体，decoder 倾向按训练数据输出繁体。这与 Vocalinux 无关，是 Whisper decoder 的输出习惯。

解决：

- `language` 固定为 `zh`（不要用 auto——auto 会先做语言检测，再由 decoder 自行决定字符风格；固定 zh 减少一次判断）
- initial_prompt 增加提示：`以下是简体中文普通话，请使用简体中文输出。`（该方法已被 whisper.cpp 社区验证）

落地配置：

```json
{
  "speech_recognition": {
    "language": "zh",
    "initial_prompt": "以下是简体中文普通话，请使用简体中文输出。"
  }
}
```

### 3. Whisper initial_prompt 不生效 / 长 prompt 反而变差（已定位）

现象：短 prompt 有效，长 prompt 失效；UI 输入框颜色由紫变白，一度怀疑没保存。实际颜色变化只是 GTK 输入框的渲染状态变化，**不代表 Whisper 是否接收到**。当时使用的长 prompt 原文（反例，约 2000 字）：

```text
机器人领域专业词汇：ROS2, ROS, rclcpp, rclpy, Nav2, MoveIt2, TF2, SLAM, FAST-LIO2, LIO-SAM, KISS-ICP, VLP-16, Livox MID70, RealSense D435i, STM32, STM32F103, STM32H7, CAN, SocketCAN, FreeRTOS, PID, FOC, Jetson Nano, TensorRT, CUDA, YOLO, ONNX, MuJoCo, Isaac Sim, Isaac Lab, PPO, SAC, APPO, Ubuntu, Linux, Docker。输出简体中文。
```

排查结论：

- **代码调用链存在**：config_manager.py（读取）→ settings_dialog.py（UI 保存）→ main.py → recognition_manager.py（`if self.whispercpp_initial_prompt: model_kwargs["initial_prompt"] = ...`）。不是功能不存在，是"配置保存了但没生效"。
- **验证方法**：启动日志应出现 `whisper.cpp initial prompt: xxx`；当时日志只有 `Loading whisper.cpp 'small' model...` 没有该行 → 怀疑该版本配置未真正传给 pywhispercpp（当时未最终确认）。
- **关键坑：`whispercpp_no_context = true`** 会关闭"上一段识别结果作为上下文"，连续技术语音识别明显下降 → 应改为 `false`。注意 whisper.cpp 有两个机制：A. initial prompt（首次输入提示，影响解码先验）；B. context（上一段识别结果作为上下文）。当时配置把 B 关了，对连续技术语音影响明显。

为什么长 prompt 反而降低效果：Whisper 的 initial_prompt 是**解码上下文提示（decoder conditioning）**，不是词库/词典——它只影响 token 概率和解码路径，不能修改模型词库、不能强行纠正发音。堆几十个词（约 2000 字）会占满 context window、稀释音频信息，普通中文反而下降。

正确策略：**100 字以内（约 50~200 token）**，只放少量高频领域词 + 关键缩写；Ubuntu / Linux / Docker 这类普通词没必要放。

### 4. Push-to-talk 首尾丢字（用户习惯已绕过，代码优化未做）

现象：按住右 Alt 马上说话丢开头；说完马上松键丢结尾。

原因（录音链路）：

```text
按键 → 启动录音线程 → 麦克风流建立 → VAD 检测 → audio_buffer 累计 → Whisper 推理
```

- **开头丢字**：麦克风 stream 启动后前 200~500ms 不稳定（类似摄像头第一帧黑屏），前几十~几百 ms 音频丢失。时序上：按键 0ms → 麦克风启动 50ms → 音频流稳定 100ms → VAD 开始判断 200ms → buffer 开始积累 300ms，所以"按了就马上说"的 ROS2 会被吃掉。
- **结尾丢字**：`stop_sound_guard_ms` 会在停止时丢弃末尾 200ms 声音，若尾部音频还没进 buffer 就被丢掉。代码：

  ```python
  if stop_sound_guard_chunks > 0:
      discarded_chunks = self.audio_buffer[-stop_sound_guard_chunks:]
  ```

代码证据（recognition_manager.py）：`self.audio_buffer = []`、`_process_final_buffer()`、stop_sound_guard 丢弃逻辑；grep `pre_roll|buffer|warm` 确认 **Vocalinux 没有实现录音前置缓冲（pre-roll）**，只有 audio_buffer / silence_timeout / stop_sound_guard_ms。

相关配置现状：

```json
"silence_timeout": 2.0,
"stop_sound_guard_ms": 200,
"model_keepalive": { "enabled": true, "idle_timeout_seconds": 300 }
```

（model_keepalive 保持 small 模型不卸载，避免每次重新加载 465MB；此时慢的不是模型加载，而是音频链路启动。）

当前解决方式（用户习惯层）：

- 按键后等 **0.3~0.5 秒**再说话；
- 松键后停 **0.3 秒以上**再进行下一次输入（silence_timeout=2.0 提供兜底保护）。

软件优化方向（未实施，按收益排序）：

| 优化项 | 做法 | 收益 |
|:---|:---|:---|
| pre-roll buffer | `from collections import deque; audio_buffer = deque(maxlen=20)`，保留按键前约 2s 音频 | ★★★★★ |
| stop_sound_guard_ms | 200 → 500~800（Siri / ChatGPT Voice / 语音助手通常 300~800ms） | ★★★★ |
| silence_timeout | 保持 1.5~2.5s，**不要改小**（改 1s 会把 "ROS2 导航" 断成 "ROS2"） | — |
| 接 LLM system prompt | 语义纠错 | ★★★★★ |

**本质认识**：首尾丢字不是 Whisper 准不准的问题，而是语音 Agent 的核心工程问题——实时性。链路"人 → 语音输入 → 实时 ASR → 语义理解 → 机器人控制"中每一个环节都有实时性问题，这里调的是 ASR front-end（语音前端）。Siri、ChatGPT Voice、Windows Voice Access 等产品都会预留几十到几百 ms 的按键前后缓冲，属于行业标准做法。

### 5. "无法输出"类问题排查清单

排查完以上问题后的状态判断：快捷键、麦克风、Whisper 推理、文本注入四环节均正常，问题集中在 tiny 模型 + language=auto + Whisper 中文输出风格，不是安装问题。

- 中文完全不输出 → `arecord -l` 确认麦克风设备存在
- 有声音但输出空白 → VAD 过于敏感，调整 `vad_sensitivity`（Vocalinux 用 Silero VAD 控制语音检测）
- 输出乱码 → `echo $LANG` 应类似 `zh_CN.UTF-8`

### 6. 排障时间线（本轮试错顺序）

```text
AppImage 报 GLIBC_2.38 → 改源码方式部署
→ tiny 中文/专业词差 → 换 small（提升明显）
→ 开机自动退回 tiny → 固定 ModelSize（已解决）
→ 中文输出繁体 → language=zh + 简体 prompt（已解决）
→ initial_prompt 长 prompt 失效 → 缩到 100 字内、no_context 改 false（已定位）
→ Push-to-talk 首尾丢字 → 用户习惯 0.3~0.5s（已绕过），pre/post-roll 待改代码
```

---

## 四、落地配置（当前最佳）

### 1. Whisper 侧（~/.config/vocalinux/config.json）

```json
{
  "speech_recognition": {
    "engine": "whisper_cpp",
    "model_size": "small",
    "language": "zh",
    "temperature": 0,
    "whispercpp_no_context": false,
    "whispercpp_no_timestamps": true,
    "silence_timeout": 2.0,
    "stop_sound_guard_ms": 500,
    "model_keepalive": { "enabled": true, "idle_timeout_seconds": 300 },
    "whispercpp_initial_prompt": "机器人开发术语：ROS2，ROS，rclcpp，rclpy，Nav2，MoveIt2，TF2，SLAM，FAST-LIO2，LIO-SAM，KISS-ICP，VLP-16，Livox，RealSense，STM32，CAN，总线，FreeRTOS，PID，FOC，Jetson，TensorRT，CUDA，YOLO，ONNX，MuJoCo，Isaac，PPO，SAC。请输出简体中文。"
  }
}
```

要点：固定 small + 固定 zh + 简体提示词，三步解决"模型退回 tiny、繁体输出、专业词丢失"。

保守起步版本（若专业词 prompt 效果待验证，可先用最简简体提示）：

```json
{
  "speech_recognition": {
    "engine": "whisper_cpp",
    "model_size": "small",
    "language": "zh",
    "initial_prompt": "以下是简体中文技术交流内容，请使用简体中文输出。"
  }
}
```

### 2. Whisper prompt 与 LLM system prompt 的分工

两者解决不同问题，不要混在一起：

| | Whisper prompt | LLM system prompt |
|:---|:---|:---|
| 解决 | 声音 → 文字（听清、专业词保持） | 文字 → 理解 / 回答 |
| 放什么 | 少量领域词 + 输出风格 | 用户背景、技术栈、回答习惯 |

推荐 LLM system prompt：

```text
你是机器人领域技术助手。用户主要讨论：ROS2、STM32、CAN、FreeRTOS、SLAM、LiDAR、IMU、机器人控制、强化学习、边缘AI。
请：1. 保留专业名词英文缩写；2. 不要翻译 ROS、CAN、PID、CUDA 等技术名称；
3. 对模糊语音进行技术领域纠错；4. 优先按照机器人工程实践回答；5. 给出架构、代码、调试步骤和工程建议。
```

---

## 五、定位：与 VLA 的关系

本项目不是 VLA（Vision-Language-Action：视觉 + 语言 → 动作 token），而是：

```text
Audio + Language + Action = Speech-Language-Action
```

对比：

```text
VLA:    camera → vision encoder → language model → action head
本项目: microphone → Whisper → LLM → ROS action
```

举例理解：VLA 是机器人看到杯子、听到语言"拿起来"，直接映射为动作；本项目是语音"让机器人移动到桌子旁边" → 文本 → 生成 cmd_vel / Nav2 goal，动作由现有控制链路执行。

属于 **Voice Interface for Embodied AI（具身智能语音入口）**，是 VLA 的输入扩展方向——不是 VLA 本身，但可以成为 VLA 系统的一部分。

---

## 六、已完成清单

- ✅ Vocalinux 安装、whisper.cpp 运行
- ✅ 中文识别、small 模型固定（开机不再退回 tiny）
- ✅ Whisper initial_prompt 接入、机器人专业词增强
- ✅ 本地语音输入链路整体跑通（快捷键 → 录音 → 识别 → 文本注入）

---

## 七、后续方向（按收益排序）

1. **pre/post-roll buffer 优化**：改 recognition_manager.py 增加录音前置 / 后置缓冲（当前最值得做的代码改动）
2. **接 LLM 做语义纠错**：Whisper 管"声音 → 文字"，LLM 管"文字 → 理解"，两段式
3. **LLM 接 ROS2 工具调用 / 语音生成 ROS2 action**：说"让机器人移动到桌子旁边" → 生成 cmd_vel / Nav2 goal
4. **机器人专用知识库（RAG）**：比继续堆 Whisper prompt 更有价值
5. 终极形态：麦克风 → Whisper → LLM → ROS2 → 机器人（机器人语音 Agent / 开发 Copilot，如语音提问"STM32 CAN 节点收到 80 帧每秒，如何设计？"，LLM 自动结合 CAN 协议、ROS2 架构、FreeRTOS 输出方案）；再进一步与 Camera、LiDAR、IMU、Speech、LLM、RL Policy、Controller 融合形成**机器人认知层**——与现有 ROS2 + Jetson + LiDAR + RL + CAN 的技术路线高度一致

一句话总结：这个项目补上的是机器人系统里长期缺失的**自然语言接口层**——传统机器人是"代码 → 控制 → 机器人"，未来是"人 → 语言 → AI Agent → ROS2 → 机器人"。与现有 STM32 实时控制 + ROS2 系统 + 感知 + 强化学习 + 语音 Agent 的路线高度一致，已逐渐形成完整机器人系统路线，系统本身也已从"语音转文字工具"开始接近"机器人语音 Agent"。

---

## 八、遗留问题 / 待办

- [ ] pre/post-roll buffer 未实现（需改 recognition_manager.py）
- [ ] 用日志确认当前版本 initial_prompt 是否真正传入 whisper.cpp（找 `whisper.cpp initial prompt:` 日志行）
- [ ] Vocalinux 源码部署步骤未留档（AppImage 因 glibc 不可用后的实际安装路径）
- [ ] 切到 small + zh 后简繁输出实测确认（应已通过 initial_prompt 控制为简体）
