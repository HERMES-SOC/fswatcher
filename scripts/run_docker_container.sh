#! /bin/bash

# Script to build and run the fswatcher docker container

# Container name
CONTAINER_NAME=fswatcher

# Image name
IMAGE_NAME=fswatcher

# S3 bucket name
S3_BUCKET_NAME=swsoc-unsorted

# Filepath to the directory to be watched
WATCH_DIR=~/watch_directory

# Get path of current working directory (where the script is located)
SCRIPT_PATH=$(pwd)

# If the script is not located in the scripts directory, then change the path to the scripts directory
if [ "$(basename $SCRIPT_PATH)" != "scripts" ]; then
    SCRIPT_PATH="$SCRIPT_PATH/scripts"
fi

# Print Script path
echo "Script path: $SCRIPT_PATH"

# Get path of the dockerfile which is in the upper directory
DOCKERFILE_PATH=$(dirname $SCRIPT_PATH)

# Print Dockerfile path
echo "Dockerfile path: $DOCKERFILE_PATH"

# Remove the docker container if it already exists
if [ "$(docker ps -a | grep $CONTAINER_NAME)" ]; then
    echo "Removing existing container $CONTAINER_NAME"
    docker rm $CONTAINER_NAME
fi

# Remove the docker image if it already exists
if [ "$(docker images | grep $IMAGE_NAME)" ]; then
    echo "Removing existing image $IMAGE_NAME"
    docker rmi $IMAGE_NAME
fi

# Build the docker image
echo "Building docker image $IMAGE_NAME"
docker build -t $IMAGE_NAME $DOCKERFILE_PATH

# Run the docker container
echo "Running docker container $CONTAINER_NAME"


# Docker environment variables
SDC_AWS_S3_BUCKET="-b $S3_BUCKET_NAME"

SDC_AWS_CONCURRENCY_LIMIT='-c 10'

AWS_REGION='us-east-1'

echo "SDC_AWS_S3_BUCKET: $SDC_AWS_S3_BUCKET"

echo "WATCH_DIR: $WATCH_DIR"

echo "AWS_REGION: $AWS_REGION"

docker run \
    -it \
    --name $CONTAINER_NAME \
    -e SDC_AWS_S3_BUCKET="$SDC_AWS_S3_BUCKET" \
    -e SDC_AWS_CONCURRENCY_LIMIT="$SDC_AWS_CONCURRENCY_LIMIT" \
    -e AWS_REGION="$AWS_REGION" \
    -v /etc/passwd:/etc/passwd \
    -v $WATCH_DIR:/watch \
    -v ${HOME}/.aws/credentials:/root/.aws/credentials:ro \
    $IMAGE_NAME 
