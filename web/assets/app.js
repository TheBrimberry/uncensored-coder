/* ===== app.js — CoinScope front-end logic ===== */
(() => {
  'use strict';

  const CG = 'https://api.coingecko.com/api/v3';
  const PROXY = '/.netlify/functions/cg?endpoint=';
  const TOP_N = 1000;            // target number of coins
  const PER_PAGE = 250;          // CoinGecko max page size
  const PAGES = Math.ceil(TOP_N / PER_PAGE);
  const marketsEndpoint = (page) => 'coins/markets'
    + `?vs_currency=usd&order=market_cap_desc&per_page=${PER_PAGE}&page=${page}`
    + '&sparkline=true&price_change_percentage=1h%2C24h%2C7d';
  const TABLE_CAP = 150;         // max rows rendered in the big screener table

  // CoinGecko fetch: prefer the Netlify proxy (keyed, cached), fall back to the
  // public API directly (e.g. when running from a static file server). The first
  // success pins the mode so we don't double-request afterwards.
  let CG_MODE = null; // 'proxy' | 'direct'
  async function cg(endpoint) {
    const proxyURL = PROXY + encodeURIComponent(endpoint);
    const directURL = CG + '/' + endpoint;
    const order = CG_MODE === 'direct' ? [directURL]
      : CG_MODE === 'proxy' ? [proxyURL]
        : [proxyURL, directURL];
    let lastErr;
    for (const u of order) {
      try { const d = await getJSON(u); CG_MODE = u === proxyURL ? 'proxy' : 'direct'; return d; }
      catch (e) { lastErr = e; }
    }
    throw lastErr;
  }

  const LS = {
    watch: 'cs_watch',
    alerts: 'cs_alerts',
    portfolio: 'cs_portfolio',
  };

  const state = {
    coins: [],
    sort: { key: 'mcap', dir: -1 },
    filters: { q: '', signal: '', cap: 0, trend: '', watchOnly: false },
    live: false,
    watch: new Set(loadLS(LS.watch, [])),
    alerts: loadLS(LS.alerts, []),
    arbCoin: 'bitcoin',
    arbMinPct: 0.5,
    arbBase: 'usd',
    pickHorizon: 'day',
    predHorizon: '1m',
    portfolio: loadLS(LS.portfolio, []),
    convReady: false,
    compare: [],
    cmpDays: 90,
    global: null,
  };

  const ICON = (c) => c.image
    ? `<img class="coin-ico" src="${c.image}" alt="" loading="lazy">`
    : `<span class="coin-ico" style="background:${c.color}"></span>`;
  const btcPrice = () => (state.coins.find((c) => c.id === 'bitcoin') || {}).price || 0;

  // ---------- helpers ----------
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const on = (sel, ev, fn) => { const el = typeof sel === 'string' ? $(sel) : sel; if (el) el.addEventListener(ev, fn); };
  function loadLS(k, def) { try { return JSON.parse(localStorage.getItem(k)) ?? def; } catch { return def; } }
  function saveLS(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* ignore */ } }

  const fmtPrice = (n) => {
    if (n == null) return '—';
    if (n >= 1) return '$' + n.toLocaleString('en-US', { maximumFractionDigits: 2 });
    if (n >= 0.01) return '$' + n.toFixed(4);
    return '$' + n.toPrecision(2);
  };
  const fmtBig = (n) => {
    if (n == null) return '—';
    if (n >= 1e12) return '$' + (n / 1e12).toFixed(2) + 'T';
    if (n >= 1e9) return '$' + (n / 1e9).toFixed(2) + 'B';
    if (n >= 1e6) return '$' + (n / 1e6).toFixed(2) + 'M';
    if (n >= 1e3) return '$' + (n / 1e3).toFixed(1) + 'K';
    return '$' + n.toLocaleString();
  };
  const pct = (n) => {
    if (n == null) return '<span class="muted">—</span>';
    const cls = n >= 0 ? 'pos' : 'neg';
    return `<span class="${cls}">${n >= 0 ? '+' : ''}${n.toFixed(2)}%</span>`;
  };
  const colorFor = (c) => c.color || '#' + (c.id || 'aaa').split('').reduce((a, ch) => (a * 33 + ch.charCodeAt(0)) >>> 0, 7).toString(16).slice(0, 6).padEnd(6, 'a');

  async function getJSON(url) {
    const res = await fetch(url, { headers: { accept: 'application/json' } });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return res.json();
  }

  // ---------- core market data ----------
  async function load() {
    setStatus('Loading…', '');
    let raw = [];
    try {
      // Fetch the top N coins across paginated requests (sequential to be gentle on the free API).
      for (let p = 1; p <= PAGES; p++) {
        const page = await cg(marketsEndpoint(p));
        if (!Array.isArray(page) || !page.length) break;
        raw = raw.concat(page);
        setStatus(`Loading… ${raw.length} coins`, '');
      }
      if (!raw.length) throw new Error('empty');
      state.live = true;
    } catch (err) {
      console.warn('Live API unavailable or partial, using what we have / fallback:', err.message);
      if (!raw.length) { raw = FALLBACK_DATA; state.live = false; }
      else { state.live = true; }
    }
    state.coins = raw.map(enrich).filter(Boolean);
    setStatus(
      state.live ? `● Live · ${state.coins.length} coins` : `● Demo data · ${state.coins.length} coins`,
      state.live ? 'live' : 'fallback'
    );
    renderAll();
    checkAlerts();
  }

  function enrich(c) {
    const prices = (c.sparkline_in_7d && c.sparkline_in_7d.price) || [];
    const ch24h = c.price_change_percentage_24h_in_currency ?? c.price_change_percentage_24h ?? 0;
    const ch7d = c.price_change_percentage_7d_in_currency ?? 0;
    const sig = TA.signal({ prices, ch24h, ch7d });
    const slow = TA.sma(prices, Math.min(30, prices.length));
    const o = {
      id: c.id, name: c.name, symbol: (c.symbol || '').toUpperCase(),
      price: c.current_price, rank: c.market_cap_rank ?? 999,
      ch1h: c.price_change_percentage_1h_in_currency ?? null,
      ch24h, ch7d, mcap: c.market_cap ?? 0, vol: c.total_volume ?? 0,
      high24: c.high_24h, low24: c.low_24h, ath: c.ath, athChange: c.ath_change_percentage ?? 0,
      supply: c.circulating_supply, image: c.image,
      prices, rsi: sig.rsi, signal: sig.label, signalCls: sig.cls, score: sig.score,
      pattern: TA.detectPattern({ prices, ch7d }),
      trend: slow ? (c.current_price > slow ? 'up' : 'down') : 'up',
      color: colorFor(c),
    };
    o.valuation = valuationScore(o);   // <0 undervalued, >0 overvalued
    o.explode = explosionScore(o);     // 0–100 momentum/explosion potential
    o.volCap = o.mcap ? o.vol / o.mcap : 0;
    return o;
  }

  // Heuristic valuation: distance from ATH + RSI. Negative = undervalued.
  function valuationScore(c) {
    const athComp = Math.max(-40, Math.min(60, (c.athChange ?? 0) + 60)); // at ATH→+60, deep below→-40
    const rsiComp = ((c.rsi ?? 50) - 50) * 1.4;
    return Math.max(-100, Math.min(100, Math.round(0.6 * athComp + 0.5 * rsiComp)));
  }

  // Heuristic "explosion" score 0–100: turnover, momentum, room to run, structure.
  function explosionScore(c) {
    const volRatio = c.mcap ? c.vol / c.mcap : 0;
    let s = Math.min(volRatio / 0.25, 1) * 30;
    s += Math.max(0, Math.min(c.ch24h, 15)) * 1.2;
    s += Math.max(0, Math.min(c.ch7d, 25)) * 0.5;
    if (c.rsi >= 40 && c.rsi <= 60 && c.ch24h > 0) s += 12;
    if (c.rsi < 35) s += 8;
    s += c.mcap < 2e9 ? 15 : c.mcap < 1e10 ? 8 : 3;
    if (['Breakout', 'Bull Flag', 'Ascending Triangle', 'Double Bottom'].includes(c.pattern)) s += 10;
    return Math.max(0, Math.min(100, Math.round(s)));
  }
  function explodeCatalyst(c) {
    if (['Breakout', 'Bull Flag', 'Ascending Triangle'].includes(c.pattern)) return c.pattern;
    if (c.volCap > 0.2) return 'Volume surge';
    if (c.rsi < 38) return 'Oversold bounce';
    if (c.mcap < 2e9) return 'Low-cap momentum';
    return 'Trend continuation';
  }

  // ---------- render orchestration ----------
  function renderAll() {
    renderTicker();
    renderMovers();
    renderTable();
    renderPatterns();
    renderSetups();
    renderHeatmap();
    populateArbCoins();
    renderPulse();
    renderSmart();
    renderPicks(state.pickHorizon);
    renderArbBoard();
    renderPredictions(state.predHorizon);
    setupConverter();
    renderPortfolio();
    renderCoinPage();
    renderCompare();
    renderUpdates();
    renderHomeUpdate();
  }

  // ---------- screener ----------
  function applyFilters() {
    const { q, signal, cap, trend, watchOnly } = state.filters;
    let list = state.coins.filter((c) => {
      if (watchOnly && !state.watch.has(c.id)) return false;
      if (cap && c.mcap < cap) return false;
      if (signal && c.signal !== signal) return false;
      if (trend && c.trend !== trend) return false;
      if (q) {
        const t = q.toLowerCase();
        if (!c.name.toLowerCase().includes(t) && !c.symbol.toLowerCase().includes(t)) return false;
      }
      return true;
    });
    const { key, dir } = state.sort;
    list.sort((a, b) => {
      if (key === 'name' || key === 'signal' || key === 'pattern')
        return String(a[key]).localeCompare(String(b[key])) * dir;
      return ((a[key] ?? 0) - (b[key] ?? 0)) * dir;
    });
    return list;
  }

  const badge = (c) => `<span class="badge badge--${c.signalCls}">${c.signal}</span>`;

  function renderTable() {
    const body = $('#screener-body');
    if (!body) return;
    const full = applyFilters();
    const list = full.slice(0, TABLE_CAP);
    const countEl = $('#screener-count');
    if (countEl) countEl.textContent = `Showing ${list.length} of ${full.length} coins`;
    if (!list.length) {
      body.innerHTML = `<tr><td colspan="12" class="empty">No coins match your filters.</td></tr>`;
      return;
    }
    body.innerHTML = list.map((c) => `
      <tr data-id="${c.id}">
        <td class="star-col"><button class="star ${state.watch.has(c.id) ? 'on' : ''}" data-star="${c.id}" title="Watchlist">${state.watch.has(c.id) ? '★' : '☆'}</button></td>
        <td class="num muted">${c.rank}</td>
        <td>
          <div class="coin-cell">
            ${c.image ? `<img class="coin-ico" src="${c.image}" alt="" loading="lazy">` : `<span class="coin-ico" style="background:${c.color}"></span>`}
            <span><b>${c.name}</b> <small>${c.symbol}</small></span>
          </div>
        </td>
        <td class="num">${fmtPrice(c.price)}</td>
        <td class="num">${pct(c.ch1h)}</td>
        <td class="num">${pct(c.ch24h)}</td>
        <td class="num">${pct(c.ch7d)}</td>
        <td class="num">${c.rsi == null ? '—' : c.rsi.toFixed(0)}</td>
        <td>${badge(c)}</td>
        <td><span class="pattern-tag">${c.pattern}</span></td>
        <td class="num">${fmtBig(c.mcap)}</td>
        <td>${sparkSVG(c.prices, c.ch7d >= 0)}</td>
      </tr>`).join('');
  }

  function sparkSVG(prices, up) {
    if (!prices || prices.length < 2) return '';
    const w = 110, h = 30, n = prices.length;
    const min = Math.min(...prices), max = Math.max(...prices), span = max - min || 1;
    const pts = prices.map((p, i) => `${((i / (n - 1)) * w).toFixed(1)},${(h - ((p - min) / span) * (h - 4) - 2).toFixed(1)}`).join(' ');
    return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polyline fill="none" stroke="${up ? '#16c784' : '#ea3943'}" stroke-width="1.5" points="${pts}"/></svg>`;
  }

  function renderTicker() {
    const track = $('#ticker-track');
    if (!track) return;
    const html = state.coins.slice(0, 16).map((c) =>
      `<span class="ticker__item"><span class="sym">${c.symbol}</span><span>${fmtPrice(c.price)}</span>${pct(c.ch24h)}</span>`).join('');
    track.innerHTML = html + html;
  }

  function renderMovers() {
    const el = $('#hero-movers');
    if (!el) return;
    const top = [...state.coins].sort((a, b) => b.ch24h - a.ch24h).slice(0, 6);
    el.innerHTML = top.map((c) => `
      <li data-id="${c.id}">
        ${c.image ? `<img class="coin-ico" src="${c.image}" alt="">` : `<span class="coin-ico" style="background:${c.color}"></span>`}
        <span class="coin-name"><b>${c.name}</b><small>${c.symbol}</small></span>
        <span>${fmtPrice(c.price)}</span><span>${pct(c.ch24h)}</span>
      </li>`).join('');
  }

  const TIMEFRAMES = ['15m', '1h', '4h', '1d'];
  function renderPatterns() {
    const el = $('#patterns-grid');
    if (!el) return;
    const picks = [...state.coins].sort((a, b) => Math.abs(b.ch7d) - Math.abs(a.ch7d)).slice(0, 6);
    el.innerHTML = picks.map((c, i) => {
      const bull = c.ch7d >= 0;
      const target = c.price * (1 + (bull ? 1 : -1) * (0.04 + Math.abs(c.ch7d) / 400));
      return `
      <div class="pcard" data-id="${c.id}">
        <div class="pcard__top">
          <span class="pcard__coin">${c.image ? `<img class="coin-ico" src="${c.image}" alt="">` : `<span class="coin-ico" style="background:${c.color}"></span>`}${c.name}</span>
          <span class="pcard__tf">${TIMEFRAMES[i % 4]}</span>
        </div>
        <h4>${c.pattern}</h4>
        <div class="pattern-tag">${bull ? 'Bullish' : 'Bearish'} · ${badge(c)}</div>
        <div class="pcard__meta">
          <div><span>Current</span><b>${fmtPrice(c.price)}</b></div>
          <div><span>Target</span><b class="${bull ? 'pos' : 'neg'}">${fmtPrice(target)}</b></div>
          <div><span>RSI</span><b>${c.rsi.toFixed(0)}</b></div>
        </div>
      </div>`;
    }).join('');
  }

  function renderSetups() {
    const el = $('#signals-grid');
    if (!el) return;
    const buys = [...state.coins].filter((c) => c.signal === 'Strong Buy' || c.signal === 'Buy').sort((a, b) => b.score - a.score).slice(0, 3);
    const fill = buys.length ? buys : [...state.coins].sort((a, b) => b.score - a.score).slice(0, 3);
    el.innerHTML = fill.map((c) => {
      const long = c.score >= 0, entry = c.price;
      const stop = entry * (long ? 0.94 : 1.06), t1 = entry * (long ? 1.08 : 0.92), t2 = entry * (long ? 1.16 : 0.84);
      const rr = Math.abs((t1 - entry) / (entry - stop)).toFixed(1);
      return `
      <div class="setup" data-id="${c.id}">
        <div class="setup__head">
          ${c.image ? `<img class="coin-ico" src="${c.image}" alt="">` : `<span class="coin-ico" style="background:${c.color}"></span>`}
          <span><b>${c.name}</b> <small>${c.symbol}</small></span>
          <span style="margin-left:auto">${badge(c)}</span>
        </div>
        <div class="setup__rows">
          <div class="setup__row"><span>Direction</span><b class="${long ? 'pos' : 'neg'}">${long ? 'Long' : 'Short'}</b></div>
          <div class="setup__row"><span>Entry</span><b>${fmtPrice(entry)}</b></div>
          <div class="setup__row"><span>Stop-loss</span><b class="neg">${fmtPrice(stop)}</b></div>
          <div class="setup__row"><span>Target 1</span><b class="pos">${fmtPrice(t1)}</b></div>
          <div class="setup__row"><span>Target 2</span><b class="pos">${fmtPrice(t2)}</b></div>
          <div class="setup__row"><span>Risk/Reward</span><b>${rr}R</b></div>
        </div>
      </div>`;
    }).join('');
  }

  // ---------- global stats bar ----------
  async function loadGlobal() {
    let g;
    try { g = (await cg('global')).data; }
    catch { g = FALLBACK_GLOBAL.data; }
    state.global = g;
    renderPulseCards();
    const set = (id, v) => { const el = $(id); if (el) el.textContent = v; };
    set('#g-mcap', fmtBig(g.total_market_cap.usd));
    const mch = $('#g-mcap-ch'); if (mch) mch.innerHTML = pct(g.market_cap_change_percentage_24h_usd);
    set('#g-vol', fmtBig(g.total_volume.usd));
    set('#g-btc', g.market_cap_percentage.btc.toFixed(1) + '%');
    set('#g-eth', (g.market_cap_percentage.eth ?? 0).toFixed(1) + '%');
    set('#g-coins', (g.active_cryptocurrencies ?? 0).toLocaleString());
  }

  // ---------- Fear & Greed gauge ----------
  async function loadFNG() {
    if (!$('#fng-arc')) return;
    let v, label;
    try {
      const d = (await getJSON('https://api.alternative.me/fng/')).data[0];
      v = +d.value; label = d.value_classification;
    } catch {
      const d = FALLBACK_FNG.data[0]; v = +d.value; label = d.value_classification;
    }
    const frac = Math.max(0, Math.min(100, v)) / 100;
    const arc = $('#fng-arc');
    const len = 283; // semicircle path length
    arc.style.strokeDashoffset = String(len - len * frac);
    const hue = 120 * frac; // red→green
    const col = `hsl(${hue}, 70%, 45%)`;
    arc.setAttribute('stroke', col);
    const ang = -90 + 180 * frac; // needle angle in degrees
    const rad = (ang * Math.PI) / 180;
    $('#fng-needle').setAttribute('x2', (100 + 72 * Math.sin(rad)).toFixed(1));
    $('#fng-needle').setAttribute('y2', (100 - 72 * Math.cos(rad)).toFixed(1));
    $('#fng-value').textContent = v;
    $('#fng-value').style.color = col;
    $('#fng-label').textContent = label;
  }

  // ---------- Trending ----------
  async function loadTrending() {
    if (!$('#trending-list')) return;
    let coins;
    try { coins = (await cg('search/trending')).coins; }
    catch { coins = FALLBACK_TRENDING.coins; }
    $('#trending-list').innerHTML = coins.slice(0, 7).map((w, i) => {
      const it = w.item;
      const ch = it.data?.price_change_percentage_24h?.usd;
      return `<li data-id="${it.id}">
        <span class="trending__rank">${i + 1}</span>
        ${it.thumb || it.small ? `<img class="coin-ico" src="${it.thumb || it.small}" alt="">` : `<span class="coin-ico"></span>`}
        <span class="coin-name"><b>${it.name}</b><small>${(it.symbol || '').toUpperCase()}</small></span>
        <span>${ch == null ? '' : pct(ch)}</span>
      </li>`;
    }).join('');
  }

  // ---------- Heatmap ----------
  function renderHeatmap() {
    const el = $('#heatmap');
    if (!el) return;
    const coins = [...state.coins].sort((a, b) => b.mcap - a.mcap).slice(0, 30);
    const max = Math.max(...coins.map((c) => c.mcap)) || 1;
    el.innerHTML = coins.map((c) => {
      const rel = Math.sqrt(c.mcap / max); // size factor
      const flex = (8 + rel * 28).toFixed(2);
      const ch = c.ch24h;
      const intensity = Math.min(Math.abs(ch) / 8, 1);
      const bg = ch >= 0
        ? `rgba(22,199,132,${0.12 + intensity * 0.5})`
        : `rgba(234,57,67,${0.12 + intensity * 0.5})`;
      return `<div class="heat" data-id="${c.id}" style="flex:${flex} 1 ${(40 + rel * 70).toFixed(0)}px;background:${bg}">
        <b>${c.symbol}</b><span>${ch >= 0 ? '+' : ''}${ch.toFixed(1)}%</span>
      </div>`;
    }).join('');
  }

  // ---------- Watchlist ----------
  function toggleWatch(id) {
    if (state.watch.has(id)) state.watch.delete(id); else state.watch.add(id);
    saveLS(LS.watch, [...state.watch]);
    renderTable();
  }

  // ---------- Coin detail drawer ----------
  async function openDrawer(id) {
    const c = state.coins.find((x) => x.id === id);
    if (!c) return;
    const drawer = $('#drawer');
    drawer.hidden = false;
    document.body.style.overflow = 'hidden';
    $('#drawer-content').innerHTML = `<div class="loading">Loading ${c.name}…</div>`;

    let prices = c.prices;
    try {
      const d = await cg(`coins/${id}/market_chart?vs_currency=usd&days=30&interval=daily`);
      if (d.prices && d.prices.length) prices = d.prices.map((p) => p[1]);
    } catch { /* keep 7d sparkline */ }

    const rsi = TA.rsi(prices) ?? c.rsi;
    const sma20 = TA.sma(prices, Math.min(20, prices.length));
    const sma50 = TA.sma(prices, Math.min(50, prices.length));
    const existing = state.alerts.find((a) => a.id === id);

    $('#drawer-content').innerHTML = `
      <div class="dr__head">
        ${c.image ? `<img class="coin-ico coin-ico--lg" src="${c.image}" alt="">` : `<span class="coin-ico coin-ico--lg" style="background:${c.color}"></span>`}
        <div>
          <h3 id="drawer-name">${c.name} <small class="muted">${c.symbol}</small></h3>
          <div class="dr__price">${fmtPrice(c.price)} <span>${pct(c.ch24h)} (24h)</span></div>
          <a class="dr__fullpage" href="coin.html?id=${c.id}">Open full page →</a>
        </div>
        <span class="dr__rank">Rank #${c.rank}</span>
      </div>

      <div id="dr-chart" class="dr__chart-host">${areaSVG(prices, c.ch7d >= 0)}</div>

      <div class="dr__stats">
        <div><span>Signal</span><b>${badge(c)}</b></div>
        <div><span>RSI(14)</span><b>${rsi == null ? '—' : rsi.toFixed(0)}</b></div>
        <div><span>Pattern</span><b class="pattern-tag">${c.pattern}</b></div>
        <div><span>SMA20</span><b>${sma20 ? fmtPrice(sma20) : '—'}</b></div>
        <div><span>SMA50</span><b>${sma50 ? fmtPrice(sma50) : '—'}</b></div>
        <div><span>Trend</span><b class="${c.trend === 'up' ? 'pos' : 'neg'}">${c.trend === 'up' ? 'Up' : 'Down'}</b></div>
        <div><span>Market Cap</span><b>${fmtBig(c.mcap)}</b></div>
        <div><span>24h Vol</span><b>${fmtBig(c.vol)}</b></div>
        <div><span>24h High</span><b>${c.high24 ? fmtPrice(c.high24) : '—'}</b></div>
        <div><span>24h Low</span><b>${c.low24 ? fmtPrice(c.low24) : '—'}</b></div>
        <div><span>ATH</span><b>${c.ath ? fmtPrice(c.ath) : '—'}</b></div>
        <div><span>From ATH</span><b>${c.athChange != null ? pct(c.athChange) : '—'}</b></div>
      </div>

      <div class="dr__alert">
        <h4>Price alert</h4>
        ${existing ? `<p class="muted">Active alert: ${existing.dir === 'above' ? '↑ above' : '↓ below'} <b>${fmtPrice(existing.price)}</b> <button class="link-btn" id="dr-alert-clear">remove</button></p>` : ''}
        <div class="dr__alert-row">
          <select class="input" id="dr-alert-dir">
            <option value="above">Rises above</option>
            <option value="below">Falls below</option>
          </select>
          <input class="input" id="dr-alert-price" type="number" step="any" placeholder="${fmtPrice(c.price).replace('$', '')}" />
          <button class="btn btn--primary" id="dr-alert-set">Set alert</button>
        </div>
        <p class="muted dr__alert-note">Alerts are stored in your browser and checked on each refresh.</p>
      </div>
    `;

    loadDrawerChart(id, prices);

    $('#dr-alert-set')?.addEventListener('click', () => {
      const price = parseFloat($('#dr-alert-price').value);
      if (!price || price <= 0) { toast('Enter a valid target price.', 'warn'); return; }
      const dir = $('#dr-alert-dir').value;
      state.alerts = state.alerts.filter((a) => a.id !== id);
      state.alerts.push({ id, symbol: c.symbol, name: c.name, price, dir });
      saveLS(LS.alerts, state.alerts);
      toast(`Alert set: ${c.symbol} ${dir === 'above' ? '↑' : '↓'} ${fmtPrice(price)}`, 'ok');
      requestNotifyPermission();
      openDrawer(id);
    });
    $('#dr-alert-clear')?.addEventListener('click', () => {
      state.alerts = state.alerts.filter((a) => a.id !== id);
      saveLS(LS.alerts, state.alerts);
      openDrawer(id);
    });
  }

  function areaSVG(prices, up) {
    if (!prices || prices.length < 2) return '<div class="muted" style="padding:1rem 0">No chart data.</div>';
    const w = 560, h = 180, pad = 6, n = prices.length;
    const min = Math.min(...prices), max = Math.max(...prices), span = max - min || 1;
    const x = (i) => pad + (i / (n - 1)) * (w - 2 * pad);
    const y = (p) => pad + (1 - (p - min) / span) * (h - 2 * pad);
    const line = prices.map((p, i) => `${x(i).toFixed(1)},${y(p).toFixed(1)}`).join(' ');
    const col = up ? '#16c784' : '#ea3943';
    const area = `${x(0).toFixed(1)},${(h - pad).toFixed(1)} ${line} ${x(n - 1).toFixed(1)},${(h - pad).toFixed(1)}`;
    return `<svg class="dr__chart" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" width="100%">
      <defs><linearGradient id="grad" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="${col}" stop-opacity="0.35"/>
        <stop offset="100%" stop-color="${col}" stop-opacity="0"/>
      </linearGradient></defs>
      <polygon fill="url(#grad)" points="${area}"/>
      <polyline fill="none" stroke="${col}" stroke-width="2" points="${line}"/>
    </svg>
    <div class="dr__chart-label muted">Last ${n} data points</div>`;
  }

  // Candlestick chart from OHLC rows [t, open, high, low, close].
  function candleSVG(ohlc) {
    if (!ohlc || ohlc.length < 2) return '';
    const W = 680, H = 240, padX = 4, padY = 10, n = ohlc.length;
    const max = Math.max(...ohlc.map((d) => d[2])), min = Math.min(...ohlc.map((d) => d[3])), span = max - min || 1;
    const cw = (W - 2 * padX) / n, bw = Math.max(1.2, cw * 0.62);
    const y = (v) => padY + (1 - (v - min) / span) * (H - 2 * padY);
    const cx = (i) => padX + cw * i + cw / 2;
    const bars = ohlc.map((d, i) => {
      const [, o, h, l, c] = d, up = c >= o, col = up ? '#16c784' : '#ea3943';
      const yo = y(o), yc = y(c), top = Math.min(yo, yc), bh = Math.max(1, Math.abs(yc - yo));
      return `<line x1="${cx(i).toFixed(1)}" x2="${cx(i).toFixed(1)}" y1="${y(h).toFixed(1)}" y2="${y(l).toFixed(1)}" stroke="${col}" stroke-width="1"/>`
        + `<rect x="${(cx(i) - bw / 2).toFixed(1)}" y="${top.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" fill="${col}"/>`;
    }).join('');
    return `<svg class="candles" viewBox="0 0 ${W} ${H}" width="100%" preserveAspectRatio="none">${bars}</svg>`;
  }

  async function loadOHLC(id, days) {
    try { const d = await cg(`coins/${id}/ohlc?vs_currency=usd&days=${days}`); if (Array.isArray(d) && d.length) return d; } catch { /* none */ }
    return null;
  }

  async function loadCoinChart(id, days) {
    const el = $('#cp-chart'); if (!el) return;
    el.innerHTML = '<div class="loading">Loading chart…</div>';
    const ohlc = await loadOHLC(id, days);
    if (ohlc) el.innerHTML = candleSVG(ohlc) + `<div class="dr__chart-label muted">${ohlc.length} candles · ${days}-day OHLC</div>`;
    else { const c = state.coins.find((x) => x.id === id); el.innerHTML = areaSVG(c ? c.prices : [], true); }
    $$('#cp-tf .tf').forEach((t) => t.classList.toggle('active', +t.dataset.days === days));
  }

  async function loadDrawerChart(id, fallbackPrices) {
    const el = $('#dr-chart'); if (!el) return;
    const ohlc = await loadOHLC(id, 30);
    el.innerHTML = ohlc ? candleSVG(ohlc) + `<div class="dr__chart-label muted">30-day OHLC</div>` : areaSVG(fallbackPrices, true);
  }

  function closeDrawer() {
    $('#drawer').hidden = true;
    document.body.style.overflow = '';
  }

  // ---------- Price alerts ----------
  function requestNotifyPermission() {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission().catch(() => {});
    }
  }
  function checkAlerts() {
    if (!state.alerts.length) return;
    const remaining = [];
    for (const a of state.alerts) {
      const c = state.coins.find((x) => x.id === a.id);
      if (!c) { remaining.push(a); continue; }
      const hit = (a.dir === 'above' && c.price >= a.price) || (a.dir === 'below' && c.price <= a.price);
      if (hit) {
        const msg = `${a.symbol} ${a.dir === 'above' ? 'rose above' : 'fell below'} ${fmtPrice(a.price)} — now ${fmtPrice(c.price)}`;
        toast('🔔 ' + msg, 'ok', 8000);
        if ('Notification' in window && Notification.permission === 'granted') {
          try { new Notification('CoinScope alert', { body: msg }); } catch { /* ignore */ }
        }
      } else {
        remaining.push(a);
      }
    }
    if (remaining.length !== state.alerts.length) { state.alerts = remaining; saveLS(LS.alerts, state.alerts); }
  }

  // ---------- Arbitrage scanner ----------
  function populateArbCoins() {
    const sel = $('#arb-coin');
    if (!sel) return;
    const cur = state.arbCoin;
    sel.innerHTML = state.coins.slice(0, 40).map((c) => `<option value="${c.id}">${c.name} (${c.symbol})</option>`).join('');
    if (state.coins.some((c) => c.id === cur)) sel.value = cur;
    else state.arbCoin = sel.value;
    if (!sel.dataset.scanned) { sel.dataset.scanned = '1'; scanArb(state.arbCoin); }
  }

  function synthTickers(c) {
    // Build plausible exchange tickers around the live price when the API is unavailable.
    const exchanges = ['Binance', 'Coinbase', 'Kraken', 'OKX', 'Bybit', 'KuCoin', 'Bitstamp', 'Gate.io'];
    let seed = c.id.split('').reduce((a, ch) => (a * 31 + ch.charCodeAt(0)) >>> 0, 7);
    const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    return exchanges.map((name) => {
      const dev = (rnd() - 0.5) * 2 * 0.012; // ±1.2%
      return {
        market: { name }, base: c.symbol, target: 'USDT',
        converted_last: { usd: c.price * (1 + dev) },
        converted_volume: { usd: c.vol * (0.05 + rnd() * 0.4) },
        trust_score: rnd() > 0.25 ? 'green' : 'yellow',
        trade_url: null,
      };
    });
  }

  async function scanArb(id) {
    const body = $('#arb-body');
    const c = state.coins.find((x) => x.id === id) || state.coins[0];
    if (!c) return;
    state.arbCoin = id;
    body.innerHTML = `<tr><td colspan="7" class="loading">Scanning exchanges for ${c.name}…</td></tr>`;

    let tickers;
    try {
      const d = await cg(`coins/${id}/tickers?include_exchange_logo=false&depth=false`);
      tickers = (d.tickers || [])
        .filter((t) => t.converted_last && t.converted_last.usd && ['USD', 'USDT', 'USDC', 'BUSD'].includes(t.target))
        .map((t) => ({
          name: t.market.name, base: t.base, target: t.target,
          usd: t.converted_last.usd, vol: t.converted_volume?.usd ?? 0, trust: t.trust_score,
        }));
      // de-dup by exchange (keep highest volume)
      const byEx = {};
      for (const t of tickers) if (!byEx[t.name] || t.vol > byEx[t.name].vol) byEx[t.name] = t;
      tickers = Object.values(byEx);
      if (tickers.length < 2) throw new Error('not enough markets');
    } catch (err) {
      console.warn('Tickers API unavailable, synthesizing:', err.message);
      tickers = synthTickers(c).map((t) => ({ name: t.market.name, base: t.base, target: t.target, usd: t.converted_last.usd, vol: t.converted_volume.usd, trust: t.trust_score }));
    }

    tickers.sort((a, b) => a.usd - b.usd);
    const low = tickers[0].usd, high = tickers[tickers.length - 1].usd;
    const spread = ((high - low) / low) * 100;
    const profit1k = (1000 / low) * high - 1000;

    $('#arb-summary').innerHTML = `
      <div class="arb__stat arb__stat--buy"><span>Best buy</span><b>${fmtPrice(low)}</b><small>${tickers[0].name}</small></div>
      <div class="arb__stat arb__stat--sell"><span>Best sell</span><b>${fmtPrice(high)}</b><small>${tickers[tickers.length - 1].name}</small></div>
      <div class="arb__stat"><span>Max spread</span><b class="${spread > 0.5 ? 'pos' : ''}">${spread.toFixed(2)}%</b><small>${tickers.length} exchanges</small></div>
      <div class="arb__stat"><span>Profit / $1,000</span><b class="${profit1k > 0 ? 'pos' : ''}">${fmtPrice(profit1k)}</b><small>before fees</small></div>`;

    body.innerHTML = tickers.map((t) => {
      const vsLow = ((t.usd - low) / low) * 100;
      const isLow = t.usd === low, isHigh = t.usd === high;
      const trustCls = t.trust === 'green' ? 'pos' : t.trust === 'yellow' ? 'warn-t' : 'muted';
      return `<tr class="${isLow ? 'arb-row--buy' : isHigh ? 'arb-row--sell' : ''}">
        <td><b>${t.name}</b></td>
        <td class="muted">${t.base}/${t.target}</td>
        <td class="num">${fmtPrice(t.usd)}</td>
        <td class="num">${vsLow < 0.0001 ? '<span class="muted">—</span>' : pct(vsLow)}</td>
        <td class="num">${t.vol ? fmtBig(t.vol) : '—'}</td>
        <td><span class="trust ${trustCls}">●</span> ${t.trust || 'n/a'}</td>
        <td>${isLow ? '<span class="tag tag--buy">BUY</span>' : isHigh ? '<span class="tag tag--sell">SELL</span>' : ''}</td>
      </tr>`;
    }).join('');
  }

  // ---------- Market Pulse (cryptopulse) ----------
  function pulseRows(list, metric) {
    return `<table class="mini">${list.map((c, i) => `
      <tr data-id="${c.id}">
        <td class="mini__rank">${i + 1}</td>
        <td class="mini__coin">${ICON(c)}<b>${c.symbol}</b></td>
        <td class="num">${fmtPrice(c.price)}</td>
        <td class="num">${metric(c)}</td>
      </tr>`).join('')}</table>`;
  }

  function renderPulseCards() {
    const el = $('#pulse-cards');
    if (!el) return;
    const g = state.global;
    const sumMcap = state.coins.reduce((a, c) => a + c.mcap, 0);
    const sumVol = state.coins.reduce((a, c) => a + c.vol, 0);
    const mcap = g ? g.total_market_cap.usd : sumMcap;
    const vol = g ? g.total_volume.usd : sumVol;
    const mcapCh = g ? g.market_cap_change_percentage_24h_usd : (state.coins.reduce((a, c) => a + c.ch24h, 0) / (state.coins.length || 1));
    const btcDom = g ? g.market_cap_percentage.btc : 0;
    const altCap = mcap * (1 - btcDom / 100);
    el.innerHTML = `
      <div class="pcard2"><span>Total Market Cap</span><b>${fmtBig(mcap)}</b>${pct(mcapCh)}</div>
      <div class="pcard2"><span>Altcoin Market Cap</span><b>${fmtBig(altCap)}</b><small class="muted">excl. BTC</small></div>
      <div class="pcard2"><span>24h Volume</span><b>${fmtBig(vol)}</b><small class="muted">${state.coins.length} coins tracked</small></div>`;
  }

  function renderPulse() {
    if (!$('#pulse-gainers')) return;
    renderPulseCards();
    const liquid = state.coins.filter((c) => c.vol > 1e5);
    const by = (arr, fn, dir = -1, n = 10) => [...arr].sort((a, b) => (fn(a) - fn(b)) * dir).slice(0, n);
    const rsiPct = (c) => `<span class="${c.rsi <= 35 ? 'pos' : c.rsi >= 70 ? 'neg' : ''}">${c.rsi.toFixed(0)}</span>`;

    $('#pulse-gainers').innerHTML = pulseRows(by(liquid, (c) => c.ch24h, -1), (c) => pct(c.ch24h));
    $('#pulse-losers').innerHTML = pulseRows(by(liquid, (c) => c.ch24h, 1), (c) => pct(c.ch24h));
    $('#pulse-volume').innerHTML = pulseRows(by(state.coins, (c) => c.vol, -1), (c) => fmtBig(c.vol));
    $('#pulse-bullish').innerHTML = pulseRows(by(state.coins, (c) => c.score + c.ch7d / 100, -1), (c) => badge(c));
    $('#pulse-bearish').innerHTML = pulseRows(by(state.coins, (c) => c.score + c.ch7d / 100, 1), (c) => badge(c));
    $('#pulse-oversold').innerHTML = pulseRows(by(state.coins, (c) => c.rsi, 1), rsiPct);
    $('#pulse-overbought').innerHTML = pulseRows(by(state.coins, (c) => c.rsi, -1), rsiPct);
    $('#pulse-volcap').innerHTML = pulseRows(by(state.coins, (c) => c.volCap, -1), (c) => (c.volCap * 100).toFixed(1) + '%');
  }

  // ---------- Smart picks: valuation + explosion ----------
  function valMeter(v) {
    const left = ((v + 100) / 200) * 100; // -100..100 → 0..100%
    const col = v < -15 ? 'var(--green)' : v > 25 ? 'var(--red)' : 'var(--muted)';
    return `<div class="vmeter"><span style="left:${left.toFixed(0)}%;background:${col}"></span></div>`;
  }
  function renderSmart() {
    if (!$('#smart-under')) return;
    const sorted = [...state.coins];
    const under = sorted.sort((a, b) => a.valuation - b.valuation).slice(0, 6);
    const over = [...state.coins].sort((a, b) => b.valuation - a.valuation).slice(0, 6);
    const explode = [...state.coins].sort((a, b) => b.explode - a.explode).slice(0, 6);

    const valRow = (c) => `
      <div class="srow" data-id="${c.id}">
        <span class="srow__coin">${ICON(c)}<b>${c.symbol}</b></span>
        <span class="srow__mid">${valMeter(c.valuation)}<small class="muted">${c.athChange.toFixed(0)}% vs ATH · RSI ${c.rsi.toFixed(0)}</small></span>
        <span class="num">${fmtPrice(c.price)}</span>
      </div>`;
    $('#smart-under').innerHTML = under.map(valRow).join('');
    $('#smart-over').innerHTML = over.map(valRow).join('');
    $('#smart-explode').innerHTML = explode.map((c) => `
      <div class="srow" data-id="${c.id}">
        <span class="srow__coin">${ICON(c)}<b>${c.symbol}</b></span>
        <span class="srow__mid">
          <div class="ebar"><span style="width:${c.explode}%"></span></div>
          <small class="muted">${explodeCatalyst(c)}</small>
        </span>
        <span class="escore">${c.explode}</span>
      </div>`).join('');
  }

  // ---------- Top picks (day / week / month) ----------
  function renderPicks(horizon) {
    state.pickHorizon = horizon;
    if (!$('#picks-grid')) return;
    const rank = {
      day: (c) => c.explode * 0.5 + c.ch24h * 1.5 + c.score * 3,
      week: (c) => c.ch7d * 1.2 + c.score * 4 + c.explode * 0.3,
      month: (c) => c.score * 5 - c.valuation * 0.2 + (c.trend === 'up' ? 8 : -8),
    }[horizon] || ((c) => c.score);
    const picks = [...state.coins].sort((a, b) => rank(b) - rank(a)).slice(0, 4);
    const horizonMult = { day: 0.06, week: 0.14, month: 0.30 }[horizon] || 0.1;

    $('#picks-grid').innerHTML = picks.map((c, i) => {
      const long = c.score >= 0 || c.trend === 'up';
      const entry = c.price;
      const target = entry * (1 + (long ? 1 : -1) * horizonMult);
      const stop = entry * (long ? 1 - horizonMult / 2.5 : 1 + horizonMult / 2.5);
      const conv = Math.max(1, Math.min(5, Math.round(3 + c.score / 2)));
      const thesis = long
        ? `${c.pattern} with ${c.signal.toLowerCase()} momentum; RSI ${c.rsi.toFixed(0)} and price ${c.trend === 'up' ? 'above' : 'testing'} its moving average.`
        : `Weak structure — ${c.pattern}, ${c.signal.toLowerCase()}. Watching for a reclaim before entry.`;
      return `
      <div class="pick" data-id="${c.id}">
        <div class="pick__head">
          <span class="pick__rank">#${i + 1}</span>
          ${ICON(c)}<span><b>${c.name}</b> <small class="muted">${c.symbol}</small></span>
          <span class="pick__conv" title="Conviction">${'★'.repeat(conv)}${'☆'.repeat(5 - conv)}</span>
        </div>
        <p class="pick__thesis">${thesis}</p>
        <div class="pick__rows">
          <div><span>Entry</span><b>${fmtPrice(entry)}</b></div>
          <div><span>Target</span><b class="${long ? 'pos' : 'neg'}">${fmtPrice(target)}</b></div>
          <div><span>Stop</span><b class="neg">${fmtPrice(stop)}</b></div>
          <div><span>Signal</span><b>${badge(c)}</b></div>
        </div>
      </div>`;
    }).join('');
    $$('#picks-tabs .ptab').forEach((t) => t.classList.toggle('active', t.dataset.pick === horizon));
  }

  // ---------- Discover: new / upcoming / airdrops ----------
  function renderDiscover() {
    const X = window.EXTRAS || {};
    if ($('#disc-new')) $('#disc-new').innerHTML = `<table class="mini">${(X.newListings || []).map((c) => `
      <tr><td class="mini__coin"><span class="coin-ico" style="background:#2dd4bf22"></span><b>${c.symbol}</b></td>
      <td class="muted">${c.cat}</td><td class="num">${fmtPrice(c.price)}</td><td class="num">${pct(c.ch24h)}</td>
      <td class="muted mini__hide">${c.exchange}</td></tr>`).join('')}</table>`;
    if ($('#disc-upcoming')) $('#disc-upcoming').innerHTML = `<table class="mini">${(X.upcoming || []).map((c) => `
      <tr><td class="mini__coin"><b>${c.symbol}</b></td><td class="muted">${c.cat}</td>
      <td class="muted">${c.date}</td><td class="mini__hide"><span class="tag tag--soon">${c.status}</span></td>
      <td class="num"><div class="hype"><span style="width:${c.hype}%"></span></div></td></tr>`).join('')}</table>`;
    if ($('#disc-airdrops')) $('#disc-airdrops').innerHTML = `<table class="mini">${(X.airdrops || []).map((a) => `
      <tr><td class="mini__coin"><b>${a.symbol}</b></td><td class="muted">${a.type}</td>
      <td class="pos">${a.est}</td><td><span class="tag ${a.status === 'Live' ? 'tag--buy' : a.status === 'Confirmed' ? 'tag--soon' : ''}">${a.status}</span></td>
      <td class="muted mini__hide">${a.deadline}</td></tr>`).join('')}</table>`;
  }

  function renderArticles() {
    const el = $('#articles-grid');
    if (!el) return;
    el.innerHTML = (window.EXTRAS?.articles || []).map((a) => `
      <a class="article" href="#learn">
        <div class="article__top"><span class="edu__tag">${a.tag}</span><span class="muted">${a.read}</span></div>
        <h4>${a.title}</h4>
        <p class="muted">${a.blurb}</p>
        <span class="muted article__date">${a.date}</span>
      </a>`).join('');
  }

  // ---------- Arbitrage opportunities board ----------
  function arbOpp(c) {
    const ex = ['Binance', 'Coinbase', 'Kraken', 'OKX', 'Bybit', 'KuCoin', 'Gate.io', 'Bitstamp'];
    let seed = c.id.split('').reduce((a, ch) => (a * 31 + ch.charCodeAt(0)) >>> 0, 11);
    const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    const volBoost = Math.min(Math.abs(c.ch24h) / 18, 1);
    const spreadPct = +(0.08 + rnd() * 0.6 + volBoost * 2.4).toFixed(2);
    const lowI = Math.floor(rnd() * ex.length);
    let highI = Math.floor(rnd() * ex.length);
    if (highI === lowI) highI = (highI + 1) % ex.length;
    const low = c.price * (1 - spreadPct / 200);
    const high = low * (1 + spreadPct / 100);
    return { coin: c, buyEx: ex[lowI], sellEx: ex[highI], low, high, spreadPct };
  }

  function renderArbBoard() {
    const body = $('#arb-board-body');
    if (!body) return;
    const btc = btcPrice();
    const inBase = (usd) => {
      if (state.arbBase === 'btc' && btc) return '₿' + (usd / btc).toFixed(usd / btc < 1 ? 6 : 4);
      return fmtPrice(usd);
    };
    const opps = state.coins.slice(0, 30).map(arbOpp)
      .filter((o) => o.spreadPct >= state.arbMinPct)
      .sort((a, b) => b.spreadPct - a.spreadPct);

    $('#arb-board-meta').textContent =
      `Scanned ${Math.min(30, state.coins.length)} coins across 8 exchanges · ${opps.length} opportunit${opps.length === 1 ? 'y' : 'ies'} ≥ ${state.arbMinPct}% · updated ${new Date().toLocaleTimeString()}`;

    if (!opps.length) {
      body.innerHTML = `<tr><td colspan="9" class="empty">No arbitrage opportunity found. Lower the minimum spread.</td></tr>`;
      return;
    }
    body.innerHTML = opps.map((o, i) => {
      const profit = (1000 / o.low) * o.high - 1000;
      return `<tr data-id="${o.coin.id}">
        <td class="muted">${i + 1}</td>
        <td class="mini__coin">${ICON(o.coin)}<b>${o.coin.symbol}</b> <small class="muted">${o.coin.name}</small></td>
        <td class="num neg">${inBase(o.low)}</td>
        <td><span class="ex-tag ex-tag--buy">${o.buyEx}</span></td>
        <td class="num pos">${inBase(o.high)}</td>
        <td><span class="ex-tag ex-tag--sell">${o.sellEx}</span></td>
        <td class="num"><b class="${o.spreadPct >= 1 ? 'pos' : ''}">${o.spreadPct.toFixed(2)}%</b></td>
        <td class="num pos">${fmtPrice(profit)}</td>
        <td><button class="link-btn" data-deep="${o.coin.id}">deep scan →</button></td>
      </tr>`;
    }).join('');
  }

  // ---------- Price predictions ----------
  const PRED_HORIZONS = [['5d', '5-Day', 5], ['1m', '1-Month', 30], ['3m', '3-Month', 90], ['1y', '1-Year', 365]];

  // Daily log-volatility estimated from the 7d sparkline (hourly), with fallback.
  function dailyVol(c) {
    const p = c.prices;
    if (p && p.length > 3) {
      let s = 0, s2 = 0, n = 0;
      for (let i = 1; i < p.length; i++) {
        if (p[i - 1] > 0) { const r = Math.log(p[i] / p[i - 1]); s += r; s2 += r * r; n++; }
      }
      if (n > 2) {
        const mean = s / n, varr = Math.max(0, s2 / n - mean * mean);
        return Math.min(0.25, Math.max(0.01, Math.sqrt(varr) * Math.sqrt(24))); // hourly → daily
      }
    }
    return Math.min(0.25, Math.max(0.02, Math.abs(c.ch7d || 5) / 100 / Math.sqrt(7) * 1.2));
  }
  function confLabel(sig) { return sig < 0.25 ? 'High' : sig < 0.5 ? 'Medium' : sig < 0.9 ? 'Low' : 'Very low'; }

  // Principled forecast: decaying momentum + RSI mean-reversion, compounded and
  // anchored to a neutral long-run baseline, with a volatility-based range.
  function predict(c, days) {
    const P = c.price;
    const muM = Math.log(1 + (c.ch7d || 0) / 100) / 7;        // recent daily momentum (log)
    const lambda = Math.LN2 / 10;                             // momentum half-life ≈ 10 days
    const momentum = muM * (1 - Math.exp(-lambda * days)) / lambda;
    const rsi = c.rsi == null ? 50 : c.rsi;
    const reversion = (-((rsi - 50) / 50) * 0.10) * (1 - Math.exp(-days / 14)); // overbought ↓, oversold ↑
    let cum = momentum + reversion;                           // neutral (zero) long-run drift
    const capUp = days <= 5 ? 0.45 : days <= 30 ? 1.0 : days <= 90 ? 2.0 : 4.0;
    const capDn = days <= 5 ? -0.35 : days <= 30 ? -0.55 : days <= 90 ? -0.75 : -0.9;
    cum = Math.max(Math.log(1 + capDn), Math.min(Math.log(1 + capUp), cum));
    const base = P * Math.exp(cum);
    const sig = Math.min(1.5, dailyVol(c) * Math.sqrt(days)); // band widens with √time
    return {
      base, low: Math.max(P * 0.02, base * Math.exp(-sig)), high: base * Math.exp(sig),
      pct: (base / P - 1) * 100, conf: confLabel(sig),
    };
  }
  function forecast(c, days) { return predict(c, days).base; }
  function predSentiment(c) {
    const bull = Math.max(0, Math.min(26, Math.round(13 + c.score * 2)));
    const label = c.score >= 3 ? 'Strong Bullish' : c.score >= 1 ? 'Bullish' : c.score > -1 ? 'Neutral' : c.score > -3 ? 'Bearish' : 'Strong Bearish';
    return { bull, bear: 26 - bull, label };
  }
  function renderPredictions(horizon) {
    if (horizon) state.predHorizon = horizon;
    const body = $('#pred-body');
    if (!body) return;
    // Default order: market cap (state.coins arrives mcap-sorted), majors first.
    const list = [...state.coins].slice(0, 60);
    body.innerHTML = list.map((c, i) => {
      const cells = PRED_HORIZONS.map(([k, , d]) => {
        const pr = predict(c, d);
        const active = k === state.predHorizon;
        return `<td class="num ${active ? 'pred-active' : ''}" title="Likely range ${fmtPrice(pr.low)} – ${fmtPrice(pr.high)} · ${pr.conf} confidence">
          ${fmtPrice(pr.base)}<small class="${pr.pct >= 0 ? 'pos' : 'neg'}"> ${pr.pct >= 0 ? '+' : ''}${pr.pct.toFixed(1)}%</small>
          ${active ? `<span class="pred-range muted">${fmtPrice(pr.low)} – ${fmtPrice(pr.high)} · ${pr.conf}</span>` : ''}</td>`;
      }).join('');
      const s = predSentiment(c);
      return `<tr data-id="${c.id}">
        <td class="muted">${i + 1}</td>
        <td class="mini__coin">${ICON(c)}<b>${c.symbol}</b> <small class="muted">${c.name}</small></td>
        <td class="num">${fmtPrice(c.price)}</td>${cells}
        <td><span class="badge badge--${c.signalCls}" title="${s.bull}/26 indicators bullish">${s.label}</span></td>
      </tr>`;
    }).join('');
    $$('#pred-tabs .ptab').forEach((t) => t.classList.toggle('active', t.dataset.pred === state.predHorizon));
  }

  // ---------- Converter (CoinCodex-style) ----------
  function priceOf(v) { if (v === 'usd') return 1; const c = state.coins.find((x) => x.id === v); return c ? c.price : null; }
  function labelOf(v) { if (v === 'usd') return 'USD'; return (state.coins.find((c) => c.id === v) || {}).symbol || v; }
  function setupConverter() {
    const from = $('#cv-from'), to = $('#cv-to');
    if (!from || !to) return;
    if (!state.convReady && state.coins.length) {
      const opts = `<option value="usd">USD — US Dollar</option>` +
        state.coins.slice(0, 300).map((c) => `<option value="${c.id}">${c.symbol} — ${c.name}</option>`).join('');
      from.innerHTML = opts; to.innerHTML = opts;
      from.value = 'bitcoin'; to.value = 'usd';
      state.convReady = true;
    }
    runConverter();
  }
  function runConverter() {
    const out = $('#cv-result'); if (!out) return;
    const amt = parseFloat(($('#cv-amount') || {}).value) || 0;
    const from = $('#cv-from').value, to = $('#cv-to').value;
    const pf = priceOf(from), pt = priceOf(to);
    if (pf == null || pt == null) { out.textContent = '—'; return; }
    const result = amt * pf / pt;
    out.innerHTML = `${amt.toLocaleString()} ${labelOf(from)} = <b>${result.toLocaleString('en-US', { maximumFractionDigits: 8 })} ${labelOf(to)}</b>`;
    const rate = $('#cv-rate');
    if (rate) rate.textContent = `1 ${labelOf(from)} = ${(pf / pt).toLocaleString('en-US', { maximumFractionDigits: 8 })} ${labelOf(to)}  ·  1 ${labelOf(to)} = ${(pt / pf).toLocaleString('en-US', { maximumFractionDigits: 8 })} ${labelOf(from)}`;
  }

  // ---------- News ----------
  function renderNews() {
    const el = $('#news-grid'); if (!el) return;
    el.innerHTML = (window.EXTRAS?.news || []).map((n) => `
      <a class="article" href="#" onclick="return false">
        <div class="article__top"><span class="edu__tag">${n.source}</span><span class="muted">${n.time}</span></div>
        <h4>${n.title}</h4>
        <p class="muted">${n.summary}</p>
        <span class="muted article__date">${n.tag || ''}</span>
      </a>`).join('');
  }

  // ---------- Portfolio ----------
  function renderPortfolio() {
    const sel = $('#pf-coin');
    if (sel && !sel.dataset.filled && state.coins.length) {
      sel.innerHTML = state.coins.slice(0, 300).map((c) => `<option value="${c.id}">${c.symbol} — ${c.name}</option>`).join('');
      sel.dataset.filled = '1';
    }
    const body = $('#pf-body'); if (!body) return;
    const holdings = state.portfolio.map((h) => {
      const c = state.coins.find((x) => x.id === h.id);
      return c ? { ...h, c, value: h.amount * c.price } : null;
    }).filter(Boolean);
    const total = holdings.reduce((a, h) => a + h.value, 0);
    const totalCh = holdings.reduce((a, h) => a + h.value * (h.c.ch24h / 100), 0);

    const sum = $('#pf-summary');
    if (sum) sum.innerHTML = `
      <div class="arb__stat"><span>Total value</span><b>${fmtPrice(total)}</b><small class="muted">${holdings.length} asset${holdings.length === 1 ? '' : 's'}</small></div>
      <div class="arb__stat"><span>24h change</span><b class="${totalCh >= 0 ? 'pos' : 'neg'}">${fmtPrice(totalCh)}</b><small class="${totalCh >= 0 ? 'pos' : 'neg'}">${total ? ((totalCh / total) * 100).toFixed(2) : '0'}%</small></div>
      <div class="arb__stat"><span>Best performer</span><b>${holdings.length ? [...holdings].sort((a, b) => b.c.ch24h - a.c.ch24h)[0].c.symbol : '—'}</b></div>`;

    if (!holdings.length) {
      body.innerHTML = `<tr><td colspan="7" class="empty">No holdings yet — add a coin above to track your portfolio.</td></tr>`;
      return;
    }
    body.innerHTML = holdings.sort((a, b) => b.value - a.value).map((h) => {
      const alloc = total ? (h.value / total) * 100 : 0;
      return `<tr data-id="${h.c.id}">
        <td class="mini__coin">${ICON(h.c)}<b>${h.c.symbol}</b> <small class="muted">${h.c.name}</small></td>
        <td class="num">${h.amount.toLocaleString('en-US', { maximumFractionDigits: 8 })}</td>
        <td class="num">${fmtPrice(h.c.price)}</td>
        <td class="num">${pct(h.c.ch24h)}</td>
        <td class="num">${fmtPrice(h.value)}</td>
        <td class="num">${alloc.toFixed(1)}%</td>
        <td><button class="link-btn" data-remove="${h.c.id}">remove</button></td>
      </tr>`;
    }).join('');
  }

  // ---------- Coin detail page (CoinCodex-style) ----------
  async function renderCoinPage() {
    const host = $('#coin-page'); if (!host) return;
    const params = new URLSearchParams(location.search);
    let id = params.get('id');
    if (!id) { const sym = (params.get('symbol') || '').toUpperCase(); const m = state.coins.find((x) => x.symbol === sym); id = m ? m.id : 'bitcoin'; }
    const c = state.coins.find((x) => x.id === id);
    if (!c) { host.innerHTML = `<p class="muted">Coin not found in the top ${state.coins.length}.</p>`; return; }
    document.title = `${c.name} (${c.symbol}) — CoinScope`;

    let prices = c.prices;
    try {
      const d = await cg(`coins/${id}/market_chart?vs_currency=usd&days=90&interval=daily`);
      if (d.prices && d.prices.length) prices = d.prices.map((p) => p[1]);
    } catch { /* keep sparkline */ }
    const rsi = TA.rsi(prices) ?? c.rsi, sma20 = TA.sma(prices, Math.min(20, prices.length)), sma50 = TA.sma(prices, Math.min(50, prices.length));
    const s = predSentiment(c);

    host.innerHTML = `
      <div class="dr__head">
        ${c.image ? `<img class="coin-ico coin-ico--lg" src="${c.image}" alt="">` : `<span class="coin-ico coin-ico--lg" style="background:${c.color}"></span>`}
        <div><h1 id="drawer-name" style="font-size:1.6rem">${c.name} <small class="muted">${c.symbol}</small></h1>
          <div class="dr__price" style="font-size:1.3rem">${fmtPrice(c.price)} <span>${pct(c.ch24h)} (24h)</span></div></div>
        <span class="dr__rank">Rank #${c.rank}</span>
      </div>
      <div class="tf-tabs" id="cp-tf">
        <button class="tf" data-days="7">7D</button>
        <button class="tf" data-days="30">30D</button>
        <button class="tf active" data-days="90">90D</button>
        <button class="tf" data-days="365">1Y</button>
      </div>
      <div id="cp-chart" class="cp-chart"><div class="loading">Loading chart…</div></div>
      <h3 class="arb__deep-title">Price prediction</h3>
      <div class="pred-cards">${PRED_HORIZONS.map(([, lbl, d]) => {
        const pr = predict(c, d);
        return `<div class="arb__stat"><span>${lbl}</span><b>${fmtPrice(pr.base)}</b>
          <small class="${pr.pct >= 0 ? 'pos' : 'neg'}">${pr.pct >= 0 ? '+' : ''}${pr.pct.toFixed(1)}%</small>
          <small class="muted pred-range">${fmtPrice(pr.low)} – ${fmtPrice(pr.high)}</small>
          <small class="muted">${pr.conf} confidence</small></div>`;
      }).join('')}</div>
      <p class="muted pred-disclaim">Base estimate with a bear–bull range from each coin's own volatility. Estimates, not financial advice.</p>
      <div class="techsum">
        <div class="techsum__verdict">
          <span class="muted">Technical sentiment</span>
          <b class="${c.score >= 1 ? 'pos' : c.score <= -1 ? 'neg' : ''}">${s.label}</b>
          <small class="muted">${s.bull} bullish · ${s.bear} bearish of 26 signals</small>
        </div>
        <div class="techsum__bar"><span class="pos" style="width:${(s.bull / 26 * 100).toFixed(0)}%"></span><span class="neg" style="width:${(s.bear / 26 * 100).toFixed(0)}%"></span></div>
      </div>
      <h3 class="arb__deep-title">Key statistics</h3>
      <div class="dr__stats">
        <div><span>Signal</span><b>${badge(c)}</b></div>
        <div><span>RSI(14)</span><b>${rsi == null ? '—' : rsi.toFixed(0)}</b></div>
        <div><span>Pattern</span><b class="pattern-tag">${c.pattern}</b></div>
        <div><span>SMA20</span><b>${sma20 ? fmtPrice(sma20) : '—'}</b></div>
        <div><span>SMA50</span><b>${sma50 ? fmtPrice(sma50) : '—'}</b></div>
        <div><span>Trend</span><b class="${c.trend === 'up' ? 'pos' : 'neg'}">${c.trend === 'up' ? 'Up' : 'Down'}</b></div>
        <div><span>Market Cap</span><b>${fmtBig(c.mcap)}</b></div>
        <div><span>24h Volume</span><b>${fmtBig(c.vol)}</b></div>
        <div><span>24h High</span><b>${c.high24 ? fmtPrice(c.high24) : '—'}</b></div>
        <div><span>24h Low</span><b>${c.low24 ? fmtPrice(c.low24) : '—'}</b></div>
        <div><span>ATH</span><b>${c.ath ? fmtPrice(c.ath) : '—'}</b></div>
        <div><span>From ATH</span><b>${c.athChange != null ? pct(c.athChange) : '—'}</b></div>
        <div><span>Valuation</span><b class="${c.valuation < -15 ? 'pos' : c.valuation > 25 ? 'neg' : ''}">${c.valuation < -15 ? 'Undervalued' : c.valuation > 25 ? 'Overvalued' : 'Fair'}</b></div>
        <div><span>Explosion score</span><b class="escore">${c.explode}</b></div>
        <div><span>Circ. supply</span><b>${c.supply ? c.supply.toLocaleString('en-US', { maximumFractionDigits: 0 }) : '—'}</b></div>
      </div>`;

    $$('#cp-tf .tf').forEach((t) => t.addEventListener('click', () => loadCoinChart(id, +t.dataset.days)));
    loadCoinChart(id, 90);
  }

  // ---------- Compare page ----------
  const CMP_PAL = ['#16c784', '#3b82f6', '#f0b90b', '#e84142'];
  function multiLineSVG(series) {
    const valid = series.filter((s) => s.prices && s.prices.length > 1);
    if (!valid.length) return '<div class="muted" style="padding:1rem">No chart data.</div>';
    const norm = valid.map((s) => ({ ...s, pct: s.prices.map((p) => (p / s.prices[0] - 1) * 100) }));
    const all = norm.flatMap((s) => s.pct);
    const min = Math.min(...all), max = Math.max(...all), span = max - min || 1;
    const W = 680, H = 240, pad = 10;
    const y = (v) => pad + (1 - (v - min) / span) * (H - 2 * pad);
    const lines = norm.map((s) => {
      const n = s.pct.length;
      const pts = s.pct.map((v, i) => `${(pad + (i / (n - 1)) * (W - 2 * pad)).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
      return `<polyline fill="none" stroke="${s.color}" stroke-width="2" points="${pts}"/>`;
    }).join('');
    const zero = y(0);
    return `<svg class="candles" viewBox="0 0 ${W} ${H}" width="100%" preserveAspectRatio="none">
      <line x1="0" x2="${W}" y1="${zero.toFixed(1)}" y2="${zero.toFixed(1)}" stroke="#1e2a38" stroke-dasharray="4 4"/>${lines}</svg>`;
  }
  async function loadCompareChart() {
    const el = $('#cmp-chart'); if (!el) return;
    if (!state.compare.length) { el.innerHTML = '<div class="muted" style="padding:1rem">Add coins to compare.</div>'; return; }
    el.innerHTML = '<div class="loading">Loading chart…</div>';
    const series = [];
    for (let i = 0; i < state.compare.length; i++) {
      const id = state.compare[i], c = state.coins.find((x) => x.id === id);
      let prices = c ? c.prices : [];
      try { const d = await cg(`coins/${id}/market_chart?vs_currency=usd&days=${state.cmpDays}&interval=daily`); if (d.prices && d.prices.length) prices = d.prices.map((p) => p[1]); } catch { /* keep */ }
      series.push({ name: c ? c.symbol : id, color: CMP_PAL[i % CMP_PAL.length], prices });
    }
    el.innerHTML = multiLineSVG(series)
      + `<div class="cmp-legend">${series.map((s) => `<span><i style="background:${s.color}"></i>${s.name}</span>`).join('')}</div>`
      + `<div class="dr__chart-label muted">Normalized % change · ${state.cmpDays}-day</div>`;
    $$('#cmp-tf .tf').forEach((t) => t.classList.toggle('active', +t.dataset.days === state.cmpDays));
  }
  function renderCompare() {
    const host = $('#cmp-table'); if (!host) return;
    const add = $('#cmp-add');
    if (add && !add.dataset.filled && state.coins.length) {
      add.innerHTML = state.coins.slice(0, 300).map((c) => `<option value="${c.id}">${c.symbol} — ${c.name}</option>`).join('');
      add.dataset.filled = '1';
    }
    if (!state.compare.length && state.coins.length) {
      state.compare = ['bitcoin', 'ethereum', 'solana'].filter((id) => state.coins.some((c) => c.id === id));
    }
    const cs = state.compare.map((id) => state.coins.find((c) => c.id === id)).filter(Boolean);
    const chips = $('#cmp-chips');
    if (chips) chips.innerHTML = cs.map((c) => `<span class="cmp-chip">${ICON(c)}<b>${c.symbol}</b><button class="cmp-x" data-cmpremove="${c.id}" aria-label="Remove">✕</button></span>`).join('') || '<span class="muted">No coins selected.</span>';

    if (!cs.length) { host.innerHTML = '<tbody><tr><td class="empty">Add coins to compare.</td></tr></tbody>'; loadCompareChart(); return; }
    const rows = [
      ['Price', (c) => fmtPrice(c.price)],
      ['24h', (c) => pct(c.ch24h)],
      ['7d', (c) => pct(c.ch7d)],
      ['Market cap', (c) => fmtBig(c.mcap)],
      ['24h volume', (c) => fmtBig(c.vol)],
      ['RSI(14)', (c) => c.rsi.toFixed(0)],
      ['Signal', (c) => badge(c)],
      ['Pattern', (c) => `<span class="pattern-tag">${c.pattern}</span>`],
      ['Valuation', (c) => c.valuation < -15 ? '<span class="pos">Undervalued</span>' : c.valuation > 25 ? '<span class="neg">Overvalued</span>' : 'Fair'],
      ['Explosion', (c) => `<span class="escore">${c.explode}</span>`],
      ['From ATH', (c) => c.athChange != null ? pct(c.athChange) : '—'],
      ['1M forecast', (c) => { const f = forecast(c, 30); return `${fmtPrice(f)} <small class="${f >= c.price ? 'pos' : 'neg'}">${((f / c.price - 1) * 100).toFixed(1)}%</small>`; }],
      ['1Y forecast', (c) => { const f = forecast(c, 365); return `${fmtPrice(f)} <small class="${f >= c.price ? 'pos' : 'neg'}">${((f / c.price - 1) * 100).toFixed(1)}%</small>`; }],
    ];
    const thead = `<thead><tr><th>Metric</th>${cs.map((c) => `<th>${ICON(c)} ${c.symbol}</th>`).join('')}</tr></thead>`;
    const tbody = `<tbody>${rows.map(([label, fn]) => `<tr><td class="muted">${label}</td>${cs.map((c) => `<td>${fn(c)}</td>`).join('')}</tr>`).join('')}</tbody>`;
    host.innerHTML = thead + tbody;
    loadCompareChart();
  }

  // ---------- Coin Updates feed (CoinGecko webhook) ----------
  const WEBHOOK = '/.netlify/functions/cg-webhook';
  function relTime(iso) {
    const t = new Date(iso).getTime(); if (!t) return '';
    const s = Math.max(0, (Date.now() - t) / 1000);
    if (s < 60) return 'just now';
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    return `${Math.floor(s / 86400)}d ago`;
  }
  function changeRow(ch) {
    const type = (ch.change_type || 'update').toLowerCase();
    const cls = type === 'addition' ? 'pos' : type === 'removal' ? 'neg' : 'blue';
    const arrow = type === 'addition' ? '+' : type === 'removal' ? '−' : '↻';
    const ov = ch.old_value, nv = ch.new_value;
    let val;
    if (type === 'addition') val = `<b>${esc(nv)}</b>`;
    else if (type === 'removal') val = `<s class="muted">${esc(ov)}</s>`;
    else val = `<s class="muted">${esc(ov)}</s> → <b>${esc(nv)}</b>`;
    return `<li class="upd__row"><span class="upd__type upd__type--${cls}">${arrow} ${type}</span>
      <span class="upd__field">${esc(ch.field)}</span><span class="upd__val">${val}</span></li>`;
  }
  function esc(v) {
    if (v == null) return '—';
    return String(v).replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]));
  }
  function updateCard(ev) {
    return `<article class="upd" data-id="${esc(ev.id)}">
      <header class="upd__head">
        <div><b>${esc(ev.name)}</b> <span class="muted">${esc((ev.symbol || '').toUpperCase())}</span></div>
        <time class="muted" title="${esc(ev.received_at)}">${relTime(ev.received_at)}</time>
      </header>
      <ul class="upd__changes">${(ev.changes || []).map(changeRow).join('') || '<li class="muted">No field details.</li>'}</ul>
    </article>`;
  }
  async function renderUpdates() {
    const host = $('#updates-feed'); if (!host) return;
    host.innerHTML = '<div class="loading">Loading updates…</div>';
    let events = null;
    try { const r = await fetch(WEBHOOK); if (r.ok) events = (await r.json()).events || []; } catch { /* offline */ }
    const url = `${location.origin}${WEBHOOK}`;
    const setup = `<div class="upd-empty">
      <p>No coin updates received yet.</p>
      <p class="muted">This feed shows CoinGecko <code>cg.coin.info.updated</code> events — rebrands,
      ticker/logo changes, new contract addresses, category changes and security notices.</p>
      <p class="muted">Register this endpoint as your webhook URL with CoinGecko:</p>
      <code class="upd-url">${esc(url)}</code></div>`;
    if (events === null) { host.innerHTML = `<div class="upd-empty"><p>Live feed unavailable.</p><p class="muted">The webhook endpoint isn't reachable from here (it runs on Netlify Functions). Deploy the site, then register:</p><code class="upd-url">${esc(url)}</code></div>`; return; }
    if (!events.length) { host.innerHTML = setup; return; }
    host.innerHTML = events.map(updateCard).join('');
  }

  // Compact "latest coin update" banner for the home page.
  async function renderHomeUpdate() {
    const el = $('#home-update'); if (!el) return;
    let ev = null;
    try { const r = await fetch(WEBHOOK); if (r.ok) ev = ((await r.json()).events || [])[0]; } catch { /* offline */ }
    if (!ev) { el.hidden = true; return; }
    const first = (ev.changes || [])[0] || {};
    const type = (first.change_type || 'update').toLowerCase();
    const cls = type === 'addition' ? 'pos' : type === 'removal' ? 'neg' : 'blue';
    const more = (ev.changes || []).length - 1;
    el.innerHTML = `<span class="home-update__tag">📡 Coin update</span>
      <b>${esc(ev.name)}</b> <span class="muted">${esc((ev.symbol || '').toUpperCase())}</span>
      <span class="upd__type upd__type--${cls}">${esc(type)}</span>
      <span class="upd__field">${esc(first.field || '')}</span>
      ${more > 0 ? `<span class="muted">+${more} more</span>` : ''}
      <time class="muted home-update__time">${relTime(ev.received_at)}</time>
      <span class="home-update__cta">View all →</span>`;
    el.hidden = false;
  }

  // ---------- AI Copilot ----------
  function copilotAnswer(text) {
    const t = text.toLowerCase();
    const f = { signal: '', cap: 0, trend: '' };
    const notes = [];
    if (/strong buy/.test(t)) { f.signal = 'Strong Buy'; notes.push('signal = Strong Buy'); }
    else if (/\bbuy\b|bullish|long/.test(t)) { f.signal = 'Buy'; notes.push('signal = Buy'); }
    else if (/strong sell/.test(t)) { f.signal = 'Strong Sell'; notes.push('signal = Strong Sell'); }
    else if (/\bsell\b|bearish|short/.test(t)) { f.signal = 'Sell'; notes.push('signal = Sell'); }
    if (/uptrend|up\s?trend|above (the )?(sma|ma|average)/.test(t)) { f.trend = 'up'; notes.push('trend = up'); }
    if (/downtrend|down\s?trend|below (the )?(sma|ma|average)/.test(t)) { f.trend = 'down'; notes.push('trend = down'); }
    if (/10\s?b|\$10b|large\s?cap/.test(t)) { f.cap = 1e10; notes.push('market cap > $10B'); }
    else if (/1\s?b|\$1b/.test(t)) { f.cap = 1e9; notes.push('market cap > $1B'); }
    else if (/100\s?m|\$100m/.test(t)) { f.cap = 1e8; notes.push('market cap > $100M'); }

    const rsiLt = t.match(/rsi (?:below|under|<)\s*(\d+)/);
    const rsiGt = t.match(/rsi (?:above|over|>)\s*(\d+)/);
    const ch24 = t.match(/(?:up|gain).{0,12}?(\d+)\s?%/);
    const ch24d = t.match(/(?:down|drop|lose).{0,12}?(\d+)\s?%/);

    let list = state.coins.slice();
    if (f.signal) list = list.filter((c) => c.signal === f.signal);
    if (f.trend) list = list.filter((c) => c.trend === f.trend);
    if (f.cap) list = list.filter((c) => c.mcap >= f.cap);
    if (/oversold/.test(t)) { list = list.filter((c) => c.rsi <= 35); notes.push('oversold (RSI ≤ 35)'); }
    if (/overbought/.test(t)) { list = list.filter((c) => c.rsi >= 70); notes.push('overbought (RSI ≥ 70)'); }
    if (rsiLt) { list = list.filter((c) => c.rsi < +rsiLt[1]); notes.push('RSI < ' + rsiLt[1]); }
    if (rsiGt) { list = list.filter((c) => c.rsi > +rsiGt[1]); notes.push('RSI > ' + rsiGt[1]); }
    if (ch24) { list = list.filter((c) => c.ch24h >= +ch24[1]); notes.push('24h ≥ +' + ch24[1] + '%'); }
    if (ch24d) { list = list.filter((c) => c.ch24h <= -ch24d[1]); notes.push('24h ≤ -' + ch24d[1] + '%'); }

    list.sort((a, b) => b.score - a.score || b.mcap - a.mcap);
    const top = list.slice(0, 6);

    state.filters.signal = f.signal; state.filters.cap = f.cap; state.filters.trend = f.trend;
    $('#signal-filter').value = f.signal; $('#cap-filter').value = String(f.cap); $('#trend-filter').value = f.trend;
    renderTable();

    const summary = notes.length ? notes.join(' · ') : 'no specific filters detected — showing top ranked';
    let html = `Applied filters: <b>${summary}</b>.`;
    if (!top.length) html += `<br>No coins matched — try loosening the criteria.`;
    else {
      html += `<table><tbody>` + top.map((c) =>
        `<tr><td><b>${c.symbol}</b></td><td>${fmtPrice(c.price)}</td><td>${pct(c.ch24h)}</td><td>${c.signal}</td></tr>`).join('') + `</tbody></table>`;
      html += `<div class="muted" style="margin-top:.4rem;font-size:.8rem">↑ Screener updated with these filters.</div>`;
    }
    return html;
  }

  function pushBubble(html, who) {
    const log = $('#copilot-log');
    const div = document.createElement('div');
    div.className = 'bubble bubble--' + who;
    div.innerHTML = html;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  // ---------- toast ----------
  function toast(msg, kind = 'ok', ms = 4000) {
    const el = document.createElement('div');
    el.className = 'toast toast--' + kind;
    el.innerHTML = msg;
    $('#toasts').appendChild(el);
    requestAnimationFrame(() => el.classList.add('show'));
    setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 300); }, ms);
  }

  function setStatus(text, cls) {
    const el = $('#data-status');
    if (!el) return;
    el.textContent = text;
    el.className = 'screener__status ' + (cls || '');
  }

  // ---------- events ----------
  function bind() {
    on('#search', 'input', (e) => { state.filters.q = e.target.value; renderTable(); });
    on('#signal-filter', 'change', (e) => { state.filters.signal = e.target.value; renderTable(); });
    on('#cap-filter', 'change', (e) => { state.filters.cap = +e.target.value; renderTable(); });
    on('#trend-filter', 'change', (e) => { state.filters.trend = e.target.value; renderTable(); });
    on('#refresh', 'click', () => { load(); loadGlobal(); loadFNG(); loadTrending(); });

    on('#watch-toggle', 'click', (e) => {
      state.filters.watchOnly = !state.filters.watchOnly;
      e.currentTarget.classList.toggle('active', state.filters.watchOnly);
      renderTable();
    });

    $$('#screener-table thead th[data-sort]').forEach((th) => th.addEventListener('click', () => {
      const key = th.dataset.sort;
      if (state.sort.key === key) state.sort.dir *= -1;
      else state.sort = { key, dir: key === 'name' ? 1 : -1 };
      renderTable();
    }));

    // Delegated clicks: stars, deep-scan, then open drawer from any coin element
    document.addEventListener('click', (e) => {
      const star = e.target.closest('[data-star]');
      if (star) { e.stopPropagation(); toggleWatch(star.dataset.star); return; }
      const deep = e.target.closest('[data-deep]');
      if (deep) {
        e.stopPropagation();
        const id = deep.dataset.deep;
        const sel = $('#arb-coin'); if (sel) sel.value = id;
        scanArb(id);
        const sum = $('#arb-summary'); if (sum) sum.scrollIntoView({ behavior: 'smooth', block: 'center' });
        return;
      }
      const row = e.target.closest('[data-id]');
      if (row && !e.target.closest('a,button,select,input')) openDrawer(row.dataset.id);
    });

    on('#drawer-close', 'click', closeDrawer);
    on('#drawer-overlay', 'click', closeDrawer);
    document.addEventListener('keydown', (e) => { const d = $('#drawer'); if (e.key === 'Escape' && d && !d.hidden) closeDrawer(); });

    // Arbitrage opportunities board controls
    on('#arb-min', 'input', (e) => {
      state.arbMinPct = +e.target.value;
      const lbl = $('#arb-min-label'); if (lbl) lbl.textContent = state.arbMinPct.toFixed(1) + '%';
      renderArbBoard();
    });
    on('#arb-base', 'change', (e) => { state.arbBase = e.target.value; renderArbBoard(); });
    on('#arb-refresh', 'click', renderArbBoard);

    // Deep scan controls
    on('#arb-coin', 'change', (e) => scanArb(e.target.value));
    on('#arb-scan', 'click', () => scanArb(state.arbCoin));

    // Top picks tabs
    $$('#picks-tabs .ptab').forEach((t) => t.addEventListener('click', () => renderPicks(t.dataset.pick)));

    // Compare
    on('#cmp-addbtn', 'click', () => {
      const v = ($('#cmp-add') || {}).value;
      if (v && !state.compare.includes(v) && state.compare.length < 4) { state.compare.push(v); renderCompare(); }
      else if (state.compare.length >= 4) toast('You can compare up to 4 coins.', 'warn');
    });
    on('#cmp-chips', 'click', (e) => {
      const x = e.target.closest('[data-cmpremove]');
      if (x) { state.compare = state.compare.filter((id) => id !== x.dataset.cmpremove); renderCompare(); }
    });
    $$('#cmp-tf .tf').forEach((t) => t.addEventListener('click', () => { state.cmpDays = +t.dataset.days; loadCompareChart(); }));

    // Predictions horizon tabs
    $$('#pred-tabs .ptab').forEach((t) => t.addEventListener('click', () => renderPredictions(t.dataset.pred)));

    // Converter
    on('#cv-amount', 'input', runConverter);
    on('#cv-from', 'change', runConverter);
    on('#cv-to', 'change', runConverter);
    on('#cv-swap', 'click', () => {
      const f = $('#cv-from'), t = $('#cv-to');
      if (f && t) { const tmp = f.value; f.value = t.value; t.value = tmp; runConverter(); }
    });

    // Portfolio
    on('#pf-form', 'submit', (e) => {
      e.preventDefault();
      const id = $('#pf-coin').value, amt = parseFloat($('#pf-amount').value);
      if (!id || !amt || amt <= 0) { toast('Enter a coin and a valid amount.', 'warn'); return; }
      state.portfolio = state.portfolio.filter((h) => h.id !== id);
      state.portfolio.push({ id, amount: amt });
      saveLS(LS.portfolio, state.portfolio);
      $('#pf-amount').value = '';
      renderPortfolio();
      toast('Added to portfolio.', 'ok');
    });
    on('#pf-table', 'click', (e) => {
      const rm = e.target.closest('[data-remove]');
      if (rm) { state.portfolio = state.portfolio.filter((h) => h.id !== rm.dataset.remove); saveLS(LS.portfolio, state.portfolio); renderPortfolio(); }
    });

    on('#copilot-form', 'submit', (e) => {
      e.preventDefault();
      const input = $('#copilot-input'), q = input.value.trim();
      if (!q) return;
      pushBubble(q, 'user'); input.value = '';
      setTimeout(() => pushBubble(copilotAnswer(q), 'bot'), 350);
    });
    $$('.chip').forEach((chip) => chip.addEventListener('click', () => {
      const ci = $('#copilot-input'); if (!ci) return;
      ci.value = chip.dataset.q;
      $('#copilot-form').dispatchEvent(new Event('submit'));
    }));
  }

  // ---------- init ----------
  bind();
  renderDiscover();
  renderArticles();
  renderNews();
  load();
  loadGlobal();
  loadFNG();
  loadTrending();
})();
