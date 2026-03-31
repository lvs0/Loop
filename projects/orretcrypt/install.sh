#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔐 OrretCrypt — Installation"
echo "=============================="

if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

echo "📦 Activating venv..."
source .venv/bin/activate

echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -e .

echo ""
echo "✅ Installation complete!"
echo ""
echo "Usage:"
echo "  python3 -m orretcrypt keygen --dir ~/keys"
echo "  python3 -m orretcrypt encrypt --key ~/keys/orretpub.pem --file doc.pdf"
echo "  python3 -m orretcrypt decrypt --key ~/keys/orretpriv.pem --file doc.pdf.orret"
echo ""
echo "Or run directly:"
echo "  .venv/bin/python3 -m orretcrypt keygen"
