#!/usr/bin/env python3
"""Serve a local browser reviewer for visual casebook SVGs.

This is a manual research-review tool. It writes labels and notes to
``outputs/casebook/manual_review.csv`` and does not compute entries, exits, or
PnL.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


REVIEW_LABELS = ["clean", "late", "noisy", "untradable", "ignore"]
REVIEW_FIELDS = [
    "event_id",
    "chart_path",
    "manual_label",
    "notes",
    "reviewed_at_utc",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--casebook-dir", default="outputs/casebook")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    casebook_dir = Path(args.casebook_dir).resolve()
    manifest_path = casebook_dir / "casebook_manifest.csv"
    if not manifest_path.exists():
        raise FileNotFoundError(f"missing manifest: {manifest_path}")

    handler = make_handler(casebook_dir)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}"
    print(f"Serving casebook reviewer at {url}")
    print(f"Writing reviews to {casebook_dir / 'manual_review.csv'}")
    server.serve_forever()
    return 0


def make_handler(casebook_dir: Path) -> type[BaseHTTPRequestHandler]:
    class CasebookHandler(BaseHTTPRequestHandler):
        server_version = "CasebookReviewer/1.0"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self.send_html(reviewer_html())
                return
            if parsed.path == "/api/items":
                self.send_json(load_items(casebook_dir))
                return
            if parsed.path == "/api/reviews.csv":
                self.send_file(casebook_dir / "manual_review.csv", fallback_text="")
                return
            self.send_static(casebook_dir, parsed.path)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/api/review":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                saved = upsert_review(casebook_dir / "manual_review.csv", payload)
            except ValueError as exc:
                self.send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self.send_json(saved)

        def log_message(self, fmt: str, *args: object) -> None:
            return

        def send_json(self, payload: Any) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_html(self, body: str) -> None:
            data = body.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def send_file(self, path: Path, fallback_text: str | None = None) -> None:
            if not path.exists():
                if fallback_text is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                data = fallback_text.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            data = path.read_bytes()
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def send_static(self, root: Path, request_path: str) -> None:
            rel = unquote(request_path).lstrip("/")
            path = (root / rel).resolve()
            if not is_inside(path, root) or not path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self.send_file(path)

    return CasebookHandler


def load_items(casebook_dir: Path) -> list[dict[str, str]]:
    manifest = read_csv(casebook_dir / "casebook_manifest.csv")
    reviews = {review_key(row): row for row in read_csv(casebook_dir / "manual_review.csv")}
    items = []
    for row in manifest:
        review = reviews.get(review_key(row), {})
        item = dict(row)
        item["manual_label"] = review.get("manual_label", "")
        item["notes"] = review.get("notes", "")
        item["reviewed_at_utc"] = review.get("reviewed_at_utc", "")
        items.append(item)
    return items


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def upsert_review(review_path: Path, payload: dict[str, object]) -> dict[str, str]:
    event_id = str(payload.get("event_id", "")).strip()
    chart_path = str(payload.get("chart_path", "")).strip()
    label = str(payload.get("manual_label", "")).strip()
    notes = str(payload.get("notes", "")).strip()
    if not event_id or not chart_path:
        raise ValueError("event_id and chart_path are required")
    if label not in REVIEW_LABELS:
        raise ValueError(f"manual_label must be one of: {', '.join(REVIEW_LABELS)}")

    saved = {
        "event_id": event_id,
        "chart_path": chart_path,
        "manual_label": label,
        "notes": notes,
        "reviewed_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
    }
    rows = read_csv(review_path)
    rows_by_key = {review_key(row): row for row in rows}
    rows_by_key[review_key(saved)] = saved
    ordered = sorted(rows_by_key.values(), key=lambda row: (row.get("chart_path", ""), row.get("event_id", "")))

    review_path.parent.mkdir(parents=True, exist_ok=True)
    with review_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in REVIEW_FIELDS} for row in ordered)
    return saved


def review_key(row: dict[str, object]) -> tuple[str, str]:
    return (str(row.get("event_id", "")), str(row.get("chart_path", "")))


def is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def reviewer_html() -> str:
    labels = json.dumps(REVIEW_LABELS)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Box Casebook Reviewer</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f8fafc;
      --panel: #ffffff;
      --ink: #0f172a;
      --muted: #64748b;
      --line: #dbe4ef;
      --accent: #2563eb;
      --good: #15803d;
      --warn: #b45309;
      --bad: #b91c1c;
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
      border-right: 1px solid var(--line);
      background: var(--panel);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }}
    header {{
      padding: 16px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{
      font-size: 18px;
      line-height: 1.2;
      margin: 0 0 10px;
    }}
    .stats {{
      color: var(--muted);
      font-size: 13px;
      display: grid;
      gap: 3px;
    }}
    .filters {{
      padding: 12px 16px;
      display: grid;
      gap: 8px;
      border-bottom: 1px solid var(--line);
    }}
    select, input, textarea {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      font: inherit;
      padding: 8px 10px;
    }}
    .list {{
      overflow: auto;
      padding: 8px;
      flex: 1;
    }}
    .item {{
      border: 1px solid transparent;
      border-radius: 8px;
      padding: 10px;
      cursor: pointer;
      display: grid;
      gap: 5px;
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
    .item-meta {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 2px 7px;
      font-size: 11px;
      font-weight: 700;
      background: #e2e8f0;
      color: #334155;
      width: fit-content;
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
      padding: 14px 18px;
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }}
    .context {{
      min-width: 0;
    }}
    .context strong {{
      display: block;
      font-size: 16px;
      overflow-wrap: anywhere;
    }}
    .context span {{
      color: var(--muted);
      font-size: 13px;
    }}
    .nav {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    button {{
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      font-weight: 700;
      padding: 8px 10px;
      cursor: pointer;
      min-height: 36px;
    }}
    button:hover {{ border-color: var(--accent); }}
    button.primary {{
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }}
    .chart-wrap {{
      overflow: auto;
      padding: 18px;
    }}
    .chart {{
      width: 100%;
      max-width: 1320px;
      min-width: 760px;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
      display: block;
    }}
    .review {{
      background: var(--panel);
      border-top: 1px solid var(--line);
      padding: 14px 18px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 260px;
      gap: 14px;
      align-items: start;
    }}
    .label-buttons {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 10px;
    }}
    .label-buttons button.active {{
      outline: 2px solid var(--accent);
      outline-offset: 1px;
    }}
    textarea {{
      min-height: 72px;
      resize: vertical;
    }}
    .summary {{
      font-size: 13px;
      color: var(--muted);
      display: grid;
      gap: 4px;
    }}
    @media (max-width: 900px) {{
      .app {{ grid-template-columns: 1fr; }}
      aside {{ min-height: 42vh; border-right: 0; border-bottom: 1px solid var(--line); }}
      .review {{ grid-template-columns: 1fr; }}
      .chart {{ min-width: 680px; }}
    }}
  </style>
</head>
<body>
  <div class="app">
    <aside>
      <header>
        <h1>Box Casebook Reviewer</h1>
        <div class="stats" id="stats"></div>
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
          <button id="csvBtn">Reviews CSV</button>
        </div>
      </div>
      <div class="chart-wrap">
        <img class="chart" id="chart" alt="Casebook chart">
      </div>
      <div class="review">
        <div>
          <div class="label-buttons" id="labelButtons"></div>
          <textarea id="notes" placeholder="Optional note: late, too choppy, clear reclaim, untradeable open noise..."></textarea>
        </div>
        <div class="summary" id="summary"></div>
      </div>
    </main>
  </div>
<script>
const LABELS = {labels};
let items = [];
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
  csvBtn: document.getElementById('csvBtn'),
  labelButtons: document.getElementById('labelButtons'),
  notes: document.getElementById('notes'),
  summary: document.getElementById('summary'),
}};

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
    const nextIndex = filtered.findIndex(item => item.event_id === current.event_id && item.chart_path === current.chart_path);
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
  els.stats.innerHTML = `
    <div>${{reviewed}} / ${{items.length}} reviewed</div>
    <div>${{filtered.length}} visible</div>
  `;
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
    els.chart.removeAttribute('src');
    els.labelButtons.innerHTML = '';
    els.notes.value = '';
    return;
  }}
  els.title.textContent = `${{item.symbol}} ${{item.timestamp_close}}`;
  els.subtitle.textContent = `${{item.pattern_label}} · auto=${{item.classification}} · event=${{item.event_id}}`;
  els.chart.src = encodeURI(item.chart_path);
  els.notes.value = item.notes || '';
  els.labelButtons.innerHTML = LABELS.map((label, i) => `
    <button class="${{item.manual_label === label ? 'active' : ''}}" data-label="${{label}}">
      ${{i + 1}} ${{label}}
    </button>
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

async function saveReview(label) {{
  const item = filtered[index];
  if (!item) return;
  const response = await fetch('/api/review', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{
      event_id: item.event_id,
      chart_path: item.chart_path,
      manual_label: label,
      notes: els.notes.value,
    }}),
  }});
  if (!response.ok) {{
    alert(await response.text());
    return;
  }}
  const saved = await response.json();
  const fullIndex = items.findIndex(row => row.event_id === saved.event_id && row.chart_path === saved.chart_path);
  if (fullIndex >= 0) {{
    items[fullIndex].manual_label = saved.manual_label;
    items[fullIndex].notes = saved.notes;
    items[fullIndex].reviewed_at_utc = saved.reviewed_at_utc;
  }}
  applyFilters(true);
  if (index < filtered.length - 1) index += 1;
  render();
}}

function move(delta) {{
  if (!filtered.length) return;
  index = Math.max(0, Math.min(filtered.length - 1, index + delta));
  render();
}}

async function boot() {{
  const response = await fetch('/api/items');
  items = await response.json();
  setPatterns();
  applyFilters();
}}

els.patternFilter.addEventListener('change', () => applyFilters());
els.reviewFilter.addEventListener('change', () => applyFilters());
els.search.addEventListener('input', () => applyFilters());
els.prevBtn.addEventListener('click', () => move(-1));
els.nextBtn.addEventListener('click', () => move(1));
els.csvBtn.addEventListener('click', () => window.open('/api/reviews.csv', '_blank'));
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
