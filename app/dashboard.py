from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.responses import HTMLResponse

LOG_PATH = Path(os.getenv("LOG_PATH", "data/logs.jsonl"))


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = (len(values) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(values[int(k)])
    d0 = values[int(f)] * (c - k)
    d1 = values[int(c)] * (k - f)
    return float(d0 + d1)


def compute_metrics() -> dict[str, Any]:
    if not LOG_PATH.exists():
        return {"error": "data/logs.jsonl not found"}

    records: list[dict[str, Any]] = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    total_records = len(records)
    received = [r for r in records if r.get("event") == "request_received"]
    sent = [r for r in records if r.get("event") == "response_sent"]
    failed = [r for r in records if r.get("event") == "request_failed"]

    # 1. Latency
    latencies = [float(r["latency_ms"]) for r in sent if "latency_ms" in r]
    ttfts = [float(r["ttft_ms"]) for r in sent if "ttft_ms" in r]
    p50 = round(_percentile(latencies, 50), 1)
    p95 = round(_percentile(latencies, 95), 1)
    p99 = round(_percentile(latencies, 99), 1)
    ttft_p95 = round(_percentile(ttfts, 95), 1)
    latency_ok = p95 <= 3000

    # 2. Traffic
    req_count = len(received)
    traffic_rate = round(req_count / 60.0, 2)
    traffic_ok = req_count >= 1

    # 3. Errors & Retrieval
    err_count = len(failed)
    error_rate = round((err_count / max(1, req_count)) * 100, 2)
    errors_by_type: dict[str, int] = {}
    for r in failed:
        etype = r.get("error_type", "Unknown")
        errors_by_type[etype] = errors_by_type.get(etype, 0) + 1

    tools_called = [r for r in records if r.get("tool_name") == "retrieval"]
    tools_success = [r for r in tools_called if r.get("tool_success") is True]
    retrieval_rate = round((len(tools_success) / max(1, len(tools_called))) * 100, 1) if tools_called else 100.0
    error_ok = error_rate <= 2.0

    # 4. Cost
    costs = [float(r["cost_usd"]) for r in sent if "cost_usd" in r]
    total_cost = round(sum(costs), 6)
    cost_ok = total_cost <= 2.5

    # 5. Tokens
    tokens_in = [int(r["tokens_in"]) for r in sent if "tokens_in" in r]
    tokens_out = [int(r["tokens_out"]) for r in sent if "tokens_out" in r]
    sum_tokens_in = sum(tokens_in)
    sum_tokens_out = sum(tokens_out)
    avg_tokens_out = round(sum_tokens_out / max(1, len(tokens_out)), 1)
    tokens_ok = avg_tokens_out <= 500

    # 6. Quality
    qualities = [float(r["quality_score"]) for r in sent if "quality_score" in r]
    avg_quality = round(sum(qualities) / max(1, len(qualities)), 2) if qualities else 1.0
    quality_ok = avg_quality >= 0.70

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_records": total_records,
        "latency": {"p50": p50, "p95": p95, "p99": p99, "ttft_p95": ttft_p95, "ok": latency_ok, "threshold": 3000},
        "traffic": {"count": req_count, "rate_per_min": traffic_rate, "ok": traffic_ok, "threshold": 1},
        "errors": {"rate_pct": error_rate, "errors_by_type": errors_by_type, "retrieval_success_pct": retrieval_rate, "ok": error_ok, "threshold": 2.0},
        "cost": {"total_usd": total_cost, "ok": cost_ok, "threshold": 2.5},
        "tokens": {"sum_in": sum_tokens_in, "sum_out": sum_tokens_out, "avg_out": avg_tokens_out, "ok": tokens_ok, "threshold": 500},
        "quality": {"avg_score": avg_quality, "ok": quality_ok, "threshold": 0.75},
    }


def render_dashboard_html() -> HTMLResponse:
    data = compute_metrics()
    l = data["latency"]
    t = data["traffic"]
    e = data["errors"]
    c = data["cost"]
    tok = data["tokens"]
    q = data["quality"]

    badge = lambda ok: '<span class="badge pass">NORMAL</span>' if ok else '<span class="badge fail">ALERTING</span>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="30">
    <title>K4-L3B Monitoring & LLMOps Dashboard</title>
    <style>
        :root {{
            --bg-color: #0d1117;
            --card-bg: #161b22;
            --border-color: #30363d;
            --text-primary: #f0f6fc;
            --text-secondary: #8b949e;
            --accent-green: #238636;
            --accent-red: #da3633;
            --accent-blue: #58a6ff;
            --accent-purple: #bc8cff;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            margin: 0;
            padding: 24px;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        h1 {{ margin: 0; font-size: 22px; font-weight: 600; display: flex; align-items: center; gap: 8px; }}
        .header-meta {{ font-size: 13px; color: var(--text-secondary); }}
        .meta-pill {{ background: #21262d; padding: 4px 10px; border-radius: 20px; border: 1px solid var(--border-color); margin-left: 8px; }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
            gap: 20px;
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            display: flex;
            flex-direction: column;
        }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 16px;
        }}
        .card-title {{ font-size: 15px; font-weight: 600; color: var(--text-primary); margin: 0; }}
        .card-sub {{ font-size: 12px; color: var(--text-secondary); margin-top: 4px; }}
        .badge {{
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 12px;
            text-transform: uppercase;
        }}
        .badge.pass {{ background: rgba(35, 134, 54, 0.2); color: #3fb950; border: 1px solid rgba(63, 185, 80, 0.3); }}
        .badge.fail {{ background: rgba(218, 54, 51, 0.2); color: #f85149; border: 1px solid rgba(248, 81, 73, 0.3); }}
        .metric-main {{ font-size: 32px; font-weight: 700; margin: 8px 0; color: var(--text-primary); }}
        .metric-unit {{ font-size: 14px; font-weight: 400; color: var(--text-secondary); }}
        .stats-row {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
            gap: 12px;
            margin-top: 14px;
            padding-top: 14px;
            border-top: 1px solid #21262d;
        }}
        .stat-item {{ display: flex; flex-direction: column; }}
        .stat-label {{ font-size: 11px; color: var(--text-secondary); text-transform: uppercase; }}
        .stat-val {{ font-size: 16px; font-weight: 600; margin-top: 2px; }}
        .threshold-footer {{
            margin-top: auto;
            padding-top: 14px;
            font-size: 12px;
            color: var(--text-secondary);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .progress-bar {{
            height: 6px;
            background: #21262d;
            border-radius: 3px;
            overflow: hidden;
            margin-top: 8px;
        }}
        .progress-fill {{ height: 100%; border-radius: 3px; }}
        .progress-fill.green {{ background: var(--accent-green); }}
        .progress-fill.red {{ background: var(--accent-red); }}
    </style>
</head>
<body>
    <header>
        <div>
            <h1>📊 K4-L3B Monitoring & LLMOps Dashboard</h1>
            <div class="header-meta">Service: day13-l3b-monitoring-llmops-lab | Student: Nguyen Minh Hieu (2A202602669)</div>
        </div>
        <div class="header-meta">
            <span class="meta-pill">⏱️ Time Range: 60 min</span>
            <span class="meta-pill">🔄 Refresh: 30s</span>
            <span class="meta-pill">📁 Logs: {data['total_records']} events</span>
        </div>
    </header>

    <div class="grid">
        <!-- Panel 1: Latency -->
        <div class="card" id="panel-latency">
            <div class="card-header">
                <div>
                    <h3 class="card-title">Panel 1: Latency Percentiles & TTFT</h3>
                    <div class="card-sub">Tail latency and Time-to-First-Token</div>
                </div>
                {badge(l['ok'])}
            </div>
            <div class="metric-main">{l['p95']} <span class="metric-unit">ms (P95)</span></div>
            <div class="stats-row">
                <div class="stat-item"><span class="stat-label">P50</span><span class="stat-val">{l['p50']}ms</span></div>
                <div class="stat-item"><span class="stat-label">P95</span><span class="stat-val">{l['p95']}ms</span></div>
                <div class="stat-item"><span class="stat-label">P99</span><span class="stat-val">{l['p99']}ms</span></div>
                <div class="stat-item"><span class="stat-label">TTFT P95</span><span class="stat-val">{l['ttft_p95']}ms</span></div>
            </div>
            <div class="threshold-footer">
                <span>Threshold: P95 &le; {l['threshold']}ms</span>
                <span>SLO: 3000ms</span>
            </div>
        </div>

        <!-- Panel 2: Traffic -->
        <div class="card" id="panel-traffic">
            <div class="card-header">
                <div>
                    <h3 class="card-title">Panel 2: Request Traffic</h3>
                    <div class="card-sub">Throughput & total request volume</div>
                </div>
                {badge(t['ok'])}
            </div>
            <div class="metric-main">{t['count']} <span class="metric-unit">requests</span></div>
            <div class="stats-row">
                <div class="stat-item"><span class="stat-label">Total Req</span><span class="stat-val">{t['count']}</span></div>
                <div class="stat-item"><span class="stat-label">Rate</span><span class="stat-val">{t['rate_per_min']} req/m</span></div>
                <div class="stat-item"><span class="stat-label">Source</span><span class="stat-val">data/logs</span></div>
            </div>
            <div class="threshold-footer">
                <span>Threshold: Rate &ge; {t['threshold']} req/m</span>
                <span>Unit: requests_per_minute</span>
            </div>
        </div>

        <!-- Panel 3: Errors -->
        <div class="card" id="panel-errors">
            <div class="card-header">
                <div>
                    <h3 class="card-title">Panel 3: Error Rate & Retrieval Success</h3>
                    <div class="card-sub">Error percentage & vector retrieval health</div>
                </div>
                {badge(e['ok'])}
            </div>
            <div class="metric-main">{e['rate_pct']}% <span class="metric-unit">error rate</span></div>
            <div class="stats-row">
                <div class="stat-item"><span class="stat-label">Error Rate</span><span class="stat-val">{e['rate_pct']}%</span></div>
                <div class="stat-item"><span class="stat-label">Retrieval Success</span><span class="stat-val">{e['retrieval_success_pct']}%</span></div>
                <div class="stat-item"><span class="stat-label">Error Types</span><span class="stat-val">{list(e['errors_by_type'].keys()) or 'None'}</span></div>
            </div>
            <div class="threshold-footer">
                <span>Threshold: Error rate &le; {e['threshold']}%</span>
                <span>Retrieval Target: &ge; 90%</span>
            </div>
        </div>

        <!-- Panel 4: Cost -->
        <div class="card" id="panel-cost">
            <div class="card-header">
                <div>
                    <h3 class="card-title">Panel 4: Cost Over Time</h3>
                    <div class="card-sub">Estimated LLM inference spend</div>
                </div>
                {badge(c['ok'])}
            </div>
            <div class="metric-main">${c['total_usd']} <span class="metric-unit">USD</span></div>
            <div class="stats-row">
                <div class="stat-item"><span class="stat-label">Window Total</span><span class="stat-val">${c['total_usd']}</span></div>
                <div class="stat-item"><span class="stat-label">Budget Max</span><span class="stat-val">${c['threshold']}</span></div>
            </div>
            <div class="threshold-footer">
                <span>Threshold: Total &le; ${c['threshold']}</span>
                <span>Unit: USD</span>
            </div>
        </div>

        <!-- Panel 5: Tokens -->
        <div class="card" id="panel-tokens">
            <div class="card-header">
                <div>
                    <h3 class="card-title">Panel 5: Input & Output Tokens</h3>
                    <div class="card-sub">Prompt and completion token volume</div>
                </div>
                {badge(tok['ok'])}
            </div>
            <div class="metric-main">{tok['sum_out']} <span class="metric-unit">out tokens</span></div>
            <div class="stats-row">
                <div class="stat-item"><span class="stat-label">Sum In</span><span class="stat-val">{tok['sum_in']}</span></div>
                <div class="stat-item"><span class="stat-label">Sum Out</span><span class="stat-val">{tok['sum_out']}</span></div>
                <div class="stat-item"><span class="stat-label">Avg Out/req</span><span class="stat-val">{tok['avg_out']}</span></div>
            </div>
            <div class="threshold-footer">
                <span>Threshold: Avg Out &le; {tok['threshold']}</span>
                <span>Unit: tokens</span>
            </div>
        </div>

        <!-- Panel 6: Quality -->
        <div class="card" id="panel-quality">
            <div class="card-header">
                <div>
                    <h3 class="card-title">Panel 6: Quality Score Proxy</h3>
                    <div class="card-sub">Heuristic response evaluation</div>
                </div>
                {badge(q['ok'])}
            </div>
            <div class="metric-main">{q['avg_score']} <span class="metric-unit">/ 1.0</span></div>
            <div class="stats-row">
                <div class="stat-item"><span class="stat-label">Avg Quality</span><span class="stat-val">{q['avg_score']}</span></div>
                <div class="stat-item"><span class="stat-label">Target Min</span><span class="stat-val">{q['threshold']}</span></div>
            </div>
            <div class="threshold-footer">
                <span>Threshold: Avg &ge; {q['threshold']}</span>
                <span>Unit: score</span>
            </div>
        </div>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html)
