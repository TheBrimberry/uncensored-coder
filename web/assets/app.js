/* ===== app.js — CoinScope front-end logic ===== */
(() => {
  'use strict';

  const API = 'https://api.coingecko.com/api/v3/coins/markets'
    + '?vs_currency=usd&order=market_cap_desc&per_page=100&page=1'
    + '&sparkline=true&price_change_percentage=1h%2C24h%2C7d';

  const state = {
    coins: [],        // normalized + enriched coins
    sort: { key: 'mcap', dir: -1 },
    filters: { q: '', signal: '', cap: 0, trend: '' },
    live: false,
  };

  // ---------- helpers ----------
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

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
    return '$' + n.toLocaleString();
  };
  const pct = (n) => {
    if (n == null) return '<span class="muted">—</span>';
    const cls = n >= 0 ? 'pos' : 'neg';
    const sign = n >= 0 ? '+' : '';
    return `<span class="${cls}">${sign}${n.toFixed(2)}%</span>`;
  };
  const colorFor = (c) => c.color || '#' + (c.id || 'aaa').split('').reduce((a, ch) => (a * 33 + ch.charCodeAt(0)) >>> 0, 7).toString(16).slice(0, 6).padEnd(6, 'a');

  // ---------- data ----------
  async function load() {
    setStatus('Loading…', '');
    let raw;
    try {
      const res = await fetch(API, { headers: { accept: 'application/json' } });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      raw = await res.json();
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
  }

  function enrich(c) {
    const prices = (c.sparkline_in_7d && c.sparkline_in_7d.price) || [];
    const ch24h = c.price_change_percentage_24h_in_currency ?? c.price_change_percentage_24h ?? 0;
    const ch7d = c.price_change_percentage_7d_in_currency ?? 0;
    const sig = TA.signal({ prices, ch24h, ch7d });
    const slow = TA.sma(prices, Math.min(30, prices.length));
    return {
      id: c.id,
      name: c.name,
      symbol: (c.symbol || '').toUpperCase(),
      price: c.current_price,
      rank: c.market_cap_rank ?? 999,
      ch1h: c.price_change_percentage_1h_in_currency ?? null,
      ch24h, ch7d,
      mcap: c.market_cap ?? 0,
      vol: c.total_volume ?? 0,
      prices,
      rsi: sig.rsi,
      signal: sig.label,
      signalCls: sig.cls,
      score: sig.score,
      pattern: TA.detectPattern({ prices, ch7d }),
      trend: slow ? (c.current_price > slow ? 'up' : 'down') : 'up',
      color: colorFor(c),
    };
  }

  // ---------- rendering ----------
  function renderAll() {
    renderTicker();
    renderMovers();
    renderTable();
    renderPatterns();
    renderSetups();
  }

  function applyFilters() {
    const { q, signal, cap, trend } = state.filters;
    let list = state.coins.filter((c) => {
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
      let av = a[key], bv = b[key];
      if (key === 'name' || key === 'signal' || key === 'pattern') {
        return String(av).localeCompare(String(bv)) * dir;
      }
      return ((av ?? 0) - (bv ?? 0)) * dir;
    });
    return list;
  }

  function badge(c) {
    return `<span class="badge badge--${c.signalCls}">${c.signal}</span>`;
  }

  function renderTable() {
    const body = $('#screener-body');
    const list = applyFilters();
    if (!list.length) {
      body.innerHTML = `<tr><td colspan="11" class="empty">No coins match your filters.</td></tr>`;
      return;
    }
    body.innerHTML = list.map((c) => `
      <tr>
        <td class="num muted">${c.rank}</td>
        <td>
          <div class="coin-cell">
            <span class="coin-ico" style="background:${c.color}"></span>
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

  // Inline SVG sparkline — no external chart lib needed.
  function sparkSVG(prices, up) {
    if (!prices || prices.length < 2) return '';
    const w = 110, h = 30, n = prices.length;
    const min = Math.min(...prices), max = Math.max(...prices);
    const span = max - min || 1;
    const pts = prices.map((p, i) => {
      const x = (i / (n - 1)) * w;
      const y = h - ((p - min) / span) * (h - 4) - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
    const col = up ? '#16c784' : '#ea3943';
    return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
      <polyline fill="none" stroke="${col}" stroke-width="1.5" points="${pts}" />
    </svg>`;
  }

  function renderTicker() {
    const items = state.coins.slice(0, 16);
    const html = items.map((c) => `
      <span class="ticker__item">
        <span class="sym">${c.symbol}</span>
        <span>${fmtPrice(c.price)}</span>
        ${pct(c.ch24h)}
      </span>`).join('');
    $('#ticker-track').innerHTML = html + html; // duplicate for seamless loop
  }

  function renderMovers() {
    const top = [...state.coins].sort((a, b) => b.ch24h - a.ch24h).slice(0, 6);
    $('#hero-movers').innerHTML = top.map((c) => `
      <li>
        <span class="coin-ico" style="background:${c.color}"></span>
        <span class="coin-name"><b>${c.name}</b><small>${c.symbol}</small></span>
        <span>${fmtPrice(c.price)}</span>
        <span>${pct(c.ch24h)}</span>
      </li>`).join('');
  }

  const TIMEFRAMES = ['15m', '1h', '4h', '1d'];
  function renderPatterns() {
    // Show the most "interesting" coins — biggest absolute 7d moves.
    const picks = [...state.coins]
      .sort((a, b) => Math.abs(b.ch7d) - Math.abs(a.ch7d))
      .slice(0, 6);
    $('#patterns-grid').innerHTML = picks.map((c, i) => {
      const bullish = c.ch7d >= 0;
      const target = c.price * (1 + (bullish ? 1 : -1) * (0.04 + Math.abs(c.ch7d) / 400));
      return `
      <div class="pcard">
        <div class="pcard__top">
          <span class="pcard__coin"><span class="coin-ico" style="background:${c.color}"></span>${c.name}</span>
          <span class="pcard__tf">${TIMEFRAMES[i % TIMEFRAMES.length]}</span>
        </div>
        <h4>${c.pattern}</h4>
        <div class="pattern-tag">${bullish ? 'Bullish' : 'Bearish'} · ${badge(c)}</div>
        <div class="pcard__meta">
          <div><span>Current</span><b>${fmtPrice(c.price)}</b></div>
          <div><span>Target</span><b class="${bullish ? 'pos' : 'neg'}">${fmtPrice(target)}</b></div>
          <div><span>RSI</span><b>${c.rsi.toFixed(0)}</b></div>
        </div>
      </div>`;
    }).join('');
  }

  function renderSetups() {
    const picks = [...state.coins]
      .filter((c) => c.signal === 'Strong Buy' || c.signal === 'Buy')
      .sort((a, b) => b.score - a.score)
      .slice(0, 3);
    const fill = picks.length ? picks : [...state.coins].sort((a, b) => b.score - a.score).slice(0, 3);
    $('#signals-grid').innerHTML = fill.map((c) => {
      const long = c.score >= 0;
      const entry = c.price;
      const stop = entry * (long ? 0.94 : 1.06);
      const t1 = entry * (long ? 1.08 : 0.92);
      const t2 = entry * (long ? 1.16 : 0.84);
      const rr = Math.abs((t1 - entry) / (entry - stop)).toFixed(1);
      return `
      <div class="setup">
        <div class="setup__head">
          <span class="coin-ico" style="background:${c.color}"></span>
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

  function setStatus(text, cls) {
    const el = $('#data-status');
    el.textContent = text;
    el.className = 'screener__status ' + (cls || '');
  }

  // ---------- AI Copilot (rule-based intent parser) ----------
  function copilotAnswer(text) {
    const t = text.toLowerCase();
    const f = { q: '', signal: '', cap: 0, trend: '' };
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

    // numeric thresholds
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

    // Push the parsed filters into the live screener too.
    state.filters.signal = f.signal;
    state.filters.cap = f.cap;
    state.filters.trend = f.trend;
    $('#signal-filter').value = f.signal;
    $('#cap-filter').value = String(f.cap);
    $('#trend-filter').value = f.trend;
    renderTable();

    const summary = notes.length ? notes.join(' · ') : 'no specific filters detected — showing top ranked';
    let html = `Applied filters: <b>${summary}</b>.`;
    if (!top.length) {
      html += `<br>No coins matched — try loosening the criteria.`;
    } else {
      html += `<table><tbody>` + top.map((c) =>
        `<tr><td><b>${c.symbol}</b></td><td>${fmtPrice(c.price)}</td><td>${pct(c.ch24h)}</td><td>${c.signal}</td></tr>`
      ).join('') + `</tbody></table>`;
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

  // ---------- events ----------
  function bind() {
    $('#search').addEventListener('input', (e) => { state.filters.q = e.target.value; renderTable(); });
    $('#signal-filter').addEventListener('change', (e) => { state.filters.signal = e.target.value; renderTable(); });
    $('#cap-filter').addEventListener('change', (e) => { state.filters.cap = +e.target.value; renderTable(); });
    $('#trend-filter').addEventListener('change', (e) => { state.filters.trend = e.target.value; renderTable(); });
    $('#refresh').addEventListener('click', load);

    $$('#screener-table thead th[data-sort]').forEach((th) => {
      th.addEventListener('click', () => {
        const key = th.dataset.sort;
        if (state.sort.key === key) state.sort.dir *= -1;
        else state.sort = { key, dir: key === 'name' ? 1 : -1 };
        renderTable();
      });
    });

    $('#copilot-form').addEventListener('submit', (e) => {
      e.preventDefault();
      const input = $('#copilot-input');
      const q = input.value.trim();
      if (!q) return;
      pushBubble(q, 'user');
      input.value = '';
      setTimeout(() => pushBubble(copilotAnswer(q), 'bot'), 350);
    });

    $$('.chip').forEach((chip) => chip.addEventListener('click', () => {
      const q = chip.dataset.q;
      $('#copilot-input').value = q;
      $('#copilot-form').dispatchEvent(new Event('submit'));
      document.getElementById('copilot').scrollIntoView({ behavior: 'smooth' });
    }));
  }

  // ---------- init ----------
  bind();
  load();
})();
