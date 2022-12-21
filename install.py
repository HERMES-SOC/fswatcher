"""
Installation script to install the sdc_aws_fswatcher service
"""

import os
import sys

# Get the current working directory
cwd = os.getcwd()
print("Current working directory: " + cwd)

# Get absolute path of the current working directory
abs = os.path.abspath(cwd)
print("Absolute path: " + abs)

# Create venv if it does not exist
if not os.path.exists(abs + "/venv"):
    print("Creating venv")
    os.system("python3 -m venv " + abs + "/venv")
    print("Created venv")

# Install requirements
print("Installing requirements")
os.system(abs + "/venv/bin/pip install -r requirements.txt")
print("Installed requirements")

yaml = __import__("yaml")
# Parse config file
try:
    with open("config.yaml", "r") as ymlfile:
        cfg = yaml.load(ymlfile)
except:
    print("Unable to parse config.yaml")
    sys.exit(1)

# Verify awscli is installed
if os.system("which aws") != 0:
    print("awscli is not installed")
    sys.exit(1)
else:
    print("awscli is installed")
    # Change permissions on awscli using which aws
    os.system("sudo chmod -R 755 " + os.popen("which aws").read().strip())

# Verify script exists sdc_aws_fswatcher.py
if not os.path.exists(abs + "/sdc_aws_fswatcher/sdc_aws_fswatcher.py"):
    print("sdc_aws_fswatcher.py does not exist")
    sys.exit(1)
else:
    print("sdc_aws_fswatcher.py exists")

# Verify service file exists
if not os.path.exists(abs + "/sdc_aws_fswatcher_template.service"):
    print("sdc_aws_fswatcher_template.service does not exist")
    sys.exit(1)
else:
    print("sdc_aws_fswatcher_template.service exists")


# Change variables in service file
filedata = None
with open(abs + "/sdc_aws_fswatcher_template.service", "r") as file:
    filedata = file.read()

    filedata = filedata.replace("$CURRENT_WORKING_DIRECTORY$", abs)

    if cfg.get("SDC_SYSTEM_USER"):
        filedata = filedata.replace("$SDC_SYSTEM_USER$", cfg["SDC_SYSTEM_USER"])
    else:
        print("SDC_SYSTEM_USER is required")
        sys.exit(1)

    if cfg.get("SDC_AWS_S3_BUCKET"):
        filedata = filedata.replace(
            "$SDC_AWS_S3_BUCKET$", f'-b {cfg["SDC_AWS_S3_BUCKET"]}'
        )
    else:
        print("SDC_AWS_S3_BUCKET is required")
        sys.exit(1)

    if cfg.get("SDC_AWS_WATCH_PATH"):
        filedata = filedata.replace(
            "$SDC_AWS_WATCH_PATH$", f'-d {cfg["SDC_AWS_WATCH_PATH"]}'
        )
    else:
        print("SDC_AWS_WATCH_PATH is required")
        sys.exit(1)

    if cfg.get("SDC_AWS_PROFILE"):
        filedata = filedata.replace("$SDC_AWS_PROFILE$", f'-p {cfg["SDC_AWS_PROFILE"]}')
    else:
        filedata = filedata.replace("$SDC_AWS_PROFILE$", "")

    if cfg.get("SDC_AWS_TIMESTREAM_DB"):
        filedata = filedata.replace(
            "$SDC_AWS_TIMESTREAM_DB$", f'-t {cfg["SDC_AWS_TIMESTREAM_DB"]}'
        )
    else:
        filedata = filedata.replace("$SDC_AWS_TIMESTREAM_DB$", "")

    if cfg.get("SDC_AWS_TIMESTREAM_TABLE"):
        filedata = filedata.replace(
            "$SDC_AWS_TIMESTREAM_TABLE$", f'-tt {cfg["SDC_AWS_TIMESTREAM_TABLE"]}'
        )
    else:
        filedata = filedata.replace("$SDC_AWS_TIMESTREAM_TABLE$", "")

    if cfg.get("SDC_AWS_CONCURRENCY_LIMIT"):
        filedata = filedata.replace(
            "$SDC_AWS_CONCURRENCY_LIMIT$", f'-c {cfg["SDC_AWS_CONCURRENCY_LIMIT"]}'
        )
    else:
        filedata = filedata.replace("$SDC_AWS_CONCURRENCY_LIMIT$", "")

    if "SDC_AWS_ALLOW_DELETE" in cfg and cfg["SDC_AWS_ALLOW_DELETE"] == "True":
        filedata = filedata.replace("$SDC_AWS_ALLOW_DELETE$", "-a")
    else:
        filedata = filedata.replace("$SDC_AWS_ALLOW_DELETE$", "")


# Write the file out again
with open(abs + "/sdc_aws_fswatcher.service", "w") as file:
    file.write(filedata)

# Check if service already exists and remove it
if os.path.exists("/etc/systemd/system/sdc_aws_fswatcher.service"):
    print("Service already exists - Updating service")
    os.system("sudo systemctl stop sdc_aws_fswatcher.service")
    os.system("sudo systemctl disable sdc_aws_fswatcher.service")
    os.system("sudo rm /etc/systemd/system/sdc_aws_fswatcher.service")
    print("Removed existing service")

# Copy service file to /etc/systemd/system
os.system("sudo cp " + abs + "/sdc_aws_fswatcher.service /etc/systemd/system/")
print("Copied service file to /etc/systemd/system")

# Enable service
os.system("sudo systemctl enable sdc_aws_fswatcher.service")
print("Enabled service")

# Start service
os.system("sudo systemctl start sdc_aws_fswatcher.service")
print("Started service")

# Verify service is running
os.system("sudo systemctl status sdc_aws_fswatcher.service")
print("Service status")
