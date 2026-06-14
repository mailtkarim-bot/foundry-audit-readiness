#!/bin/bash
# Install readiness and readiness-full wrappers into ~/.local/bin

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/.local/bin"

echo "🔧 Installing readiness wrappers to $INSTALL_DIR"

mkdir -p "$INSTALL_DIR"
cp "$SCRIPT_DIR/readiness" "$INSTALL_DIR/readiness"
cp "$SCRIPT_DIR/readiness-full" "$INSTALL_DIR/readiness-full"
chmod +x "$INSTALL_DIR/readiness"
chmod +x "$INSTALL_DIR/readiness-full"

echo ""
echo "✅ Installed:"
echo "  - $INSTALL_DIR/readiness"
echo "  - $INSTALL_DIR/readiness-full"
echo ""

if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo "⚠️  $INSTALL_DIR is not in your PATH."
    echo "Add this to your ~/.bashrc or ~/.zshrc:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo "Then reload your shell:"
    echo "  source ~/.bashrc"
else
    echo "🚀 You can now run:"
    echo "  readiness        # fast mode (3 tools)"
    echo "  readiness-full   # full mode (7 tools)"
fi
