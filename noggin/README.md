# Noggin

A localhost-only mind map tool. One central idea, branches out to the left and
right, laid out automatically: add, edit, move, collapse and delete nodes from the
keyboard or the mouse. Every change is saved as you go.

Pure Python 3 standard library on the server, one HTML page with plain JavaScript
in the browser. No `pip install`, no build step, works offline.

Deliberately small. Only the core that most mind map tools share is here: no
images, icons, notes, cross-links, themes per node or collaboration.

## Requirements

- **Python 3.7+** (standard library only — no packages to install).
- A modern web browser.

## Run

```sh
python3 ~/jankytools/noggin/server.py
```

This opens `http://127.0.0.1:8791` in your browser automatically.

Options:

```sh
python3 server.py --port 9000          # use a different port
python3 server.py --data-dir DIR       # store maps somewhere else
python3 server.py --no-browser         # don't auto-open a browser
```

The data directory can also be set with `NOGGIN_DATA_DIR`; `--data-dir` wins.

The port is pinned: if `8791` is already in use, Noggin prints the conflict and
exits `1` rather than quietly moving to another port, so the bookmark never drifts.

## Use

Start with **+ New map**. Type the central idea, then press <kbd>Tab</kbd> to
branch off it. Children of the central idea are shared out between its right and
left sides, and each first-level branch gets its own colour.

| Key / action | Does |
|---|---|
| <kbd>Tab</kbd> | Add a child to the selected node |
| <kbd>Enter</kbd> | Add a sibling below the selected node |
| Double-click a node | Add a child to it |
| <kbd>F2</kbd>, click an already selected node, or just start typing | Edit the text (typing replaces it) |
| <kbd>Shift</kbd>+<kbd>Enter</kbd> | New line while editing |
| <kbd>Esc</kbd> | Stop editing — reverts the edit on an existing node |
| <kbd>Delete</kbd> / <kbd>Backspace</kbd>, or right-click → Delete | Delete the node and its branch (the status bar says how many went; <kbd>Ctrl</kbd>+<kbd>Z</kbd> brings them back) |
| Right-click a node | Menu: add child, add sibling, edit, collapse/expand, delete |
| Right-click empty space | Menu: add a branch, fit to window |
| <kbd>Space</kbd>, or click the circle beside a node | Collapse / expand its branch |
| Arrow keys | Move between nodes |
| <kbd>Alt</kbd>+<kbd>↑</kbd> / <kbd>↓</kbd> | Reorder among siblings |
| Drag a node | Move it, and its branch with it, anywhere on the canvas |
| Drag a node and drop it on another | Make it a child of that node; drop on the left or right half of the central idea to pick a side |
| Double-click empty space | Add a branch to the central idea |
| <kbd>Ctrl</kbd>+<kbd>Z</kbd> / <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd> (or <kbd>Ctrl</kbd>+<kbd>Y</kbd>) | Undo / redo |
| Drag the background or the central idea, scroll | Pan |
| <kbd>Ctrl</kbd>+scroll, pinch, <kbd>+</kbd> / <kbd>-</kbd> | Zoom |
| <kbd>Home</kbd> or **Fit** | Fit the whole map in the window |
| <kbd>Ctrl</kbd>+<kbd>F</kbd> | Find — <kbd>Enter</kbd> / <kbd>Shift</kbd>+<kbd>Enter</kbd> step through matches, <kbd>Esc</kbd> closes |
| <kbd>Ctrl</kbd>+<kbd>C</kbd> / <kbd>X</kbd> / <kbd>V</kbd> (or right-click) | Copy / cut the selected branch; paste inside the selected node |
| <kbd>Ctrl</kbd>+<kbd>S</kbd> | Save the map to a `.noggin` file |
| <kbd>Ctrl</kbd>+<kbd>O</kbd> | Open a `.noggin`, JSON or Markdown file as a new map |
| <kbd>?</kbd> | Show the shortcuts |

A new node left empty is thrown away when you leave it.

A node you drag keeps its new spot, held as an offset from where the automatic
layout would put it, so it still moves sensibly when you add or remove nodes
around it. Moving it under a new parent drops the offset.

**Find** searches every node's text, including inside collapsed branches —
stepping onto a match there opens the branch. All matches are highlighted.

**Copy, cut and paste.** A copied branch goes to the clipboard as a Markdown
outline, so it pastes sensibly into a ticket, a doc or Slack. Pasted back into
Noggin — the same map or another — it comes back exactly, multi-line text and
collapsed branches included. Pasting any other text adds one node per line under
the selected node, nested by indentation (or `#` heading level); bullets,
numbers and `[ ]` checkboxes are stripped. So a list copied from anywhere becomes
a branch. While you are editing a node's text, paste goes into the text as usual.

**Version history** (Map ▾ → Version history…). Auto-save overwrites the map,
so the server also keeps earlier versions of it: before a save, at most every 10
minutes while you edit, and always when a save would drop 5 or more nodes at
once (a big delete or cut) or a restore is about to replace it. The newest 100
per map are kept. Each entry shows when, how many nodes, and the first-level
branches; **Restore** puts that version back, and because the map as it was is
kept as a version first, a restore can itself be undone from the same list.

Nodes never overlap. Whenever the map is laid out, any node that would sit on
top of another is moved, with its whole branch, just far enough to clear it, so
adding to a branch next to something you dragged pushes things aside. This
is worked out afresh each time and not saved, so branches settle back when
there is room again. While you are dragging nothing moves out of the way; it
happens when you let go. **Map ▾ → Tidy layout**
clears every offset and puts the whole map back to the automatic layout (undoable).

Maps save themselves to Noggin's own store as you edit; files are for keeping a
copy elsewhere, sharing, or moving a map between machines. The **Map ▾** menu:

- **Save to file…** writes the map as a `.noggin` file — the map's JSON with a
  `"format": "noggin"` marker. In Brave it is an ordinary download, because Brave
  ships with the browser's file-picker API switched off; in Chrome or Chromium
  the first save asks where to put the file and later saves in the same session
  write straight back to it.
- **Open file…** reads a `.noggin` file, a JSON export, or any nested Markdown
  bullet list and makes a **new** map from it. The file itself is never changed.
- **Export as JPEG image** paints the whole visible map — collapsed branches
  show their hidden-node count — at twice screen resolution, in the current
  theme. Very large maps are scaled down to stay within what a canvas can hold.
- **Export as Markdown** writes a `# Title` line and a nested `- ` list.
- **Tidy layout** and **Delete this map**.

The map's title in the sidebar is the first line of its central idea. The sidebar
(☰ to hide it) and the light/dark theme are remembered in localStorage, and so is
the last map you had open.

## Data

```
~/.local/share/noggin/
├── maps/<id>.json       one file per map, written atomically on every save
├── history/<id>/<stamp>.json  earlier versions of each map (newest 100)
└── trash/<stamp>-<id>.json   deleted maps, moved here rather than erased
```

A map file is the whole tree:

```json
{
 "id": "3f9a1c0b7d2e",
 "title": "Project",
 "updated": 1793264067802,
 "root": {
  "id": "…", "text": "Project",
  "children": [
   {"id": "…", "text": "Goals", "side": "right", "collapsed": false,
    "dx": 150, "dy": -120, "children": []}
  ]
 }
}
```

`side` only appears on children of the root; `dx`/`dy` only on nodes that were
dragged by hand. Undo history lives in the browser
tab and is not saved.

## Install as an app (background service + launcher)

```sh
~/jankytools/noggin/install.sh
```

This sets Noggin up the way the other jankytools run, plus a launcher:

- **`~/.config/systemd/user/noggin-server.service`** — a systemd user unit,
  enabled and started, so the server is always up from login. It runs with
  `--no-browser` and gives up after 5 failed starts in 5 minutes (a taken port
  makes it exit 1) rather than restarting forever.
- **`~/.local/share/applications/noggin.desktop`** — a "Noggin" entry in your app
  launcher, with `icon.svg`. It runs `launch.sh`, which starts the service if it
  isn't running, waits for it to answer, and opens Noggin in its own window —
  a Chromium-family browser's `--app` mode, so no tabs or URL bar (Brave,
  Chromium or Chrome, whichever is found first; otherwise a normal browser tab).

Re-run it after moving the checkout; it overwrites both files. To remove both
(your maps are kept):

```sh
~/jankytools/noggin/install.sh --uninstall
```

Day to day:

```sh
systemctl --user status noggin-server.service
journalctl --user -u noggin-server.service -f
systemctl --user restart noggin-server.service   # after pulling server.py changes
```

Changes to `index.html` need only a page reload (<kbd>Ctrl</kbd>+<kbd>R</kbd> in the
window). To keep the service running while logged out: `loginctl enable-linger $USER`.

## Security

The server binds `127.0.0.1` only. Map ids are generated by the server and must
match `^[a-f0-9]{12}$`, so a request can never name a path outside the maps
directory. Request bodies are capped at 8 MB and tree shape is checked before
anything is written.
