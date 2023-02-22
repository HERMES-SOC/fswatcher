"""
Utility functions for fswatcher.
"""
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Create log file handler if file log environment variable is set
if os.environ.get("FILE_LOGGING") == "true":
    log.info("File logging enabled")
    file_handler = logging.FileHandler("fswatcher.log")
    file_handler.setLevel(logging.INFO)

    # Create formatter and add it to the handlers
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)

    # Add the handlers to the logger
    log.addHandler(file_handler)

# Configure boto3 logging to debug
boto3_log = logging.getLogger("boto3")
boto3_log.setLevel(logging.DEBUG)
