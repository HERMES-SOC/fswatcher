# Installation script to create a new linux service
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
    with open("config.yaml", 'r') as ymlfile:
        cfg = yaml.load(ymlfile)
except:
    print("Unable to parse config.yml")
    sys.exit(1)



# Verify script exists sdc_aws_fswatcher.py
if not os.path.exists(abs + "/sdc_aws_fswatcher.py"):
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
with open(abs + "/sdc_aws_fswatcher_template.service", 'r') as file:
    filedata = file.read()

    # Replace the target string
    filedata = filedata.replace('$CURRENT_WORKING_DIRECTORY$', abs)
    filedata = filedata.replace('$SDC_AWS_S3_BUCKET$', cfg['SDC_AWS_S3_BUCKET'])
    filedata = filedata.replace('$SDC_AWS_WATCH_PATH$', cfg['SDC_AWS_WATCH_PATH'])
    filedata = filedata.replace('$SDC_AWS_PROFILE$', cfg['SDC_AWS_PROFILE'])
    filedata = filedata.replace('$SDC_SYSTEM_USER$', cfg['SDC_SYSTEM_USER'])

# Write the file out again
with open(abs + "/sdc_aws_fswatcher.service", 'w') as file:
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



