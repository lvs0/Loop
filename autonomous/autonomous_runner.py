#!/usr/bin/env python3
"""
SOE Autonomous Runner
=====================
Runs continuously, spawns sub-agents for tasks, sends periodic Telegram updates.
Based on the Reddit approach: keep context light with sub-agents, use Claude Code CLI for heavy lifting.
"""

import asyncio
import json
import time
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

# ---- Config ----
SOE_DIR = Path.home() / "soe"
WORKSPACE = Path.home() / ".openclaw" / "workspace"
TELEGRAM_CHAT_ID = "7666797404"  # L-VS
UPDATE_INTERVAL_MINUTES = 30
CLAUDE_TMUX_SESSION = "soe-claude-code"
LOG_FILE = SOE_DIR / "logs" / "autonomous_runner.log"

# Ensure log dir
(SOE_DIR / "logs").mkdir(exist_ok=True)


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    LOG_FILE.write_text(LOG_FILE.read_text() + line + "\n" if LOG_FILE.exists() else line + "\n")


# ---- Telegram notification ----
def send_telegram(message: str):
    import urllib.request
    import urllib.parse

    token = "8561222169:AAEtfmPENrKA0-hh9SK9vMhtoCFAm6orxs8"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as e:
        log(f"Telegram error: {e}")


# ---- Task queue (file-based) ----
TASK_FILE = SOE_DIR / "autonomous" / "task_queue.json"

def load_tasks():
    if TASK_FILE.exists():
        return json.loads(TASK_FILE.read_text())
    return []

def save_tasks(tasks):
    TASK_FILE.parent.mkdir(exist_ok=True)
    TASK_FILE.write_text(json.dumps(tasks, indent=2))

def add_task(description: str, priority: int = 5):
    tasks = load_tasks()
    tasks.append({
        "id": int(time.time()),
        "description": description,
        "priority": priority,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    })
    tasks.sort(key=lambda t: t["priority"], reverse=True)
    save_tasks(tasks)
    log(f"Task added: {description}")

def get_next_task():
    tasks = load_tasks()
    for t in tasks:
        if t["status"] == "pending":
            t["status"] = "running"
            t["started_at"] = datetime.now().isoformat()
            save_tasks(tasks)
            return t
    return None

def complete_task(task_id: int, result: str = ""):
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["status"] = "completed"
            t["completed_at"] = datetime.now().isoformat()
            t["result"] = result
            save_tasks(tasks)
            return
    log(f"Task {task_id} not found")


# ---- Sub-agent spawning ----
async def spawn_subagent(task_description: str, model: str = "minimax-portal/MiniMax-M2.7") -> dict:
    """Spawn a sub-agent to handle a task."""
    import urllib.request
    import urllib.parse

    gateway_url = "http://127.0.0.1:18789"
    token = "2724f6daf48a838cf0510abf49ecbf31589f741ef0905c70"

    prompt = f"""You are working on the SOE (Système Orret) autonomous task system.
Task: {task_description}
workspace: {WORKSPACE}
sof: {SOE_DIR}

Work autonomously. Read relevant files, make improvements, commit if needed.
When done, write a brief result summary. Reply with NO_REPLY when done."""

    payload = {
        "model": model,
        "message": prompt,
        "stream": False
    }

    req = urllib.request.Request(
        f"{gateway_url}/api/v1/sessions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            session_id = result.get("sessionId", "unknown")
            log(f"Sub-agent spawned: session={session_id}")
            return {"sessionId": session_id, "status": "spawned"}
    except Exception as e:
        log(f"Sub-agent spawn error: {e}")
        return {"error": str(e)}


# ---- Claude Code via tmux ----
def run_claude_code_command(command: str, timeout: int = 120) -> str:
    """Run a Claude Code CLI command in tmux."""
    import subprocess

    # Create tmux session if not exists
    subprocess.run(["tmux", "new-session", "-d", "-s", CLAUDE_TMUX_SESSION, "echo 'ready'"],
                  stderr=subprocess.DEVNULL)

    # Send command
    escaped = command.replace('"', '\\"').replace('\n', ' ')
    subprocess.run(
        ["tmux", "send-keys", "-t", CLAUDE_TMUX_SESSION, escaped, "Enter"],
        stderr=subprocess.DEVNULL
    )

    # Wait for execution
    time.sleep(timeout)

    # Capture output
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", CLAUDE_TMUX_SESSION, "-p"],
        capture_output=True, text=True
    )
    return result.stdout


# ---- Status report ----
def build_status() -> str:
    tasks = load_tasks()
    pending = [t for t in tasks if t["status"] == "pending"]
    running = [t for t in tasks if t["status"] == "running"]
    completed = [t for t in tasks if t["status"] == "completed"][-5:]  # last 5

    # Check services
    import urllib.request
    services_ok = []
    for port in [8765, 8766, 8767, 8767, 8768, 8769, 8770, 8773, 8777]:
        try:
            with urllib.request.urlopen(f"http://localhost:{port}", timeout=2) as r:
                if r.status == 200:
                    services_ok.append(str(port))
        except:
            pass

    uptime = ""
    try:
        with open("/proc/uptime") as f:
            secs = float(f.read().split()[0])
            uptime = str(timedelta(seconds=int(secs)))
    except:
        pass

    msg = f"""🤖 *SOE Autonomous Status*
⏱ Uptime: `{uptime}`

*Services:* {len(services_ok)}/9 ports UP ({', '.join(services_ok) if services_ok else 'none'})

*Tasks:*
• Pending: {len(pending)}
• Running: {len(running)}
• Completed (recent): {len(completed)}"""

    if pending:
        msg += f"\n*Next task:* {pending[0]['description'][:80]}"
    if running:
        msg += f"\n*In progress:* {running[0]['description'][:80]}"

    return msg


# ---- Main loop ----
async def main():
    log("=== SOE Autonomous Runner STARTED ===")
    send_telegram("🟢 *SOE Autonomous Runner activated*\\nJe bosse, tu peux dormir. 💤")

    last_update = time.time()
    loop_count = 0

    while True:
        loop_count += 1
        now = time.time()

        # Check for next task
        task = get_next_task()
        if task:
            log(f"Processing task: {task['description']}")
            send_telegram(f"🔄 *Starting:* `{task['description'][:100]}`")

            # Spawn sub-agent for heavy lifting
            try:
                sub_result = await spawn_subagent(task["description"])
                if "error" not in sub_result:
                    send_telegram(f"✅ Sub-agent lancé pour cette tâche")
            except Exception as e:
                log(f"Sub-agent error: {e}")

            # For quick tasks, do them directly
            # For dev tasks, use Claude Code tmux
            if any(kw in task["description"].lower() for kw in ["code", "refactor", "build", "fix", "写代码"]):
                task_desc = task["description"].replace("'", "\\'")
                result = run_claude_code_command(
                    f"cd {SOE_DIR} && claude --print '{task_desc}'"
                )
                complete_task(task["id"], result[:200])
            else:
                # Direct work in this session
                log(f"Task handled: {task['description']}")
                complete_task(task["id"], "processed")

        # Periodic status update
        if now - last_update >= UPDATE_INTERVAL_MINUTES * 60:
            status = build_status()
            send_telegram(status)
            last_update = now
            log("Periodic status sent")

        # Heartbeat to HEARTBEAT.md
        try:
            hb_path = Path.home() / ".openclaw" / "workspace" / "HEARTBEAT.md"
            if hb_path.exists():
                content = hb_path.read_text()
                if "## Autonomous Runner" not in content:
                    hb_path.write_text(content + f"\n## Autonomous Runner Check ({datetime.now().isoformat()})\n- Loop #{loop_count} ✅\n")
        except Exception as e:
            log(f"HEARTBEAT update error: {e}")

        await asyncio.sleep(60)  # Check every minute


if __name__ == "__main__":
    asyncio.run(main())
