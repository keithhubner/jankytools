# pr-review

A localhost dashboard that summarises the open pull requests awaiting your
review. It pulls every PR where you're a requested reviewer, runs a short Claude
analysis over each diff (risk level, one-line summary, things to check), layers
in CI status and Checkmarx code-scanning findings, and renders it all as a
filterable HTML page with a small Python web server in front for re-running,
notes and ignore toggles.

Pure Python 3 stdlib for the server; the generator shells out to the `gh` and
`claude` CLIs.

## What's here

| File | Purpose |
|------|---------|
| `pr-review-summary.sh` | The generator. Fetches PRs via `gh`, runs Claude per diff, writes `pr-review-summary.{md,html}`. Embeds the analysis/render logic in Python. |
| `pr-review-server.py` | Localhost HTTP server for the dashboard: serves the HTML and exposes `/api/{status,logs,trigger,notes,ignored,clear-cache}`. |
| `Dockerfile`, `docker-compose.yml`, `entrypoint.sh` | Containerised run (bundles `gh` + the Claude CLI). |

Generated output and runtime state (`*.html`, `*.md`, the `*.json` caches,
`*.log`, `*.pid`, `*.port`) are git-ignored — they're recreated on each run.

## Requirements

- Python 3
- [`gh`](https://cli.github.com/) — authenticated (`gh auth login`)
- [`claude`](https://github.com/anthropics/claude-code) CLI — authenticated
- Optional: the `markdown` PyPI package for nicer HTML (a built-in fallback
  converter is used if it's absent)

## Run

Generate the report once:

```bash
./pr-review-summary.sh
```

Serve the dashboard (binds `127.0.0.1:8787`; the page's **Re-run** button
triggers the generator):

```bash
python3 pr-review-server.py
```

Set `PORT` to bind `0.0.0.0:$PORT` instead (e.g. inside Docker). Note this
exposes the dashboard — which can trigger Claude runs using your credentials —
to the network, so only do it on a trusted host.

### As a systemd user service

```ini
# ~/.config/systemd/user/pr-review-server.service
[Unit]
Description=PR Review Summary dashboard server
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/jankytools/pr-review
ExecStart=/usr/bin/python3 %h/jankytools/pr-review/pr-review-server.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable --now pr-review-server.service
```

### Docker

```bash
docker compose up --build
```

## Notes

- Analyses are cached per PR by diff hash, so re-runs only re-analyse PRs whose
  diff changed. Use **Clear cache** in the UI to force a full re-analysis.
- PRs labelled `major-update` or `security` additionally get a breaking-changes
  investigation that researches release notes and greps the repo for impact.
- The dashboard filters by repo, author and risk level, and supports per-PR
  notes and an ignore toggle (ignored PRs auto-resurface when their diff
  changes).
