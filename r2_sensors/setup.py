from setuptools import setup
from glob import glob

package_name = 'r2_sensors'

setup(
    name=package_name,
    version='0.1.0',
    packages=[],
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.urdf')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='lin',
    maintainer_email='lin@example.com',
    description='R2 传感器外设启动包 — VLP-16 雷达 launch + 安装 URDF',
    license='MIT',
)
