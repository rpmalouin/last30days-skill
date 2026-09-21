# last30days-skill (rpmalouin fork) — Memory File

**Engine**: upstream tag `v3.25.0` (unmodified) · **Python** >=3.12, stdlib-only · **License**: MIT (upstream)
**Upstream**: `mvanhorn/last30days-skill` (public) · **Fork**: `rpmalouin/last30days-skill` (private, `origin`)
**Re-based onto upstream history**: 2026-09-21

Read this before changing anything here.

---

## What this repo is

Upstream's repository at tag `v3.25.0` **plus the fork's container UI**. That is the whole
delta — `git diff v3.25.0 HEAD` names 8 files (+1380 / −333); everything else is upstream's.

```
A  .env.example          A  entrypoint.sh           A  README.docker.md
A  Dockerfile            A  scripts/serve.py        A  FORK.md
A  docker-compose.yaml   A  MEMORY.md               M  .skillignore  (+4 lines)
```

(`README.md` and its six translations are upstream's again — see the test-suite section.)

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

Do not edit `docs/`, `tests/`, `.github/`, `CHANGELOG.md` or `README.md`: those are upstream's,
and changes there turn every future merge into a fight. `README.md` in particular is asserted on
by upstream's own doc-contract tests, so the fork's deployment documentation lives in
`README.docker.md` instead. The fork's `.skillignore` delta (4 lines) is the remaining deliberate
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

The previous build's image was **not** retained — `docker compose build` moved the tag and the
untagged image was reclaimed, so there is no `local-prev-*` rollback tag for this one. Roll back by
rebuilding from the archived line (tag present locally and on the fork):

```bash
git switch --detach docker-ui-v3.18.4 && docker compose build \
  && docker compose create --force-recreate && docker start last30days-runner
```

---

## Sandbox verification recipe (never test against the live container)

```bash
docker build -t last30days:selftest-<ver> .
mkdir -p /tmp/l30d-selftest/data
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

Expect exactly that one failure (plus 3 skips) on a clean root-run. Anything else is real.

Re-measured after the README fix (2026-09-21): **4,979 collected / 4,975 passed / 1 failed (the
root artifact above) / 3 skipped**. The numbers come from pytest's own cache
(`.pytest_cache/v/cache/nodeids` = 4,979, `lastfailed` = 1 node), because `addopts` in
`pyproject.toml` (`-q --tb=short`) captured no counts line in the log.

---

## Gotchas

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

## Open questions / next

1. **Auth in front of the UI: declined for now** — it stays LAN-only. Revisit if it ever has to be
   reachable from outside the LAN.
2. `.env` keeps `SOURCES=` empty, so all 26 lanes render as toggles; pin a subset there if the pill
   bar gets unwieldy.
3. The stale `last30days:selftest-v3.25.0` / `-lanes` images can be deleted whenever (gotcha 11).
