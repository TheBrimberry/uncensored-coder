// Side panel: persistent, auto-refreshing live signal board.
const $ = (id) => document.getElementById(id);

function setStatus(text, cls) {
  const s = $("status"); s.textContent = "● " + text;
  s.className = "status" + (cls ? " " + cls : "");
}

function card(s) {
  const el = document.createElement("div");
  if (!s || !s.ok) { el.className = "card flat";
    el.innerHTML = `<div class="head"><span>${(s&&s.symbol)||"?"}</span><span class="muted">no data</span></div>`;
    return el; }
  if (!s.has_trade) { el.className = "card flat";
    el.innerHTML = `<div class="head"><span>${s.symbol}</span><span class="muted">FLAT</span></div>` +
      `<div class="why">Regime ${s.regime} • prob↑ ${(s.prob_up*100)|0}%</div>`;
    return el; }
  el.className = "card " + s.direction;
  el.innerHTML =
    `<div class="head"><span>${s.direction.toUpperCase()} ${s.symbol}</span>` +
    `<span class="conv">${(s.conviction*100)|0}%</span></div>` +
    `<div class="lvls">Entry ${s.entry} · SL ${s.stop} · TP ${s.take_profit} · RR 1:${s.rr}</div>` +
    `<div class="lvls">Size ${s.size} · ${s.regime}</div>` +
    (s.reasons && s.reasons.length ? `<div class="why">• ${s.reasons[0]}</div>` : "");
  return el;
}

async function refresh() {
  const cfg = await omniConfig();
  document.body.dataset.theme = cfg.theme || "dark";
  const box = $("cards");
  const syms = cfg.watchSymbols || [];
  if (!syms.length) { box.textContent = "Add symbols in the popup's Watchlist tab."; return; }
  box.innerHTML = "";
  for (const sym of syms) {
    try {
      const s = await apiSignal(sym, "1d", cfg);
      box.appendChild(card(s));
      setStatus("agent connected", "ok");
    } catch (e) {
      const c = card({ ok: false, symbol: sym });
      box.appendChild(c);
      setStatus("agent offline — start serve.py", "bad");
    }
  }
  $("clock").textContent = new Date().toLocaleTimeString();
}

document.addEventListener("DOMContentLoaded", () => {
  refresh();
  $("refresh").addEventListener("click", refresh);
  setInterval(refresh, 60000);  // auto-refresh every minute
});
