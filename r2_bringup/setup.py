from setuptools import setup
from glob import glob

package_name = 'r2_bringup'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        # 原版（G8 修复前，2026-11-07 注释保留备查）：
        # ('share/' + package_name + '/config', glob('config/*.yaml')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
        # G8 修复（2026-11-07）：launch 用 -d <share>/config/nav2.rviz，但原 glob 只收 *.yaml，
        # 源文件存在而 install 无该文件 → rviz:=true 加载不到配置。
        ('share/' + package_name + '/config', glob('config/*.rviz')),
        ('share/' + package_name + '/config/dds', glob('config/dds/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='lin',
    maintainer_email='lin@localhost',
    description='R2 全向轮底盘 ROS2 驱动包 — CAN 控制、运动学解算、里程计',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'chassis_node = r2_bringup.chassis_node:main',
            'chassis_test = r2_bringup.chassis_node:test_main',
            'teleop_keyboard = r2_bringup.teleop_keyboard:main',
        ],
    },
)
