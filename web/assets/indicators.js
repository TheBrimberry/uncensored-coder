/* ===== indicators.js — lightweight technical analysis ===== */
/* All functions operate on an array of closing prices (oldest → newest). */

const TA = (() => {

  function sma(prices, period) {
    if (prices.length < period) return null;
    let sum = 0;
    for (let i = prices.length - period; i < prices.length; i++) sum += prices[i];
    return sum / period;
  }

  function ema(prices, period) {
    if (prices.length < period) return null;
    const k = 2 / (period + 1);
    let e = prices.slice(0, period).reduce((a, b) => a + b, 0) / period;
    for (let i = period; i < prices.length; i++) e = prices[i] * k + e * (1 - k);
    return e;
  }

  // Classic Wilder RSI over `period` (default 14).
  function rsi(prices, period = 14) {
    if (prices.length < period + 1) return null;
    let gain = 0, loss = 0;
    for (let i = 1; i <= period; i++) {
      const d = prices[i] - prices[i - 1];
      if (d >= 0) gain += d; else loss -= d;
    }
    let avgGain = gain / period, avgLoss = loss / period;
    for (let i = period + 1; i < prices.length; i++) {
      const d = prices[i] - prices[i - 1];
      avgGain = (avgGain * (period - 1) + Math.max(d, 0)) / period;
      avgLoss = (avgLoss * (period - 1) + Math.max(-d, 0)) / period;
    }
    if (avgLoss === 0) return 100;
    const rs = avgGain / avgLoss;
    return 100 - 100 / (1 + rs);
  }

  // Composite momentum signal from price action + RSI + trend.
  // Returns { label, cls, score }.
  function signal({ prices, ch24h = 0, ch7d = 0 }) {
    const r = rsi(prices) ?? 50;
    const fast = sma(prices, Math.min(10, prices.length));
    const slow = sma(prices, Math.min(30, prices.length));
    const last = prices[prices.length - 1];

    let score = 0;
    // Trend: fast vs slow MA
    if (fast && slow) score += fast > slow ? 1 : -1;
    // Price vs slow MA
    if (slow) score += last > slow ? 1 : -1;
    // Momentum windows
    score += ch24h > 3 ? 1 : ch24h < -3 ? -1 : 0;
    score += ch7d > 8 ? 1 : ch7d < -8 ? -1 : 0;
    // RSI extremes (mean-reversion / strength)
    if (r >= 70) score += 1; else if (r <= 30) score -= 1;
    else if (r > 55) score += 0.5; else if (r < 45) score -= 0.5;

    let label, cls;
    if (score >= 3) { label = 'Strong Buy'; cls = 'sb'; }
    else if (score >= 1) { label = 'Buy'; cls = 'b'; }
    else if (score > -1) { label = 'Neutral'; cls = 'n'; }
    else if (score > -3) { label = 'Sell'; cls = 's'; }
    else { label = 'Strong Sell'; cls = 'ss'; }
    return { label, cls, score, rsi: r };
  }

  // Heuristic chart-pattern label from recent price geometry.
  function detectPattern({ prices, ch7d = 0 }) {
    if (!prices || prices.length < 12) return 'Range';
    const n = prices.length;
    const recent = prices.slice(-Math.min(24, n));
    const min = Math.min(...recent), max = Math.max(...recent);
    const first = recent[0], last = recent[recent.length - 1];
    const mid = recent[Math.floor(recent.length / 2)];
    const range = (max - min) / (min || 1);

    const up = last > first;
    const dipMiddle = mid < first && mid < last;
    const peakMiddle = mid > first && mid > last;

    if (range < 0.04) return 'Tight Consolidation';
    if (up && dipMiddle) return 'Bull Flag';
    if (!up && peakMiddle) return 'Bear Flag';
    if (up && last >= max * 0.995) return 'Ascending Triangle';
    if (!up && last <= min * 1.005) return 'Descending Triangle';
    if (dipMiddle && last > first) return 'Double Bottom';
    if (peakMiddle && last < first) return 'Double Top';
    if (ch7d > 12) return 'Breakout';
    if (ch7d < -12) return 'Breakdown';
    if (up) return 'Rising Channel';
    return 'Falling Channel';
  }

  return { sma, ema, rsi, signal, detectPattern };
})();
