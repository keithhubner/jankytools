# Replanish

A tiny localhost-only web app to browse, read and copy the plan files Claude Code
writes to `~/.claude/plans/` — so you can replenish a new session with an old plan.
Pure Python 3 standard library — no `pip install`, no build step, works offline.

## Requirements

- **Python 3.7+** (uses only the standard library — no packages to install).
- A modern web browser.
- Some Claude Code plan files to browse (by default in `~/.claude/plans/`; you can
  point Replanish elsewhere via **⚙ Settings** or `--plans-dir`).

No build step, no virtualenv, no network access required (it runs entirely offline
on `127.0.0.1`).

## Run

```sh
python3 ~/jankytools/replanish/server.py
```

This opens `http://127.0.0.1:8799` in your browser automatically.

Options:

```sh
python3 server.py --port 9000          # use a different port
python3 server.py --plans-dir DIR      # override the plans directory for this run
python3 server.py --no-browser         # don't auto-open a browser
```

## Use

- **Search** filters by filename, title, and full body text as you type.
- **Date range** (with 7-day / 30-day / All quick buttons) filters by file
  modification time. **Sort** reorders the list.
- Click a plan to read it (rendered markdown; toggle **Raw** for the source).
- **Copy** puts the plan's raw markdown on your clipboard — paste it into a Claude
  session.
- **Copy path** puts the plan's absolute file path on your clipboard — paste it
  into a new session and ask Claude to read that file directly.
- **⚙ Settings** lets you change the plans directory if your plans live somewhere
  other than `~/.claude/plans`. The choice is saved to
  `~/.config/replanish/config.json` and used on the next launch. (A `--plans-dir`
  argument overrides the saved setting for that run only.)

### Deleting plans

Deletion is **permanent** (`os.remove`) — there is no trash or undo. Every delete
asks for confirmation showing how many plans will be removed.

- **Delete** (reading-pane toolbar) removes the plan you're currently viewing.
- **Bulk delete**: tick the checkbox on any rows, then **Delete selected** in the
  bar above the list.
- **Delete plans from the last N days** (5 / 10 / 30) removes every plan *modified
  within* that window.

The server binds to `127.0.0.1` only and guards against path traversal (it will
only ever read or delete `.md` files inside the configured plans directory).
