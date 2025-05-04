"""
ChronoVault scanner module.

Handles recursive scanning of directories to locate images based on file
extensions.

Author: chronomicron@gmail.com
Created: 2025-05-03
"""

import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import chronovault.config as config
import chronovault.archiver as archiver
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def init_scanner():
    """Initialize the scanner module."""
    return "Scanner module initialized"

def scan_directory(scan_dir, vault_dir, status_callback):
    """Recursively scan a directory for images and store results in a temporary file."""
    logging.info(f"Starting scan of {scan_dir}")
    try:
        scan_path = Path(scan_dir)
        if not scan_path.exists():
            status_callback(f"Error: Scan directory does not exist: {scan_path}")
            logging.error(f"Scan directory does not exist: {scan_path}")
            return
        if not scan_path.is_dir():
            status_callback(f"Error: Scan path is not a directory: {scan_path}")
            logging.error(f"Scan path is not a directory: {scan_path}")
            return

        # Load config for image extensions and thread limit
        config_data = config.load_config()
        image_extensions = config.IMAGE_EXTENSIONS
        max_threads = config_data.get("max_threads", 4)

        # Initialize results
        results = {"images": []}
        seen_paths = set()

        def scan_folder(folder):
            """Scan a single folder and return image paths."""
            logging.info(f"Scanning folder: {folder}")
            local_images = []
            try:
                for item in folder.iterdir():
                    try:
                        if not item.exists():
                            status_callback(f"Skipping non-existent item: {item}")
                            logging.warning(f"Non-existent item: {item}")
                            continue
                        if item.is_symlink() and not item.resolve().exists():
                            status_callback(f"Skipping broken symlink: {item}")
                            logging.warning(f"Broken symlink: {item}")
                            continue
                        if item.is_file() and item.suffix.lower() in image_extensions:
                            if item not in seen_paths:
                                seen_paths.add(item)
                                local_images.append(str(item))
                                status_callback(f"Found image: {item}")
                                logging.info(f"Found image: {item}")
                        elif item.is_dir():
                            status_callback(f"Entering directory: {item}")
                            local_images.extend(scan_folder(item))
                        else:
                            status_callback(f"Skipping non-image: {item}")
                            logging.debug(f"Skipping non-image: {item}")
                    except PermissionError as e:
                        status_callback(f"Error: Permission denied accessing {item}: {e}")
                        logging.error(f"Permission denied: {item}: {e}")
                    except OSError as e:
                        status_callback(f"Error: OS error accessing {item}: {e}")
                        logging.error(f"OS error: {item}: {e}")
                    except Exception as e:
                        status_callback(f"Error: Failed to process {item}: {e}")
                        logging.error(f"Failed to process {item}: {e}")
            except PermissionError as e:
                status_callback(f"Error: Permission denied scanning {folder}: {e}")
                logging.error(f"Permission denied scanning {folder}: {e}")
            except Exception as e:
                status_callback(f"Error: Failed to scan {folder}: {e}")
                logging.error(f"Failed to scan {folder}: {e}")
            return local_images

        # Use thread pool for scanning
        status_callback(f"Starting scan with {max_threads} threads")
        logging.info(f"Starting scan with {max_threads} threads")
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            future = executor.submit(scan_folder, scan_path)
            results["images"] = future.result()

        # Save results to temporary file
        temp_file = Path("scan_results.json")
        try:
            with temp_file.open('w') as f:
                json.dump(results, f, indent=4)
            status_callback(f"Scan results saved to {temp_file}")
            logging.info(f"Scan results saved to {temp_file}")
        except PermissionError as e:
            status_callback(f"Error: Permission denied writing to {temp_file}: {e}")
            logging.error(f"Permission denied writing to {temp_file}: {e}")
        except Exception as e:
            status_callback(f"Error: Failed to write scan results: {e}")
            logging.error(f"Failed to write scan results: {e}")

    except Exception as e:
        status_callback(f"Error: Scan failed: {e}")
        logging.error(f"Scan failed: {e}")