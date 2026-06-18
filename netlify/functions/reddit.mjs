// Keyless Reddit proxy — fetches hot/top crypto posts server-side (avoids
// browser CORS) and returns a trimmed, normalized shape for the Social page.

const cors = {
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET, OPTIONS',
};
const json = (statusCode, body) => ({
  statusCode,
  headers: { ...cors, 'content-type': 'application/json', 'cache-control': 'public, max-age=120, stale-while-revalidate=300' },
  body: JSON.stringify(body),
});

const ALLOW = new Set(['CryptoCurrency', 'CryptoMarkets', 'Bitcoin', 'ethereum', 'altcoin', 'defi', 'solana', 'CryptoMoonShots']);
const SORTS = new Set(['hot', 'top', 'new', 'rising']);

export const handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: cors, body: '' };
  const p = event.queryStringParameters || {};
  const sub = ALLOW.has(p.sub) ? p.sub : 'CryptoCurrency';
  const sort = SORTS.has(p.sort) ? p.sort : 'hot';
  const limit = Math.min(25, Math.max(1, parseInt(p.limit || '14', 10)));
  const t = sort === 'top' ? '&t=day' : '';
  try {
    const r = await fetch(`https://www.reddit.com/r/${sub}/${sort}.json?limit=${limit}${t}&raw_json=1`, {
      headers: { 'user-agent': 'coinscope-social/1.0 (+https://coinscope-analytics.netlify.app)' },
    });
    if (!r.ok) return json(r.status, { error: `reddit ${r.status}`, posts: [] });
    const j = await r.json();
    const posts = ((j.data && j.data.children) || [])
      .filter((c) => c && c.data && !c.data.stickied)
      .map((c) => ({
        id: c.data.id,
        title: c.data.title,
        sub: c.data.subreddit,
        ups: c.data.ups,
        comments: c.data.num_comments,
        created: c.data.created_utc,
        permalink: 'https://www.reddit.com' + c.data.permalink,
        flair: c.data.link_flair_text || '',
        author: c.data.author,
        domain: c.data.domain || '',
      }));
    return json(200, { sub, sort, posts });
  } catch (e) {
    return json(502, { error: String(e), posts: [] });
  }
};
