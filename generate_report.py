"""
Generate a styled HTML run log for a completed HR workflow session.
Usage: python generate_report.py <session_id>
"""
import sys
import json
import asyncio
from datetime import datetime
from db.mongodb import connect, get_db

import os
from pathlib import Path

SESSION_ID = sys.argv[1] if len(sys.argv) > 1 else None

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>HR Workflow Run Log — {session_id}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: #0f1117; color: #e2e8f0; padding: 32px; }}
  h1   {{ font-size: 22px; font-weight: 700; color: #fff; margin-bottom: 4px; }}
  .sub {{ font-size: 13px; color: #64748b; margin-bottom: 24px; }}

  /* Tabs */
  .tabs {{ display: flex; gap: 4px; margin-bottom: 20px; border-bottom: 1px solid #2d3148; padding-bottom: 0; }}
  .tab-btn {{
    background: none; border: none; color: #64748b; font-size: 13px; font-weight: 600;
    padding: 8px 18px; cursor: pointer; border-radius: 6px 6px 0 0;
    border: 1px solid transparent; border-bottom: none; position: relative; bottom: -1px;
    letter-spacing: .04em;
  }}
  .tab-btn:hover {{ color: #e2e8f0; }}
  .tab-btn.active {{ color: #e2e8f0; background: #1e2130; border-color: #2d3148; }}
  .tab-pane {{ display: none; }}
  .tab-pane.active {{ display: block; }}

  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }}
  .card {{ background: #1e2130; border: 1px solid #2d3148; border-radius: 10px; padding: 20px; }}
  .card h2 {{ font-size: 11px; text-transform: uppercase; letter-spacing: .08em;
              color: #64748b; margin-bottom: 14px; }}
  .badge {{ display: inline-block; padding: 3px 10px; border-radius: 99px;
            font-size: 12px; font-weight: 600; }}
  .green  {{ background: #14532d44; color: #4ade80; border: 1px solid #166534; }}
  .blue   {{ background: #1e3a5f44; color: #60a5fa; border: 1px solid #1e40af; }}
  .gray   {{ background: #1f293744; color: #94a3b8; border: 1px solid #334155; }}
  .red    {{ background: #3b0f0f44; color: #f87171; border: 1px solid #7f1d1d; }}
  .kv     {{ display: flex; justify-content: space-between; align-items: flex-start;
             padding: 8px 0; border-bottom: 1px solid #2d3148; font-size: 13px; }}
  .kv:last-child {{ border-bottom: none; }}
  .kv .k  {{ color: #94a3b8; flex-shrink: 0; margin-right: 12px; }}
  .kv .v  {{ color: #e2e8f0; text-align: right; word-break: break-word; }}
  .skill-list {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }}
  .skill {{ background: #1e3a5f44; border: 1px solid #1e40af44; color: #93c5fd;
            font-size: 11px; padding: 2px 8px; border-radius: 4px; }}
  .timeline {{ list-style: none; position: relative; padding-left: 24px; }}
  .timeline::before {{ content:''; position:absolute; left:7px; top:4px; bottom:4px;
                       width:2px; background:#2d3148; }}
  .timeline li {{ position: relative; margin-bottom: 18px; font-size: 13px; }}
  .timeline li::before {{ content:''; position:absolute; left:-20px; top:4px;
                           width:10px; height:10px; border-radius:50%;
                           background:#4ade80; border:2px solid #14532d; }}
  .timeline .ts  {{ font-size: 11px; color: #64748b; margin-bottom: 2px; }}
  .timeline .msg {{ color: #e2e8f0; }}

  /* Data table */
  .data-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  .data-table th {{
    text-align: left; padding: 8px 12px; font-size: 11px; text-transform: uppercase;
    letter-spacing: .06em; color: #64748b; border-bottom: 1px solid #2d3148;
    white-space: nowrap;
  }}
  .data-table td {{ padding: 10px 12px; border-bottom: 1px solid #1e293766; vertical-align: top; }}
  .data-table tr:last-child td {{ border-bottom: none; }}
  .data-table tr:hover td {{ background: #ffffff08; }}
  .score-pill {{ font-size: 16px; font-weight: 800; color: #4ade80; }}
  .reason-cell {{ color: #94a3b8; font-style: italic; max-width: 260px; }}
  .name-cell {{ font-weight: 600; color: #e2e8f0; }}
  .meta-cell {{ color: #94a3b8; font-size: 12px; }}

  /* Transcript */
  .cand-section {{ margin-bottom: 24px; }}
  .cand-section-header {{
    display: flex; align-items: center; gap: 12px;
    font-size: 13px; font-weight: 700; color: #e2e8f0;
    margin-bottom: 14px; padding-bottom: 10px;
    border-bottom: 1px solid #2d3148;
  }}
  .convo {{ font-size: 13px; }}
  .turn  {{ display: flex; gap: 10px; margin-bottom: 12px; }}
  .turn .who {{ font-size: 11px; font-weight: 700; min-width: 72px; padding-top: 2px; }}
  .agent-who {{ color: #818cf8; }}
  .cand-who  {{ color: #34d399; }}
  .turn .txt {{ background: #111827; border: 1px solid #2d3148; border-radius: 8px;
                padding: 8px 12px; color: #e2e8f0; flex: 1; }}
  .no-transcript {{ color: #64748b; font-style: italic; font-size: 13px; padding: 12px 0; }}

  .full {{ grid-column: 1 / -1; }}
  .section-title {{ font-size: 13px; font-weight: 600; color: #94a3b8;
                    text-transform: uppercase; letter-spacing: .06em;
                    margin: 24px 0 10px; }}

  /* Terminal / Logs tab */
  .terminal {{
    background: #090c10; border: 1px solid #1e2d40; border-radius: 10px;
    padding: 20px; font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
    font-size: 12px; line-height: 1.7; overflow-x: auto;
  }}
  .log-line {{ display: flex; gap: 12px; margin-bottom: 2px; }}
  .log-ts   {{ color: #2d6a4f; white-space: nowrap; flex-shrink: 0; }}
  .log-lvl  {{ font-weight: 700; white-space: nowrap; flex-shrink: 0; min-width: 46px; }}
  .log-evt  {{ color: #e2e8f0; flex: 1; }}
  .log-fields {{ color: #64748b; word-break: break-all; }}
  .lvl-info    {{ color: #4ade80; }}
  .lvl-warning {{ color: #fbbf24; }}
  .lvl-error   {{ color: #f87171; }}
  .lvl-debug   {{ color: #818cf8; }}
  .log-sep {{ border: none; border-top: 1px solid #1e2d40; margin: 12px 0; }}

  .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; margin-bottom: 20px; }}
  .metric-card {{ background: #111827; border: 1px solid #1e2d40; border-radius: 8px; padding: 14px 16px; }}
  .metric-card .m-name {{ font-size: 11px; text-transform: uppercase; letter-spacing: .07em; color: #4ade80; margin-bottom: 6px; }}
  .metric-card .m-val  {{ font-size: 22px; font-weight: 800; color: #e2e8f0; }}
  .metric-card .m-sub  {{ font-size: 11px; color: #64748b; margin-top: 2px; }}
</style>
</head>
<body>
<h1>HR Workflow Run Log</h1>
<div class="sub">Session: {session_id} &nbsp;·&nbsp; Generated: {generated_at}</div>

<!-- Tabs -->
<div class="tabs">
  <button class="tab-btn active" onclick="showTab('overview', this)">Overview</button>
  <button class="tab-btn"       onclick="showTab('transcript', this)">Call Transcripts</button>
  <button class="tab-btn"       onclick="showTab('logs', this)">Terminal Logs</button>
</div>

<!-- Overview tab -->
<div id="tab-overview" class="tab-pane active">
  <div class="grid">
    <div class="card">
      <h2>Workflow Status</h2>
      {status_rows}
    </div>
    <div class="card">
      <h2>Workflow Timeline</h2>
      <ul class="timeline">{timeline_html}</ul>
    </div>
  </div>

  <div class="card full" style="margin-bottom:16px;">
    <h2>Shortlisted Candidates ({candidate_count})</h2>
    {candidates_table}
  </div>

  <div class="card full" style="margin-bottom:16px;">
    <h2>Pre-Screening Results ({screening_count})</h2>
    {screening_table}
  </div>
</div>

<!-- Transcript tab -->
<div id="tab-transcript" class="tab-pane">
  {all_transcripts}
</div>

<!-- Logs tab -->
<div id="tab-logs" class="tab-pane">
  <div class="metric-grid">{metric_cards_html}</div>
  <div class="terminal">{terminal_html}</div>
</div>

<script>
function showTab(name, btn) {{
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  btn.classList.add('active');
}}
</script>
</body>
</html>"""


def badge(text, color="green"):
    return f'<span class="badge {color}">{text}</span>'


def kv(key, value):
    return f'<div class="kv"><span class="k">{key}</span><span class="v">{value}</span></div>'


def _log_line(ts: str, level: str, event: str, fields: dict) -> str:
    ts_short = ts[:19].replace("T", " ") if ts else ""
    lvl_class = {
        "info": "lvl-info", "warning": "lvl-warning",
        "error": "lvl-error", "debug": "lvl-debug",
    }.get(level.lower(), "lvl-info")
    lvl_label = level.upper()[:4]
    fields_str = "  " + "  ".join(
        f'<span style="color:#60a5fa">{k}</span>=<span style="color:#94a3b8">{v}</span>'
        for k, v in fields.items()
    ) if fields else ""
    return (
        f'<div class="log-line">'
        f'<span class="log-ts">{ts_short}</span>'
        f'<span class="log-lvl {lvl_class}">[{lvl_label}]</span>'
        f'<span class="log-evt">{event}{fields_str}</span>'
        f'</div>'
    )


def _call_status_badge(status: str) -> str:
    color = "green" if status == "completed" else ("red" if status == "failed" else "gray")
    return badge(status or "—", color)


def _build_candidates_table(candidates: list[dict]) -> str:
    if not candidates:
        return '<p style="color:#64748b;font-size:13px;padding:8px 0;">No candidates found.</p>'

    rows = ""
    for c in candidates:
        skills_html = "".join(
            f'<span class="skill">{s[:30]}</span>'
            for s in c.get("skills", [])[:12]
        )
        score = c.get("match_score", 0)
        score_color = "#4ade80" if score >= 7 else ("#fbbf24" if score >= 5 else "#f87171")
        rows += (
            f'<tr>'
            f'<td class="name-cell">{c.get("name","—")}</td>'
            f'<td class="meta-cell">{c.get("current_role","—")}</td>'
            f'<td><span style="font-size:18px;font-weight:800;color:{score_color}">{score}</span>'
            f'<span style="color:#64748b;font-size:11px">/10</span></td>'
            f'<td><div class="skill-list">{skills_html}</div></td>'
            f'<td class="reason-cell">{c.get("selection_reason","—")}</td>'
            f'</tr>'
        )

    return (
        '<table class="data-table">'
        '<thead><tr>'
        '<th>Name</th><th>Current Role</th><th>Score</th><th>Skills</th><th>Selection Reason</th>'
        '</tr></thead>'
        f'<tbody>{rows}</tbody>'
        '</table>'
    )


def _build_screening_table(results: list[dict]) -> str:
    if not results:
        return '<p style="color:#64748b;font-size:13px;padding:8px 0;">No pre-screening results found.</p>'

    rows = ""
    for r in results:
        looking = r.get("looking_for_change")
        looking_badge = badge("Yes", "green") if looking is True else (badge("No", "gray") if looking is False else badge("—", "gray"))
        exp = r.get("experience_years")
        exp_str = f"{exp} yrs" if exp else "—"
        rows += (
            f'<tr>'
            f'<td class="name-cell">{r.get("name","—")}</td>'
            f'<td>{looking_badge}</td>'
            f'<td class="reason-cell">{r.get("reason_for_change") or "—"}</td>'
            f'<td>{r.get("current_ctc") or "—"}</td>'
            f'<td>{r.get("expected_ctc") or "—"}</td>'
            f'<td>{"<br>".join(r.get("interview_slots") or []) or "—"}</td>'
            f'<td>{exp_str}</td>'
            f'<td>{_call_status_badge(r.get("call_status",""))}</td>'
            f'</tr>'
        )

    return (
        '<table class="data-table">'
        '<thead><tr>'
        '<th>Name</th><th>Looking for Change</th><th>Reason</th>'
        '<th>Current CTC</th><th>Expected CTC</th>'
        '<th>Interview Slots</th><th>Experience</th><th>Call Status</th>'
        '</tr></thead>'
        f'<tbody>{rows}</tbody>'
        '</table>'
    )


def _build_all_transcripts(calls: list[dict], results: list[dict]) -> str:
    if not calls:
        return '<div class="card"><p class="no-transcript">No call records found for this session.</p></div>'

    # Build name lookup from pre-screening results (candidate_id → name)
    name_by_candidate = {r.get("candidate_id", ""): r.get("name", "") for r in results}

    html = ""
    for call_doc in calls:
        cid = call_doc.get("candidate_id", "")
        name = name_by_candidate.get(cid) or call_doc.get("candidate_name") or cid or "Unknown Candidate"
        status = call_doc.get("status", "—")
        call_sid = call_doc.get("call_sid", "")
        turns = call_doc.get("conversation", [])

        status_b = _call_status_badge(status)
        turns_count = len(turns)

        if turns:
            convo_html = ""
            for turn in turns:
                role = turn.get("role", "")
                text = turn.get("text", "")
                who_class = "agent-who" if role == "agent" else "cand-who"
                who_label = "AI Agent" if role == "agent" else "Candidate"
                convo_html += (
                    f'<div class="turn">'
                    f'<div class="who {who_class}">{who_label}</div>'
                    f'<div class="txt">{text}</div>'
                    f'</div>'
                )
        else:
            convo_html = '<p class="no-transcript">No conversation recorded (call did not connect or was not answered).</p>'

        sid_short = f'<span style="color:#64748b;font-size:11px;font-weight:400">{call_sid[:16]}…</span>' if call_sid else ""
        html += (
            f'<div class="card cand-section" style="margin-bottom:16px;">'
            f'<div class="cand-section-header">'
            f'{name} &nbsp; {status_b} &nbsp; '
            f'<span style="color:#64748b;font-size:12px;font-weight:400">{turns_count} turns</span>'
            f'&nbsp; {sid_short}'
            f'</div>'
            f'<div class="convo">{convo_html}</div>'
            f'</div>'
        )

    return html


async def build_report(session_id: str) -> str:
    await connect()
    db = get_db()

    session = await db.sessions.find_one({"session_id": session_id})
    if not session:
        print(f"Session {session_id} not found")
        sys.exit(1)

    snap = session.get("state_snapshot", {})
    calls = await db.calls.find({"session_id": session_id}).to_list(100)

    # ── Status rows ──────────────────────────────────────────────────────
    step = snap.get("current_step", "—")
    sl_status = snap.get("shortlist_approval_status", "—")
    ps_status = snap.get("pre_screening_approval_status", "—")

    status_rows = (
        kv("Current Step", badge(step, "green" if "approved" in step else "blue")) +
        kv("Shortlist", badge(sl_status, "green" if sl_status == "approved" else "gray")) +
        kv("Pre-Screening", badge(ps_status, "green" if ps_status == "approved" else "gray")) +
        kv("Error", snap.get("error") or badge("None", "green"))
    )

    # ── Candidates table ─────────────────────────────────────────────────
    candidates = snap.get("shortlisted_candidates", [])
    candidates_table = _build_candidates_table(candidates)

    # ── Screening table ──────────────────────────────────────────────────
    results = snap.get("pre_screening_results", [])
    screening_table = _build_screening_table(results)

    # ── Timeline ─────────────────────────────────────────────────────────
    timeline_html = ""
    for h in snap.get("workflow_history", []):
        ts = h.get("timestamp", "")[:19].replace("T", " ")
        timeline_html += (
            f'<li><div class="ts">{ts}</div>'
            f'<div class="msg">{h.get("summary","")}</div></li>'
        )

    # ── All transcripts ───────────────────────────────────────────────────
    all_transcripts = _build_all_transcripts(calls, results)

    # ── Terminal Logs tab ─────────────────────────────────────────────────
    agent_metrics = snap.get("agent_metrics", [])
    tool_metrics  = snap.get("tool_metrics", [])

    total_tokens_in  = sum(m.get("tokens_in", 0)  for m in agent_metrics + tool_metrics)
    total_tokens_out = sum(m.get("tokens_out", 0) for m in agent_metrics + tool_metrics)
    total_latency    = sum(m.get("latency_ms", 0) for m in agent_metrics + tool_metrics)
    num_agents       = len(agent_metrics)

    metric_cards_html = (
        f'<div class="metric-card"><div class="m-name">Agents Run</div>'
        f'<div class="m-val">{num_agents}</div><div class="m-sub">nodes executed</div></div>'

        f'<div class="metric-card"><div class="m-name">Tokens In</div>'
        f'<div class="m-val">{total_tokens_in:,}</div><div class="m-sub">prompt tokens</div></div>'

        f'<div class="metric-card"><div class="m-name">Tokens Out</div>'
        f'<div class="m-val">{total_tokens_out:,}</div><div class="m-sub">completion tokens</div></div>'

        f'<div class="metric-card"><div class="m-name">Total Latency</div>'
        f'<div class="m-val">{total_latency/1000:.1f}s</div><div class="m-sub">agent processing time</div></div>'

        f'<div class="metric-card"><div class="m-name">Candidates</div>'
        f'<div class="m-val">{len(candidates)}</div><div class="m-sub">shortlisted</div></div>'

        f'<div class="metric-card"><div class="m-name">Calls</div>'
        f'<div class="m-val">{len(calls)}</div><div class="m-sub">placed</div></div>'
    )

    # ── Try to read real captured log file first ─────────────────────────
    log_file = Path("logs") / f"{session_id}.jsonl"
    terminal_html = ""

    if log_file.exists():
        print(f"Reading log file: {log_file} ({log_file.stat().st_size} bytes)")
        raw_lines = log_file.read_text().splitlines()
        for raw in raw_lines:
            if not raw.strip():
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                terminal_html += (
                    f'<div class="log-line">'
                    f'<span class="log-evt" style="color:#64748b">{raw}</span>'
                    f'</div>'
                )
                continue

            ts    = str(rec.pop("timestamp", ""))[:19]
            level = str(rec.pop("level", "info"))
            event = str(rec.pop("event", ""))
            rec.pop("logger", None)
            rec.pop("_logger", None)
            terminal_html += _log_line(ts, level, event, {k: str(v) for k, v in rec.items()})

    else:
        terminal_html += (
            '<div class="log-line" style="margin-bottom:12px;">'
            '<span class="log-evt" style="color:#fbbf24">'
            '⚠ No log file found for this session. '
            'Showing reconstructed events from MongoDB snapshot.'
            '</span></div>'
        )
        history = snap.get("workflow_history", [])
        log_events = []

        created_at = session.get("created_at") or (
            session.get("_id").generation_time.isoformat() if session.get("_id") else ""
        )
        log_events.append({"ts": str(created_at)[:19], "level": "info",  "event": "workflow_started",  "fields": {"session_id": session_id[:8] + "..."}})
        log_events.append({"ts": str(created_at)[:19], "level": "info",  "event": "mongodb_connected", "fields": {"db": "hr_workflow"}})

        for h in history:
            log_events.append({"ts": h.get("timestamp", "")[:19], "level": "info", "event": f'node_completed  step={h.get("step", "")}', "fields": {}})
            log_events.append({"ts": h.get("timestamp", "")[:19], "level": "info", "event": h.get("summary", ""),
                                "fields": {k: str(v) for k, v in h.items() if k not in ("step", "timestamp", "summary")}})

        for m in agent_metrics:
            log_events.append({"ts": m.get("timestamp", "")[:19], "level": "info", "event": f'agent_metric  name={m["name"]}',
                                "fields": {"latency_ms": f'{m.get("latency_ms",0):.0f}', "tokens_in": str(m.get("tokens_in",0)), "tokens_out": str(m.get("tokens_out",0))}})

        for call_doc in calls:
            log_events.append({"ts": "", "level": "info", "event": "outbound_call_initiated",
                                "fields": {"call_sid": call_doc.get("call_sid","")[:12]+"...",
                                           "to": call_doc.get("to_number",""),
                                           "candidate": call_doc.get("candidate_id",""),
                                           "status": call_doc.get("status","")}})
            for turn in call_doc.get("conversation", []):
                text = turn.get("text","")[:80] + ("..." if len(turn.get("text","")) > 80 else "")
                log_events.append({"ts": "", "level": "debug", "event": f'call_turn  role={turn.get("role","")}', "fields": {"text": f'"{text}"'}})
            log_events.append({"ts": "", "level": "info", "event": "call_completed",
                                "fields": {"duration_s": str(call_doc.get("duration_seconds","—")), "final_status": call_doc.get("status","")}})

        if sl_status:
            log_events.append({"ts": "", "level": "info", "event": "hitl_decision  gate=shortlist",
                                "fields": {"decision": sl_status, "feedback": snap.get("shortlist_approval_feedback","")}})
        if ps_status:
            log_events.append({"ts": "", "level": "info", "event": "hitl_decision  gate=pre_screening",
                                "fields": {"decision": ps_status, "feedback": snap.get("pre_screening_approval_feedback","")}})

        log_events.append({"ts": "", "level": "info", "event": "workflow_complete", "fields": {"final_step": snap.get("current_step","")}})

        for entry in log_events:
            terminal_html += _log_line(entry["ts"], entry["level"], entry["event"], entry["fields"])

    html = HTML_TEMPLATE.format(
        session_id=session_id,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status_rows=status_rows,
        candidate_count=len(candidates),
        candidates_table=candidates_table,
        screening_count=len(results),
        screening_table=screening_table,
        timeline_html=timeline_html,
        all_transcripts=all_transcripts,
        metric_cards_html=metric_cards_html,
        terminal_html=terminal_html,
    )

    return html


async def save_report(session_id: str) -> str:
    """Build the report and write it to disk. Returns the filename."""
    html = await build_report(session_id)
    out = f"run_log_{session_id[:8]}.html"
    with open(out, "w") as f:
        f.write(html)
    print(f"Report saved: {out}")
    return out


if __name__ == "__main__":
    if not SESSION_ID:
        print("Usage: python generate_report.py <session_id>")
        sys.exit(1)
    asyncio.run(save_report(SESSION_ID))
