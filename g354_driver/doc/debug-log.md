# G354 IMU 驱动 · 调试日志

> 各次调试中遇到的问题和解决方案

---

## 2026-07-30 · JLink VCP 空读异常

**问题**：`test_g354.py` 运行约 12 帧后崩溃：

```
运行错误: device reports readiness to read but returned no data
```

**原因**：pyserial 在 CDC ACM 设备（JLink VCP）上的已知行为 —— `in_waiting` 报告有数据，但 `read()` 返回空字节，触发 `SerialException`。

**修复**：
- 在 `test_g354.py` 中增加 `try/except serial.SerialException` + 空读保护
- 空读时 `continue` 跳过，异常时重试
- `scripts/test_g354.py` 已修复

---

## 2026-07-30 · 旧互补滤波姿态漂移大

**问题**：原 `imu_node.py` 使用欧拉角互补滤波，小范围动作返回后误差达十几度。

**原因**：
1. 无陀螺仪零偏校准 → 零偏一直积分
2. 欧拉角积分 → 大角度时轴耦合
3. α=0.98 → 加速度计修正极慢（占 2%）
4. 无运动检测 → 运动时加速度计参考被污染

**修复**：
- 重写为四元数 Mahony 滤波
- 增加启动时 250 帧静态零偏校准
- 增加运动检测（`|acc| ∈ [0.85, 1.15]g`）
- 静止时漂移从 ~0.5°/s 降至接近 0

---

## 2026-07-30 · 36 字节 vs 38 字节帧

**问题**：参考仓库使用 38 字节帧（含 CHECKSUM），而我们用 36 字节帧。

**结论**：两种都是 G354 的合法配置，取决于 `BURST_CTRL1/BURST_CTRL2` 设置。36 字节帧运行稳定，无需改动。
