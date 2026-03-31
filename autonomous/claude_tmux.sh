#!/bin/bash
# SOE Claude Code Tmux Runner
# Based on Reddit approach: tmux sessions for Claude Code CLI
# Usage: ./claude_tmux.sh "your task description"

SESSION="soe-claude-code"
TASK="$1"
SOE_DIR="$HOME/soe"
LOG="$SOE_DIR/logs/claude_tmux.log"

if [ -z "$TASK" ]; then
    echo "Usage: $0 <task description>"
    exit 1
fi

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"
}

log "=== Task START: $TASK ==="

# Create detached session
tmux new-session -d -s "$SESSION" 2>/dev/null || tmux kill-session -t "$SESSION" && tmux new-session -d -s "$SESSION"

# Change to SOE dir and run claude
tmux send-keys -t "$SESSION" "cd $SOE_DIR" Enter
sleep 1
tmux send-keys -t "$SESSION" "claude --print --dangerously-skip-permissions '$TASK'" Enter

# Wait for completion (with timeout)
TIMEOUT=300
INTERVAL=5
ELAPSED=0

while [ $ELAPSED -lt $TIMEOUT ]; do
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))

    # Check if still running
    if ! tmux has-session -t "$SESSION" 2>/dev/null; then
        log "Session ended"
        break
    fi

    # Check for completion markers in pane
    PANE=$(tmux capture-pane -t "$SESSION" -p | tail -5)
    if echo "$PANE" | grep -qE "(DONE|ERROR|completed|finished)"; then
        log "Task completed detected"
        break
    fi
done

# Capture final output
OUTPUT=$(tmux capture-pane -t "$SESSION" -p)
log "=== Task END ==="
log "Output: $OUTPUT"

# Detach (keep session for next task)
echo "$OUTPUT"
