/* ===== markets.js — forex / metals / commodities / indexes ===== */
(function () {
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));
  const FN = '/.netlify/functions/markets';

  // Symbol catalogue: [yahooSymbol, label, sublabel, decimals, fallbackPrice]
  const GROUPS = {
    forex: [
      ['EURUSD=X', 'EUR/USD', 'Euro', 4, 1.0850], ['GBPUSD=X', 'GBP/USD', 'Pound', 4, 1.2720],
      ['USDJPY=X', 'USD/JPY', 'Yen', 2, 156.40], ['USDCHF=X', 'USD/CHF', 'Franc', 4, 0.8920],
      ['AUDUSD=X', 'AUD/USD', 'Aussie', 4, 0.6650], ['USDCAD=X', 'USD/CAD', 'Loonie', 4, 1.3680],
      ['NZDUSD=X', 'NZD/USD', 'Kiwi', 4, 0.6120], ['EURGBP=X', 'EUR/GBP', 'Euro/Pound', 4, 0.8530],
      ['USDCNY=X', 'USD/CNY', 'Yuan', 4, 7.2500], ['USDMXN=X', 'USD/MXN', 'Peso', 4, 18.450],
      ['DX-Y.NYB', 'DXY', 'Dollar Index', 2, 104.80],
    ],
    metals: [
      ['GC=F', 'Gold', 'per oz', 2, 2380.0], ['SI=F', 'Silver', 'per oz', 2, 30.20],
      ['PL=F', 'Platinum', 'per oz', 2, 1010.0], ['PA=F', 'Palladium', 'per oz', 2, 970.0],
      ['HG=F', 'Copper', 'per lb', 4, 4.55],
    ],
    commodities: [
      ['CL=F', 'WTI Crude', 'per bbl', 2, 78.50], ['BZ=F', 'Brent Crude', 'per bbl', 2, 82.60],
      ['NG=F', 'Natural Gas', 'per MMBtu', 3, 2.85], ['RB=F', 'Gasoline', 'per gal', 4, 2.45],
      ['ZC=F', 'Corn', 'per bu', 2, 445.0], ['ZW=F', 'Wheat', 'per bu', 2, 600.0],
      ['ZS=F', 'Soybeans', 'per bu', 2, 1180.0], ['KC=F', 'Coffee', 'per lb', 2, 225.0],
      ['SB=F', 'Sugar', 'per lb', 2, 19.50], ['CT=F', 'Cotton', 'per lb', 2, 72.00],
    ],
    indexes: [
      ['^GSPC', 'S&P 500', 'US', 2, 5430.0], ['^DJI', 'Dow Jones', 'US', 2, 38800.0],
      ['^IXIC', 'Nasdaq', 'US', 2, 17600.0], ['^RUT', 'Russell 2000', 'US', 2, 2030.0],
      ['^VIX', 'VIX', 'Volatility', 2, 13.20], ['^FTSE', 'FTSE 100', 'UK', 2, 8240.0],
      ['^GDAXI', 'DAX', 'Germany', 2, 18300.0], ['^FCHI', 'CAC 40', 'France', 2, 7650.0],
      ['^N225', 'Nikkei 225', 'Japan', 2, 38500.0], ['^HSI', 'Hang Seng', 'Hong Kong', 2, 18100.0],
      ['^STOXX50E', 'Euro Stoxx 50', 'Europe', 2, 4950.0],
    ],
  };

  let current = 'forex';
  let quotes = {}; // symbol -> {price, changePct}
  let live = false;

  const fmt = (v, d) => v == null ? '—' : Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });

  function status() {
    const el = $('#mkt-status'); if (!el) return;
    el.textContent = live ? '● Live (delayed)' : '● Sample data';
    el.className = 'screener__status ' + (live ? 'live' : 'fallback');
  }

  function render() {
    const host = $('#mkt-cards'); if (!host) return;
    const rows = GROUPS[current];
    host.innerHTML = rows.map(([sym, label, sub, dec, fb]) => {
      const q = quotes[sym] || {};
      const price = q.price != null ? q.price : fb;
      const ch = q.changePct;
      const up = ch == null ? null : ch >= 0;
      return `<div class="mkt-card ${up == null ? '' : up ? 'is-up' : 'is-down'}">
        <div class="mkt-card__top">
          <span class="mkt-card__label">${label}</span>
          <span class="mkt-card__sub muted">${sub}</span>
        </div>
        <div class="mkt-card__price">${fmt(price, dec)}</div>
        <div class="mkt-card__chg ${ch == null ? 'muted' : up ? 'pos' : 'neg'}">
          ${ch == null ? '—' : `${up ? '▲' : '▼'} ${ch >= 0 ? '+' : ''}${ch.toFixed(2)}%`}
        </div>
      </div>`;
    }).join('');
    status();
  }

  async function load() {
    const all = Object.values(GROUPS).flat().map((r) => r[0]);
    try {
      const r = await fetch(`${FN}?symbols=${encodeURIComponent(all.join(','))}`);
      if (r.ok) {
        const j = await r.json();
        (j.quotes || []).forEach((q) => { quotes[q.symbol] = q; });
        live = (j.quotes || []).length > 0;
      }
    } catch { /* fallback prices stay */ }
    render();
  }

  $$('#mkt-tabs .tf').forEach((t) => t.addEventListener('click', () => {
    current = t.dataset.group;
    $$('#mkt-tabs .tf').forEach((x) => x.classList.toggle('active', x === t));
    render();
  }));

  render();          // instant paint with fallback values
  load();            // then hydrate with live quotes
  setInterval(load, 60000); // refresh each minute
})();
