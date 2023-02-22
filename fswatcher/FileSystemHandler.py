"""
File System Handler Module for SDC AWS File System Watcher
"""

import sys
import os
import time
from datetime import datetime
from urllib import parse
import boto3
import botocore
import boto3.s3.transfer as s3transfer
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from fswatcher.FileSystemHandlerEvent import FileSystemHandlerEvent
from fswatcher.FileSystemHandlerConfig import FileSystemHandlerConfig
from watchdog.events import (
    FileSystemEvent,
    FileClosedEvent,
    FileSystemEventHandler,
)
from typing import List
from fswatcher import log


class FileSystemHandler(FileSystemEventHandler):
    """
    Subclass to handle file system events
    """

    events: List[FileSystemHandlerEvent] = []

    def __init__(
        self,
        config: FileSystemHandlerConfig,
    ) -> None:
        """
        Overloaded Constructor
        """
        # Initialize the allow S3 delete flag
        self.allow_delete = config.allow_delete

        # Initialize the concurrency_limit (Max number of concurrent S3 Uploads)
        self.concurrency_limit = config.concurrency_limit

        # Check if bucket name is and accessible using boto
        try:
            # Initialize Boto3 Session
            self.boto3_session = (
                boto3.session.Session(
                    profile_name=config.profile, region_name=os.getenv("AWS_REGION")
                )
                if config.profile != ""
                else boto3.session.Session(region_name=os.getenv("AWS_REGION"))
            )

            # Initialize S3 Transfer Manager with concurrency limit
            botocore_config = botocore.config.Config(
                max_pool_connections=self.concurrency_limit
            )
            s3client = self.boto3_session.client("s3", config=botocore_config)
            transfer_config = s3transfer.TransferConfig(
                use_threads=True,
                max_concurrency=self.concurrency_limit,
            )
            self.s3t = s3transfer.create_transfer_manager(s3client, transfer_config)

        except botocore.exceptions.ClientError as e:
            # If a client error is thrown, then check that it was a 404 error.
            # If it was a 404 error, then the bucket does not exist.
            error_code = int(e.response["Error"]["Code"])
            if error_code == 404:
                log.error(
                    {
                        "status": "ERROR",
                        "message": f"Bucket ({config.bucket_name}) does not exist",
                    }
                )

                sys.exit(1)

        # Initialize the bucket name
        self.bucket_name = config.bucket_name

        # Initialize the timestream db
        self.timestream_db = config.timestream_db

        # Initialize the timestream table
        self.timestream_table = config.timestream_table

        # Initialize the slack client
        if config.slack_token is not None:
            try:
                
                # Initialize the slack client
                self.slack_client = WebClient(token=config.slack_token)

                # Initialize the slack channel
                self.slack_channel = config.slack_channel

            except SlackApiError as e:
                error_code = int(e.response["Error"]["Code"])
                if error_code == 404:
                    log.error(
                        {
                            "status": "ERROR",
                            "message": f"Slack Token ({config.slack_token}) is invalid",
                        }
                    )
        else:
            self.slack_client = None

        # Validate the path
        if not os.path.exists(config.path):
            log.error(
                {"status": "ERROR", "message": f"Path ({config.path}) does not exist"}
            )

            sys.exit(1)

        # Path to watch
        self.path = config.path

        log.info(f"Watching for file events in: {config.path}")


    def on_any_event(self, event: FileSystemEvent) -> None:
        """
        Overloaded Function to deal with any event
        """

        # Filter the event
        filtered_event = self._filter_event(event)

        if filtered_event is None:
            return

        # Append the event to the list of events
        self.events.append(filtered_event)

        # Handle the event
        self._handle_event(filtered_event)

    def _filter_event(self, event: FileSystemEvent) -> FileSystemHandlerEvent or None:
        """
        Function to filter events
        """
        # Skip if file is hermes.log file
        if "hermes.log" in event.src_path:
            return None

        # Skip closed events
        if isinstance(event, FileClosedEvent):
            return None

        # Skip if directory
        if event.is_directory:
            return None

        # Initialize the file system event
        file_system_event = FileSystemHandlerEvent(
            event=event,
            watch_path=self.path,
            bucket_name=self.bucket_name,
        )

        # Skip if duplicate event
        if file_system_event in self.events:
            return None

        return file_system_event

    def _handle_event(self, event: FileSystemHandlerEvent) -> None:
        """
        Function to handle file events and upload to S3
        """
        try:
            # Send Slack Notification about the event
            if self.slack_client is not None:
                if event.action_type == "CREATE":
                    slack_message = f"FSWatcher: New file in watch directory - ({event.get_parsed_path()}) :file_folder:"
                elif event.action_type == "UPDATE":
                    slack_message = f"FSWatcher: File modified in watch directory - ({event.get_parsed_path()}) :file_folder:"
                elif event.action_type == "PUT":
                    slack_message = f"FSWatcher: File moved in watch directory - ({event.get_parsed_path()}) :file_folder:"
                elif event.action_type == "DELETE":
                    slack_message = f"FSWatcher: File deleted from watch directory - ({event.get_parsed_path()}) :file_folder:"
                else:
                    slack_message = f"FSWatcher: Unknown file event in watch directory - ({event.get_parsed_path()}) :file_folder:"

                self._send_slack_notification(
                    slack_client=self.slack_client,
                    slack_channel=self.slack_channel,
                    slack_message=slack_message,
                )

            # Get the log message
            log_message = event.get_log_message()

            # Capital Case Action Type
            log.info(log_message)

            if event.action_type != "DELETE":
                # Generate Object Tags String
                tags = self._generate_object_tags(
                    event=event,
                )

                # Upload to S3 Bucket
                self._upload_to_s3_bucket(
                    src_path=event.get_path(),
                    bucket_name=event.bucket_name,
                    file_key=event.get_parsed_path(),
                    tags=tags,
                )

                # Send Slack Notification about the event
                if self.slack_client is not None:
                    slack_message = f"FSWatcher: File successfully uploaded to {event.bucket_name} - ({event.get_parsed_path()}) :file_folder:"
                    self._send_slack_notification(
                        slack_client=self.slack_client,
                        slack_channel=self.slack_channel,
                        slack_message=slack_message,
                    )

            elif event.action_type == "DELETE" and self.allow_delete:

                # Delete from S3 Bucket if allowed
                self._delete_from_s3_bucket(
                    bucket_name=event.bucket_name,
                    file_key=event.get_parsed_path(),
                )

            # Log to Timestream
            if self.timestream_db and self.timestream_table:
                self._log(
                    boto3_session=self.boto3_session,
                    action_type=event.action_type,
                    file_key=event.get_path(),
                    new_file_key=event.get_parsed_path(),
                    source_bucket="External Server",
                    destination_bucket=None
                    if event.action_type == "DELETE"
                    else event.bucket_name,
                    timestream_db=self.timestream_db,
                    timestream_table=self.timestream_table,
                )

            # Remove the event from the list
            self.events.remove(event)

        except Exception as e:
            log.error(e)
            log.error(
                {
                    "status": "ERROR",
                    "message": f"Error handling file skipping to next: {e}",
                }
            )

    @staticmethod
    def _generate_object_tags(event: FileSystemHandlerEvent) -> str:
        """
        Function to generate object tags and return as a url encoded string
        """
        log.info(f"Object ({event.get_parsed_path()}) - Generating S3 Object Tags")
        try:
            # Get Object Stats
            object_stats = os.stat(event.get_path())

            stat_list = dir(object_stats)

            tags = {}

            # Create Tags Dictionary
            for stat in stat_list:
                if stat in [
                    "st_mode",
                    "st_ino",
                    "st_uid",
                    "st_gid",
                    "st_size",
                    "st_atime",
                    "st_mtime",
                    "st_ctime",
                    "st_type",
                    "st_creator",
                ]:
                    tags[stat] = object_stats.__getattribute__(stat)

            # Log Object Creation and Modification Times
            log.info(f"Object ({event.get_parsed_path()}) - Stats: {tags}")

            return parse.urlencode(tags)

        except Exception as e:
            log.error(
                {"status": "ERROR", "message": f"Error generating object tags: {e}"}
            )

    def _upload_to_s3_bucket(self, src_path, bucket_name, file_key, tags):
        """
        Function to Upload a file to an S3 Bucket
        """
        log.info(f"Object ({file_key}) - Uploading file to S3 Bucket ({bucket_name})")
        try:
            # Upload to S3 Bucket
            self.s3t.upload(
                src_path,
                bucket_name,
                file_key,
                extra_args={"Tagging": tags},
            )

            log.info(
                f"Object ({file_key}) - Successfully Uploaded to S3 Bucket ({bucket_name})"
            )

        except botocore.exceptions.ClientError as e:
            log.error(
                {"status": "ERROR", "message": f"Error uploading to S3 Bucket: {e}"}
            )
            self._send_slack_notification(
                slack_client=self.slack_client,
                slack_channel=self.slack_channel,
                slack_message=f"FSWatcher: Error uploading file to {bucket_name} - ({file_key}) :file_folder:",
                alert_type="error",
            )
    
    def _delete_from_s3_bucket(self, bucket_name, file_key):
        """
        Function to Delete a file from an S3 Bucket
        """
        log.info(f"Object ({file_key}) - Deleting file from S3 Bucket ({bucket_name})")
        try:
            # Delete from S3 Bucket
            self.s3t.delete(
                bucket_name,
                file_key,
            )

            log.info(
                f"Object ({file_key}) - Successfully Deleted from S3 Bucket ({bucket_name})"
            )

        except botocore.exceptions.ClientError as e:
            log.error(
                {"status": "ERROR", "message": f"Error deleting from S3 Bucket: {e}"}
            )
            self._send_slack_notification(
                slack_client=self.slack_client,
                slack_channel=self.slack_channel,
                slack_message=f"FSWatcher: Error deleting file from {bucket_name} - ({file_key}) :file_folder:",
                alert_type="error",
            )

    @staticmethod
    def _send_slack_notification(
        slack_client,
        slack_channel: str,
        slack_message: str,
        alert_type: str = "success",
    ) -> None:
        """
        Function to send a Slack Notification
        """
        log.info(f"Sending Slack Notification to {slack_channel}")
        try:
            color = {
                "success": "#3498db",
                "error": "#ff0000",
            }
            ct = datetime.now()
            ts = ct.strftime("%y-%m-%d %H:%M:%S")
            slack_client.chat_postMessage(
                channel=slack_channel,
                text=f"{ts} - {slack_message}",
                attachments=[
                    {
                        "color": color[alert_type],
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "plain_text",
                                    "text": f"{ts} - {slack_message}",
                                },
                            }
                        ],
                    }
                ],
            )

        except SlackApiError as e:
            log.error(
                {"status": "ERROR", "message": f"Error sending Slack Notification: {e}"}
            )

    @staticmethod
    def _log(
        boto3_session,
        action_type,
        file_key,
        new_file_key=None,
        source_bucket=None,
        destination_bucket=None,
        timestream_db=None,
        timestream_table=None,
    ):
        """
        Function to Log to Timestream
        """
        log.info(f"Object ({new_file_key}) - Logging Event to Timestream")
        CURRENT_TIME = str(int(time.time() * 1000))
        try:
            # Initialize Timestream Client
            timestream = boto3_session.client("timestream-write")

            if not source_bucket and not destination_bucket:
                raise ValueError("A Source or Destination Buckets is required")

            # Write to Timestream
            timestream.write_records(
                DatabaseName=timestream_db if timestream_db else "sdc_aws_logs",
                TableName=timestream_table
                if timestream_table
                else "sdc_aws_s3_bucket_log_table",
                Records=[
                    {
                        "Time": CURRENT_TIME,
                        "Dimensions": [
                            {"Name": "action_type", "Value": action_type},
                            {
                                "Name": "source_bucket",
                                "Value": source_bucket or "N/A",
                            },
                            {
                                "Name": "destination_bucket",
                                "Value": destination_bucket or "N/A",
                            },
                            {"Name": "file_key", "Value": file_key},
                            {
                                "Name": "new_file_key",
                                "Value": new_file_key or "N/A",
                            },
                            {
                                "Name": "current file count",
                                "Value": "N/A",
                            },
                        ],
                        "MeasureName": "timestamp",
                        "MeasureValue": str(datetime.utcnow().timestamp()),
                        "MeasureValueType": "DOUBLE",
                    },
                ],
            )

            log.info(
                (f"Object ({new_file_key}) - Event Successfully Logged to Timestream")
            )

        except botocore.exceptions.ClientError as e:
            log.error(
                {"status": "ERROR", "message": f"Error logging to Timestream: {e}"}
            )

    @staticmethod
    # Function to open all files in a directory to trigger the on_modified event
    def backtrack(path):
        """
        Function to open all files in a directory and close them to trigger the on_modified event
        """
        log.info(f"Object ({path}) - Backtracking Directory")
        try:
            for root, dirs, files in os.walk(path):
                for file in files:
                    print(file)
                    with open(os.path.join(root, file), "r") as f:
                        f.close()

            log.info(f"Object ({path}) - Successfully Backtracked Directory")

        except Exception as e:
            log.error(
                {"status": "ERROR", "message": f"Error backtracking directory: {e}"}
            )