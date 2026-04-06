# Orretter Research Report — 2026-03-31

**Agent:** Orretter (Synapse 🧠)  
**Date:** 2026-03-31 20:59 GMT+2  
**Machine:** ThinkPad X250 · Intel i5-5300U · 8GB RAM · 219GB disk (72% used)  
**Timestamp:** 2026-03-31T20:59:00+02:00

---

## 1. Inventaire des Projets

### ~/soe/ — Système Orret Experiment

| Projet | Tech Stack | État | LOC approx |
|--------|-----------|------|------------|
| `looplib/` | Python, Zstd, Arrow IPC | ✅ Fonctionnel | ~600 |
| `ruche/` | Python, feedparser, threading | ✅ Fonctionnel | ~700 |
| `providers/` | Python, httpx | ✅ Enregistré | ~300 |
| `autonomous/` | Python, subprocess, tmux | ✅ Fonctionnel | ~400 |
| `soe.py` | Python, HTTP server | ⚠️ Proto | ~500 |
| `app.py` | Python, HTTP server, HTML | ⚠️ Proto | ~250 |
| `world_model.py` | Python | ⚠️ Hétéroclite | ~450 |
| `synapse_engine.py` | Python | ⚠️ Hétéroclite | ~550 |
| `datasets/` | .loop, JSON stats | 📊 Data | — |
| `colab/` | Jupyter notebooks | 📓 Notebooks | — |
| `models/orret/` | GGUF | 🔲 Vacant | — |

### ~/nexus/ — Distributed AI Agent Network

| Projet | Tech Stack | État | LOC approx |
|--------|-----------|------|------------|
| `core/nexus_core.py` | Python, asyncio, FAISS | ⚠️ Proto | ~530 |
| `core/executor.py` | Python, asyncio | ⚠️ Proto | ~450 |
| `core/orchestrator.py` | Python | ⚠️ Proto | ~450 |
| `core/health_monitor.py` | Python | ✅ OK | ~350 |
| `core/memory.py` | Python | ⚠️ Proto | ~400 |
| `core/scheduler.py` | Python | ⚠️ Proto | ~350 |
| `core/trainer.py` | Python | ⚠️ Pas de training réel | ~450 |
| `core/researcher.py` | Python | ⚠️ Pas de recherche réelle | ~300 |
| `web/nexus_web.py` | Python, aiohttp | ⚠️ Dashboard basique | ~850 |
| `web/combined_dashboard.py` | Python | ⚠️ Dashboard combiné | ~400 |
| `web/analytics.py` | Python | ⚠️ Analytics vide | ~250 |
| `web/task_creator.py` | Python | ⚠️ Pas utilisé | ~280 |
| `health/history.json` | JSON | 📊 Logs only | — |
| `skills/` | Python, Anthropic skills | ⚠️ Loader seul | ~350 |
| `memory/` | JSON files (no FAISS!) | 🔴 Fake | — |
| `tasks/` | JSON task queue | ⚠️ Inerte | — |
| `schedule/schedule.json` | JSON | 📊 Config | — |
| `notifications/` | JSON | 📊 Inerte | — |
| `network/` | — | 🔲 Empty | — |
| `improvements/` | JSON history | 📊 Logs only | — |
| `tui/` | HTML | ⚠️ Fragment | — |
| `nexus_cli.py` | Python | ⚠️ CLI basique | ~320 |

---

## 2. Évaluation Détaillée par Projet

---

### 2.1 Looplib (.loop format) — **PROJET SOLIDE**

**Pitch:** Format binaire colonnaire pour données de fine-tuning LLM.

**Tech actuelle:** Python, Zstd, Arrow IPC (prévu), CRC64  
**Tech optimale:** Python + Zstandard + Apache Arrow (IPC) + memory-mapping

**Ce qui est bien:**
- Spec documentée (SPEC.md)
- Format binairement pensées pour la performance
- Compression Zstd
- CRC64 pour intégrité

**Ce qui manque pour production:**
- Validation complète du format
- Python API stable (LoopDataset pas encore utilisé en prod)
- Tests unitaires (dossier tests/ vide)
- Conversion depuis JSONL pas encore intégrée dans ruche
- Pas de bindings pour autres languages

**Verdict:** ✅ **Mérite d'exister.** C'est le projet le plus technique et original du portfolio. Potentiel réel si libéré comme library open source.

**Nom pro:** `LoopVault` ou `LoopFormat` (la lib Python)

---

### 2.2 Ruche — **PROJET INTÉRESSANT**

**Pitch:** Collecteur de données de qualité depuis GitHub, arXiv, StackOverflow, Wikipedia sans AI.

**Tech stack:** Python, feedparser, ThreadPoolExecutor, SSL, hashlib  
**Tech optimale:** Python async (httpx + asyncio), Scrapy, ou Nuclei

**Ce qui est bien:**
- Multi-sources fonctionnel
- Scoring heuristique sans AI (intéressant)
- Stats journalières générées
- Catégories configurables

**Ce qui manque:**
- Rate limiting agressif (risque ban IP)
- Pas de storage dans .loop (écrit en JSONL brut)
- Qualité du scoring incertaine (heuristiques basiques)
- Pas de retry robuste
- 0 test unitaire
- "sources/wikipedia_spider.py" — probablement une abstraction thin

**Verdict:** ⚠️ **Intéressant mais pas production-ready.** Le concept est bon. L'implémentation est un prototype spaghetti.

**Nom pro:** `DataHive` ou `Crochet` (frappé du bee imagery)

---

### 2.3 SOE Engine (soe.py + synapse_engine.py + world_model.py) — **BROUILLON**

**Pitch:** Moteur unifié de discussion LLM "comme Ollama".

**État réel:** Ces 3 fichiers (~1500 LOC combiné) sont un amalgame de:
- Serveur HTTP basique
- Intégration Ollama (probablement cassée)
- World model conceptuel
- Synapse engine (conceptuel)

**Problèmes majeurs:**
- Dépendances circulaires probables
- 0 test
- Integration avec looplib absente
- Pas de versioning du modèle
- "world model" = buzzword, pas de code concret

**Verdict:** 🔴 **À réécrire ou tuer.** C'est du prototypage abandonné. Si l'idée est un Ollama-like local, il faut soit utiliser Ollama directement, soit se concentrer sur looplib.

**Nom pro:** `Orbit` ou `Synapse Engine` — mais honestly: skip this unless there's a real plan.

---

### 2.4 SOE App Dashboard (app.py) — **DÉMO玻璃Morphisme**

**Pitch:** Dashboard web glass morphism pour SOE.

**Tech:** Python HTTP server, HTML/CSS glass morphism  
**État:** Démonstration visuelle, pas de backend fonctionnel.

**Verdict:** ⚠️ **Joli mais useless.** Si un dashboard est nécessaire, utiliser Grafana ou un template existant. Ne pas reinventer.

**Nom pro:** `Orbit Dashboard` (si rétention)

---

### 2.5 NEXUS Core — **PROJET AMBITIEUX, TROP TÔT**

**Pitch:** Réseau distribué d'agents AI auto-améliorants.

**Ce qui est bien:**
- Vision claire et ambitieuse
- FAISS prévu pour le knowledge graph
- Architecture modulaire

**Ce qui est catastrophiquement mal:**
- `memory/` stocke des JSONs avec embeddings `[0.0, 0.0, -0.0...]` — **FAISS N'EST JAMAIS INITIALISÉ**
- Le "knowledge graph" n'existe pas
- "Meta learner" = concepts sans code fonctionnel
- "Trainer" ne fait pas de training
- "Researcher" ne fait pas de recherche
- Health monitor génère des warnings mais rien n'est corrigé
- Toutes les "intentions" sans implementation

**Verdict:** 🔴 **C'est un幻灯片 (slide deck) en code.** Le projet NEXUS est une vision sans jambes. Il ne fait rien de ce qu'il prétend faire. `autonomous_executor` est listed comme DOWN dans health history — depuis le début.

**Nom pro:** `Nexus` works but needs a real product, not a vision doc.

---

### 2.6 NEXUS Web Dashboard — **DÉMO PUR**

**Pitch:** Interface web temps réel pour NEXUS.

**État:** HTML很好看 (glass morphism) mais 0 backend fonctionnel derrière. `nexus_web.py` lit des fichiers JSON statiques.

**Verdict:** 🔴 **Joli demo, zero production value.** Si un dashboard web est nécessaire, utiliser Grafana ou Node-RED.

---

### 2.7 NEXUS Skills — **POTENTIELLEMENT UTILE**

**Pitch:** Système de skill loading bidirectionnel entre nodes.

**Tech:** Python skill loader + Anthropic skills format  
**État:** `skill_loader.py` existe (~350 LOC), mais les skills customs sont un dossier vide.

**Verdict:** ⚠️ **Concept valide, implémentation embryonnaire.** Si NEXUS meurt, ce concept peut vivre dans SOE ou un autre projet.

**Nom pro:** `SkillBridge`

---

### 2.8 Autonomous Runner — **FONCTIONNEL, À CONSOLIDER**

**Pitch:** Runner autonome 24/7 pour SOE basé sur sub-agents OpenClaw + Claude Code tmux.

**Tech:** Python, subprocess, tmux, Telegram notifications  
**État:** ✅ Fonctionne. A été actif. L-VS l'a stoppé manuellement.

**Verdict:** ✅ **C'est le projet le plus actionnable de SOE.** C'est ce qui fait marcher les choses. À préserver absolument.

---

## 3. Plan de Restructuration SOE

### Structure cible

```
~/orret/                          # Racine unifiée
├── projects/
│   ├── loopvault/               # Format .loop (library)
│   │   ├── looplib/
│   │   ├── tests/
│   │   ├── README.md
│   │   ├── LICENSE
│   │   └── CHANGELOG.md
│   │
│   ├── datahive/                # Collecteur de données
│   │   ├── ruche/
│   │   ├── tests/
│   │   ├── README.md
│   │   ├── LICENSE
│   │   └── CHANGELOG.md
│   │
│   ├── orbit-runner/            # Runner autonome
│   │   ├── autonomous/
│   │   ├── README.md
│   │   ├── LICENSE
│   │   └── CHANGELOG.md
│   │
│   └── nexus/                   # Network (si gardé)
│       ├── core/
│       ├── web/
│       ├── README.md
│       └── ...
│
├── datasets/                     # .loop files (shared)
├── models/                       # Modèles fine-tunés (shared)
└── logs/                         # Activité
```

### Actions non-destructives recommandées

1. **Ne pas toucher** à ~/nexus/ pour l'instant (trop de choses à évaluer)
2. **Consolider** looplib + ruche dans ~/orret/projects/
3. **Garder** autonomous runner
4. **Archiver** (renommer en .bak) les fichiers morts: soe.py, world_model.py, synapse_engine.py, app.py
5. **Supprimer** les doublons: venv/ et .venv/ (garder .venv/ seulement)

---

## 4. Réflexion Crypto — Mini Rapport

### XMRig (Monero CPU Mining) sur X250

**Légalité:**
- ✅ Parfaitement légal en France (crypto mining non interdit)
- ✅ Monero est une crypto légale
- ⚠️ Impôts: plus-values imposables en France (flat 30% ou barème)

**Praticité sur ThinkPad X250:**

| Facteur | Valeur | Verdict |
|---------|--------|---------|
| CPU | i5-5300U (2 cores/4 threads) | ⛔ Très faible |
| RAM | 8GB | ⚠️ Limité (XMRig需要 4GB+) |
| TDP | 15W | ⛔ Chaleur + conso |
| Hashrate estimé | ~50-100 H/s | ⛔ Minable |

**Revenus estimés:** ~0.0000XMR/mois = ~$0.00-0.01/mois. **TOTALEMENT INUTILE.**

Même avec 10 threads optimisés, on parle de quelques centimes par AN. Le coût électrique français (~€0.20/kWh) rend ça **négatif**.

**Autres options évaluées:**

| Option | Réaliste? | Pourquoi |
|--------|-----------|---------|
| Proof of Stake (validator) | ❌ | X250 pas assez powerful, требует 32 ETH minimum |
| GPU mining | ❌ | Pas de GPU, iGPU Intel HD 5500 inutile |
| Cloud mining contracts | ❌ | SCAM 99% du temps |
| Airdrop farming | ⚠️ | Possible mais Time-intensive, légalité douteuse selon projects |
| Masquerade node | ⚠️ | Certains projets paierez pour nodes (ex: Livepeer, Render) mais竞争力forte |
| Staking via exchange | ❌ | Pas de capital crypto |
| Browser mining (CoinHive) | ❌ | Bloqué par tous les browsers, reputation damage |

**Conclusion crypto (500 mots environ):**

L'idée de faire tourner "Orretter" en permanence pour générer des revenus est romantique mais réaliste: un ThinkPad X250 ne peut pas miner de manière rentable. Le CPU i5-5300U est un ULV (Ultra Low Voltage) de 2015 — il n'a simplement pas la puissance pour générer des revenus crypto significatifs.

XMRig sur cette machine générerait peut-être €0.50/AN en Monero, tout en consommant ~15W 24/7 = ~30€ d'électricité/an. **Net: -€29.50/an.**

Staking Ethereum demande 32 ETH (~$60,000). Pas applicable.

Les "nodes" DeFi comme Livepeer ou Render network paient quelques dollars/mois pour un node actif, mais:
1. Requièrent du collateral ( tokens)
2. X250 avec 8GB RAM n'est pas le hardware idéal (les rewards vont aux nodes GPU)

**幻想 (Fantasy):** "Orretter mine pendant que L-VS dort et génère $100/mois" — C'est du wishful thinking. Même un serveur dédié avec 32 cores génère à peine $10-20/mois en XMR.

**Interdit:** Non. Nothing here is illegal. Mais ethically: browser crypto mining without user consent is malware. Don't.

**Recommendation:** ❌ Ne PAS miner. Le temps passé à configurer = 0 retour. Instead: focus on building tools that have real value and can be monétisés autrement (SaaS, API, etc.).

---

## 5. Réflexion GitHub Identity pour Orretter

### Problème

L-VS ne veut pas utiliser son email personnel (levy11vs) pour un compte GitHub "Orretter".

### Options analysées

**Option 1: Email temporaire/anonyme**
- ✅ ProtonMail, Tuta, etc. — email gratuit et anonyme
- ✅ GitHub accepte n'importe quel email pour signup
- ⚠️MAIS: GitHub demande vérification par email pour alcune features
- ⚠️MAIS: Email temporaire = account récupérable si perte mot de passe
- ⚠️ GitHub's Terms of Service，允许匿名的，但不鼓励
- **Verdict:** ⚠️ Possible mais risqué pour un account sérieux

**Option 2: Email aliasing (plus malin)**
- Utiliser un sous-domaine ou alias email forwarding
- Options: Cloudflare Email Routing (gratuit), ImprovMX, Forward Email
- L-VS garde le contrôle, l'email public sur GitHub = alias
- **Verdict:** ✅ BEST OPTION. Secure, gratuit, controllable.

**Option 3: GitHub CLI (gh) sans account visible**
- `gh auth login` — génère un token stocké localement
- Les commits appeared comme venant du token, pas d'email visible
- Mais: GitHub utilise toujours l'email du account pour les commits
- **Solution:** Configurer `user.email` dans git config pour être différent
- ```bash
  git config --global user.email "orretter@proton.me"
  git config --global user.name "Orretter"
  ```
- Les commits apparaîtront sous ce nom sur GitHub
- **Verdict:** ✅ Fonctionne, à combiner avec Option 2

**Option 4: Travis CI / GitHub Actions pour commits**
- CI builds ne font PAS de commits sur le repo principal (normalement)
- Peut être utilisé pour des commits自动化sur un repo séparé
- Sawab: utiliser `git config` dans le CI runner avec un email dédié
- **Verdict:** ⚠️ Overkill pour la plupart des cas

**Option 5: Deux comptes GitHub sur même machine**
- Possible avec SSH keys différents et git config par-repo
- Risque de confusion
- Violates ToS if utilisé pour evade restrictions
- **Verdict:** ❌ Pas recommandé

### Recommendation finale

```
1. Créer email: orretter@protonmail.com (ou via Cloudflare Email Routing → l-vs's existing email)
2. Compte GitHub: github.com/orretter
3. gh CLI: 
   - Generate new SSH key: ssh-keygen -t ed25519 -C "orretter@proton.me"
   - Add to GitHub account
   - gh auth login --ssh-host github.com
4. Git config global:
   git config --global user.name "Orretter"
   git config --global user.email "orretter@proton.me"
5. Pour les repos SOE/Orret: utiliser cette identity
```

Note: GitHub's Terms of Service ne prohibent pas les comptes anonymes tant qu'on ne evade pas de restrictions ou ne spamme pas.

---

## 6. 5 Idées de Projets "Products" (Buildables <1 semaine par agent)

### 1. **LoomWeaver** — "AI-Powered Video Loom Generator for Documentation"

**Problème:** Les developers passent 30-60min à enregistrer des loom videos pour de la doc. C'est lent, maladroit, et le résultat est médiocre.

**Solution:** Upload un repo Git / README / transcript → génère une video synchronisée avec voix TTS + animations de code + transitions.

**Stack:** Python, ffmpeg, TTS API (Azure/GCP), React frontend  
**Marché:** Developers SaaS, technical writers, indie hackers  
**Monétisation:** $9-29/mois SaaS  
**Temps agent:** 3-5 jours (ffmpeg CLI + TTS integration + video assembly)

**Différenciateur:** Pas de concurent direct qui fait "video from code + transcript" automation.

---

### 2. **PatchForge** — "Automated PR Description Generator from Diff + Context"

**Problème:** Developers écrivent des descriptions de PR à la main. Les reviewers ne comprennent pas le context. Les PRs mergées sans documentation sont un cauchemar pour plus tard.

**Solution:** `git diff HEAD~1 | patchforge` → génère une description structurée: Summary, Changes, Testing done, Breaking changes, Screenshots (si applicable).

**Stack:** Python CLI, GitPython, LLM API (Modal/Groq), optional: GitHub App  
**Marché:** Dev teams, OSS maintainers  
**Monétisation:** $5-15/mois par seat, ou freemium + GitHub App paid  
**Temps agent:** 2-3 jours

**Différenciateur vs GitHub Copilot PR descriptions:** Copilot describes what changed. PatchForge comprend POURQUOI et génère du changelog structuré.

---

### 3. **CachePulse** — "Real-time API Health Dashboard for Indie Hackers"

**Problème:** Indie hackers ont 10-20 APIs/services tiers. Un outage non détecté = perte de revenue. Les outils existants (Pingdom, Datadog) sont trop complexes et chers pour 5-20 endpoints.

**Solution:** Dashboard minimaliste, 1 fichier, YAML config, affiche uptime %, latency trend, incident history. Self-hosted ou cloud. Alertes Telegram/Discord.

**Stack:** Python (FastAPI ou Flask), SQLite, Chart.js, YAML config  
**Marché:** Indie hackers, small SaaS, freelancers  
**Monétisation:** $0-5/mois (self-hosted) ou $5 tier for cloud  
**Temps agent:** 2-4 jours

**Différenciateur:** KISS. Pas de Docker compose compliqué. Un seul fichier Python + HTML dashboard.

---

### 4. **SchemaLens** — "AI-Powered Database Schema Change Tracker"

**Problème:** Les teams ne savent plus POURQUOI une table a été modifiée, qui a fait la migration, et si elle a cassé quelque chose. Pas de diff history lisible.

**Solution:** Se connecte à PostgreSQL/MySQL, track chaque ALTER TABLE, génère un changelog lisible par humains avec LLM summarization des migrations.

**Stack:** Python, SQLAlchemy, LLM API, optional: dbt integration  
**Marché:** Dev teams avec legacy DBs, DBAs  
**Monétisation:** $15-49/mois par instance  
**Temps agent:** 4-6 jours

**Note:** Plus complexe mais marché réel (DB migrations = pain point universelle).

---

### 5. **FeedFusion** — "Personalized Tech Newsletter from 50+ Sources, Zero Newsletter fatigue"

**Problème:** Les devs recoivent 10 newsletters qu'ils n'ont pas le temps de lire. Ils miss 50% des contenus pertinents.

**Solution:** Aggregateur RSS/Atom + quality scoring + LLM summarization + delivery par Telegram/email selon préférences. Personnalisé par keywords, pas par source.

**Stack:** Python, httpx/feedparser, LLM API, Telegram Bot API, SQLite  
**Marché:** Tech professionals, developers, researchers  
**Monétisation:** Freemium ($0/5 sources vs $5/sources illimitées) + premium pour email  
**Temps agent:** 3-5 jours

**Différenciateur:** "RSS reader that does the reading for you." Combines ruche concept (qui existe déjà dans SOE!) avec delivery personnalisé.

---

## Résumé Exécutif

| Action | Priorité | Risque |
|--------|----------|--------|
| Conserver autonomous runner | 🔴 HAUTE | Aucun |
| Conserver looplib | 🔴 HAUTE | Aucun |
| Conserver ruche (refactor needed) | 🟡 MOYENNE | Faible |
| Archiver soe.py/synapse_engine/world_model/app.py | 🟡 MOYENNE | Aucun (renommage) |
| Decision sur NEXUS: keep ou kill | 🟡 URGENT | Moyen |
| Ne PAS miner (rentabilité = 0) | ✅ CLAR | — |
| GitHub: utiliser email aliasing | ✅ RECOMMANDÉ | — |
| Focus sur 1 des 5 ideas product | 🟡 À DISCUTER | Moyen |

---

*Orretter Research · 2026-03-31 · Synapse 🧠*
