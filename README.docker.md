# last30days-skill — Docker Web App

Research any topic across **26 source lanes** (Reddit, X, YouTube, TikTok, Instagram, Hacker News, Bluesky, Truth Social, Polymarket, web, Xiaohongshu, GitHub, Perplexity, Threads, Pinterest, Digg, arXiv, Techmeme, Trustpilot, Amazon, Meta Ads, jobs, LinkedIn, private corpus, DripStack, Telegram) and read the results in a self-hosted web console.

Built on the [last30days research engine](https://github.com/mvanhorn/last30days-skill) by Matt Van Horn. This fork adds a containerized web server: a warm-dark research console over the engine's dated HTML brief and its raw evidence.

---

## Quick start

```bash
git clone https://github.com/rpmalouin/last30days-skill.git
cd last30days-skill

# Create config from template
cp .env.example .env
# Edit .env to set your research topic

# Build and run
docker compose up --build
```

Open http://localhost:8080 — the engine runs research on startup and serves the report library in the browser.

---

## The UI

The index is a temporal console, not a file list.

- **Trailing-window header** — the `last30days` wordmark, the active window (`Trailing 30 Days: Aug 22 – Sep 21`, derived from `WINDOW_DAYS` at request time, so it follows the clock), and the number of indexed reports.
- **Command box** — one control holding the `30d` scope chip, the topic input and the embedded `Research` action at its right edge. Enter submits. The hint underneath states what a re-run does to an existing topic.
- **Lane bar** — every lane as a muted chip, grouped `Code & Dev` / `Social` / `Articles & Papers`, each group labelled with `[all]` / `[none]` quick toggles. Selected lanes take the gold accent; lanes this container cannot reach are dashed and dimmed, with a tooltip. A run sends an explicit lane subset only when the selection differs from "all 26".
- **Topic cards** — one card per topic rather than one per file. The title is the topic itself (the engine's `last30days · ` prefix is stripped); the meta line reads `Indexed <day> · Covering last 30d`, plus `· N snapshots` when a topic has been run more than once.
- **Snapshot pills** — every run of that topic is a dated pill, newest first, with the newest active. Clicking a pill *selects* that run: it re-points the card's `Report`, `Evidence` and title links at it and updates the timestamp pill. The small `×` is separate from selection — it arms on the first click (`delete?`) and deletes on the second, disarming after 6 seconds or as soon as another pill is selected.
- **Action row** — `Report` · `Evidence` · the active snapshot's exact timestamp (`Sep 21, 2026 · 19:13`, container timezone), left-aligned on every card.
- **Card Delete** — top-right on every card, matching across single and aggregated cards. On a topic card it removes the whole topic after asking `Delete topic and all N snapshots?`; on a single-run card it asks `Delete this report and its evidence?`.
- **Report + evidence views** — `/report/{slug}/` renders the engine's prose brief with a collapsible raw-evidence block injected before `</body>`; `/report/{slug}/evidence` is the full drill-down grouped by source. Both use the same lane bar, where a chip filters items by source.

### Design system

Warm dark, one theme (no light-scheme variant). Every colour is a token defined in `THEME_TOKENS` in `scripts/serve.py`:

| Token | Value | Role |
|---|---|---|
| `--bg` | `#14120f` | espresso page background |
| `--bg-elev` / `--bg-card` | `#1a1613` / `#1f1b16` | elevated surfaces / roasted-umber cards |
| `--fg` / `--fg-muted` / `--fg-subtle` | `#ede5d8` / `#9e9282` / `#8a7e6f` | linen text / sandstone muted text and timestamps / dimmest labels |
| `--label-fg` | `#8f8270` | category labels and `[all]` / `[none]` |
| `--accent` / `--accent-soft` / `--accent-hover` / `--accent-fg` | `#d4a359` / `#e3bd85` / `#e0b26a` / `#181512` | burnished gold; espresso text on gold |
| `--border` / `--border-soft` / `--border-hover` / `--brass` | `#332c23` / `#2a241d` / `#443a2d` / `#544735` | card borders and separators; brass search border + focus ring |
| `--chip-bg` / `--chip-border` / `--chip-fg` | `#241f1a` / `#383027` / `#8a7e6f` | lanes at rest |
| `--chip-sel-bg` / `--chip-sel-border` / `--chip-sel-fg` | `#3a2f1e` / `#d4a359` / `#ede5d8` | selected lanes |
| `--snap-bg` / `--snap-fg` | `#26211a` / `#9e9282` | inactive snapshot pills |
| `--pill-active-bg` / `--pill-active-fg` | `#e6ded1` / `#1c1813` | active snapshot pill (parchment) |
| `--danger` | `#c86446` | terracotta delete hover |

The tokens are emitted twice: into the index/evidence pages, and at the top of the block injected into engine-rendered report pages. That second emission is deliberate — upstream's report CSS declares its own cold, purple-accented palette, but it is entirely variable-driven with no hardcoded colour declarations, so the injected `:root` (the last `<style>` in the document) repaints the whole report page in the fork's theme without editing a byte of engine output.

---

## Supported sources

Reddit · X/Twitter · YouTube · TikTok · Instagram · Hacker News · Bluesky · Truth Social · Polymarket · Web · Xiaohongshu · GitHub · Perplexity · Threads · Pinterest · Digg · arXiv · Techmeme · Trustpilot · Amazon · Meta Ads · Jobs · LinkedIn · private corpus · DripStack · Telegram

`stocktwits` is deliberately absent: the engine's CLI rejects that key, so any lane subset containing it aborted the run.

Configure which lanes appear via `SOURCES` in `.env` (leave it empty for all 26). Availability is auto-detected per lane — the same gates the engine uses (API keys, CLI tools on `PATH`) — and unavailable lanes render dashed and dimmed rather than disappearing.

---

## Configuration

Copy `.env.example` to `.env` and edit:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `RESEARCH_TOPIC` | unset | Topic to research on container start |
| `SOURCES` | unset (all) | Comma-separated lane keys to show (e.g. `reddit,x,youtube`). **No spaces** after commas. |
| `SCRAPECREATORS_API_KEY` | unset | Required for reliable Reddit/TikTok/LinkedIn results (keyless Reddit is rate-limited to HTTP 429) |
| `RESEARCH_INTERVAL_HOURS` | unset | Re-run research on a schedule |
| `DATA_PATH` | `./data` | Host directory mounted to `/data` for report storage |
| `PORT` | `8080` | Host port mapped to the web UI |

Example `.env`:

```
DATA_PATH=./data
PORT=8080
RESEARCH_TOPIC=AI coding agents
SOURCES=reddit,x,youtube,hackernews,github
SCRAPECREATORS_API_KEY=your_key_here
```

### API keys and CLI tools

Lanes that need credentials fall back gracefully when not configured — they simply return nothing, and the UI marks them unavailable. Set any of these in `.env` or export them before `docker compose up`:

| Source | Required |
|--------|----------|
| Reddit | `SCRAPECREATORS_API_KEY` (paid) or keyless fallback (RSS + scraping) |
| X/Twitter | `XAI_API_KEY`, `XQUIK_API_KEY`, or `bird` CLI installed |
| YouTube | `yt-dlp` (installed by the Dockerfile) |
| GitHub | `gh` CLI or `GITHUB_TOKEN` |
| TikTok / LinkedIn / Instagram / Threads / Pinterest / Meta Ads / Telegram | `SCRAPECREATORS_API_KEY` |
| Perplexity | `PERPLEXITY_API_KEY` |
| Digg / arXiv / Techmeme / Trustpilot | respective CLI tool on `PATH` |
| Private corpus | `LAST30DAYS_CORPUS_DIRS` |
| HN / Polymarket / Web / Jobs / DripStack | keyless (always work) |

> **Note**: the Docker build requires the engine at `skills/last30days/` in the repo. It is upstream's code, unmodified — `git diff v3.25.0 HEAD -- skills/last30days/` must stay empty, and engine updates arrive by merging an upstream tag (`git fetch upstream --tags && git merge vX.Y.Z`), not by editing it here.

---

## Routes

| Route | Description |
|-------|-------------|
| `/` | Library index — window header, command box, grouped lane bar, topic cards with snapshot pills |
| `/report/{slug}/` | Engine prose report + injected collapsible raw evidence with source filtering |
| `/report/{slug}/evidence` | Full evidence drill-down grouped by source |
| `DELETE /api/reports/{slug}` | Deletes that report and its evidence JSON → `{status, slug, files}` |
| `/api/reports` | JSON report list — one entry per report: `slug`, `html`, `title`, `mtime`, `size`, `has_json` |
| `/api/sources` | JSON lane list — `key`, `label`, `available` |
| `/api/research` | POST to trigger a research run (`{topic, sources?}`) → 202 |
| `/api/research/status` | GET research status (poll for completion) |
| `/api/health` | Health check — `{status, report_count}` |

Topic grouping, snapshot pills and timestamps are **view-data computed in the server for the page**: `/api/reports` keeps its flat, one-entry-per-report shape for API consumers.

---

## API usage

```bash
# Trigger research
curl -X POST http://localhost:8080/api/research \
  -d '{"topic":"AI agents"}'

# Trigger research with specific lanes
curl -X POST http://localhost:8080/api/research \
  -d '{"topic":"AI agents","sources":["reddit","x"]}'

# Poll status
curl http://localhost:8080/api/research/status

# List available lanes
curl http://localhost:8080/api/sources

# Delete a report and its evidence
curl -X DELETE http://localhost:8080/api/reports/ai-agents-raw-html-2026-09-21
```

Deleting a whole topic from the UI issues one `DELETE /api/reports/<slug>` per snapshot — the API stays single-report, the cardinality lives in the markup.

---

## Architecture

`scripts/serve.py` is a single-file Python app using only the standard library — zero dependencies. It serves the engine's dated HTML reports, injects raw evidence from the sibling JSON file, and renders the console (server-side HTML + inline CSS/JS, no build step, no framework).

No modifications were made to the engine (`last30days.py` or any `lib/` module). The Docker deployment is entirely additive.

```
docker compose up
  │
  ├── entrypoint.sh
  │     ├── python3 last30days.py <topic> --emit=html          → {topic}-raw-html[-YYYY-MM-DD[-N]].html
  │     └── python3 last30days.py <topic> --emit=json --json-profile=raw → {topic}-raw[-YYYY-MM-DD[-N]].json
  │
  └── python3 scripts/serve.py /data --port 8080
        ├── GET    /                          → index (topic cards from list_topic_groups())
        ├── GET    /report/{slug}/            → engine HTML + evidence block injected before </body>
        ├── GET    /report/{slug}/evidence    → evidence page
        ├── DELETE /api/reports/{slug}        → removes the report and its JSON
        └── POST   /api/research              → triggers an engine run in a background thread
```

The engine's own report pages carry their own stylesheet; the fork injects its theme tokens into them at serve time rather than rewriting engine output.

---

## Operations

```bash
# Rebuild and swap the running container
docker compose build && docker compose up -d
```

- With `RESEARCH_TOPIC` set, the entrypoint runs the startup research pass **before** the server binds, so a recreate costs roughly two minutes of UI downtime and spends ScrapeCreators credits while that key is set.
- Before rebuilding, keep the running image as a rollback point: `docker tag last30days-last30days:latest last30days-last30days:prev-$(git rev-parse --short HEAD)`. Restoring is a retag back to `latest` plus a recreate — no rebuild.
- There is **no authentication** on the UI. Keep it LAN-only, or put a proxy in front of it.
- Sandbox a change before touching the live container: build a scratch tag and run it on a loopback port with a **fresh copy** of the data directory. A stale copy makes the engine write the dated filename variant instead of the base name and skews what the topic cards show.
- Each UI research run writes up to two report keys (the base name plus a dated one when the base is taken), so a topic that is run repeatedly legitimately shows several snapshot pills.

---

## Development

```bash
# Run engine directly (no Docker)
python3 skills/last30days/scripts/last30days.py "topic" --emit=compact

# Run the upstream test suite (engine; Python 3.12 via uv)
uv run pytest
uv run pytest --cov

# Run the web server locally against a data directory
python3 scripts/serve.py /path/to/data --port 8080 --bind 127.0.0.1
```

The fork ships no test suite of its own. The UI↔engine contract that matters when the engine is bumped — CLI flags, report filenames (base and dated ladder), the raw JSON `items_by_source` shape, and the `</body>` injection anchor — is small and is re-checked by hand, then by one real pass in a throwaway container.

---

## Credits

Research engine by [Matt Van Horn](https://github.com/mvanhorn). Docker web UI and research console by [rpmalouin](https://github.com/rpmalouin).

License: MIT
