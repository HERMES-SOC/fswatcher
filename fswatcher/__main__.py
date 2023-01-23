"""
Main File for the AWS File System Watcher
"""

import time
from watchdog.observers import Observer
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

    print(event_handler)
    # Initialize the Observer and start watching
    observer = Observer()
    observer.schedule(event_handler, config.path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    finally:
        observer.stop()
        observer.join()


# Main Function
if __name__ == "__main__":
    main()
