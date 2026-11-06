#!/usr/bin/env python3
"""Read-only collector: scan /home/box/agent-data/agents for bots + routines → web/data.js + data/snapshot.json."""
from __future__ import annotations

import glob
import json
import os
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/home/box/agent-data/agents"
TZ = ZoneInfo("America/New_York")


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return json.load(f)
    except Exception:
        return default


def parse_ts(v):
    """Accept ISO strings or epoch ms/s."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        n = float(v)
        if n > 1e12:  # ms
            n /= 1000.0
        try:
            return datetime.fromtimestamp(n, tz=timezone.utc)
        except Exception:
            return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:
        return None


def cron_field(f, lo, hi):
    out = set()
    for part in str(f).split(","):
        rng, _, step = part.partition("/")
        step = int(step) if step else 1
        if rng == "*":
            a, b = lo, hi
        elif "-" in rng:
            a, b = map(int, rng.split("-", 1))
        else:
            a = b = int(rng)
            if step > 1:
                b = hi
        vals = set(range(a, b + 1, step))
        if hi == 6:  # dow: normalize 7→0
            vals = {(v % 7) for v in vals}
        out |= vals
    return out


def next_cron_fire(cron: str, after: datetime) -> datetime | None:
    """Next fire of a 5-field cron after `after` (aware), returned in TZ."""
    if not cron or not str(cron).strip():
        return None
    try:
        m, h, dom, mon, dow = str(cron).split()[:5]
        M, Hh, D, Mo, W = (
            cron_field(m, 0, 59),
            cron_field(h, 0, 23),
            cron_field(dom, 1, 31),
            cron_field(mon, 1, 12),
            cron_field(dow, 0, 6),
        )
    except Exception:
        return None
    cur = after.astimezone(TZ).replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(370 * 24 * 60):
        # cron dow: 0/7=Sun, 1=Mon … 6=Sat → map from Python weekday() Mon=0…Sun=6
        cron_dow = (cur.weekday() + 1) % 7
        if (
            cur.minute in M
            and cur.hour in Hh
            and cur.day in D
            and cur.month in Mo
            and cron_dow in W
        ):
            return cur
        cur += timedelta(minutes=1)
    return None


def weekday_only(cron: str) -> bool:
    if not cron:
        return False
    try:
        dow = cron.split()[4]
    except Exception:
        return False
    if dow in ("*", "?"):
        return False
    # Common weekday patterns
    if dow in ("1-5", "MON-FRI", "mon-fri"):
        return True
    try:
        days = cron_field(dow, 0, 6)
        # weekdays = Mon-Fri = cron 1-5
        return days and days.issubset({1, 2, 3, 4, 5})
    except Exception:
        return False


def quiet_hours(cron: str) -> bool:
    """True if scheduled hour is overnight (22–5 ET)."""
    if not cron:
        return False
    try:
        h = cron.split()[1]
        hours = cron_field(h, 0, 23)
        overnight = {22, 23, 0, 1, 2, 3, 4, 5}
        return bool(hours & overnight) and not (hours - overnight)  # only overnight hours
    except Exception:
        return False


def _case_like(src: str, dest: str) -> str:
    """Map dest onto src's capitalization (upper / lower / leading capital)."""
    letters = [c for c in src if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        return dest.upper()
    if letters and all(c.islower() for c in letters):
        return dest.lower()
    if src[:1].isupper():
        return dest[:1].upper() + dest[1:]
    return dest


def _replace_token(text: str, src: str, dest: str) -> str:
    """Case-insensitive whole-word replace. Underscore is part of the word, so boyd_msg is not Boyd."""
    pat = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(src)}(?![A-Za-z0-9_])", re.IGNORECASE)
    return pat.sub(lambda m: _case_like(m.group(0), dest), text)


def scrub_text(text: str) -> str:
    """Replace family names in demo copy. Leaves BoydVC, @chrisalexboyd, Victoria, and sports names alone."""
    if not text:
        return text

    def nick_title(src: str, dest: str, title: str, s: str) -> str:
        pat = re.compile(
            rf"(?<![A-Za-z0-9_])({re.escape(src)})(\s+)({re.escape(title)})(?![A-Za-z0-9_])",
            re.IGNORECASE,
        )
        return pat.sub(lambda m: _case_like(m.group(1), dest) + m.group(2) + m.group(3), s)

    # Longer / special forms before short nicknames.
    text = _replace_token(text, "Boyd Family Times", "Alex Family Times")
    text = nick_title("Char", "Riley", "Tutor", text)
    text = nick_title("Vic", "Jordan", "Tutor", text)
    text = _replace_token(text, "Charlotte", "Riley")
    text = _replace_token(text, "Victor", "Jordan")
    text = _replace_token(text, "Miranda", "Sam")
    text = _replace_token(text, "Spalding", "Northside Academy")
    school = re.compile(
        r"(?<![A-Za-z0-9_])((?:St\.?|Saint)\s+Mary(?:'s|’s))(?![A-Za-z0-9_])",
        re.IGNORECASE,
    )
    text = school.sub(lambda m: _case_like(m.group(1), "Northside Academy"), text)
    ident = re.compile(r"(?<![A-Za-z0-9])boyd_msg(?![A-Za-z0-9])", re.IGNORECASE)
    text = ident.sub(lambda m: _case_like(m.group(0), "alex_msg"), text)
    text = _replace_token(text, "Boyd", "Alex")
    text = _replace_token(text, "Char", "Ri")
    text = _replace_token(text, "Vic", "Jo")
    return text


def scrub_obj(value):
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, list):
        return [scrub_obj(v) for v in value]
    if isinstance(value, dict):
        return {k: scrub_obj(v) for k, v in value.items()}
    return value


def human_eta(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 0:
        return "overdue"
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        h, m = divmod(s // 60, 60)
        return f"{h}h {m}m" if m else f"{h}h"
    d, rem = divmod(s, 86400)
    h = rem // 3600
    return f"{d}d {h}h" if h else f"{d}d"


BOT_COLORS = [
    "#4ade80", "#60a5fa", "#fbbf24", "#f472b6", "#a78bfa",
    "#34d399", "#fb923c", "#22d3ee", "#e879f9", "#f87171",
    "#94a3b8", "#c084fc", "#2dd4bf", "#facc15", "#38bdf8",
    "#86efac", "#fdba74",
]


def collect():
    now = datetime.now(timezone.utc)
    bots = []
    routines = []
    bot_index = {}

    for prof in sorted(glob.glob(os.path.join(ROOT, "*", "profile.json"))):
        adir = os.path.dirname(prof)
        bid = os.path.basename(adir)
        p = read_json(prof, {}) or {}
        name = p.get("name") or bid[:8]
        color = BOT_COLORS[len(bots) % len(BOT_COLORS)]
        bot = {
            "id": bid,
            "name": name,
            "title": p.get("title") or "",
            "color": color,
            "avatarColor": p.get("avatarColor") or color,
            "routineCount": 0,
            "enabledCount": 0,
        }
        bot_index[bid] = bot
        bots.append(bot)

        for apath in sorted(glob.glob(os.path.join(adir, "automations", "*", "automation.json"))):
            a = read_json(apath, {}) or {}
            runs = read_json(os.path.join(os.path.dirname(apath), "runs.json"), []) or []
            if not isinstance(runs, list):
                runs = []
            trig = (a.get("triggerPresentation") or {}).get("trigger") or {}
            ttype = trig.get("type") or ("cron" if a.get("schedule") else "event")
            cron = a.get("schedule") or trig.get("schedule") or ""
            enabled = a.get("enabled", True) is not False
            last_run_at = parse_ts(a.get("lastRunAt"))
            last_status = None
            last_run_iso = None
            # Prefer last runs.json entry with startedAt
            finished = [r for r in runs if isinstance(r, dict) and r.get("startedAt")]
            if finished:
                last = finished[-1]
                last_run_at = parse_ts(last.get("finishedAt") or last.get("startedAt")) or last_run_at
                last_status = last.get("status") or "unknown"
            if last_run_at:
                last_run_iso = last_run_at.astimezone(TZ).isoformat()

            next_fire = None
            eta_sec = None
            if ttype == "cron" and cron and enabled:
                nf = next_cron_fire(cron, now)
                if nf:
                    next_fire = nf.isoformat()
                    eta_sec = (nf.astimezone(timezone.utc) - now).total_seconds()

            # Stable angle/radius for radar placement (hash from id)
            h = abs(hash(f"{bid}:{a.get('name')}")) % 10000
            angle = (h % 360) * 3.1415926535 / 180.0
            radius = 0.25 + (h % 70) / 100.0 * 0.65  # 0.25–0.90

            rid = os.path.basename(os.path.dirname(apath))
            routines.append({
                "id": rid,
                "botId": bid,
                "botName": name,
                "name": a.get("name") or rid,
                "enabled": enabled,
                "triggerType": ttype if ttype in ("cron", "event") else ("cron" if cron else "event"),
                "cron": cron or "",
                "weekdayOnly": weekday_only(cron),
                "quietHours": quiet_hours(cron),
                "lastStatus": last_status,
                "lastRunAt": last_run_iso,
                "nextFireAt": next_fire,
                "etaSeconds": eta_sec,
                "etaLabel": human_eta(eta_sec) if enabled and ttype == "cron" else ("paused" if not enabled else "event"),
                "runCount": len(finished),
                "angle": round(angle, 4),
                "radius": round(radius, 4),
                "color": color,
            })
            bot["routineCount"] += 1
            if enabled:
                bot["enabledCount"] += 1

    # bots with no routines still appear (empty blips area)
    routines.sort(key=lambda r: (r["enabled"] is False, r["etaSeconds"] is None, r["etaSeconds"] if r["etaSeconds"] is not None else 1e18))

    snap = {
        "generatedAt": now.astimezone(TZ).isoformat(),
        "timezone": "America/New_York",
        "sources": {"root": ROOT, "bots": len(bots), "routines": len(routines)},
        "bots": bots,
        "routines": routines,
        "counts": {
            "bots": len(bots),
            "routines": len(routines),
            "enabled": sum(1 for r in routines if r["enabled"]),
            "paused": sum(1 for r in routines if not r["enabled"]),
            "cron": sum(1 for r in routines if r["triggerType"] == "cron"),
            "event": sum(1 for r in routines if r["triggerType"] == "event"),
            "weekdayOnly": sum(1 for r in routines if r["weekdayOnly"]),
            "quietHours": sum(1 for r in routines if r["quietHours"]),
        },
    }
    return snap


def load_for_write():
    """Use a live scan when agent profiles exist. Otherwise keep the checked-in demo snapshot.

    build.py always recollects. On a checkout without /home/box/agent-data that would wipe the
    demo fixture, and a live scan would republish family names. Scrubbing happens in write_outputs.
    """
    profiles = glob.glob(os.path.join(ROOT, "*", "profile.json")) if os.path.isdir(ROOT) else []
    if profiles:
        return collect()
    json_path = os.path.join(HERE, "data", "snapshot.json")
    existing = read_json(json_path) if os.path.isfile(json_path) else None
    if isinstance(existing, dict) and (existing.get("bots") or existing.get("routines")):
        return existing
    return collect()


def scrub_companion_text():
    """Scrub README and web sources other than the generated data.js payload."""
    paths = [os.path.join(HERE, "README.md")]
    web = os.path.join(HERE, "web")
    for fn in os.listdir(web):
        if fn == "data.js":
            continue
        if fn.endswith((".html", ".css", ".js", ".md")):
            paths.append(os.path.join(web, fn))
    for path in paths:
        if not os.path.isfile(path):
            continue
        text = open(path, encoding="utf-8").read()
        scrubbed = scrub_text(text)
        if scrubbed != text:
            with open(path, "w", encoding="utf-8") as f:
                f.write(scrubbed)


def write_outputs(snap=None):
    snap = scrub_obj(snap if snap is not None else load_for_write())
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "web"), exist_ok=True)
    json_path = os.path.join(HERE, "data", "snapshot.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=2)
        f.write("\n")
    # Embed as JS for offline single-file + live web/
    js_path = os.path.join(HERE, "web", "data.js")
    payload = json.dumps(snap, separators=(",", ":"))
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("/* generated by collect.py — do not edit */\n")
        f.write(f"window.RR_DATA = {payload};\n")
    scrub_companion_text()
    return json_path, js_path, snap


if __name__ == "__main__":
    jp, jsp, snap = write_outputs()
    c = snap["counts"]
    print(f"wrote {jp} + {jsp}")
    print(f"bots={c['bots']} routines={c['routines']} enabled={c['enabled']} paused={c['paused']} cron={c['cron']}")
