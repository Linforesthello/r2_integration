// locationMode_cli.cpp —— locationMode_8010t1.cpp 的命令行参数版（方案 A）
//
// 与原始文件的关系：
//   - 原文件 locationMode_8010t1.cpp 保持不动（N97 实机验证基线）
//   - 本文件 = 原文件复制 + 命令行参数改造 + --dry-run 自检模式 + 预读成功校验
//   - 不传参时目标角度与原文件一致（150 度）；步长默认改为 0.005（原文件 5.0）
//
// 用法：
//   ./locationMode_cli                      # 默认：150 度 / 步长 0.005
//   ./locationMode_cli 180                  # 只改目标角度
//   ./locationMode_cli 180 0.01             # 改角度 + 改步长
//   ./locationMode_cli 180 0.01 --dry-run   # 不开串口，只打印轨迹（VM 上可跑）
//
// 步长说明：stepSize 是「每个循环的电机轴步进(rad)」，不是速度。
//   循环约 200us，电机输出上限 30 rad/s = 电机轴 190 rad/s
//   → 每循环最多走 0.038 rad；stepSize > 0.04 时电机只能全速追，等效阶跃指令。
//   想控速：0.005 约 0.7s 走完 150°，0.01 约 0.35s。

#include <unistd.h>
#include <cmath>
#include <cstdlib>
#include <cerrno>
#include <cstring>
#include "serialPort/SerialPort.h"
#include "unitreeMotor/unitreeMotor.h"

#include <csignal>
#include <iostream>

static volatile sig_atomic_t running = 1;

void signalHandler(int) {
  running = 0;
}

// 严格解析一个浮点数：整串必须被消费、且为有限值
// （用 atof 会把 "15O" 静默吞成 15，对会甩臂的电机不安全）
static bool parseFloat(const char* s, float& out) {
  char* end = nullptr;
  errno = 0;
  const float v = std::strtof(s, &end);
  if (errno != 0 || end == s || *end != '\0' || !std::isfinite(v)) return false;
  out = v;
  return true;
}


int main(int argc, char** argv) {

  // ---- 命令行参数（不传时：150 度 / 步长 0.005）----
  float targetDeg = 150.0f;              // 输出端目标角度（度）
  float stepSize  = 0.005f;                // 每次最大步进（rad，电机轴），安全缓变
  bool  dryRun    = false;               // --dry-run: 不开串口，只打印轨迹

  int parsed = 0;
  for (int i = 1; i < argc; i++) {
    if (std::strcmp(argv[i], "--dry-run") == 0) { dryRun = true; continue; }
    float v = 0.0f;
    if (parsed > 1 || !parseFloat(argv[i], v)) {
      std::cerr << "参数错误: " << argv[i] << "\n"
                << "用法: " << argv[0] << " [目标角度(度)] [步长(rad,电机轴)] [--dry-run]\n"
                << "  目标角度  输出端角度，默认 150\n"
                << "  步长      每循环最大步进(电机轴 rad)，默认 0.005\n"
                << "            注意: >0.04 时电机只能全速追，等效阶跃\n"
                << "            控速建议 0.005 (约 0.7s) / 0.01 (约 0.35s)\n"
                << "  --dry-run 不打开串口，只打印目标轨迹后退出\n"
                << "示例: " << argv[0] << " 180 0.01\n";
      return 1;
    }
    if (parsed == 0) targetDeg = v;
    else             stepSize  = v;
    parsed++;
  }
  if (stepSize <= 0.0f) {
    std::cerr << "参数错误: 步长必须 > 0\n";
    return 1;
  }

  // 直接使用 queryGearRatio 返回的 6.33，不再额外乘 6.33，避免减速比重复计算
  const float gearRatio  = -queryGearRatio(MotorType::GO_M8010_6);
  const float targetPos  = targetDeg * M_PI / 180.0f * gearRatio;  // 度→rad→电机轴位置

  std::cout << "[参数] targetDeg=" << targetDeg
            << "  stepSize=" << stepSize
            << "  targetPos=" << targetPos << " rad(电机轴)" << std::endl;

  if (dryRun) {
    // 不开串口，只跑位置逼近逻辑。假设从 0 出发；真机从 data.q 出发，步数只会更少
    float p = 0.0f;
    long  steps = 0;
    while (std::fabs(targetPos - p) > stepSize) {
      p += (targetPos > p) ? stepSize : -stepSize;
      steps++;
      if (steps > 20000000L) break;     // 防步长过小导致死循环
    }
    steps++;                            // 最后一帧直接对齐目标
    p = targetPos;
    std::cout << "[dry-run] 步数=" << steps
              << "  估算耗时=" << steps * 200e-6f << " s"
              << " (按 200us/循环，未含串口与打印开销)"
              << "  终值=" << p << " rad = "
              << p / gearRatio * 180.0 / M_PI << " 度" << std::endl;
    return 0;
  }

  SerialPort  serial("/dev/r2_g8010");
  MotorCmd    cmd;
  MotorData   data;

  std::signal(SIGINT, signalHandler);

  // ---- 以下与原文件基本一致，仅预读段增加了成功校验 ----
  // 先读一次当前位置，避免启动时从 0 出发导致突然反转
  cmd.motorType = MotorType::GO_M8010_6;
  data.motorType = MotorType::GO_M8010_6;
  cmd.mode = queryMotorMode(MotorType::GO_M8010_6, MotorMode::FOC);
  cmd.id = 0; 
  cmd.kp = 0; 
  cmd.kd = 0; 
  cmd.q = 0; 
  cmd.dq = 0; 
  cmd.tau = 0;

  // 预读必须确认成功：sendRecv 返回 false 时 data.q 仍是未初始化值（MotorData(){} 是空构造，
  // 只有 correct 有默认值），拿它当起点会让电机朝一个未知位置猛冲——比从 0 起步危险得多。
  bool ok = false;
  for (int i = 0; i < 3 && !ok; i++) {
    ok = serial.sendRecv(&cmd, &data) && std::isfinite(data.q);
    if (!ok) {
      std::cerr << "[预读] 第 " << (i + 1) << " 次读取电机位置失败" << std::endl;
      usleep(1000);   // 稍等再试，避免连续撞同一个时序窗口
    }
  }
  if (!ok) {
    std::cerr << "预读电机位置失败，拒绝启动（避免朝未知位置发指令）" << std::endl;
    return 2;         // 2 = 预读失败，与 1（参数错误）区分
  }
  float cmdPos = data.q;  // 从实际位置出发
  std::cout << "[预读] 当前位置 q=" << cmdPos << " rad(电机轴) = "
            << cmdPos / gearRatio * 180.0 / M_PI << " 度" << std::endl;

  

  while(running)
  {
    // 缓慢逼近目标，避免瞬间大力矩
    if (std::fabs(targetPos - cmdPos) > stepSize)
      cmdPos += (targetPos > cmdPos) ? stepSize : -stepSize;
    else
      cmdPos = targetPos;

    cmd.motorType = MotorType::GO_M8010_6;
    data.motorType = MotorType::GO_M8010_6;
    cmd.mode = queryMotorMode(MotorType::GO_M8010_6,MotorMode::FOC);
    cmd.id   = 0;
    cmd.kp   = 0.15;
    cmd.kd   = 0.1;
    cmd.q    = cmdPos;  
    cmd.dq   = 0.0;
    cmd.tau  = 0.0;
    serial.sendRecv(&cmd, &data);

    std::cout <<  std::endl;

    std::cout << "queryGearRatio returned: " << queryGearRatio(MotorType::GO_M8010_6) << std::endl;
    std::cout << "gearRatio: " << gearRatio << std::endl;

    std::cout << "motor.q: "      << data.q      << std::endl;
    std::cout << "output(deg): "  << data.q / gearRatio * 180.0 / M_PI << std::endl;
    std::cout << "motor.temp: "   << data.temp   << std::endl;
    std::cout << "motor.dq: "     << data.dq     << std::endl;
    std::cout << "motor.merror: " << data.merror << std::endl;
    std::cout <<  std::endl;

    usleep(200);
  }

  // 第1步：渐进撤力（保持位置目标不变，逐步降低 kp，加大 kd 吸收动能）
  for (int i = 0; i < 100; i++) {
    float t = (100 - i) / 100.0f;       // 1.0 → 0.0
    cmd.kp = 0.15f * t;                 // 位置刚度递减
    cmd.kd = 0.1f * (2.0f - t);         // 阻尼递增：0.1 → 0.2
    cmd.q = cmdPos;                     // 维持当前位置目标
    serial.sendRecv(&cmd, &data);
    usleep(200);
  }

  // 第2步：力矩已接近 0，切换到停止模式
  cmd.mode = 0;
  cmd.dq  = 0.0f;
  cmd.q   = 0.0f;
  cmd.tau = 0.0f;
  cmd.kp  = 0.0f;
  cmd.kd  = 0.0f;
  serial.sendRecv(&cmd, &data);

  return 0;
}