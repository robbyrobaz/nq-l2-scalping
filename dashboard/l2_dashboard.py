#!/usr/bin/env python3
"""
L2 Trading Dashboard - Strategy 020 Monitoring

Shows:
- Recent signals
- Sim fills from NinjaTrader
- Backtest vs Sim PF comparison
- Slippage analysis
- Fill latency
"""

from flask import Flask, render_template_string
from pathlib import Path
from datetime import datetime, timedelta

app = Flask(__name__)

L2_DB = Path(__file__).parent.parent / "data" / "l2_signals.db"

TEMPLATE = r"""
<!DOCTYPE html>
<html>
<head>
    <title>L2 Dashboard - Strategy 020</title>
    <meta http-equiv="refresh" content="30">
    <style>
        body { background: #0a0e14; color: #e4eaf2; font-family: monospace; padding: 20px; }
        h1 { color: #00e676; }
        h2 { color: #00e5ff; margin-top: 30px; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #2a2a2a; }
        th { background: #161b22; color: #00e5ff; }
        .pos { color: #00e676; }
        .neg { color: #ff5252; }
        .pending { color: #ffd740; }
        .metric { display: inline-block; margin: 10px 20px; padding: 15px; background: #161b22; border-radius: 8px; }
        .metric-label { color: #858fa0; font-size: 12px; }
        .metric-value { font-size: 24px; font-weight: bold; }
    </style>
</head>
<body>
    <h1>📊 L2 Dashboard — Strategy 020</h1>
    <p style="color: #858fa0;">Opening Range Breakout (OR=50, TP=32, SL=4) | SimL2020 Account</p>
    
    <div>
        <div class="metric">
            <div class="metric-label">Signals Today</div>
            <div class="metric-value">{{ stats.signals_today }}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Fills Today</div>
            <div class="metric-value">{{ stats.fills_today }}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Sim PnL (Today)</div>
            <div class="metric-value {{ 'pos' if stats.pnl_today > 0 else 'neg' if stats.pnl_today < 0 else '' }}">
                ${{ "%.0f"|format(stats.pnl_today) }}
            </div>
        </div>
        <div class="metric">
            <div class="metric-label">Sim PF (All Time)</div>
            <div class="metric-value">{{ "%.2f"|format(stats.sim_pf) if stats.sim_pf else "—" }}</div>
        </div>
    </div>
    
    <h2>Recent Signals</h2>
    <table>
        <thead>
            <tr>
                <th>Time</th>
                <th>Direction</th>
                <th>Entry</th>
                <th>TP</th>
                <th>SL</th>
                <th>OR High</th>
                <th>OR Low</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody>
            {% for s in signals %}
            <tr>
                <td>{{ s.timestamp }}</td>
                <td>{{ s.direction.upper() }}</td>
                <td>{{ "%.2f"|format(s.entry_price) }}</td>
                <td>{{ "%.2f"|format(s.tp_price) }}</td>
                <td>{{ "%.2f"|format(s.sl_price) }}</td>
                <td>{{ "%.2f"|format(s.or_high) }}</td>
                <td>{{ "%.2f"|format(s.or_low) }}</td>
                <td class="{{ 'pos' if s.executed else 'pending' }}">
                    {{ "✅ Filled" if s.executed else "⏳ Pending" }}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    
    <h2>Sim Fills</h2>
    <table>
        <thead>
            <tr>
                <th>Entry Time</th>
                <th>Exit Time</th>
                <th>Entry Price</th>
                <th>Exit Price</th>
                <th>Contracts</th>
                <th>PnL</th>
                <th>Exit Reason</th>
                <th>Slippage</th>
                <th>Latency</th>
            </tr>
        </thead>
        <tbody>
            {% for f in fills %}
            <tr>
                <td>{{ f.entry_time }}</td>
                <td>{{ f.exit_time or "Open" }}</td>
                <td>{{ "%.2f"|format(f.entry_price) }}</td>
                <td>{{ "%.2f"|format(f.exit_price) if f.exit_price else "—" }}</td>
                <td>{{ f.contracts }}</td>
                <td class="{{ 'pos' if f.pnl_usd and f.pnl_usd > 0 else 'neg' if f.pnl_usd and f.pnl_usd < 0 else '' }}">
                    ${{ "%.0f"|format(f.pnl_usd) if f.pnl_usd else "—" }}
                </td>
                <td>{{ f.exit_reason or "—" }}</td>
                <td>{{ "%.2f"|format(f.slippage_ticks) if f.slippage_ticks else "—" }} ticks</td>
                <td>{{ f.fill_latency_ms if f.fill_latency_ms else "—" }} ms</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    
    <h2>Backtest vs Sim Comparison</h2>
    <table>
        <thead>
            <tr>
                <th>Metric</th>
                <th>Backtest (21-day)</th>
                <th>Sim (Live)</th>
                <th>Difference</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Profit Factor</td>
                <td>8.00</td>
                <td>{{ "%.2f"|format(stats.sim_pf) if stats.sim_pf else "—" }}</td>
                <td class="{{ 'neg' if stats.sim_pf and stats.sim_pf < 8.0 else 'pos' if stats.sim_pf else '' }}">
                    {{ "%.2f"|format(stats.sim_pf - 8.0) if stats.sim_pf else "—" }}
                </td>
            </tr>
            <tr>
                <td>Win Rate</td>
                <td>50.0%</td>
                <td>{{ "%.1f"|format(stats.sim_wr * 100) if stats.sim_wr else "—" }}%</td>
                <td>—</td>
            </tr>
            <tr>
                <td>Avg Slippage</td>
                <td>0 ticks (assumed)</td>
                <td>{{ "%.2f"|format(stats.avg_slippage) if stats.avg_slippage else "—" }} ticks</td>
                <td class="neg">{{ "%.2f"|format(stats.avg_slippage) if stats.avg_slippage else "—" }} ticks</td>
            </tr>
            <tr>
                <td>Avg Fill Latency</td>
                <td>0 ms (instant)</td>
                <td>{{ "%d"|format(stats.avg_latency) if stats.avg_latency else "—" }} ms</td>
                <td class="neg">{{ "%d"|format(stats.avg_latency) if stats.avg_latency else "—" }} ms</td>
            </tr>
        </tbody>
    </table>
    
    <p style="color: #858fa0; margin-top: 30px;">
        🔄 Auto-refreshes every 30 seconds | Data: {{ now }}
    </p>
</body>
</html>
"""

def get_data():
    """Load signals and fills from database."""
    con = duckdb.connect(str(L2_DB), read_only=True)
    
    # Recent signals (last 7 days)
    signals = con.execute("""
        SELECT * FROM l2_signals
        WHERE timestamp >= datetime('now', '-7 days')
        ORDER BY timestamp DESC
        LIMIT 20
    """).fetchdf().to_dict('records')
    
    # Recent fills
    fills = con.execute("""
        SELECT * FROM l2_fills
        ORDER BY entry_time DESC
        LIMIT 20
    """).fetchdf().to_dict('records')
    
    # Today's stats
    today = datetime.now().date().isoformat()
    
    try:
        signals_today = con.execute(f"""
            SELECT COUNT(*) as cnt FROM l2_signals
            WHERE CAST(timestamp AS DATE) = CAST('{today}' AS DATE)
        """).fetchone()[0]
    except:
        signals_today = 0
    
    try:
        fills_today = con.execute(f"""
            SELECT COUNT(*) as cnt FROM l2_fills
            WHERE CAST(entry_time AS DATE) = CAST('{today}' AS DATE)
        """).fetchone()[0]
    except:
        fills_today = 0
    
    try:
        pnl_today = con.execute(f"""
            SELECT COALESCE(SUM(pnl_usd), 0) as total FROM l2_fills
            WHERE CAST(entry_time AS DATE) = CAST('{today}' AS DATE)
        """).fetchone()[0]
    except:
        pnl_today = 0.0
    
    # All-time sim stats
    import pandas as pd
    fills_raw = con.execute("SELECT * FROM l2_fills WHERE pnl_usd IS NOT NULL").fetchall()
    all_fills = pd.DataFrame([dict(row) for row in fills_raw]) if fills_raw else pd.DataFrame()
    
    sim_pf = None
    sim_wr = None
    avg_slippage = None
    avg_latency = None
    
    if len(all_fills) > 0:
        wins = all_fills[all_fills['pnl_usd'] > 0]
        losses = all_fills[all_fills['pnl_usd'] < 0]
        
        if len(losses) > 0:
            sim_pf = wins['pnl_usd'].sum() / abs(losses['pnl_usd'].sum())
        
        sim_wr = len(wins) / len(all_fills)
        avg_slippage = all_fills['slippage_ticks'].mean() if 'slippage_ticks' in all_fills else None
        avg_latency = all_fills['fill_latency_ms'].mean() if 'fill_latency_ms' in all_fills else None
    
    con.close()
    
    return {
        'signals': signals,
        'fills': fills,
        'stats': {
            'signals_today': signals_today,
            'fills_today': fills_today,
            'pnl_today': pnl_today,
            'sim_pf': sim_pf,
            'sim_wr': sim_wr,
            'avg_slippage': avg_slippage,
            'avg_latency': avg_latency,
        },
        'now': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }


@app.route("/")
def index():
    data = get_data()
    return render_template_string(TEMPLATE, **data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8896, debug=False)
