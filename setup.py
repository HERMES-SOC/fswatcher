from setuptools import setup

setup(
    name="fswatcher",
    version="0.1.0",
    description="AWS File System Watcher",
    author="Damian Barrous-Dume",
    author_email="dbarrous@navteca.com",
    packages=["fswatcher"],
    include_package_data=True,
    install_requires=[
        "watchdog==2.2.0",
        "boto3==1.26.35",
        "slack_sdk==3.19.5",
        "sdc_aws_utils @ git+https://github.com/HERMES-SOC/sdc_aws_utils.git",
    ],
    entry_points={
        "console_scripts": [
            "fswatcher = fswatcher.fswatcher:main",
        ]
    },
)
