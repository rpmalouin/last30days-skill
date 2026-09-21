# FORK.md

**Fork of [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill)** (MIT).

- **Upstream** (`upstream` remote): `mvanhorn/last30days-skill` — public, very active (v3.25.0 at
  the time of this re-base, ~1,260 commits on `main`, releases roughly weekly). Read-only from
  here: never open an upstream PR, never push to it.
- **Fork** (`origin` remote): `rpmalouin/last30days-skill` — **private**, holds the published work.
- **Basis**: upstream tag `v3.25.0`, re-based 2026-09-21. `main` is upstream's history plus one
  commit of fork files; `git diff v3.25.0 HEAD` is the entire fork delta.

## Why the fork exists

The homelab wants a **browser console** for the engine: type a topic, toggle which sources get
searched, trigger and delete runs from a web page, browse the prose report and the raw evidence
items it came from. Upstream ships no server, no dashboard and no UI of any kind — the product is
the skill installed into an agent host. Everything the fork adds is that console.

## What the fork adds (the only fork-owned code)

| Path | Purpose |
|---|---|
| `scripts/serve.py` | stdlib HTTP server: index with research bar + source toggles, report page with inline evidence, evidence page, small JSON API, CSRF-free local use, delete |
| `entrypoint.sh` | container entrypoint: optional startup research (HTML + raw JSON), then exec the server |
| `Dockerfile` | `python:3.12-slim`, installs `uv` + `yt-dlp` (yt-dlp gates the YouTube lane) |
| `docker-compose.yaml` | service definition (published port, `DATA_PATH` volume, `SOURCES`, `RESEARCH_TOPIC`, `SCRAPECREATORS_API_KEY`) |
| `.env.example` | the documented knobs |
| `README.docker.md` | the fork's deployment doc. Upstream's `README.md` and its six translations are deliberately left untouched — upstream's doc-contract tests assert on them |
| `.skillignore` | +4 lines excluding the fork's files from the skill package |
| `MEMORY.md` | fork + deployment memory; read it before editing |

Nothing under `skills/last30days/` is modified. That is deliberate: it keeps upstream releases
mergeable (`git diff v3.25.0 -- skills/` empty is the invariant to preserve).

## Syncing

```bash
git fetch upstream --tags
git merge v3.26.0
```

Then follow "UI ↔ engine contract" and "Sandbox verification recipe" in `MEMORY.md`, and only then
swap the live container. The contract is small — flags, report filenames (base and dated), the raw
JSON shape, and the `</body>` injection anchor — so a bump is minutes when it holds, and obvious
when it does not.

## Support

This is a personal fork. **Pull requests are disabled and no support is offered — fork it and
support your fork.** Questions about the engine itself belong upstream, with
[mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill); this repository only
wraps it.

Nothing runs in this repository's Actions: all nine upstream workflows are
`disabled_manually` (the files are kept so upstream merges stay trivial) and Dependabot
version updates are off (`.github/dependabot.yml` removed, and pull requests are disabled
anyway).

## History

- **2026-08-01**: fork bootstrapped as a squashed snapshot of engine `v3.18.4` plus the container
  UI. Worked, but had no merge path to upstream — updating the engine meant re-snapshotting by
  hand and re-deriving the fallout.
- **2026-09-21**: re-based onto upstream's real history at `v3.25.0` and re-applied the fork files.
  From here, upstream releases arrive by merge. The old line is preserved as branch
  `backup/docker-ui-v3.18.4` and tag `docker-ui-v3.18.4` (aa5575a), locally and on the fork.
  Same day: the fork's source toggles were re-derived from the engine's canonical registry (26
  lanes), upstream's `README.md` was restored in favour of `README.docker.md`, the re-based `main`
  was force-pushed to `origin`, and the live container was rebuilt and swapped onto 3.25.0.
