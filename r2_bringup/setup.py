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
        ('share/' + package_name + '/config', glob('config/*.yaml')),
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
