// CoinGecko webhook receiver + feed reader (cg.coin.info.updated).
//
//   POST  -> CoinGecko delivers a coin-info change event; we validate it,
//            timestamp it, and append it to a capped feed in Netlify Blobs.
//   GET   -> returns the stored feed (newest first) for the Updates page.
//
// Security: if CG_WEBHOOK_SECRET is set, incoming POSTs must present it via the
// `x-webhook-secret` header or a `?token=` query param, otherwise they're
// rejected. With no secret configured the endpoint accepts all POSTs (dev mode).

import { getStore } from '@netlify/blobs';

const KEY = 'feed';
const MAX = 200;
const cors = {
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET, POST, OPTIONS',
  'access-control-allow-headers': 'content-type, x-webhook-secret',
};
const json = (statusCode, body, extra = {}) => ({
  statusCode,
  headers: { ...cors, 'content-type': 'application/json', ...extra },
  body: JSON.stringify(body),
});

function store() {
  return getStore({ name: 'cg-events', consistency: 'strong' });
}
async function readFeed(s) {
  try { const v = await s.get(KEY, { type: 'json' }); return Array.isArray(v) ? v : []; }
  catch { return []; }
}

export const handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: cors, body: '' };

  let s;
  try { s = store(); } catch (e) { return json(500, { error: 'blob store unavailable', detail: String(e) }); }

  if (event.httpMethod === 'GET') {
    const feed = await readFeed(s);
    return json(200, { count: feed.length, events: feed }, { 'cache-control': 'no-store' });
  }

  if (event.httpMethod === 'POST') {
    const secret = process.env.CG_WEBHOOK_SECRET;
    if (secret) {
      const provided = (event.headers && (event.headers['x-webhook-secret'] || event.headers['X-Webhook-Secret']))
        || (event.queryStringParameters && event.queryStringParameters.token);
      if (provided !== secret) return json(401, { error: 'unauthorized' });
    }

    let body;
    try { body = JSON.parse(event.body || '{}'); } catch { return json(400, { error: 'invalid json' }); }
    if (body.event_type !== 'cg.coin.info.updated' || !body.data || !body.data.id) {
      return json(400, { error: 'unsupported event' });
    }

    const d = body.data;
    const record = {
      received_at: new Date().toISOString(),
      event_type: body.event_type,
      id: d.id,
      symbol: d.symbol || '',
      name: d.name || d.id,
      changes: Array.isArray(d.changes) ? d.changes : [],
    };

    const feed = await readFeed(s);
    feed.unshift(record);
    await s.setJSON(KEY, feed.slice(0, MAX));
    return json(200, { ok: true, stored: record.changes.length });
  }

  return json(405, { error: 'method not allowed' });
};
