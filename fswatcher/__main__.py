import sys
import time

from watchdog.observers import Observer
from aws_sdc_utils.logging import log

from fswatcher.FileSystemHandler import FileSystemHandler
from fswatcher.FileSystemHandlerConfig import get_config


def main() -> None:
    """
    Main Function
    """

    # Get the configuration dataclass object
    config = get_config()

    # Initialize the FileSystemHandler
    event_handler = FileSystemHandler(config=config)

    # Initialize the Observer and start watching
    log.info("Starting observer")
    observer = Observer()

    try:
        observer.schedule(event_handler, config.path, recursive=True)
        observer.start()

        # If backtrack is enabled, run the initial scan
        if config.backtrack:
            log.info(
                "Backtracking enabled, backtracking (This might take awhile if a large amount of directories and files)..."
            )
            event_handler.backtrack(
                config.path, event_handler.parse_datetime(config.backtrack_date)
            )
            log.info("Backtracking complete")
            config.backtrack = False

        log.info(f"Watching for file events with INotify Observer in: {config.path}")

        while True:
            time.sleep(1)
    except OSError:
        log.warning("INotify Limit Reached, falling back to polling observer.")
        log.warning(
            "We suggest you increase the inotify limit for better performance, see: https://gist.github.com/coenraadhuman/fa7345e95a9b4dea851dbe9e8f011470"
        )
        log.warning(
            "This is limited by your RAM, 1,000,000 Directory Watches per 1GB of RAM, see: https://unix.stackexchange.com/questions/13751/kernel-inotify-watch-limit-reached"
        )
        sys.exit(0)
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
