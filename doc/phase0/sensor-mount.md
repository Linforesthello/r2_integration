# R2 传感器安装定义（车体物理安装）

> 最后更新: 2026-08-03
> 目的: 车体坐标系基准、各模块物理安装位置与朝向 —— 静态 TF 与 IMU 轴映射的依据
> 关联: [chassis_definition.md](chassis_definition.md)（底盘运动学定义）、[g354-wiring.md](../phase1/g354-wiring.md)

---

## 一、车体坐标系（REP-103）

```
        前 (x⁺)
         ↑
   左 ←───┼───→ 右      y⁺ 左, z⁺ 上
         ↓
        后
```

| 轴 | 正向 | 说明 |
|:--:|:-----|:-----|
| x | 车前 | 前进方向 |
| y | 车左 | 侧向 |
| z | 车上 | 竖直向上 |

---

## 二、车体基本参数

| 参数 | 值 | 说明 |
|:-----|:---:|:-----|
| 底盘离地高度 | 13 cm | base_footprint（地面）→ base_link 的高度 |

---

## 三、模块安装

### 3.1 G354 IMU

| 项目 | 值 | 说明 |
|:-----|:---|:-----|
| 安装位置 | **(-30, 0, +20) cm** | ⚠️ 基准待确认（base_footprint 或 base_link），见第四节 |
| 传感器轴向 | **x 朝车左、y 朝车前、z 朝车下** | **G354 出厂轴定义**（模块正放安装即此朝向，非标准 REP-103） |
| 驱动参数 | `mount_axes:=y_front_x_left_z_down` | imu_node 内做轴映射（传感器系→车体系） |
| 静态 TF | 单位变换（旋转为 0，因数据已映射到车体系） | 平移待基准确认后补齐 |

**传感器轴系**（G354 出厂定义，模块正放时相对车体）：

```
    传感器 y → 车前(x⁺)
    传感器 x → 车左(y⁺)
    传感器 z → 车下(z⁻)
```

### 3.2 VLP-16 雷达

| 项目 | 值 | 说明 |
|:-----|:---|:-----|
| 安装位置 | **(0, 0, +65) cm** | ⚠️ 基准待确认；与旧记录（base_footprint→velodyne z=0.77m）冲突，见第四节 |
| 安装方式 | 车顶水平安装（z 轴朝上） | frame_id: velodyne |
| 静态 TF | `robot_state_publisher` 发布 base_footprint→base_link→velodyne | 由 velodyne_n97.launch.py 启动 |

---

## 四、待确认项（影响静态 TF 平移，不影响姿态）

| # | 问题 | 现状 | 影响 |
|:--|:-----|:-----|:-----|
| 1 | IMU/雷达坐标的**基准系**是 base_footprint（地面投影）还是 base_link（底盘中心）？ | 未知 | 静态 TF 平移值（差 13cm 及坐标系原点） |
| 2 | 雷达高度 **65cm vs 旧记录 77cm** 哪个对？ | 冲突 | 同上（若 77cm 为真需更新 TF） |

> 备注：当前 IMU 轴映射 + 静态 TF 单位旋转下，EKF 姿态/航向已正确（8-03 实车验证）；
> 平移只影响 TF 树的显示位置与 IMU 加速度处理（当前 EKF 不融合加速度，无实际影响）。

---

## 五、相关文件

- 运动学定义/参数: `phase0/chassis_definition.md`、`r2_bringup/config/r2_params.yaml`
- IMU 轴映射实现: `g354_driver/g354_imu_driver/imu_node.py`（`mount_axes` 参数）
- 雷达驱动: `~/.ros/velodyne_n97.launch.py`（N97）
- 排障记录: `retrospect/2026-08-02_ekf_tf_fusion_fix.md`（3.5 节 IMU 朝向修复）
