"""
File System Handler Module for SDC AWS File System Watcher
"""

import sys
import os
import time
from datetime import datetime
from urllib import parse
from typing import List, Optional

import boto3
import botocore
from boto3.s3.transfer import TransferConfig, S3Transfer

from sdc_aws_utils.logging import log
from sdc_aws_utils.aws import (
    create_timestream_client_session,
    log_to_timestream,
    object_exists,
)
from sdc_aws_utils.slack import get_slack_client, send_slack_notification

from fswatcher.FileSystemHandlerEvent import FileSystemHandlerEvent
from fswatcher.FileSystemHandlerConfig import FileSystemHandlerConfig
from watchdog.events import (
    FileSystemEvent,
    FileClosedEvent,
    FileSystemEventHandler,
    FileMovedEvent,
)


class FileSystemHandler(FileSystemEventHandler):
    """
    Subclass to handle file system events
    """

    events: List[FileSystemHandlerEvent] = []
    dead_letter_queue: List[dict] = []

    def __init__(self, config: FileSystemHandlerConfig) -> None:
        """
        Initialize the FileSystemHandler object.

        Args:
            config (FileSystemHandlerConfig): The configuration object for the FileSystemHandler.
        """
        self.allow_delete = config.allow_delete
        self.concurrency_limit = config.concurrency_limit
        self._initialize_boto3_session(config)
        self.bucket_name = config.bucket_name
        self.timestream_db = config.timestream_db
        self.timestream_table = config.timestream_table
        self.check_with_s3 = os.getenv("CHECK_S3") == "true"
        self._initialize_slack_client(config)
        self._validate_path_and_set(config.path)
        self._test_iam_policy()

    def _initialize_boto3_session(self, config: FileSystemHandlerConfig) -> None:
        """Initialize Boto3 session and S3 Transfer Manager."""
        try:
            session_args = {"region_name": os.getenv("AWS_REGION")}
            if config.profile:
                session_args["profile_name"] = config.profile

            self.boto3_session = boto3.session.Session(**session_args)
            botocore_config = botocore.config.Config(
                max_pool_connections=self.concurrency_limit
            )
            self.s3_client = self.boto3_session.client("s3", config=botocore_config)
            transfer_config = TransferConfig(
                use_threads=True, max_concurrency=self.concurrency_limit
            )
            self.s3t = S3Transfer(self.s3_client, transfer_config)
            if config.timestream_db and config.timestream_table:
                self.timestream_client = create_timestream_client_session()
        except botocore.exceptions.ClientError as e:
            error_code = int(e.response["Error"]["Code"])
            if error_code == 404:
                log.error(
                    {
                        "status": "ERROR",
                        "message": f"Bucket ({config.bucket_name}) does not exist",
                    }
                )
                sys.exit(1)

    def _initialize_slack_client(self, config: FileSystemHandlerConfig) -> None:
        """Initialize the Slack client if a Slack token is provided."""
        if config.slack_token is not None:
            try:
                self.slack_client = get_slack_client(token=config.slack_token)
                self.slack_channel = config.slack_channel
            except Exception as e:
                log.error(e)
        else:
            self.slack_client = None

    def _validate_path_and_set(self, path: str) -> None:
        """Validate the provided path and set it to the FileSystemHandler object."""
        if not os.path.exists(path):
            log.error({"status": "ERROR", "message": f"Path ({path}) does not exist"})
            sys.exit(1)
        self.path = path

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

    def _filter_event(self, event: FileSystemEvent) -> Optional[FileSystemHandlerEvent]:
        """
        Filter events based on pre-defined conditions and return a FileSystemHandlerEvent if the event passes the filters.

        Args:
            event (FileSystemEvent): The file system event to be filtered.

        Returns:
            FileSystemHandlerEvent or None: A FileSystemHandlerEvent object if the event passes the filters, otherwise None.
        """
        if self._is_ignored_event(event):
            return None

        file_system_event = FileSystemHandlerEvent(
            event=event,
            watch_path=self.path,
            bucket_name=self.bucket_name,
        )

        if self._is_duplicate_event(file_system_event):
            return None

        return file_system_event

    def _is_ignored_event(self, event: FileSystemEvent) -> bool:
        """Determine if the event should be ignored based on pre-defined conditions."""
        ignored_conditions = [
            "hermes.log" in event.src_path,
            isinstance(event, FileClosedEvent),
            event.is_directory,
        ]
        return any(ignored_conditions)

    def _is_duplicate_event(self, file_system_event: FileSystemHandlerEvent) -> bool:
        """Determine if the event is a duplicate."""
        return file_system_event in self.events

    def _handle_event(self, event: FileSystemHandlerEvent) -> None:
        """
        Handle file system events and upload to S3.

        Args:
            event (FileSystemHandlerEvent): The file system event to be handled.
        """
        try:
            self._send_slack_notification_for_event(event)
            log.info(event.get_log_message())

            if event.action_type != "DELETE":
                tags = self._generate_object_tags(event)
                self._upload_to_s3_bucket(
                    src_path=event.get_path(),
                    bucket_name=event.bucket_name,
                    file_key=event.get_parsed_path(),
                    tags=tags,
                )
                self._send_slack_notification_for_upload(event)

            elif event.action_type == "DELETE" and self.allow_delete:
                self._delete_from_s3_bucket(
                    bucket_name=event.bucket_name,
                    file_key=event.get_parsed_path(),
                )

            self._log_to_timestream(event)

            self.events.remove(event)

        except Exception as e:
            log.error(
                {
                    "status": "ERROR",
                    "message": f"Error handling file, skipping to next: {e}",
                }
            )

    def _send_slack_notification_for_event(self, event: FileSystemHandlerEvent) -> None:
        """Send a Slack notification for the given file system event."""
        if self.slack_client is not None:
            event_description_map = {
                "CREATE": "New file in watch directory",
                "UPDATE": "File modified in watch directory",
                "PUT": "File moved in watch directory",
                "DELETE": "File deleted from watch directory",
            }
            action_type = event.action_type
            description = event_description_map.get(
                action_type, "Unknown file event in watch directory"
            )
            slack_message = (
                f"FSWatcher: {description} - ({event.get_parsed_path()}) :file_folder:"
            )

            send_slack_notification(
                slack_client=self.slack_client,
                slack_channel=self.slack_channel,
                slack_message=slack_message,
            )

    def _send_slack_notification_for_upload(
        self, event: FileSystemHandlerEvent
    ) -> None:
        """Send a Slack notification after a successful file upload."""
        if self.slack_client is not None:
            slack_message = f"FSWatcher: File successfully uploaded to {event.bucket_name} - ({event.get_parsed_path()}) :file_folder:"
            send_slack_notification(
                slack_client=self.slack_client,
                slack_channel=self.slack_channel,
                slack_message=slack_message,
            )

    def _log_to_timestream(self, event: FileSystemHandlerEvent) -> None:
        """Log the event to Timestream."""
        if self.timestream_client:
            log_to_timestream(
                boto3_session=self.timestream_client,
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

    @staticmethod
    def _generate_object_tags(event: FileSystemHandlerEvent) -> str:
        """
        Generate object tags and return as a URL-encoded string.

        Args:
            event (FileSystemHandlerEvent): The file system event to generate tags for.

        Returns:
            str: URL-encoded string of object tags.
        """
        log.debug(f"Object ({event.get_parsed_path()}) - Generating S3 Object Tags")
        try:
            object_stats = os.stat(event.get_path())
            stat_list = dir(object_stats)
            tags = {}

            taggable_stats = [
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
            ]

            for stat in stat_list:
                if stat in taggable_stats:
                    tags[stat] = object_stats.__getattribute__(stat)

            log.debug(f"Object ({event.get_parsed_path()}) - Stats: {tags}")
            return parse.urlencode(tags)

        except Exception as e:
            log.error(
                {"status": "ERROR", "message": f"Error generating object tags: {e}"}
            )

    def _upload_to_s3_bucket(self, src_path, bucket_name, file_key, tags):
        """
        Upload a file to an S3 bucket.

        Args:
            src_path (str): The source path of the file to be uploaded.
            bucket_name (str): The name of the S3 bucket to upload the file to.
            file_key (str): The file key for the uploaded file.
            tags (str): The URL-encoded tags for the uploaded file.
        """
        log.debug(f"Object ({file_key}) - Uploading file to S3 Bucket ({bucket_name})")
        bucket_name, folder, upload_file_key = self._prepare_s3_bucket_components(
            bucket_name, file_key
        )

        try:
            self.s3t.upload_file(
                src_path, bucket_name, upload_file_key, extra_args={"Tagging": tags}
            )
            log.info(
                f"Object ({file_key}) - Successfully Uploaded to S3 Bucket ({bucket_name}/{folder})"
            )

        except boto3.exceptions.RetriesExceededError:
            self._handle_s3_upload_retry_exceeded(src_path, bucket_name, file_key, tags)

        except botocore.exceptions.ClientError as e:
            self._handle_s3_upload_client_error(bucket_name, file_key, e)

    def _delete_from_s3_bucket(self, bucket_name, file_key):
        """
        Delete a file from an S3 bucket.

        Args:
            bucket_name (str): The name of the S3 bucket to delete the file from.
            file_key (str): The file key for the file to be deleted.
        """
        log.debug(f"Object ({file_key}) - Deleting file from S3 Bucket ({bucket_name})")
        bucket_name, folder, delete_file_key = self._prepare_s3_bucket_components(
            bucket_name, file_key
        )

        try:
            self.s3t.download_file(bucket_name, delete_file_key)
            log.info(
                f"Object ({file_key}) - Successfully Deleted from S3 Bucket ({bucket_name}/{folder})"
            )

        except botocore.exceptions.ClientError as e:
            self._handle_s3_delete_client_error(bucket_name, file_key, e)

    def _prepare_s3_bucket_components(self, bucket_name, file_key):
        """
        Prepare S3 bucket components.

        Args:
            bucket_name (str): The name of the S3 bucket.
            file_key (str): The file key.

        Returns:
            tuple: A tuple containing the bucket name, folder, and file key.
        """
        if "/" in bucket_name:
            bucket_name, folder = bucket_name.split("/", 1)
            if folder != "" and folder[-1] != "/":
                folder = f"{folder}/"
            file_key = f"{folder}{file_key}"
        else:
            folder = ""

        return bucket_name, folder, file_key

    def _handle_s3_upload_retry_exceeded(self, src_path, bucket_name, file_key, tags):
        """Handle retries exceeded error during S3 upload."""
        log.error(
            {
                "status": "ERROR",
                "message": f"Error uploading to S3 Bucket ({bucket_name}): Retries Exceeded",
            }
        )
        time.sleep(5)
        self.dead_letter_queue.append(
            {
                "src_path": src_path,
                "bucket_name": bucket_name,
                "file_key": file_key,
                "tags": tags,
            }
        )
        print(self.dead_letter_queue)

    def _handle_s3_upload_client_error(self, bucket_name, file_key, error):
        """Handle client error during S3 upload."""
        log.error(
            {"status": "ERROR", "message": f"Error uploading to S3 Bucket: {error}"}
        )
        send_slack_notification(
            slack_client=self.slack_client,
            slack_channel=self.slack_channel,
            slack_message=f"FSWatcher: Error uploading file to {bucket_name} - ({file_key}) :file_folder:",
            alert_type="error",
        )

    def _handle_s3_delete_client_error(self, bucket_name, file_key, error):
        """Handle client error during S3 delete."""
        log.error(
            {"status": "ERROR", "message": f"Error deleting from S3 Bucket: {error}"}
        )
        send_slack_notification(
            slack_client=self.slack_client,
            slack_channel=self.slack_channel,
            slack_message=f"FSWatcher: Error deleting file from {bucket_name} - ({file_key}) :file_folder:",
            alert_type="error",
        )

    def _filter_files_by_date(self, file_paths, date_filter):
        """
        Filter files by a given date filter.

        Args:
            file_paths (list): List of file paths.
            date_filter (datetime): A datetime object to filter files by.

        Returns:
            list: A list of filtered file paths.
        """
        filtered_files = []
        for file_path in file_paths:
            if self._is_newer_than_date_filter(file_path, date_filter):
                filtered_files.append(file_path)
        return filtered_files

    def _is_newer_than_date_filter(self, file_path, date_filter):
        """
        Check if a file is newer than the given date filter.

        Args:
            file_path (str): The file path.
            date_filter (datetime): The date filter.

        Returns:
            bool: True if the file is newer, False otherwise.
        """
        timestamp = datetime.timestamp(date_filter)
        return os.path.getmtime(file_path) > timestamp

    def _compare_files_with_s3_keys(self, files, s3_keys):
        """
        Compare local files with S3 keys and return the files not present in S3.

        Args:
            files (list): A list of local file paths.
            s3_keys (list): A list of S3 object keys.

        Returns:
            list: A list of files not present in S3.
        """
        return list(set(files) - set(s3_keys))

    def _dispatch_file_moved_events(self, files):
        """
        Dispatch FileMovedEvent for each file in the given list.

        Args:
            files (list): A list of file paths.
        """
        for file in files:
            event = FileMovedEvent(file, file)
            self.dispatch(event)

    def backtrack(self, path, date_filter=None):
        all_files = self._get_files(path)
        filtered_files = (
            self._filter_files_by_date(all_files, date_filter)
            if date_filter
            else all_files
        )

        if self.check_with_s3:
            s3_keys = self._get_s3_keys(self.bucket_name)
            unique_files = self._compare_files_with_s3_keys(filtered_files, s3_keys)
        else:
            unique_files = filtered_files

        self._dispatch_file_moved_events(unique_files)

    def _create_test_file(self, test_file):
        with open(test_file, "w") as f:
            f.write("This is a test file")

    # Perform IAM Policy Configuration Test
    def _test_iam_policy(self):
        if os.getenv("TEST_IAM_POLICY") == "true":
            test_filename = "fswatcher_test_file.txt"
            test_file = os.path.join(self.path, test_filename)
            test_event = FileMovedEvent(test_file, test_file)

            file_system_event = FileSystemHandlerEvent(
                event=test_event,
                watch_path=self.path,
                bucket_name=self.bucket_name,
            )

            self._create_test_file(test_file)

            tags = self._generate_object_tags(file_system_event)
            bucket_name, folder, file_key = self._parse_bucket_name_and_key(
                self.bucket_name, test_filename
            )

            self._upload_to_s3_bucket(test_file, bucket_name, file_key, tags)

            log.info("Waiting for file to be added...")
            time.sleep(5)

            if object_exists(self.s3_client, bucket_name, file_key):
                os.remove(test_file)

                if self.allow_delete:
                    self._delete_from_s3_bucket(bucket_name, test_filename)

                    log.info("Waiting for file to be deleted...")
                    time.sleep(5)

                    if not object_exists(self.s3_client, bucket_name, file_key):
                        log.info("Test Passed - IAM Policy Configuration is correct")
                    else:
                        log.error(
                            f"Test Failed - Check IAM Policy Configuration, also clean up the test file in S3 bucket ({self.bucket_name})"
                        )
                        sys.exit(1)
                else:
                    log.info("Test Passed - IAM Policy Configuration is correct")
                    log.warning(
                        "Since allow_delete is set to False, the test file will not be deleted from S3, please delete it manually"
                    )
            else:
                log.error("Test Failed - Check IAM Policy Configuration")
                sys.exit(1)
