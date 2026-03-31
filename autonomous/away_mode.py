#!/usr/bin/env python3
"""
SOE Away Mode — Activates autonomous operation
Usage:
  python3 away_mode.py                        # Default tasks only
  python3 away_mode.py "fix the memory bug"    # + custom high-priority task
"""

import sys
import json
import time
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path

SOE_DIR = Path.home() / "soe"
AUTONOMOUS_DIR = SOE_DIR / "autonomous"
TASK_FILE = AUTONOMOUS_DIR / "task_queue.json"
LOG_FILE = SOE_DIR / "logs" / "autonomous_runner.log"
TELEGRAM_CHAT_ID = "7666797404"
TELEGRAM_TOKEN = "8561222169:AAEtfmPENrKA0-hh9SK9vMhtoCFAm6orxs8"

AUTONOMOUS_DIR.mkdir(exist_ok=True)
(SOE_DIR / "logs").mkdir(exist_ok=True, exist_ok=True)


def send_tg(msg: str):
    data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10): pass
    except Exception as e:
        print(f"TG error: {e}")


def load_tasks():
    if TASK_FILE.exists():
        return json.loads(TASK_FILE.read_text())
    return []


def save_tasks(tasks):
    TASK_FILE.write_text(json.dumps(tasks, indent=2))


def add_task(description: str, priority: int = 5):
    tasks = load_tasks()
    tasks.append({
        "id": int(time.time() * 1000),
        "description": description,
        "priority": priority,
        "status": "pending",
        "created_at": subprocess.run(["date", "-Iseconds"], capture_output=True, text=True).stdout.strip()
    })
    tasks.sort(key=lambda t: t["priority"], reverse=True)
    save_tasks(tasks)
    print(f"✓ Task added: {description[:60]}")


DEFAULT_TASKS = [
    ("Continue SOE infrastructure improvements", 8),
    ("Research and add new data sources to Ruche", 7),
    ("Review logs for errors or improvement opportunities", 6),
    ("Improve NEXUS agent system", 5),
    ("Keep services running, restart if down", 9),
]


def start_runner():
    subprocess.run(["pkill", "-f", "autonomous_runner.py"], stderr=subprocess.DEVNULL)
    time.sleep(1)
    subprocess.Popen(
        [sys.executable, str(AUTONOMOUS_DIR / "autonomous_runner.py")],
        stdout=open(LOG_FILE, "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True
    )
    time.sleep(2)
    # Verify it's running
    if subprocess.run(["pgrep", "-f", "autonomous_runner.py"], capture_output=True).returncode == 0:
        print("✓ Runner started")
    else:
        print("✗ Runner failed to start")


def main():
    custom_task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None

    if custom_task:
        add_task(custom_task, priority=10)
        msg = f"🟡 *Away Mode ACTIVE*\n\nTask prioritaire: `{custom_task[:100]}`\n\nJe m'en occupe. 💤"
    else:
        msg = "🟡 *Away Mode ACTIVE*\n\nJe bosse sur la SOE todo-list. 💤"

    send_tg(msg)

    # Add default tasks if queue is empty
    tasks = load_tasks()
    pending = [t for t in tasks if t["status"] == "pending"]
    if not pending:
        for desc, pri in DEFAULT_TASKS:
            add_task(desc, pri)
        print(f"✓ Added {len(DEFAULT_TASKS)} default tasks")
    else:
        print(f"✓ {len(pending)} pending tasks already in queue")

    start_runner()
    print("\nAway mode started. Check Telegram.")


if __name__ == "__main__":
    main()
