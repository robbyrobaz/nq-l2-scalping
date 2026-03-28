# L2 Strategy 020 - Setup Instructions

## ✅ COMPLETED (Omen Side)

1. Signal engine created: `pipeline/engines/strategy_020_signal_engine.py`
2. Dashboard created: `dashboard/l2_dashboard.py` (port 8896)
3. Database initialized: `data/l2_signals.db`
4. Services configured (but NOT started yet)

## 🎯 NEXT STEPS

### On Omen (Start Services)

```bash
cd /home/rob/.openclaw/workspace/nq-l2-scalping

# Start dashboard (http://127.0.0.1:8896)
systemctl --user start l2-dashboard.service

# Check dashboard is running
curl http://127.0.0.1:8896

# Start signal engine (DRY_RUN=True by default)
systemctl --user start l2-signal-engine.service

# Watch logs
journalctl --user -u l2-signal-engine.service -f
```

### On REBEL-ALLIANCE (Windows)

1. **Copy NinjaTrader AddOn:**
   - File: `/home/rob/.openclaw/workspace/nq-l2-scalping/nt_bridge/L2SignalExecutor.cs`
   - Destination: `C:\Users\hartw\Documents\NinjaTrader 8\bin\Custom\AddOns\`

2. **Compile in NinjaTrader:**
   - Open NinjaTrader
   - Tools → NinjaScript Editor
   - Open `L2SignalExecutor.cs`
   - Press F5 (compile)
   - Close editor

3. **Enable AddOn:**
   - Tools → Options → NinjaScript
   - Check "L2SignalExecutor"
   - Click OK
   - Restart NinjaTrader

4. **Verify SimL2020 account exists:**
   - Tools → Accounts
   - Should see "SimL2020" (Sim account)
   - Connect the account

### Testing Flow

**Day 1: Verify Signal Generation (DRY_RUN=True)**

1. Let signal engine run through RTH session
2. Check dashboard: http://127.0.0.1:8896
3. Verify signals appear in "Recent Signals" table
4. Check NT AddOn logs in NinjaTrader Output window
5. Should see: "⏭️  Dry run signal skipped"

**Day 2: Enable Live Execution (DRY_RUN=False)**

1. Edit `/home/rob/.openclaw/workspace/nq-l2-scalping/pipeline/engines/strategy_020_signal_engine.py`
2. Line 23: Change `DRY_RUN = True` to `DRY_RUN = False`
3. Restart: `systemctl --user restart l2-signal-engine.service`
4. Next signal will execute in SimL2020 account
5. Check NT fills + dashboard

**Day 3-14: Collect Data**

- Monitor 2 weeks (~10 trades expected)
- Dashboard tracks: signals, fills, PnL, slippage, latency
- Compare sim PF vs backtest PF (8.00)
- Expected sim PF: 5.0-6.0 (degraded due to reality)

## 📊 Dashboard

http://127.0.0.1:8896

Shows:
- Signals today
- Fills today (from NT)
- Sim PnL
- Backtest vs Sim comparison
- Slippage analysis (entry expected vs actual)
- Fill latency (signal → fill time)

## 🔧 Configuration

### Signal Engine (`pipeline/engines/strategy_020_signal_engine.py`)

```python
OR_BARS = 50        # Opening range: first 50 bars (9:30-10:20 ET)
TP_TICKS = 32       # Take profit: 32 ticks ($640)
SL_TICKS = 4        # Stop loss: 4 ticks ($80)
DRY_RUN = True      # Set False to execute real trades in SimL2020
```

### NT AddOn (`nt_bridge/L2SignalExecutor.cs`)

- Polls signal file every 5 seconds
- Executes market orders via ATI
- Account: SimL2020 (hardcoded line 27)
- Contracts: 1 (hardcoded in signal, line 205 of engine)

## 🚨 Safety

- **Completely separate from main NQ pipeline**
- **SimL2020 paper account** (no real money)
- **DRY_RUN flag** (test signals before execution)
- **1 contract only** (minimize variance during testing)

## 📝 Monitoring

```bash
# Signal engine logs
tail -f /home/rob/.openclaw/workspace/nq-l2-scalping/data/l2_signal_engine.log

# Dashboard status
systemctl --user status l2-dashboard.service

# Database query
sqlite3 /home/rob/.openclaw/workspace/nq-l2-scalping/data/l2_signals.db \
  "SELECT * FROM l2_signals ORDER BY timestamp DESC LIMIT 5;"
```

## 🎯 Success Criteria

After 2 weeks (10-15 trades):

- **Sim PF ≥ 4.0** → Consider live account promotion
- **Sim PF 3.0-4.0** → Keep testing, investigate slippage
- **Sim PF < 3.0** → Strategy doesn't work with real execution

**Key metrics to watch:**
- Avg slippage per entry (target: <1 tick)
- Fill latency (target: <1000ms)
- Win rate (backtest: 50%, expect similar)

## 📂 File Locations

**Omen:**
- Signal engine: `/home/rob/.openclaw/workspace/nq-l2-scalping/pipeline/engines/strategy_020_signal_engine.py`
- Dashboard: `/home/rob/.openclaw/workspace/nq-l2-scalping/dashboard/l2_dashboard.py`
- Database: `/home/rob/.openclaw/workspace/nq-l2-scalping/data/l2_signals.db`
- Signal output: `/home/rob/.openclaw/workspace/nq-l2-scalping/nt_bridge/signal_output.json`

**REBEL-ALLIANCE (Windows):**
- NT AddOn: `C:\Users\hartw\Documents\NinjaTrader 8\bin\Custom\AddOns\L2SignalExecutor.cs`
- Signal file (via WSL): `\\WSLHOST$\Ubuntu\home\rob\.openclaw\workspace\nq-l2-scalping\nt_bridge\signal_output.json`
- Fill logs: `C:\Users\hartw\Documents\NinjaTrader ML Bridge\position_state.json`
- Executions: `C:\Users\hartw\Documents\NinjaTrader ML Bridge\executions.csv`

---

**Ready to start! Enable services on Omen, install NT AddOn on REBEL-ALLIANCE, then monitor dashboard.**
