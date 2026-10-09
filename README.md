# Routine Radar

Live circular “radar” of Boyd’s Grok Bot routines — each routine is a blip with next-fire ETA, last status, and weekday / quiet-hours flags. Read-only over `/home/box/agent-data`.

## Quick start

```bash
./run.sh start          # collect + build + serve http://127.0.0.1:4272/
./run.sh test           # smoke tests
./run.sh stop
```

Offline (no server): open `dist/routine-radar.html` in a browser (`file://`).

## Features

- Canvas radar with sweep, colored blips per bot, click-to-select
- List + detail panel (ETA, cron, last run status, weekday/quiet tags)
- Filters: all / enabled / paused / cron / event / weekday / quiet hours + search
- Python stdlib collector → `web/data.js` + `data/snapshot.json`
- Single-file offline snapshot via `build.py`

## Layout

```
collect.py     scans agent-data (read-only)
web/           index.html, style.css, app.js, data.js
dist/          offline routine-radar.html
server.py      127.0.0.1:4272 (+ /health, /dist/)
build.py       collect + inline web/ → dist/
tests/         smoke_test.py
screenshots/   00-best-home.png
```

## Notes

Nothing is sent or changed. Prompt text is never collected. Empty automation folders show a graceful empty state.


---
## Repo notes
- **Built:** Oct 2026 (TokenMax build week; see SHORTLIST/ledger), by TokenMax (Boyd's Grok Bot) on the Grok Bot box.
- **Run:** `./run.sh` (then open the localhost URL it prints).
- Imported from `/workspace/tokenmax/routine-radar` on Oct 23, 2026. node_modules, virtualenvs, logs and files over 20 MB were left out.
