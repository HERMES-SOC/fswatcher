import argparse
import sys
import os
import time
from datetime import datetime
from urllib import parse
import boto3
import botocore
from hermes_core import log
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent, FileMovedEvent, FileDeletedEvent


class FileSystemHandler(FileSystemEventHandler):
    """
    Subclass to handle file system events
    """

    def __init__(self, path, bucket_name, profile=None, src_limit=100000):
        """
        Overloaded Constructor
        """
        # Initialize the src limit (Max number of src paths to store in memory)
        self.src_limit = src_limit

        # Initialize the src list
        self.src = []

        # Check if bucket name is and accessible using boto
        try:
            # Initialize Boto3 Session
            self.boto3_session = boto3.session.Session(profile_name=profile) if profile else boto3.session.Session()

            # Initialize S3 Client
            s3 = self.boto3_session.resource("s3")

            # Check if bucket exists
            s3.meta.client.head_bucket(Bucket=bucket_name)

        except botocore.exceptions.ClientError as e:
            # If a client error is thrown, then check that it was a 404 error.
            # If it was a 404 error, then the bucket does not exist.
            error_code = int(e.response["Error"]["Code"])
            if error_code == 404:
                log.error(
                    {
                        "status": "ERROR",
                        "message": f"Bucket ({bucket_name}) does not exist",
                    }
                )

                sys.exit(1)

        # Initialize the bucket name
        self.bucket_name = bucket_name

        # Validate the path
        if not os.path.exists(path):
            log.error({"status": "ERROR", "message": f"Path ({path}) does not exist"})

            sys.exit(1)

        # Path to watch
        self.path = path

        log.info(f"Watching for file events in: {path}")

    def on_any_event(self, event):
        """
        Overloaded Function to deal with any event
        """
        # Skip if directory
        if event.is_directory:
            return None

        # Skip if file is hermes.log file
        if "hermes.log" in event.src_path:
            return None

        # Handle File Creation Event if it is a FileCreatedEvent
        if isinstance(event, FileCreatedEvent):
            self._file_handler(event.src_path, self.bucket_name, "CREATE")

        # Handle File Modification Event
        elif isinstance(event, FileModifiedEvent):
            self._file_handler(event.src_path, self.bucket_name, "PUT")

        # Handle File Move Event
        elif isinstance(event, FileMovedEvent):
            self._file_handler(event.src_path, self.bucket_name, "PUT", event.dest_path)

        # Handle File Deletion Event
        elif isinstance(event, FileDeletedEvent):
            self._file_handler(event.src_path, self.bucket_name, "DELETE")


    def _file_handler(self, src_path, bucket_name, action_type, dest_path=None):
        """
        Function to handle file events and upload to S3
        """
        try:
            # Validate Action Type
            if action_type not in ["CREATE", "PUT", "DELETE"]:
                raise ValueError("Invalid Action Type")
            
            # Skip if duplicate event
            if src_path in self.src and dest_path is not None:
                return None

            # Set path to use
            path_to_use = dest_path if dest_path is not None else src_path
            
            # Capital Case Action Type
            action_type_capped = action_type.capitalize()
            log.info(
                f"Object ({self._parse_src_path(src_path)}) - File {action_type_capped}: {self._parse_src_path(src_path) + (f' to {dest_path}' if dest_path is not None else '')}"
            )


            if action_type != "DELETE":
                # Generate Object Tags String
                tags = self._generate_object_tags(path_to_use, self._parse_src_path(path_to_use))

                # Upload to S3 Bucket
                self._upload_to_s3_bucket(
                    boto3_session=self.boto3_session,
                    src_path=path_to_use,
                    bucket_name=bucket_name,
                    file_key=self._parse_src_path(path_to_use),
                    tags=tags,
                )

            # Log to Timestream
            self._log(
                boto3_session=self.boto3_session,
                action_type=action_type,
                file_key=path_to_use,
                new_file_key=self._parse_src_path(path_to_use),
                source_bucket="SDC External Server",
                destination_bucket=None if action_type == "DELETE" else bucket_name,
            )

            # Cleans up the src list
            if len(self.src) >= self.src_limit:
                # Get half of the src limit and remove the first half
                self.src = self.src[int(self.src_limit / 2) :]

            # Append the src path to the src list
            self.src.append(src_path)

        except Exception as e:
            log.error({"status": "ERROR", "message": f"Error handling file skipping to next: {e}"})


    def _parse_src_path(self, src_path):
        """
        Function to return parsed src path
        """
        # Strip path from src_path by splitting on the path by src_path      
        parsed_src_path = src_path.split(f"{self.path}/")[1]

        return parsed_src_path

    @staticmethod
    def _generate_object_tags(src_path, parsed_src_path):
        """
        Function to generate object tags and return as a url encoded string
        """
        log.info(f"Object ({parsed_src_path}) - Generating S3 Object Tags")
        try:
            # Both the variables would contain time
            # elapsed since EPOCH in float
            ti_c = os.path.getctime(src_path)
            ti_m = os.path.getmtime(src_path)

            # Converting the time in seconds to a timestamp
            c_ti = time.ctime(ti_c)
            m_ti = time.ctime(ti_m)

            # Log Object Creation and Modification Times
            log.info(f"Object ({parsed_src_path}) - Creation Time: {c_ti}")
            log.info(f"Object ({parsed_src_path}) - Modification Time: {m_ti}")

            # Tags to be applied to the object
            tags = {
                "Created_Time": c_ti,
                "Created_Epoch": ti_c,
                "Modified_Time": m_ti,
                "Modified_Epoch": ti_m,
            }

            return parse.urlencode(tags)

        except Exception as e:
            log.error(
                {"status": "ERROR", "message": f"Error generating object tags: {e}"}
            )


    @staticmethod
    def _upload_to_s3_bucket(boto3_session, src_path, bucket_name, file_key, tags):
        """
        Function to Upload a file to an S3 Bucket
        """
        log.info(f"Object ({file_key}) - Uploading file to S3 Bucket ({bucket_name})")
        try:
            # Initialize S3 Client
            s3 = boto3_session.resource("s3")

            # Upload to S3 Bucket
            s3.meta.client.upload_file(
                src_path,
                bucket_name,
                file_key,
                ExtraArgs={"Tagging": tags},
            )

            log.info(
                f"Object ({file_key}) - Successfully Uploaded to S3 Bucket ({bucket_name})"
            )

        except botocore.exceptions.ClientError as e:
            log.error(
                {"status": "ERROR", "message": f"Error uploading to S3 Bucket: {e}"}
            )


    @staticmethod
    def _log(
        boto3_session,
        action_type,
        file_key,
        new_file_key=None,
        source_bucket=None,
        destination_bucket=None,
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
                DatabaseName="sdc_aws_logs",
                TableName="sdc_aws_s3_bucket_log_table",
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

            log.info((f"Object ({new_file_key}) - Event Successfully Logged to Timestream"))

        except botocore.exceptions.ClientError as e:
            log.error(
                {"status": "ERROR", "message": f"Error logging to Timestream: {e}"}
            )


# Main Function
if __name__ == "__main__":
    # Initialize Argument Parser
    parser = argparse.ArgumentParser()

    # Add Argument to parse directory path to be watched
    parser.add_argument("-d", "--directory", help="Directory Path to be Watched")


    # Add Argument to parse S3 Bucket Name to upload files to
    parser.add_argument("-b", "--bucket_name", help="User name")

    # Add Argument to profile to use when connecting to AWS
    parser.add_argument(
        "-p", "--profile", help="AWS Profile to use when connecting to AWS"
    )

    args = parser.parse_args()

    if args.directory and args.bucket_name:
        path = args.directory
        # Get the absolute path of the directory
        path = os.path.abspath(path)
        bucket_name = args.bucket_name
        if args.profile != '':
            profile = args.profile

    else:
        print("Please provide both the directory path and bucket name")
        sys.exit(1)

    # Initialize the FileSystemHandler
    event_handler = FileSystemHandler(
        path=path, bucket_name=bucket_name, profile=profile
    )

    # Initialize the Observer and start watching
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    finally:
        observer.stop()
        observer.join()
