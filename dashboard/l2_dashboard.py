#!/usr/bin/env python3
"""L2 Trading Dashboard - Strategy 020 Monitoring"""

from flask import Flask, render_template_string
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
L2_DB = Path(__file__).parent.parent / "data" / "l2_signals.db"

TEMPLATE = """
<!DOCTYPE html>
<html><head><title>L2 Dashboard - Strategy 020</title>
<meta http-equiv="refresh" content="30">
<style>
body{background:#0a0e14;color:#e4eaf2;font-family:monospace;padding:20px}
h1{color:#00e676}table{width:100%;border-collapse:collapse;margin:20px 0}
th,td{padding:10px;text-align:left;border-bottom:1px solid #2a2a2a}
th{background:#161b22;color:#00e5ff}.pos{color:#00e676}.neg{color:#ff5252}
</style></head><body>
<h1>📊 L2 Dashboard — Strategy 020</h1>
<p>Signals: {{ stats.signals_today }} | Fills: {{ stats.fills_today }} | PnL: ${{ stats.pnl_today }}</p>
<h2>Recent Signals</h2><table><thead><tr>
<th>Time</th><th>Direction</th><th>Entry</th><th>TP</th><th>SL</th></tr></thead><tbody>
{% for s in signals %}<tr><td>{{ s.timestamp }}</td><td>{{ s.direction.upper() }}</td>
<td>{{ "%.2f"|format(s.entry_price) }}</td><td>{{ "%.2f"|format(s.tp_price) }}</td>
<td>{{ "%.2f"|format(s.sl_price) }}</td></tr>{% endfor %}</tbody></table>
<h2>Fills</h2><table><thead><tr><th>Entry</th><th>Exit</th><th>PnL</th></tr></thead><tbody>
{% for f in fills %}<tr><td>{{ f.entry_time }}</td><td>{{ f.exit_time or "Open" }}</td>
<td class="{{ 'pos' if f.pnl_usd and f.pnl_usd > 0 else 'neg' if f.pnl_usd else '' }}">
${{ "%.0f"|format(f.pnl_usd) if f.pnl_usd else "—" }}</td></tr>{% endfor %}</tbody></table>
</body></html>
"""

def get_data():
    con = sqlite3.connect(str(L2_DB))
    con.row_factory = sqlite3.Row
    
    signals = [dict(r) for r in con.execute("SELECT * FROM l2_signals ORDER BY timestamp DESC LIMIT 20").fetchall()]
    fills = [dict(r) for r in con.execute("SELECT * FROM l2_fills ORDER BY entry_time DESC LIMIT 20").fetchall()]
    
    today = datetime.now().date().isoformat()
    stats = {
        'signals_today': con.execute(f"SELECT COUNT(*) FROM l2_signals WHERE DATE(timestamp)='{today}'").fetchone()[0],
        'fills_today': con.execute(f"SELECT COUNT(*) FROM l2_fills WHERE DATE(entry_time)='{today}'").fetchone()[0],
        'pnl_today': con.execute(f"SELECT COALESCE(SUM(pnl_usd),0) FROM l2_fills WHERE DATE(entry_time)='{today}'").fetchone()[0]
    }
    con.close()
    return {'signals': signals, 'fills': fills, 'stats': stats}

@app.route("/")
def index():
    return render_template_string(TEMPLATE, **get_data())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8896, debug=False)
