// Popup logic: tabs, analyze, live signals, watchlist, alerts, journal, settings.
const $ = (id) => document.getElementById(id);
const JOURNAL_KEY = "omni_journal";

// ---------- tabs ----------
function initTabs() {
  document.querySelectorAll(".tab").forEach((t) => {
    t.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
      document.querySelectorAll(".panel").forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      $("tab-" + t.dataset.tab).classList.add("active");
      if (t.dataset.tab === "signals") loadSignals();
      if (t.dataset.tab === "watch") renderWatch();
      if (t.dataset.tab === "journal") renderJournal();
      if (t.dataset.tab === "chat") $("chatInput").focus();
    });
  });
}

// ---------- status ----------
function setStatus(text, cls) {
  const s = $("status"); s.textContent = "● " + text;
  s.className = "status" + (cls ? " " + cls : "");
}
async function ping() {
  try {
    const cfg = await omniConfig();
    const r = await fetch(cfg.serverUrl + "/api/price?symbol=BTC/USDT");
    setStatus(r.ok ? "agent connected" : "agent HTTP " + r.status, r.ok ? "ok" : "bad");
  } catch (e) { setStatus("agent offline — start serve.py", "bad"); }
}

// ---------- analyze tab ----------
async function runAction(action) {
  $("out").innerHTML = '<span class="spin">Working…</span>';
  try {
    if (action === "signal") {
      const s = await apiSignal($("symbol").value.trim(), $("timeframe").value);
      $("out").textContent = fmtSignal(s) + (s.rationale ? "\n\n" + s.rationale : "");
    } else {
      const text = await apiText(action, {
        symbol: $("symbol").value.trim(),
        timeframe: $("timeframe").value,
        question: $("question").value.trim(),
        strategy: $("question").value.trim().replace(/^strategy:\s*/i, ""),
      });
      $("out").textContent = text;
    }
    setStatus("agent connected", "ok");
  } catch (e) {
    $("out").textContent = "Could not reach the agent.\nStart it: double-click " +
      "\"Start Trading Agent.bat\" (or run python serve.py).\n\n" + e.message;
    setStatus("agent offline — start serve.py", "bad");
  }
}

// ---------- signals tab ----------
async function loadSignals() {
  const box = $("signalCards");
  box.innerHTML = '<span class="spin">Scanning watchlist…</span>';
  const cfg = await omniConfig();
  const syms = cfg.watchSymbols || [];
  if (!syms.length) { box.textContent = "Add symbols in the Watchlist tab."; return; }
  box.innerHTML = "";
  for (const sym of syms) {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `<div class="head"><span>${sym}</span><span class="muted">…</span></div>`;
    box.appendChild(card);
    try {
      const s = await apiSignal(sym, "1d", cfg);
      renderCard(card, s);
      setStatus("agent connected", "ok");
    } catch (e) {
      card.querySelector(".muted").textContent = "offline";
      setStatus("agent offline — start serve.py", "bad");
    }
  }
}

function renderCard(card, s) {
  if (!s || !s.ok) { card.className = "card flat";
    card.innerHTML = `<div class="head"><span>${s.symbol||"?"}</span><span class="muted">no data</span></div>`;
    return; }
  const dir = s.has_trade ? s.direction : "flat";
  card.className = "card " + dir;
  if (!s.has_trade) {
    card.innerHTML =
      `<div class="head"><span>${s.symbol}</span><span class="muted">FLAT</span></div>` +
      `<div class="why">Regime ${s.regime} • prob↑ ${(s.prob_up*100)|0}% • no high-quality setup</div>`;
    return;
  }
  card.innerHTML =
    `<div class="head"><span>${s.direction.toUpperCase()} ${s.symbol}</span>` +
    `<span class="conv">${(s.conviction*100)|0}%</span></div>` +
    `<div class="lvls">Entry ${s.entry} · SL ${s.stop} · TP ${s.take_profit} · RR 1:${s.rr}</div>` +
    `<div class="lvls">Size ${s.size} · ${s.regime}</div>` +
    (s.reasons && s.reasons.length ? `<div class="why">• ${s.reasons[0]}</div>` : "");
}

// ---------- watchlist tab ----------
async function renderWatch() {
  const cfg = await omniConfig();
  const ul = $("symbolList"); ul.innerHTML = "";
  (cfg.watchSymbols || []).forEach((sym) => {
    const li = document.createElement("li");
    li.innerHTML = `<span>${sym}</span><button class="x">✕</button>`;
    li.querySelector(".x").addEventListener("click", async () => {
      const c = await omniConfig();
      await omniSet({ watchSymbols: c.watchSymbols.filter((x) => x !== sym) });
      renderWatch();
    });
    ul.appendChild(li);
  });
  const al = $("alertList"); al.innerHTML = "";
  (cfg.priceAlerts || []).forEach((a, i) => {
    const li = document.createElement("li");
    li.innerHTML = `<span>${a.symbol} ${a.dir} ${a.price} ${a.active?"":"(done)"}</span>` +
                   `<button class="x">✕</button>`;
    li.querySelector(".x").addEventListener("click", async () => {
      const c = await omniConfig();
      c.priceAlerts.splice(i, 1);
      await omniSet({ priceAlerts: c.priceAlerts });
      renderWatch();
    });
    al.appendChild(li);
  });
}

// ---------- journal tab ----------
async function renderJournal() {
  const data = await omniLocalGet({ [JOURNAL_KEY]: [] });
  const arr = data[JOURNAL_KEY];
  const box = $("journalList");
  if (!arr.length) { box.textContent = "No entries yet."; return; }
  box.innerHTML = "";
  arr.slice(0, 80).forEach((e) => {
    const d = new Date(e.ts);
    const card = document.createElement("div");
    card.className = "card " + (e.direction || "flat");
    card.innerHTML =
      `<div class="head"><span>${(e.direction||"").toUpperCase()} ${e.symbol}</span>` +
      `<span class="muted">${d.toLocaleString()}</span></div>` +
      `<div class="lvls">Entry ${e.entry} · SL ${e.stop} · TP ${e.tp} · RR 1:${e.rr} · ${(e.conviction*100)|0}%</div>`;
    box.appendChild(card);
  });
}

async function exportCsv() {
  const data = await omniLocalGet({ [JOURNAL_KEY]: [] });
  const arr = data[JOURNAL_KEY];
  const head = "timestamp,symbol,direction,entry,stop,take_profit,rr,conviction,regime,price\n";
  const rows = arr.map((e) =>
    [new Date(e.ts).toISOString(), e.symbol, e.direction, e.entry, e.stop, e.tp,
     e.rr, e.conviction, e.regime, e.price].join(","));
  const blob = new Blob([head + rows.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = "trading_journal.csv"; a.click();
  URL.revokeObjectURL(url);
}

// ---------- chat ----------
function addMsg(cls, text) {
  const log = $("chatLog");
  const el = document.createElement("div");
  el.className = "msg " + cls;
  el.textContent = text;
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
  return el;
}

async function sendChat() {
  const input = $("chatInput");
  const msg = input.value.trim();
  if (!msg) return;
  input.value = "";
  addMsg("user", msg);
  const thinking = addMsg("bot think", "thinking…");
  try {
    const reply = await apiChat(msg, $("chatSymbol").value.trim(), "1d");
    thinking.remove();
    addMsg("bot", reply);
    setStatus("agent connected", "ok");
  } catch (e) {
    thinking.remove();
    addMsg("bot", "Agent offline — start serve.py (and Ollama for full chat).");
    setStatus("agent offline — start serve.py", "bad");
  }
}

// ---------- start server (native messaging) ----------
const NATIVE_HOST = "com.omni.trading.launcher";

function setPill(state, text) {
  const p = $("srvPill");
  if (!p) return;
  p.textContent = text;
  p.className = "pill" + (state === "on" ? " on" : state === "off" ? " off" : "");
}

async function serverUp() {
  try {
    const cfg = await omniConfig();
    const r = await fetch(cfg.serverUrl + "/api/price?symbol=BTC/USDT");
    return r.ok;
  } catch (e) { return false; }
}

async function pollUntilUp(seconds) {
  for (let i = 0; i < seconds; i++) {
    if (await serverUp()) return true;
    await new Promise((r) => setTimeout(r, 1000));
  }
  return false;
}

async function startServer() {
  if (await serverUp()) { setPill("on", "running"); setStatus("agent connected", "ok"); return; }
  setPill("", "starting…");
  setStatus("starting server…", "");
  try {
    chrome.runtime.sendNativeMessage(NATIVE_HOST, { action: "start" }, async (resp) => {
      if (chrome.runtime.lastError || !resp) {
        // Helper not installed — fall back to clear instructions.
        setPill("off", "not running");
        setStatus("helper not installed — run install_server_button.bat once", "bad");
        $("startHint").innerHTML =
          "One-click start needs the helper. From your agent folder, double-click " +
          "<b>install_server_button.bat</b> once, then reload this extension. " +
          "Or just double-click <b>Start Trading Agent.bat</b> to start it now.";
        return;
      }
      const ok = await pollUntilUp(20);
      setPill(ok ? "on" : "off", ok ? "running" : "no response");
      setStatus(ok ? "agent connected" : "server didn't respond", ok ? "ok" : "bad");
      if (ok) { loadSignals(); }
    });
  } catch (e) {
    setPill("off", "error");
    setStatus("could not start: " + e.message, "bad");
  }
}

async function refreshPill() {
  setPill(await serverUp() ? "on" : "off", await serverUp() ? "running" : "not running");
}

// ---------- settings ----------
async function loadSettings() {
  const cfg = await omniConfig();
  $("serverUrl").value = cfg.serverUrl;
  $("equity").value = cfg.equity;
  $("risk").value = cfg.risk;
  $("watchEnabled").checked = !!cfg.watchEnabled;
  $("watchMins").value = cfg.watchMins;
  $("minConviction").value = cfg.minConviction;
  $("sound").checked = !!cfg.sound;
  document.body.dataset.theme = cfg.theme || "dark";
}
async function saveSettings() {
  await omniSet({
    serverUrl: $("serverUrl").value.trim().replace(/\/+$/, ""),
    equity: $("equity").value.trim() || "10000",
    risk: $("risk").value.trim() || "1",
    watchEnabled: $("watchEnabled").checked,
    watchMins: $("watchMins").value.trim() || "15",
    minConviction: parseFloat($("minConviction").value) || 0.45,
    sound: $("sound").checked,
  });
  chrome.runtime.sendMessage({ type: "reschedule" });
  setStatus("settings saved", "ok");
  ping();
}

// ---------- init ----------
document.addEventListener("DOMContentLoaded", async () => {
  initTabs();
  await loadSettings();
  ping();
  loadSignals();

  $("themeBtn").addEventListener("click", async () => {
    const next = document.body.dataset.theme === "dark" ? "light" : "dark";
    document.body.dataset.theme = next;
    await omniSet({ theme: next });
  });
  document.querySelectorAll(".buttons button").forEach((b) =>
    b.addEventListener("click", () => runAction(b.dataset.act)));
  $("symbol").addEventListener("keydown", (e) => { if (e.key === "Enter") runAction("signal"); });
  $("refreshSignals").addEventListener("click", () => {
    chrome.runtime.sendMessage({ type: "scan-now" }); loadSignals();
  });
  $("addSymbol").addEventListener("click", async () => {
    const v = $("newSymbol").value.trim(); if (!v) return;
    const c = await omniConfig();
    if (!c.watchSymbols.includes(v)) c.watchSymbols.push(v);
    await omniSet({ watchSymbols: c.watchSymbols });
    $("newSymbol").value = ""; renderWatch();
  });
  $("addAlert").addEventListener("click", async () => {
    const sym = $("alSymbol").value.trim();
    const price = parseFloat($("alPrice").value);
    if (!sym || isNaN(price)) return;
    const c = await omniConfig();
    c.priceAlerts.push({ symbol: sym, dir: $("alDir").value, price, active: true });
    await omniSet({ priceAlerts: c.priceAlerts });
    $("alSymbol").value = ""; $("alPrice").value = ""; renderWatch();
  });
  $("chatSend").addEventListener("click", sendChat);
  $("chatInput").addEventListener("keydown", (e) => { if (e.key === "Enter") sendChat(); });
  $("chatReset").addEventListener("click", async () => {
    $("chatLog").innerHTML = "";
    try { await apiChat("/reset", "", "1d"); addMsg("bot", "Conversation cleared."); }
    catch (e) {}
  });
  $("startServer").addEventListener("click", startServer);
  refreshPill();
  $("saveSettings").addEventListener("click", saveSettings);
  $("exportCsv").addEventListener("click", exportCsv);
  $("clearJournal").addEventListener("click", async () => {
    await omniLocalSet({ [JOURNAL_KEY]: [] }); renderJournal();
  });
});
