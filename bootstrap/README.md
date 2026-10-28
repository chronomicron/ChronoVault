# ChronoVault Bootstrap

This directory will hold the first-run setup launchers and their Python setup
program. The intended entry points are:

- `bootstrap.sh` for Linux and macOS
- `bootstrap.bat` as a future Windows launcher
- `initialize.py` for dependency checks, workspace folder creation, and
  GUI-managed per-tool configuration setup

## Current status

`bootstrap.sh` checks for Python 3.8 or newer and launches the adjacent
`initialize.py`, forwarding any command-line arguments. If Python is missing,
too old, or cannot be run, it explains the problem, gives OS-specific starting
steps, and stops. It does not install Python or check Python package
dependencies.

`bootstrap.bat` and `initialize.py` remain placeholders. The initializer
currently reports that setup is not implemented; it does not inspect package
dependencies, create directories, or write configuration files.

The eventual platform launchers should first locate a supported Python
interpreter without depending on Python themselves. Linux/macOS use the shell
launcher; Windows uses its native launcher. If no supported interpreter is
available, the launcher should identify the operating system as well as it
can, show appropriate Python installation instructions, and stop without
trying to run Python code or silently installing software.

Once Python is available, the shell launcher should automatically start
`initialize.py`. That Python program should own the dependency checks, reusing
the useful checks already in `test_functions/test_env.py` rather than running
a second dependency-checking app. The shell should not repeat package checks.
Required missing dependencies should get clear installation guidance and
block setup; optional gaps should be reported without blocking unrelated
features. Workspace- and database-specific checks should use the user's
selected paths, not assume the repository root. GUI-managed configurations
should be kept separate from the standalone configurations in each tool's
module directory. If `test_env.py` remains a standalone diagnostic, it should
call the same shared check logic rather than maintain a second implementation.

## Planned setup responsibilities

1. Native launchers check that a supported Python runtime is available and
   give OS-specific installation guidance if it is missing. The Linux/macOS
   shell launcher is implemented; the Windows launcher is still a placeholder.
2. The shell launcher automatically starts the Python initializer. The
   initializer should check required and optional dependencies using shared
   environment-check logic.
3. Ask for or confirm the user's workspace and archive locations.
4. Create only the required workspace directories, without deleting or
   overwriting existing user data.
5. Prepare GUI-managed configuration files for the individual tools.
6. Validate the resulting paths and configurations before the first scan.

See the root `TODO.md` and `roadmap.md` for the planned first-run bootstrap
work. This scaffold is not an installer and does not yet make ChronoVault
ready to run on a new computer.
