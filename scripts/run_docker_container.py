# Script to build and run the fswatcher docker container
import os
import subprocess

# Container name
container_name = 'test-fswatcher'

# Image name
image_name = 'fswatcher'

# Get path of this script
script_path = os.path.dirname(os.path.realpath(__file__))

# Get path of the dockerfile which is in the upper directory
dockerfile_path = os.path.join(script_path, '..')

# Remove the docker container if it already exists
subprocess.call(['docker', 'rm', '-f', image_name])

# Remove the docker image if it already exists
subprocess.call(['docker', 'rmi', '-f', image_name])

# Build the docker container
subprocess.call(['docker', 'build', '-t', image_name, dockerfile_path])

# Run the docker container with the passed in arguments
subprocess.call(['docker', 'run', '-it', '-n', container_name, image_name])

