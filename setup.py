from setuptools import setup, find_packages


setup(
    name="sdc_aws_fswatcher",
    version="0.1.0",
    description="AWS File System Watcher",
    author="Damian Barrous-Dume",
    packages=["sdc_aws_fswatcher"],
    include_package_data=True,
    install_requires=[
        "watchdog",
        "boto3",
        "pyyaml",
    ],
    entry_points={
        "console_scripts": [
            "sdc_aws_fswatcher = sdc_aws_fswatcher.sdc_aws_fswatcher:main",
        ]
    },
)
