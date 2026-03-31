#!/bin/bash
# OrretCrypt — Script d'installation
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔐 OrretCrypt — Installation"
echo "============================"

# Créer venv si nécessaire
if [ ! -d ".venv" ]; then
    echo "📦 Création de l'environnement virtuel..."
    python3 -m venv .venv
fi

# Activer venv
echo "📦 Activation de l'environnement virtuel..."
source .venv/bin/activate

# Installer dépendances
echo "📦 Installation des dépendances..."
pip install --upgrade pip
pip install kyber-py cryptography ecdsa

echo ""
echo "✅ Installation terminée!"
echo ""
echo "Utilisation:"
echo "  source .venv/bin/activate"
echo "  python3 orretcrypt.py keygen"
echo "  python3 orretcrypt.py encrypt --key pub.pem --file fichier.txt"
echo ""
echo "Ou lancez directement avec:"
echo "  .venv/bin/python3 orretcrypt.py keygen"
