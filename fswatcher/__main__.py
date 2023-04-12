import sys
import time

from watchdog.observers import Observer

from fswatcher import log
from fswatcher.FileSystemHandler import FileSystemHandler
from fswatcher.FileSystemHandlerConfig import get_config

# Change the log level to info
log.setLevel("INFO")


import os
import time
import sqlite3
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor


def init_db():
    conn = sqlite3.connect("file_info.db")
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS files (
                       file_path TEXT PRIMARY KEY,
                       modified_time REAL)"""
    )

    conn.commit()
    return conn


def update_files_info(conn, file_info):
    cur = conn.cursor()
    cur.execute(
        "REPLACE INTO files (file_path, modified_time) VALUES (?, ?)",
        (file_info["file_path"], file_info["modified_time"]),
    )
    conn.commit()


def delete_file_info(conn, file_path):
    cur = conn.cursor()
    cur.execute("DELETE FROM files WHERE file_path=?", (file_path,))
    conn.commit()


def get_files_info(conn):
    cur = conn.cursor()
    cur.execute("SELECT file_path, modified_time FROM files")
    return {row[0]: row[1] for row in cur.fetchall()}


def check_for_changes(conn, current_files_info):
    new_files = []
    deleted_files = []
    previous_files_info = get_files_info(conn)

    for file, mtime in current_files_info.items():
        if file not in previous_files_info or mtime > previous_files_info[file]:
            new_files.append(file)
            update_files_info(conn, {"file_path": file, "modified_time": mtime})

    for file in previous_files_info:
        if file not in current_files_info:
            deleted_files.append(file)
            delete_file_info(conn, file)

    return new_files, deleted_files


def check_path_exists(path):
    if not Path(path).exists():
        print(f"Path {path} does not exist")
        return False
    return True


def walk_directory(
    path, process_id=0, num_processes=1, excluded_files=None, excluded_exts=None
):
    all_files = []
    for root, _, files in os.walk(path):
        if process_id == hash(root) % num_processes:
            for file in files:
                if (excluded_files and file in excluded_files) or (
                    excluded_exts and os.path.splitext(file)[1] in excluded_exts
                ):
                    continue
                file_path = os.path.join(root, file)
                file_mtime = os.path.getmtime(file_path)
                all_files.append((file_path, file_mtime))
    return all_files


def process_files(conn, all_files):
    current_files_info = {file_path: mtime for file_path, mtime in all_files}
    new_files, deleted_files = check_for_changes(conn, current_files_info)
    return new_files, deleted_files


def main():
    path = "/watch"
    max_workers = 2
    check_interval = 0

    # Add file names or extensions you want to exclude
    # excluded_files = ["file_to_exclude.txt"]
    # excluded_exts = [".log", ".tmp"]

    if not check_path_exists(path):
        print("Path does not exist, exiting...")
        return
    else:
        print(f"Monitoring path: {path}")

    conn = init_db()

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # while True:
        start = time.time()
        time.sleep(
            check_interval
        )  # Wait for 60 seconds before checking for new files again

        # Submit tasks for all worker processes
        all_files_futures = [
            executor.submit(
                walk_directory,
                path,
                process_id=i,
                num_processes=max_workers,
            )
            for i in range(max_workers)
        ]

        # Collect results from all worker processes
        all_files = []
        for future in all_files_futures:
            all_files += future.result()

        # Check for new, updated, and deleted files
        new_files, deleted_files = process_files(conn, all_files)

        if new_files:
            print(f"New or updated files found: {new_files}")
        if deleted_files:
            print(f"Deleted files found: {deleted_files}")

        end = time.time()
        print(f"Time taken: {end - start} seconds")


if __name__ == "__main__":
    main()

# def main() -> None:
#     """
#     Main Function
#     """

#     # Get the configuration dataclass object
#     config = get_config()

#     # Initialize the FileSystemHandler
#     event_handler = FileSystemHandler(config=config)

#     # Initialize the Observer and start watching
#     log.info("Starting observer")
#     observer = Observer()

#     try:
#         observer.schedule(event_handler, config.path, recursive=True)
#         observer.start()

#         # If backtrack is enabled, run the initial scan
#         if config.backtrack:
#             log.info(
#                 "Backtracking enabled, backtracking (This might take awhile if a large amount of directories and files)..."
#             )
#             event_handler.backtrack(
#                 config.path, event_handler.parse_datetime(config.backtrack_date)
#             )
#             log.info("Backtracking complete")
#             config.backtrack = False

#         log.info(f"Watching for file events with INotify Observer in: {config.path}")

#         while True:
#             time.sleep(1)
#     except OSError:
#         log.warning("INotify Limit Reached, falling back to polling observer.")
#         log.warning(
#             "We suggest you increase the inotify limit for better performance, see: https://gist.github.com/coenraadhuman/fa7345e95a9b4dea851dbe9e8f011470"
#         )
#         log.warning(
#             "This is limited by your RAM, 1,000,000 Directory Watches per 1GB of RAM, see: https://unix.stackexchange.com/questions/13751/kernel-inotify-watch-limit-reached"
#         )
#         sys.exit(0)
#     finally:
#         observer.stop()
#         observer.join()


# if __name__ == "__main__":
#     main()
