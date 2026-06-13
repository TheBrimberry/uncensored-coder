/* ===== layout.js — shared chrome injected on every page ===== */
(function () {
  const page = (document.body.dataset.page || 'index');
  const NAV = [
    ['index.html', 'Home'],
    ['pulse.html', 'Pulse'],
    ['screener.html', 'Screener'],
    ['arbitrage.html', 'Arbitrage'],
    ['predictions.html', 'Predictions'],
    ['converter.html', 'Converter'],
    ['compare.html', 'Compare'],
    ['smart.html', 'Smart Picks'],
    ['picks.html', 'Top Picks'],
    ['discover.html', 'Discover'],
    ['news.html', 'News'],
    ['portfolio.html', 'Portfolio'],
    ['learn.html', 'Learn'],
  ];
  const isActive = (href) => href.split('.')[0] === page ? 'active' : '';

  const header = `
  <header class="nav" id="top">
    <div class="container nav__inner">
      <a class="brand" href="index.html"><span class="brand__mark">◈</span><span class="brand__name">CoinScope</span></a>
      <nav class="nav__links" id="nav-links">
        ${NAV.map(([h, l]) => `<a class="${isActive(h)}" href="${h}">${l}</a>`).join('')}
      </nav>
      <div class="nav__actions">
        <a class="btn btn--ghost" href="pricing.html">Pricing</a>
        <a class="btn btn--primary" href="screener.html">Launch app</a>
        <button class="nav__burger" id="nav-burger" aria-label="Menu">☰</button>
      </div>
    </div>
  </header>
  <div class="ticker" id="ticker" aria-label="Live market ticker"><div class="ticker__track" id="ticker-track"></div></div>
  <div class="globalbar"><div class="container globalbar__inner">
    <span class="globalbar__item"><span class="muted">Market Cap</span> <b id="g-mcap">—</b> <span id="g-mcap-ch"></span></span>
    <span class="globalbar__item"><span class="muted">24h Vol</span> <b id="g-vol">—</b></span>
    <span class="globalbar__item"><span class="muted">BTC Dom</span> <b id="g-btc">—</b></span>
    <span class="globalbar__item"><span class="muted">ETH Dom</span> <b id="g-eth">—</b></span>
    <span class="globalbar__item"><span class="muted">Coins</span> <b id="g-coins">—</b></span>
  </div></div>`;

  const footer = `
  <footer class="footer">
    <div class="container footer__inner">
      <div>
        <a class="brand" href="index.html"><span class="brand__mark">◈</span><span class="brand__name">CoinScope</span></a>
        <p class="muted">Scan. Analyze. Predict. Trade.</p>
      </div>
      <div class="footer__cols">
        <div><h4>Markets</h4><a href="pulse.html">Market Pulse</a><a href="screener.html">Screener</a><a href="arbitrage.html">Arbitrage</a><a href="converter.html">Converter</a></div>
        <div><h4>Insights</h4><a href="predictions.html">Predictions</a><a href="smart.html">Smart Picks</a><a href="picks.html">Top Picks</a><a href="discover.html">Discover</a></div>
        <div><h4>More</h4><a href="news.html">News</a><a href="portfolio.html">Portfolio</a><a href="learn.html">Learn</a><a href="pricing.html">Pricing</a></div>
      </div>
    </div>
    <div class="container footer__note muted">
      Demo project for educational purposes — not affiliated with altFINS, CoinArbitrageBot or CoinCodex.
      Market data via CoinGecko; predictions are model-based and not financial advice.
    </div>
  </footer>`;

  const chrome = document.getElementById('app-chrome');
  if (chrome) chrome.innerHTML = header;
  const foot = document.getElementById('app-foot');
  if (foot) foot.innerHTML = footer;

  // Drawer + toast host (used by app.js on every page)
  const extra = document.createElement('div');
  extra.innerHTML = `
    <div class="drawer" id="drawer" hidden>
      <div class="drawer__overlay" id="drawer-overlay"></div>
      <aside class="drawer__panel" role="dialog" aria-modal="true" aria-labelledby="drawer-name">
        <button class="drawer__close" id="drawer-close" aria-label="Close">✕</button>
        <div id="drawer-content"><div class="loading">Loading…</div></div>
      </aside>
    </div>
    <div class="toasts" id="toasts" aria-live="polite"></div>`;
  document.body.appendChild(extra);

  const burger = document.getElementById('nav-burger');
  if (burger) burger.addEventListener('click', () => document.getElementById('nav-links').classList.toggle('open'));
})();
