// Shared config + API helpers for popup, side panel and background worker.

const OMNI_DEFAULTS = {
  serverUrl: "http://127.0.0.1:8765",
  equity: "10000",
  risk: "1",
  theme: "dark",
  sound: true,
  // background watch
  watchEnabled: false,
  watchMins: "15",
  watchSymbols: ["BTC/USDT", "EUR/USD", "AAPL"],
  minConviction: 0.45,
  // price alerts: [{symbol, price, dir:'above'|'below', active}]
  priceAlerts: [],
};

function omniGet(keys) {
  return new Promise((res) => chrome.storage.sync.get(keys, res));
}
function omniSet(obj) {
  return new Promise((res) => chrome.storage.sync.set(obj, res));
}
function omniLocalGet(keys) {
  return new Promise((res) => chrome.storage.local.get(keys, res));
}
function omniLocalSet(obj) {
  return new Promise((res) => chrome.storage.local.set(obj, res));
}

async function omniConfig() {
  const cfg = await omniGet(OMNI_DEFAULTS);
  cfg.serverUrl = (cfg.serverUrl || OMNI_DEFAULTS.serverUrl).replace(/\/+$/, "");
  return cfg;
}

async function apiText(action, params) {
  const cfg = await omniConfig();
  const p = new URLSearchParams(Object.assign({ action }, params));
  const r = await fetch(cfg.serverUrl + "/api/run?" + p.toString());
  const d = await r.json();
  return d.text || "(empty)";
}

async function apiSignal(symbol, timeframe, cfg) {
  cfg = cfg || (await omniConfig());
  const p = new URLSearchParams({
    symbol, timeframe: timeframe || "1d", equity: cfg.equity, risk: cfg.risk,
  });
  const r = await fetch(cfg.serverUrl + "/api/signal?" + p.toString());
  return r.json();
}

async function apiPrice(symbol, timeframe, cfg) {
  cfg = cfg || (await omniConfig());
  const p = new URLSearchParams({ symbol, timeframe: timeframe || "1d" });
  const r = await fetch(cfg.serverUrl + "/api/price?" + p.toString());
  return r.json();
}

async function apiChat(message, symbol, timeframe, cfg) {
  cfg = cfg || (await omniConfig());
  const p = new URLSearchParams({
    message, symbol: symbol || "", timeframe: timeframe || "1d",
  });
  const r = await fetch(cfg.serverUrl + "/api/chat?" + p.toString());
  const d = await r.json();
  return d.reply || "(no reply)";
}

// Format a signal object into a compact human string.
function fmtSignal(s) {
  if (!s || !s.ok) return (s && s.error) ? ("error: " + s.error) : "no data";
  if (!s.has_trade) {
    return `${s.symbol}: FLAT — no high-quality setup.\n` +
           `Regime ${s.regime} • prob↑ ${(s.prob_up*100|0)}%`;
  }
  const d = s.direction.toUpperCase();
  return `${d} ${s.symbol}  •  conviction ${(s.conviction*100)|0}%\n` +
         `Entry ${s.entry}   SL ${s.stop}   TP ${s.take_profit}  (RR 1:${s.rr})\n` +
         `Size ${s.size}  •  Regime ${s.regime}\n` +
         (s.reasons && s.reasons.length ? "• " + s.reasons.slice(0,2).join("\n• ") : "");
}
