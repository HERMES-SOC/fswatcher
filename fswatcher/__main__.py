"""
Main File for the AWS File System Watcher
"""
import sys
import time
import logging
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from fswatcher.FileSystemHandler import FileSystemHandler
from fswatcher.FileSystemHandlerConfig import get_config

# Configure logging
logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

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
        print(observer.event_queue.maxsize)
        observer.start()
        # If backtrack is enabled, run the initial scan
        if config.backtrack:
            # Dispatch an empty event to trigger the initial scan
            event_handler.dispatch(None)
            
        logging.info(f"Watching for file events with INotify Observer in: {config.path}")

    except OSError:
        # If inotify fails, use the polling observer
        logging.warning("INotify Limit Reached, falling back to polling observer.")
        logging.warning("We suggest you increase the inotify limit for better performance, see: https://gist.github.com/coenraadhuman/fa7345e95a9b4dea851dbe9e8f011470")
        try:
            observer = PollingObserver()
            observer.schedule(event_handler, config.path, recursive=True)
            observer.start()
            logging.info(f"Watching for file events in: {config.path}")
        except Exception as e:
            logging.error(f"Failed to initialize observer: {e}")
            sys.exit(0)
    try:
        while True:
            time.sleep(1)
    finally:
        observer.stop()
        observer.join()


# Main Function
if __name__ == "__main__":
    main()
