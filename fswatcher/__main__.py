import os
import time
import sqlite3
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import psycopg2


def init_db():
    conn = psycopg2.connect(
        dbname="mydb",
        user="postgres",
        password="password",
        host="localhost",
        port="5432",
    )
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
        "INSERT INTO files (file_path, modified_time) VALUES (%s, %s) "
        "ON CONFLICT (file_path) DO UPDATE SET modified_time = EXCLUDED.modified_time",
        (file_info["file_path"], file_info["modified_time"]),
    )
    conn.commit()


def delete_file_info(conn, file_path):
    cur = conn.cursor()
    cur.execute("DELETE FROM files WHERE file_path=%s", (file_path,))
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
    for root, _, files in os.walk(path, followlinks=True):
        if process_id == hash(root) % num_processes:
            for file in files:
                if not excluded_files or not excluded_exts:
                    if (
                        file in excluded_files
                        or os.path.splitext(file)[1] in excluded_exts
                    ):
                        continue
                    file_path = os.path.join(root, file)
                    real_file_path = os.path.realpath(file_path)
                    file_mtime = os.path.getmtime(real_file_path)
                    all_files.append((real_file_path, file_mtime))
    return all_files


def process_files(conn, all_files):
    current_files_info = {file_path: mtime for file_path, mtime in all_files}
    new_files, deleted_files = check_for_changes(conn, current_files_info)
    return new_files, deleted_files


def main():
    path = "/watch"
    max_workers = 1
    check_interval = 5

    # Initialize excluded_files and excluded_exts as empty lists
    excluded_files = []
    excluded_exts = []
    # # Add file names or extensions you want to exclude
    # excluded_files = ["file_to_exclude.txt"]
    # excluded_exts = [".log", ".tmp"]

    if not check_path_exists(path):
        print("Path does not exist, exiting...")
        return
    else:
        print(f"Monitoring path: {path}")

    conn = init_db()

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        while True:
            start = time.time()
            time.sleep(
                check_interval
            )  # Wait for 60 seconds before checking for new files again
            inner_start = time.time()
            # Submit tasks for all worker processes
            all_files_futures = [
                executor.submit(
                    walk_directory,
                    path,
                    process_id=i,
                    num_processes=max_workers,
                    excluded_files=excluded_files,
                    excluded_exts=excluded_exts,
                )
                for i in range(max_workers)
            ]
            inner_end = time.time()
            print(f"Time taken for inner loop: {inner_end - inner_start}")

            # Collect results from all worker processes
            all_files = []
            for future in all_files_futures:
                all_files += future.result()

            # Check for new, updated, and deleted files
            new_files, deleted_files = process_files(conn, all_files)
            end = time.time()
            print(f"Time taken: {end - start}")
            print(f"Total files found: {len(all_files)}")
            print(f"New or updated files found: {len(new_files)}")
            print(f"Deleted files found: {len(deleted_files)}")
            print(f"Size of db file: {os.path.getsize('file_info.db')} bytes")

            # if new_files:
            #     print(f"New or updated files found: {len(new_files)}")
            # if deleted_files:
            #     print(f"Deleted files found: {len(deleted_files)}")


if __name__ == "__main__":
    main()
