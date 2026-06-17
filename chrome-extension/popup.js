// Omniscient Trading Agent — popup logic.
// Talks to the local Python agent (serve.py) over its /api/run endpoint.

const DEFAULTS = {
  serverUrl: "http://127.0.0.1:8765",
  equity: "10000",
  risk: "1",
  watchEnabled: false,
  watchSymbol: "BTC/USDT",
  watchMins: "15",
};

const $ = (id) => document.getElementById(id);

function loadSettings() {
  chrome.storage.sync.get(DEFAULTS, (cfg) => {
    $("serverUrl").value   = cfg.serverUrl;
    $("equity").value      = cfg.equity;
    $("risk").value        = cfg.risk;
    $("watchEnabled").checked = !!cfg.watchEnabled;
    $("watchSymbol").value = cfg.watchSymbol;
    $("watchMins").value   = cfg.watchMins;
    pingAgent(cfg.serverUrl);
  });
}

function saveSettings() {
  const cfg = {
    serverUrl: $("serverUrl").value.trim().replace(/\/+$/, ""),
    equity:    $("equity").value.trim() || "10000",
    risk:      $("risk").value.trim() || "1",
    watchEnabled: $("watchEnabled").checked,
    watchSymbol:  $("watchSymbol").value.trim() || "BTC/USDT",
    watchMins:    $("watchMins").value.trim() || "15",
  };
  chrome.storage.sync.set(cfg, () => {
    // Tell the background worker to (re)schedule the watch.
    chrome.runtime.sendMessage({ type: "reschedule" });
    setStatus("settings saved", "ok");
    pingAgent(cfg.serverUrl);
  });
}

function setStatus(text, cls) {
  const s = $("status");
  s.textContent = "●  " + text;
  s.className = "status" + (cls ? " " + cls : "");
}

function serverBase() {
  return ($("serverUrl").value || DEFAULTS.serverUrl).trim().replace(/\/+$/, "");
}

async function pingAgent(url) {
  const base = (url || serverBase()).replace(/\/+$/, "");
  try {
    const r = await fetch(base + "/api/run?action=regime&symbol=BTC/USDT&timeframe=1d",
                          { method: "GET" });
    if (r.ok) setStatus("agent connected", "ok");
    else setStatus("agent responded HTTP " + r.status, "bad");
  } catch (e) {
    setStatus("agent offline — start serve.py", "bad");
  }
}

async function run(action) {
  const base = serverBase();
  const p = new URLSearchParams({
    action,
    symbol: $("symbol").value.trim(),
    timeframe: $("timeframe").value,
    question: $("question").value.trim(),
    strategy: $("question").value.trim().replace(/^strategy:\s*/i, ""),
    equity: $("equity").value.trim() || "10000",
    risk: $("risk").value.trim() || "1",
  });
  $("out").innerHTML = '<span class="spin">Working… (first AI call can take a moment)</span>';
  try {
    const r = await fetch(base + "/api/run?" + p.toString(), { method: "GET" });
    const d = await r.json();
    $("out").textContent = d.text || "(empty response)";
    setStatus("agent connected", "ok");
  } catch (e) {
    $("out").textContent =
      "Could not reach the agent at " + base + ".\n\n" +
      "Start it first: double-click \"Start Trading Agent.bat\"\n" +
      "(or run: python serve.py)\n\nError: " + e.message;
    setStatus("agent offline — start serve.py", "bad");
  }
}

// --- wire up UI ---
document.addEventListener("DOMContentLoaded", () => {
  loadSettings();
  $("gear").addEventListener("click", () =>
    $("settings").classList.toggle("hidden"));
  $("saveSettings").addEventListener("click", saveSettings);
  document.querySelectorAll(".buttons button").forEach((btn) =>
    btn.addEventListener("click", () => run(btn.dataset.act)));
  $("symbol").addEventListener("keydown", (e) => {
    if (e.key === "Enter") run("analyze");
  });
});
