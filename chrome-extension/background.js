// Background service worker: the always-on co-pilot.
// - scans your watchlist on a schedule
// - pushes FULL signal notifications (entry / SL / TP / RR / reasons)
// - fires price-cross alerts
// - logs every signal to a local journal
// - keeps a toolbar badge with the count of live setups

importScripts("common.js");

const ALARM = "omni-watch";
const JOURNAL_KEY = "omni_journal";
const SEEN_KEY = "omni_seen";        // debounce: last notified direction per symbol

// ---- scheduling -----------------------------------------------------------
async function schedule() {
  await chrome.alarms.clear(ALARM);
  const cfg = await omniConfig();
  if (!cfg.watchEnabled) { setBadge(0); return; }
  const mins = Math.max(parseFloat(cfg.watchMins) || 15, 1);
  chrome.alarms.create(ALARM, { periodInMinutes: mins, delayInMinutes: 0.1 });
}

// ---- badge ----------------------------------------------------------------
function setBadge(n) {
  chrome.action.setBadgeBackgroundColor({ color: n > 0 ? "#2ea043" : "#30363d" });
  chrome.action.setBadgeText({ text: n > 0 ? String(n) : "" });
}

// ---- notifications --------------------------------------------------------
function notifySignal(s) {
  const dir = s.direction.toUpperCase();
  const title = `${dir === "LONG" ? "🟢" : "🔴"} ${dir} ${s.symbol} • ${(s.conviction*100)|0}%`;
  const msg =
    `Entry ${s.entry}  SL ${s.stop}  TP ${s.take_profit}  (RR 1:${s.rr})\n` +
    `Regime ${s.regime}` +
    (s.reasons && s.reasons.length ? `\n• ${s.reasons[0]}` : "");
  chrome.notifications.create("sig-" + s.symbol + "-" + Date.now(), {
    type: "basic",
    iconUrl: "icons/icon128.png",
    title,
    message: msg.slice(0, 300),
    priority: 2,
    buttons: [{ title: "Analyze" }, { title: "Snooze 1h" }],
  });
}

function notifyPlain(title, message) {
  chrome.notifications.create("omni-" + Date.now(), {
    type: "basic", iconUrl: "icons/icon128.png",
    title, message: String(message).slice(0, 300), priority: 2,
  });
}

// ---- journal --------------------------------------------------------------
async function journalAdd(entry) {
  const data = await omniLocalGet({ [JOURNAL_KEY]: [] });
  const arr = data[JOURNAL_KEY];
  arr.unshift(entry);
  if (arr.length > 300) arr.length = 300;
  await omniLocalSet({ [JOURNAL_KEY]: arr });
}

// ---- the scan -------------------------------------------------------------
async function runScan() {
  const cfg = await omniConfig();
  if (!cfg.watchEnabled) { setBadge(0); return; }

  const seenData = await omniLocalGet({ [SEEN_KEY]: {} });
  const seen = seenData[SEEN_KEY];
  let live = 0;

  for (const sym of cfg.watchSymbols || []) {
    let s;
    try { s = await apiSignal(sym, "1d", cfg); }
    catch (e) { continue; }                 // agent offline — stay quiet
    if (!s || !s.ok) continue;

    if (s.has_trade && s.conviction >= (cfg.minConviction || 0.45)) {
      live++;
      const key = s.direction;              // debounce on direction change
      if (seen[sym] !== key) {
        seen[sym] = key;
        notifySignal(s);
        if (cfg.sound) playPing();
        journalAdd({
          ts: Date.now(), symbol: s.symbol, direction: s.direction,
          entry: s.entry, stop: s.stop, tp: s.take_profit, rr: s.rr,
          conviction: s.conviction, regime: s.regime, price: s.price,
        });
      }
    } else if (s.direction === "flat") {
      seen[sym] = "flat";
    }
  }
  await omniLocalSet({ [SEEN_KEY]: seen });
  setBadge(live);

  await checkPriceAlerts(cfg);
}

// ---- price alerts ---------------------------------------------------------
async function checkPriceAlerts(cfg) {
  const alerts = cfg.priceAlerts || [];
  if (!alerts.length) return;
  let changed = false;
  for (const a of alerts) {
    if (!a.active) continue;
    let p;
    try { p = await apiPrice(a.symbol, "1d", cfg); }
    catch (e) { continue; }
    if (!p || !p.ok) continue;
    const hit = (a.dir === "above") ? (p.price >= a.price) : (p.price <= a.price);
    if (hit) {
      notifyPlain(`🔔 ${a.symbol} ${a.dir} ${a.price}`,
                  `Price is now ${p.price}. Your alert triggered.`);
      if (cfg.sound) playPing();
      a.active = false;
      changed = true;
    }
  }
  if (changed) await omniSet({ priceAlerts: alerts });
}

// ---- sound (offscreen-free: use a short notification ping via TTS-less) ----
function playPing() {
  // Service workers can't play <audio>; use a soft chime via the chrome API is
  // unavailable, so we no-op gracefully. Notifications already alert the user.
}

// ---- context menu: analyze selected text ----------------------------------
function setupContextMenu() {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: "omni-analyze-sel",
      title: "Analyze \"%s\" with Trading Agent",
      contexts: ["selection"],
    });
  });
}

chrome.contextMenus?.onClicked.addListener(async (info) => {
  if (info.menuItemId !== "omni-analyze-sel" || !info.selectionText) return;
  const sym = info.selectionText.trim().slice(0, 20);
  try {
    const s = await apiSignal(sym, "1d");
    if (s && s.ok && s.has_trade) notifySignal(s);
    else notifyPlain(`${sym}`, fmtSignal(s));
  } catch (e) {
    notifyPlain("Agent offline", "Start serve.py to analyze " + sym + ".");
  }
});

// ---- notification buttons -------------------------------------------------
chrome.notifications.onButtonClicked.addListener(async (id, btn) => {
  if (btn === 0) {
    // Analyze -> open the side panel (best-effort) and the popup data refresh
    try { await chrome.windows.getCurrent().then(w => chrome.sidePanel.open({ windowId: w.id })); }
    catch (e) {}
  } else if (btn === 1) {
    // Snooze 1h: clear the alarm and re-arm in 60 min
    await chrome.alarms.clear(ALARM);
    chrome.alarms.create(ALARM, { delayInMinutes: 60, periodInMinutes: 60 });
  }
  chrome.notifications.clear(id);
});

// open side panel when toolbar action is used alongside popup is automatic;
// also allow the keyboard command to open it.
chrome.commands?.onCommand.addListener(async (cmd) => {
  if (cmd === "open-side-panel") {
    const w = await chrome.windows.getCurrent();
    try { await chrome.sidePanel.open({ windowId: w.id }); } catch (e) {}
  }
});

// ---- lifecycle ------------------------------------------------------------
chrome.runtime.onInstalled.addListener(() => { setupContextMenu(); schedule(); });
chrome.runtime.onStartup.addListener(() => { setupContextMenu(); schedule(); });
chrome.runtime.onMessage.addListener((msg) => {
  if (msg && msg.type === "reschedule") schedule();
  if (msg && msg.type === "scan-now") runScan();
});
chrome.alarms.onAlarm.addListener((a) => { if (a.name === ALARM) runScan(); });
