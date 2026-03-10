#!/bin/bash
# NQ L2 optimize watchdog — runs every 10 min via systemd timer
export PATH="/home/rob/.npm-global/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

LOG="/home/rob/.openclaw/workspace/nq-l2-scalping/data/optimize_run3.log"
LOCK="/tmp/nq_optimize_watchdog.lock"

send_telegram() {
    /home/rob/.npm-global/bin/openclaw message send \
        --target 1585771201 --channel telegram \
        --message "$1" 2>/dev/null || true
}

# Prevent concurrent watchdog runs
exec 9>"$LOCK"
flock -n 9 || exit 0

# Count running optimize processes — kill duplicates
PIDS=$(pgrep -f "optimize.py" 2>/dev/null | tr '\n' ' ')
COUNT=$(pgrep -f "optimize.py" 2>/dev/null | wc -l)

if [ "$COUNT" -gt 1 ]; then
    OLDEST=$(pgrep -f "optimize.py" | head -1)
    pgrep -f "optimize.py" | tail -n +2 | xargs kill 2>/dev/null
    send_telegram "⚠️ NQ L2: Killed $((COUNT-1)) duplicate optimize process(es)."
fi

# Check if optimize is running
if pgrep -f "optimize.py" > /dev/null; then
    DONE=$(grep "^Strategy [0-9]" "$LOG" 2>/dev/null | wc -l | tr -d ' ')
    CURRENT=$(grep "^Strategy [0-9]" "$LOG" 2>/dev/null | tail -1)
    WINNERS=$(grep "1\. var.*PF=[1-9]" "$LOG" 2>/dev/null | grep -v "Trades=[0-3]:" | head -5)
    MSG="⏳ NQ L2 sweep: $DONE/14 done
Current: $CURRENT
Winners: ${WINNERS:-none yet}"
    send_telegram "$MSG"
else
    # Not running — check if completed or died
    if grep -q "Strategy 014" "$LOG" 2>/dev/null && grep -q "Results saved" "$LOG" 2>/dev/null; then
        TOP=$(grep "1\. var.*PF=" "$LOG" | sort -t= -k2 -rn | head -6)
        send_telegram "✅ NQ L2 optimize COMPLETE!

$TOP"
        systemctl --user disable nq-optimize-watchdog.timer 2>/dev/null
    else
        LAST=$(grep "^Strategy [0-9]" "$LOG" 2>/dev/null | tail -1)
        cd /home/rob/.openclaw/workspace/nq-l2-scalping
        nohup /usr/bin/timeout 7200 /usr/bin/python3 pipeline/optimize.py --strategy-id all >> "$LOG" 2>&1 &
        NEW_PID=$!
        send_telegram "🔄 NQ L2 optimize died at: $LAST
Auto-restarted PID $NEW_PID"
    fi
fi
