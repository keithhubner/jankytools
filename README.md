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
- **[noggin](noggin/)** — a simple mind map tool. One central idea, branches
  laid out automatically to either side, keyboard-first editing, drag to move,
  collapse, undo, save/open `.noggin` files, and export to JPEG or a Markdown
  outline, find, copy/paste of branches and a version history. Saves as you go,
  one JSON file per map. Python 3 stdlib only. Runs on <http://127.0.0.1:8791>.
  Run: `python3 noggin/server.py`, or `noggin/install.sh` to install it as a
  background service with an app-launcher entry that opens it in its own window.

## License

MIT — see [LICENSE](LICENSE).
