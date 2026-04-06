# GitHub Identity Setup Plan
**Date:** 2026-03-31  
**Agent:** Orretter (Synapse 🧠)  
**Status:** ANALYSIS COMPLETE — AWAITING APPROVAL TO PROCEED

---

## Step 1: Machine Analysis

### Current State

| Check | Result |
|-------|--------|
| `gh` (GitHub CLI) | ❌ NOT installed |
| `git` global user.name | ❌ Not configured |
| `git` global user.email | ❌ Not configured |
| SSH keys (~/.ssh/*.pub) | ❌ None found |
| Package managers | ✅ apt, snap available |
| SOE project | ✅ Well-developed |

### GitHub CLI Installation
```bash
# Option A: apt (slower but official)
sudo apt update && sudo apt install gh

# Option B: snap
sudo snap install gh --classic

# Option C: Binary download (fastest, no sudo needed)
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update && sudo apt install gh
```

**Recommendation:** Option C (binary download) — fastest, no dependency issues.

---

## Step 2: GitHub Identity

### Account Name Decision

Two candidates:
1. **orretter** — short, memorable, matches "Orret" in project name and "Orretter" as the agent identity
2. **synapse-ai** — matches the Synapse 🧠 persona name

**✅ RECOMMENDATION: `orretter`**
- Reason: Short, unique, matches the project's internal naming (Orret), not confused with a general "AI" account
- The persona can still be "Synapse 🧠" on the profile

### Email Strategy (No Cost, No Phone)

GitHub requires a **verified email**. Options:

| Option | Cost | Phone? | Setup Complexity | Notes |
|--------|------|--------|-------------------|-------|
| Cloudflare Email Routing | FREE | No | Medium | Requires domain or free Cloudflare account |
| Proton Mail (free) | FREE | No | Easy | proton.me email, no phone needed for basic account |
| Disroot | FREE | No | Easy | @disroot.org free email |
| GitHub's no-reply email | FREE | No | Trivial | `username+username@users.noreply.github.com` — but cannot receive emails |

**✅ RECOMMENDATION: Proton Mail (proton.me)**
- Reason: Clean, no phone required for basic free account
- Email: e.g., `orretter@proton.me` (check availability)
- Alternative: Cloudflare Email Routing (if a domain is available) — more professional

**⚠️ IMPORTANT:** GitHub's noreply email (`username+...@users.noreply.github.com`) is NOT recommended because:
- Cannot receive notifications
- Cannot recover the account if locked out
- Used by some as primary — but risky

---

## Step 3: SSH Key Setup

Since no SSH key exists, we need to create one:

```bash
ssh-keygen -t ed25519 -C "orretter@proton.me" -f ~/.ssh/github_orretter -N ""
```

- Algorithm: **Ed25519** (modern, secure, shorter than RSA)
- Comment: email address for identification
- No passphrase (for automation use; add passphrase later for human use)

Then add to GitHub via `gh auth login` or manual web UI.

---

## Step 4: Git Configuration

```bash
git config --global user.name "Orretter"
git config --global user.email "orretter@proton.me"
```

---

## Step 5: First Project to Publish

The SOE project has several components. Best candidates for first public repo:

### Option A: `soe` (full project)
- Everything in ~/soe/
- **Pro:** Complete showcase
- **Con:** Large, some parts may be messy/incomplete

### Option B: `orret-looplib` (focused library)
- Just the `core/looplib/` — the binary columnar fine-tuning data format
- **Pro:** Clean, focused, impressive as first repo
- **Con:** Partial

### Option C: `soe-engine` (the main engine)
- `synapse_engine.py`, `soe.py`, `world_model.py`
- **Pro:** Core AI engine
- **Con:** May reference internal paths

### ✅ RECOMMENDATION: Option B — `orret-looplib`
**Reasoning:**
1. Clean, self-contained Python library
2. Has a clear SPEC.md
3. Easy to document (README + pip install)
4. Impressive technical content (binary format, columnar storage)
5. Safe as first public repo — no internal paths/secrets
6. Future repos can add more components

**License:** MIT (simple, permissive)

---

## Step 6: Action Checklist (for main agent)

When ready to execute, in order:

```bash
# 1. Install GitHub CLI (binary method)
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update && sudo apt install gh

# 2. Create Proton Mail account (manual step or via browser)
#    Email: orretter@proton.me or similar

# 3. Authenticate gh with GitHub
gh auth login --ssh-host github.com
# Will prompt for email, one-time code from web browser

# 4. Add SSH public key to GitHub
#    Via: gh ssh-key add ~/.ssh/github_orretter.pub
#    Or manually: https://github.com/settings/keys

# 5. Configure git
git config --global user.name "Orretter"
git config --global user.email "orretter@proton.me"

# 6. Create looplib repo locally
mkdir -p ~/soe/core/looplib
# (already exists — verify)

# 7. Init git, commit, push
cd ~/soe/core/looplib
git init
git add SPEC.md looplib.py README.md LICENSE
git commit -m "Initial commit: orret-looplib v1.0 — binary columnar fine-tuning format"
gh repo create orretter/orret-looplib --public --source=. --remote=origin --push

# 8. Add repo URL to local docs
```

---

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Proton Mail requires phone verification | Low | Use Cloudflare Email Routing instead |
| gh auth fails in headless environment | Medium | Use browser-based auth with one-time code |
| Username "orretter" taken | Medium | Fallbacks: `orretter-ai`, `synapse-orret`, `orret-ai` |
| Email already used on GitHub | Low | Use different email address |

---

## Timeline Estimate

| Step | Time |
|------|------|
| Install gh | 2 min |
| Create Proton Mail account | 5 min (web browser) |
| gh auth + SSH key | 5 min |
| Git config + repo setup | 2 min |
| First commit + push | 2 min |
| **Total** | ~15 min |

---

*Plan by Orretter (Synapse 🧠) · 2026-03-31*
