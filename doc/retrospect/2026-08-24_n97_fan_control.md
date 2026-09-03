# N97 风扇调速：从 ACPI 死路到 IT8613E 驱动突破

> 日期：2026-08-24
> 环境：N97 迷你主机（Intel N97 / AMI BIOS 5.27 白牌机，Ubuntu 22.04 + 内核 6.8.0-136-generic）
> 结论：**N97 风扇挂在 ITE IT8613E SuperIO 芯片的 fan2 通道**，`it87` 驱动加 `force_id=0x8622` 可接管，
> 通过 sysfs `pwm2` 即刻调速（0-255），恢复自动/重启均可撤销。
> 原始命令记录：本会话所有在 N97 上敲的命令与输出，见 [n97info.md](../n97/n97info.md)。

---

## 背景与需求

- 用户：N97 迷你主机散热差，想**从终端用命令即刻设置风扇固定转速**
- 硬约束 1：**不更改策略**（此前在 BIOS/固件层动过，出过问题差点救不回来）
- 硬约束 2：**所有操作必须带恢复/撤销指令**
- 排障前系统状态：`sensors` 仅有 iwlwifi 56°C / acpitz 27.8°C / coretemp 48°C / nvme 46.9°C；
  `/sys/class/hwmon/hwmon*/name` = acpitz / nvme / iwlwifi_1 / coretemp

---

## 结论速览（TL;DR）

| 项 | 结论 |
|:---|:---|
| 风扇硬件在哪 | ITE **IT8613E** SuperIO 芯片的 **fan2** 通道（tach + pwm2 输出），芯片自动曲线实时控转速 |
| 内核驱动 | 主线 `it87` 模块 + **`force_id=0x8622`** 参数（IT8613E 不在主线型号表，用相似型号 IT8622E 顶替） |
| 调速方式 | sysfs：`echo 1 > pwm2_enable` 切手动 → `echo N > pwm2` 设值（**0-255**，超出报"无效的参数"） |
| 撤销方式 | `echo 2 > pwm2_enable` 交回芯片自动曲线；**重启彻底兜底**（驱动不持久化，it8622 消失回出厂状态） |
| 实测转速 | pwm 100→1956｜150→2537｜200→3068｜255→3534 RPM（中段近似线性，250+ 饱和） |
| 死路（勿再碰） | ACPI thermal cooling_device（**cur_state=1 曾致风扇停转，撤销无效，重启才恢复**）；EC 直读（标准端口关闭、内核驱动不绑定） |

---

## 排查时间线（按尝试顺序）

### 路径 1：ACPI thermal 接口 —— 事故 + 死路 ❌

- 初始尝试：`/sys/class/thermal/cooling_device*/cur_state`（0/1）
- **事故**：写入 `cur_state=1` → 风扇停转；写回 0 撤销**无效**；重启才恢复
- 事后反汇编固件表定位根因（`acpidump → acpixtract → iasl -d dsdt.dat`，产物 ~/dsdt.dsl / ssdt*.dsl）：
  - `ssdt12.dsl`：FAN0-4 设备 = PowerResource FN00-04 的 `_ON/_OFF`；`FNCL` 函数读 GNVS 字段（CVF0-4/VFN0-4）后经 `ECWT/ECMD` 写 EC
  - **`ECWT/ECMD/ECNT` 方法体全空（stub）**；`ECON/AC0F/AC1F/VFN0-4` 是 GNVS 共享内存字段；
    H_EC（PNP0C09）`_STA` 返回 Zero、无 `_CRS`
- **结论**：ACPI 风扇接口是**空壳**，实际控制是 EC 固件内部锁存逻辑；白牌机 DSDT 声明不可信
- **教训**：此接口绝对不能再碰

### 路径 2：EC 逆向 —— 死路 ❌

| 尝试 | 结果 | 原因 |
|:---|:---|:---|
| `modprobe ec_sys write_support=1` | 模块加载成功，但 `/sys/kernel/debug/ec/` 不存在 | 内核 EC 驱动未绑定（PNP0C09 `_STA=0`） |
| 标准 EC 端口 0x62/0x66 探测 | 读回全 ff | 标准通道未解码/被固件关闭 |
| ITE 配置端口 0x2E/0x2F（`/dev/port` + dd） | 空输出（方法问题） | 之后 sensors-detect 在同一端口成功，说明 dd 时序不对 |
| `/dev/port` 直通 | 可用 | CONFIG_DEVPORT=y |

### 路径 3：sensors-detect 浮出真芯片 ✅

```bash
sudo apt install lm-sensors
sudo sensors-detect
```

关键输出：

```
Probing for Super-I/O at 0x2e/0x2f
Trying family `ITE'...                                      Yes
Found `ITE IT8613E Super IO Sensors'                        Success!
    (address 0xa30, driver `to-be-written')
```

- **IT8613E 是 SuperIO 芯片（非 EC）**：标准硬件监控芯片，内核有 it87 驱动家族
- `driver 'to-be-written'` = **lm-sensors 3.6.0 芯片数据库过时**（IT8613E 型号 ID 已被识别但驱动名没入库），不是"没有驱动"
- 芯片挂 LPC 总线，通过 0x2E/0x2F 端口进入配置模式访问

### 路径 4：主线 it87 驱动 —— 失败 ❌

```bash
sudo modprobe it87                     # ERROR: could not insert 'it87': No such device
sudo modprobe it87 force_id=0x8613     # 同样失败（0x8613 不在主线型号表）
```

排查三连：

| 检查 | 结果 | 排除项 |
|:---|:---|:---|
| `sudo dmesg \| grep -iE "it87\|sio"` | 完全无记录（成功时驱动会打印 `Found ... chip`） | 探测静默失败 |
| `modinfo it87` | 模块存在、参数齐全（force_id / ignore_resource_conflict / fix_pwm_polarity） | 驱动本身没问题 |
| `cat /proc/ioports \| grep -iE "2e\|2f\|a30"` | 无保留 | 排除 ACPI 资源冲突 |

### 路径 5：用户空间直读 SuperIO —— 验证通道 ✅

内核驱动探测失败，但 sensors-detect（用户空间）能访问芯片 → 用 `/dev/port` 写 python 脚本直读：

```python
# 进入配置模式：写 0x87,0x01,0x55,0x55 → 0x2E；数据口 0x2F
# 读 device ID：0x20/0x21；LDN 选择：写 0x07；LDN base：0x60/0x61；LDN enable：0x30
```

关键输出：

```
chip ID: 0x86 0x13  ->  0x8613                      # 芯片确认
LDN  4: enable=0x01  base=0xa30                     # sensors-detect 报的地址（注意脚本高低字节拼反显示为 0x300a）
LDN  7: enable=0x00  base=0x0a10                    # HWM 实际所在（当时未知）
```

- 读 LDN4 @ 0xa30 寄存器：config=0x19（bit6=0）、数据全 0xFF → **一度误判**"环境控制器未启用、风扇在 EC 侧"
- **后经搜索修正**（见路径 6）：读错了 LDN——IT8613E 的硬件监控在 **LDN7**，且风扇编号是 fan2~5

### 路径 6：搜索核实 —— 转折点 ✅

WebSearch 核实（来源见文末）修正三个认知：

1. **IT8613E 不在主线 it87 型号表**（[it87.c 源码](https://github.com/a1wong/it87/blob/40bec4b5a7896d4406d2a7d095d06c0624c24aca/it87.c#L3286-L3288)）→ modprobe 失败真因；社区 fork（a1wong/shauno8 等）有原生支持
2. **IT8613E 硬件监控（HWM）在 LDN7**；支持 4 个风扇但编号 **fan2~fan5（没有 fan1/pwm1）**；PWM 寄存器偏移与 IT87xx 不同（[linux-hwmon 邮件列表：fan3/4 的 PWM 在 0x1e/0x1f](https://marc.info/?l=linux-hwmon&m=149866895332421&w=3)）
3. **IT8622E 与 IT8613E 相似，`force_id=0x8622` 可让主线驱动绑定**（[TrueNAS 用户实测验证：Odroid H4+ 风扇转速读取 + PWM 控制均工作](https://forums.truenas.com/t/closed-include-more-up-to-date-it87-module/23861/10)）

### 路径 7：force_id=0x8622 成功 + 调速验证 ✅

```bash
sudo modprobe it87 force_id=0x8622
```

- `cat /sys/class/hwmon/hwmon*/name` → 新增 **it8622**（hwmon4）
- 接口：`fan2/3/4/5_input` + `pwm1~5` 全套（enable/freq/auto_point），**编号 fan2-5 与社区描述吻合**
- `sensors` 读数：

| 通道 | 值 | 含义 |
|:---|:---|:---|
| **fan2** | **1956 RPM** | ✅ 真实风扇（tach 在走） |
| fan3/4/5 | 0 RPM | 空通道 |
| temp1 | +41.0°C，sensor = **Intel PECI** | ✅ 芯片经 PECI 直读 CPU 温度（coretemp 45°C 同量级），采样真实 |
| temp2 | +127.0°C ALARM | 未接热敏电阻的浮动通道，忽略 |
| in0-6 / 3VSB / Vbat | 全部合理 | 芯片运行正常 |
| pwm2_enable / pwm2 | 2（自动）/ 100 | 芯片自动曲线正在控制真实风扇 |

调速验证（每步读回确认）：

```
pwm2_enable  2(自动) → 写 1 → 读回 1        ✅ 通道未被硬件锁自动
pwm2         100 → 150 → 200 → 250 → 255    ✅ 写入全部生效
fan2_input   1956 → 2537 → 3068 → 3214 → 3534 RPM ✅ 转速随 PWM 单调上升
pwm2         300/280/260 → "无效的参数"      ✅ 内核范围校验（0-255），越界被拒
```

> 小插曲：写 300 失败后 fan2 瞬时显示 3515，是 250 档转速未稳定的瞬态，非 300 生效——内核已拒绝越界写。

---

## 最终指令（日常使用，N97 终端）

```bash
# ① 开机后加载驱动（重启后需重新执行；详见"持久化"待办）
sudo modprobe it87 force_id=0x8622

# ② 设固定转速（0-255；建议从 150 附近起步，观察后再调；不要直接 0 或 255）
echo 1 | sudo tee /sys/class/hwmon/hwmon4/pwm2_enable   # 切手动（只需设一次）
echo 200 | sudo tee /sys/class/hwmon/hwmon4/pwm2         # 设转速，即刻生效
cat /sys/class/hwmon/hwmon4/fan2_input                   # 查看实际 RPM

# ③ 撤销/恢复自动曲线（芯片接管，负载自适应）
echo 2 | sudo tee /sys/class/hwmon/hwmon4/pwm2_enable

# ④ 查询
sensors                                              # 总览（含 it8622 块）
cat /sys/class/hwmon/hwmon4/fan2_input               # 风扇实际转速
cat /sys/class/hwmon/hwmon4/pwm2                     # 当前 PWM 值
cat /sys/class/hwmon/hwmon4/pwm2_enable              # 模式（1=手动 2=自动）

# ⑤ 重启兜底：驱动不持久化，重启后 it8622 消失，彻底回到出厂 EC 控制状态
```

**PWM 值 → 转速实测速查**（实测值，250+ 区域有波动）：100→1956｜120→~2200（外推）｜150→2537｜200→3068｜255→3534。中段（100-200）近似线性，实用区间建议 120-220。

---

## 关键教训

1. **白牌机固件声明不可信**：DSDT 里风扇接口是空壳（方法体全空、_STA=0），EC 固件锁存内部逻辑——ACPI 层写入可致风扇停转且撤销无效，**thermal cooling_device 接口不可用于此机**
2. **sensors-detect 的 `driver 'to-be-written'` ≠ 无驱动**：lm-sensors 数据库过时，真实支持看内核源码/社区；`force_id` 是主线驱动绑定"表外相似芯片"的官方逃生门
3. **用户空间（/dev/port + iopl）能访问的 SuperIO，内核驱动未必能绑定**：但反过来，用户空间访问是可靠的诊断通道（本案例用它确认了芯片 ID 与 LDN 布局）
4. **IT8613E 与 IT87xx 寄存器布局不同**：HWM 在 LDN7、风扇编号 fan2-5、PWM 偏移特殊——用 IT87xx 通用读法会得到全 0xFF 假象，易误判"芯片没干活"
5. **排障纪律的胜利**：每次只加一个变量（ACPI 事故后改为纯读探测 → 搜索核实 → 才做写入），全程记录预期/实际，调速验证每步读回确认

---

## 待办 / 可选

- [ ] **持久化（可选）**：开机自动加载驱动 → `/etc/modprobe.d/it87.conf`（`options it87 force_id=0x8622`）+ `/etc/modules-load.d/`（`it87`）。纯 OS 层，不碰固件，删除文件即恢复出厂
- [ ] **自定义温控曲线（可选，属"改策略"）**：`pwmconfig` 生成 `/etc/fancontrol` 配置 + fancontrol 服务，可完全自定义温度-转速映射
- [ ] 未验证项：pwm 极性反转（若某次发现转速反向变化，用 `fix_pwm_polarity=1` 重载模块）；pwm1/3/4/5 通道是否也接有设备（当前读数显示空通道）

---

## 来源（2026-08-24 WebSearch 核实）

> 来源 = WebSearch 结果 + 本机实测；"force_id=0x8622 可行"为社区实测（TrueNAS 用户），未在本机之外复测

- [it87.c 源码 it8613 条目（a1wong fork）](https://github.com/a1wong/it87/blob/40bec4b5a7896d4406d2a7d095d06c0624c24aca/it87.c#L3286-L3288) — IT8613E 驱动支持
- [linux-hwmon 邮件列表：IT87_REG_PWM[3-5] 对 IT8613E 的错误](https://marc.info/?l=linux-hwmon&m=149866895332421&w=3) — PWM 寄存器偏移差异实锤
- [飞牛 NAS：ITE IT8613E 驱动探索](https://cszj.wang/posts/CvMSn) — IT8613E 探测/驱动实况（LDN7、fan2-5 编号）
- [TrueNAS 论坛：include more up to date it87 module](https://forums.truenas.com/t/include-more-up-to-date-it87-module/23861) — 主线不支持 0x8613、out-of-tree 方案
- [TrueNAS：Odroid H4+ force_id=0x8622 实测验证](https://forums.truenas.com/t/closed-include-more-up-to-date-it87-module/23861/10) — force_id 生效案例
- [IT-Kuny/UGREEN-DXP-FAN-NAS-Driver](https://github.com/IT-Kuny/UGREEN-DXP-FAN-NAS-Driver) — DKMS 安装 it87 + systemd 时序
- [shauno8/it87（fix IT8613E in lm-sensors）](https://github.com/shauno8/it87) — IT8613E 风扇转速支持
- [yuyuyuyu-an/it87-dkms（Fedora COPR）](https://copr.fedorainfracloud.org/coprs/yuyuyuyu-an/it87-dkms/) — DKMS 包
- [OpenWrt PR #18903（graysky2 kmod it87）](https://github.com/openwrt/openwrt/pull/18903) — 新硬件 kmod 修改
- [CSDN：SuperIO 芯片寄存器访问与 GPIO 控制工具（UEFI）](https://blog.csdn.net/q9w8e7r6t5/article/details/151124734) — SuperIO 访问原理参考
- [CSDN：SuperIO 芯片 GPIO 配置与硬件监控](https://blog.csdn.net/weixin_29189987/article/details/158786032) — SuperIO 配置模式参考

---

## 相关文件

- 原始命令/输出记录（用户持续维护）：[n97info.md](../n97/n97info.md)
- 本文档为本次排障的单一事实来源；本机状态以 `sensors` 与 `/sys/class/hwmon/hwmon4/` 实测为准
