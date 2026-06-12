/* ===== app.js — CoinScope front-end logic ===== */
(() => {
  'use strict';

  const CG = 'https://api.coingecko.com/api/v3';
  const API_MARKETS = CG + '/coins/markets'
    + '?vs_currency=usd&order=market_cap_desc&per_page=100&page=1'
    + '&sparkline=true&price_change_percentage=1h%2C24h%2C7d';

  const LS = {
    watch: 'cs_watch',
    alerts: 'cs_alerts',
  };

  const state = {
    coins: [],
    sort: { key: 'mcap', dir: -1 },
    filters: { q: '', signal: '', cap: 0, trend: '', watchOnly: false },
    live: false,
    watch: new Set(loadLS(LS.watch, [])),
    alerts: loadLS(LS.alerts, []),
    arbCoin: 'bitcoin',
  };

  // ---------- helpers ----------
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
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
    let raw;
    try {
      raw = await getJSON(API_MARKETS);
      if (!Array.isArray(raw) || !raw.length) throw new Error('empty');
      state.live = true;
    } catch (err) {
      console.warn('Live API unavailable, using fallback:', err.message);
      raw = FALLBACK_DATA;
      state.live = false;
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
    return {
      id: c.id, name: c.name, symbol: (c.symbol || '').toUpperCase(),
      price: c.current_price, rank: c.market_cap_rank ?? 999,
      ch1h: c.price_change_percentage_1h_in_currency ?? null,
      ch24h, ch7d, mcap: c.market_cap ?? 0, vol: c.total_volume ?? 0,
      high24: c.high_24h, low24: c.low_24h, ath: c.ath, athChange: c.ath_change_percentage,
      supply: c.circulating_supply, image: c.image,
      prices, rsi: sig.rsi, signal: sig.label, signalCls: sig.cls, score: sig.score,
      pattern: TA.detectPattern({ prices, ch7d }),
      trend: slow ? (c.current_price > slow ? 'up' : 'down') : 'up',
      color: colorFor(c),
    };
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
    const list = applyFilters();
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
    const html = state.coins.slice(0, 16).map((c) =>
      `<span class="ticker__item"><span class="sym">${c.symbol}</span><span>${fmtPrice(c.price)}</span>${pct(c.ch24h)}</span>`).join('');
    $('#ticker-track').innerHTML = html + html;
  }

  function renderMovers() {
    const top = [...state.coins].sort((a, b) => b.ch24h - a.ch24h).slice(0, 6);
    $('#hero-movers').innerHTML = top.map((c) => `
      <li data-id="${c.id}">
        ${c.image ? `<img class="coin-ico" src="${c.image}" alt="">` : `<span class="coin-ico" style="background:${c.color}"></span>`}
        <span class="coin-name"><b>${c.name}</b><small>${c.symbol}</small></span>
        <span>${fmtPrice(c.price)}</span><span>${pct(c.ch24h)}</span>
      </li>`).join('');
  }

  const TIMEFRAMES = ['15m', '1h', '4h', '1d'];
  function renderPatterns() {
    const picks = [...state.coins].sort((a, b) => Math.abs(b.ch7d) - Math.abs(a.ch7d)).slice(0, 6);
    $('#patterns-grid').innerHTML = picks.map((c, i) => {
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
    const buys = [...state.coins].filter((c) => c.signal === 'Strong Buy' || c.signal === 'Buy').sort((a, b) => b.score - a.score).slice(0, 3);
    const fill = buys.length ? buys : [...state.coins].sort((a, b) => b.score - a.score).slice(0, 3);
    $('#signals-grid').innerHTML = fill.map((c) => {
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
    try { g = (await getJSON(CG + '/global')).data; }
    catch { g = FALLBACK_GLOBAL.data; }
    const set = (id, v) => { const el = $(id); if (el) el.textContent = v; };
    set('#g-mcap', fmtBig(g.total_market_cap.usd));
    $('#g-mcap-ch').innerHTML = pct(g.market_cap_change_percentage_24h_usd);
    set('#g-vol', fmtBig(g.total_volume.usd));
    set('#g-btc', g.market_cap_percentage.btc.toFixed(1) + '%');
    set('#g-eth', (g.market_cap_percentage.eth ?? 0).toFixed(1) + '%');
    set('#g-coins', (g.active_cryptocurrencies ?? 0).toLocaleString());
  }

  // ---------- Fear & Greed gauge ----------
  async function loadFNG() {
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
    let coins;
    try { coins = (await getJSON(CG + '/search/trending')).coins; }
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
    const coins = [...state.coins].sort((a, b) => b.mcap - a.mcap).slice(0, 30);
    const max = Math.max(...coins.map((c) => c.mcap)) || 1;
    $('#heatmap').innerHTML = coins.map((c) => {
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
      const d = await getJSON(`${CG}/coins/${id}/market_chart?vs_currency=usd&days=30&interval=daily`);
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
        </div>
        <span class="dr__rank">Rank #${c.rank}</span>
      </div>

      ${areaSVG(prices, c.ch7d >= 0)}

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
    <div class="dr__chart-label muted">Last ${n} data points · 30-day price</div>`;
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
      const d = await getJSON(`${CG}/coins/${id}/tickers?include_exchange_logo=false&depth=false`);
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
    el.textContent = text;
    el.className = 'screener__status ' + (cls || '');
  }

  // ---------- events ----------
  function bind() {
    $('#search').addEventListener('input', (e) => { state.filters.q = e.target.value; renderTable(); });
    $('#signal-filter').addEventListener('change', (e) => { state.filters.signal = e.target.value; renderTable(); });
    $('#cap-filter').addEventListener('change', (e) => { state.filters.cap = +e.target.value; renderTable(); });
    $('#trend-filter').addEventListener('change', (e) => { state.filters.trend = e.target.value; renderTable(); });
    $('#refresh').addEventListener('click', () => { load(); loadGlobal(); loadFNG(); loadTrending(); });

    $('#watch-toggle').addEventListener('click', (e) => {
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

    // Delegated clicks: stars + open drawer from any coin element
    document.addEventListener('click', (e) => {
      const star = e.target.closest('[data-star]');
      if (star) { e.stopPropagation(); toggleWatch(star.dataset.star); return; }
      const row = e.target.closest('[data-id]');
      if (row && !e.target.closest('a,button,select,input')) openDrawer(row.dataset.id);
    });

    $('#drawer-close').addEventListener('click', closeDrawer);
    $('#drawer-overlay').addEventListener('click', closeDrawer);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('#drawer').hidden) closeDrawer(); });

    $('#arb-coin').addEventListener('change', (e) => scanArb(e.target.value));
    $('#arb-refresh').addEventListener('click', () => scanArb(state.arbCoin));

    $('#copilot-form').addEventListener('submit', (e) => {
      e.preventDefault();
      const input = $('#copilot-input'), q = input.value.trim();
      if (!q) return;
      pushBubble(q, 'user'); input.value = '';
      setTimeout(() => pushBubble(copilotAnswer(q), 'bot'), 350);
    });
    $$('.chip').forEach((chip) => chip.addEventListener('click', () => {
      $('#copilot-input').value = chip.dataset.q;
      $('#copilot-form').dispatchEvent(new Event('submit'));
      document.getElementById('copilot').scrollIntoView({ behavior: 'smooth' });
    }));
  }

  // ---------- init ----------
  bind();
  load();
  loadGlobal();
  loadFNG();
  loadTrending();
})();
