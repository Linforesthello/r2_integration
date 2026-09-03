#!/usr/bin/env python3
"""W3 避障验收 bag 全局浏览：轨迹/速度/前向距离/事件段全量解析

用途: 08-25 W3 避障实车 3 个 bag（nav2_avoid_0825_1357/1401/1405）的全局浏览，
      产出: goal 列表、轨迹/速度统计、运动段、减速/停车事件（A=cmd_smoothed 决策 / B=odom30Hz 实际
      双通道）、接近窗口（fwd<2.5m，按运动切子块: 静止摘要/运动逐帧 0.1s 粒度）

方法: 官方 rosbag2_py 全量读取（无采样，dt=scan 0.1s / odom 0.033s）；scan↔cmd 对齐 argmin 最近帧
      误差 ≤0.05s；前向 fwd = 车头 ±30° 扇区最小有限距离（scan 0° = velodyne +x = 车头，正装）；
      减速事件 = 0.6s 窗口内 |v| 从 >0.10 降到 <0.03（起点去重 <1s）

用法: python3 browse_avoid_bags.py [bag1 bag2 ...]   # 默认三个 bag
依赖: rosbag2_py / rclpy（ROS2 自带，零第三方）
关联: 输出留档 out/avoid_0825_1357_1401_1405_full.txt；根因结论见 retrospect/（待定稿）
"""
import sys, os, rosbag2_py, numpy as np
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

BAGS = sys.argv[1:] or ["nav2_avoid_0825_1357", "nav2_avoid_0825_1401", "nav2_avoid_0825_1405"]
BAG_DIR = os.path.expanduser("~/Lin_workspace/r2_integration/bags/raw")
FWD_ANGLE = 0.52  # 车头 ±30°

def load(bag):
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=os.path.join(BAG_DIR, bag), storage_id="sqlite3"),
           rosbag2_py.ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"))
    r.set_filter(rosbag2_py.StorageFilter(topics=["/scan","/odometry/filtered","/cmd_vel_smoothed","/goal_pose","/amcl_pose"]))
    types = {}
    for t in r.get_all_topics_and_types(): types[t.name] = t.type
    scans, odoms, cvs, goals, amcls = [], [], [], [], []
    t0 = None
    while r.has_next():
        topic, data, ts = r.read_next()
        if t0 is None: t0 = ts
        t = (ts - t0) * 1e-9
        if topic == "/scan":
            m = deserialize_message(data, get_message(types[topic]))
            a = np.array(m.ranges, dtype=np.float32)
            finite = np.isfinite(a)
            if not finite.any(): continue
            ang = m.angle_min + np.arange(len(a)) * m.angle_increment
            fwd = a[(ang >= -FWD_ANGLE) & (ang <= FWD_ANGLE) & finite]
            mn = a[finite].min(); argmn = ang[finite][np.argmin(a[finite])]
            scans.append((t, mn if len(fwd) else np.inf, fwd.min() if len(fwd) else np.inf, argmn))
        elif topic == "/odometry/filtered":
            m = deserialize_message(data, get_message(types[topic]))
            q = m.pose.pose.orientation
            yaw = np.arctan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
            cvs.append((t, m.pose.pose.position.x, m.pose.pose.position.y, yaw,
                        m.twist.twist.linear.x, m.twist.twist.linear.y, m.twist.twist.angular.z))
        elif topic == "/cmd_vel_smoothed":
            m = deserialize_message(data, get_message(types[topic]))
            cvs.append((t, None, None, None, m.linear.x, m.linear.y, m.angular.z))
        elif topic == "/goal_pose":
            m = deserialize_message(data, get_message(types[topic]))
            goals.append((t, m.pose.position.x, m.pose.position.y))
        elif topic == "/amcl_pose":
            m = deserialize_message(data, get_message(types[topic]))
            amcls.append((t, m.pose.pose.position.x, m.pose.pose.position.y))
    scans = np.array(scans); goals = np.array(goals)
    return scans, cvs, goals, np.array(amcls)

def summarize(name, scans, cvs, goals, amcls):
    print(f"\n{'='*78}\n### {name}")
    if len(cvs):
        c = np.array(cvs, dtype=float)
        # odom 帧与 cmd 帧合并（None 列补齐）
    print(f"scan帧={len(scans)}  cmd帧={len(cvs)}  goal数={len(goals)}  amcl帧={len(amcls)}")
    # --- goal 列表
    if len(goals):
        print("goal_pose 列表:")
        for g in goals: print(f"   t={g[0]:7.1f}s  x={g[1]:7.3f} y={g[2]:7.3f}")
    # --- 轨迹（odom）
    od = [x for x in cvs if x[1] is not None]
    if len(od):
        o = np.array(od, dtype=float)
        t, x, y, yaw, vx, vy, wz = o.T
        disp = np.sqrt((x[-1]-x[0])**2 + (y[-1]-y[0])**2)
        print(f"轨迹: 起点({x[0]:.2f},{y[0]:.2f}) 终点({x[-1]:.2f},{y[-1]:.2f}) 直线位移={disp:.2f}m 全程t={t[-1]:.1f}s")
        print(f"速度: vx_max={np.abs(vx).max():.2f} vy_max={np.abs(vy).max():.2f} wz_max={np.abs(wz).max():.2f} |v|均值={np.hypot(vx,vy).mean():.3f}")
    # --- scan 距离统计
    if len(scans):
        mn = scans[:,1]; fwd = scans[:,2]
        print(f"scan: 全向最近min={np.nanmin(mn):.2f}m 前向±30°最近min={np.nanmin(fwd):.2f}m")
        print(f"       前向距离分布: <0.8m {np.sum(fwd<0.8)}帧  <1.5m {np.sum(fwd<1.5)}帧  <2.5m {np.sum(fwd<2.5)}帧  共{len(fwd)}帧")
    # --- 运动/静止分段（用 cmd_vel_smoothed，vx/vy）
    cm = [x for x in cvs if x[1] is None]
    if len(cm):
        c = np.array(cm, dtype=float)
        tc, vx, vy, wz = c[:,0], c[:,4], c[:,5], c[:,6]
        v = np.hypot(vx, vy); moving = v > 0.03
        # 运动段
        segs = []; start = None
        for i in range(len(tc)):
            if moving[i] and start is None: start = i
            elif not moving[i] and start is not None:
                if tc[i-1]-tc[start] > 0.8: segs.append((tc[start], tc[i-1]))
                start = None
        if start is not None and tc[-1]-tc[start] > 0.8: segs.append((tc[start], tc[-1]))
        print(f"运动段(>0.8s, |v|>0.03): {len(segs)}段")
        for s0, s1 in segs:
            m = (tc>=s0)&(tc<=s1)
            mvx, mvy = np.abs(vx[m]).max(), np.abs(vy[m]).max()
            kind = "直行" if mvx>0.08 and mvy<0.08 else ("平移" if mvy>0.08 and mvx<0.08 else ("旋转为主" if np.abs(wz[m]).max()>0.3 else "混合"))
            if len(scans):
                f = fwd[(scans[:,0]>=s0)&(scans[:,0]<=s1)]; fmin = f.min() if len(f) else np.inf
                fd = f" 途中前向最近={fmin:.2f}m"
            else: fd = ""
            print(f"   [{s0:6.1f}~{s1:6.1f}] 时长{s1-s0:5.1f}s {kind} |v|max={np.hypot(mvx,mvy):.2f}{fd}")
        # 减速/停车事件：双通道（0.6s 窗口内 |v| 从 >0.10 降至 <0.03）
        #   A: cmd_vel_smoothed（MPPI 决策）
        #   B: odometry 30Hz（实际运动）
        print("减速/停车事件(0.6s内从>0.10降到<0.03): A=cmd(决策) B=odom(实际)")
        def detect_dec(vt, vv):
            ev = []
            for i in range(len(vv)):
                if vv[i] > 0.10:
                    j = i
                    while j < len(vv) and vt[j] - vt[i] < 0.6: j += 1
                    win = vv[i:j+1]
                    if win.min() < 0.03:
                        k = i + int(np.argmin(win))
                        f = fwd[np.abs(scans[:,0]-vt[k]).argmin()] if len(scans) else np.inf
                        ev.append((vt[i], vt[k], vv[i], win.min(), f))
            # 去重：合并起点 <1s 内的事件（保留速度最大的起点）
            out = []
            for e in ev:
                if out and e[0] - out[-1][0] < 1.0:
                    if e[2] > out[-1][2]: out[-1] = e
                else:
                    out.append(e)
            return out
        for e in detect_dec(tc, v):
            print(f"   A 减速起t={e[0]:6.1f}s 止t={e[1]:6.1f}s  |v| {e[2]:.2f}→{e[3]:.2f}  止时前向最近={e[4]:.2f}m")
        odarr = np.array(od, dtype=float)
        to_, vxo, vyo = odarr[:,0], odarr[:,4], odarr[:,5]
        for e in detect_dec(to_, np.hypot(vxo, vyo)):
            print(f"   B 减速起t={e[0]:6.1f}s 止t={e[1]:6.1f}s  |v| {e[2]:.2f}→{e[3]:.2f}  止时前向最近={e[4]:.2f}m")
        # 接近窗口（fwd<2.5m）：按运动状态切子块，静止=摘要、运动=逐帧（scan 0.1s 粒度）
        if len(scans):
            close = fwd < 2.5
            print("接近窗口（fwd<2.5m; 子块按运动切分: 静止=摘要, 运动=逐帧 0.1s）:")
            i = 0
            while i < len(scans):
                if close[i]:
                    j = i
                    while j < len(scans) and close[j]: j += 1
                    # 块内按 cmd|v| 切子块
                    k = i
                    while k < j:
                        idxk = np.abs(tc-scans[k,0]).argmin()
                        moving_k = v[idxk] > 0.03
                        kk = k + 1
                        while kk < j:
                            idx2 = np.abs(tc-scans[kk,0]).argmin()
                            if (v[idx2] > 0.03) != moving_k: break
                            kk += 1
                        s0, s1 = scans[k,0], scans[kk-1,0]
                        if s1 - s0 >= 0.3:  # 忽略 <0.3s 碎块
                            if moving_k:
                                vmax = max(v[np.abs(tc-scans[m,0]).argmin()] for m in range(k, kk))
                                print(f"  ┌ 运动段 [{s0:7.1f}~{s1:7.1f}] 长{s1-s0:5.1f}s {kk-k}帧  cmd|v|max={vmax:.2f}")
                                for m in range(k, kk, max(1, (kk-k)//24)):
                                    idx = np.abs(tc-scans[m,0]).argmin()
                                    print(f"  │ t={scans[m,0]:7.1f}  fwd={fwd[m]:5.2f}m  allmin={scans[m,1]:5.2f}m  方向={np.degrees(scans[m,3]):6.1f}°  cmd|v|={v[idx]:.2f}")
                            else:
                                print(f"  · 静止段 [{s0:7.1f}~{s1:7.1f}] 长{s1-s0:5.1f}s {kk-k}帧  fwd={fwd[k:kk].min():.2f}~{fwd[k:kk].max():.2f}m 全向min={scans[k:kk,1].min():.2f}m")
                        k = kk
                    i = j
                else: i += 1

for b in BAGS:
    try:
        s, c, g, a = load(b)
        summarize(b, s, c, g, a)
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"{b}: ERROR {e}")
