from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'g354_imu_driver'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(),
    data_files=[
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.rviz')),
        (os.path.join('share', package_name), ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='lin',
    maintainer_email='you@example.com',
    description='ROS 2 driver for Epson M-G354 IMU',
    license='MIT',
    entry_points={
        'console_scripts': [
            'imu_node = g354_imu_driver.imu_node:main',
        ],
    },
)
