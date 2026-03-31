# SOE Autonomous Mode

Based on the Reddit approach: keep OpenClaw running 24/7 with sub-agents, Claude Code CLI, and periodic Telegram updates.

## Architecture

```
┌─────────────────────────────────────────────┐
│  Away Mode (away_mode.py)                   │
│  "Je serai absent, continue à bosser"      │
└──────────┬──────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────┐
│  Autonomous Runner (autonomous_runner.py)  │
│  • Main loop (every 60s)                  │
│  • Spawns sub-agents for heavy tasks      │
│  • Uses Claude Code CLI via tmux          │
│  • Sends Telegram updates every 30min     │
└──────────┬──────────────────────────────────┘
           │
     ┌─────┴──────┐
     ▼            ▼
┌─────────┐  ┌────────────┐
│ Sub-    │  │ Claude Code│
│ agents  │  │ CLI tmux   │
└─────────┘  └────────────┘
```

## Components

| File | Purpose |
|------|---------|
| `autonomous_runner.py` | Main loop, spawns sub-agents, Telegram updates |
| `away_mode.py` | Activates away mode with tasks |
| `claude_tmux.sh` | Runs Claude Code CLI in tmux session |
| `task_queue.json` | File-based task queue |

## Usage

### Activate away mode
```bash
cd ~/soe
python3 autonomous/away_mode.py "Ta description de tâche ici"
# ou juste:
python3 autonomous/away_mode.py
```

### Add tasks manually
```bash
cd ~/soe
python3 -c "
import sys; sys.path.insert(0, 'autonomous')
from autonomous_runner import add_task
add_task('Ta tâche', priority=8)
"
```

### Check runner status
```bash
ps aux | grep autonomous_runner
tail -f ~/soe/logs/autonomous_runner.log
```

### Stop runner
```bash
pkill -f autonomous_runner.py
```

## Memory System (Upgraded)

Config in `~/.openclaw/openclaw.json`:
- **Hybrid search**: BM25 keyword + vector similarity
- **Temporal decay**: older memories score lower (30-day half-life)
- **Auto-capture**: facts extracted from conversations
- **Auto-recall**: relevant memories injected before each turn

## Sub-agents

Spawned via OpenClaw sessions API. Each task = one isolated session = no context bloat in main session.

## Telegram Updates

Every 30 minutes while runner is active:
- Uptime
- Services status
- Task queue depth
- Current task

## Cron Removed

Les crons système ont été désactivés. Le runner tourne en daemon via `nohup`.
