#!/bin/bash
# 09-08 近距丢黑块修复 A/B（box_TrendsParallel 反转重放）：$1 = old|new
# 静态 tf(identity odom→base_link + 0.655 base_link→velodyne) + standalone costmap + reader
# + 反转重放（mark 相 2.10m → 接近相 → 盲区 clear 相）
# 清理纪律：costmap 子进程不随 ros2 run 包装死——按命令行特征精确杀，绝不 pkill -x python3
source /opt/ros/humble/setup.bash
MODE="$1"
[ "$MODE" = old ] || [ "$MODE" = new ] || { echo "用法: $0 old|new"; exit 1; }
YAML=/tmp/costmap_vm_global_${MODE}.yaml
OUT=/tmp/vm_ab_sweep_${MODE}_marks.jsonl

# ---- 前置残留检查：任何 costmap/static tf 测试进程都必须不存在 ----
if pgrep -f "nav2_costmap_2d --ros-args" >/dev/null || pgrep -f "static_transform_publisher" >/dev/null; then
  echo "残留进程！先手动清理"; exit 1
fi
rm -f "$OUT"

cleanup() {
  pkill -f "nav2_costmap_2d --ros-args --params-file /tmp/costmap_vm_global_${MODE}.yaml" 2>/dev/null
  pkill -f "static_transform_publisher 0 0 0 0 0 0 odom base_link" 2>/dev/null
  pkill -f "static_transform_publisher 0 0 0.655 0 0 0 base_link velodyne" 2>/dev/null
  pkill -f "/tmp/vm_ab_reader.py" 2>/dev/null
  sleep 1.5
}

echo "== [1] 静态 tf =="
ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 odom base_link >/tmp/vm_sweep_tf1.log 2>&1 &
ros2 run tf2_ros static_transform_publisher 0 0 0.655 0 0 0 base_link velodyne >/tmp/vm_sweep_tf2.log 2>&1 &
sleep 2
echo "== [2] costmap (${MODE}) =="
ros2 run nav2_costmap_2d nav2_costmap_2d --ros-args --params-file "$YAML" >/tmp/vm_sweep_${MODE}_costmap.log 2>&1 &
sleep 3
timeout 15 ros2 lifecycle set /costmap/costmap configure >/dev/null 2>&1 || true
timeout 15 ros2 lifecycle set /costmap/costmap activate  >/dev/null 2>&1 || true
echo "== [3] reader =="
sed "s#/tmp/vm_new_marks.jsonl#$OUT#" /tmp/vm_read_marks.py > /tmp/vm_ab_reader.py
python3 /tmp/vm_ab_reader.py >/tmp/vm_sweep_${MODE}_reader.log 2>&1 &
sleep 2
echo "== [4] 反转重放（mark 相→接近相→盲区 clear 相）=="
python3 /tmp/vm_replay_sweep_rev.py >/tmp/vm_sweep_${MODE}_replay.log 2>&1
echo "== 收尾清理 =="
cleanup
sleep 1
echo "== done ${MODE}, marks: $(wc -l < "$OUT") 帧 =="
pgrep -f "nav2_costmap_2d --ros-args" && echo "!! 仍有 costmap 残留" || echo "清理干净"
