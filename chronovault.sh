#!/bin/bash
# chronovault.sh -- step-by-step test runner for ChronoVault.
# Run from the ChronoVault/ project root: ./chronovault.sh
#
# CONTAINMENT: every test artifact this script creates -- generated test
# data, located_files.db, archive/ (including archive_database.db), and
# every JSON report -- lives inside ./chronovault_test/, never at the
# project root. That means:
#   - Cleanup (option 1) is always a single, safe folder delete. It can
#     never touch a REAL archive you might have sitting at the project
#     root from actual use, because it never looks there.
#   - Add "chronovault_test/" to .gitignore once and nothing this script
#     creates will ever show up in `git status`.
#
# HOW THIS WORKS: every ChronoVault tool already resolves its own
# database/archive/report paths relative to the CURRENT WORKING DIRECTORY
# it's invoked from, not relative to its own config.json (documented in
# e.g. indexer/README.md) -- that was a deliberate existing design choice.
# This script takes advantage of it by cd-ing into chronovault_test/
# before calling each tool with its real, completely unmodified
# config.json. No config files or tool code needed to change for this.

TEST_ROOT="chronovault_test"

show_menu() {
    echo ""
    echo "ChronoVault Test Runner"
    echo "------------------------"
    echo "All test artifacts live in: $TEST_ROOT/"
    echo ""
    echo "-- Pipeline --"
    echo "[1]  Cleanup Test Environment (delete everything in $TEST_ROOT/)"
    echo "[2]  Generate Test Data"
    echo "[3]  Indexer"
    echo "[4]  Condition Database (hash + date + mark duplicates, before import)"
    echo "[5]  Importer"
    echo "[6]  Audit Archive"
    echo "[7]  Duplicate Finder"
    echo ""
    echo "-- Module Tests (test_functions/) --"
    echo "[8]  Test Environment (dependency check)"
    echo "[9]  Test Retrieve Data (review-bucket read layer)"
    echo "[10] Test Write Data (apply a correction + before/after Audit diff)"
    echo "[11] Test Analyze Date (single file, choose path + options)"
    echo "[12] Test OCR Date (needs real photos placed in $TEST_ROOT/OCR_test_images/)"
    echo ""
    echo "[0]  Exit"
    echo ""
    read -p "Choose an option: " choice
}

ensure_test_root() {
    mkdir -p "$TEST_ROOT"
}

cleanup_environment() {
    echo "This will permanently delete the entire '$TEST_ROOT/' folder and everything in it:"
    echo "  generated test data, located_files.db, archive/, and every generated report."
    echo "(Nothing outside '$TEST_ROOT/' is touched -- a real archive at the project root,"
    echo " if you have one from actual use, is completely unaffected.)"
    read -p "Are you sure? (y/N): " confirm
    if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
        rm -rf "$TEST_ROOT"
        mkdir -p "$TEST_ROOT"
        echo "Test environment cleaned -- '$TEST_ROOT/' is now empty."
    else
        echo "Cancelled -- nothing was deleted."
    fi
}

generate_test_data_step() {
    ensure_test_root
    # NOTED, NOT YET BUILT: generate_test_data.py should grow two more
    # scenario categories once this containment change has settled --
    #   1) a folder using a French month name (e.g. "mars 2024") to
    #      exercise analyze_folder.py's planned French MONTH_NAMES support.
    #   2) a hidden folder (e.g. ".hidden_backup") with real matching files
    #      inside it, to actually VERIFY Indexer's rglob walks into it,
    #      rather than continuing to just assume it does.
    # Both are tracked in roadmap.md -- flagged here so they aren't
    # forgotten once this script itself is working end to end.
    (cd "$TEST_ROOT" && python3 "../generate_test_data/generate_test_data.py" --output-dir test_data)
}

indexer_step() {
    ensure_test_root
    read -p "Path to search, relative to $TEST_ROOT/ (or an absolute path like ~/Pictures) [test_data]: " search_path
    search_path="${search_path:-test_data}"
    search_path="${search_path/#\~/$HOME}"
    (cd "$TEST_ROOT" && python3 "../indexer/indexer.py" "../indexer/config.json" "$search_path")
}

condition_database_step() {
    ensure_test_root
    (cd "$TEST_ROOT" && python3 "../condition_database/condition_database.py" "../condition_database/config.json")
}

importer_step() {
    ensure_test_root
    (cd "$TEST_ROOT" && python3 "../importer/importer.py" "../importer/config.json")
}

audit_step() {
    ensure_test_root
    (cd "$TEST_ROOT" && python3 "../audit_archive/audit_archive.py" "../audit_archive/config.json")
}

duplicate_finder_step() {
    ensure_test_root
    (cd "$TEST_ROOT" && python3 "../duplicate_finder/duplicate_finder.py" "../duplicate_finder/config.json")
}

test_env_step() {
    # Deliberately NOT run inside $TEST_ROOT. test_env.py checks real
    # project-root paths for its OWN archive/database integrity checks
    # (see test_functions/test_env.py) -- that's about a real archive at
    # the project root if you have one, not the test one, so this always
    # runs from the project root regardless of $TEST_ROOT's contents.
    python3 test_functions/test_env.py
}

test_retrieve_data_step() {
    ensure_test_root
    if [ ! -f "$TEST_ROOT/archive/archive_database.db" ]; then
        echo "No archive found in $TEST_ROOT/ yet -- run Importer (option 5) at least once first."
        return
    fi
    (cd "$TEST_ROOT" && python3 "../test_functions/test_retrieve_data.py")
}

test_write_data_step() {
    ensure_test_root
    if [ ! -f "$TEST_ROOT/audit_result.json" ]; then
        echo "No audit_result.json found in $TEST_ROOT/ yet -- run Audit Archive (option 6) at least once first."
        return
    fi
    (cd "$TEST_ROOT" && python3 "../test_functions/test_write_data.py")
}

test_analyze_date_step() {
    ensure_test_root
    read -p "Path to a file, relative to $TEST_ROOT/ (e.g. test_data/DCIM/Camera/match_0001.jpg): " file_path
    if [ -z "$file_path" ]; then
        echo "No file given -- cancelled."
        return
    fi
    read -p "Override file type? (e.g. .tiff) [leave blank to auto-detect from extension]: " file_type
    read -p "Also try OCR corner-stamp scanning? (y/N): " try_ocr

    args=("$file_path")
    if [ -n "$file_type" ]; then
        args+=(--type "$file_type")
    fi
    if [[ "$try_ocr" == "y" || "$try_ocr" == "Y" ]]; then
        args+=(--try-ocr)
    fi

    (cd "$TEST_ROOT" && python3 "../test_functions/test_analyze_date.py" "${args[@]}")
}

test_ocr_date_step() {
    ensure_test_root
    mkdir -p "$TEST_ROOT/OCR_test_images"
    echo "Looking for real-world test photos in $TEST_ROOT/OCR_test_images/ ..."
    echo "(This test needs REAL downloaded or scanned photos with visible date stamps --"
    echo " generate_test_data.py's synthetic files won't exercise OCR meaningfully.)"
    (cd "$TEST_ROOT" && python3 "../test_functions/test_ocr_date.py")
}

while true; do
    show_menu
    case $choice in
        1) cleanup_environment ;;
        2) generate_test_data_step ;;
        3) indexer_step ;;
        4) condition_database_step ;;
        5) importer_step ;;
        6) audit_step ;;
        7) duplicate_finder_step ;;
        8) test_env_step ;;
        9) test_retrieve_data_step ;;
        10) test_write_data_step ;;
        11) test_analyze_date_step ;;
        12) test_ocr_date_step ;;
        0) echo "Goodbye!"; exit 0 ;;
        *) echo "Invalid option." ;;
    esac
done
