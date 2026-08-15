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
| 安装位置 | **(-30, 0, +20) cm**（base_link 系） | ⏳ 平移待实测（静态 TF 当前为单位变换，见第四节 #3） |
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
| 安装位置 | **(0, 0, +56) cm** | ✅ 实测定案（2026-08-06）：base_link→velodyne；雷达光学中心离地 **69cm**，base_link 离地 13cm（69-13=56） |
| 安装方式 | 车顶水平安装（z 轴朝上） | frame_id: velodyne |
| 静态 TF | `robot_state_publisher` 发布 base_link→velodyne（z=0.56） | 由 velodyne.launch.py（r2_sensors 包内）启动；base_footprint 已删除（双父冲突） |

---

## 四、坐标基准定案（2026-08-06 实测）

| # | 问题 | 定案 |
|:--|:-----|:-----|
| 1 | IMU/雷达坐标的**基准系**？ | ✅ **base_link = 车体底盘正中心，离地 13cm**（实测）；base_footprint 已从 URDF 删除（TF2 双父冲突，无人使用） |
| 2 | 雷达高度 **65cm vs 77cm** 哪个对？ | ✅ **雷达光学中心离地 69cm**（实测）；base_link→velodyne = 0.56m（69-13）；URDF 已更新（备份 .bak_20260806） |
| 3 | G354 IMU 安装位置 (-30, 0, +20)cm | ⏳ 待实测（本次未量测，当前静态 TF 为单位变换，平移待补） |

> 备注：当前 IMU 轴映射 + 静态 TF 单位旋转下，EKF 姿态/航向已正确（8-03 实车验证）；
> 平移只影响 TF 树的显示位置与 IMU 加速度处理（当前 EKF 不融合加速度，无实际影响）。

---

## 五、相关文件

- 运动学定义/参数: `phase0/chassis_definition.md`、`r2_bringup/config/r2_params.yaml`
- IMU 轴映射实现: `g354_driver/g354_imu_driver/imu_node.py`（`mount_axes` 参数）
- 雷达驱动: `r2_sensors velodyne.launch.py`（N97）
- 排障记录: `retrospect/2026-08-02_ekf_tf_fusion_fix.md`（3.5 节 IMU 朝向修复）
