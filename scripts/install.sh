#!/usr/bin/env bash
# Sets up the venv, installs rojgar into it, and links the `rojgar`
# command into ~/.local/bin so it works from any directory without
# activating the venv or typing its path every time.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$PROJECT_ROOT/.venv"

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

if command -v rojgar >/dev/null 2>&1; then
    echo "Done. Try: rojgar --help"
else
    echo "$BIN_DIR isn't on your PATH yet. Add this to your shell's rc file"
    echo "(~/.bashrc, ~/.zshrc, etc.), then open a new terminal:"
    echo ""
    echo '  export PATH="$HOME/.local/bin:$PATH"'
fi
