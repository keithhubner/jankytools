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

## Run as a background service (systemd)

To keep Replanish running in the background (and restart it on failure / at login),
install it as a **systemd user service** — the same way the sibling `pr-review` app
is run.

Create `~/.config/systemd/user/replanish-server.service`:

```ini
[Unit]
Description=Replanish — browse Claude Code plan files
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/keithhubner/jankytools/replanish
ExecStart=/usr/bin/python3 /home/keithhubner/jankytools/replanish/server.py --no-browser
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

`--no-browser` is important here: as a background service it should not try to spawn
a browser. Then enable and start it:

```sh
systemctl --user daemon-reload
systemctl --user enable --now replanish-server.service
```

It now serves on `http://127.0.0.1:8799` — open that in your browser any time.
To have it keep running while you're logged out: `loginctl enable-linger $USER`.

Useful commands:

```sh
systemctl --user status replanish-server.service     # check it's running
journalctl --user -u replanish-server.service -f      # follow the logs
systemctl --user restart replanish-server.service     # restart after changes
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
