# L2 Strategy 020 - Live Testing Infrastructure

## Architecture

```
IBKR Tick Data (DuckDB)
    ↓
Signal Engine (Omen)
    ↓ JSON file
REBEL-ALLIANCE (Windows node)
    ↓ ATI socket (port 36973)
NinjaTrader (SimL2020 account)
    ↓ Fill data
position_state.json + executions.csv
    ↓
L2 Dashboard (port 8896)
```

## Components

### 1. Signal Engine (`pipeline/engines/strategy_020_signal_engine.py`)
- Reads IBKR 1-min bars from DuckDB
- Calculates opening range (first 50 bars, 9:30-10:20 ET)
- Detects breakouts (close > OR high = long, close < OR low = short)
- Writes signals to `nt_bridge/signal_output.json`
- Logs to database (`data/l2_signals.db`)

### 2. NinjaTrader AddOn (`nt_bridge/L2SignalExecutor.cs`)
- Runs on REBEL-ALLIANCE Windows node
- Polls signal file every 5 seconds
- Executes market orders via ATI
- Writes fills to position_state.json + executions.csv
- Account: SimL2020 (paper)

### 3. Dashboard (`dashboard/l2_dashboard.py`)
- Port: 8896
- Shows recent signals, fills, PnL
- Compares backtest vs sim performance
- Tracks slippage & latency

## Setup

### On Omen (Linux)

```bash
cd /home/rob/.openclaw/workspace/nq-l2-scalping

# Enable services
systemctl --user daemon-reload
systemctl --user enable l2-signal-engine.service
systemctl --user enable l2-dashboard.service
systemctl --user start l2-signal-engine.service
systemctl --user start l2-dashboard.service

# Check logs
journalctl --user -u l2-signal-engine.service -f
```

### On REBEL-ALLIANCE (Windows)

1. Copy `nt_bridge/L2SignalExecutor.cs` to:
   `C:\Users\hartw\Documents\NinjaTrader 8\bin\Custom\AddOns\`

2. Compile in NinjaTrader:
   - Tools → NinjaScript Editor
   - Open L2SignalExecutor.cs
   - Compile (F5)

3. Enable the AddOn:
   - Tools → Options → NinjaScript
   - Check "L2SignalExecutor"
   - Restart NinjaTrader

4. Verify account:
   - SimL2020 must exist and be connected

## Config

**Signal Engine:**
- `DRY_RUN = True` (line 23) → signals written but NT won't execute
- Set `DRY_RUN = False` when ready to test live execution

**Strategy Params:**
- OR_BARS = 50 (9:30-10:20 ET)
- TP_TICKS = 32 ($640 profit target)
- SL_TICKS = 4 ($80 stop loss)

## Dashboard

http://127.0.0.1:8896

Shows:
- Signals today
- Fills today
- Sim PnL
- Backtest vs Sim comparison
- Slippage analysis
- Fill latency

## Data Flow

1. **9:30 AM ET:** RTH opens, signal engine starts tracking OR
2. **10:20 AM ET:** OR complete (50 bars)
3. **10:20+ AM ET:** Signal engine monitors for breakout
4. **Breakout detected:** Signal written to `nt_bridge/signal_output.json`
5. **5 seconds later:** NT AddOn reads signal, executes market order
6. **Fill received:** NT writes to position_state.json + executions.csv
7. **Dashboard updates:** Shows signal + fill + PnL

## Expected Performance

**Backtest (21-day):**
- PF: 8.00
- Trades: 34
- Win Rate: 50%

**Expected Sim (with execution reality):**
- PF: 5.0-6.0 (degraded due to slippage)
- Slippage: 0.5-1.0 ticks per entry
- Fill latency: 500-1000ms (NinjaTrader ATI)

## Monitoring

```bash
# Signal engine logs
tail -f data/l2_signal_engine.log

# Dashboard
systemctl --user status l2-dashboard.service

# Check database
sqlite3 data/l2_signals.db "SELECT * FROM l2_signals ORDER BY timestamp DESC LIMIT 5;"
```

## Safety

- **Separate from main NQ pipeline** (no risk to $50k BLE accounts)
- **SimL2020 account** (paper trading only)
- **DRY_RUN flag** (test signals before live execution)
- **1 contract** (minimize risk during testing)

## Next Steps

1. Start services (Omen side)
2. Install NT AddOn (REBEL-ALLIANCE side)
3. Set DRY_RUN=False when ready
4. Monitor for 2 weeks (expect ~10 trades)
5. Compare sim PF vs backtest PF
6. If sim PF ≥ 4.0 → consider live account
