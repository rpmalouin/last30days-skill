# last30days-skill (rpmalouin fork) — Memory File

**Engine**: upstream tag `v3.25.0` (unmodified) · **Python** >=3.12, stdlib-only · **License**: MIT (upstream)
**Upstream**: `mvanhorn/last30days-skill` (public) · **Fork**: `rpmalouin/last30days-skill` (private, `origin`)
**Re-based onto upstream history**: 2026-09-21

Read this before changing anything here.

---

## What this repo is

Upstream's repository at tag `v3.25.0` **plus the fork's container UI**, minus upstream's CI. The
repository is **public** since 2026-09-21; `git diff v3.25.0 HEAD` names 26 files
(+1,482 / −864): 8 added, 8 modified, 10 deleted.

```
A  .env.example          A  entrypoint.sh           A  README.docker.md
A  Dockerfile            A  scripts/serve.py        A  FORK.md
A  docker-compose.yaml   A  MEMORY.md               M  .skillignore  (+4 lines)
M  README.md + its six translations — one Why-this-fork block, mirrored in all seven
D  .github/workflows/*.yml (nine files) + .github/dependabot.yml — this fork runs no CI
```

The engine under `skills/last30days/` is upstream's code and is **not** ours to edit:
`git diff v3.25.0 -- skills/` must stay empty. Engine changes arrive by syncing (below).

The previous state — a squashed 7-commit history pinning engine v3.18.4 with no merge path
to upstream (upstream's newer commits were not even in the object database) — is preserved
as branch `backup/docker-ui-v3.18.4` and tag `docker-ui-v3.18.4` (aa5575a).

Previous history in full: `/root/backups/last30days-fork-delta-v3.18.4_*.patch` and
`/root/backups/last30days-docker-ui_*.tar.gz`.

---

## Syncing with upstream (why the re-base happened)

```bash
git fetch upstream --tags
git merge v3.26.0            # or whichever tag; conflicts are ours to resolve, none expected
```

Then, in order:
1. Re-run the **UI ↔ engine contract check** (below) — static, cheap.
2. Run the **sandbox verification recipe** (below) — one real research pass through the UI.
3. Rebuild and swap the live container (a service restart — confirm with Ron first).

Do not edit `docs/`, `tests/`, `.github/` or `CHANGELOG.md`: those are upstream's, and changes
there turn every future merge into a fight. `README.md` is a special case — it carries exactly one
fork-owned block (the **Why this fork** section under the language nav line) and nothing else, and
the same block is mirrored into the six translations, because
`tests/test_readme_translations.py` asserts element parity across all seven files. A merge conflict
there resolves to upstream's text plus our block. The fork's deployment documentation lives in
`README.docker.md`. The fork's `.skillignore` delta (4 lines) is the remaining deliberate
divergence — re-apply it if a merge conflicts.

---

## UI ↔ engine contract (verify after EVERY engine bump)

`scripts/serve.py` is a stdlib HTTP server bolted onto the engine's CLI surface. It breaks
only if one of these moves:

| Contract | What serve.py / entrypoint.sh relies on |
|---|---|
| Flags | `--search=<k1,k2>`, `--emit=html`, `--json-profile=raw`, `--save-dir=<dir>` |
| Filenames | `{slug}-raw-html.html` and `{slug}-raw.json`, plus the dated ladder `-YYYY-MM-DD` / `-YYYY-MM-DD-N`; pairing via `html_report_key()` / `json_name_for_html()` / `report_key_to_json_name()` |
| Raw JSON | `Report.items_by_source: dict[str, list[SourceItem]]`, whose items carry `title, url, source, author, container, published_at, engagement, snippet/body` |
| HTML anchor | serve.py injects the evidence block by replacing the literal `</body>` in the engine's rendered HTML (`lib/html_render.py`) |
| Startup | entrypoint.sh runs the engine twice when `RESEARCH_TOPIC` is set (HTML, then raw JSON), then execs the server |

Verified against v3.25.0 on 2026-09-21: 12/12 static checks PASS, and a live pass through the
UI produced base-form *and* dated-form reports, both paired with their JSON, both rendering
the injected Raw Evidence section.

---

## Live deployment

| | |
|---|---|
| Container | `last30days-runner` (image `last30days-last30days`, built from this dir) |
| Port | `0.0.0.0:8095 -> 8080` (`.env` sets `PORT=8095`; the compose default is 8080) |
| Data | `DATA_PATH=/appdata/last30days/data` -> `/data` (reports + JSON + `.last30days-library.db`) |
| Env | `RESEARCH_TOPIC="AI agents"`, `SOURCES=` (empty = every tab), `SCRAPECREATORS_API_KEY` set |
| Auth | **none** on the UI. LAN-reachable; no Caddy/cloudflared route publishes it |
| Cost | a UI-triggered run spends ScrapeCreators credits while that key is set |

**Running 3.25.0** since 2026-09-21 (container recreated onto the rebuilt tag): engine reports
`3.25.0` inside the container, 26 lanes served, the 7 pre-existing reports still listed plus the
startup run. Note the startup research pass runs *before* the server binds, so a recreate costs
about two minutes of UI downtime.

**Live container carries all three UI passes** (swapped three times on 2026-09-21: 19:12Z temporal
index, 19:26Z card/lane interaction, 19:40Z warm theme). Current image
`last30days-last30days:latest` → `735f003e0801`, container `last30days-runner` recreated from this
tree, `scripts/serve.py` inside the container is the committed blob (sha256 `7e4f0c2f…`). Each
recreate costs **2m10s** of UI downtime because the startup research pass runs before the server
binds (two engine passes on `RESEARCH_TOPIC="AI agents"`, ~57s each, ScrapeCreators credits spent;
each swap stacked another AI agents snapshot — that card now shows 9 pills, and Ron's own test of
the card Delete took one report off the list, so `report_count` is not monotonic).

Rollback images kept for this stack (all on disk, retained by the `*:prev-*` pattern in
`PRUNE-RETENTION.md`) — retag and recreate, no rebuild:

| Tag | Holds | What it is |
|---|---|---|
| `last30days-last30days:prev-9abbac6` | `e88530c5b1fb` | interaction pass, BEFORE the warm theme |
| `last30days-last30days:prev-aca820a` | `f577bd88a923` | temporal index, before the interaction pass |
| `last30days-last30days:prev-7f71a8d` | `a96620cb34d2` | pre-UI-refactor (old cards + neon chips) |

Verified on the live instance after the third swap: `report_count` 11, 26 lanes and
`/api/sources` = `{key,label,available}` (no `color`), `/api/reports` still six keys, warm tokens
present in both the index and the injected block of the engine's report pages, zero cold/neon hex in
the live index, and computed colours in the browser — body `rgb(20,18,15)`/`rgb(237,229,216)`, card
`rgb(31,27,22)`/`rgb(51,44,35)`, Research button `rgb(212,163,89)` with `rgb(24,21,18)`, search border
`rgb(84,71,53)`, selected chip `rgb(58,47,30)`/`rgb(212,163,89)`, active pill
`rgb(230,222,209)`/`rgb(28,24,19)`, inactive pill `rgb(38,33,26)`/`rgb(158,146,130)`, labels
`rgb(143,130,112)`, timestamp pill `rgb(26,22,19)`/`rgb(158,146,130)`, `--accent` resolves to
`#d4a359` on a report page whose own stylesheet declares `#a855f7`. Scratch verification instances
(`selftest-ui`, `selftest-ui2`, `selftest-theme`) and their `/tmp` data copies were removed after
each swap; they are re-creatable with `docker build` + the sandbox recipe above.

The previous build's image was **not** retained — `docker compose build` moved the tag and the
untagged image was reclaimed, so the v3.25.0 engine-bump build has no `local-prev-*` rollback tag.
Roll back that one by rebuilding from the archived line (tag present locally and on the fork):

```bash
git switch --detach docker-ui-v3.18.4 && docker compose build \
  && docker compose create --force-recreate && docker start last30days-runner
```

---

## Sandbox verification recipe (never test against the live container)

```bash
docker build -t last30days:selftest-<ver> .
rm -rf /tmp/l30d-selftest/data && mkdir -p /tmp/l30d-selftest/data
cp -a /appdata/last30days/data/. /tmp/l30d-selftest/data/   # optional: exercises the grouped index
docker run -d --name last30days-selftest -p 127.0.0.1:18096:8080 \
  -v /tmp/l30d-selftest/data:/data -e LAST30DAYS_MEMORY_DIR=/data last30days:selftest-<ver>
curl -s 127.0.0.1:18096/api/health
# keyless sources only: no API credits spent, completes in seconds
curl -s -X POST 127.0.0.1:18096/api/research -H 'Content-Type: application/json' \
  -d '{"topic":"MCP servers","sources":["hackernews","github"]}'
# then: /api/reports, /report/<key>/ (must contain "Raw Evidence"), /report/<key>/evidence
docker rm -f last30days-selftest
```

Run a second pass with the same topic to exercise the **dated** filename path — that is the
case the UI once missed (all dated reports invisible), so it is the one worth re-proving.
Measured on v3.25.0: ~1.5s per emit, exit 0, 22 items across github+hackernews.

---

## Upstream test suite (baseline after the re-base)

`uv run --python 3.12 --group dev pytest -q` — 4,979 collected. Measured 2026-09-21 on the
re-based tree: **4,973 passed, 3 failed, 3 skipped** on the first run. Two of those failures came
from the fork having replaced `README.md` (upstream's own doc-contract tests assert on it:
`test_doc_security_contract.py::test_preflight_permission_contract_is_documented` wants
`--preflight` plus an exact sentence, `test_readme_translations.py` wants line 1 to be
`# /last30days` with the six translations mirroring the structure). Decision taken 2026-09-21:
upstream's `README.md` + translations were restored and the fork's deployment doc moved to
`README.docker.md`, which removes both.

The remaining failure is environment, not code:

| Test | Cause |
|---|---|
| `test_setup_wizard.py::TestWriteApiKey::test_unwritable_target_returns_false` | The fixture `chmod 0o500`s a dir and expects the write to fail; as root it succeeds. Proven both ways (root: write OK; uid 1000: `PermissionError`, test passes). The container runs as root too (`User` empty, `id` → uid 0), so it is inherent to a root-run, fork or not |

Expect exactly that one failure (plus 3 skips) on a clean root-run. Anything else is real — with one
deliberate exception now: after the workflows were deleted (2026-09-21) the three upstream
CI-contract files fail by design, because they assert on CI this fork does not have —
`tests/test_changelog_workflow.py`, `tests/test_scorecard_workflow.py`,
`tests/test_security_workflow.py` (16 between them: 7 + 5 + 4). Those are upstream's tests for
upstream's CI, kept rather than deleted so the tree stays mergeable; read them as "CI is absent
here", not as a regression.

Re-measured after the README fix (2026-09-21): **4,979 collected / 4,975 passed / 1 failed (the
root artifact above) / 3 skipped**. The numbers come from pytest's own cache
(`.pytest_cache/v/cache/nodeids` = 4,979, `lastfailed` = 1 node), because `addopts` in
`pyproject.toml` (`-q --tb=short`) captured no counts line in the log.

Re-measured after the workflow deletion (2026-09-21, HEAD `be38ca`+): **4,979 collected /
4,959 passed / 17 failed / 3 skipped** — the 16 CI-contract failures above plus the root artifact.

---

## Gotchas

0. **The public repo runs nothing.** Since 2026-09-21 it is **public**, with **pull requests
   disabled**, no support offered (`fork it and support your fork` in the README block +
   `FORK.md`), **all nine upstream workflows deleted** (`git rm .github/workflows/*.yml` — they had
   first been set to `disabled_manually`, but a disabled workflow in a public repo is still visible
   dead weight), Dependabot off (`.github/dependabot.yml` removed), and Issues off (Ron, 2026-09-21).
   Two repo-settings writes still cannot be done from this box: the PAT lacks `administration`
   scope, so every `PATCH /repos/...` returns 403 — topics stay empty and the run history cannot be
   cleared. The **description** is set (About panel, Ron, 2026-09-21): `Research any topic across 26
   source lanes and 14 platforms - self-hosted web UI for the last30days engine, with a topic box and
   a toggle per lane, and a dated HTML brief with its raw evidence. Wraps mvanhorn/last30days-skill.
   Personal fork: fork it and support your fork.` Treat repo-settings edits as UI clicks; the
   per-workflow disable endpoint does work (`PUT .../actions/workflows/<id>/disable`).

1. **The source toggles are a hardcoded mirror of the engine's registry.** `SOURCE_TABS` /
   `SOURCE_COLORS` / `_detect_source` in `scripts/serve.py` now carry all 26 canonical lanes
   (2026-09-21). Re-derive them from `pipeline.MOCK_AVAILABLE_SOURCES` + `SEARCH_ALIAS` after every
   engine bump instead of extending by hand. `stocktwits` is deliberately absent — the engine's
   `parse_search_flag` rejects it, so any toggle subset containing it aborted the run, and a single
   deselection was enough to trigger that.
2. **`container_name: last30days-runner` in the compose blocks a second instance.** A
   `docker compose -p selftest up` collides with the live container — use `docker run` for
   sandboxes, or drop `container_name`.
3. **`bytes.replace(b"</body>", ...)` in serve.py takes no count** — it replaces every
   occurrence. Harmless with the current renderer (one `</body>`), fragile if that changes.
4. **No authentication** on the UI, and it can spend credits. Keep it LAN-only or put auth in front.
5. The engine writes **`.last30days-library.db`** into the save dir (the 3.19+ library index).
6. **Python >=3.12**; the image is `python:3.12-slim` + `uv` + `yt-dlp`. `yt-dlp` gates the
   YouTube lane (`shutil.which` is the gate). The host's own `python3` is 3.10 — run the engine
   or its tests through `uv run --python 3.12`.
7. **`.env` is untracked and must stay that way** (holds `SCRAPECREATORS_API_KEY`).
   `opencode.jsonc` and `.claude/` are code-review-graph installer artifacts, kept untracked
   via `.git/info/exclude`.
8. `MEMORY.md` **is tracked** in this fork (the usual convention is to gitignore it) because the
   fork publishes it with the deployment.
9. Upstream's `AGENTS.md` is kept as-is; the code-review-graph block the installer had written
   there was dropped deliberately so it cannot conflict on every merge. CRG still works through
   Hermes's global MCP config, and the repo-local `opencode.jsonc` still carries it.
10. **The keyless web floor is unreachable from this network.** The `grounding` (Web) lane reports
   `source_status: unreachable` with 0 items — measured in the sandbox and in the live startup run,
   whose log carries `Some sources failed: grounding`. That is the engine's honest empty, not a UI
   fault; the badge stays green because the engine's own gate is `keyless_web_allowed`, true for a
   non-native-search host. `web` is not a lane key any more — tabs use canonical `grounding`
   (`web` is only a `--search` alias).
11. **Verification images accumulate.** `last30days:selftest-*` tags are scratch builds (about
   0.6 GB each) and are re-creatable with `docker build` from any commit; the live tag
   `last30days-last30days` is the only one the container follows.
12. **Start the sandbox from a FRESH data copy.** `cp -a` onto an old `/tmp/l30d-selftest/data`
   leaves earlier reports behind, so the engine's "first" run writes the dated ladder variant
   (`-YYYY-MM-DD-1`) instead of the base name and the card counts look wrong. `rm -rf
   /tmp/l30d-selftest/data` first (the recipe above now says so).
13. **The report ladder's suffix is not the run number.** The engine writes
   `{topic}-raw-html-YYYY-MM-DD` for the 1st run that day and `…-YYYY-MM-DD-N` for the (N+1)th,
   so `-1` is the SECOND run: `_snapshot_of()` adds one to the suffix before displaying it as
   `#2`. Two runs on one day otherwise render as two identical date badges.
14. **The library index groups by topic, and that view-data is not the API.** `list_topic_groups()`
   collapses every report key of one topic into a single card (`clean_topic_title()` strips the
   engine's `last30days · ` prefix, `_snapshot_of()` supplies day/run). `/api/reports` and
   `/api/sources` keep their original payload shape — do not push view-only fields into them.
15. **Interaction model of a topic card (client-side only, no endpoint of its own).** Pill bodies
   (`selectSnapshot`) switch the card's active snapshot and rewire `.act-report` / `.act-evidence` /
   `.topic-title` plus the `.action-meta` timestamp from the pill's `data-*`; the small `×`
   (`deleteSnapshot`) arms on the first click (`delete?`, class `armed`) and deletes on the second,
   disarming after 6s or as soon as another pill is selected. The top-right Delete
   (`deleteTopic`) reads `data-slugs` (a JSON array of every snapshot of the topic) and issues one
   `DELETE /api/reports/<slug>` per snapshot — cardinality stays in the markup, so the HTTP API is
   unchanged. Category `[all]`/`[none]` (`groupLanes`) mutate the same `selectedSources` map as the
   chips, via `ensureSelection()`: `null` still means "every lane".
16. **The theme lives in `THEME_TOKENS`, and the engine's report pages need it injected.** Every
   colour is a token; `THEME_TOKENS` is the single source and is emitted twice — in `INDEX_CSS`'s
   `:root` for the index/evidence pages, and at the top of `INLINE_EVIDENCE_CSS` for the block
   injected into the engine's own report pages. Upstream's report CSS declares its own cold/purple
   palette (`--accent: #a855f7`, `#7c3aed`, `#6d28d9`) but is 100% variable-driven with no hardcoded
   colour declarations, so our later `:root` block (the injected `<style>` is the last in the
   document) repaints the whole page warm — including inside `@media (prefers-color-scheme: light)`,
   which is why the tokens are mirrored there too. Never edit the engine's HTML on disk to retheme
   it; the purple strings that stay in the served page are dead declarations, and the computed
   colours are all warm. The app is now warm-dark ONLY (the light-scheme block was dropped).
17. **`/api/sources` returns `{key, label, available}` — the `color` field is gone** (with
   `SOURCE_COLORS` and the per-source CSS brand vars). It only ever fed the pre-refactor neon chips,
   nothing else consumed it (no test, script or doc enumerated it), and it carried the last purple
   in the tree. `/api/reports` is still the original six keys.

---

## Decisions

- **2026-09-21 — re-based onto upstream `v3.25.0`** instead of re-snapshotting `skills/` alone.
  The squashed history had no merge path, the pinned engine was 9 releases (7 weeks) behind, and
  two of the missed fixes are security-relevant to a service that renders engine HTML in a
  browser: v3.19.0's unsafe-scheme URL hardening (`javascript:` / `data:` links) and v3.25.0's
  scraped-title sentinel forging. Cost was one re-apply of 8 files; the payoff is that future
  releases are a plain merge.
- **2026-09-21 — took upstream's whole tree** (tests, CI, pyproject, LICENSE come back). The fork
  gains 227 test files, so engine behaviour is checkable rather than assumed.
- **2026-09-21 — verified in a selftest container on 127.0.0.1:18096**, live 8095 untouched.
- **2026-09-21 — restored upstream's `README.md`** and moved the fork's deployment doc to
  `README.docker.md`. Taking upstream's tree brought upstream's doc-contract tests with it, and
  two of them assert on `README.md`; keeping a fork README there would have meant a permanently
  red suite or permanently excluding tests — which would have thrown away the main reason for
  taking the tree at all. The fork keeps its deployment doc, just not at the contested path.
- **2026-09-21 — extended the UI's lanes to the engine's canonical 26** (delegated to dsh, diff-vs-intent
  gate `match` 0.81). Two fixes rode along: `stocktwits` dropped (the CLI rejects it, so a single
  deselection aborted any run) and `web` renamed to its canonical `grounding` so the evidence filter
  matches item sources.
- **2026-09-21 — swapped the live container onto v3.25.0** and verified from the running system:
  engine reports `3.25.0` inside the container, `GET /` 200, `/api/sources` returns 26 lanes,
  `/api/health` report_count 8 (the 7 pre-existing reports survived, plus the startup run).
- **2026-09-21 — pushed the re-based `main` to `origin`** with `--force-with-lease`, plus the backup
  branch and tag. Verified from the remote: `refs/heads/main` = c9570bf, `backup/docker-ui-v3.18.4`
  and `docker-ui-v3.18.4` = aa5575a.
- **2026-09-21 — added a Why-this-fork block to all seven READMEs** (English + translations, kept
  element-neutral and mirrored so the parity test still passes). The landing page no longer reads as
  upstream-only.
- **2026-09-21 — went public** with a `fork it and support your fork` line, pull requests disabled,
  the nine upstream workflows `disabled_manually`, and Dependabot off. It is a standalone repo
  (`fork: false, parent: null`), so the visibility flip was a normal, reversible change rather than
  a fork-network one-way door. A secrets sweep over all refs and all 12k objects came back clean
  first — no live credential value appears in any commit.
- **2026-09-21 — rebuilt the library UI around the trailing window** (fork-only, `scripts/serve.py`):
  the top bar carries the wordmark, the active window (`Trailing 30 Days: <start> – <end>`, derived
  from `WINDOW_DAYS`) and the indexed count; report cards became topic cards whose titles drop the
  engine's `last30days · ` prefix and whose meta reads `Indexed <day> · Covering last 30d`; a topic
  run repeatedly collapses into one card whose snapshots are date badges (newest first, per-snapshot
  delete); the multicoloured chip bar became muted zinc-800 chips grouped `Code & Dev / Social /
  Articles & Papers` with a single accent for selected lanes and dashed chips for lanes this
  container cannot reach (`SOURCE_GROUPS`, checked against `SOURCE_TABS` at import); the research
  input is one command box with the action embedded at its right edge and a `30d` scope chip, and
  Enter submits. Engine-facing behaviour is untouched (`/api/reports` and `/api/sources` payloads
  unchanged). Verified: 37 static assertions, then in-container end to end — two research passes on
  one topic produced the base + dated report keys and rendered as ONE card with two snapshot
  badges, report pages keep the injected Raw Evidence section, evidence pages render monochrome
  badges. The JEV diff gate returned `mismatch` (noul 0.45) on the patch against the intent; the
  diff is a large CSS/markup rewrite, so treat that as "review the diff, don't trust the label".
- **2026-09-21 — card and lane interaction pass** (same file): snapshot pills got an explicit
  active state (`bg-zinc-200 / text-zinc-950 / font-medium`, inactive `bg-zinc-800 / text-zinc-400 /
  border zinc-700/60`, both via `--pill-active-*` tokens with a light-mode inversion) and a pill body
  that SELECTS instead of navigating, so `Report`/`Evidence` open the selected run; the `×` became
  arm-then-confirm (no native dialog); the top-right `Delete` came back to aggregated cards and is
  topic-scoped (`data-slugs` → one DELETE per snapshot, prompt `Delete topic and all N snapshots?`);
  every card's action row is now `Report · Evidence · <exact timestamp>` (`.action-meta`, from
  `_exact_ts`, container-TZ); each category label carries muted 11px `[all]`/`[none]` lane toggles.
  Verified: 70 static assertions, DOM-level interaction tests against a COPY of the reports
  (selection rewires hrefs + timestamp, arm/disarm, `[none]` → 0 selected then `[all]` → 12, snapshot
  deletion and topic deletion actually removing files, live data untouched), computed-style checks in
  both themes, and a rebuilt container serving the same markup.
- **2026-09-21 — rethemed to a warm dark design system** (`THEME_TOKENS`, `scripts/serve.py`):
  espresso root `#14120f`, roasted-umber cards `#1f1b16` with brass `#332c23` borders, linen text
  `#ede5d8`, sandstone muted/timestamps `#9e9282`; the purple accent is replaced by burnished gold
  `#d4a359` (espresso `#181512` text on the Research button, hover `#e0b26a`); the search box border
  and its 2px focus ring are brass `#544735`; source chips are `#241f1a`/`#383027`/`#8a7e6f` at rest
  and `#3a2f1e`/`#d4a359`/`#ede5d8` when selected; category labels and `[all]`/`[none]` are `#8f8270`;
  snapshot pills are `#26211a`/`#9e9282` inactive and parchment `#e6ded1`/`#1c1813` active; Delete is
  muted at rest and terracotta `#c86446` on hover. Two deliberate side effects: the light-scheme
  block is gone (one warm-dark theme), and the dead `color` field left `/api/sources` (gotcha 17).
  Verified: 81 static assertions incl. a palette audit proving every colour in the stylesheet is in
  the warm set and no purple/red/cold neutral survives anywhere in the file; computed-style checks in
  a browser for every token above, plus real mouse-hover reads (Delete → `rgb(200,100,70)`, button →
  `rgb(224,178,106)`) and a real click into the search box (`rgb(212,163,89)` border + `rgb(84,71,53)`
  2px ring); the engine's report pages repaint warm because the injected `:root` wins by source order
  (accent resolves to `#d4a359` on a page whose own stylesheet declares `#a855f7`).
- **2026-09-21 — docs resynced to the rebuilt console.** `README.docker.md` was rewritten for the
  current UI (trailing window, command box, grouped lane bar with `[all]`/`[none]`, topic cards and
  snapshot pills, arm-to-confirm and topic-scoped delete), gained the token table for the warm
  design system and the reason the tokens are injected into engine-rendered pages, corrected the
  26-lane source list (no `stocktwits`), the route table (`DELETE /api/reports/{slug}`, the real
  `/api/reports` and `/api/sources` payload keys) and the stale `git checkout v3.18.4` engine note
  (the engine now arrives by merging an upstream tag), and added an Operations section (recreate
  downtime, `prev-*` rollback tags, sandbox-with-a-fresh-copy). `FORK.md` gained the same console
  description in "Why the fork exists" + the history entry. The vault project notes
  (`Homelab/02 Projects/last30days/…`, container `notes`) were updated through Hatchdoor MCP.
- **2026-09-21 — the console's checks now live in the repo**: `scripts/ui_selftest.py` (85 assertions,
  stdlib only, `-v` for one line per check, `-k <group>` to filter). It builds a synthetic report
  library in a temp dir — a singleton topic, a topic with three runs including the engine's same-day
  ladder suffix, a run with no JSON sidecar — and covers the temporal labels, grouping, pills,
  action rows, delete surface, lane bar, the warm-palette audit (every stylesheet colour must be a
  `THEME_TOKENS` value) and the engine contract (flags, filename ladder, `/api` shapes, `</body>`
  anchor), then starts the server on a loopback port and drives the HTTP surface including snapshot
  and topic deletes. 85/85 on the host's Python 3.10 and inside the shipped image (3.12). This
  replaces the ad-hoc `/tmp` harnesses.
- **2026-09-21 — the `Why this fork` block was rewritten in all seven READMEs.** That block is the
  fork's ONLY owned text in `README.md` and is mirrored into `README.fr/de/es/pt-BR/ja/zh-CN.md`; it
  now describes the console as it actually is (trailing window, cards per topic with selectable
  snapshot pills, lane bar grouped by source type, the self-test script, `README.docker.md` as the
  deployment doc) instead of the pre-refactor "topic box, per-lane toggles" wording. The FR/DE/ES/PT
  mirrors were also de-ASCII-fied — they had been written accent-folded while upstream's own text in
  those files is accented. Element parity holds exactly across all seven: 28 code fences, 23 code
  commands, 31 external link targets, identical per-line `|` table profile, 14 ordered items, and
  `tests/test_readme_translations.py` + `test_doc_security_contract.py` + `test_env_doc_contract.py`
  + `test_version_consistency.py` pass (16 tests). **Editing rule**: the block is element-neutral —
  adding a fence, table, ordered item or external link to it means adding it to all seven, and the
  relative-link set differs per file by design (each translation links to the other six, not itself).

## Open questions / next

1. **Auth in front of the UI: declined for now** — it stays LAN-only. Revisit if it ever has to be
   reachable from outside the LAN.
2. `.env` keeps `SOURCES=` empty, so all 26 lanes render as toggles; pin a subset there if the pill
   bar gets unwieldy.
3. The stale `last30days:selftest-v3.25.0` / `-lanes` images can be deleted whenever (gotcha 11).
