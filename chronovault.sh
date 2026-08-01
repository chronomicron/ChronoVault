#!/bin/bash
# chronovault.sh -- step-by-step test runner for ChronoVault.
# Run from the ChronoVault/ project root: ./chronovault.sh

show_menu() {
    echo ""
    echo "ChronoVault"
    echo "-----------"
    echo "[1] Cleanup Environment (delete archive, databases, reports, test data)"
    echo "[2] Generate Test Data"
    echo "[3] Indexer"
    echo "[4] Importer"
    echo "[5] Audit Archive"
    echo "[6] Duplicate Finder"
    echo "[0] Exit"
    echo ""
    read -p "Choose an option: " choice
}

cleanup_environment() {
    echo "This will permanently delete, if present:"
    echo "  archive/"
    echo "  located_files.db"
    echo "  audit_result.json"
    echo "  duplicate_report.json"
    echo "  test_data/"
    read -p "Are you sure? (y/N): " confirm
    if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
        rm -rf archive
        rm -f located_files.db
        rm -f audit_result.json
        rm -f duplicate_report.json
        rm -rf test_data
        echo "Environment cleaned."
    else
        echo "Cancelled -- nothing was deleted."
    fi
}

generate_test_data_step() {
    python3 generate_test_data/generate_test_data.py --output-dir test_data
}

indexer_step() {
    read -p "Enter the top-level path to search [test_data]: " search_path
    search_path="${search_path:-test_data}"
    search_path="${search_path/#\~/$HOME}"
    python3 indexer/indexer.py indexer/config.json "$search_path"
}

importer_step() {
    python3 importer/importer.py importer/config.json
}

audit_step() {
    python3 audit_archive/audit_archive.py audit_archive/config.json
}

duplicate_finder_step() {
    python3 duplicate_finder/duplicate_finder.py duplicate_finder/config.json
}

while true; do
    show_menu
    case $choice in
        1) cleanup_environment ;;
        2) generate_test_data_step ;;
        3) indexer_step ;;
        4) importer_step ;;
        5) audit_step ;;
        6) duplicate_finder_step ;;
        0) echo "Goodbye!"; exit 0 ;;
        *) echo "Invalid option." ;;
    esac
done
