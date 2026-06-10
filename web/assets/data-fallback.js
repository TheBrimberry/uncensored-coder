/* ===== data-fallback.js =====
 * Offline snapshot used when the live CoinGecko API is unreachable.
 * Sparklines are generated from a seeded walk so signals/patterns still render.
 */
const FALLBACK_DATA = (() => {
  // Seeded PRNG so the demo looks the same on every load.
  function rng(seed) {
    let s = seed % 2147483647;
    if (s <= 0) s += 2147483646;
    return () => (s = (s * 16807) % 2147483647) / 2147483647;
  }
  // Build a 7d (~168 point) sparkline trending toward ch7d% with volatility.
  function spark(seed, start, ch7d, vol) {
    const rand = rng(seed);
    const end = start * (1 + ch7d / 100);
    const out = [];
    const N = 168;
    for (let i = 0; i < N; i++) {
      const t = i / (N - 1);
      const base = start + (end - start) * t;
      const noise = (rand() - 0.5) * 2 * vol * start;
      out.push(Math.max(base + noise, start * 0.01));
    }
    return out;
  }

  const seed = [
    // [id, name, symbol, price, rank, ch1h, ch24h, ch7d, mcap, vol, image]
    ['bitcoin', 'Bitcoin', 'btc', 67250, 1, 0.2, 1.8, 6.4, 1320000000000, 28000000000, '#f7931a'],
    ['ethereum', 'Ethereum', 'eth', 3520, 2, 0.4, 2.6, 9.1, 423000000000, 15000000000, '#627eea'],
    ['tether', 'Tether', 'usdt', 1.0, 3, 0.0, 0.0, 0.1, 112000000000, 45000000000, '#26a17b'],
    ['solana', 'Solana', 'sol', 168, 4, 0.9, 5.2, 14.3, 76000000000, 4200000000, '#14f195'],
    ['bnb', 'BNB', 'bnb', 605, 5, 0.1, 1.1, 3.2, 89000000000, 1800000000, '#f0b90b'],
    ['xrp', 'XRP', 'xrp', 0.62, 6, -0.3, -1.4, -4.8, 34000000000, 1500000000, '#23292f'],
    ['cardano', 'Cardano', 'ada', 0.58, 7, 0.2, 3.1, 7.7, 20000000000, 600000000, '#0033ad'],
    ['dogecoin', 'Dogecoin', 'doge', 0.16, 8, 1.4, 8.9, 22.1, 23000000000, 2100000000, '#c2a633'],
    ['avalanche-2', 'Avalanche', 'avax', 38.5, 9, -0.6, -2.2, -9.4, 14000000000, 480000000, '#e84142'],
    ['chainlink', 'Chainlink', 'link', 18.2, 10, 0.7, 4.4, 11.8, 11000000000, 520000000, '#2a5ada'],
    ['polkadot', 'Polkadot', 'dot', 7.4, 11, -0.2, -0.8, -2.1, 9500000000, 240000000, '#e6007a'],
    ['polygon', 'Polygon', 'matic', 0.72, 12, 0.5, 2.0, 5.5, 7100000000, 410000000, '#8247e5'],
    ['litecoin', 'Litecoin', 'ltc', 84, 13, 0.1, 1.3, 0.9, 6300000000, 380000000, '#bfbbbb'],
    ['shiba-inu', 'Shiba Inu', 'shib', 0.0000245, 14, 2.1, 12.5, 31.2, 14500000000, 980000000, '#e63329'],
    ['uniswap', 'Uniswap', 'uni', 9.8, 15, -0.4, -1.1, -6.7, 5900000000, 190000000, '#ff007a'],
    ['aave', 'Aave', 'aave', 138, 16, 0.8, 5.8, 18.4, 2050000000, 220000000, '#b6509e'],
    ['near', 'NEAR Protocol', 'near', 6.2, 17, 0.3, 3.9, 13.1, 6700000000, 310000000, '#00ec97'],
    ['arbitrum', 'Arbitrum', 'arb', 1.05, 18, -0.5, -3.3, -11.2, 3200000000, 270000000, '#28a0f0'],
    ['optimism', 'Optimism', 'op', 2.35, 19, 0.6, 4.1, 9.9, 2600000000, 180000000, '#ff0420'],
    ['injective-protocol', 'Injective', 'inj', 27.4, 20, 1.2, 7.3, 25.6, 2700000000, 240000000, '#00d2ff'],
  ];

  return seed.map(([id, name, symbol, price, rank, ch1h, ch24h, ch7d, mcap, vol, color], i) => ({
    id, name, symbol, current_price: price, market_cap_rank: rank,
    price_change_percentage_1h_in_currency: ch1h,
    price_change_percentage_24h_in_currency: ch24h,
    price_change_percentage_7d_in_currency: ch7d,
    market_cap: mcap, total_volume: vol, color,
    sparkline_in_7d: { price: spark(i * 97 + 13, price, ch7d, Math.abs(ch7d) / 600 + 0.01) },
  }));
})();
