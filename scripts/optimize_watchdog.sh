#!/bin/bash
# NQ L2 optimize watchdog — runs every 10 min via systemd timer
# Checks progress, kills duplicates, alerts Rob on Telegram

LOG="/home/rob/.openclaw/workspace/nq-l2-scalping/data/optimize_run3.log"
LOCK="/tmp/nq_optimize_watchdog.lock"
OPENCLAW_CMD="openclaw send telegram 1585771201"

# Prevent concurrent watchdog runs
exec 9>"$LOCK"
flock -n 9 || exit 0

# Count running optimize processes
PIDS=$(pgrep -f "optimize.py.*all" 2>/dev/null)
COUNT=$(echo "$PIDS" | grep -c . 2>/dev/null || echo 0)

# Kill duplicates — keep only the oldest PID
if [ "$COUNT" -gt 1 ]; then
    OLDEST=$(echo "$PIDS" | head -1)
    echo "$PIDS" | tail -n +2 | xargs kill 2>/dev/null
    $OPENCLAW_CMD "⚠️ NQ L2: Killed $((COUNT-1)) duplicate optimize process(es). Keeping PID $OLDEST." 2>/dev/null
fi

# Check if optimize is still running
if echo "$PIDS" | grep -q .; then
    # Still running — report current strategy
    CURRENT=$(grep "^Strategy" "$LOG" 2>/dev/null | tail -1)
    DONE=$(grep "^Strategy" "$LOG" 2>/dev/null | wc -l | tr -d ' ')
    WINNERS=$(grep "PF=[1-9]" "$LOG" 2>/dev/null | grep "Trades=[1-9]" | grep "1\. var" | grep -v "Trades=0")
    $OPENCLAW_CMD "⏳ NQ L2 sweep: $DONE/14 done. $CURRENT
Winners so far:
$(echo "$WINNERS" | head -5 || echo '  none yet')" 2>/dev/null
else
    # Optimize finished or died
    if [ -f "$LOG" ] && grep -q "Strategy 014" "$LOG" 2>/dev/null; then
        # Completed — send full results
        RESULTS=$(grep -E "^  1\. var" "$LOG" | head -14)
        TOP=$(grep -E "PF=[1-9]\.[0-9]" "$LOG" | grep "1\. var" | grep -v "Trades=[0-3]:" | sort -t= -k2 -rn | head -5)
        $OPENCLAW_CMD "✅ NQ L2 optimize COMPLETE!

Top performers:
$TOP

Full results in data/optimize_run3.log" 2>/dev/null
    else
        # Died mid-run — restart
        LAST=$(grep "^Strategy" "$LOG" 2>/dev/null | tail -1 | grep -oP '\d+' | head -1)
        cd /home/rob/.openclaw/workspace/nq-l2-scalping
        nohup timeout 7200 python3 pipeline/optimize.py --strategy-id all >> "$LOG" 2>&1 &
        $OPENCLAW_CMD "🔄 NQ L2 optimize died at strategy $LAST. Auto-restarted (PID $!)." 2>/dev/null
    fi
fi
