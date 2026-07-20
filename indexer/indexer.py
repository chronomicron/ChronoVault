import json
import sys
import os
from pathlib import Path

def load_config(config_file):
    """Load the JSON configuration file and return the list of extensions to search for."""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        return config.get('extensions', [])
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Configuration file '{config_file}' is not valid JSON.")
        sys.exit(1)

def find_files(root_path, extensions):
    """Recursively walk through the directory hierarchy and find files matching the extensions."""
    matching_files = []
    
    try:
        root = Path(root_path)
        if not root.exists():
            print(f"Error: Path '{root_path}' does not exist.")
            sys.exit(1)
        
        if not root.is_dir():
            print(f"Error: '{root_path}' is not a directory.")
            sys.exit(1)
        
        # Recursively walk through all directories
        for file_path in root.rglob('*'):
            if file_path.is_file():
                file_extension = file_path.suffix.lower()  # Get extension with the dot
                # Check if extension matches (with or without the dot in config)
                for ext in extensions:
                    ext_normalized = ext.lower() if ext.startswith('.') else '.' + ext.lower()
                    if file_extension == ext_normalized:
                        matching_files.append(str(file_path))
                        break
    
    except PermissionError as e:
        print(f"Error: Permission denied accessing '{root_path}': {e}")
        sys.exit(1)
    
    return matching_files

def main():
    # Check if we have the required arguments
    if len(sys.argv) != 3:
        print("Usage: python indexer.py  ")
        print("Example: python indexer.py config.json /home/user/documents")
        sys.exit(1)
    
    config_file = sys.argv[1]
    root_path = sys.argv[2]
    
    print(f"Loading configuration from: {config_file}")
    extensions = load_config(config_file)
    
    if not extensions:
        print("Error: No extensions specified in configuration file.")
        sys.exit(1)
    
    print(f"Looking for file extensions: {extensions}")
    print(f"Searching in: {root_path}")
    print("-" * 60)
    
    # Find all matching files
    files = find_files(root_path, extensions)
    
    print(f"Found {len(files)} matching file(s):")
    print("-" * 60)
    for file_path in files:
        print(file_path)
    
    print("-" * 60)
    print(f"Total: {len(files)} file(s)")

if __name__ == "__main__":
    main()