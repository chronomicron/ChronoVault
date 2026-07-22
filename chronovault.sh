#!/bin/bash
# ChronoVault launcher -- run from the ChronoVault project root:
#   ./chronovault.sh

echo "ChronoVault"
echo "-----------"
echo "[1] Indexer"
echo "[2] Importer"
echo "[3] Audit Archive"
echo "[4] Duplicate Finder"
echo "[0] Exit"
echo
read -p "Choose an option: " choice

case $choice in
    1)
        read -p "Enter the top-level path to search: " search_path
        python3 indexer/indexer.py indexer/config.json "$search_path"
        ;;
    2)
        python3 importer/importer.py importer/config.json
        ;;
    3)
        python3 audit_archive/audit_archive.py audit_archive/config.json
        ;;
    4)
        python3 duplicate_finder/duplicate_finder.py duplicate_finder/config.json
        ;;
    0)
        echo "Bye."
        ;;
    *)
        echo "Not a valid option."
        ;;
esac
