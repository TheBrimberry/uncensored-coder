// Background service worker: periodic "watch your back" signal checks.
// Polls the local agent for the watched symbol's co-pilot read and raises a
// desktop notification when a high-conviction regime / pattern shows up.

const DEFAULTS = {
  serverUrl: "http://127.0.0.1:8765",
  watchEnabled: false,
  watchSymbol: "BTC/USDT",
  watchMins: "15",
  equity: "10000",
  risk: "1",
};

const ALARM = "omni-watch";

function base(cfg) {
  return (cfg.serverUrl || DEFAULTS.serverUrl).replace(/\/+$/, "");
}

async function schedule() {
  chrome.alarms.clear(ALARM);
  chrome.storage.sync.get(DEFAULTS, (cfg) => {
    if (!cfg.watchEnabled) return;
    const mins = Math.max(parseFloat(cfg.watchMins) || 15, 1);
    chrome.alarms.create(ALARM, { periodInMinutes: mins, delayInMinutes: 0.1 });
  });
}

function notify(title, message) {
  chrome.notifications.create("omni-" + Date.now(), {
    type: "basic",
    iconUrl: "icons/icon128.png",
    title: title,
    message: message.slice(0, 300),
    priority: 2,
  });
}

async function check() {
  chrome.storage.sync.get(DEFAULTS, async (cfg) => {
    if (!cfg.watchEnabled) return;
    const sym = cfg.watchSymbol || "BTC/USDT";
    try {
      // Pull the regime read; it's compact and signals high-vol / strong trend.
      const url = base(cfg) +
        "/api/run?action=regime&symbol=" + encodeURIComponent(sym) + "&timeframe=1d";
      const r = await fetch(url, { method: "GET" });
      const d = await r.json();
      const text = d.text || "";

      // Surface a notification only on actionable regimes to avoid spam.
      const firstLine = text.split("\n").find((l) => l.includes("Regime")) || "";
      const interesting =
        /high_volatility|trending_up|trending_down/.test(text);
      if (interesting) {
        notify("📈 " + sym + " — market update", firstLine.trim() || text.slice(0, 200));
      }
    } catch (e) {
      // Agent offline; stay quiet.
    }
  });
}

chrome.runtime.onInstalled.addListener(schedule);
chrome.runtime.onStartup.addListener(schedule);
chrome.runtime.onMessage.addListener((msg) => {
  if (msg && msg.type === "reschedule") schedule();
});
chrome.alarms.onAlarm.addListener((a) => {
  if (a.name === ALARM) check();
});
