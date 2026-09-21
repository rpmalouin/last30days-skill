#!/usr/bin/env python3
"""Self-test for the fork's web console (scripts/serve.py).

Stdlib only, no network and no fixtures from the live deployment: it builds a tiny
synthetic report library in a temp dir, exercises the render helpers and the HTTP
surface, and asserts the UI<->engine contract that has to hold after an engine bump.

    python3 scripts/ui_selftest.py            # quiet, prints a summary
    python3 scripts/ui_selftest.py -v         # one line per check
    python3 scripts/ui_selftest.py -k palette # only checks whose name matches

Exit code 0 = every check passed, 1 = at least one failure, 2 = harness error.
"""

from __future__ import annotations

import argparse
import http.server
import importlib.util
import json
import os
import re
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SERVE = Path(__file__).resolve().parent / "serve.py"

# Every colour the stylesheet is allowed to contain. Anything else fails the palette audit.
WARM_PALETTE = {
    "#14120f",  # bg
    "#1a1613",  # bg-elev
    "#1f1b16",  # bg-card
    "#ede5d8",  # fg
    "#9e9282",  # fg-muted
    "#8a7e6f",  # fg-subtle / chip-fg
    "#8f8270",  # label-fg
    "#d4a359",  # accent
    "#e3bd85",  # accent-soft
    "#e0b26a",  # accent-hover
    "#181512",  # accent-fg
    "#332c23",  # border
    "#2a241d",  # border-soft
    "#443a2d",  # border-hover
    "#544735",  # brass
    "#241f1a",  # chip-bg
    "#383027",  # chip-border
    "#3a2f1e",  # chip-sel-bg
    "#26211a",  # snap-bg
    "#e6ded1",  # pill-active-bg
    "#1c1813",  # pill-active-fg
    "#c86446",  # danger
    "#b9a98a",  # label hover
}
FORBIDDEN = ("#a855f7", "#d8b4fe", "#7c3aed", "#6d28d9", "#ef4444", "#f87171", "#27272a", "#3f3f46")

CHECKS: list[tuple[str, str]] = []      # (group, name)
FAILURES: list[str] = []
VERBOSE = False
PATTERN: str | None = None


def check(name: str, ok: bool, detail: str = "", group: str = "general") -> None:
    if PATTERN and PATTERN not in f"{group}/{name}":
        return
    CHECKS.append((group, name))
    if ok:
        if VERBOSE:
            print(f"  ok   {group}/{name}")
        return
    FAILURES.append(f"{group}/{name}" + (f" :: {detail}" if detail else ""))
    print(f"  FAIL {group}/{name}" + (f" :: {detail}" if detail else ""))


# --------------------------------------------------------------------------- fixtures

def build_library(root: Path) -> Path:
    """Synthetic reports: one singleton topic, one topic with three runs (incl. the
    engine's same-day ladder suffix), one singleton without a JSON sidecar."""
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    stamp = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)

    def write(name: str, title: str, when: datetime, sidecar: dict | None = None) -> None:
        html = (
            "<!DOCTYPE html><html><head>"
            f"<title>{title}</title></head><body><h1>{title}</h1></body></html>"
        )
        p = data / name
        p.write_text(html, encoding="utf-8")
        os.utime(p, (when.timestamp(), when.timestamp()))
        if sidecar is not None:
            j = data / name.replace("-raw-html", "-raw").replace(".html", ".json")
            j.write_text(json.dumps(sidecar), encoding="utf-8")
            os.utime(j, (when.timestamp(), when.timestamp()))

    evidence = {
        "topic": "Beta Topic",
        "items_by_source": {
            "reddit": [{"title": "a thread", "url": "https://example.invalid/1", "snippet": "s",
                        "author": "u/x", "container": "r/y", "published_at": "2026-09-01",
                        "engagement": {"score": 12}}],
            "hackernews": [{"title": "a story", "url": "https://example.invalid/2", "snippet": "s",
                            "author": "pg", "container": "HN", "published_at": "2026-09-02",
                            "engagement": {"score": 3, "num_comments": 1}}],
        },
    }
    write("alpha-raw-html.html", "last30days · Alpha Topic", stamp, {"topic": "Alpha Topic", "items_by_source": {}})
    write("gamma-raw-html-2026-09-11.html", "last30days · Gamma Topic", stamp + timedelta(days=1))
    write("beta-raw-html-2026-09-10.html", "last30days · Beta Topic", stamp + timedelta(days=2), evidence)
    write("beta-raw-html-2026-09-10-1.html", "last30days · Beta Topic", stamp + timedelta(days=3), evidence)
    write("beta-raw-html-2026-09-12.html", "last30days · Beta Topic", stamp + timedelta(days=4), evidence)
    return data


# --------------------------------------------------------------------------- checks

def static_checks(m, data: Path) -> str:
    index = m.render_index(data)
    groups = m.list_topic_groups(data)
    reports = m.list_reports(data)
    by_topic = {g["topic"]: g for g in groups}
    src = SERVE.read_text(encoding="utf-8")
    css = m.INDEX_CSS + m.SOURCE_BAR_CSS + m.INLINE_EVIDENCE_CSS

    # --- temporal labels
    label = m._trailing_window_label(now=datetime(2026, 9, 21, 18, 0, tzinfo=timezone.utc))
    check("trailing window label", label == "Trailing 30 Days: Aug 22 – Sep 21", label, "temporal")
    check("exact timestamp format", re.fullmatch(r"[A-Z][a-z]{2} \d{1,2}, \d{4} · \d{2}:\d{2}",
                                                m._exact_ts("2026-09-21T19:13:00+00:00")) is not None, "", "temporal")
    check("window pill rendered", f'class="window-pill">{label}' in index.replace(label, label), "", "temporal")
    check("indexed count rendered", f'class="indexed">{len(reports)} reports indexed' in index, "", "temporal")

    # --- grouping
    check("reports grouped into topic cards", len(groups) == 3 and len(reports) == 5,
          f"{len(reports)} reports / {len(groups)} cards", "grouping")
    beta = by_topic.get("beta", {})
    check("recurring topic collapses to one card", len(beta.get("snapshots", [])) == 3,
          str(len(beta.get("snapshots", []))), "grouping")
    check("snapshots newest first",
          all(beta["snapshots"][i]["mtime"] >= beta["snapshots"][i + 1]["mtime"]
              for i in range(len(beta["snapshots"]) - 1)), "", "grouping")
    check("ladder suffix read as the run number",
          [s["run"] for s in beta["snapshots"]] == [1, 2, 1], str([s["run"] for s in beta["snapshots"]]), "grouping")
    check("same-day runs get distinct labels",
          len({f'{s["day"]}#{s["run"]}' for s in beta["snapshots"]}) == 3, "", "grouping")
    check("card title is the topic only",
          sorted(g["title"] for g in groups) == ["Alpha Topic", "Beta Topic", "Gamma Topic"],
          str([g["title"] for g in groups]), "grouping")
    check("cards ordered by their newest run", groups[0]["title"] == "Beta Topic",
          str([g["title"] for g in groups]), "grouping")
    check("no engine title prefix anywhere", "last30days ·" not in index and "# last30days" not in index, "", "grouping")
    check("relative meta on every card", index.count("Covering last 30d") == len(groups), "", "grouping")

    # --- snapshot pills + action rows
    n_pills = sum(len(g["snapshots"]) for g in groups if len(g["snapshots"]) > 1)
    check("one pill per run of an aggregated topic", index.count('<span class="snapshot') == n_pills,
          str(index.count('<span class="snapshot')), "pills")
    check("pills carry slug/ts/has-json",
          index.count("data-slug=") == index.count("data-ts=") == index.count("data-has-json="), "", "pills")
    check("exactly one active pill per aggregated card", index.count('class="snapshot active"') == 1, "", "pills")
    check("active pill is the newest run",
          re.search(r'<span class="snapshot active" data-slug="([^"]+)"', index).group(1)
          == beta["snapshots"][0]["slug"], "", "pills")
    check("pill body is a button, not a link",
          '<button class="snap-body" type="button"' in index
          and "<a " not in index.split('class="snapshots"')[1].split("</div>")[0], "", "pills")
    check("action row on every card",
          index.count('class="act-report"') == index.count('class="act-evidence"')
          == index.count('class="action-meta"') == len(groups), "", "pills")
    check("action row targets the active snapshot",
          f'class="act-report" href="/report/{beta["snapshots"][0]["slug"]}/"' in index
          and f'class="act-evidence" href="/report/{beta["snapshots"][0]["slug"]}/evidence"' in index, "", "pills")
    check("timestamp pill matches the active snapshot",
          re.search(r'class="action-meta">([^<]+)<', index).group(1) == m._exact_ts(beta["snapshots"][0]["mtime"]),
          "", "pills")
    gamma_title_at = index.find("Gamma Topic")
    check("Evidence link hidden when a run has no JSON",
          'style="display:none"' in index[gamma_title_at:gamma_title_at + 900], "", "pills")

    # --- delete surface
    check("card Delete on every card", index.count('class="delete-btn"') == len(groups), "", "delete")
    check("aggregated card lists all of its snapshots",
          str(len(beta["snapshots"])) in index and f'data-count="{len(beta["snapshots"])}"' in index, "", "delete")
    check("topic-delete prompt string", "'Delete topic and all ' + slugs.length + ' snapshots?'" in src, "", "delete")
    check("single-delete prompt string", "'Delete this report and its evidence?'" in src, "", "delete")
    check("no legacy deleteReport handler", "deleteReport" not in src, "", "delete")
    check("per-snapshot delete button", index.count('class="snap-del"') == n_pills, "", "delete")

    # --- lane bar
    bar = m.render_source_tabs(clickable=True, selected=None)
    check("three category rows", bar.count("source-group-row") == 3, "", "lanes")
    check("every lane rendered", bar.count('<span class="source-tab') == len(m.SOURCE_TABS), "", "lanes")
    check("no lane left ungrouped", m._UNGROUPED_LANES == [], str(m._UNGROUPED_LANES), "lanes")
    check("[all]/[none] per row", bar.count('class="group-toggle"') == 6 and bar.count(">[all]</button>") == 3
          and bar.count(">[none]</button>") == 3, "", "lanes")
    check("no inline colours in the bar", "background:" not in bar, "", "lanes")
    check("lane group handlers wired",
          'onclick="groupLanes(this, true)"' in bar and 'onclick="groupLanes(this, false)"' in bar, "", "lanes")

    # --- palette / theme
    hexes = set(re.findall(r"#[0-9a-fA-F]{6}", css))
    check("palette audit: only warm tokens", hexes <= WARM_PALETTE, str(sorted(hexes - WARM_PALETTE)), "palette")
    check("no purple / raw red / cold neutral token", not any(c in src for c in FORBIDDEN),
          str([c for c in FORBIDDEN if c in src]), "palette")
    check("single theme (no light-scheme override)", "prefers-color-scheme" not in m.INDEX_CSS, "", "palette")
    for token, value, group in [
        ("--bg", "#14120f", "palette"), ("--bg-card", "#1f1b16", "palette"),
        ("--border", "#332c23", "palette"), ("--fg", "#ede5d8", "palette"),
        ("--fg-muted", "#9e9282", "palette"), ("--accent", "#d4a359", "palette"),
        ("--accent-fg", "#181512", "palette"), ("--brass", "#544735", "palette"),
        ("--chip-bg", "#241f1a", "palette"), ("--chip-border", "#383027", "palette"),
        ("--chip-fg", "#8a7e6f", "palette"), ("--chip-sel-bg", "#3a2f1e", "palette"),
        ("--chip-sel-border", "#d4a359", "palette"), ("--chip-sel-fg", "#ede5d8", "palette"),
        ("--snap-bg", "#26211a", "palette"), ("--snap-fg", "#9e9282", "palette"),
        ("--pill-active-bg", "#e6ded1", "palette"), ("--pill-active-fg", "#1c1813", "palette"),
        ("--danger", "#c86446", "palette"), ("--label-fg", "#8f8270", "palette"),
    ]:
        check(f"token {token}", f"{token}: {value}" in m.INDEX_CSS, "", group)
    check("brass search border + focus ring",
          "border: 1px solid var(--brass)" in m.INDEX_CSS and "box-shadow: 0 0 0 2px var(--brass)" in m.INDEX_CSS,
          "", "palette")
    check("tokens injected into engine pages", m.INLINE_EVIDENCE_CSS.count(m.THEME_TOKENS) == 2, "", "palette")

    # --- UI <-> engine contract
    for fragment, group in [
        ("--emit={emit}", "contract"), ("--save-dir={data_dir}", "contract"),
        ("--json-profile={profile}", "contract"), ("--search={','.join(sources)}", "contract"),
        ('data.replace(b"</body>"', "contract"),
    ]:
        check(f"engine contract kept: {fragment}", fragment in src, "", group)
    check("report key helper (base)", m.html_report_key("alpha-raw-html.html") == "alpha-raw-html", "", "contract")
    check("report key helper (dated ladder)",
          m.html_report_key("beta-raw-html-2026-09-10-1.html") == "beta-raw-html-2026-09-10-1", "", "contract")
    check("json pairing (base)", m.json_name_for_html("alpha-raw-html.html") == "alpha-raw.json", "", "contract")
    check("json pairing (dated)",
          m.json_name_for_html("beta-raw-html-2026-09-10-1.html") == "beta-raw-2026-09-10-1.json", "", "contract")
    check("key -> json", m.report_key_to_json_name("beta-raw-html-2026-09-12") == "beta-raw-2026-09-12.json",
          "", "contract")
    check("api/reports payload shape",
          set(reports[0]) == {"slug", "html", "title", "mtime", "size", "has_json"}, str(set(reports[0])), "contract")
    check("api/sources payload shape",
          set(m._list_sources()[0]) == {"key", "label", "available"}, str(set(m._list_sources()[0])), "contract")

    return index


def http_checks(m, data: Path) -> None:
    handler = lambda *a, **kw: m.Last30daysHandler(*a, data_dir=data, **kw)  # noqa: E731
    m.Last30daysHandler.log_message = lambda *a, **kw: None  # keep the harness output clean
    httpd = http.server.HTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    def get(path: str) -> tuple[int, str]:
        try:
            with urllib.request.urlopen(base + path, timeout=10) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, ""

    def delete(path: str) -> int:
        req = urllib.request.Request(base + path, method="DELETE")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status
        except urllib.error.HTTPError as exc:
            return exc.code

    try:
        status, index = get("/")
        check("GET / serves the console", status == 200 and 'class="topic-card"' in index, str(status), "http")
        status, body = get("/api/health")
        check("GET /api/health", status == 200 and json.loads(body)["report_count"] == 5, body, "http")
        status, body = get("/api/sources")
        check("GET /api/sources lane count", status == 200 and len(json.loads(body)) == len(m.SOURCE_TABS),
              body[:80], "http")
        status, body = get("/api/reports")
        check("GET /api/reports entries", status == 200 and len(json.loads(body)) == 5, body[:80], "http")

        def card(topic: str) -> dict:
            return next(g for g in m.list_topic_groups(data) if g["topic"] == topic)

        beta = card("beta")
        slug = beta["snapshots"][0]["slug"]
        status, body = get(f"/report/{slug}/")
        check("report page carries injected evidence", status == 200 and 'class="evidence-section"' in body
              and "Raw Evidence" in body, str(status), "http")
        status, body = get(f"/report/{slug}/evidence")
        check("evidence page groups by source", status == 200 and 'class="source-group"' in body, str(status), "http")
        check("evidence page is themed warm", "#d4a359" in body, "", "http")
        status, _ = get("/report/does-not-exist/")
        check("unknown report is a 404", status == 404, str(status), "http")

        # snapshot delete: one report + its sidecar
        victim = beta["snapshots"][1]["slug"]
        check("DELETE removes report + evidence", delete(f"/api/reports/{victim}") == 200
              and not (data / f"{victim}.html").exists()
              and not (data / m.report_key_to_json_name(victim)).exists(), "", "http")
        check("deleted run is gone from the index", victim not in get("/")[1], "", "http")
        check("its card keeps the other runs", len(card("beta")["snapshots"]) == 2, "", "http")

        # topic delete: fan out over every snapshot of the card
        remaining = [s["slug"] for s in card("beta")["snapshots"]]
        codes = [delete(f"/api/reports/{s}") for s in remaining]
        check("topic delete fans out over its snapshots", codes == [200] * len(remaining), str(codes), "http")
        check("emptied topic card disappears", "Beta Topic" not in get("/")[1], "", "http")
        check("health reflects the deletions", json.loads(get("/api/health")[1])["report_count"] == 2, "", "http")
    finally:
        httpd.shutdown()
        httpd.server_close()


def main() -> int:
    global VERBOSE, PATTERN
    ap = argparse.ArgumentParser(description="self-test for scripts/serve.py")
    ap.add_argument("-v", "--verbose", action="store_true", help="print every check")
    ap.add_argument("-k", dest="pattern", default=None, help="only run checks whose name matches")
    args = ap.parse_args()
    VERBOSE, PATTERN = args.verbose, args.pattern

    if not SERVE.is_file():
        print(f"harness error: {SERVE} not found", file=sys.stderr)
        return 2
    spec = importlib.util.spec_from_file_location("serve", SERVE)
    if spec is None or spec.loader is None:
        print(f"harness error: cannot load {SERVE}", file=sys.stderr)
        return 2
    serve = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(serve)

    with tempfile.TemporaryDirectory(prefix="serve-selftest-") as tmp:
        data = build_library(Path(tmp))
        static_checks(serve, data)
        http_checks(serve, data)

    print(f"\n{len(CHECKS) - len(FAILURES)}/{len(CHECKS)} checks passed")
    if FAILURES:
        print("failed: " + ", ".join(FAILURES))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
