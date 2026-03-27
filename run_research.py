#!/usr/bin/env python3
"""Memory-efficient L2 strategy research runner.

Uses DuckDB ASOF join to infer side without loading all quotes into Python.
"""
import sys, json, importlib.util, gc, traceback
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))

DB_PATH = "/tmp/nq_feed_readonly.duckdb"
NQ_TICK_SIZE = 0.25


def load_ticks_with_side(lookback_days=14):
    """Load ticks with side inferred via DuckDB ASOF join (no Python quote loading)."""
    conn = duckdb.connect(DB_PATH, read_only=True)
    
    # Filter to recent data to avoid OOM
    cutoff = f"NOW() - INTERVAL {lookback_days} DAYS"
    
    # Use DuckDB's ASOF JOIN to infer side efficiently in SQL
    df = conn.execute(f"""
        WITH trades_ordered AS (
            SELECT ts_utc, price, size FROM nq_ticks 
            WHERE ts_utc >= {cutoff}
            ORDER BY ts_utc
        ),
        quotes_ordered AS (
            SELECT ts_utc as q_ts, bid, ask FROM nq_quotes 
            WHERE ts_utc >= {cutoff}
            ORDER BY ts_utc
        )
        SELECT t.ts_utc, t.price, t.size,
               q.bid, q.ask,
               CASE 
                   WHEN t.price >= q.ask THEN 'B'
                   WHEN t.price <= q.bid THEN 'S'
                   ELSE ''
               END as side,
               CASE 
                   WHEN t.price >= q.ask THEN t.size
                   WHEN t.price <= q.bid THEN -t.size
                   ELSE 0
               END as delta
        FROM trades_ordered t ASOF JOIN quotes_ordered q ON t.ts_utc >= q.q_ts
        ORDER BY t.ts_utc
    """).fetchdf()
    
    conn.close()
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
    return df


def build_bars_from_ticks(ticks: pd.DataFrame) -> pd.DataFrame:
    """Build 1-min bars with delta from ticks."""
    if ticks.empty:
        return pd.DataFrame()
    
    bar_ts = ticks["ts_utc"].dt.floor("1min")
    
    bars = ticks.groupby(bar_ts).agg(
        open=("price", "first"),
        high=("price", "max"),
        low=("price", "min"),
        close=("price", "last"),
        volume=("size", "sum"),
        bar_delta=("delta", "sum"),
        trade_count=("price", "count"),
    ).reset_index()
    bars.rename(columns={"index": "ts_utc"}, inplace=True)
    if "ts_utc" not in bars.columns:
        bars = bars.rename_axis("ts_utc").reset_index()
    bars["cumulative_delta"] = bars["bar_delta"].cumsum()
    
    # Add session tags for compatibility with old strategy code
    from pipeline.data_loader import tag_sessions
    bars = tag_sessions(bars, ts_col="ts_utc")
    
    return bars


def load_strategy_module(strat_dir: str):
    """Dynamically load a strategy backtest module."""
    path = Path(__file__).parent / "strategies" / strat_dir / "backtest.py"
    spec = importlib.util.spec_from_file_location(f"backtest_{strat_dir}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_strategy(strat_dir: str, bars: pd.DataFrame, ticks: pd.DataFrame, params: dict = None) -> dict:
    """Run strategy with full tick simulation."""
    from pipeline.backtest_utils import compute_trade_metrics, iter_trade_specs
    
    mod = load_strategy_module(strat_dir)
    if params is None:
        params = mod.PARAMS.copy()
    
    if not hasattr(mod, '_build_specs'):
        return None
    
    specs = mod._build_specs(bars, ticks, params)
    if not specs:
        return {"num_trades": 0, "profit_factor": 0, "net_pnl": 0}
    
    trades = iter_trade_specs(specs, ticks)
    if not trades:
        return {"num_trades": 0, "profit_factor": 0, "net_pnl": 0}
    
    metrics = compute_trade_metrics(trades, bars)
    return metrics


def run_param_sweep(strat_dir: str, bars: pd.DataFrame, ticks: pd.DataFrame, param_grid: dict) -> list:
    """Run parameter sweep."""
    from itertools import product as iprod
    from pipeline.backtest_utils import compute_trade_metrics, iter_trade_specs
    
    mod = load_strategy_module(strat_dir)
    base_params = mod.PARAMS.copy()
    
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combos = list(iprod(*values))
    
    print(f"  Running {len(combos)} param combos...")
    results = []
    for i, combo in enumerate(combos):
        params = base_params.copy()
        for k, v in zip(keys, combo):
            params[k] = v
        
        try:
            specs = mod._build_specs(bars, ticks, params)
            if not specs:
                continue
            trades = iter_trade_specs(specs, ticks)
            if not trades:
                continue
            metrics = compute_trade_metrics(trades, bars)
            metrics["params"] = {k: v for k, v in zip(keys, combo)}
            results.append(metrics)
            if (i + 1) % 10 == 0:
                print(f"  ...{i+1}/{len(combos)} done")
        except Exception as e:
            pass
    
    results.sort(key=lambda x: x.get("profit_factor", 0), reverse=True)
    return results


if __name__ == "__main__":
    print("=" * 60)
    print("L2 SCALPING RESEARCH — MEMORY-EFFICIENT RUNNER")
    print(f"Time: {datetime.now()}")
    print("=" * 60)
    
    # Load ticks with NBBO via DuckDB ASOF join
    print("\nLoading ticks with side inference (DuckDB ASOF join)...")
    ticks = load_ticks_with_side()
    print(f"  Ticks: {len(ticks):,} rows ({ticks.ts_utc.min()} to {ticks.ts_utc.max()})")
    print(f"  Side distribution: B={sum(ticks.side=='B'):,}, S={sum(ticks.side=='S'):,}, ?={sum(ticks.side==''):,}")
    print(f"  Memory: {ticks.memory_usage(deep=True).sum()/1e9:.2f} GB")
    
    # Build bars
    print("Building bars...")
    bars = build_bars_from_ticks(ticks)
    print(f"  Bars: {len(bars)} rows")
    
    # Priority strategies
    strategies = [
        ("020_simplest_orderflow_model", "020 Simplest Orderflow (IVB Breakout)", {
            "opening_range_bars": [15, 30, 45, 60],
            "take_profit_ticks": [12, 16, 20, 24, 32],
            "stop_loss_ticks": [6, 8, 10, 12, 16],
            "wait_for_retest": [False, True],
        }),
        ("014_failed_auction_hook", "014 Failed Auction Hook", None),
        ("001_delta_absorption_breakout", "001 Delta Absorption Breakout", None),
        ("018_delta_absorption_live_trade", "018 Delta Absorption Live Trade", None),
    ]
    
    all_results = {}
    winners = []
    
    for strat_dir, name, param_grid in strategies:
        print(f"\n{'='*60}")
        print(f"STRATEGY: {name}")
        print(f"{'='*60}")
        
        try:
            if param_grid:
                results = run_param_sweep(strat_dir, bars, ticks, param_grid)
                if results:
                    print(f"\n  Top 5 configurations:")
                    for i, r in enumerate(results[:5]):
                        pf = r.get('profit_factor', 0)
                        nt = r.get('num_trades', 0)
                        pnl = r.get('net_pnl', 0)
                        dd = r.get('max_drawdown', 0)
                        wr = r.get('win_rate', 0)
                        print(f"  #{i+1}: PF={pf:.2f} WR={wr:.1%} Trades={nt} PnL=${pnl:.0f} DD=${dd:.0f} Params={r['params']}")
                        if pf > 1.5 and nt >= 50 and abs(dd) < 3000:
                            winners.append({"strategy": name, "pf": pf, "trades": nt, "pnl": pnl, "dd": dd, "params": r["params"]})
                    all_results[strat_dir] = results[:10]
                else:
                    print("  No winning configurations found")
            else:
                # Run with defaults first
                metrics = run_strategy(strat_dir, bars, ticks)
                if metrics and metrics.get("num_trades", 0) > 0:
                    pf = metrics.get('profit_factor', 0)
                    nt = metrics.get('num_trades', 0)
                    pnl = metrics.get('net_pnl', 0)
                    dd = metrics.get('max_drawdown', 0)
                    wr = metrics.get('win_rate', 0)
                    print(f"  Default: PF={pf:.2f} WR={wr:.1%} Trades={nt} PnL=${pnl:.0f} DD=${dd:.0f}")
                    
                    if pf > 1.5 and nt >= 50 and abs(dd) < 3000:
                        winners.append({"strategy": name, "pf": pf, "trades": nt, "pnl": pnl, "dd": dd, "params": "default"})
                    
                    # Quick TP/SL sweep
                    mod = load_strategy_module(strat_dir)
                    base = mod.PARAMS.copy()
                    variants = []
                    for tp in [12, 16, 20, 24, 32]:
                        for sl in [6, 8, 10, 12, 16]:
                            p = base.copy()
                            if "take_profit_ticks" in p:
                                p["take_profit_ticks"] = tp
                            if "stop_loss_ticks" in p:
                                p["stop_loss_ticks"] = sl
                            if "tp_ticks" in p:
                                p["tp_ticks"] = tp
                            if "sl_ticks" in p:
                                p["sl_ticks"] = sl
                            m = run_strategy(strat_dir, bars, ticks, p)
                            if m and m.get("num_trades", 0) > 0:
                                m["params"] = {"tp": tp, "sl": sl}
                                variants.append(m)
                    
                    variants.sort(key=lambda x: x.get("profit_factor", 0), reverse=True)
                    if variants:
                        print(f"\n  Top 5 TP/SL variants:")
                        for i, r in enumerate(variants[:5]):
                            pf = r.get('profit_factor', 0)
                            nt = r.get('num_trades', 0)
                            pnl = r.get('net_pnl', 0)
                            dd = r.get('max_drawdown', 0)
                            wr = r.get('win_rate', 0)
                            print(f"  #{i+1}: PF={pf:.2f} WR={wr:.1%} Trades={nt} PnL=${pnl:.0f} DD=${dd:.0f} Params={r['params']}")
                            if pf > 1.5 and nt >= 50 and abs(dd) < 3000:
                                winners.append({"strategy": name, "pf": pf, "trades": nt, "pnl": pnl, "dd": dd, "params": r["params"]})
                    all_results[strat_dir] = variants[:10] if variants else [metrics]
                else:
                    print("  No trades generated")
        except Exception as e:
            print(f"  ERROR: {e}")
            traceback.print_exc()
    
    # Save results
    print(f"\n{'='*60}")
    print("SAVING RESULTS")
    print(f"{'='*60}")
    
    today = datetime.now().strftime("%Y-%m-%d")
    results_dir = Path("data/results")
    results_dir.mkdir(parents=True, exist_ok=True)
    
    for strat_dir, results in all_results.items():
        strat_num = strat_dir.split("_")[0]
        outpath = results_dir / f"{strat_num}_optimization_{today}.json"
        clean = []
        for r in results:
            c = {k: v for k, v in r.items() if k not in ("trades_detail", "trades")}
            clean.append(c)
        with open(outpath, "w") as f:
            json.dump(clean, f, indent=2, default=str)
        print(f"  Saved: {outpath}")
    
    # Summary
    print(f"\n{'='*60}")
    print("WINNERS (PF>1.5, trades>=50, DD<$3K)")
    print(f"{'='*60}")
    if winners:
        for w in winners:
            print(f"  🎯 {w['strategy']}: PF={w['pf']:.2f} Trades={w['trades']} PnL=${w['pnl']:.0f} DD=${w['dd']:.0f} Params={w['params']}")
    else:
        print("  No winners meeting all criteria this run")
    
    # Save status
    with open("data/l2_research_status.md", "w") as f:
        f.write(f"# L2 Research Status\n\n")
        f.write(f"## Last Update\n{datetime.now().strftime('%Y-%m-%d %H:%M')} MST\n\n")
        f.write(f"## Data\n")
        f.write(f"- Ticks: {len(ticks):,} ({ticks.ts_utc.min().date()} to {ticks.ts_utc.max().date()})\n")
        f.write(f"- Bars: {len(bars)}\n\n")
        f.write(f"## Strategies Run\n")
        for strat_dir, name, _ in strategies:
            if strat_dir in all_results:
                top = all_results[strat_dir][0] if all_results[strat_dir] else {}
                f.write(f"- {name}: PF={top.get('profit_factor',0):.2f} Trades={top.get('num_trades',0)}\n")
            else:
                f.write(f"- {name}: no results\n")
        f.write(f"\n## Winners\n")
        if winners:
            for w in winners:
                f.write(f"- 🎯 {w['strategy']}: PF={w['pf']:.2f} Trades={w['trades']} PnL=${w['pnl']:.0f}\n")
        else:
            f.write("- None meeting criteria (PF>1.5, trades>=50, DD<$3K)\n")
    
    print(f"\nDone! Status saved to data/l2_research_status.md")
