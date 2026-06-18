/* ===== social.js — crypto social trends monitor ===== */
(function () {
  const $ = (s) => document.querySelector(s);
  const CGP = '/.netlify/functions/cg?endpoint=';
  const CGD = 'https://api.coingecko.com/api/v3/';
  const REDDIT = '/.netlify/functions/reddit';

  const esc = (v) => v == null ? '' : String(v).replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]));
  const num = (n) => n == null ? '—' : Math.abs(n) >= 1000 ? (n / 1000).toFixed(1) + 'k' : String(n);
  const pct = (n) => n == null ? '' : `<span class="${n >= 0 ? 'pos' : 'neg'}">${n >= 0 ? '+' : ''}${n.toFixed(1)}%</span>`;
  function ago(sec) {
    const s = Math.max(0, Date.now() / 1000 - sec);
    if (s < 3600) return `${Math.floor(s / 60)}m`;
    if (s < 86400) return `${Math.floor(s / 3600)}h`;
    return `${Math.floor(s / 86400)}d`;
  }

  async function cgGet(ep) {
    for (const u of [CGP + encodeURIComponent(ep), CGD + ep]) {
      try { const r = await fetch(u); if (r.ok) return await r.json(); } catch { /* next */ }
    }
    return null;
  }

  // ---- Fallback data (used if APIs are unreachable) ----
  const FB_TRENDING = {
    coins: [
      { item: { id: 'solana', name: 'Solana', symbol: 'SOL', market_cap_rank: 5, thumb: '', data: { price_change_percentage_24h: { usd: 5.2 } } } },
      { item: { id: 'pepe', name: 'Pepe', symbol: 'PEPE', market_cap_rank: 24, thumb: '', data: { price_change_percentage_24h: { usd: 12.5 } } } },
      { item: { id: 'dogecoin', name: 'Dogecoin', symbol: 'DOGE', market_cap_rank: 8, thumb: '', data: { price_change_percentage_24h: { usd: 8.9 } } } },
      { item: { id: 'chainlink', name: 'Chainlink', symbol: 'LINK', market_cap_rank: 12, thumb: '', data: { price_change_percentage_24h: { usd: 4.4 } } } },
      { item: { id: 'injective-protocol', name: 'Injective', symbol: 'INJ', market_cap_rank: 28, thumb: '', data: { price_change_percentage_24h: { usd: 7.3 } } } },
      { item: { id: 'near', name: 'NEAR Protocol', symbol: 'NEAR', market_cap_rank: 18, thumb: '', data: { price_change_percentage_24h: { usd: 3.9 } } } },
      { item: { id: 'render-token', name: 'Render', symbol: 'RNDR', market_cap_rank: 30, thumb: '', data: { price_change_percentage_24h: { usd: 6.1 } } } },
    ],
    categories: [
      { name: 'AI Agents', market_cap_1h_change: 2.4 }, { name: 'Memecoins', market_cap_1h_change: 1.8 },
      { name: 'Solana Ecosystem', market_cap_1h_change: 1.2 }, { name: 'DePIN', market_cap_1h_change: 0.9 },
      { name: 'Real World Assets', market_cap_1h_change: 0.6 }, { name: 'Layer 1', market_cap_1h_change: 0.4 },
    ],
  };
  const FB_POSTS = [
    { id: 'a', title: 'Daily Crypto Discussion - what are you watching today?', sub: 'CryptoCurrency', ups: 1840, comments: 920, created: Date.now() / 1000 - 5400, permalink: 'https://www.reddit.com/r/CryptoCurrency', flair: 'GENERAL-NEWS', author: 'automod' },
    { id: 'b', title: 'Bitcoin holds key support as ETF inflows continue', sub: 'CryptoCurrency', ups: 1220, comments: 410, created: Date.now() / 1000 - 9000, permalink: 'https://www.reddit.com/r/CryptoCurrency', flair: 'ANALYSIS', author: 'satoshifan' },
    { id: 'c', title: 'Solana network activity hits new highs — here is why', sub: 'CryptoCurrency', ups: 980, comments: 305, created: Date.now() / 1000 - 14400, permalink: 'https://www.reddit.com/r/CryptoCurrency', flair: 'TECHNOLOGY', author: 'soldev' },
  ];

  function status(live) {
    const el = $('#soc-status'); if (!el) return;
    el.textContent = live ? '● Live' : '● Sample data';
    el.className = 'screener__status ' + (live ? 'live' : 'fallback');
  }

  // ---- Trending searches + narratives ----
  async function renderTrending() {
    const list = $('#soc-trending'), cats = $('#soc-cats');
    const data = await cgGet('search/trending');
    const live = !!data;
    const d = data || FB_TRENDING;
    const coins = (d.coins || []).slice(0, 10);
    if (list) list.innerHTML = coins.map((c, i) => {
      const it = c.item || c;
      const ch = it.data && it.data.price_change_percentage_24h && it.data.price_change_percentage_24h.usd;
      const heat = Math.max(6, 100 - i * 9);
      return `<li class="soc-trend__row">
        <span class="soc-rank">${i + 1}</span>
        ${it.thumb ? `<img class="coin-ico" src="${esc(it.thumb)}" alt="" loading="lazy"/>` : '<span class="coin-ico"></span>'}
        <span class="soc-trend__name"><b>${esc(it.name)}</b> <small class="muted">${esc((it.symbol || '').toUpperCase())}</small></span>
        <span class="soc-heat"><span style="width:${heat}%"></span></span>
        ${ch != null ? pct(ch) : `<span class="muted">#${esc(it.market_cap_rank || '—')}</span>`}
      </li>`;
    }).join('') || '<li class="muted">No trending data.</li>';

    const categories = (d.categories || []).slice(0, 8);
    if (cats) cats.innerHTML = categories.map((c) => {
      const ch = c.market_cap_1h_change;
      return `<span class="soc-cat">${esc(c.name)} ${ch != null ? pct(ch) : ''}</span>`;
    }).join('') || '<span class="muted">No narratives.</span>';
    return live;
  }

  // ---- Reddit community feed ----
  function postCard(p) {
    const src = p.source === 'hn' ? 'Hacker News' : `r/${esc(p.sub)}`;
    return `<a class="soc-post" href="${esc(p.permalink)}" target="_blank" rel="noopener">
      <div class="soc-post__main">
        ${p.flair ? `<span class="soc-flair">${esc(p.flair)}</span>` : ''}
        <span class="soc-post__title">${esc(p.title)}</span>
      </div>
      <div class="soc-post__meta muted">
        <span>${src}</span><span>▲ ${num(p.ups)}</span><span>💬 ${num(p.comments)}</span><span>${ago(p.created)} ago</span>
      </div>
    </a>`;
  }
  async function renderFeed() {
    const host = $('#soc-feed'); if (!host) return false;
    host.innerHTML = '<div class="loading">Loading discussion…</div>';
    const sub = ($('#soc-sub') || {}).value || 'CryptoCurrency';
    const sort = ($('#soc-sort') || {}).value || 'hot';
    let posts = null;
    try { const r = await fetch(`${REDDIT}?sub=${encodeURIComponent(sub)}&sort=${encodeURIComponent(sort)}&limit=16`); if (r.ok) { const j = await r.json(); posts = j.posts || []; } } catch { /* fallback */ }
    const live = Array.isArray(posts) && posts.length > 0;
    const rows = live ? posts : FB_POSTS;
    host.innerHTML = rows.map(postCard).join('');
    return live;
  }

  async function init() {
    const [t, f] = await Promise.all([renderTrending(), renderFeed()]);
    status(t || f);
    const sub = $('#soc-sub'), sort = $('#soc-sort');
    const reload = async () => { const l = await renderFeed(); status(l || t); };
    if (sub) sub.addEventListener('change', reload);
    if (sort) sort.addEventListener('change', reload);
  }
  init();
})();
