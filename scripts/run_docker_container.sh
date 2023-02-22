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

# Concurrency limit
CONCURRENCY_LIMIT=10

# AWS region
AWS_REGION="us-east-1"

# TimeStream database name (optional)
TIMESTREAM_DB=""

# TimeStream table name (optional)
TIMESTREAM_TABLE=""

# Slack token (optional)
SLACK_TOKEN=""

# Slack channel (optional)
SLACK_CHANNEL=""

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

SDC_AWS_CONCURRENCY_LIMIT="-c $CONCURRENCY_LIMIT"

# If TimeStream database name is provided, then add it to the environment variables
if [ ! -z "$TIMESTREAM_DB" ]; then
    SDC_AWS_TIMESTREAM_DB="-t $TIMESTREAM_DB"
fi

# If TimeStream table name is provided, then add it to the environment variables
if [ ! -z "$TIMESTREAM_TABLE" ]; then
    SDC_AWS_TIMESTREAM_TABLE="-tt $TIMESTREAM_TABLE"
fi

# If Slack token is provided, then add it to the environment variables
if [ ! -z "$SLACK_TOKEN" ]; then
    SDC_AWS_SLACK_TOKEN="-s $SLACK_TOKEN"
fi

# If Slack channel is provided, then add it to the environment variables
if [ ! -z "$SLACK_CHANNEL" ]; then
    SDC_AWS_SLACK_CHANNEL="-sc $SLACK_CHANNEL"
fi

# Run the docker container
docker run \
    -it \
    --name $CONTAINER_NAME \
    -e SDC_AWS_S3_BUCKET="$SDC_AWS_S3_BUCKET" \
    -e SDC_AWS_CONCURRENCY_LIMIT="$SDC_AWS_CONCURRENCY_LIMIT" \
    -e SDC_AWS_TIMESTREAM_DB="$SDC_AWS_TIMESTREAM_DB" \
    -e SDC_AWS_TIMESTREAM_TABLE="$SDC_AWS_TIMESTREAM_TABLE"
    -e SDC_AWS_SLACK_TOKEN="$SDC_AWS_SLACK_TOKEN" \
    -e SDC_AWS_SLACK_CHANNEL="$SDC_AWS_SLACK_CHANNEL" \
    -e AWS_REGION="$AWS_REGION" \
    -v /etc/passwd:/etc/passwd \
    -v $WATCH_DIR:/watch \
    -v ${HOME}/.aws/credentials:/root/.aws/credentials:ro \
    $IMAGE_NAME
