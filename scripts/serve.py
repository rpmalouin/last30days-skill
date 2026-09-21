#!/usr/bin/env python3
"""Static file server for last30days HTML reports with raw-evidence drill-down."""

from __future__ import annotations

import argparse
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

SOURCE_COLORS = {
    "reddit": "var(--reddit)", "x": "var(--x)", "youtube": "var(--youtube)",
    "tiktok": "var(--tiktok)", "instagram": "#e1306c",
    "hackernews": "var(--hackernews)", "bluesky": "#0285ff",
    "truthsocial": "#544b8a", "polymarket": "var(--polymarket)",
    "grounding": "var(--web)", "xiaohongshu": "#ff2442",
    "github": "var(--github)", "perplexity": "#21fb9a", "threads": "#000000",
    "pinterest": "#e60023", "digg": "var(--digg)", "arxiv": "var(--arxiv)",
    "techmeme": "#333333", "trustpilot": "#00b67a", "amazon": "#ff9900",
    "meta_ads": "#0866ff", "jobs": "#10b981", "linkedin": "var(--linkedin)",
    "corpus": "#f59e0b", "dripstack": "#7c3aed", "telegram": "#229ed9",
}

# Keys mirror pipeline.MOCK_AVAILABLE_SOURCES (the engine's canonical source set).
SOURCE_TABS = [
    ("reddit", "Reddit"), ("x", "X"), ("youtube", "YouTube"), ("tiktok", "TikTok"),
    ("instagram", "Instagram"), ("hackernews", "HN"), ("bluesky", "Bluesky"),
    ("truthsocial", "Truth Social"), ("polymarket", "Polymarket"), ("grounding", "Web"),
    ("xiaohongshu", "Xiaohongshu"), ("github", "GitHub"), ("perplexity", "Perplexity"),
    ("threads", "Threads"), ("pinterest", "Pinterest"), ("digg", "Digg"),
    ("arxiv", "arXiv"), ("techmeme", "Techmeme"), ("trustpilot", "Trustpilot"),
    ("amazon", "Amazon"), ("meta_ads", "Meta Ads"), ("jobs", "Jobs"),
    ("linkedin", "LinkedIn"), ("corpus", "Your files"), ("dripstack", "DripStack"),
    ("telegram", "Telegram"),
]

SOURCE_BAR_CSS = """
.source-tabs { display: flex; gap: 0.35rem; flex-wrap: wrap; margin-bottom: 1.5rem;
  padding-bottom: 1rem; border-bottom: 1px solid var(--border); }
.source-tab { font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.04em; padding: 0.2rem 0.6rem; border-radius: 4px;
  transition: opacity .2s ease; text-decoration: none; }
.source-tab.on { color: #fff; }
.source-tab.off { color: var(--fg-subtle); background: var(--bg-elev);
  border: 1px solid var(--border); opacity: 0.5; }
.source-tab.off:hover { opacity: 1; }
.source-tab.sel { outline: 2px solid var(--accent); outline-offset: 1px; }"""


def _detect_source(key: str) -> bool:
    checks = {
        "reddit": lambda: True,
        "x": lambda: bool(
            (os.environ.get("AUTH_TOKEN") and os.environ.get("CT0"))
            or os.environ.get("XAI_API_KEY") or os.environ.get("XQUIK_API_KEY")
            or os.environ.get("X_BEARER_TOKEN")
            or shutil.which("xurl") or shutil.which("bird") or shutil.which("grok")
        ),
        "youtube": lambda: bool(shutil.which("yt-dlp") or os.environ.get("SCRAPECREATORS_API_KEY")),
        "tiktok": lambda: bool(os.environ.get("SCRAPECREATORS_API_KEY")),
        "instagram": lambda: bool(os.environ.get("SCRAPECREATORS_API_KEY")),
        "hackernews": lambda: True,
        "bluesky": lambda: bool(os.environ.get("BSKY_HANDLE") and os.environ.get("BSKY_APP_PASSWORD")),
        "truthsocial": lambda: bool(os.environ.get("TRUTHSOCIAL_TOKEN")),
        "polymarket": lambda: True,
        "grounding": lambda: True,
        "xiaohongshu": lambda: bool(os.environ.get("XIAOHONGSHU_API_BASE")),
        "github": lambda: True,
        "perplexity": lambda: bool(os.environ.get("PERPLEXITY_API_KEY") or os.environ.get("OPENROUTER_API_KEY")),
        "threads": lambda: bool(os.environ.get("SCRAPECREATORS_API_KEY")),
        "pinterest": lambda: bool(os.environ.get("SCRAPECREATORS_API_KEY")),
        "digg": lambda: bool(shutil.which("digg-pp-cli")),
        "arxiv": lambda: bool(shutil.which("arxiv-pp-cli")),
        "techmeme": lambda: bool(shutil.which("techmeme-pp-cli")),
        "trustpilot": lambda: bool(shutil.which("trustpilot-pp-cli")),
        "amazon": lambda: bool(shutil.which("brightdata")),
        "meta_ads": lambda: bool(os.environ.get("SCRAPECREATORS_API_KEY")),
        "jobs": lambda: True,
        "linkedin": lambda: bool(os.environ.get("SCRAPECREATORS_API_KEY")),
        "corpus": lambda: bool(os.environ.get("LAST30DAYS_CORPUS_DIRS")),
        "dripstack": lambda: True,
        "telegram": lambda: bool(os.environ.get("SCRAPECREATORS_API_KEY") and os.environ.get("TELEGRAM_SOURCES")),
    }
    return checks.get(key, lambda: False)()


def _list_sources() -> list[dict]:
    raw = os.environ.get("SOURCES", "").strip()
    allowed = {s.strip().lower() for s in raw.split(",") if s.strip()} if raw else None
    return [
        {"key": k, "label": label, "available": _detect_source(k),
         "color": SOURCE_COLORS.get(k, "var(--accent)")}
        for k, label in SOURCE_TABS
        if allowed is None or k in allowed
    ]


def render_source_tabs(
    active_sources: set[str] | None = None,
    clickable: bool = False,
    selected: set[str] | None = None,
    onclick: str = "toggleSourceTab",
) -> str:
    tabs = []
    for s in _list_sources():
        on = active_sources is None or s["key"] in active_sources
        style = f"background:{s['color']}" if on else ""
        sel = selected is None or s["key"] in selected
        cls = "source-tab on" if on else "source-tab off"
        if sel and on:
            cls += " sel"
        if clickable:
            extra = f' style="cursor:pointer;{style}" data-key="{s["key"]}" onclick="{onclick}(this)"'
        else:
            extra = f' style="{style}"'
        tabs.append(f'<span class="{cls}"{extra}>{s["label"]}</span>')
    return f'<div class="source-tabs">{"".join(tabs)}</div>'


INDEX_CSS = """
:root { --bg: #0e0e10; --bg-elev: #18181b; --bg-card: #1e1e21; --fg: #fafafa;
  --fg-muted: #a1a1aa; --fg-subtle: #71717a; --accent: #a855f7; --accent-soft: #c4b5fd;
  --border: #27272a; --border-hover: #3f3f46; --max-w: 800px; --radius: 10px;
  --reddit: #ff4500; --x: #1da1f2; --youtube: #ff0000; --github: #6e40c9;
  --hackernews: #ff6600; --digg: #000000; --polymarket: #0a0a23; --tiktok: #ff0050;
  --linkedin: #0a66c2; --arxiv: #b31b1b; --web: #2563eb; }
@media (prefers-color-scheme: light) { :root { --bg: #ffffff; --bg-elev: #fafafa;
  --bg-card: #f4f4f5; --fg: #18181b; --fg-muted: #52525b; --fg-subtle: #71717a;
  --accent: #7c3aed; --border: #e4e4e7; --border-hover: #d4d4d8; } }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--bg); color: var(--fg);
  font-family: Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto,
  system-ui, sans-serif; font-size: 17px; line-height: 1.65; }
body { max-width: var(--max-w); margin: 0 auto; padding: 2rem 1.5rem 6rem; }
h1 { font-size: 26px; font-weight: 700; margin: 0 0 0.25rem; }
p.sub { color: var(--fg-subtle); margin: 0 0 2.5rem; font-size: 14px; }
.report { display: flex; padding: 1rem 1.25rem; margin-bottom: 0.75rem;
  background: var(--bg-elev); border: 1px solid var(--border);
  border-radius: var(--radius); text-decoration: none; color: var(--fg);
  transition: border-color .15s ease; gap: 0.5rem; align-items: flex-start; }
.report:hover { border-color: var(--accent); }
.report .report-body { flex: 1; min-width: 0; }
.report .title { font-weight: 600; font-size: 16px; margin-bottom: 0.3rem; }
.report .title .accent { color: var(--accent); }
.report .meta { font-size: 13px; color: var(--fg-subtle); }
.report .links { margin-top: 0.5rem; display: flex; gap: 0.75rem; }
.report .links a { font-size: 13px; color: var(--accent); text-decoration: none;
  border: 1px solid var(--border); border-radius: 6px; padding: 0.2rem 0.7rem;
  transition: border-color .15s ease; }
.report .links a:hover { border-color: var(--accent); }
.report .delete-btn { font-size: 13px; color: #ef4444; text-decoration: none;
  border: 1px solid var(--border); border-radius: 6px; padding: 0.2rem 0.7rem;
  transition: all .15s ease; cursor: pointer; background: none; font-family: inherit;
  margin-left: auto; }
.report .delete-btn:hover { border-color: #ef4444; background: rgba(239,68,68,0.08); }
.missing { text-align: center; padding: 4rem 0; color: var(--fg-subtle); }
.missing h2 { font-size: 20px; color: var(--fg-muted); margin: 0 0 0.5rem; }
.missing p { font-size: 14px; margin: 0; }
.nav { margin-bottom: 2rem; }
.nav a { color: var(--accent); text-decoration: none; font-size: 14px; }
.nav a:hover { text-decoration: underline; }
.controls { margin-bottom: 1.5rem; display: flex; gap: 0.5rem; flex-wrap: wrap; }
.controls a { font-size: 13px; color: var(--fg-muted); text-decoration: none;
  border: 1px solid var(--border); border-radius: 6px; padding: 0.35rem 0.85rem;
  transition: all .15s ease; background: var(--bg-elev); }
.controls a:hover, .controls a.active { border-color: var(--accent); color: var(--accent); }
.research-bar { background: var(--bg-elev); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1.25rem; margin-bottom: 2rem; }
.research-bar .row { display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; }
.research-bar input { flex: 1; min-width: 200px; padding: 0.6rem 0.85rem;
  background: var(--bg); border: 1px solid var(--border); border-radius: 6px;
  color: var(--fg); font-size: 15px; outline: none; transition: border-color .15s ease; }
.research-bar input:focus { border-color: var(--accent); }
.research-bar input::placeholder { color: var(--fg-subtle); }
.research-bar button { padding: 0.6rem 1.25rem; background: var(--accent);
  border: none; border-radius: 6px; color: #fff; font-size: 15px; font-weight: 500;
  cursor: pointer; transition: opacity .15s ease; white-space: nowrap; }
.research-bar button:hover { opacity: 0.9; }
.research-bar button:disabled { opacity: 0.4; cursor: not-allowed; }
.research-bar .status { margin-top: 0.75rem; font-size: 14px; color: var(--fg-muted);
  display: flex; gap: 0.5rem; align-items: center; }
.research-bar .spinner { display: inline-block; width: 14px; height: 14px;
  border: 2px solid var(--border); border-top-color: var(--accent);
  border-radius: 50%; animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.source-group { margin-bottom: 2.5rem; }
.source-header { display: flex; align-items: center; gap: 0.6rem;
  margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border); }
.source-badge { display: inline-block; font-size: 11px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.05em; padding: 0.2rem 0.55rem;
  border-radius: 4px; color: #fff; }
.item-card { background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1rem 1.25rem; margin-bottom: 0.75rem;
  transition: border-color .15s ease; }
.item-card:hover { border-color: var(--border-hover); }
.item-card .item-title { font-weight: 600; font-size: 15px; margin-bottom: 0.3rem; }
.item-card .item-title a { color: var(--fg); text-decoration: none; }
.item-card .item-title a:hover { color: var(--accent); }
.item-card .item-meta { font-size: 12px; color: var(--fg-subtle);
  display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 0.4rem; }
.item-card .item-meta .container { color: var(--fg-muted); }
.item-card .item-snippet { font-size: 14px; color: var(--fg-muted);
  line-height: 1.5; margin-top: 0.3rem; }
.item-card .engagements { display: flex; gap: 0.75rem; margin-top: 0.5rem;
  font-size: 13px; color: var(--fg-subtle); }
.item-card .engagements span { display: flex; align-items: center; gap: 0.2rem; }
.summary-bar { background: var(--bg-elev); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 0.75rem 1.25rem; margin-bottom: 2rem;
  font-size: 14px; color: var(--fg-muted); display: flex; gap: 1.5rem; flex-wrap: wrap; }
.summary-bar strong { color: var(--fg); }
""" + SOURCE_BAR_CSS

_TITLE_RE = re.compile(rb"<title>(.+?)</title>", re.IGNORECASE)
_H1_RE = re.compile(rb"<h1[^>]*>(.+?)</h1>", re.IGNORECASE)
_BADGE_RE = re.compile(
    rb'<div class="badge">\s*<span class="accent">#</span>\s*last30days:\s*(.+?)\s*</div>',
    re.IGNORECASE,
)
# Matches report files, both base ({topic}-raw-html.html / {topic}-raw.json)
# and dated-counter variants ({topic}-raw-html-YYYY-MM-DD-N.html / -raw-...json).
# Dated variants are produced by the engine whenever the base name is taken.
_RAW_HTML_RE = re.compile(
    r"^(?P<topic>.+?)-raw-html(?P<date>(?:-\d{4}-\d{2}-\d{2}(?P<run>-\d+)?)?)\.html$"
)
_RAW_JSON_RE = re.compile(
    r"^(?P<topic>.+?)-raw(?P<date>(?:-\d{4}-\d{2}-\d{2}(?P<run>-\d+)?)?)\.json$"
)


def extract_title(html_path: Path) -> str:
    raw = html_path.read_bytes()[:4096]
    for pat in (_BADGE_RE, _TITLE_RE, _H1_RE):
        m = pat.search(raw)
        if m:
            return m.group(1).decode("utf-8", errors="replace").strip()
    return html_path.stem


def html_report_key(html_name: str) -> str | None:
    """Unique report key for an HTML report filename (base or dated).

    The key is the html filename stem, e.g. ``ai-agents-raw-html-2026-08-01-3``.
    """
    m = _RAW_HTML_RE.match(html_name)
    if m:
        return f"{m.group('topic')}-raw-html{m.group('date') or ''}"
    return None


def json_name_for_html(html_name: str) -> str | None:
    """Return the paired JSON evidence filename for an HTML report filename."""
    m = _RAW_HTML_RE.match(html_name)
    if m:
        return f"{m.group('topic')}-raw{m.group('date') or ''}.json"
    return None


def report_key_to_json_name(key: str) -> str:
    """Map a report key (html stem) to its JSON evidence filename."""
    return key.replace("-raw-html", "-raw") + ".json"


def json_path_for_html(html_name: str, data_dir: Path) -> Path | None:
    json_name = json_name_for_html(html_name)
    if json_name is None:
        return None
    candidate = data_dir / json_name
    return candidate if candidate.is_file() else None


def list_reports(data_dir: Path) -> list[dict]:
    reports = {}
    for p in sorted(data_dir.iterdir(), reverse=True):
        key = html_report_key(p.name)
        if key is None:
            continue
        mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        json_name = json_name_for_html(p.name)
        has_json = (data_dir / json_name).is_file() if json_name else False
        reports.setdefault(key, {
            "slug": key,
            "html": p.name,
            "title": extract_title(p),
            "mtime": mtime.isoformat(),
            "size": p.stat().st_size,
            "has_json": has_json,
        })
    return sorted(reports.values(), key=lambda r: r["mtime"], reverse=True)


def load_evidence_json(path: Path) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def render_index(data_dir: Path) -> str:
    reports = list_reports(data_dir)
    rows = []
    if reports:
        for r in reports:
            evidence_link = ""
            if r["has_json"]:
                evidence_link = f'<a href="/report/{r["slug"]}/evidence">Evidence</a>'
            rows.append(
                f'<div class="report">'
                f'<div class="report-body">'
                f'<a href="/report/{r["slug"]}/" style="text-decoration:none;color:var(--fg);display:block">'
                f'<div class="title"><span class="accent">#</span> {html_escape(r["title"])}</div>'
                f'<div class="meta">{html_escape(r["mtime"][:10])} &middot; {r["size"] // 1024} KB</div>'
                f'<div class="links"><a href="/report/{r["slug"]}/" onclick="event.stopPropagation()">Report</a>{evidence_link}</div>'
                f'</a>'
                f'</div>'
                f'<button class="delete-btn" onclick="deleteReport(\'{r["slug"]}\')">Delete</button>'
                f'</div>'
            )
    else:
        rows.append(
            '<div class="missing">'
            "<h2>No reports yet</h2>"
            "<p>Run the engine to generate HTML reports,<br>or set RESEARCH_TOPIC on container start.</p>"
            "</div>"
        )
    body = "\n".join(rows)

    with _research_lock:
        initial_running = _research_status["running"]
        initial_topic = _research_status["topic"]

    research_bar = f"""<div class="research-bar">
<div class="row">
<input type="text" id="topic-input" placeholder="Enter research topic..." value="{html_escape(initial_topic)}">
<button id="research-btn" onclick="startResearch()">Research</button>
</div>
<div id="research-status" class="status">{'<span class="spinner"></span> Researching ' + html_escape(initial_topic) + '...' if initial_running else ''}</div>
</div>"""

    js = """<script>
var selectedSources = null;

function toggleSourceTab(el) {
  var key = el.getAttribute('data-key');
  if (selectedSources === null) {
    selectedSources = {};
    document.querySelectorAll('.source-tabs .source-tab').forEach(function(t) {
      selectedSources[t.getAttribute('data-key')] = true;
    });
  }
  if (selectedSources[key]) {
    delete selectedSources[key];
    el.classList.remove('sel');
  } else {
    selectedSources[key] = true;
    el.classList.add('sel');
  }
}

async function pollStatus() {
  const res = await fetch('/api/research/status');
  return res.json();
}
async function startResearch() {
  var topic = document.getElementById('topic-input').value.trim();
  if (!topic) return;
  var btn = document.getElementById('research-btn');
  var status = document.getElementById('research-status');
  status.innerHTML = '<span class="spinner"></span> Researching ' + topic + '...';
  btn.disabled = true;
  var body = {topic: topic};
  if (selectedSources) {
    var keys = Object.keys(selectedSources);
    var allKeys = [];
    document.querySelectorAll('.source-tabs .source-tab').forEach(function(t) {
      allKeys.push(t.getAttribute('data-key'));
    });
    if (keys.length !== allKeys.length) {
      body.sources = keys;
    }
  }
  await fetch('/api/research', { method: 'POST', body: JSON.stringify(body) });
  const poll = setInterval(async () => {
    const data = await pollStatus();
    if (!data.running) {
      clearInterval(poll);
      status.innerHTML = '\\u2705 Complete! Reloading...';
      location.reload();
    }
  }, 2000);
}
async function deleteReport(slug) {
  if (!confirm('Delete this report and its evidence?')) return;
  await fetch('/api/reports/' + slug, { method: 'DELETE' });
  location.reload();
}
(async function() {
  const data = await pollStatus();
  if (data.running) {
    document.getElementById('research-btn').disabled = true;
    const poll = setInterval(async () => {
      const d = await pollStatus();
      if (!d.running) {
        clearInterval(poll);
        location.reload();
      }
    }, 2000);
  }
})();
</script>"""

    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>last30days Library</title><style>{INDEX_CSS}</style></head><body>
<h1>last30days</h1>
<p class="sub">Research library &middot; {len(reports)} report{"s" if len(reports) != 1 else ""}</p>
{research_bar}
{render_source_tabs(clickable=True, selected=None)}
{body}
{js}
</body></html>"""


def render_evidence_page(slug: str, data: dict, mtime: str) -> str:
    items_by_source = data.get("items_by_source") or {}
    ranked = data.get("ranked_candidates") or []
    topic = data.get("topic") or slug
    total_items = sum(len(v) for v in items_by_source.values())
    sources = sorted(items_by_source.keys())

    source_groups = []
    for src in sources:
        items = items_by_source[src]
        if not items:
            continue
        color = SOURCE_COLORS.get(src.lower(), "var(--accent)")
        cards = []
        for item in items:
            title = item.get("title") or "(no title)"
            url = item.get("url") or ""
            snippet = item.get("snippet") or item.get("body", "")[:300] or ""
            author = item.get("author") or ""
            container = item.get("container") or ""
            published = item.get("published_at") or ""
            eng = item.get("engagement") or {}
            eng_parts = engagement_spans(eng)
            author_line = f"by {html_escape(author)}" if author else ""
            container_line = f"in {html_escape(container)}" if container else ""
            date_line = html_escape(published) if published else ""
            meta_parts = " &middot; ".join(p for p in [author_line, container_line, date_line] if p)

            cards.append(f"""<div class="item-card">
<div class="item-title"><a href="{html_escape(url)}" target="_blank" rel="noopener">{html_escape(title)}</a></div>
<div class="item-meta">{meta_parts}</div>
<div class="item-snippet">{html_escape(snippet[:400])}</div>
<div class="engagements">{eng_parts}</div>
</div>""")

        source_groups.append(f"""<div class="source-group" data-source="{html_escape(src)}">
<div class="source-header">
<span class="source-badge" style="background:{color}">{html_escape(src)}</span>
<span style="font-size:14px;color:var(--fg-subtle)">{len(cards)} item{"s" if len(cards)!=1 else ""}</span>
</div>
{''.join(cards)}
</div>""")

    source_summary = " &middot; ".join(
        f"<strong>{len(v)}</strong> from {html_escape(k)}" for k, v in sorted(items_by_source.items()) if v
    )
    filter_js = """<script>
function filterSource(el) {
  var key = el.getAttribute('data-key');
  document.querySelectorAll('.source-group').forEach(function(g) {
    g.style.display = (!key || g.getAttribute('data-source') === key) ? '' : 'none';
  });
  document.querySelectorAll('.source-tabs .source-tab').forEach(function(t) {
    t.style.opacity = (!key || t.getAttribute('data-key') === key) ? '1' : '0.3';
  });
}
</script>"""
    r = f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Evidence: {html_escape(topic)} — last30days</title><style>{INDEX_CSS}</style></head><body>
<div class="nav"><a href="/">← Library</a> &middot; <a href="/report/{slug}/">Report</a> &middot; <strong>Evidence</strong></div>
{render_source_tabs(set(sources), clickable=True, onclick="filterSource")}
<h1>{html_escape(topic)}</h1>
<p class="sub">Raw evidence &middot; {html_escape(mtime[:10])} &middot; {total_items} items across {len(sources)} sources</p>
<div class="summary-bar">{source_summary}</div>
{''.join(source_groups)}
{filter_js}
</body></html>"""
    return r


INLINE_EVIDENCE_CSS = """
.evidence-section { margin-top: 4rem; padding-top: 2rem; border-top: 1px solid var(--border); }
.evidence-section h2 { font-size: 20px; font-weight: 600; margin: 0 0 0.25rem; color: var(--fg); }
.evidence-section p.sub { margin: 0 0 1.5rem; font-size: 14px; }
""" + SOURCE_BAR_CSS + """
.evidence-toggle { font-size: 13px; color: var(--accent); cursor: pointer;
  border: 1px solid var(--border); border-radius: 6px; padding: 0.35rem 0.85rem;
  background: var(--bg-elev); margin-bottom: 1.5rem; display: inline-block; }
.evidence-toggle:hover { border-color: var(--accent); }
.evidence-items { display: none; }
.evidence-items.open { display: block; }
"""


def render_evidence_inline(slug: str, data: dict) -> str:
    items_by_source = data.get("items_by_source") or {}
    topic = data.get("topic") or slug
    total_items = sum(len(v) for v in items_by_source.values())
    sources = sorted(items_by_source.keys())

    source_groups = []
    for src in sources:
        items = items_by_source[src]
        if not items:
            continue
        color = SOURCE_COLORS.get(src.lower(), "var(--accent)")
        cards = []
        for item in items:
            title = item.get("title") or "(no title)"
            url = item.get("url") or ""
            snippet = item.get("snippet") or item.get("body", "")[:300] or ""
            author = item.get("author") or ""
            container = item.get("container") or ""
            published = item.get("published_at") or ""
            eng = item.get("engagement") or {}
            eng_parts = engagement_spans(eng)
            author_line = f"by {html_escape(author)}" if author else ""
            container_line = f"in {html_escape(container)}" if container else ""
            date_line = html_escape(published) if published else ""
            meta_parts = " &middot; ".join(p for p in [author_line, container_line, date_line] if p)

            cards.append(f"""<div class="item-card">
<div class="item-title"><a href="{html_escape(url)}" target="_blank" rel="noopener">{html_escape(title)}</a></div>
<div class="item-meta">{meta_parts}</div>
<div class="item-snippet">{html_escape(snippet[:400])}</div>
<div class="engagements">{eng_parts}</div>
</div>""")

        source_groups.append(f"""<div class="source-group" data-source="{html_escape(src)}">
<div class="source-header">
<span class="source-badge" style="background:{color}">{html_escape(src)}</span>
<span style="font-size:14px;color:var(--fg-subtle)">{len(cards)} item{"s" if len(cards)!=1 else ""}</span>
</div>
{''.join(cards)}
</div>""")

    source_summary = " &middot; ".join(
        f"<strong>{len(v)}</strong> from {html_escape(k)}" for k, v in sorted(items_by_source.items()) if v
    ) if items_by_source else "No items"

    return f"""<div class="evidence-section">
<style>{INLINE_EVIDENCE_CSS}</style>
{render_source_tabs(set(sources), clickable=True, onclick="filterSource")}
<h2>Raw Evidence</h2>
<p class="sub">{total_items} items across {len(sources)} sources &middot; <span class="evidence-toggle" onclick="this.classList.toggle('open');document.getElementById('evidence-body').classList.toggle('open')">Toggle items</span></p>
<div class="summary-bar">{source_summary}</div>
<div id="evidence-body" class="evidence-items">
{''.join(source_groups)}
</div>
{_INLINE_FILTER_JS}
</div>"""

_INLINE_FILTER_JS = """<script>
function filterSource(el) {
  var key = el.getAttribute('data-key');
  document.querySelectorAll('.evidence-section .source-group').forEach(function(g) {
    g.style.display = (!key || g.getAttribute('data-source') === key) ? '' : 'none';
  });
  document.querySelectorAll('.evidence-section .source-tab').forEach(function(t) {
    t.style.opacity = (!key || t.getAttribute('data-key') === key) ? '1' : '0.3';
  });
}
</script>"""


def engagement_spans(eng: dict) -> str:
    labels = {
        "score": "↑", "num_comments": "💬", "likes": "♥", "reposts": "↻",
        "retweets": "↻", "views": "👁", "comments": "💬", "postCount": "📦",
        "uniqueAuthors": "✎", "reshares": "↻", "rank_score": "★",
    }
    parts = []
    for k, v in sorted(eng.items()):
        lbl = labels.get(k, k)
        val = int(v) if isinstance(v, (int, float)) else v
        parts.append(f"<span>{lbl} {val}</span>")
    return "".join(parts)


def html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _read_file(p: Path) -> bytes | None:
    try:
        return p.read_bytes()
    except OSError:
        return None


_research_lock = threading.Lock()
_research_status = {
    "running": False,
    "topic": "",
    "started_at": None,
    "completed_at": None,
    "exit_code": None,
    "slug": None,
}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "topic"


class Last30daysHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, data_dir: Path, **kwargs):
        self.data_dir = data_dir
        super().__init__(*args, directory=str(data_dir), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/" or path == "/index.html":
            self._serve_index()
            return
        if path.startswith("/report/"):
            parts = path.split("/")
            if len(parts) == 3:
                key = parts[2]
                html_file = self.data_dir / f"{key}.html"
                if html_file.is_file():
                    self._serve_file(html_file)
                else:
                    self.send_error(404, "Report not found")
                return
            if len(parts) == 4 and parts[3] == "evidence":
                key = parts[2]
                json_file = self.data_dir / report_key_to_json_name(key)
                html_file = self.data_dir / f"{key}.html"
                if json_file.is_file():
                    data = load_evidence_json(json_file)
                    mtime = ""
                    if html_file.is_file():
                        mtime = datetime.fromtimestamp(html_file.stat().st_mtime, tz=timezone.utc).isoformat()
                    if data:
                        self._serve_string(render_evidence_page(key, data, mtime), "text/html")
                        return
                self.send_error(404, "Evidence not found")
                return
            self.send_error(404)
            return
        if path == "/api/reports":
            self._serve_string(json.dumps(list_reports(self.data_dir), indent=2), "application/json")
            return
        if path == "/api/sources":
            self._serve_string(json.dumps(_list_sources(), indent=2), "application/json")
            return
        if path == "/api/health":
            body = json.dumps({"status": "ok", "report_count": len(list_reports(self.data_dir))})
            self._serve_string(body, "application/json")
            return
        if path == "/api/research/status":
            with _research_lock:
                status = dict(_research_status)
            self._serve_string(json.dumps(status), "application/json")
            return
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/research":
            self._handle_research()
        else:
            self.send_error(404)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        parts = path.split("/")
        if len(parts) == 4 and parts[1] == "api" and parts[2] == "reports":
            key = parts[3]
            deleted = 0
            for p in [self.data_dir / f"{key}.html", self.data_dir / report_key_to_json_name(key)]:
                if p.is_file():
                    p.unlink()
                    deleted += 1
            if deleted:
                self._serve_string(json.dumps({"status": "deleted", "slug": key, "files": deleted}), "application/json")
            else:
                self.send_error(404, "Report not found")
        else:
            self.send_error(404)

    def _serve_index(self):
        self._serve_string(render_index(self.data_dir), "text/html")

    def _serve_file(self, path: Path):
        data = _read_file(path)
        if data is None:
            self.send_error(404)
            return
        content_type = "text/html" if path.suffix == ".html" else "application/octet-stream"
        if content_type == "text/html":
            key = html_report_key(path.name)
            if key:
                json_file = self.data_dir / report_key_to_json_name(key)
                evidence_data = load_evidence_json(json_file) if json_file.is_file() else None
                if evidence_data:
                    items_html = render_evidence_inline(key, evidence_data)
                    data = data.replace(b"</body>", items_html.encode("utf-8") + b"</body>")
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_string(self, content: str, content_type: str):
        body = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_research(self):
        content_length = int(self.headers.get("Content-Length", 0))
        topic = os.environ.get("RESEARCH_TOPIC", "")
        sources = None
        if content_length:
            raw = self.rfile.read(content_length)
            try:
                payload = json.loads(raw)
                topic = payload.get("topic", topic)
                sources = payload.get("sources")
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        if not topic:
            self._serve_string(
                json.dumps({"error": "No topic. Set RESEARCH_TOPIC or provide one in the request body."}),
                "application/json",
            )
            return
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "started", "topic": topic}).encode())
        threading.Thread(target=_run_research, args=(topic, self.data_dir), kwargs={"sources": sources}, daemon=True).start()

    def log_message(self, fmt, *args):
        super().log_message(fmt, *args)


def _run_research(topic: str, data_dir: Path, sources: list[str] | None = None):
    if sources is None:
        raw = os.environ.get("SOURCES", "").strip()
        sources = [s.strip().lower() for s in raw.split(",") if s.strip()] if raw else None
    slug = _slugify(topic)
    with _research_lock:
        _research_status.update(
            running=True, topic=topic, slug=slug,
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=None, exit_code=None,
        )
    engine = Path("skills/last30days/scripts/last30days.py").resolve()
    if not engine.exists():
        engine = Path("/app/skills/last30days/scripts/last30days.py")
    exit_code = 0
    for emit, profile in [("html", None), ("json", "raw")]:
        cmd = [sys.executable, str(engine), topic, f"--emit={emit}", f"--save-dir={data_dir}"]
        if sources is not None:
            cmd.append(f"--search={','.join(sources)}")
        if profile:
            cmd.append(f"--json-profile={profile}")
        sys.stderr.write(f"[serve] Running: {' '.join(cmd)}\n")
        try:
            subprocess.run(cmd, timeout=600, check=True)
        except subprocess.TimeoutExpired:
            sys.stderr.write(f"[serve] {emit} timed out after 600s\n")
            exit_code = -1
        except subprocess.CalledProcessError as exc:
            sys.stderr.write(f"[serve] {emit} failed with exit code {exc.returncode}\n")
            exit_code = exc.returncode
    with _research_lock:
        _research_status.update(
            running=False, exit_code=exit_code,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )


def _scheduler_loop(data_dir: Path, interval_hours: float):
    topic = os.environ.get("RESEARCH_TOPIC", "")
    if not topic:
        return
    raw = os.environ.get("SOURCES", "").strip()
    sources = [s.strip().lower() for s in raw.split(",") if s.strip()] if raw else None
    while True:
        time.sleep(interval_hours * 3600)
        _run_research(topic, data_dir, sources=sources)


def main():
    parser = argparse.ArgumentParser(description="last30days HTML report server")
    parser.add_argument("data_dir", type=Path, default=Path("/data"), nargs="?")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--bind", default="0.0.0.0")
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    interval = float(os.environ.get("RESEARCH_INTERVAL_HOURS", "0"))
    if interval > 0:
        t = threading.Thread(target=_scheduler_loop, args=(data_dir, interval), daemon=True)
        t.start()
        sys.stderr.write(f"[serve] Research schedule: every {interval}h\n")

    handler = lambda *a: Last30daysHandler(*a, data_dir=data_dir)
    server = http.server.HTTPServer((args.bind, args.port), handler)
    sys.stderr.write(f"[serve] Listening on http://{args.bind}:{args.port}\n")
    sys.stderr.write(f"[serve] Serving: {data_dir}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()