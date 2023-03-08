"""
Main File for the AWS File System Watcher
"""

import time
import logging
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from fswatcher.FileSystemHandler import FileSystemHandler
from fswatcher.FileSystemHandlerConfig import get_config


# Main Function
def main() -> None:
    """
    Main Function
    """

    # Get the configuration dataclass object
    config = get_config()

    # Initialize the FileSystemHandler
    event_handler = FileSystemHandler(config=config)

    # Try to use the inotify observer
    try:
        # Initialize the Observer and start watching
        logging.info("Starting observer")
        observer = Observer()
        observer.schedule(event_handler, config.path, recursive=True)
        observer.start()
        logging.info(f"Watching for file events in: {config.path}")

    except OSError:
        # If inotify fails, use the polling observer
        logging.warning("Inotify Observer failed, falling back to polling observer")
        observer = PollingObserver()
        observer.schedule(event_handler, config.path, recursive=True)
        observer.start()
        logging.info(f"Watching for file events in: {config.path}")

    try:
        while True:
            time.sleep(1)
    finally:
        observer.stop()
        observer.join()


# Main Function
if __name__ == "__main__":
    main()
