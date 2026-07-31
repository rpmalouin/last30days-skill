# last30days-skill — Memory File

**Version**: 3.18.4 | **Python**: >=3.12 | **Tests**: 2700+ | **Coverage gate**: 84% | **License**: MIT

---

## Identity

Multi-source AI agent research engine — slash command `/last30days <topic>` that searches 14+ platforms (Reddit, X, YouTube, TikTok, HN, Polymarket, GitHub, Digg, arXiv, Techmeme, LinkedIn, StockTwits, Perplexity, web) and synthesizes results by real human engagement. Product is the Skill (SKILL.md), not the CLI.

**Key mantra**: Slash-command UX first. Every engine flag must be documented in SKILL.md or the model won't know it exists. CLI invocation is dev/fallback only.

---

## Directory Map

```
/ (repo root)
├── skills/last30days/
│   ├── SKILL.md                 # Canonical runtime spec (1400+ lines) — model reads this
│   └── scripts/
│       ├── last30days.py        # CLI entry point (3614 lines), ~50 flags
│       ├── lib/                 # Engine library (88 files)
│       │   ├── pipeline.py      # v3 orchestration (4160 lines)
│       │   ├── schema.py        # Core data model dataclasses
│       │   ├── planner.py       # LLM-first query planning
│       │   ├── render.py        # Cluster-first rendering (3550 lines)
│       │   ├── doctor.py        # Unified health surface (1693 lines)
│       │   ├── setup_wizard.py  # First-run setup (1118 lines)
│       │   ├── discovery_handoff.py  # Checkpointed protocol
│       │   ├── env.py           # Env/credential management (1295 lines)
│       │   ├── http.py          # HTTP utilities (stdlib only)
│       │   ├── store.py         # SQLite research store
│       │   ├── fusion.py        # Weighted Reciprocal Rank Fusion
│       │   ├── cluster.py       # MMR greedy clustering
│       │   ├── relevance.py     # Token-overlap relevance scoring
│       │   ├── rerank.py        # Cross-source reranking + confidence floor
│       │   ├── dedupe.py        # N-gram near-duplicate detection
│       │   ├── grounding.py     # Entity verification
│       │   ├── dates.py         # 30-day window date utilities
│       │   └── vendor/bird-search/  # Vendored X/Twitter scraper (Node.js)
│       ├── briefing.py          # Daily/weekly digest generator
│       └── watchlist.py         # Scheduled topic monitoring
├── scripts/
│   └── serve.py                 # Docker web server (stdlib-only, 810+ lines)
├── Dockerfile                   # Python 3.12-slim container build
├── entrypoint.sh                # Container entrypoint: research (HTML+JSON), web server
├── docker-compose.yaml          # Port 8080, RESEARCH_TOPIC, SOURCES, RESEARCH_INTERVAL_HOURS
├── .env                         # DATA_PATH, PORT, RESEARCH_TOPIC, SOURCES
├── tests/                       # 190 test files, pytest 9.1+
│   ├── conftest.py              # Auto-use: no arctic network, reset probe caches
│   ├── eval/                    # Research quality eval harness
│   └── hermes/                  # Hermes-specific tests
├── docs/solutions/              # Documented past problems (YAML frontmatter)
│   ├── architecture-patterns/   # Discovery checkpoint protocol, topic queue
│   ├── architecture/            # Search quality eval decisions
│   ├── conventions/             # Argparse truthiness
│   ├── design-patterns/         # Confidence floor pattern
│   ├── integration-issues/      # Digg CLI agent PATH setup
│   ├── logic-errors/            # Entity grounding, daemon threads
│   └── workflow-issues/         # Release consistency, towncrier lockstep
├── changelog.d/                 # Towncrier news fragments (never edit CHANGELOG.md)
├── .github/
│   ├── workflows/               # 9 workflows (validate, security, changelog-guard,
│   │                            #   prepare-release, tag-release, release, osv-scanner,
│   │                            #   scorecard, zizmor)
│   └── scripts/
│       └── prepare_release.py   # Lockstep version bump + towncrier
├── .grok-plugin/                # Grok plugin manifest (bare URL source)
├── .claude-plugin/              # Claude Code plugin manifest
├── .codex-plugin/               # Codex plugin manifest
├── gemini-extension.json        # Gemini CLI extension
├── CONCEPTS.md                  # Shared domain vocabulary
├── CONFIGURATION.md             # User-facing config reference
├── CHANGELOG.md                 # Release history (auto-generated)
├── CONTRIBUTING.md              # Contributor guide
└── per-host agent docs: AGENTS.md, CLAUDEMD, CODEBUDDY.md, GEMINI.md, QODER.md
```

---

## Architecture — Pipeline Flow

```
Topic → Plan → Subquery fan-out → Parallel source fetch → Normalize
  → Score (relevance + engagement + freshness + source quality)
  → Fusion (RRF) → Cluster (MMR) → Render (cluster-first)
```

### Research pipeline (topic-provided path)
1. **Plan** (`planner.py`): Builds `QueryPlan` from topic — resolves subqueries, sources, handles. LLM-first with deterministic fallback.
2. **Fan-out** (`pipeline.py`): Parallel `ThreadPoolExecutor` dispatch across all active sources. Each source has its own backend chain with failover.
3. **Normalize** (`normalize.py`): Raw source responses → canonical `SourceItem` format.
4. **Score** (`signals.py`, `relevance.py`): Per-item `local_relevance`, `freshness`, `engagement_score`, `source_quality`, `local_rank_score`.
5. **Ground** (`grounding.py`): Verifies items mention the primary entity. Decisive demotion for off-entity content.
6. **Fusion** (`fusion.py`): Weighted Reciprocal Rank Fusion (`RRF_K = 60`) — merges per-(subquery, source) streams. URL dedup, per-author caps.
7. **Cluster** (`cluster.py`): Greedy clustering around high-ranked leaders using MMR.
8. **Render** (`render.py`, 3550 lines): BADGE line, ranked evidence clusters, Top Community Comments (round-robin by within-platform rank), Best Takes, emoji-tree footer.

### Discovery path (no topic)
```
Sweep listings → Nominate → Confidence floor → Enrichment pass → Rank → Render
```
On reasoning hosts: 3-leg host-judged protocol (L-gather, model judges, 2-enrich). On headless: one-shot with deterministic heuristics.

### Source backend chains
- **X**: xai → bird (vendored) → xurl → xquik (unified single source)
- **Reddit**: keyless (RSS + shreddit + arctic-shift) with optional ScrapeCreators primary/backfill
- **YouTube**: yt-dlp (search + transcripts)
- **Web**: keyless floor: DuckDuckGo → Startpage → SearXNG

---

## Docker / Web Deployment

Deploy the engine as a containerized web app. Serves both the agent-synthesized prose report and the raw evidence items (threads, stories, items with URLs and engagement) on a styled web page.

### Files (zero engine surgery — only new files, no engine/lib changes)

| File | Purpose |
|------|---------|
| `Dockerfile` | Python 3.12-slim, no external deps (engine is stdlib-only), exposes 8080 |
| `entrypoint.sh` | If `RESEARCH_TOPIC` is set, runs engine twice (HTML + raw JSON). Then starts web server |
| `scripts/serve.py` | stdlib-only HTTP server. Routes, evidence injection, index page, research API |
| `docker-compose.yaml` | Port 8080, DATA_PATH volume, RESEARCH_TOPIC / RESEARCH_INTERVAL_HOURS env vars |

### How it works

1. **Startup**: container runs engine with `--emit=html` → `{slug}-raw-html.html` (prose report) and `--emit=json --json-profile=raw` → `{slug}-raw.json` (full evidence corpus)
2. **Index page** (`/`): lists all reports with links to Report (prose), Evidence (raw items), and a Delete button per report. Topic input + Research button at the top.
3. **Report page** (`/report/{slug}/`): serves the HTML file — server injects a collapsible **Raw Evidence** section at the bottom reading from the sibling JSON
4. **Evidence page** (`/report/{slug}/evidence`): full-screen view of all items grouped by source with colored badges, original URLs, engagement counters, author, container, snippet
5. **API**: research status tracking with polling, report deletion, trigger new runs

### Interactive features

- **Research bar** (top of index page): type any topic and click Research. Server POSTs to `/api/research`, polls `/api/research/status` every 2s, auto-reloads the page on completion. Shows a CSS spinner during the run.
- **Status persistence**: on page load, checks if research is already running (from container startup or another tab) and starts polling immediately.
- **Source tabs** (horizontal pill bar): all available sources shown as colored badges at the top of every page.
  - **Index page**: sources are toggleable. Click to deselect a source for the next research run; deselected sources get a dimmed outline instead of full color. Selected sources get a purple outline (`.sel` class). Only sources that differ from "all" are passed as `--search` to the engine.
  - **Evidence / report pages**: sources are filterable. Click a source to show only items from that source; other source groups and tabs are dimmed. Click the same source again to show all.
- **Source availability detection**: each source is checked at render time via `shutil.which` (CLI tools) and env var presence (API keys). Unavailable sources show dimmed with outline styling.
- **SOURCES env var**: set `SOURCES=reddit,x,youtube` in `.env` to restrict which source tabs appear. Unset or empty shows all 14 defaults. Also passed as `--search` to the engine on startup and scheduled runs.
- **Delete**: each report card has a red Delete button. Triggers `confirm()` dialog, then `DELETE /api/reports/<slug>`, removes both `.html` and `.json` files, reloads the page.

### Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Library index with research bar, source tabs, report list, delete buttons |
| `/report/{slug}/` | GET | Prose report + collapsible raw evidence with source filtering |
| `/report/{slug}/evidence` | GET | Full evidence drill-down with source filtering |
| `/api/reports` | GET | JSON report list |
| `/api/reports/<slug>` | DELETE | Delete a report and its evidence files |
| `/api/sources` | GET | JSON source list with availability booleans |
| `/api/research` | POST | Trigger research (body: `{"topic": "...", "sources": ["reddit","x"]}`) |
| `/api/research/status` | GET | Research status: `running`, `topic`, `slug`, `started_at`, `completed_at`, `exit_code` |
| `/api/health` | GET | Health check |

### Env vars

| Variable | Default | Description |
|----------|---------|-------------|
| `RESEARCH_TOPIC` | unset | Topic to research on startup (runs HTML + JSON emit) |
| `RESEARCH_INTERVAL_HOURS` | `0` | If > 0, re-runs research on a schedule (requires RESEARCH_TOPIC) |
| `LAST30DAYS_MEMORY_DIR` | `/data` | Save directory for reports |
| `SOURCES` | unset (all) | Comma-separated source keys to show in the UI (e.g. `reddit,x,youtube`). Filters which source tabs appear. Also passed as `--search` to engine on startup/scheduled runs. |
| `DATA_PATH` | `./data` | Host path mounted to `/data` in container |
| `PORT` | `8080` | Host port mapped to container port 8080 |

### Evidence data flow

- Engine saves `{slug}-raw-html.html` (agent prose) and `{slug}-raw.json` (raw `items_by_source`)
- `items_by_source` in the JSON is `dict[str, list[SourceItem]]` — full flat corpus keyed by platform
- Each `SourceItem` has `title`, `url`, `source`, `author`, `container`, `published_at`, `engagement` (platform-specific counters), `snippet`/`body`
- Server injects evidence into HTML by parsing the JSON, grouping items by source, rendering cards with links and engagement — **no engine changes**

### Save filename patterns

| Emit mode | Pattern | Example |
|-----------|---------|---------|
| `--emit=html` | `{slug}-raw-html.html` | `ai-agents-raw-html.html` |
| `--emit=json --json-profile=raw` | `{slug}-raw.json` | `ai-agents-raw.json` |

### Common commands

```bash
# Build and run with default topic
RESEARCH_TOPIC="AI agents" docker compose up --build

# Run with scheduled re-research
RESEARCH_TOPIC="AI agents" RESEARCH_INTERVAL_HOURS=6 docker compose up

# Run web server only (serve existing reports)
docker compose up

# Trigger research via API
curl -X POST http://localhost:8080/api/research -d '{"topic":"AI agents"}'
```

---

## Key Engineering Conventions

### Coding standards
- **No comments in code** unless explicitly required
- `lib/__init__.py` must be bare package marker only (NO eager imports)
- Every `lib/*.py` call to `log.source_log(...)` must pass `tty_only=False`
- CLI-gated sources (Digg, YouTube) activate only when `shutil.which` resolves the binary on agent subprocess PATH

### Output contract (LAWs)
1. No `Sources:` block at end — emoji-tree footer IS the citation
2. No invented title line — BADGE is the title; `What I learned:` on line 3
3. No em-dashes or en-dashes — use ` - ` instead
4. No `##` section headers in body (comparison queries excepted)
5. Engine footer pass-through verbatim
6. No raw ranked evidence clusters — transform into prose
7. `--plan` is mandatory on named-entity topics
8. Cite readably per host
9. Weave community voice (2+ verbatim attributed comments)
10. First-party posts are first-class evidence
11. Discovery = three-command host-judged protocol

### Config priority
1. Process env (highest)
2. Project-scoped `.claude/last30days.env` (if `LAST30DAYS_TRUST_PROJECT_CONFIG=1`)
3. Global `~/.config/last30days/.env`
4. macOS Keychain (`last30days-*`)
5. `pass(1)` (`last30days/*`)
6. Defaults (lowest)

File permissions: `.env` → 0o600, config dir → 0o700.

---

## Testing

```bash
uv run pytest                          # full suite
uv run pytest tests/test_dedupe_v3.py  # single file
uv run pytest --cov                    # with coverage
```

- Coverage gate: 84% `fail_under` — never lower without documented justification
- Coverage omits `lib/vendor/*` and `dist/*`
- Two auto-use conftest fixtures: `_no_arctic_network()` (prevents accidental network calls), `_reset_probe_caches()` (clears health probes between tests)
- Test pattern: one file per major module (`test_pipeline_v3.py`, `test_planner_v3.py`, etc.)
- Contract tests: `test_plugin_contract.py`, `test_onboarding_contract.py`, `test_changelog_workflow.py`, `test_source_log_visibility.py`, `test_version_consistency.py`

---

## Release Process

```
Feature PR → add changelog.d/<issue>.<type>.md → merge to main
  ↓ (manual dispatch)
Prepare release (Actions) → opens release PR → merge → tag-release
  ↓
release.yml → build .skill + .mcpb → GitHub Release with attestation
```

**Rules**:
- NEVER edit `CHANGELOG.md` in a feature PR
- NEVER bump version strings outside a release PR
- `changelog-guard.yml` enforces both
- Version lockstep enforced by `tests/test_plugin_contract.py::test_versions_match_across_manifests`

---

## Important Gotchas

1. **Stale SKILL.md**: Claude Code has a stale-cache bug where SKILL.md loads from `marketplaces/` instead of versioned plugin cache. SKILL.md Step 0 has a self-check.
2. **npx skills add . -g -y**: Copies working tree to `~/.agents/skills/last30days/` — edits DON'T propagate. Re-run to sync, or symlink for live dev.
3. **Coverage floor must rise**: `fail_under = 84` is a floor, not a ceiling. PRs that drop it need documented justification.
4. **Source log visibility**: `tty_only=True` (default) silently drops log lines when stderr isn't a TTY. All production calls must pass `tty_only=False`.
5. **Onboarding consent-driven**: Two flows — Modal (Claude Code) and Non-Modal Prose (others). Setup subprocess does mechanical work only; consent lives in SKILL.md Step 0.
6. **Discovery protocol**: Engine gathers evidence, model judges. No API key needed for reasoning — the host model IS the provider.
7. **Nothing-solid**: Honest empty discovery result is a first-class outcome, not an error. Reports the closest sub-floor candidate as weak signal.
8. **Slash command vs CLI**: Slash form passes no shell mechanics (`| pbcopy` invalid). CLI form is `python3 scripts/last30days.py ...` for scripting only.
9. **Agent PATH for CLI-gated sources**: Digg, yt-dlp, etc. must be on the agent subprocess PATH, not merely on disk. `shutil.which` is the gate.

---

## Key Source Files Index

| File | Lines | Purpose |
|------|-------|---------|
| `skills/last30days/SKILL.md` | 1400+ | Canonical runtime spec (model-facing contract) |
| `skills/last30days/scripts/last30days.py` | 3614 | CLI entry point, dispatch hub |
| `skills/last30days/scripts/lib/pipeline.py` | 4160 | v3 orchestration, parallel dispatch |
| `skills/last30days/scripts/lib/render.py` | 3550 | Cluster-first rendering, LAW contract |
| `skills/last30days/scripts/lib/schema.py` | 999 | Core data model dataclasses |
| `skills/last30days/scripts/lib/planner.py` | 1026 | Query planning, LLM-first |
| `skills/last30days/scripts/lib/env.py` | 1295 | Environment, credentials, 6-layer priority |
| `skills/last30days/scripts/lib/doctor.py` | 1693 | Health surface (U1-U4 stack) |
| `skills/last30days/scripts/lib/setup_wizard.py` | 1118 | First-run setup, device auth |
| `skills/last30days/scripts/lib/discovery_handoff.py` | 976 | Checkpointed protocol, TTL enforcement |
| `skills/last30days/scripts/lib/reddit.py` | 804 | Reddit via ScrapeCreators |
| `skills/last30days/scripts/lib/dates.py` | 169 | Date utilities |
| `skills/last30days/scripts/lib/freshness.py` | 566 | Claim re-verification |
| `skills/last30days/scripts/lib/categories.py` | 289 | Category-peer subreddit map |
| `scripts/serve.py` | 810 | Docker web server: index, source tabs, evidence injection, research API, delete |
| `entrypoint.sh` | 30 | Container entrypoint: runs research (HTML+JSON) with --search flag, starts server |
| `Dockerfile` | 10 | Python 3.12-slim container build |
| `docker-compose.yaml` | 22 | Service definition: port 8080, SOURCES, RESEARCH_TOPIC, volume mount |
| `.env` | 10 | Data path, port, research topic, SOURCES template |

---

## Quick Reference

```bash
# Run engine directly (dev only)
python3 skills/last30days/scripts/last30days.py "query" --emit=compact

# Run tests
uv run pytest
uv run pytest --cov

# Install skill locally (syncs working tree to harness)
npx skills add . -g -y

# Release prep
uv run python .github/scripts/prepare_release.py --bump patch

# Build skill artifact for claude.ai
bash skills/last30days/scripts/build-skill.sh

# Docker: build and run with research + web server
RESEARCH_TOPIC="AI agents" docker compose up --build

# Docker: run with filtered sources
RESEARCH_TOPIC="AI agents" SOURCES="reddit,x,youtube,hackernews" docker compose up --build

# Docker: web server only (serve existing reports)
docker compose up

# Docker: trigger research via API
curl -X POST http://localhost:8080/api/research -d '{"topic":"AI agents"}'

# Docker: trigger research with specific sources via API
curl -X POST http://localhost:8080/api/research -d '{"topic":"AI agents","sources":["reddit","x"]}'

# Docker: check available sources via API
curl http://localhost:8080/api/sources
```