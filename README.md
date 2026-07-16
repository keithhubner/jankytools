# jankytools

A small collection of personal, single-purpose tools. Each lives in its own
subdirectory with its own README.

## Tools

- **[replanish](replanish/)** — a tiny localhost-only web app to browse, read and
  copy the plan files Claude Code writes to `~/.claude/plans/`, so you can
  replenish a new session with an old plan. Pure Python 3 stdlib, no dependencies.
  Run: `python3 replanish/server.py`
- **[pr-review](pr-review/)** — a localhost dashboard summarising the open PRs
  awaiting your review: pulls them via `gh`, runs a short Claude analysis per
  diff (risk, summary, checks), adds CI and Checkmarx findings, and renders a
  filterable HTML page. Run: `python3 pr-review/pr-review-server.py`

## License

MIT — see [LICENSE](LICENSE).
