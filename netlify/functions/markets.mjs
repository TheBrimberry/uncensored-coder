// Keyless markets proxy — quotes for forex, metals, commodities and indexes.
// Fetches Yahoo Finance chart data server-side for an allowlisted symbol set
// and returns normalized { symbol, price, prevClose, changePct, currency, time }.

const cors = {
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET, OPTIONS',
};
const json = (statusCode, body) => ({
  statusCode,
  headers: { ...cors, 'content-type': 'application/json', 'cache-control': 'public, max-age=60, stale-while-revalidate=180' },
  body: JSON.stringify(body),
});

// Allowlisted Yahoo symbols, grouped. Keys are kept in sync with the frontend.
const ALLOW = new Set([
  // Forex
  'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'USDCHF=X', 'AUDUSD=X', 'USDCAD=X', 'NZDUSD=X', 'EURGBP=X', 'USDCNY=X', 'USDMXN=X', 'DX-Y.NYB',
  // Metals
  'GC=F', 'SI=F', 'PL=F', 'PA=F', 'HG=F',
  // Commodities
  'CL=F', 'BZ=F', 'NG=F', 'RB=F', 'ZC=F', 'ZW=F', 'ZS=F', 'KC=F', 'SB=F', 'CT=F',
  // Indexes
  '^GSPC', '^DJI', '^IXIC', '^RUT', '^VIX', '^FTSE', '^GDAXI', '^FCHI', '^N225', '^HSI', '^STOXX50E',
]);

async function quote(symbol) {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=1d&interval=1d`;
  const r = await fetch(url, { headers: { 'user-agent': 'Mozilla/5.0 (compatible; coinscope/1.0)' } });
  if (!r.ok) throw new Error(`yahoo ${r.status}`);
  const j = await r.json();
  const res = j && j.chart && j.chart.result && j.chart.result[0];
  const m = res && res.meta;
  if (!m) throw new Error('no meta');
  const price = m.regularMarketPrice;
  const prev = m.chartPreviousClose != null ? m.chartPreviousClose : m.previousClose;
  const changePct = (price != null && prev) ? ((price - prev) / prev) * 100 : null;
  return { symbol, price, prevClose: prev, changePct, currency: m.currency || '', time: m.regularMarketTime || null };
}

export const handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: cors, body: '' };
  const raw = (event.queryStringParameters && event.queryStringParameters.symbols) || '';
  const symbols = raw.split(',').map((s) => s.trim()).filter((s) => ALLOW.has(s)).slice(0, 40);
  if (!symbols.length) return json(400, { error: 'no valid symbols' });
  const settled = await Promise.allSettled(symbols.map(quote));
  const quotes = settled.filter((s) => s.status === 'fulfilled').map((s) => s.value);
  return json(200, { count: quotes.length, quotes });
};
