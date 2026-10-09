"""Routine Radar smoke test. Run: python3 tests/smoke_test.py"""
import json, os, re, socket, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(HERE, "dist", "routine-radar.html")
LINES, RES = [], []


def log(s):
    print(s, flush=True)
    LINES.append(s)


def check(ok, msg):
    RES.append(bool(ok))
    log(("PASS " if ok else "FAIL ") + msg)


log(f"Routine Radar smoke test · {time.strftime('%Y-%m-%d %H:%M %Z')}")
subprocess.run([sys.executable, os.path.join(HERE, "build.py")], check=True, capture_output=True)

snap = json.load(open(os.path.join(HERE, "data", "snapshot.json"), encoding="utf-8"))
check(isinstance(snap.get("bots"), list) and len(snap["bots"]) >= 1, f"collector bots present ({len(snap.get('bots') or [])})")
check(isinstance(snap.get("routines"), list) and len(snap["routines"]) >= 1, f"collector routines present ({len(snap.get('routines') or [])})")
check("counts" in snap and snap["counts"].get("routines", 0) == len(snap["routines"]), "counts.routines matches list")

html = open(DIST, encoding="utf-8").read()
check(os.path.getsize(DIST) > 5000, f"offline snapshot built ({os.path.getsize(DIST):,} bytes)")
check("window.RR_DATA" in html and '"routines"' in html, "dist HTML embeds RR_DATA / routines")
check("Routine Radar" in html, "title/brand present")
check("id=\"radar\"" in html or 'id="radar"' in html, "radar canvas present")

srcs = {
    f: open(os.path.join(HERE, "web", f), encoding="utf-8").read()
    for f in os.listdir(os.path.join(HERE, "web"))
    if f.endswith((".js", ".css", ".html"))
}
ext = [m for t in [html, *srcs.values()] for m in re.findall(r"https?://[^\s'\"<>)]+", t)]
ext = [e for e in ext if not e.startswith("http://127.0.0.1")]
check(not ext, f"no external http(s) references ({ext[:3]})")
check(
    not re.search(
        r"<script[^>]+src=|<link[^>]+href=\"(?!data:)|@import\b|url\((?!['\"]?(?:data:|#))",
        html,
    ),
    "snapshot has no external script/link/import/url() refs",
)

# prompt leak check (light)
leak = False
for r in snap.get("routines") or []:
    # we never put prompt text in snapshot — ensure keys don't include prompt
    if "prompt" in r:
        leak = True
check(not leak, "snapshot has no routine prompt fields")


def free(p):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", p)) != 0


port = 4272 if free(4272) else 42729
srv = subprocess.Popen(
    [sys.executable, os.path.join(HERE, "server.py")],
    env={**os.environ, "RR_PORT": str(port)},
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
try:
    body = health = snap_html = None
    for _ in range(40):
        try:
            body = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2).read().decode()
            health = urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2).read().decode()
            snap_html = urllib.request.urlopen(
                f"http://127.0.0.1:{port}/dist/routine-radar.html", timeout=2
            ).read().decode()
            break
        except Exception:
            time.sleep(0.15)
    check(bool(body) and "Routine Radar" in (body or ""), f"server.py serves web/ on 127.0.0.1:{port}")
    ok_health = False
    try:
        ok_health = bool(health) and json.loads(health).get("ok") is True and "routine-radar" in health
    except Exception:
        ok_health = False
    check(ok_health, "health endpoint ok")
    check(snap_html == html, "server serves matching dist snapshot")
finally:
    srv.terminate()
    try:
        srv.wait(timeout=2)
    except Exception:
        srv.kill()

shots = os.path.join(HERE, "screenshots")
have = [f for f in os.listdir(shots) if f.endswith(".png")] if os.path.isdir(shots) else []
check(any(h.startswith("00-best") for h in have), f"best screenshot present ({have})")

n, p = len(RES), sum(RES)
log(f"RESULT: {p}/{n} checks passed" + ("" if p == n else f" ({n - p} FAILED)"))
open(os.path.join(HERE, "tests", "smoke-test.log"), "w").write("\n".join(LINES) + "\n")
sys.exit(0 if p == n else 1)
