# N97 硬件信息 · 风扇调速排查记录

> 说明：本文件为 N97 迷你主机（Intel N97 / AMI BIOS 5.27 白牌机，Ubuntu 22.04 + 内核 6.8）风扇调速排查的**原始命令记录**（2026-08-24）
> 完整结论 / 排查链条 / 来源 / 教训：**[retrospect/2026-08-24_n97_fan_control.md](../retrospect/2026-08-24_n97_fan_control.md)**（单一事实来源）
> 本文件只做原始输出留档 + 速查，细节以 retrospect 为准。

---

## 结论速览（2026-08-24 实测）

| 项 | 结论 |
|:---|:---|
| 风扇硬件 | ITE **IT8613E** SuperIO 芯片的 **fan2** 通道（tach + pwm2 输出），芯片自动曲线实时控制 |
| 驱动 | 主线 `it87` + **`force_id=0x8622`**（IT8613E 不在主线型号表，用相似型号 IT8622E 绑定） |
| 调速 | `echo 1 > pwm2_enable` 切手动 → `echo N > pwm2` 设值（**0-255**，越界报"无效的参数"） |
| 撤销 | `echo 2 > pwm2_enable` 恢复自动曲线；**重启彻底兜底**（驱动不持久化） |
| 实测转速 | pwm 100→1956｜150→2537｜200→3068｜255→3534 RPM（中段线性，250+ 饱和） |
| 勿再碰 | ACPI `/sys/class/thermal/cooling_device*/cur_state`（**写入曾致风扇停转、撤销无效、重启才恢复**）；EC 直读（死路） |

## 常用指令（速查）

```bash
# 开机后加载驱动（重启需重跑；持久化未做，见 retrospect 待办）
sudo modprobe it87 force_id=0x8622

# 设固定转速（建议 120-220 区间起步）
echo 1 | sudo tee /sys/class/hwmon/hwmon4/pwm2_enable   # 切手动
echo 200 | sudo tee /sys/class/hwmon/hwmon4/pwm2         # 设转速，即刻生效
cat /sys/class/hwmon/hwmon4/fan2_input                   # 看实际 RPM

# 恢复自动（芯片接管）
echo 2 | sudo tee /sys/class/hwmon/hwmon4/pwm2_enable

# 查询
sensors                                            # 总览（含 it8622 块）
cat /sys/class/hwmon/hwmon4/pwm2_enable            # 模式（1=手动 2=自动）
cat /sys/class/hwmon/hwmon4/pwm2                   # 当前 PWM 值
```

---

## 原始记录（按阶段）

### ① sensors-detect 全量扫描 —— 发现 IT8613E

> 关键行：`Found 'ITE IT8613E Super IO Sensors' (address 0xa30, driver 'to-be-written')`
> `to-be-written` = lm-sensors 数据库过时，非无驱动；I2C/SMBus 全量扫描（74 行起）结果全部 No，可跳过。

```
lin@lin-Default-string:~$ sudo sensors-detect
# sensors-detect version 3.6.0
# System: Default string Default string [Default string]
# Kernel: 6.8.0-136-generic x86_64
# Processor: Intel(R) N97 (6/190/0)

This program will help you determine which kernel modules you need
to load to use lm_sensors most effectively. It is generally safe
and recommended to accept the default answers to all questions,
unless you know what you're doing.

Some south bridges, CPUs or memory controllers contain embedded sensors.
Do you want to scan for them? This is totally safe. (YES/no): yes
Module cpuid loaded successfully.
Silicon Integrated Systems SIS5595...                       No
VIA VT82C686 Integrated Sensors...                          No
VIA VT8231 Integrated Sensors...                            No
AMD K8 thermal sensors...                                   No
AMD Family 10h thermal sensors...                           No
AMD Family 11h thermal sensors...                           No
AMD Family 12h and 14h thermal sensors...                   No
AMD Family 15h thermal sensors...                           No
AMD Family 16h thermal sensors...                           No
AMD Family 17h thermal sensors...                           No
AMD Family 15h power sensors...                             No
AMD Family 16h power sensors...                             No
Hygon Family 18h thermal sensors...                         No
Intel digital thermal sensor...                             Success!
    (driver `coretemp')
Intel AMB FB-DIMM thermal sensor...                         No
Intel 5500/5520/X58 thermal sensor...                       No
VIA C7 thermal sensor...                                    No
VIA Nano thermal sensor...                                  No

Some Super I/O chips contain embedded sensors. We have to write to
standard I/O ports to probe them. This is usually safe.
Do you want to scan for Super I/O sensors? (YES/no): yes
Probing for Super-I/O at 0x2e/0x2f
Trying family `National Semiconductor/ITE'...               No
Trying family `SMSC'...                                     No
Trying family `VIA/Winbond/Nuvoton/Fintek'...               No
Trying family `ITE'...                                      Yes
Found `ITE IT8613E Super IO Sensors'                        Success!
    (address 0xa30, driver `to-be-written')
Probing for Super-I/O at 0x4e/0x4f
Trying family `National Semiconductor/ITE'...               No
Trying family `SMSC'...                                     No
Trying family `VIA/Winbond/Nuvoton/Fintek'...               No
Trying family `ITE'...                                      No

Some systems (mainly servers) implement IPMI, a set of common interfaces
through which system health data may be retrieved, amongst other things.
We first try to get the information from SMBIOS. If we don't find it
there, we have to read from arbitrary I/O ports to probe for such
interfaces. This is normally safe. Do you want to scan for IPMI
interfaces? (YES/no): yes
Probing for `IPMI BMC KCS' at 0xca0...                      No
Probing for `IPMI BMC SMIC' at 0xca8...                     No

Some hardware monitoring chips are accessible through the ISA I/O ports.
We have to write to arbitrary I/O ports to probe them. This is usually
safe though. Yes, you do have ISA I/O ports even if you do not have any
ISA slots! Do you want to scan the ISA I/O ports? (yes/NO): yes
Probing for `National Semiconductor LM78' at 0x290...       No
Probing for `National Semiconductor LM79' at 0x290...       No
Probing for `Winbond W83781D' at 0x290...                   No
Probing for `Winbond W83782D' at 0x290...                   No

Lastly, we can probe the I2C/SMBus adapters for connected hardware
monitoring devices. This is the most risky part, and while it works
reasonably well on most systems, it has been reported to cause trouble
on some systems.
Do you want to probe the I2C/SMBus adapters now? (YES/no): yes
Found unknown SMBus adapter 8086:54a3 at 0000:00:1f.4.
Sorry, no supported PCI bus adapters found.

Next adapter: SMBus I801 adapter at efa0 (i2c-0)
Do you want to scan it? (yes/NO/selectively): yes
Client found at address 0x50
Handled by driver `ee1004' (already loaded), chip type `ee1004'
    (note: this is probably NOT a sensor chip!)

Next adapter: i915 gmbus dpa (i2c-1)
Do you want to scan it? (yes/NO/selectively): yes

Next adapter: i915 gmbus dpb (i2c-2)
Do you want to scan it? (yes/NO/selectively): yes
Client found at address 0x4a
Probing for `National Semiconductor LM75'...                No
Probing for `National Semiconductor LM75A'...               No
Probing for `Dallas Semiconductor DS75'...                  No
Probing for `National Semiconductor LM77'...                No
Probing for `Analog Devices ADT7410/ADT7420'...             No
Probing for `Analog Devices ADT7411'...                     No
Probing for `Maxim MAX6642'...                              No
Probing for `Texas Instruments TMP435'...                   No
Probing for `National Semiconductor LM73'...                No
Probing for `National Semiconductor LM92'...                No
Probing for `National Semiconductor LM76'...                No
Probing for `Maxim MAX6633/MAX6634/MAX6635'...              No
Probing for `NXP/Philips SA56004'...                        No
Client found at address 0x4b
Probing for `National Semiconductor LM75'...                No
Probing for `National Semiconductor LM75A'...               No
Probing for `Dallas Semiconductor DS75'...                  No
Probing for `National Semiconductor LM77'...                No
Probing for `Analog Devices ADT7410/ADT7420'...             No
Probing for `Analog Devices ADT7411'...                     No
Probing for `Maxim MAX6642'...                              No
Probing for `Texas Instruments TMP435'...                   No
Probing for `National Semiconductor LM73'...                No
Probing for `National Semiconductor LM92'...                No
Probing for `National Semiconductor LM76'...                No
Probing for `Maxim MAX6633/MAX6634/MAX6635'...              No
Probing for `NXP/Philips SA56004'...                        No
Probing for `Analog Devices ADT7481'...                     No

Next adapter: i915 gmbus dpc (i2c-3)
Do you want to scan it? (yes/NO/selectively): yes

Next adapter: i915 gmbus tc1 (i2c-4)
Do you want to scan it? (yes/NO/selectively): yes

Next adapter: i915 gmbus tc2 (i2c-5)
Do you want to scan it? (yes/NO/selectively): yes

Next adapter: i915 gmbus tc3 (i2c-6)
Do you want to scan it? (yes/NO/selectively): yes

Next adapter: i915 gmbus tc4 (i2c-7)
Do you want to scan it? (yes/NO/selectively): yes
Client found at address 0x18
Probing for `Analog Devices ADM1021'...                     No
Probing for `Analog Devices ADM1021A/ADM1023'...            No
Probing for `Maxim MAX1617'...                              No
Probing for `Maxim MAX1617A'...                             No
Probing for `Maxim MAX1668'...                              No
Probing for `Maxim MAX1805'...                              No
Probing for `Maxim MAX1989'...                              No
Probing for `Maxim MAX6655/MAX6656'...                      No
Probing for `TI THMC10'...                                  No
Probing for `National Semiconductor LM84'...                No
Probing for `Genesys Logic GL523SM'...                      No
Probing for `Onsemi MC1066'...                              No
Probing for `Maxim MAX1618'...                              No
Probing for `Maxim MAX1619'...                              No
Probing for `National Semiconductor LM82/LM83'...           No
Probing for `Maxim MAX6654'...                              No
Probing for `Maxim MAX6690'...                              No
Probing for `Maxim MAX6680/MAX6681'...                      No
Probing for `Maxim MAX6695/MAX6696'...                      No
Probing for `Texas Instruments TMP400'...                   No
Probing for `Texas Instruments AMC6821'...                  No
Probing for `National Semiconductor LM95233'...             No
Probing for `National Semiconductor LM95234'...             No
Probing for `National Semiconductor LM95235'...             No
Probing for `National Semiconductor LM95245'...             No
Probing for `National Semiconductor LM64'...                No
Probing for `SMSC EMC1047'...                               No
Probing for `SMSC EMC1402'...                               No
Probing for `SMSC EMC1403'...                               No
Probing for `SMSC EMC1404'...                               No
Probing for `ST STTS424'...                                 No
Probing for `ST STTS424E'...                                No
Probing for `ST STTS2002'...                                No
Probing for `ST STTS3000'...                                No
Probing for `NXP SE97/SE97B'...                             No
Probing for `NXP SE98'...                                   No
Probing for `Analog Devices ADT7408'...                     No
Probing for `IDT TS3000/TSE2002'...                         No
Probing for `IDT TSE2004'...                                No
Probing for `IDT TS3001'...                                 No
Probing for `Maxim MAX6604'...                              No
Probing for `Microchip MCP9804'...                          No
Probing for `Microchip MCP9808'...                          No
Probing for `Microchip MCP98242'...                         No
Probing for `Microchip MCP98243'...                         No
Probing for `Microchip MCP98244'...                         No
Probing for `Microchip MCP9843'...                          No
Probing for `ON CAT6095/CAT34TS02'...                       No
Probing for `ON CAT34TS02C'...                              No
Probing for `ON CAT34TS04'...                               No
Probing for `Atmel AT30TS00'...                             No
Probing for `Giantec GT30TS00'...                           No
Client found at address 0x19
Probing for `Analog Devices ADM1021'...                     No
Probing for `Analog Devices ADM1021A/ADM1023'...            No
Probing for `Maxim MAX1617'...                              No
Probing for `Maxim MAX1617A'...                             No
Probing for `Maxim MAX1668'...                              No
Probing for `Maxim MAX1805'...                              No
Probing for `Maxim MAX1989'...                              No
Probing for `Maxim MAX6655/MAX6656'...                      No
Probing for `TI THMC10'...                                  No
Probing for `National Semiconductor LM84'...                No
Probing for `Genesys Logic GL523SM'...                      No
Probing for `Onsemi MC1066'...                              No
Probing for `Maxim MAX1618'...                              No
Probing for `Maxim MAX1619'...                              No
Probing for `National Semiconductor LM82/LM83'...           No
Probing for `Maxim MAX6654'...                              No
Probing for `Maxim MAX6690'...                              No
Probing for `Maxim MAX6680/MAX6681'...                      No
Probing for `Maxim MAX6695/MAX6696'...                      No
Probing for `Texas Instruments TMP400'...                   No
Probing for `Texas Instruments AMC6821'...                  No
Probing for `National Semiconductor LM95231'...             No
Probing for `National Semiconductor LM95241'...             No
Probing for `National Semiconductor LM95245'...             No
Probing for `ST STTS424'...                                 No
Probing for `ST STTS424E'...                                No
Probing for `ST STTS2002'...                                No
Probing for `ST STTS3000'...                                No
Probing for `NXP SE97/SE97B'...                             No
Probing for `NXP SE98'...                                   No
Probing for `Analog Devices ADT7408'...                     No
Probing for `IDT TS3000/TSE2002'...                         No
Probing for `IDT TSE2004'...                                No
Probing for `IDT TS3001'...                                 No
Probing for `Maxim MAX6604'...                              No
Probing for `Microchip MCP9804'...                          No
Probing for `Microchip MCP9808'...                          No
Probing for `Microchip MCP98242'...                         No
Probing for `Microchip MCP98243'...                         No
Probing for `Microchip MCP98244'...                         No
Probing for `Microchip MCP9843'...                          No
Probing for `ON CAT6095/CAT34TS02'...                       No
Probing for `ON CAT34TS02C'...                              No
Probing for `ON CAT34TS04'...                               No
Probing for `Atmel AT30TS00'...                             No
Probing for `Giantec GT30TS00'...                           No
Client found at address 0x1a
Probing for `Analog Devices ADM1021'...                     No
Probing for `Analog Devices ADM1021A/ADM1023'...            No
Probing for `Maxim MAX1617'...                              No
Probing for `Maxim MAX1617A'...                             No
Probing for `Maxim MAX1668'...                              No
Probing for `Maxim MAX1805'...                              No
Probing for `Maxim MAX1989'...                              No
Probing for `Maxim MAX6655/MAX6656'...                      No
Probing for `TI THMC10'...                                  No
Probing for `National Semiconductor LM84'...                No
Probing for `Genesys Logic GL523SM'...                      No
Probing for `Onsemi MC1066'...                              No
Probing for `Maxim MAX1618'...                              No
Probing for `Maxim MAX1619'...                              No
Probing for `National Semiconductor LM82/LM83'...           No
Probing for `Maxim MAX6654'...                              No
Probing for `Maxim MAX6690'...                              No
Probing for `Maxim MAX6680/MAX6681'...                      No
Probing for `Maxim MAX6695/MAX6696'...                      No
Probing for `Texas Instruments TMP400'...                   No
Probing for `Texas Instruments AMC6821'...                  No
Probing for `ST STTS424'...                                 No
Probing for `ST STTS424E'...                                No
Probing for `ST STTS2002'...                                No
Probing for `ST STTS3000'...                                No
Probing for `NXP SE97/SE97B'...                             No
Probing for `NXP SE98'...                                   No
Probing for `Analog Devices ADT7408'...                     No
Probing for `IDT TS3000/TSE2002'...                         No
Probing for `IDT TSE2004'...                                No
Probing for `IDT TS3001'...                                 No
Probing for `Maxim MAX6604'...                              No
Probing for `Microchip MCP9804'...                          No
Probing for `Microchip MCP9808'...                          No
Probing for `Microchip MCP98242'...                         No
Probing for `Microchip MCP98243'...                         No
Probing for `Microchip MCP98244'...                         No
Probing for `Microchip MCP9843'...                          No
Probing for `ON CAT6095/CAT34TS02'...                       No
Probing for `ON CAT34TS02C'...                              No
Probing for `ON CAT34TS04'...                               No
Probing for `Atmel AT30TS00'...                             No
Probing for `Giantec GT30TS00'...                           No
Client found at address 0x1b
Probing for `ST STTS424'...                                 No
Probing for `ST STTS424E'...                                No
Probing for `ST STTS2002'...                                No
Probing for `ST STTS3000'...                                No
Probing for `NXP SE97/SE97B'...                             No
Probing for `NXP SE98'...                                   No
Probing for `Analog Devices ADT7408'...                     No
Probing for `IDT TS3000/TSE2002'...                         No
Probing for `IDT TSE2004'...                                No
Probing for `IDT TS3001'...                                 No
Probing for `Maxim MAX6604'...                              No
Probing for `Microchip MCP9804'...                          No
Probing for `Microchip MCP9808'...                          No
Probing for `Microchip MCP98242'...                         No
Probing for `Microchip MCP98243'...                         No
Probing for `Microchip MCP98244'...                         No
Probing for `Microchip MCP9843'...                          No
Probing for `ON CAT6095/CAT34TS02'...                       No
Probing for `ON CAT34TS02C'...                              No
Probing for `ON CAT34TS04'...                               No
Probing for `Atmel AT30TS00'...                             No
Probing for `Giantec GT30TS00'...                           No
Client found at address 0x1c
Probing for `Texas Instruments TMP421'...                   No
Probing for `Texas Instruments TMP441'...                   No
Probing for `SMSC EMC1072'...                               No
Probing for `SMSC EMC1073'...                               No
Probing for `SMSC EMC1074'...                               No
Probing for `ST STTS424'...                                 No
Probing for `ST STTS424E'...                                No
Probing for `ST STTS2002'...                                No
Probing for `ST STTS3000'...                                No
Probing for `NXP SE97/SE97B'...                             No
Probing for `NXP SE98'...                                   No
Probing for `Analog Devices ADT7408'...                     No
Probing for `IDT TS3000/TSE2002'...                         No
Probing for `IDT TSE2004'...                                No
Probing for `IDT TS3001'...                                 No
Probing for `Maxim MAX6604'...                              No
Probing for `Microchip MCP9804'...                          No
Probing for `Microchip MCP9808'...                          No
Probing for `Microchip MCP98242'...                         No
Probing for `Microchip MCP98243'...                         No
Probing for `Microchip MCP98244'...                         No
Probing for `Microchip MCP9843'...                          No
Probing for `ON CAT6095/CAT34TS02'...                       No
Probing for `ON CAT34TS02C'...                              No
Probing for `ON CAT34TS04'...                               No
Probing for `Atmel AT30TS00'...                             No
Probing for `Giantec GT30TS00'...                           No
Client found at address 0x1d
Probing for `TI / National Semiconductor ADC128D818'...     No
Probing for `Texas Instruments TMP421'...                   No
Probing for `Texas Instruments TMP441'...                   No
Probing for `ST STTS424'...                                 No
Probing for `ST STTS424E'...                                No
Probing for `ST STTS2002'...                                No
Probing for `ST STTS3000'...                                No
Probing for `NXP SE97/SE97B'...                             No
Probing for `NXP SE98'...                                   No
Probing for `Analog Devices ADT7408'...                     No
Probing for `IDT TS3000/TSE2002'...                         No
Probing for `IDT TSE2004'...                                No
Probing for `IDT TS3001'...                                 No
Probing for `Maxim MAX6604'...                              No
Probing for `Microchip MCP9804'...                          No
Probing for `Microchip MCP9808'...                          No
Probing for `Microchip MCP98242'...                         No
Probing for `Microchip MCP98243'...                         No
Probing for `Microchip MCP98244'...                         No
Probing for `Microchip MCP9843'...                          No
Probing for `ON CAT6095/CAT34TS02'...                       No
Probing for `ON CAT34TS02C'...                              No
Probing for `ON CAT34TS04'...                               No
Probing for `Atmel AT30TS00'...                             No
Probing for `Giantec GT30TS00'...                           No
Client found at address 0x1e
Probing for `TI / National Semiconductor ADC128D818'...     No
Probing for `Texas Instruments TMP421'...                   No
Probing for `Texas Instruments TMP441'...                   No
Probing for `ST STTS424'...                                 No
Probing for `ST STTS424E'...                                No
Probing for `ST STTS2002'...                                No
Probing for `ST STTS3000'...                                No
Probing for `NXP SE97/SE97B'...                             No
Probing for `NXP SE98'...                                   No
Probing for `Analog Devices ADT7408'...                     No
Probing for `IDT TS3000/TSE2002'...                         No
Probing for `IDT TSE2004'...                                No
Probing for `IDT TS3001'...                                 No
Probing for `Maxim MAX6604'...                              No
Probing for `Microchip MCP9804'...                          No
Probing for `Microchip MCP9808'...                          No
Probing for `Microchip MCP98242'...                         No
Probing for `Microchip MCP98243'...                         No
Probing for `Microchip MCP98244'...                         No
Probing for `Microchip MCP9843'...                          No
Probing for `ON CAT6095/CAT34TS02'...                       No
Probing for `ON CAT34TS02C'...                              No
Probing for `ON CAT34TS04'...                               No
Probing for `Atmel AT30TS00'...                             No
Probing for `Giantec GT30TS00'...                           No
Client found at address 0x1f
Probing for `TI / National Semiconductor ADC128D818'...     No
Probing for `Texas Instruments TMP421'...                   No
Probing for `Texas Instruments TMP441'...                   No
Probing for `ST STTS424'...                                 No
Probing for `ST STTS424E'...                                No
Probing for `ST STTS2002'...                                No
Probing for `ST STTS3000'...                                No
Probing for `NXP SE97/SE97B'...                             No
Probing for `NXP SE98'...                                   No
Probing for `Analog Devices ADT7408'...                     No
Probing for `IDT TS3000/TSE2002'...                         No
Probing for `IDT TSE2004'...                                No
Probing for `IDT TS3001'...                                 No
Probing for `Maxim MAX6604'...                              No
Probing for `Microchip MCP9804'...                          No
Probing for `Microchip MCP9808'...                          No
Probing for `Microchip MCP98242'...                         No
Probing for `Microchip MCP98243'...                         No
Probing for `Microchip MCP98244'...                         No
Probing for `Microchip MCP9843'...                          No
Probing for `ON CAT6095/CAT34TS02'...                       No
Probing for `ON CAT34TS02C'...                              No
Probing for `ON CAT34TS04'...                               No
Probing for `Atmel AT30TS00'...                             No
Probing for `Giantec GT30TS00'...                           No
Client found at address 0x28
Probing for `National Semiconductor LM78'...                No
Probing for `National Semiconductor LM79'...                No
Probing for `National Semiconductor LM80'...                No
Probing for `National Semiconductor LM96080'...             No
Probing for `Winbond W83781D'...                            No
Probing for `Winbond W83782D'...                            No
Probing for `Nuvoton NCT7802Y'...                           No
Probing for `Winbond W83627HF'...                           No
Probing for `Winbond W83627EHF'...                          No
Probing for `Winbond W83627DHG/W83667HG/W83677HG'...        No
Probing for `Asus AS99127F (rev.1)'...                      No
Probing for `Asus AS99127F (rev.2)'...                      No
Probing for `Asus ASB100 Bach'...                           No
Probing for `Analog Devices ADM1029'...                     No
Probing for `ITE IT8712F'...                                No
Client found at address 0x29
Probing for `National Semiconductor LM78'...                No
Probing for `National Semiconductor LM79'...                No
Probing for `National Semiconductor LM80'...                No
Probing for `National Semiconductor LM96080'...             No
Probing for `Winbond W83781D'...                            No
Probing for `Winbond W83782D'...                            No
Probing for `Nuvoton NCT7802Y'...                           No
Probing for `Winbond W83627HF'...                           No
Probing for `Winbond W83627EHF'...                          No
Probing for `Winbond W83627DHG/W83667HG/W83677HG'...        No
Probing for `Asus AS99127F (rev.1)'...                      No
Probing for `Asus AS99127F (rev.2)'...                      No
Probing for `Asus ASB100 Bach'...                           No
Probing for `Analog Devices ADM1021'...                     No
Probing for `Analog Devices ADM1021A/ADM1023'...            No
Probing for `Maxim MAX1617'...                              No
Probing for `Maxim MAX1617A'...                             No
Probing for `Maxim MAX1668'...                              No
Probing for `Maxim MAX1805'...                              No
Probing for `Maxim MAX1989'...                              No
Probing for `Maxim MAX6655/MAX6656'...                      No
Probing for `TI THMC10'...                                  No
Probing for `National Semiconductor LM84'...                No
Probing for `Genesys Logic GL523SM'...                      No
Probing for `Onsemi MC1066'...                              No
Probing for `Maxim MAX1618'...                              No
Probing for `Maxim MAX1619'...                              No
Probing for `National Semiconductor LM82/LM83'...           No
Probing for `Maxim MAX6654'...                              No
Probing for `Maxim MAX6690'...                              No
Probing for `Maxim MAX6680/MAX6681'...                      No
Probing for `Maxim MAX6695/MAX6696'...                      No
Probing for `Texas Instruments TMP400'...                   No
Probing for `National Semiconductor LM95235'...             No
Probing for `National Semiconductor LM95245'...             No
Probing for `Analog Devices ADM1029'...                     No
Probing for `ITE IT8712F'...                                No
Probing for `SMSC EMC1402'...                               No
Probing for `SMSC EMC1403'...                               No
Probing for `SMSC EMC1404'...                               No
Client found at address 0x2a
Probing for `National Semiconductor LM78'...                No
Probing for `National Semiconductor LM79'...                No
Probing for `National Semiconductor LM80'...                No
Probing for `National Semiconductor LM96080'...             No
Probing for `Winbond W83781D'...                            No
Probing for `Winbond W83782D'...                            No
Probing for `Nuvoton NCT7802Y'...                           No
Probing for `Winbond W83627HF'...                           No
Probing for `Winbond W83627EHF'...                          No
Probing for `Winbond W83627DHG/W83667HG/W83677HG'...        No
Probing for `Asus AS99127F (rev.1)'...                      No
Probing for `Asus AS99127F (rev.2)'...                      No
Probing for `Asus ASB100 Bach'...                           No
Probing for `Analog Devices ADM1021'...                     No
Probing for `Analog Devices ADM1021A/ADM1023'...            No
Probing for `Maxim MAX1617'...                              No
Probing for `Maxim MAX1617A'...                             No
Probing for `Maxim MAX1668'...                              No
Probing for `Maxim MAX1805'...                              No
Probing for `Maxim MAX1989'...                              No
Probing for `Maxim MAX6655/MAX6656'...                      No
Probing for `TI THMC10'...                                  No
Probing for `National Semiconductor LM84'...                No
Probing for `Genesys Logic GL523SM'...                      No
Probing for `Onsemi MC1066'...                              No
Probing for `Maxim MAX1618'...                              No
Probing for `Maxim MAX1619'...                              No
Probing for `National Semiconductor LM82/LM83'...           No
Probing for `Maxim MAX6654'...                              No
Probing for `Maxim MAX6690'...                              No
Probing for `Maxim MAX6680/MAX6681'...                      No
Probing for `Maxim MAX6695/MAX6696'...                      No
Probing for `Texas Instruments TMP400'...                   No
Probing for `Texas Instruments AMC6821'...                  No
Probing for `National Semiconductor LM95231'...             No
Probing for `National Semiconductor LM95233'...             No
Probing for `National Semiconductor LM95241'...             No
Probing for `Analog Devices ADM1029'...                     No
Probing for `ITE IT8712F'...                                No
Client found at address 0x2b
Probing for `National Semiconductor LM78'...                No
Probing for `National Semiconductor LM79'...                No
Probing for `National Semiconductor LM80'...                No
Probing for `National Semiconductor LM96080'...             No
Probing for `Winbond W83781D'...                            No
Probing for `Winbond W83782D'...                            No
Probing for `Nuvoton NCT7802Y'...                           No
Probing for `Winbond W83627HF'...                           No
Probing for `Winbond W83627EHF'...                          No
Probing for `Winbond W83627DHG/W83667HG/W83677HG'...        No
Probing for `Asus AS99127F (rev.1)'...                      No
Probing for `Asus AS99127F (rev.2)'...                      No
Probing for `Asus ASB100 Bach'...                           No
Probing for `Analog Devices ADM1021'...                     No
Probing for `Analog Devices ADM1021A/ADM1023'...            No
Probing for `Maxim MAX1617'...                              No
Probing for `Maxim MAX1617A'...                             No
Probing for `Maxim MAX1668'...                              No
Probing for `Maxim MAX1805'...                              No
Probing for `Maxim MAX1989'...                              No
Probing for `Maxim MAX6655/MAX6656'...                      No
Probing for `TI THMC10'...                                  No
Probing for `National Semiconductor LM84'...                No
Probing for `Genesys Logic GL523SM'...                      No
Probing for `Onsemi MC1066'...                              No
Probing for `Maxim MAX1618'...                              No
Probing for `Maxim MAX1619'...                              No
Probing for `National Semiconductor LM82/LM83'...           No
Probing for `Maxim MAX6654'...                              No
Probing for `Maxim MAX6690'...                              No
Probing for `Maxim MAX6680/MAX6681'...                      No
Probing for `Maxim MAX6695/MAX6696'...                      No
Probing for `Texas Instruments TMP400'...                   No
Probing for `Texas Instruments AMC6821'...                  No
Probing for `ST STTS424'...                                 No
Probing for `ST STTS424E'...                                No
Probing for `ST STTS2002'...                                No
Probing for `ST STTS3000'...                                No
Probing for `NXP SE97/SE97B'...                             No
Probing for `NXP SE98'...                                   No
Probing for `Analog Devices ADT7408'...                     No
Probing for `IDT TS3000/TSE2002'...                         No
Probing for `IDT TSE2004'...                                No
Probing for `IDT TS3001'...                                 No
Probing for `Maxim MAX6604'...                              No
Probing for `Microchip MCP9804'...                          No
Probing for `Microchip MCP9808'...                          No
Probing for `Microchip MCP98242'...                         No
Probing for `Microchip MCP98243'...                         No
Probing for `Microchip MCP98244'...                         No
Probing for `Microchip MCP9843'...                          No
Probing for `ON CAT6095/CAT34TS02'...                       No
Probing for `ON CAT34TS02C'...                              No
Probing for `ON CAT34TS04'...                               No
Probing for `Atmel AT30TS00'...                             No
Probing for `Giantec GT30TS00'...                           No
Client found at address 0x2c
Probing for `Myson MTP008'...                               No
Probing for `National Semiconductor LM78'...                No
Probing for `National Semiconductor LM79'...                No
Probing for `National Semiconductor LM80'...                No
Probing for `National Semiconductor LM96080'...             No
Probing for `National Semiconductor LM85'...                No
Probing for `National Semiconductor LM96000 or PC8374L'...  No
Probing for `Analog Devices ADM1027'...                     No
Probing for `Analog Devices ADT7460 or ADT7463'...          No
Probing for `SMSC EMC6D100 or EMC6D101'...                  No
Probing for `SMSC EMC6D102'...                              No
Probing for `SMSC EMC6D103'...                              No
Probing for `SMSC EMC6D103S or EMC2300'...                  No
Probing for `SMSC EMC6W201'...                              No
Probing for `Winbond WPCD377I'...                           No
Probing for `Analog Devices ADT7470'...                     No
Probing for `Analog Devices ADT7473'...                     No
Probing for `Analog Devices ADT7476'...                     No
Probing for `Analog Devices ADT7490'...                     No
Probing for `Andigilog aSC7611'...                          No
Probing for `Andigilog aSC7621'...                          No
Probing for `National Semiconductor LM87'...                No
Probing for `Analog Devices ADM1024'...                     No
Probing for `National Semiconductor LM93'...                No
Probing for `National Semiconductor LM94 or LM96194'...     No
Probing for `Winbond W83781D'...                            No
Probing for `Winbond W83782D'...                            No
Probing for `Winbond W83791D'...                            No
Probing for `Winbond W83792D'...                            No
Probing for `Winbond W83793R/G'...                          No
Probing for `Nuvoton W83795G/ADG'...                        No
Probing for `Nuvoton NCT7802Y'...                           No
Probing for `Winbond W83627HF'...                           No
Probing for `Winbond W83627EHF'...                          No
Probing for `Winbond W83627DHG/W83667HG/W83677HG'...        No
Probing for `Asus AS99127F (rev.1)'...                      No
Probing for `Asus AS99127F (rev.2)'...                      No
Probing for `Asus ASB100 Bach'...                           No
Probing for `Genesys Logic GL518SM'...                      No
Probing for `Genesys Logic GL520SM'...                      No
Probing for `Analog Devices ADM9240'...                     No
Probing for `Dallas Semiconductor DS1780'...                No
Probing for `National Semiconductor LM81'...                No
Probing for `Analog Devices ADM1026'...                     No
Probing for `Analog Devices ADM1025'...                     No
Probing for `Philips NE1619'...                             No
Probing for `Maxim MAX6639'...                              No
Probing for `Texas Instruments AMC6821'...                  No
Probing for `Analog Devices ADM1029'...                     No
Probing for `Analog Devices ADM1030'...                     No
Probing for `Analog Devices ADM1031'...                     No
Probing for `Analog Devices ADM1022'...                     No
Probing for `Texas Instruments THMC50'...                   No
Probing for `ITE IT8712F'...                                No
Probing for `ALi M5879'...                                  No
Probing for `SMSC LPC47M15x/192/292/997'...                 No
Probing for `SMSC DME1737'...                               No
Probing for `SMSC SCH5027D-NW'...                           No
Probing for `SMSC EMC1072'...                               No
Probing for `SMSC EMC1073'...                               No
Probing for `SMSC EMC1074'...                               No
Probing for `Winbond W83791SD'...                           No
Client found at address 0x2d
Probing for `Myson MTP008'...                               No
Probing for `National Semiconductor LM78'...                No
Probing for `National Semiconductor LM79'...                No
Probing for `National Semiconductor LM80'...                No
Probing for `National Semiconductor LM96080'...             No
Probing for `TI / National Semiconductor ADC128D818'...     No
Probing for `National Semiconductor LM85'...                No
Probing for `National Semiconductor LM96000 or PC8374L'...  No
Probing for `Analog Devices ADM1027'...                     No
Probing for `Analog Devices ADT7460 or ADT7463'...          No
Probing for `SMSC EMC6D100 or EMC6D101'...                  No
Probing for `SMSC EMC6D102'...                              No
Probing for `SMSC EMC6D103'...                              No
Probing for `SMSC EMC6D103S or EMC2300'...                  No
Probing for `SMSC EMC6W201'...                              No
Probing for `Winbond WPCD377I'...                           No
Probing for `Analog Devices ADT7473'...                     No
Probing for `Analog Devices ADT7476'...                     No
Probing for `Analog Devices ADT7490'...                     No
Probing for `Andigilog aSC7611'...                          No
Probing for `Andigilog aSC7621'...                          No
Probing for `National Semiconductor LM87'...                No
Probing for `Analog Devices ADM1024'...                     No
Probing for `National Semiconductor LM93'...                No
Probing for `National Semiconductor LM94 or LM96194'...     No
Probing for `Winbond W83781D'...                            No
Probing for `Winbond W83782D'...                            No
Probing for `Winbond W83783S'...                            No
Probing for `Winbond W83791D'...                            No
Probing for `Winbond W83792D'...                            No
Probing for `Winbond W83793R/G'...                          No
Probing for `Nuvoton W83795G/ADG'...                        No
Probing for `Nuvoton NCT7802Y'...                           No
Probing for `Winbond W83627HF'...                           No
Probing for `Winbond W83627EHF'...                          No
Probing for `Winbond W83627DHG/W83667HG/W83677HG'...        No
Probing for `Asus AS99127F (rev.1)'...                      No
Probing for `Asus AS99127F (rev.2)'...                      No
Probing for `Winbond W83L784R/AR/G'...                      No
Probing for `Winbond W83L785R/G'...                         No
Probing for `Genesys Logic GL518SM'...                      No
Probing for `Genesys Logic GL520SM'...                      No
Probing for `Genesys Logic GL525SM'...                      No
Probing for `Analog Devices ADM9240'...                     No
Probing for `Dallas Semiconductor DS1780'...                No
Probing for `National Semiconductor LM81'...                No
Probing for `Analog Devices ADM1026'...                     No
Probing for `Analog Devices ADM1025'...                     No
Probing for `Philips NE1619'...                             No
Probing for `Texas Instruments AMC6821'...                  No
Probing for `Analog Devices ADM1029'...                     No
Probing for `Analog Devices ADM1030'...                     No
Probing for `Analog Devices ADM1031'...                     No
Probing for `Analog Devices ADM1022'...                     No
Probing for `Texas Instruments THMC50'...                   No
Probing for `VIA VT1211 (I2C)'...                           No
Probing for `ITE IT8712F'...                                No
Probing for `ALi M5879'...                                  No
Probing for `SMSC LPC47M15x/192/292/997'...                 No
Probing for `SMSC DME1737'...                               No
Probing for `SMSC SCH5027D-NW'...                           No
Probing for `Fintek F75373S/SG'...                          No
Probing for `Fintek F75375S/SP'...                          No
Probing for `Fintek F75387SG/RG'...                         No
Probing for `Winbond W83791SD'...                           No
Client found at address 0x2e
Probing for `Myson MTP008'...                               No
Probing for `National Semiconductor LM78'...                No
Probing for `National Semiconductor LM79'...                No
Probing for `National Semiconductor LM80'...                No
Probing for `National Semiconductor LM96080'...             No
Probing for `TI / National Semiconductor ADC128D818'...     No
Probing for `National Semiconductor LM85'...                No
Probing for `National Semiconductor LM96000 or PC8374L'...  No
Probing for `Analog Devices ADM1027'...                     No
Probing for `Analog Devices ADT7460 or ADT7463'...          No
Probing for `SMSC EMC6D100 or EMC6D101'...                  No
Probing for `SMSC EMC6D102'...                              No
Probing for `SMSC EMC6D103'...                              No
Probing for `SMSC EMC6D103S or EMC2300'...                  No
Probing for `SMSC EMC6W201'...                              No
Probing for `Winbond WPCD377I'...                           No
Probing for `Analog Devices ADT7467 or ADT7468'...          No
Probing for `Analog Devices ADT7470'...                     No
Probing for `Analog Devices ADT7473'...                     No
Probing for `Analog Devices ADT7475'...                     No
Probing for `Analog Devices ADT7476'...                     No
Probing for `Analog Devices ADT7490'...                     No
Probing for `Andigilog aSC7611'...                          No
Probing for `Andigilog aSC7621'...                          No
Probing for `National Semiconductor LM87'...                No
Probing for `Analog Devices ADM1024'...                     No
Probing for `National Semiconductor LM93'...                No
Probing for `National Semiconductor LM94 or LM96194'...     No
Probing for `Winbond W83781D'...                            No
Probing for `Winbond W83782D'...                            No
Probing for `Winbond W83791D'...                            No
Probing for `Winbond W83792D'...                            No
Probing for `Winbond W83793R/G'...                          No
Probing for `Nuvoton W83795G/ADG'...                        No
Probing for `Nuvoton NCT7802Y'...                           No
Probing for `Nuvoton NCT7904D'...                           No
Probing for `Winbond W83627HF'...                           No
Probing for `Winbond W83627EHF'...                          No
Probing for `Winbond W83627DHG/W83667HG/W83677HG'...        No
Probing for `Asus AS99127F (rev.1)'...                      No
Probing for `Asus AS99127F (rev.2)'...                      No
Probing for `Winbond W83L786NR/NG/R/G'...                   No
Probing for `Winbond W83L785TS-S'...                        No
Probing for `Analog Devices ADM9240'...                     No
Probing for `Dallas Semiconductor DS1780'...                No
Probing for `National Semiconductor LM81'...                No
Probing for `Analog Devices ADM1026'...                     No
Probing for `Analog Devices ADM1025'...                     No
Probing for `Maxim MAX6639'...                              No
Probing for `Texas Instruments AMC6821'...                  No
Probing for `Analog Devices ADM1029'...                     No
Probing for `Analog Devices ADM1030'...                     No
Probing for `Analog Devices ADM1031'...                     No
Probing for `Analog Devices ADM1022'...                     No
Probing for `Texas Instruments THMC50'...                   No
Probing for `Analog Devices ADM1028'...                     No
Probing for `Texas Instruments THMC51'...                   No
Probing for `ITE IT8712F'...                                No
Probing for `SMSC DME1737'...                               No
Probing for `SMSC SCH5027D-NW'...                           No
Probing for `SMSC EMC2103'...                               No
Probing for `Fintek F75373S/SG'...                          No
Probing for `Fintek F75375S/SP'...                          No
Probing for `Fintek F75387SG/RG'...                         No
Probing for `Winbond W83791SD'...                           No
Client found at address 0x2f
Probing for `National Semiconductor LM78'...                No
Probing for `National Semiconductor LM79'...                No
Probing for `National Semiconductor LM80'...                No
Probing for `National Semiconductor LM96080'...             No
Probing for `TI / National Semiconductor ADC128D818'...     No
Probing for `Analog Devices ADT7470'...                     No
Probing for `Winbond W83781D'...                            No
Probing for `Winbond W83782D'...                            No
Probing for `Winbond W83791D'...                            No
Probing for `Winbond W83792D'...                            No
Probing for `Winbond W83793R/G'...                          No
Probing for `Nuvoton W83795G/ADG'...                        No
Probing for `Nuvoton NCT7802Y'...                           No
Probing for `Winbond W83627HF'...                           No
Probing for `Winbond W83627EHF'...                          No
Probing for `Winbond W83627DHG/W83667HG/W83677HG'...        No
Probing for `Asus AS99127F (rev.1)'...                      No
Probing for `Asus AS99127F (rev.2)'...                      No
Probing for `Winbond W83L786NR/NG/R/G'...                   No
Probing for `Analog Devices ADM9240'...                     No
Probing for `National Semiconductor LM81'...                No
Probing for `Maxim MAX6639'...                              No
Probing for `Analog Devices ADM1029'...                     No
Probing for `ITE IT8712F'...                                No
Probing for `SMSC EMC2104'...                               No
Probing for `Fintek custom power control IC'...             No
Probing for `Winbond W83791SD'...                           No
Client found at address 0x48
Probing for `National Semiconductor LM75'...                No
Probing for `National Semiconductor LM75A'...               No
Probing for `Dallas Semiconductor DS75'...                  No
Probing for `National Semiconductor LM77'...                No
Probing for `Analog Devices ADT7410/ADT7420'...             No
Probing for `Analog Devices ADT7411'...                     No
Probing for `Maxim MAX6642'...                              No
Probing for `Texas Instruments TMP435'...                   No
Probing for `National Semiconductor LM73'...                No
Probing for `National Semiconductor LM92'...                No
Probing for `National Semiconductor LM76'...                No
Probing for `Maxim MAX6633/MAX6634/MAX6635'...              No
Probing for `NXP/Philips SA56004'...                        No
Probing for `SMSC EMC1023'...                               No
Probing for `SMSC EMC1043'...                               No
Probing for `SMSC EMC1053'...                               No
Probing for `SMSC EMC1063'...                               No
Client found at address 0x49
Probing for `National Semiconductor LM75'...                No
Probing for `National Semiconductor LM75A'...               No
Probing for `Dallas Semiconductor DS75'...                  No
Probing for `National Semiconductor LM77'...                No
Probing for `Analog Devices ADT7410/ADT7420'...             No
Probing for `Maxim MAX6642'...                              No
Probing for `Texas Instruments TMP435'...                   No
Probing for `National Semiconductor LM73'...                No
Probing for `National Semiconductor LM92'...                No
Probing for `National Semiconductor LM76'...                No
Probing for `Maxim MAX6633/MAX6634/MAX6635'...              No
Probing for `NXP/Philips SA56004'...                        No
Probing for `SMSC EMC1023'...                               No
Probing for `SMSC EMC1043'...                               No
Probing for `SMSC EMC1053'...                               No
Probing for `SMSC EMC1063'...                               No
Client found at address 0x4a
Probing for `National Semiconductor LM75'...                No
Probing for `National Semiconductor LM75A'...               No
Probing for `Dallas Semiconductor DS75'...                  No
Probing for `National Semiconductor LM77'...                No
Probing for `Analog Devices ADT7410/ADT7420'...             No
Probing for `Analog Devices ADT7411'...                     No
Probing for `Maxim MAX6642'...                              No
Probing for `Texas Instruments TMP435'...                   No
Probing for `National Semiconductor LM73'...                No
Probing for `National Semiconductor LM92'...                No
Probing for `National Semiconductor LM76'...                No
Probing for `Maxim MAX6633/MAX6634/MAX6635'...              No
Probing for `NXP/Philips SA56004'...                        No
Client found at address 0x4b
Probing for `National Semiconductor LM75'...                No
Probing for `National Semiconductor LM75A'...               No
Probing for `Dallas Semiconductor DS75'...                  No
Probing for `National Semiconductor LM77'...                No
Probing for `Analog Devices ADT7410/ADT7420'...             No
Probing for `Analog Devices ADT7411'...                     No
Probing for `Maxim MAX6642'...                              No
Probing for `Texas Instruments TMP435'...                   No
Probing for `National Semiconductor LM92'...                No
Probing for `National Semiconductor LM76'...                No
Probing for `Maxim MAX6633/MAX6634/MAX6635'...              No
Probing for `NXP/Philips SA56004'...                        No
Probing for `Analog Devices ADT7481'...                     No
Client found at address 0x4c
Probing for `National Semiconductor LM75'...                No
Probing for `National Semiconductor LM75A'...               No
Probing for `Dallas Semiconductor DS75'...                  No
Probing for `Analog Devices ADT7466'...                     No
Probing for `Andigilog aSC7511'...                          No
Probing for `Analog Devices ADM1021'...                     No
Probing for `Analog Devices ADM1021A/ADM1023'...            No
Probing for `Global Mixed-mode Technology G781'...          No
Probing for `Maxim MAX1617'...                              No
Probing for `Maxim MAX1617A'...                             No
Probing for `Maxim MAX1668'...                              No
Probing for `Maxim MAX1805'...                              No
Probing for `Maxim MAX1989'...                              No
Probing for `Maxim MAX6642'...                              No
Probing for `Maxim MAX6655/MAX6656'...                      No
Probing for `TI THMC10'...                                  No
Probing for `National Semiconductor LM84'...                No
Probing for `Genesys Logic GL523SM'...                      No
Probing for `Onsemi MC1066'...                              No
Probing for `Maxim MAX1618'...                              No
Probing for `Maxim MAX1619'...                              No
Probing for `National Semiconductor LM82/LM83'...           No
Probing for `National Semiconductor LM90'...                No
Probing for `National Semiconductor LM89/LM99'...           No
Probing for `National Semiconductor LM86'...                No
Probing for `Analog Devices ADM1032'...                     No
Probing for `Maxim MAX6654'...                              No
Probing for `Maxim MAX6690'...                              No
Probing for `Maxim MAX6657/MAX6658/MAX6659'...              No
Probing for `Maxim MAX6648/MAX6649/MAX6692'...              No
Probing for `Maxim MAX6680/MAX6681'...                      No
Probing for `Maxim MAX6695/MAX6696'...                      No
Probing for `Winbond W83L771W/G'...                         No
Probing for `Winbond W83L771AWG/ASG'...                     No
Probing for `Texas Instruments TMP400'...                   No
Probing for `Texas Instruments TMP401'...                   No
Probing for `Texas Instruments TMP411A'...                  No
Probing for `Texas Instruments TMP421'...                   No
Probing for `Texas Instruments TMP422'...                   No
Probing for `Texas Instruments TMP423'...                   No
Probing for `Texas Instruments TMP431'...                   No
Probing for `Texas Instruments TMP432'...                   No
Probing for `Texas Instruments TMP435'...                   No
Probing for `Texas Instruments TMP441'...                   No
Probing for `Texas Instruments TMP442'...                   No
Probing for `Texas Instruments TMP451'...                   No
Probing for `Texas Instruments AMC6821'...                  No
Probing for `National Semiconductor LM95235'...             No
Probing for `National Semiconductor LM95245'...             No
Probing for `National Semiconductor LM63'...                No
Probing for `National Semiconductor LM96163'...             No
Probing for `Fintek F75363SG'...                            No
Probing for `National Semiconductor LM73'...                No
Probing for `Maxim MAX6633/MAX6634/MAX6635'...              No
Probing for `Analog Devices ADT7461'...                     No
Probing for `Analog Devices ADT7461A, ON Semiconductor NCT1008'... No
Probing for `NXP/Philips SA56004'...                        No
Probing for `Analog Devices ADT7481'...                     No
Probing for `Fintek F75383S/M'...                           No
Probing for `SMSC EMC1002'...                               No
Probing for `SMSC EMC1023'...                               No
Probing for `SMSC EMC1033'...                               No
Probing for `SMSC EMC1043'...                               No
Probing for `SMSC EMC1046'...                               No
Probing for `SMSC EMC1053'...                               No
Probing for `SMSC EMC1063'...                               No
Probing for `SMSC EMC1072'...                               No
Probing for `SMSC EMC1073'...                               No
Probing for `SMSC EMC1074'...                               No
Probing for `SMSC EMC1402'...                               No
Probing for `SMSC EMC1403'...                               No
Probing for `SMSC EMC1404'...                               No
Probing for `SMSC EMC1422'...                               No
Probing for `SMSC EMC1423'...                               No
Probing for `SMSC EMC1424'...                               No
Client found at address 0x4d
Probing for `National Semiconductor LM75'...                No
Probing for `National Semiconductor LM75A'...               No
Probing for `Dallas Semiconductor DS75'...                  No
Probing for `Analog Devices ADM1021'...                     No
Probing for `Analog Devices ADM1021A/ADM1023'...            No
Probing for `Global Mixed-mode Technology G781'...          No
Probing for `Maxim MAX1617'...                              No
Probing for `Maxim MAX1617A'...                             No
Probing for `Maxim MAX1668'...                              No
Probing for `Maxim MAX1805'...                              No
Probing for `Maxim MAX1989'...                              No
Probing for `Maxim MAX6642'...                              No
Probing for `Maxim MAX6655/MAX6656'...                      No
Probing for `TI THMC10'...                                  No
Probing for `National Semiconductor LM84'...                No
Probing for `Genesys Logic GL523SM'...                      No
Probing for `Onsemi MC1066'...                              No
Probing for `Maxim MAX1618'...                              No
Probing for `Maxim MAX1619'...                              No
Probing for `National Semiconductor LM82/LM83'...           No
Probing for `National Semiconductor LM89/LM99'...           No
Probing for `Analog Devices ADM1032'...                     No
Probing for `Maxim MAX6654'...                              No
Probing for `Maxim MAX6690'...                              No
Probing for `Maxim MAX6659'...                              No
Probing for `Maxim MAX6646'...                              No
Probing for `Maxim MAX6680/MAX6681'...                      No
Probing for `Maxim MAX6695/MAX6696'...                      No
Probing for `Texas Instruments TMP400'...                   No
Probing for `Texas Instruments TMP411B'...                  No
Probing for `Texas Instruments TMP421'...                   No
Probing for `Texas Instruments TMP422'...                   No
Probing for `Texas Instruments TMP423'...                   No
Probing for `Texas Instruments TMP431'...                   No
Probing for `Texas Instruments TMP432'...                   No
Probing for `Texas Instruments TMP435'...                   No
Probing for `Texas Instruments TMP441'...                   No
Probing for `Texas Instruments TMP442'...                   No
Probing for `Texas Instruments AMC6821'...                  No
Probing for `National Semiconductor LM95234'...             No
Probing for `National Semiconductor LM95245'...             No
Probing for `National Semiconductor LM73'...                No
Probing for `Maxim MAX6633/MAX6634/MAX6635'...              No
Probing for `Analog Devices ADT7461'...                     No
Probing for `Analog Devices ADT7461A, ON Semiconductor NCT1008'... No
Probing for `NXP/Philips SA56004'...                        No
Probing for `Fintek F75384S/M'...                           No
Probing for `SMSC EMC1002'...                               No
Probing for `SMSC EMC1023'...                               No
Probing for `SMSC EMC1033'...                               No
Probing for `SMSC EMC1043'...                               No
Probing for `SMSC EMC1046'...                               No
Probing for `SMSC EMC1053'...                               No
Probing for `SMSC EMC1063'...                               No
Probing for `SMSC EMC1402'...                               No
Probing for `SMSC EMC1403'...                               No
Probing for `SMSC EMC1404'...                               No
Client found at address 0x4e
Probing for `National Semiconductor LM75'...                No
Probing for `National Semiconductor LM75A'...               No
Probing for `Dallas Semiconductor DS75'...                  No
Probing for `Analog Devices ADM1021'...                     No
Probing for `Analog Devices ADM1021A/ADM1023'...            No
Probing for `Maxim MAX1617'...                              No
Probing for `Maxim MAX1617A'...                             No
Probing for `Maxim MAX1668'...                              No
Probing for `Maxim MAX1805'...                              No
Probing for `Maxim MAX1989'...                              No
Probing for `Maxim MAX6642'...                              No
Probing for `Maxim MAX6655/MAX6656'...                      No
Probing for `TI THMC10'...                                  No
Probing for `National Semiconductor LM84'...                No
Probing for `Genesys Logic GL523SM'...                      No
Probing for `Onsemi MC1066'...                              No
Probing for `Maxim MAX1618'...                              No
Probing for `Maxim MAX1619'...                              No
Probing for `National Semiconductor LM82/LM83'...           No
Probing for `Maxim MAX6654'...                              No
Probing for `Maxim MAX6690'...                              No
Probing for `Maxim MAX6659'...                              No
Probing for `Maxim MAX6647'...                              No
Probing for `Maxim MAX6680/MAX6681'...                      No
Probing for `Maxim MAX6695/MAX6696'...                      No
Probing for `Texas Instruments TMP400'...                   No
Probing for `Texas Instruments TMP411C'...                  No
Probing for `Texas Instruments TMP421'...                   No
Probing for `Texas Instruments TMP422'...                   No
Probing for `Texas Instruments TMP435'...                   No
Probing for `Texas Instruments TMP441'...                   No
Probing for `Texas Instruments AMC6821'...                  No
Probing for `National Semiconductor LM95234'...             No
Probing for `National Semiconductor LM64'...                No
Probing for `National Semiconductor LM73'...                No
Probing for `Maxim MAX6633/MAX6634/MAX6635'...              No
Probing for `NXP/Philips SA56004'...                        No
Probing for `Fintek F75121R/F75122R/RG (VID+GPIO)'...       No
Probing for `Fintek F75111R/RG/N (GPIO)'...                 No
Probing for `ITE IT8201R/IT8203R/IT8206R/IT8266R'...        No
Client found at address 0x58
Probing for `Analog Devices ADT7462'...                     No
Probing for `Andigilog aSC7512'...                          No
Client found at address 0x5c
Probing for `Analog Devices ADT7462'...                     No
Probing for `SMSC EMC1072'...                               No
Probing for `SMSC EMC1073'...                               No
Probing for `SMSC EMC1074'...                               No
Client found at address 0x73
Probing for `FSC Poseidon I'...                             No
Probing for `FSC Poseidon II'...                            No
Probing for `FSC Scylla'...                                 No
Probing for `FSC Hermes'...                                 No
Probing for `FSC Heimdal'...                                No
Probing for `FSC Heracles'...                               No
Probing for `FSC Hades'...                                  No
Probing for `FSC Syleus'...                                 No
Client found at address 0x77
Probing for `Asus Mozart-2'...                              No

Next adapter: i915 gmbus tc5 (i2c-8)
Do you want to scan it? (yes/NO/selectively): yes

Next adapter: i915 gmbus tc6 (i2c-9)
Do you want to scan it? (yes/NO/selectively): yes

Next adapter: AUX A/DDI A/PHY A (i2c-10)
Do you want to scan it? (yes/NO/selectively): yes

Next adapter: AUX USBC1/DDI TC1/PHY TC1 (i2c-11)
Do you want to scan it? (yes/NO/selectively): yes


Now follows a summary of the probes I have just done.
Just press ENTER to continue: 
```

### ② 内核 it87 驱动尝试 —— 失败记录（供参考，勿再走此路）

```
lin@lin-Default-string:~$ sudo modprobe it87
modprobe: ERROR: could not insert 'it87': No such device
lin@lin-Default-string:~$ sudo modprobe it87 force_id=0x8613
modprobe: ERROR: could not insert 'it87': No such device
# dmesg 无 it87 记录；modinfo 正常；/proc/ioports 无 0x2e/2f/a30 保留 → 非资源冲突
# 真因（搜索核实）：IT8613E 不在主线 it87 型号表，需 force_id=0x8622（IT8622E 相似型号）
```

### ③ SuperIO 用户空间探测（/dev/port 验证通道 + LDN 枚举）

> 脚本：进入配置模式（0x2E 写 0x87,0x01,0x55,0x55）→ 读 device ID（0x20/0x21）→ 枚举 LDN
> 注意：脚本中 base 高低字节拼接反了（显示 0x300a 实为 0x0a30），LDN4 base = 0xa30 与 sensors-detect 一致；
> IT8613E 的 HWM 实际在 **LDN7**（enable=0），LDN4 是其上 EC/GPIO 相关

```
lin@lin-Default-string:~$ sudo python3 /tmp/sio_probe.py
chip ID: 0x86 0x13  ->  0x8613
LDN  0: enable=0x00  base=0xf003
LDN  1: enable=0x01  base=0xf803
LDN  2: enable=0x00  base=0xf802
LDN  3: enable=0x00  base=0x7803
LDN  4: enable=0x01  base=0x300a
LDN  5: enable=0x01  base=0x6000
LDN  6: enable=0x01  base=0x0000
LDN  7: enable=0x00  base=0x100a
LDN  8: enable=0x00  base=0x7002
LDN 10: enable=0x00  base=0x1003
```

### ④ it87 驱动加载成功 + hwmon 接口（force_id=0x8622）

```
lin@lin-Default-string:~$ sudo modprobe it87 force_id=0x8622
lin@lin-Default-string:~$ cat /sys/class/hwmon/hwmon*/name
acpitz
nvme
iwlwifi_1
coretemp
it8622
lin@lin-Default-string:~$ for h in /sys/class/hwmon/hwmon*; do echo "== $h =="; ls "$h" | grep -E "fan|pwm"; done
== /sys/class/hwmon/hwmon0 ==
== /sys/class/hwmon/hwmon1 ==
== /sys/class/hwmon/hwmon2 ==
== /sys/class/hwmon/hwmon3 ==
== /sys/class/hwmon/hwmon4 ==
fan2_alarm
fan2_beep
fan2_input
fan2_min
fan3_alarm
fan3_beep
fan3_input
fan3_min
fan4_alarm
fan4_beep
fan4_input
fan4_min
fan5_alarm
fan5_beep
fan5_input
fan5_min
pwm1
pwm1_auto_channels_temp
pwm1_auto_point1_temp
pwm1_auto_point1_temp_hyst
pwm1_auto_point2_temp
pwm1_auto_point3_temp
pwm1_auto_slope
pwm1_auto_start
pwm1_enable
pwm1_freq
pwm2
pwm2_auto_channels_temp
pwm2_auto_point1_temp
pwm2_auto_point1_temp_hyst
pwm2_auto_point2_temp
pwm2_auto_point3_temp
pwm2_auto_slope
pwm2_auto_start
pwm2_enable
pwm2_freq
pwm3
pwm3_auto_channels_temp
pwm3_auto_point1_temp
pwm3_auto_point1_temp_hyst
pwm3_auto_point2_temp
pwm3_auto_point3_temp
pwm3_auto_slope
pwm3_auto_start
pwm3_enable
pwm3_freq
pwm4
pwm4_auto_channels_temp
pwm4_auto_point1_temp
pwm4_auto_point1_temp_hyst
pwm4_auto_point2_temp
pwm4_auto_point3_temp
pwm4_auto_slope
pwm4_enable
pwm4_freq
pwm5
pwm5_auto_channels_temp
pwm5_auto_point1_temp
pwm5_auto_point1_temp_hyst
pwm5_auto_point2_temp
pwm5_auto_point3_temp
pwm5_auto_slope
pwm5_enable
pwm5_freq
```

### ⑤ sensors 读数 —— 芯片状态确认（fan2 真实风扇，temp1=PECI）

```
lin@lin-Default-string:~$ sensors
it8622-isa-0a30
Adapter: ISA adapter
in0:         768.00 mV (min =  +0.00 V, max =  +3.06 V)
in1:           1.37 V  (min =  +0.00 V, max =  +3.06 V)
in2:           2.18 V  (min =  +0.00 V, max =  +3.06 V)
in3:           2.35 V  (min =  +0.00 V, max =  +3.06 V)
in4:           2.26 V  (min =  +0.00 V, max =  +3.06 V)
in5:           2.24 V  (min =  +0.00 V, max =  +3.06 V)
in6:           1.49 V  (min =  +0.00 V, max =  +3.06 V)
3VSB:          3.48 V  (min =  +0.00 V, max =  +6.12 V)
Vbat:          3.41 V  
+3.3V:         3.62 V  
fan2:        1956 RPM  (min =    0 RPM)
fan3:           0 RPM  (min =    0 RPM)
fan4:           0 RPM  (min =    0 RPM)
fan5:           0 RPM  (min =    0 RPM)
temp1:        +41.0°C  (low  =  +1.0°C, high = +110.0°C)  sensor = Intel PECI
temp2:       +127.0°C  (low  =  +1.0°C, high = +110.0°C)  ALARM  sensor = thermistor
temp3:        +41.0°C  (low  =  +1.0°C, high = +110.0°C)
temp4:        -78.0°C  
intrusion0:  ALARM

iwlwifi_1-virtual-0
Adapter: Virtual device
temp1:        +55.0°C  

acpitz-acpi-0
Adapter: ACPI interface
temp1:        +27.8°C  

coretemp-isa-0000
Adapter: ISA adapter
Package id 0:  +46.0°C  (high = +105.0°C, crit = +105.0°C)
Core 0:        +45.0°C  (high = +105.0°C, crit = +105.0°C)
Core 1:        +45.0°C  (high = +105.0°C, crit = +105.0°C)
Core 2:        +45.0°C  (high = +105.0°C, crit = +105.0°C)
Core 3:        +45.0°C  (high = +105.0°C, crit = +105.0°C)

nvme-pci-0300
Adapter: PCI adapter
Composite:    +43.9°C  (low  = -273.1°C, high = +68.8°C)
                       (crit = +71.8°C)
Sensor 1:     +43.9°C  (low  = -273.1°C, high = +65261.8°C)
Sensor 2:     +49.9°C  (low  = -273.1°C, high = +65261.8°C)
```

### ⑥ PWM 调速验证 —— 实测数据链（pwm2 ↔ fan2）

> pwm2_enable: 2(自动) → 写 1 → 读回 1（通道未被锁）；pwm2 越界（300/280/260）被内核拒绝；
> 写 300 失败后 fan2 瞬时 3515 是 250 档未稳定瞬态，非 300 生效。

```
lin@lin-Default-string:~$ cat /sys/class/hwmon/hwmon4/pwm{1,2,3,4,5}_enable
1
2
2
1
1
lin@lin-Default-string:~$ cat /sys/class/hwmon/hwmon4/pwm{1,2,3,4,5}
128
100
100
100
127
lin@lin-Default-string:~$ echo 1 | sudo tee /sys/class/hwmon/hwmon4/pwm2_enable
1
lin@lin-Default-string:~$ cat /sys/class/hwmon/hwmon4/pwm2_enable 
1
lin@lin-Default-string:~$ cat /sys/class/hwmon/hwmon4/pwm{1,2,3,4,5}_enable
1
1
2
1
1
lin@lin-Default-string:~$ cat /sys/class/hwmon/hwmon4/pwm{1,2,3,4,5}
128
100
100
100
127
lin@lin-Default-string:~$ echo 150 | sudo tee /sys/class/hwmon/hwmon4/pwm2
150
lin@lin-Default-string:~$ cat /sys/class/hwmon/hwmon4/pwm{1,2,3,4,5}_enable
1
1
2
1
1
lin@lin-Default-string:~$ cat /sys/class/hwmon/hwmon4/pwm{1,2,3,4,5}
128
150
100
100
127
lin@lin-Default-string:~$ cat /sys/class/hwmon/hwmon4/pwm2
150
lin@lin-Default-string:~$ cat /sys/class/hwmon/hwmon4/fan2_input 
2537
lin@lin-Default-string:~$ cat /sys/class/hwmon/hwmon4/fan2_input 
2537
lin@lin-Default-string:~$ echo 200 | sudo tee /sys/class/hwmon/hwmon4/pwm2
200
lin@lin-Default-string:~$ cat /sys/class/hwmon/hwmon4/fan2_input 
3068
lin@lin-Default-string:~$ echo 250 | sudo tee /sys/class/hwmon/hwmon4/pwm2
250
lin@lin-Default-string:~$ cat /sys/class/hwmon/hwmon4/fan2_input 
3214
lin@lin-Default-string:~$ echo 300 | sudo tee /sys/class/hwmon/hwmon4/pwm2
300
tee: /sys/class/hwmon/hwmon4/pwm2: 无效的参数
lin@lin-Default-string:~$ cat /sys/class/hwmon/hwmon4/fan2_input 
3515
lin@lin-Default-string:~$ echo 280 | sudo tee /sys/class/hwmon/hwmon4/pwm2
280
tee: /sys/class/hwmon/hwmon4/pwm2: 无效的参数
lin@lin-Default-string:~$ cat /sys/class/hwmon/hwmon4/fan2_input 
3515
lin@lin-Default-string:~$ echo 260 | sudo tee /sys/class/hwmon/hwmon4/pwm2
260
tee: /sys/class/hwmon/hwmon4/pwm2: 无效的参数
lin@lin-Default-string:~$ echo 255 | sudo tee /sys/class/hwmon/hwmon4/pwm2
255
lin@lin-Default-string:~$ cat /sys/class/hwmon/hwmon4/fan2_input 
3534
```

---

## 实测数据汇总（pwm2 → fan2 RPM）

| pwm2 | fan2 RPM | 备注 |
|:---|:---|:---|
| 100（自动曲线值） | 1956 | 芯片自动模式 |
| 150 | 2537 | 手动 |
| 200 | 3068 | 手动，中段线性 |
| 250 | 3214 | 增速放缓（饱和前兆） |
| 255 | 3534 | 满速 |
| 300/280/260 | — | 越界，内核拒绝（范围 0-255） |

> 完整排障回顾（7 条路径 + 来源 + 教训）：[retrospect/2026-08-24_n97_fan_control.md](../retrospect/2026-08-24_n97_fan_control.md)
