from setuptools import setup, find_packages


setup(
    name="fswatcher",
    version="0.1.0",
    description="AWS File System Watcher",
    author="Damian Barrous-Dume",
    packages=["fswatcher"],
    include_package_data=True,
    install_requires=["watchdog", "boto3", "pyyaml", "slack_sdk"],
    entry_points={
        "console_scripts": [
            "fswatcher = fswatcher.fswatcher:main",
        ]
    },
)
