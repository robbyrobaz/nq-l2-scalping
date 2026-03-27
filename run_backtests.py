#!/usr/bin/env python3
"""Run priority L2 strategies and output results."""

import sys
import json
import importlib.util
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Suppress progress bars
import os
os.environ["TQDM_DISABLE"] = "1"

STRATEGIES = [
    ("020", "strategies/020_simplest_orderflow_model/backtest.py"),
    ("014", "strategies/014_failed_auction_hook/backtest.py"),
    ("007", "strategies/007_sweep_fade/backtest.py"),
    ("018", "strategies/018_delta_absorption_live_trade/backtest.py"),
    ("001", "strategies/001_delta_absorption_breakout/backtest.py"),
]

results = {}

for sid, path in STRATEGIES:
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Running strategy {sid}...", file=sys.stderr)
    try:
        spec = importlib.util.spec_from_file_location(f"s{sid}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod.run_backtest()
        results[sid] = result
        pf = result.get("profit_factor", 0)
        trades = result.get("num_trades", 0)
        net = result.get("net_pnl", 0)
        wr = result.get("win_rate", 0)
        dd = result.get("max_drawdown", 0)
        print(f"  Strategy {sid}: PF={pf:.2f}, Trades={trades}, Net=${net:.0f}, WR={wr:.1%}, DD=${dd:.0f}", file=sys.stderr)
    except Exception as e:
        results[sid] = {"error": str(e), "traceback": traceback.format_exc()}
        print(f"  Strategy {sid} FAILED: {e}", file=sys.stderr)

# Output JSON to stdout
print(json.dumps(results, indent=2, default=str))
