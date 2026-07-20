import json
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

def load_config(config_file):
    """Load the JSON configuration file and return database path and extensions."""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        database_path = config.get('database_path')
        extensions = config.get('extensions', [])
        if not database_path:
            print("Error: 'database_path' not specified in configuration file.")
            sys.exit(1)
        return database_path, extensions
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Configuration file '{config_file}' is not valid JSON.")
        sys.exit(1)

def init_database(db_path):
    """Initialize the database and create the located_files table if it doesn't exist."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS located_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            file_extension TEXT,
            file_size INTEGER,
            creation_date TEXT,
            modification_date TEXT,
            status TEXT DEFAULT 'located'
        )
    ''')
    conn.commit()
    return conn

def find_files(root_path, extensions):
    """Recursively walk through the directory hierarchy and find files matching the extensions."""
    matching_files = []

    root = Path(root_path)
    if not root.exists():
        print(f"Error: Path '{root_path}' does not exist.")
        sys.exit(1)

    if not root.is_dir():
        print(f"Error: '{root_path}' is not a directory.")
        sys.exit(1)

    try:
        for file_path in root.rglob('*'):
            if file_path.is_file():
                file_extension = file_path.suffix.lower()
                for ext in extensions:
                    ext_normalized = ext.lower() if ext.startswith('.') else '.' + ext.lower()
                    if file_extension == ext_normalized:
                        matching_files.append(file_path)
                        break
    except PermissionError as e:
        print(f"Error: Permission denied accessing '{root_path}': {e}")
        sys.exit(1)

    return matching_files

def store_files(conn, files):
    """Insert found files into the database. Skips files already present (by file_path)."""
    cursor = conn.cursor()
    inserted = 0
    skipped = 0

    for file_path in files:
        try:
            stat = file_path.stat()
            file_extension = file_path.suffix.lower()
            file_size = stat.st_size
            creation_date = datetime.fromtimestamp(stat.st_ctime).isoformat()
            modification_date = datetime.fromtimestamp(stat.st_mtime).isoformat()

            cursor.execute('''
                INSERT OR IGNORE INTO located_files
                (file_path, file_extension, file_size, creation_date, modification_date, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (str(file_path), file_extension, file_size, creation_date, modification_date, 'located'))

            if cursor.rowcount > 0:
                inserted += 1
            else:
                skipped += 1

        except OSError as e:
            print(f"Warning: Could not read metadata for '{file_path}': {e}")

    conn.commit()
    return inserted, skipped

def main():
    if len(sys.argv) != 3:
        print("Usage: python indexer.py <config.json> <top_level_path>")
        print("Example: python indexer.py config.json /home/user/documents")
        sys.exit(1)

    config_file = sys.argv[1]
    root_path = sys.argv[2]

    print(f"Loading configuration from: {config_file}")
    database_path, extensions = load_config(config_file)

    if not extensions:
        print("Error: No extensions specified in configuration file.")
        sys.exit(1)

    print(f"Database path: {database_path}")
    print(f"Looking for file extensions: {extensions}")
    print(f"Searching in: {root_path}")
    print("-" * 60)

    conn = init_database(database_path)

    files = find_files(root_path, extensions)
    print(f"Found {len(files)} matching file(s) on disk.")

    inserted, skipped = store_files(conn, files)
    conn.close()

    print("-" * 60)
    print(f"Inserted into database: {inserted}")
    print(f"Already in database (skipped): {skipped}")
    print(f"Total matching files: {len(files)}")

if __name__ == "__main__":
    main()

    