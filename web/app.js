/* Routine Radar UI — uses window.RR_DATA from data.js */
(function () {
  const DATA = window.RR_DATA || { bots: [], routines: [], counts: {}, generatedAt: null };
  const canvas = document.getElementById("radar");
  const ctx = canvas.getContext("2d");
  const listEl = document.getElementById("list");
  const detailEl = document.getElementById("detail");
  const kpis = document.getElementById("kpis");
  const gen = document.getElementById("gen");
  let filter = "all";
  let query = "";
  let selected = null;
  let sweep = 0;
  let hover = null;

  function filtered() {
    const q = query.trim().toLowerCase();
    return (DATA.routines || []).filter((r) => {
      if (filter === "enabled" && !r.enabled) return false;
      if (filter === "paused" && r.enabled) return false;
      if (filter === "cron" && r.triggerType !== "cron") return false;
      if (filter === "event" && r.triggerType !== "event") return false;
      if (filter === "weekday" && !r.weekdayOnly) return false;
      if (filter === "quiet" && !r.quietHours) return false;
      if (!q) return true;
      return (r.name + " " + r.botName + " " + (r.cron || "")).toLowerCase().includes(q);
    });
  }

  function fmtWhen(iso) {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      return d.toLocaleString("en-US", { timeZone: "America/New_York", weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) + " ET";
    } catch (_) {
      return iso;
    }
  }

  function renderKpis() {
    const c = DATA.counts || {};
    const items = [
      ["Bots", c.bots || 0],
      ["Routines", c.routines || 0],
      ["Enabled", c.enabled || 0],
      ["Paused", c.paused || 0],
      ["Cron", c.cron || 0],
    ];
    kpis.innerHTML = items.map(([l, v]) => `<div class="kpi"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");
    gen.textContent = DATA.generatedAt
      ? "Snapshot " + new Date(DATA.generatedAt).toLocaleString("en-US", { timeZone: "America/New_York", dateStyle: "medium", timeStyle: "short" }) + " ET"
      : "No snapshot";
  }

  function renderList() {
    const rows = filtered();
    if (!rows.length) {
      listEl.innerHTML = `<div class="row"><div></div><div><div class="name">No routines match</div><div class="meta">Try another filter or wait for collector data</div></div><div></div></div>`;
      return;
    }
    listEl.innerHTML = rows.map((r) => {
      const bad = r.lastStatus && r.lastStatus !== "ok";
      const cls = [!r.enabled && "paused", bad && "bad", selected && selected.id === r.id && selected.botId === r.botId && "sel"].filter(Boolean).join(" ");
      return `<div class="row ${cls}" data-id="${r.botId}::${r.id}">
        <div class="dot" style="color:${r.color};background:${r.color}"></div>
        <div><div class="name">${esc(r.name)}</div><div class="meta">${esc(r.botName)} · ${r.triggerType}${r.weekdayOnly ? " · weekday" : ""}${r.quietHours ? " · quiet" : ""}</div></div>
        <div class="eta">${esc(r.etaLabel || "—")}</div>
      </div>`;
    }).join("");
    listEl.querySelectorAll(".row[data-id]").forEach((el) => {
      el.addEventListener("click", () => {
        const [botId, id] = el.getAttribute("data-id").split("::");
        select(DATA.routines.find((x) => x.botId === botId && x.id === id));
      });
    });
  }

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function select(r) {
    selected = r || null;
    renderList();
    if (!r) {
      detailEl.className = "detail empty";
      detailEl.innerHTML = `<div class="empty-msg">Select a routine blip or row</div>`;
      return;
    }
    detailEl.className = "detail";
    const tags = [
      r.enabled ? `<span class="tag on">enabled</span>` : `<span class="tag off">paused</span>`,
      `<span class="tag">${esc(r.triggerType)}</span>`,
      r.weekdayOnly ? `<span class="tag warn">weekday</span>` : "",
      r.quietHours ? `<span class="tag">quiet hours</span>` : "",
      r.lastStatus ? `<span class="tag ${r.lastStatus === "ok" ? "on" : "err"}">last: ${esc(r.lastStatus)}</span>` : `<span class="tag off">no runs</span>`,
    ].join("");
    detailEl.innerHTML = `
      <h2>${esc(r.name)}</h2>
      <div class="bot" style="color:${r.color}">${esc(r.botName)}</div>
      <div class="tags">${tags}</div>
      <div class="grid2">
        <div class="cell"><div class="l">Next fire</div><div class="v">${esc(fmtWhen(r.nextFireAt))}</div></div>
        <div class="cell"><div class="l">ETA</div><div class="v">${esc(r.etaLabel)}</div></div>
        <div class="cell"><div class="l">Last run</div><div class="v">${esc(fmtWhen(r.lastRunAt))}</div></div>
        <div class="cell"><div class="l">Runs logged</div><div class="v">${r.runCount}</div></div>
        <div class="cell" style="grid-column:1/-1"><div class="l">Schedule</div><div class="v"><code>${esc(r.cron || "(event / none)")}</code></div></div>
      </div>`;
  }

  function blipXY(r, cx, cy, R) {
    const rad = r.radius * R;
    return [cx + Math.cos(r.angle) * rad, cy + Math.sin(r.angle) * rad];
  }

  function draw() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const css = canvas.clientWidth || 640;
    canvas.width = Math.floor(css * dpr);
    canvas.height = Math.floor(css * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const W = css, H = css;
    const cx = W / 2, cy = H / 2, R = Math.min(W, H) * 0.42;
    ctx.clearRect(0, 0, W, H);

    // rings
    ctx.strokeStyle = "rgba(61,255,154,0.12)";
    ctx.lineWidth = 1;
    for (let i = 1; i <= 4; i++) {
      ctx.beginPath();
      ctx.arc(cx, cy, (R * i) / 4, 0, Math.PI * 2);
      ctx.stroke();
    }
    // crosshair
    ctx.beginPath();
    ctx.moveTo(cx - R - 8, cy); ctx.lineTo(cx + R + 8, cy);
    ctx.moveTo(cx, cy - R - 8); ctx.lineTo(cx, cy + R + 8);
    ctx.stroke();

    // sweep wedge
    const a0 = sweep;
    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, R);
    grad.addColorStop(0, "rgba(61,255,154,0.18)");
    grad.addColorStop(1, "rgba(61,255,154,0)");
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, R, a0 - 0.55, a0);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = "rgba(61,255,154,0.55)";
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(a0) * R, cy + Math.sin(a0) * R);
    ctx.stroke();

    const rows = filtered();
    rows.forEach((r) => {
      const [x, y] = blipXY(r, cx, cy, R);
      const isSel = selected && selected.id === r.id && selected.botId === r.botId;
      const isHov = hover && hover.id === r.id && hover.botId === r.botId;
      const alpha = r.enabled ? 1 : 0.35;
      ctx.globalAlpha = alpha;
      ctx.fillStyle = r.color;
      ctx.beginPath();
      ctx.arc(x, y, isSel || isHov ? 7 : 4.5, 0, Math.PI * 2);
      ctx.fill();
      if (isSel) {
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(x, y, 11, 0, Math.PI * 2);
        ctx.stroke();
      }
      // pulse for soon ETA
      if (r.enabled && r.etaSeconds != null && r.etaSeconds < 3600) {
        ctx.strokeStyle = r.color;
        ctx.globalAlpha = 0.35 * alpha;
        ctx.beginPath();
        ctx.arc(x, y, 10 + (Math.sin(sweep * 4) + 1) * 3, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    });

    // center label
    ctx.fillStyle = "rgba(143,163,201,0.9)";
    ctx.font = "11px system-ui";
    ctx.textAlign = "center";
    ctx.fillText(rows.length + " blips", cx, cy + R + 22);
  }

  function hitTest(mx, my) {
    const css = canvas.clientWidth || 640;
    const cx = css / 2, cy = css / 2, R = Math.min(css, css) * 0.42;
    let best = null, bestD = 14;
    filtered().forEach((r) => {
      const [x, y] = blipXY(r, cx, cy, R);
      const d = Math.hypot(x - mx, y - my);
      if (d < bestD) { bestD = d; best = r; }
    });
    return best;
  }

  canvas.addEventListener("click", (e) => {
    const rect = canvas.getBoundingClientRect();
    const r = hitTest(e.clientX - rect.left, e.clientY - rect.top);
    if (r) select(r);
  });
  canvas.addEventListener("mousemove", (e) => {
    const rect = canvas.getBoundingClientRect();
    hover = hitTest(e.clientX - rect.left, e.clientY - rect.top);
    canvas.style.cursor = hover ? "pointer" : "crosshair";
  });

  document.getElementById("filters").addEventListener("click", (e) => {
    const btn = e.target.closest(".chip");
    if (!btn) return;
    filter = btn.getAttribute("data-f");
    document.querySelectorAll(".chip").forEach((c) => c.classList.toggle("active", c === btn));
    renderList();
  });
  document.getElementById("q").addEventListener("input", (e) => {
    query = e.target.value || "";
    renderList();
  });

  function tick() {
    sweep = (sweep + 0.02) % (Math.PI * 2);
    draw();
    requestAnimationFrame(tick);
  }

  renderKpis();
  renderList();
  select(null);
  if (!(DATA.routines && DATA.routines.length)) {
    detailEl.className = "detail empty";
    detailEl.innerHTML = `<div class="empty-msg">No automations found — empty fleet snapshot (graceful).</div>`;
  }
  requestAnimationFrame(tick);
})();
