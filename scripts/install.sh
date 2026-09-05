#!/usr/bin/env bash
# Sets up the venv, installs rojgar into it, and links the `rojgar`
# command into ~/.local/bin so it works from any directory without
# activating the venv or typing its path every time.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$PROJECT_ROOT/.venv"

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 not found -- install Python 3.10+ first, then re-run this script." >&2
    exit 1
fi

PY_OK=$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 10) else 0)')
if [ "$PY_OK" != "1" ]; then
    echo "rojgar needs Python 3.10+, found $(python3 --version)." >&2
    exit 1
fi

if [ ! -d "$VENV" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV"
fi

echo "Installing dependencies..."
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -e "$PROJECT_ROOT"

BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
ln -sf "$VENV/bin/rojgar" "$BIN_DIR/rojgar"

echo "Installed 'rojgar' -> $VENV/bin/rojgar"
echo ""

if command -v rojgar >/dev/null 2>&1; then
    echo "Done. Next steps:"
    echo "  rojgar run     search for jobs (walks you through setup the first time)"
    echo "  rojgar ui      open the web dashboard"
    echo "  rojgar --help  see every command and flag"
else
    echo "$BIN_DIR isn't on your PATH yet. Add this to your shell's rc file"
    echo "(~/.bashrc, ~/.zshrc, etc.), then open a new terminal:"
    echo ""
    echo '  export PATH="$HOME/.local/bin:$PATH"'
    echo ""
    echo "Then: rojgar run"
fi
