# L2 Strategy 020 - Final Setup (Using Proven ATI Method)

## ✅ INFRASTRUCTURE COMPLETE

### On Omen (Linux):
1. Signal engine: `pipeline/engines/strategy_020_signal_engine.py` ✅
2. Database: `data/l2_signals.db` (SQLite) ✅
3. Dashboard: http://omen-claw.tail76e7df.ts.net:8896 ✅

### On REBEL-ALLIANCE (Windows):
1. Signal executor: `nt_bridge/l2_signal_executor.py` ✅ (NEW - uses proven ATI pattern)

## 🚀 HOW TO START TESTING

### Step 1: On Omen
```bash
# Start signal engine (generates signals from IBKR data)
systemctl --user start l2-signal-engine.service

# Watch logs
journalctl --user -u l2-signal-engine.service -f
```

### Step 2: On REBEL-ALLIANCE (Windows)

**A. Prerequisites:**
- NinjaTrader 8 running
- SimL2020 account connected
- ATI enabled (Tools → Options → Automated Trading Interface → Enable)

**B. Copy signal executor:**
```powershell
# From WSL/Ubuntu terminal on Windows:
cp /home/rob/.openclaw/workspace/nq-l2-scalping/nt_bridge/l2_signal_executor.py /mnt/c/Users/hartw/Documents/

# Or use Windows Explorer to copy:
# \\wsl.localhost\Ubuntu\home\rob\.openclaw\workspace\nq-l2-scalping\nt_bridge\l2_signal_executor.py
# TO: C:\Users\hartw\Documents\
```

**C. Install Python on Windows (if not already):**
```powershell
# Check if Python installed:
python --version

# If not, download: https://www.python.org/downloads/
# Make sure "Add to PATH" is checked during install
```

**D. Run signal executor:**
```powershell
cd C:\Users\hartw\Documents
python l2_signal_executor.py
```

You should see:
```
======================================================================
L2 SIGNAL EXECUTOR — Strategy 020
======================================================================
Signal file: \\wsl.localhost\Ubuntu\home\rob\.openclaw\workspace\nq-l2-scalping\nt_bridge\signal_output.json
ATI: 127.0.0.1:36973
Account: SimL2020
Instrument: NQ 03-26
======================================================================
✅ Connected to NinjaTrader ATI at 127.0.0.1:36973
✅ Executor running, polling every 5 seconds...
```

## 📊 MONITORING

**Dashboard:** http://omen-claw.tail76e7df.ts.net:8896
- Shows signals generated
- Shows fills from NT
- PnL tracking

**Signal engine logs (Omen):**
```bash
tail -f /home/rob/.openclaw/workspace/nq-l2-scalping/data/l2_signal_engine.log
```

**Database queries (Omen):**
```bash
sqlite3 /home/rob/.openclaw/workspace/nq-l2-scalping/data/l2_signals.db \
  "SELECT * FROM l2_signals ORDER BY timestamp DESC LIMIT 5;"
```

**Execution logs (Windows):**
```
C:\Users\hartw\Documents\NinjaTrader ML Bridge\executions.csv
```

## 🎯 TESTING FLOW

**Phase 1: Dry Run (Current State)**
- Signal engine: `DRY_RUN = True` (line 23 of signal engine)
- Executor sees: `⏭️ DRY RUN signal skipped`
- No orders sent to NT
- Verify signals generate correctly

**Phase 2: Live Sim (When Ready)**
1. Edit signal engine: Set `DRY_RUN = False`
2. Restart: `systemctl --user restart l2-signal-engine.service`
3. Executor will send orders to SimL2020
4. Monitor fills in dashboard

**Phase 3: Collect Data (2 weeks)**
- Let run through ~10-15 trades
- Compare sim PF vs backtest PF (8.00)
- Expected sim PF: 5.0-6.0
- Track slippage & latency

## ⚙️ CONFIGURATION

**Signal Engine** (`pipeline/engines/strategy_020_signal_engine.py`):
```python
OR_BARS = 50        # Opening range: 9:30-10:20 ET
TP_TICKS = 32       # $640 profit target
SL_TICKS = 4        # $80 stop loss
DRY_RUN = True      # Set False to send real signals
```

**Executor** (`nt_bridge/l2_signal_executor.py`):
```python
ACCOUNT = "SimL2020"
INSTRUMENT = "NQ 03-26"  # Update month as contract rolls
ATI_PORT = 36973
```

## 🚨 TROUBLESHOOTING

**"Failed to connect to ATI":**
- Check NinjaTrader is running
- Verify ATI enabled: Tools → Options → Automated Trading Interface
- Check port: should be 36973
- Restart NinjaTrader if needed

**"Signal file not found":**
- Check WSL path works: `ls \\wsl.localhost\Ubuntu\home\rob\.openclaw\workspace\nq-l2-scalping\nt_bridge\`
- If not, copy signal_output.json to C:\Users\hartw\Documents\ and update path in executor

**No signals generating:**
- Check signal engine is running: `systemctl --user status l2-signal-engine.service`
- Market must be open (RTH: 9:30 AM - 4:00 PM ET Monday-Friday)
- NQ futures resume Sunday 4:00 PM MST

## 📂 FILE LOCATIONS

**Omen:**
- Signal engine: `/home/rob/.openclaw/workspace/nq-l2-scalping/pipeline/engines/strategy_020_signal_engine.py`
- Dashboard: `/home/rob/.openclaw/workspace/nq-l2-scalping/dashboard/l2_dashboard.py`
- Database: `/home/rob/.openclaw/workspace/nq-l2-scalping/data/l2_signals.db`
- Signal output: `/home/rob/.openclaw/workspace/nq-l2-scalping/nt_bridge/signal_output.json`

**REBEL-ALLIANCE:**
- Executor: `C:\Users\hartw\Documents\l2_signal_executor.py` (after copying)
- Fills: `C:\Users\hartw\Documents\NinjaTrader ML Bridge\executions.csv`
- Position: `C:\Users\hartw\Documents\NinjaTrader ML Bridge\position_state.json`

---

**Using proven ATI pattern from NQ_Ninja_Trader. No .cs compilation needed. Pure Python.**
