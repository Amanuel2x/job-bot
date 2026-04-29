"""
Local web server — serves the control panel at http://localhost:5000
Run this once and leave it running. Open the browser, never touch the terminal again.
"""

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

BASE = Path(__file__).parent
MATCHES_FILE = BASE / "matches.json"
APPLIED_FILE = BASE / "applied.json"
QUEUE_FILE = BASE / "manual_queue.json"
PYTHON = sys.executable

# Tracks currently running bot process
_running_process = None
_running_lock = threading.Lock()
_log_lines = []


def _run_bot(args: list[str]):
    global _running_process, _log_lines
    _log_lines = []
    cmd = [PYTHON, str(BASE / "main.py")] + args
    with _running_lock:
        _running_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, cwd=str(BASE)
        )
    for line in _running_process.stdout:
        _log_lines.append(line.rstrip())
    _running_process.wait()
    with _running_lock:
        _running_process = None


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _stats() -> dict:
    applied = _load_json(APPLIED_FILE, {})
    matches = _load_json(MATCHES_FILE, [])
    by_status = {}
    for v in applied.values():
        s = v.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
    bay = sum(1 for j in matches if j.get("is_bay_area"))
    remote = sum(1 for j in matches if j.get("is_remote"))
    housing = sum(1 for j in matches if j.get("has_housing"))
    return {
        "total_applied": len(applied),
        "total_matches": len(matches),
        "by_status": by_status,
        "bay_area": bay,
        "remote": remote,
        "housing": housing,
    }


class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # Silence default request logging

    def _send(self, content: str, content_type: str = "text/html", code: int = 200):
        encoded = content.encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(encoded))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._send(render_dashboard())

        elif path == "/api/stats":
            self._send(json.dumps(_stats()), "application/json")

        elif path == "/api/matches":
            matches = _load_json(MATCHES_FILE, [])
            self._send(json.dumps(matches[:200]), "application/json")

        elif path == "/api/applied":
            applied = _load_json(APPLIED_FILE, {})
            items = list(applied.values())
            items.sort(key=lambda x: x.get("applied_at", ""), reverse=True)
            self._send(json.dumps(items[:200]), "application/json")

        elif path == "/api/logs":
            self._send(json.dumps(_log_lines[-100:]), "application/json")

        elif path == "/api/status":
            with _running_lock:
                running = _running_process is not None
            self._send(json.dumps({"running": running}), "application/json")

        elif path == "/api/run":
            qs = parse_qs(parsed.query)
            mode = qs.get("mode", ["full"])[0]
            with _running_lock:
                already_running = _running_process is not None
            if already_running:
                self._send(json.dumps({"error": "Bot is already running"}), "application/json", 409)
                return
            arg_map = {
                "full": [],
                "dry": ["--dry-run"],
                "scrape": ["--scrape-only"],
                "apply": ["--apply-only"],
                "email": ["--email-only"],
            }
            args = arg_map.get(mode, [])
            t = threading.Thread(target=_run_bot, args=(args,), daemon=True)
            t.start()
            self._send(json.dumps({"started": True, "mode": mode}), "application/json")

        elif path == "/api/stop":
            with _running_lock:
                if _running_process:
                    _running_process.terminate()
            self._send(json.dumps({"stopped": True}), "application/json")

        else:
            self._send("Not found", code=404)


def render_dashboard() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Job Bot</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f0f13; color: #e2e8f0; min-height: 100vh; }
  .header { background: #1a1a2e; border-bottom: 1px solid #2d2d44; padding: 20px 32px; display: flex; align-items: center; justify-content: space-between; }
  .header h1 { font-size: 20px; font-weight: 700; color: #a78bfa; }
  .header .status { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #94a3b8; }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: #374151; }
  .dot.running { background: #10b981; animation: pulse 1.5s infinite; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
  .container { max-width: 1100px; margin: 0 auto; padding: 32px 24px; }
  .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px; }
  .stat { background: #1a1a2e; border: 1px solid #2d2d44; border-radius: 12px; padding: 20px; text-align: center; }
  .stat .num { font-size: 36px; font-weight: 800; color: #a78bfa; }
  .stat .label { font-size: 12px; color: #64748b; margin-top: 6px; text-transform: uppercase; letter-spacing: 0.05em; }
  .actions { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 32px; }
  .btn { padding: 14px 20px; border-radius: 10px; border: none; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.15s; }
  .btn-primary { background: #7c3aed; color: white; }
  .btn-primary:hover { background: #6d28d9; }
  .btn-secondary { background: #1e293b; color: #94a3b8; border: 1px solid #2d2d44; }
  .btn-secondary:hover { background: #273548; color: #e2e8f0; }
  .btn-danger { background: #1e293b; color: #f87171; border: 1px solid #2d2d44; }
  .btn-danger:hover { background: #2d1515; }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .section { background: #1a1a2e; border: 1px solid #2d2d44; border-radius: 12px; margin-bottom: 24px; overflow: hidden; }
  .section-header { padding: 16px 20px; border-bottom: 1px solid #2d2d44; display: flex; align-items: center; justify-content: space-between; }
  .section-header h2 { font-size: 15px; font-weight: 600; color: #c4b5fd; }
  .table-wrap { overflow-x: auto; max-height: 400px; overflow-y: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { padding: 10px 16px; text-align: left; color: #64748b; font-weight: 500; border-bottom: 1px solid #2d2d44; position: sticky; top: 0; background: #1a1a2e; }
  td { padding: 10px 16px; border-bottom: 1px solid #1e2535; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: #1e2535; }
  .score { font-weight: 700; color: #a78bfa; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 500; }
  .badge-bay { background: #052e16; color: #4ade80; }
  .badge-remote { background: #0f172a; color: #60a5fa; }
  .badge-housing { background: #1c1500; color: #fbbf24; }
  .badge-applied { background: #1e1b4b; color: #a78bfa; }
  .log-box { background: #0d0d14; padding: 16px 20px; font-family: 'Courier New', monospace; font-size: 12px; color: #4ade80; max-height: 300px; overflow-y: auto; white-space: pre-wrap; }
  .log-box .err { color: #f87171; }
  a { color: #818cf8; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .empty { text-align: center; padding: 40px; color: #374151; font-size: 14px; }
  .tag-applied { color: #34d399; }
  .tag-dry_run { color: #94a3b8; }
  .tag-opened { color: #60a5fa; }
</style>
</head>
<body>

<div class="header">
  <h1>Job Bot</h1>
  <div class="status">
    <div class="dot" id="statusDot"></div>
    <span id="statusText">Idle</span>
  </div>
</div>

<div class="container">

  <div class="stats-grid">
    <div class="stat"><div class="num" id="statApplied">—</div><div class="label">Applied Total</div></div>
    <div class="stat"><div class="num" id="statMatches">—</div><div class="label">Current Matches</div></div>
    <div class="stat"><div class="num" id="statBay">—</div><div class="label">Bay Area</div></div>
    <div class="stat"><div class="num" id="statHousing">—</div><div class="label">Housing / Stipend</div></div>
  </div>

  <div class="actions">
    <button class="btn btn-primary" onclick="runBot('full')" id="btnFull">Run Full Bot</button>
    <button class="btn btn-secondary" onclick="runBot('scrape')" id="btnScrape">Scrape Only</button>
    <button class="btn btn-secondary" onclick="runBot('dry')" id="btnDry">Dry Run</button>
    <button class="btn btn-danger" onclick="stopBot()" id="btnStop">Stop</button>
  </div>

  <div class="section">
    <div class="section-header">
      <h2>Live Log</h2>
      <button class="btn btn-secondary" style="padding:6px 12px;font-size:12px;" onclick="clearLogs()">Clear</button>
    </div>
    <div class="log-box" id="logBox">Waiting for bot to run...</div>
  </div>

  <div class="section">
    <div class="section-header"><h2>Matched Jobs</h2></div>
    <div class="table-wrap">
      <table id="matchesTable">
        <thead><tr><th>#</th><th>Score</th><th>Company</th><th>Title</th><th>Location</th><th>Type</th><th>Link</th></tr></thead>
        <tbody id="matchesBody"><tr><td colspan="7" class="empty">Run the bot to load matches</td></tr></tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <div class="section-header"><h2>Applications Log</h2></div>
    <div class="table-wrap">
      <table id="appliedTable">
        <thead><tr><th>Company</th><th>Title</th><th>Score</th><th>Status</th><th>Applied At</th><th>Link</th></tr></thead>
        <tbody id="appliedBody"><tr><td colspan="6" class="empty">No applications yet</td></tr></tbody>
      </table>
    </div>
  </div>

</div>

<script>
let logInterval, statsInterval, statusInterval;
let isRunning = false;

function fmt(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
}

function badge(job) {
  let b = '';
  if (job.is_bay_area) b += '<span class="badge badge-bay">Bay Area</span> ';
  else if (job.is_remote) b += '<span class="badge badge-remote">Remote</span> ';
  if (job.has_housing) b += '<span class="badge badge-housing">Housing</span>';
  return b || '<span style="color:#374151">—</span>';
}

async function loadStats() {
  const r = await fetch('/api/stats');
  const d = await r.json();
  document.getElementById('statApplied').textContent = d.total_applied;
  document.getElementById('statMatches').textContent = d.total_matches;
  document.getElementById('statBay').textContent = d.bay_area;
  document.getElementById('statHousing').textContent = d.housing;
}

async function loadMatches() {
  const r = await fetch('/api/matches');
  const jobs = await r.json();
  const tbody = document.getElementById('matchesBody');
  if (!jobs.length) { tbody.innerHTML = '<tr><td colspan="7" class="empty">No matches yet</td></tr>'; return; }
  tbody.innerHTML = jobs.map((j, i) => `
    <tr>
      <td style="color:#4b5563">${i+1}</td>
      <td class="score">${j.match_score}</td>
      <td><strong>${j.company || ''}</strong></td>
      <td style="color:#94a3b8">${j.title || ''}</td>
      <td style="color:#64748b;font-size:12px">${(j.location||'').slice(0,25)}</td>
      <td>${badge(j)}</td>
      <td><a href="${j.url||'#'}" target="_blank">View</a></td>
    </tr>`).join('');
}

async function loadApplied() {
  const r = await fetch('/api/applied');
  const items = await r.json();
  const tbody = document.getElementById('appliedBody');
  if (!items.length) { tbody.innerHTML = '<tr><td colspan="6" class="empty">No applications yet</td></tr>'; return; }
  tbody.innerHTML = items.map(a => `
    <tr>
      <td><strong>${a.company||''}</strong></td>
      <td style="color:#94a3b8">${a.title||''}</td>
      <td class="score">${a.match_score||''}</td>
      <td><span class="tag-${a.status}">${a.status||''}</span></td>
      <td style="color:#4b5563;font-size:12px">${fmt(a.applied_at)}</td>
      <td><a href="${a.url||'#'}" target="_blank">View</a></td>
    </tr>`).join('');
}

async function loadLogs() {
  const r = await fetch('/api/logs');
  const lines = await r.json();
  const box = document.getElementById('logBox');
  if (!lines.length) return;
  box.innerHTML = lines.map(l =>
    l.toLowerCase().includes('error') || l.toLowerCase().includes('fail')
      ? `<span class="err">${l}</span>`
      : l
  ).join('\n');
  box.scrollTop = box.scrollHeight;
}

async function checkStatus() {
  const r = await fetch('/api/status');
  const d = await r.json();
  isRunning = d.running;
  const dot = document.getElementById('statusDot');
  const txt = document.getElementById('statusText');
  if (isRunning) {
    dot.className = 'dot running';
    txt.textContent = 'Running...';
  } else {
    dot.className = 'dot';
    txt.textContent = 'Idle';
  }
  ['btnFull','btnScrape','btnDry'].forEach(id => {
    document.getElementById(id).disabled = isRunning;
  });
}

async function runBot(mode) {
  const labels = { full: 'Run Full Bot', scrape: 'Scrape Only', dry: 'Dry Run' };
  const r = await fetch(`/api/run?mode=${mode}`);
  const d = await r.json();
  if (d.error) { alert(d.error); return; }
  document.getElementById('logBox').textContent = `Starting ${mode} run...\n`;
}

async function stopBot() {
  await fetch('/api/stop');
}

function clearLogs() {
  document.getElementById('logBox').textContent = '';
}

// Poll for updates
function startPolling() {
  loadStats(); loadMatches(); loadApplied(); loadLogs(); checkStatus();
  statsInterval = setInterval(() => { loadStats(); loadMatches(); loadApplied(); }, 5000);
  logInterval = setInterval(loadLogs, 1500);
  statusInterval = setInterval(checkStatus, 2000);
}

startPolling();
</script>
</body>
</html>"""


if __name__ == "__main__":
    port = 8765
    server = HTTPServer(("localhost", port), Handler)
    print(f"\n  Job Bot running at http://localhost:{port}")
    print("  Open that URL in your browser. Keep this window open.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
