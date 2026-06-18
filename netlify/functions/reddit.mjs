// Keyless social-feed proxy. Tries Reddit first (public JSON); since Reddit now
// commonly blocks datacenter IPs (403), it falls back to the Hacker News
// (Algolia) search API — keyless and server-friendly — so the feed stays live.

const cors = {
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET, OPTIONS',
};
const json = (statusCode, body) => ({
  statusCode,
  headers: { ...cors, 'content-type': 'application/json', 'cache-control': 'public, max-age=120, stale-while-revalidate=300' },
  body: JSON.stringify(body),
});

const SUBS = new Set(['CryptoCurrency', 'CryptoMarkets', 'Bitcoin', 'ethereum', 'altcoin', 'defi', 'solana', 'CryptoMoonShots']);
const SORTS = new Set(['hot', 'top', 'new', 'rising']);
const HN_QUERY = {
  CryptoCurrency: 'cryptocurrency', CryptoMarkets: 'crypto', Bitcoin: 'bitcoin',
  ethereum: 'ethereum', altcoin: 'altcoin', defi: 'defi', solana: 'solana', CryptoMoonShots: 'crypto',
};

async function fromReddit(sub, sort, limit) {
  const t = sort === 'top' ? '&t=day' : '';
  const r = await fetch(`https://www.reddit.com/r/${sub}/${sort}.json?limit=${limit}${t}&raw_json=1`, {
    headers: { 'user-agent': 'coinscope-social/1.0 (+https://coinscope-analytics.netlify.app)' },
  });
  if (!r.ok) throw new Error(`reddit ${r.status}`);
  const j = await r.json();
  const posts = ((j.data && j.data.children) || [])
    .filter((c) => c && c.data && !c.data.stickied)
    .map((c) => ({
      id: c.data.id, source: 'reddit', sub: c.data.subreddit, title: c.data.title,
      ups: c.data.ups, comments: c.data.num_comments, created: c.data.created_utc,
      permalink: 'https://www.reddit.com' + c.data.permalink, flair: c.data.link_flair_text || '', author: c.data.author,
    }));
  if (!posts.length) throw new Error('reddit empty');
  return posts;
}

async function fromHN(sub, sort, limit) {
  const q = HN_QUERY[sub] || 'cryptocurrency';
  const path = (sort === 'new' || sort === 'rising') ? 'search_by_date' : 'search';
  const r = await fetch(`https://hn.algolia.com/api/v1/${path}?query=${encodeURIComponent(q)}&tags=story&hitsPerPage=${limit}`);
  if (!r.ok) throw new Error(`hn ${r.status}`);
  const j = await r.json();
  return (j.hits || [])
    .filter((h) => h.title)
    .map((h) => ({
      id: h.objectID, source: 'hn', sub: 'Hacker News', title: h.title,
      ups: h.points || 0, comments: h.num_comments || 0, created: h.created_at_i,
      permalink: h.url || `https://news.ycombinator.com/item?id=${h.objectID}`,
      flair: q, author: h.author || '',
    }));
}

export const handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: cors, body: '' };
  const p = event.queryStringParameters || {};
  const sub = SUBS.has(p.sub) ? p.sub : 'CryptoCurrency';
  const sort = SORTS.has(p.sort) ? p.sort : 'hot';
  const limit = Math.min(25, Math.max(1, parseInt(p.limit || '16', 10)));

  try { return json(200, { source: 'reddit', sub, sort, posts: await fromReddit(sub, sort, limit) }); }
  catch { /* fall through to Hacker News */ }
  try { return json(200, { source: 'hn', sub, sort, posts: await fromHN(sub, sort, limit) }); }
  catch (e) { return json(502, { error: String(e), posts: [] }); }
};
