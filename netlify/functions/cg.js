// Netlify Function: CoinGecko proxy.
// Adds a server-side API key (if COINGECKO_API_KEY is set) and a short cache,
// so the browser isn't rate-limited and the key never ships to the client.
// Falls back to the keyless public API when no key is configured.

const ALLOW = [
  /^coins\/markets(\?|$)/,
  /^global(\?|$)/,
  /^search\/trending(\?|$)/,
  /^coins\/[a-z0-9._-]+\/market_chart(\?|$)/,
  /^coins\/[a-z0-9._-]+\/ohlc(\?|$)/,
  /^coins\/[a-z0-9._-]+\/tickers(\?|$)/,
];

const cors = {
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET, OPTIONS',
};

exports.handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: cors, body: '' };

  const endpoint = (event.queryStringParameters && event.queryStringParameters.endpoint) || '';
  if (!ALLOW.some((re) => re.test(endpoint))) {
    return { statusCode: 400, headers: { ...cors, 'content-type': 'application/json' }, body: JSON.stringify({ error: 'endpoint not allowed' }) };
  }

  const key = process.env.COINGECKO_API_KEY;
  const isPro = process.env.COINGECKO_API_TIER === 'pro';
  const base = isPro ? 'https://pro-api.coingecko.com/api/v3/' : 'https://api.coingecko.com/api/v3/';
  const headers = { accept: 'application/json' };
  if (key) headers[isPro ? 'x-cg-pro-api-key' : 'x-cg-demo-api-key'] = key;

  try {
    const r = await fetch(base + endpoint, { headers });
    const body = await r.text();
    return {
      statusCode: r.status,
      headers: { ...cors, 'content-type': 'application/json', 'cache-control': 'public, max-age=30, stale-while-revalidate=120' },
      body,
    };
  } catch (e) {
    return { statusCode: 502, headers: { ...cors, 'content-type': 'application/json' }, body: JSON.stringify({ error: String(e) }) };
  }
};
