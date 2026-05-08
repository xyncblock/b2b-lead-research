#!/usr/bin/env python3
"""
UK E-commerce Scraper — Live Dashboard
"""

import os, csv, json, glob, re
from datetime import datetime
from flask import Flask, jsonify, render_template_string

BASE_DIR = "/home/expertfox/.openclaw/workspace/uk_ecom_data"
app = Flask(__name__)

FIELDS = [
    "business_name","owner_name","email","phone","website","industry",
    "category","platform","city","google_location","facebook","instagram",
    "twitter","linkedin","tiktok","email_verified","source","found_at",
]

def read_all_stores(limit=None):
    stores = []
    for path in sorted(glob.glob(os.path.join(BASE_DIR, "uk_ecom_*.csv"))):
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stores.append(row)
        except:
            pass
    if limit:
        return stores[-limit:]
    return stores

def read_broken():
    path = os.path.join(BASE_DIR, "broken_sites.csv")
    broken = []
    if os.path.exists(path):
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    broken.append(row)
        except:
            pass
    return broken

def load_state():
    path = os.path.join(BASE_DIR, "state.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except:
            pass
    return {}

def count_by(stores, field):
    counts = {}
    for s in stores:
        val = s.get(field) or "Unknown"
        if val:
            counts[val] = counts.get(val, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1])[:10])

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🇬🇧 UK E-commerce Scraper Dashboard</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
  body { font-family: 'Inter', sans-serif; background: #0f172a; color: #e2e8f0; }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; }
  .pulse { animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }
  ::-webkit-scrollbar { width: 6px; } ::-webkit-scrollbar-track { background: #1e293b; }
  ::-webkit-scrollbar-thumb { background: #475569; border-radius: 3px; }
  .badge { display:inline-block; padding:2px 8px; border-radius:9999px; font-size:11px; font-weight:600; }
  .badge-green { background:#064e3b; color:#6ee7b7; }
  .badge-red   { background:#7f1d1d; color:#fca5a5; }
  .badge-blue  { background:#1e3a5f; color:#93c5fd; }
  .badge-gray  { background:#1f2937; color:#9ca3af; }
  tr:hover td { background: #263548 !important; }
</style>
</head>
<body class="min-h-screen">

<!-- Header -->
<div class="border-b border-slate-700 px-6 py-4 flex items-center justify-between">
  <div class="flex items-center gap-3">
    <span class="text-2xl">🇬🇧</span>
    <div>
      <h1 class="text-xl font-bold text-white">UK E-commerce Store Finder</h1>
      <p class="text-sm text-slate-400">Live scraper dashboard — auto-refreshes every 30s</p>
    </div>
  </div>
  <div class="flex items-center gap-2">
    <span class="pulse w-2 h-2 rounded-full bg-green-400 inline-block"></span>
    <span class="text-green-400 text-sm font-medium">Live</span>
    <span class="text-slate-500 text-sm ml-3" id="lastUpdate">—</span>
  </div>
</div>

<!-- Stat Cards -->
<div class="grid grid-cols-2 md:grid-cols-4 gap-4 p-6" id="statCards">
  <div class="card text-center"><div class="text-3xl font-bold text-blue-400" id="statTotal">—</div><div class="text-slate-400 text-sm mt-1">Stores Found</div></div>
  <div class="card text-center"><div class="text-3xl font-bold text-purple-400" id="statBatch">—</div><div class="text-slate-400 text-sm mt-1">Current Batch</div></div>
  <div class="card text-center"><div class="text-3xl font-bold text-green-400" id="statVerified">—</div><div class="text-slate-400 text-sm mt-1">Email Verified</div></div>
  <div class="card text-center"><div class="text-3xl font-bold text-red-400" id="statBroken">—</div><div class="text-slate-400 text-sm mt-1">Broken Sites</div></div>
</div>

<!-- Charts Row -->
<div class="grid grid-cols-1 md:grid-cols-3 gap-4 px-6 pb-6">
  <div class="card">
    <h3 class="text-sm font-semibold text-slate-300 mb-4 uppercase tracking-wider">By Industry</h3>
    <canvas id="chartIndustry" height="220"></canvas>
  </div>
  <div class="card">
    <h3 class="text-sm font-semibold text-slate-300 mb-4 uppercase tracking-wider">By Platform</h3>
    <canvas id="chartPlatform" height="220"></canvas>
  </div>
  <div class="card">
    <h3 class="text-sm font-semibold text-slate-300 mb-4 uppercase tracking-wider">By City</h3>
    <canvas id="chartCity" height="220"></canvas>
  </div>
</div>

<!-- Batch Progress -->
<div class="px-6 pb-6">
  <div class="card">
    <div class="flex justify-between items-center mb-3">
      <h3 class="text-sm font-semibold text-slate-300 uppercase tracking-wider">Batch Progress</h3>
      <span class="text-slate-400 text-sm" id="batchLabel">—</span>
    </div>
    <div class="w-full bg-slate-700 rounded-full h-3">
      <div id="batchBar" class="bg-gradient-to-r from-blue-500 to-purple-500 h-3 rounded-full transition-all duration-500" style="width:0%"></div>
    </div>
  </div>
</div>

<!-- Recent Stores Table -->
<div class="px-6 pb-6">
  <div class="card overflow-x-auto">
    <div class="flex justify-between items-center mb-4">
      <h3 class="text-sm font-semibold text-slate-300 uppercase tracking-wider">Recent Stores</h3>
      <span class="text-slate-500 text-xs">Latest 100</span>
    </div>
    <table class="w-full text-sm">
      <thead>
        <tr class="text-left border-b border-slate-700">
          <th class="pb-2 text-slate-400 font-medium pr-4">Business</th>
          <th class="pb-2 text-slate-400 font-medium pr-4">Website</th>
          <th class="pb-2 text-slate-400 font-medium pr-4">Email</th>
          <th class="pb-2 text-slate-400 font-medium pr-4">City</th>
          <th class="pb-2 text-slate-400 font-medium pr-4">Platform</th>
          <th class="pb-2 text-slate-400 font-medium pr-4">Industry</th>
          <th class="pb-2 text-slate-400 font-medium">Verified</th>
        </tr>
      </thead>
      <tbody id="storeTable">
        <tr><td colspan="7" class="py-8 text-center text-slate-500">Loading...</td></tr>
      </tbody>
    </table>
  </div>
</div>

<!-- Broken Sites -->
<div class="px-6 pb-10">
  <div class="card overflow-x-auto">
    <div class="flex justify-between items-center mb-4">
      <h3 class="text-sm font-semibold text-red-400 uppercase tracking-wider">⚠ Broken / Unreachable Sites</h3>
      <span class="text-slate-500 text-xs">Latest 30</span>
    </div>
    <table class="w-full text-sm">
      <thead>
        <tr class="text-left border-b border-slate-700">
          <th class="pb-2 text-slate-400 font-medium pr-4">URL</th>
          <th class="pb-2 text-slate-400 font-medium pr-4">Reason</th>
          <th class="pb-2 text-slate-400 font-medium">Found At</th>
        </tr>
      </thead>
      <tbody id="brokenTable">
        <tr><td colspan="3" class="py-4 text-center text-slate-500">No broken sites yet</td></tr>
      </tbody>
    </table>
  </div>
</div>

<script>
let industryChart, platformChart, cityChart;

const COLORS = ['#60a5fa','#a78bfa','#34d399','#fb923c','#f87171','#facc15','#38bdf8','#e879f9','#4ade80','#ff6b6b'];

function makeChart(id, labels, data) {
  const ctx = document.getElementById(id).getContext('2d');
  return new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{ data, backgroundColor: COLORS, borderWidth: 0 }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 11 }, boxWidth: 12, padding: 8 } }
      }
    }
  });
}

function updateChart(chart, labels, data) {
  chart.data.labels = labels;
  chart.data.datasets[0].data = data;
  chart.update();
}

async function refresh() {
  try {
    const [stats, stores, broken] = await Promise.all([
      fetch('/api/stats').then(r=>r.json()),
      fetch('/api/stores?limit=100').then(r=>r.json()),
      fetch('/api/broken?limit=30').then(r=>r.json()),
    ]);

    // Stat cards
    document.getElementById('statTotal').textContent    = stats.total.toLocaleString();
    document.getElementById('statBatch').textContent    = '#' + stats.batch;
    document.getElementById('statVerified').textContent = stats.email_verified;
    document.getElementById('statBroken').textContent   = stats.broken_count;
    document.getElementById('lastUpdate').textContent   = 'Updated ' + new Date().toLocaleTimeString();

    // Batch progress bar
    const pct = Math.round((stats.batch_count / 500) * 100);
    document.getElementById('batchBar').style.width = pct + '%';
    document.getElementById('batchLabel').textContent = stats.batch_count + ' / 500 stores';

    // Charts
    const iLabels = Object.keys(stats.by_industry), iData = Object.values(stats.by_industry);
    const pLabels = Object.keys(stats.by_platform), pData = Object.values(stats.by_platform);
    const cLabels = Object.keys(stats.by_city),     cData = Object.values(stats.by_city);

    if (!industryChart) { industryChart = makeChart('chartIndustry', iLabels, iData); }
    else updateChart(industryChart, iLabels, iData);
    if (!platformChart) { platformChart = makeChart('chartPlatform', pLabels, pData); }
    else updateChart(platformChart, pLabels, pData);
    if (!cityChart)     { cityChart     = makeChart('chartCity',     cLabels, cData); }
    else updateChart(cityChart,     cLabels, cData);

    // Store table
    const tbody = document.getElementById('storeTable');
    if (stores.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="py-8 text-center text-slate-500">Scraper is warming up — stores will appear shortly...</td></tr>';
    } else {
      tbody.innerHTML = [...stores].reverse().map(s => `
        <tr>
          <td class="py-2 pr-4 font-medium text-white">${esc(s.business_name||'—')}</td>
          <td class="py-2 pr-4"><a href="${esc(s.website)}" target="_blank" class="text-blue-400 hover:underline truncate block max-w-xs">${esc((s.website||'').replace(/^https?:\/\//,''))}</a></td>
          <td class="py-2 pr-4 text-slate-300 text-xs">${esc(s.email||'—')}</td>
          <td class="py-2 pr-4 text-slate-400">${esc(s.city||'—')}</td>
          <td class="py-2 pr-4"><span class="badge badge-blue">${esc(s.platform||'—')}</span></td>
          <td class="py-2 pr-4 text-slate-400 text-xs">${esc(s.industry||'—')}</td>
          <td class="py-2">${s.email_verified==='Yes' ? '<span class="badge badge-green">✓ Yes</span>' : '<span class="badge badge-gray">No</span>'}</td>
        </tr>`).join('');
    }

    // Broken table
    const btbody = document.getElementById('brokenTable');
    if (broken.length === 0) {
      btbody.innerHTML = '<tr><td colspan="3" class="py-4 text-center text-slate-500">No broken sites logged yet</td></tr>';
    } else {
      btbody.innerHTML = [...broken].reverse().map(b => `
        <tr>
          <td class="py-2 pr-4 text-xs text-slate-400">${esc(b.url||'')}</td>
          <td class="py-2 pr-4"><span class="badge badge-red">${esc(b.reason||'')}</span></td>
          <td class="py-2 text-slate-500 text-xs">${esc(b.found_at||'')}</td>
        </tr>`).join('');
    }

  } catch(e) { console.error('Refresh error:', e); }
}

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

refresh();
setInterval(refresh, 30000);
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/stats")
def api_stats():
    stores = read_all_stores()
    state  = load_state()
    broken = read_broken()
    verified = sum(1 for s in stores if s.get("email_verified") == "Yes")
    return jsonify({
        "total":        len(stores),
        "batch":        state.get("batch", 1),
        "batch_count":  state.get("batch_count", 0),
        "email_verified": verified,
        "broken_count": len(broken),
        "by_industry":  count_by(stores, "industry"),
        "by_platform":  count_by(stores, "platform"),
        "by_city":      count_by(stores, "city"),
    })

@app.route("/api/stores")
def api_stores():
    from flask import request
    limit = int(request.args.get("limit", 100))
    stores = read_all_stores(limit=limit)
    return jsonify(stores)

@app.route("/api/broken")
def api_broken():
    from flask import request
    limit = int(request.args.get("limit", 30))
    broken = read_broken()
    return jsonify(broken[-limit:])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
