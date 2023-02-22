#! /bin/bash

# Script to build and run the fswatcher docker container

source fswatcher.config

# Verify that the directory to be watched exists
if [ ! -d "$WATCH_DIR" ]; then
    echo "Directory $WATCH_DIR does not exist"
    exit 1
fi

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


# Build the docker image
echo "Building docker image $IMAGE_NAME"
docker build -t $IMAGE_NAME $DOCKERFILE_PATH

# Run the docker container
echo "Running docker container $CONTAINER_NAME"

# Unset all the environment variables
unset SDC_AWS_S3_BUCKET
unset SDC_AWS_CONCURRENCY_LIMIT
unset SDC_AWS_TIMESTREAM_DB
unset SDC_AWS_TIMESTREAM_TABLE
unset SDC_AWS_SLACK_TOKEN
unset SDC_AWS_SLACK_CHANNEL

# Docker environment variables
SDC_AWS_S3_BUCKET="-b $S3_BUCKET_NAME"

SDC_AWS_CONCURRENCY_LIMIT="-c $CONCURRENCY_LIMIT"

# If TimeStream database name is not "", then add it to the environment variables
if [ -z ${TIMESTREAM_DB+x} ]; then
    SDC_AWS_TIMESTREAM_DB="-t $TIMESTREAM_DB"
else
    SDC_AWS_TIMESTREAM_DB=""
fi

# If Timestream table name is not "", then add it to the environment variables
if [ -z ${TIMESTREAM_TABLE+x} ]; then
    SDC_AWS_TIMESTREAM_TABLE="-tt $TIMESTREAM_TABLE"
else
    SDC_AWS_TIMESTREAM_TABLE=""
fi

# If Slack token is not "", then add it to the environment variables else make it empty
if [ -z ${SLACK_TOKEN+x} ]; then
    SDC_AWS_SLACK_TOKEN="-s $SLACK_TOKEN"
else
    SDC_AWS_SLACK_TOKEN=""
fi

# If Slack channel is not "", then add it to the environment variables else make it empty
if [ -z ${SLACK_CHANNEL+x} ]; then
    SDC_AWS_SLACK_CHANNEL="-c $SLACK_CHANNEL"
else
    SDC_AWS_SLACK_CHANNEL=""
fi

# Print all the environment variables
echo "SDC_AWS_S3_BUCKET: $SDC_AWS_S3_BUCKET"
echo "SDC_AWS_CONCURRENCY_LIMIT: $SDC_AWS_CONCURRENCY_LIMIT"
echo "SDC_AWS_TIMESTREAM_DB: $SDC_AWS_TIMESTREAM_DB"
echo "SDC_AWS_TIMESTREAM_TABLE: $SDC_AWS_TIMESTREAM_TABLE"
echo "SDC_AWS_SLACK_TOKEN: $SDC_AWS_SLACK_TOKEN"
echo "SDC_AWS_SLACK_CHANNEL: $SDC_AWS_SLACK_CHANNEL"

# Run the docker container
docker run -it \
    --name $CONTAINER_NAME \
    -e SDC_AWS_S3_BUCKET="$SDC_AWS_S3_BUCKET" \
    -e SDC_AWS_CONCURRENCY_LIMIT="$SDC_AWS_CONCURRENCY_LIMIT" \
    -e SDC_AWS_TIMESTREAM_DB="$SDC_AWS_TIMESTREAM_DB" \
    -e SDC_AWS_TIMESTREAM_TABLE="$SDC_AWS_TIMESTREAM_TABLE" \
    -e SDC_AWS_SLACK_TOKEN="$SDC_AWS_SLACK_TOKEN" \
    -e SDC_AWS_SLACK_CHANNEL="$SDC_AWS_SLACK_CHANNEL" \
    -e AWS_REGION="$AWS_REGION" \
    -v /etc/passwd:/etc/passwd \
    -v $WATCH_DIR:/watch \
    -v ${HOME}/.aws/credentials:/root/.aws/credentials:ro \
    $IMAGE_NAME
