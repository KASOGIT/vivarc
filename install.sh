#!/bin/sh
# Thin wrapper: Vivarc is a single Python 3 script (standard library only; python3 ships with macOS tools).
set -e
cd "$(dirname "$0")"
command -v python3 >/dev/null 2>&1 || { echo "python3 not found. Install Xcode command line tools: xcode-select --install" >&2; exit 1; }
exec python3 vivarc.py "${@:-install}"
