#!/usr/bin/env python3
"""Export the visual casebook as a portable offline HTML reviewer."""

from __future__ import annotations

import argparse
import csv
import html
import json
import zipfile
from pathlib import Path


LABELS = ["clean", "late", "noisy", "untradable", "ignore"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--casebook-dir", default="outputs/casebook")
    parser.add_argument("--output-html", default="outputs/casebook/offline_reviewer.html")
    parser.add_argument("--zip", dest="zip_path", default="outputs/casebook/offline_reviewer.zip")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    casebook_dir = Path(args.casebook_dir)
    output_html = Path(args.output_html)
    manifest_path = casebook_dir / "casebook_manifest.csv"
    if not manifest_path.exists():
        raise FileNotFoundError(f"missing manifest: {manifest_path}")

    items = load_items(casebook_dir, manifest_path)
    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(render_html(items), encoding="utf-8")

    zip_path = Path(args.zip_path)
    if zip_path:
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(output_html, arcname=output_html.name)
        print(f"Wrote {output_html} and {zip_path} with {len(items)} examples")
    else:
        print(f"Wrote {output_html} with {len(items)} examples")
    return 0


def load_items(casebook_dir: Path, manifest_path: Path) -> list[dict[str, str]]:
    with manifest_path.open(newline="", encoding="utf-8") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    items = []
    for row in rows:
        svg_path = casebook_dir / row["chart_path"]
        if not svg_path.exists():
            raise FileNotFoundError(f"missing chart: {svg_path}")
        item = dict(row)
        item["svg"] = svg_path.read_text(encoding="utf-8")
        items.append(item)
    return items


def render_html(items: list[dict[str, str]]) -> str:
    payload = json.dumps(items, ensure_ascii=False)
    labels = json.dumps(LABELS)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Offline Box Casebook Reviewer</title>
  <style>
    :root {{
      --bg: #f8fafc;
      --panel: #fff;
      --ink: #0f172a;
      --muted: #64748b;
      --line: #dbe4ef;
      --accent: #2563eb;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
      letter-spacing: 0;
    }}
    .app {{
      display: grid;
      grid-template-columns: 360px minmax(0, 1fr);
      min-height: 100vh;
    }}
    aside {{
      background: var(--panel);
      border-right: 1px solid var(--line);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }}
    header, .filters {{
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 18px;
      line-height: 1.2;
    }}
    .stats, .item-meta, .hint {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
    }}
    .filters {{
      display: grid;
      gap: 8px;
    }}
    select, input, textarea {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      font: inherit;
      background: #fff;
    }}
    .list {{
      overflow: auto;
      padding: 8px;
      flex: 1;
    }}
    .item {{
      display: grid;
      gap: 5px;
      padding: 10px;
      border-radius: 8px;
      border: 1px solid transparent;
      cursor: pointer;
    }}
    .item:hover {{ background: #f1f5f9; }}
    .item.active {{
      border-color: var(--accent);
      background: #eff6ff;
    }}
    .item-title {{
      font-size: 13px;
      font-weight: 700;
      overflow-wrap: anywhere;
    }}
    .pill {{
      width: fit-content;
      border-radius: 999px;
      padding: 2px 7px;
      font-size: 11px;
      font-weight: 700;
      background: #e2e8f0;
      color: #334155;
    }}
    .pill.clean {{ background: #dcfce7; color: #166534; }}
    .pill.late {{ background: #fef3c7; color: #92400e; }}
    .pill.noisy {{ background: #ffedd5; color: #9a3412; }}
    .pill.untradable {{ background: #fee2e2; color: #991b1b; }}
    .pill.ignore {{ background: #e5e7eb; color: #374151; }}
    main {{
      min-width: 0;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      min-height: 100vh;
    }}
    .topbar {{
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      padding: 14px 18px;
      display: flex;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
    }}
    .context {{ min-width: 0; }}
    .context strong {{
      display: block;
      font-size: 16px;
      overflow-wrap: anywhere;
    }}
    .context span {{
      color: var(--muted);
      font-size: 13px;
    }}
    .nav, .label-buttons {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    button {{
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      min-height: 36px;
      padding: 8px 10px;
      font-weight: 700;
      cursor: pointer;
    }}
    button:hover {{ border-color: var(--accent); }}
    button.primary {{
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
    }}
    button.active {{
      outline: 2px solid var(--accent);
      outline-offset: 1px;
    }}
    .chart-wrap {{
      overflow: auto;
      padding: 18px;
    }}
    .chart-box {{
      width: 100%;
      max-width: 1320px;
      min-width: 760px;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .chart-box svg {{
      width: 100%;
      height: auto;
      display: block;
      border-radius: 8px;
    }}
    .review {{
      background: var(--panel);
      border-top: 1px solid var(--line);
      padding: 14px 18px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 280px;
      gap: 14px;
    }}
    textarea {{
      margin-top: 10px;
      min-height: 72px;
      resize: vertical;
    }}
    .summary {{
      color: var(--muted);
      font-size: 13px;
      display: grid;
      gap: 4px;
    }}
    @media (max-width: 900px) {{
      .app {{ grid-template-columns: 1fr; }}
      aside {{ min-height: 42vh; border-right: 0; border-bottom: 1px solid var(--line); }}
      .review {{ grid-template-columns: 1fr; }}
      .chart-box {{ min-width: 680px; }}
    }}
  </style>
</head>
<body>
<div class="app">
  <aside>
    <header>
      <h1>Offline Box Casebook</h1>
      <div class="stats" id="stats"></div>
      <div class="hint">Reviews are stored in this browser. Use Download CSV when done.</div>
    </header>
    <div class="filters">
      <select id="patternFilter"></select>
      <select id="reviewFilter">
        <option value="all">All review states</option>
        <option value="unreviewed">Unreviewed only</option>
        <option value="reviewed">Reviewed only</option>
      </select>
      <input id="search" placeholder="Search symbol, date, label">
    </div>
    <div class="list" id="list"></div>
  </aside>
  <main>
    <div class="topbar">
      <div class="context">
        <strong id="title">Loading...</strong>
        <span id="subtitle"></span>
      </div>
      <div class="nav">
        <button id="prevBtn">Prev</button>
        <button id="nextBtn">Next</button>
        <button class="primary" id="downloadBtn">Download CSV</button>
      </div>
    </div>
    <div class="chart-wrap">
      <div class="chart-box" id="chart"></div>
    </div>
    <div class="review">
      <div>
        <div class="label-buttons" id="labelButtons"></div>
        <textarea id="notes" placeholder="Optional note: late, choppy, clear reclaim, not usable on phone..."></textarea>
      </div>
      <div class="summary" id="summary"></div>
    </div>
  </main>
</div>
<script>
const RAW_ITEMS = {payload};
const LABELS = {labels};
const STORAGE_KEY = 'box_casebook_reviews_v1';
let items = RAW_ITEMS.map(item => ({{...item, manual_label: '', notes: '', reviewed_at_local: ''}}));
let filtered = [];
let index = 0;

const els = {{
  stats: document.getElementById('stats'),
  patternFilter: document.getElementById('patternFilter'),
  reviewFilter: document.getElementById('reviewFilter'),
  search: document.getElementById('search'),
  list: document.getElementById('list'),
  title: document.getElementById('title'),
  subtitle: document.getElementById('subtitle'),
  chart: document.getElementById('chart'),
  prevBtn: document.getElementById('prevBtn'),
  nextBtn: document.getElementById('nextBtn'),
  downloadBtn: document.getElementById('downloadBtn'),
  labelButtons: document.getElementById('labelButtons'),
  notes: document.getElementById('notes'),
  summary: document.getElementById('summary'),
}};

function key(item) {{
  return item.event_id + '|' + item.chart_path;
}}

function loadReviews() {{
  const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{}}');
  items = items.map(item => Object.assign(item, saved[key(item)] || {{}}));
}}

function saveReviews() {{
  const saved = {{}};
  for (const item of items) {{
    if (item.manual_label || item.notes) {{
      saved[key(item)] = {{
        manual_label: item.manual_label || '',
        notes: item.notes || '',
        reviewed_at_local: item.reviewed_at_local || '',
      }};
    }}
  }}
  localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
}}

function escapeHtml(value) {{
  return String(value ?? '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
}}

function itemText(item) {{
  return [
    item.symbol, item.timestamp_close, item.pattern, item.pattern_label,
    item.classification, item.manual_label, item.direction, item.session_bucket
  ].join(' ').toLowerCase();
}}

function setPatterns() {{
  const patterns = [...new Set(items.map(item => item.pattern))];
  els.patternFilter.innerHTML = '<option value="all">All patterns</option>' +
    patterns.map(p => `<option value="${{escapeHtml(p)}}">${{escapeHtml(p)}}</option>`).join('');
}}

function applyFilters(keepCurrent = false) {{
  const current = filtered[index];
  const pattern = els.patternFilter.value;
  const review = els.reviewFilter.value;
  const q = els.search.value.trim().toLowerCase();
  filtered = items.filter(item => {{
    if (pattern !== 'all' && item.pattern !== pattern) return false;
    if (review === 'reviewed' && !item.manual_label) return false;
    if (review === 'unreviewed' && item.manual_label) return false;
    if (q && !itemText(item).includes(q)) return false;
    return true;
  }});
  if (keepCurrent && current) {{
    const nextIndex = filtered.findIndex(item => key(item) === key(current));
    index = nextIndex >= 0 ? nextIndex : 0;
  }} else {{
    index = Math.min(index, Math.max(filtered.length - 1, 0));
  }}
  render();
}}

function render() {{
  renderStats();
  renderList();
  renderCurrent();
  renderSummary();
}}

function renderStats() {{
  const reviewed = items.filter(item => item.manual_label).length;
  els.stats.innerHTML = `<div>${{reviewed}} / ${{items.length}} reviewed</div><div>${{filtered.length}} visible</div>`;
}}

function renderList() {{
  els.list.innerHTML = filtered.map((item, i) => `
    <div class="item ${{i === index ? 'active' : ''}}" data-index="${{i}}">
      <div class="item-title">${{escapeHtml(item.symbol)}} ${{escapeHtml(item.timestamp_close)}}</div>
      <div class="item-meta">${{escapeHtml(item.pattern_label)}}</div>
      <div class="item-meta">auto=${{escapeHtml(item.classification)}} · streak=${{escapeHtml(item.streak_length)}} · ${{escapeHtml(item.session_bucket)}}</div>
      <span class="pill ${{escapeHtml(item.manual_label || '')}}">${{escapeHtml(item.manual_label || 'unreviewed')}}</span>
    </div>
  `).join('');
  [...els.list.querySelectorAll('.item')].forEach(node => {{
    node.addEventListener('click', () => {{
      index = Number(node.dataset.index);
      render();
    }});
  }});
  const active = els.list.querySelector('.item.active');
  if (active) active.scrollIntoView({{block: 'nearest'}});
}}

function renderCurrent() {{
  const item = filtered[index];
  if (!item) {{
    els.title.textContent = 'No matching examples';
    els.subtitle.textContent = '';
    els.chart.innerHTML = '';
    els.labelButtons.innerHTML = '';
    els.notes.value = '';
    return;
  }}
  els.title.textContent = `${{item.symbol}} ${{item.timestamp_close}}`;
  els.subtitle.textContent = `${{item.pattern_label}} · auto=${{item.classification}} · event=${{item.event_id}}`;
  els.chart.innerHTML = item.svg;
  els.notes.value = item.notes || '';
  els.labelButtons.innerHTML = LABELS.map((label, i) => `
    <button class="${{item.manual_label === label ? 'active' : ''}}" data-label="${{label}}">${{i + 1}} ${{label}}</button>
  `).join('');
  [...els.labelButtons.querySelectorAll('button')].forEach(button => {{
    button.addEventListener('click', () => saveReview(button.dataset.label));
  }});
}}

function renderSummary() {{
  const byLabel = Object.fromEntries(LABELS.map(label => [label, 0]));
  for (const item of items) {{
    if (item.manual_label && byLabel[item.manual_label] !== undefined) byLabel[item.manual_label] += 1;
  }}
  els.summary.innerHTML = [
    '<strong>Manual review summary</strong>',
    ...LABELS.map(label => `<span>${{label}}: ${{byLabel[label]}}</span>`),
    '<span>Shortcuts: 1-5 labels, n/p navigation.</span>'
  ].join('');
}}

function saveReview(label) {{
  const item = filtered[index];
  if (!item) return;
  item.manual_label = label;
  item.notes = els.notes.value;
  item.reviewed_at_local = new Date().toISOString();
  saveReviews();
  applyFilters(true);
  if (index < filtered.length - 1) index += 1;
  render();
}}

function move(delta) {{
  if (!filtered.length) return;
  index = Math.max(0, Math.min(filtered.length - 1, index + delta));
  render();
}}

function csvCell(value) {{
  return '"' + String(value ?? '').replaceAll('"', '""') + '"';
}}

function downloadCsv() {{
  const rows = [['event_id', 'chart_path', 'manual_label', 'notes', 'reviewed_at_local']];
  for (const item of items) {{
    if (item.manual_label || item.notes) {{
      rows.push([item.event_id, item.chart_path, item.manual_label, item.notes, item.reviewed_at_local]);
    }}
  }}
  const csv = rows.map(row => row.map(csvCell).join(',')).join('\\n') + '\\n';
  const blob = new Blob([csv], {{type: 'text/csv'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'manual_review.csv';
  a.click();
  URL.revokeObjectURL(a.href);
}}

function boot() {{
  loadReviews();
  setPatterns();
  applyFilters();
}}

els.patternFilter.addEventListener('change', () => applyFilters());
els.reviewFilter.addEventListener('change', () => applyFilters());
els.search.addEventListener('input', () => applyFilters());
els.prevBtn.addEventListener('click', () => move(-1));
els.nextBtn.addEventListener('click', () => move(1));
els.downloadBtn.addEventListener('click', downloadCsv);
document.addEventListener('keydown', event => {{
  if (event.target === els.notes) return;
  if (event.key === 'n' || event.key === 'ArrowRight') move(1);
  if (event.key === 'p' || event.key === 'ArrowLeft') move(-1);
  const number = Number(event.key);
  if (number >= 1 && number <= LABELS.length) saveReview(LABELS[number - 1]);
}});
boot();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
