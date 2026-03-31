#!/bin/bash
# ═══════════════════════════════════════════════════════════
# Orretter GitHub Setup — ONE-TIME ONLY
# ═══════════════════════════════════════════════════════════
# Run this ONCE when you create the orretter GitHub account.

set -e

echo "🔐 Orretter GitHub Setup"
echo "========================"

# 1. Show SSH key — you need to add this to GitHub
echo ""
echo "STEP 1 — Add this SSH key to GitHub:"
echo "(Go to GitHub.com → Settings → SSH Keys → New SSH key)"
echo ""
cat ~/.ssh/id_orretter.pub
echo ""
echo "Press Enter when done..."
read

# 2. Check gh auth
echo ""
echo "STEP 2 — Authenticate gh with GitHub:"
echo "Run this command manually:"
echo "  gh auth login --hostname github.com"
echo "  (Choose: HTTPS, Yes to authenticate via browser)"
echo ""
echo "Press Enter when done..."
read

# 3. Create repo and push
echo ""
echo "STEP 3 — Creating orretcrypt repo..."
cd ~/soe/projects/orretcrypt

gh repo create orretter/orretcrypt --public --source=. --push 2>/dev/null || \
  gh repo create orretter/orretcrypt --public --push 2>/dev/null || \
  echo "Repo may already exist. Check github.com/orretter/orretcrypt"

echo ""
echo "✅ Done! Check github.com/orretter/orretcrypt"
