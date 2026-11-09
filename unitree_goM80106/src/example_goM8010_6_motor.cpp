#include <unistd.h>
#include <csignal>
#include <iostream>
#include "serialPort/SerialPort.h"
#include "unitreeMotor/unitreeMotor.h"

static volatile sig_atomic_t running = 1;

void signalHandler(int) {
  running = 0;
}

int main() {

  SerialPort  serial("/dev/r2_g8010");
  MotorCmd    cmd;
  MotorData   data;

  std::signal(SIGINT, signalHandler);

  while(running)
  {
    cmd.motorType = MotorType::GO_M8010_6;
    data.motorType = MotorType::GO_M8010_6;
    cmd.mode = queryMotorMode(MotorType::GO_M8010_6,MotorMode::FOC);
    cmd.id   = 0;
    cmd.kp   = 0.0;
    cmd.kd   = 0.01;
    cmd.q    = 0.0;
    cmd.dq   = -6.28*queryGearRatio(MotorType::GO_M8010_6);
    cmd.tau  = 0.0;
    serial.sendRecv(&cmd,&data);

    std::cout <<  std::endl;
    std::cout <<  "motor.q: "    << data.q    <<  std::endl;
    std::cout <<  "motor.temp: "   << data.temp   <<  std::endl;
    std::cout <<  "motor.W: "      << data.dq      <<  std::endl;
    std::cout <<  "motor.merror: " << data.merror <<  std::endl;
    std::cout <<  std::endl;

    usleep(200);
  }

  // 退出循环后，在正常上下文中发送停止指令
  // cmd.mode = 0; // 设置为停止模式
  cmd.dq  = 0.0f;
  cmd.q   = 0.0f;
  cmd.tau = 0.0f;
  cmd.kp  = 0.0f;
  cmd.kd  = 0.0f;
  serial.sendRecv(&cmd, &data);

  return 0;
}