#!/usr/bin/env bash
# ChronoVault first-run bootstrap for Linux and macOS.
# Checks for Python 3.8+, then launches the adjacent initialize.py program.
# If Python is missing, inaccessible, or too old, prints steps to resolve it.
# This launcher does not check Python packages or install software.

set -u

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INITIALIZER="${SCRIPT_DIR}/initialize.py"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=8

if [[ ! -f "${INITIALIZER}" ]]; then
    printf 'ChronoVault setup error: initializer not found: %s\n' "${INITIALIZER}" >&2
    exit 1
fi

PYTHON=""
FOUND_PYTHON=""
PYTHON_TOO_OLD=""
PYTHON_RUN_ERROR=""
for candidate in python3 python; do
    if command -v "${candidate}" >/dev/null 2>&1; then
        candidate_path="$(command -v "${candidate}")"
        FOUND_PYTHON="${candidate_path}"
        probe_output="$("${candidate_path}" -c \
            "import sys; print('%s.%s.%s' % sys.version_info[:3]); sys.exit(0 if sys.version_info >= (${MIN_PYTHON_MAJOR}, ${MIN_PYTHON_MINOR}) else 10)" \
            2>&1)"
        probe_status=$?
        if [[ ${probe_status} -eq 0 ]]; then
            PYTHON="${candidate_path}"
            break
        elif [[ ${probe_status} -eq 10 ]]; then
            PYTHON_TOO_OLD="${candidate_path}: Python ${probe_output}"
        else
            PYTHON_RUN_ERROR="${candidate_path}: ${probe_output:-could not run the interpreter}"
        fi
    fi
done

if [[ -z "${PYTHON}" ]]; then
    if [[ -z "${FOUND_PYTHON}" ]]; then
        printf 'ChronoVault setup could not find a Python interpreter.\n' >&2
    elif [[ -n "${PYTHON_TOO_OLD}" ]]; then
        printf 'ChronoVault setup found Python, but it is too old: %s\n' "${PYTHON_TOO_OLD}" >&2
    else
        printf 'ChronoVault setup found Python, but could not run it: %s\n' "${PYTHON_RUN_ERROR}" >&2
    fi
    printf 'A working Python %s.%s or newer is required.\n' \
        "${MIN_PYTHON_MAJOR}" "${MIN_PYTHON_MINOR}" >&2
    case "$(uname -s 2>/dev/null || printf 'unknown')" in
        Darwin)
            printf '%s\n' 'Next steps: install Python 3.8 or newer using an approved macOS installer or package manager.' >&2
            ;;
        Linux)
            printf '%s\n' 'Next steps: install Python 3.8 or newer using your Linux distribution’s software center or package manager.' >&2
            ;;
        *)
            printf '%s\n' 'Next steps: install Python 3.8 or newer using this system’s approved installer or package manager.' >&2
            ;;
    esac
    printf '%s\n' 'If Python is already installed, make sure its executable is on PATH; check with `command -v python3` and `python3 --version`.' >&2
    printf '%s\n' 'If it is blocked by permissions or cannot run, ask your system administrator or IT support to allow it or provide an approved user-level Python.' >&2
    printf '%s\n' 'After installation or an access change, open a new terminal and run this bootstrap again.' >&2
    printf '%s\n' 'No software was installed or changed.' >&2
    exit 1
fi

PYTHON_VERSION="$("${PYTHON}" --version 2>&1)"
printf 'Starting ChronoVault setup with %s (%s)\n' "${PYTHON}" "${PYTHON_VERSION}"
exec "${PYTHON}" "${INITIALIZER}" "$@"
