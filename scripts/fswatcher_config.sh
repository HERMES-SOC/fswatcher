#! /bin/bash

# Environmental Variables for fswatcher

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
TIMESTREAM_TABLE="sdc_aws_s3_bucket_log_table"

# Slack token (optional)
SLACK_TOKEN=""

# Slack channel (optional)
SLACK_CHANNEL=""

# Get path of current working directory (where the script is located)
SCRIPT_PATH=$(pwd)
