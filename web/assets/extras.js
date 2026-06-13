/* ===== extras.js — curated static datasets =====
 * New listings, upcoming releases, airdrops and articles.
 * Sample/illustrative data for the demo (clearly labelled in the UI).
 */
window.EXTRAS = {
  newListings: [
    { name: 'Monad', symbol: 'MON', cat: 'Layer 1', listed: '2026-06-09', price: 3.42, ch24h: 18.4, exchange: 'Binance' },
    { name: 'Berachain', symbol: 'BERA', cat: 'Layer 1', listed: '2026-06-07', price: 6.18, ch24h: -4.2, exchange: 'OKX' },
    { name: 'Eigen', symbol: 'EIGEN', cat: 'Restaking', listed: '2026-06-05', price: 4.05, ch24h: 9.7, exchange: 'Coinbase' },
    { name: 'Story', symbol: 'IP', cat: 'AI / IP', listed: '2026-06-03', price: 2.71, ch24h: 22.1, exchange: 'Bybit' },
    { name: 'Grass', symbol: 'GRASS', cat: 'DePIN', listed: '2026-06-01', price: 1.88, ch24h: 5.3, exchange: 'KuCoin' },
    { name: 'Hyperliquid', symbol: 'HYPE', cat: 'DeFi / Perp', listed: '2026-05-29', price: 28.4, ch24h: 12.6, exchange: 'Gate.io' },
  ],
  upcoming: [
    { name: 'Nexus zkVM', symbol: 'NEX', cat: 'ZK / L1', date: '2026-06-24', status: 'Mainnet + TGE', hype: 92 },
    { name: 'Succinct', symbol: 'PROVE', cat: 'ZK Proving', date: '2026-07-02', status: 'Token Sale', hype: 84 },
    { name: 'Towns', symbol: 'TOWNS', cat: 'Social', date: '2026-07-10', status: 'Airdrop + Listing', hype: 71 },
    { name: 'Camp Network', symbol: 'CAMP', cat: 'AI Data', date: '2026-07-18', status: 'TGE', hype: 78 },
    { name: 'MegaETH', symbol: 'MEGA', cat: 'Layer 2', date: '2026-08-01', status: 'Mainnet', hype: 95 },
  ],
  airdrops: [
    { name: 'LayerZero S2', symbol: 'ZRO', type: 'Retroactive', est: '$300–$2,000', status: 'Confirmed', deadline: '2026-06-30', action: 'Bridge + vote' },
    { name: 'Monad', symbol: 'MON', type: 'Testnet', est: '$150–$1,200', status: 'Live', deadline: '2026-07-15', action: 'Run testnet txs' },
    { name: 'Hyperliquid S3', symbol: 'HYPE', type: 'Points', est: '$500–$5,000', status: 'Live', deadline: 'Ongoing', action: 'Trade + provide LP' },
    { name: 'Eclipse', symbol: 'ES', type: 'Galxe Quests', est: '$80–$600', status: 'Upcoming', deadline: '2026-08-01', action: 'Complete quests' },
    { name: 'Fogo', symbol: 'FOGO', type: 'Testnet', est: '$100–$900', status: 'Live', deadline: '2026-07-20', action: 'Validator / txs' },
  ],
  news: [
    { source: 'Market', time: '14m ago', tag: 'Bitcoin', title: 'Bitcoin holds above key support as ETF inflows resume', summary: 'Spot ETFs logged a third straight day of net inflows, easing fears of a deeper pullback.' },
    { source: 'DeFi', time: '38m ago', tag: 'Ethereum', title: 'Ethereum staking ratio hits new all-time high', summary: 'Over 29% of circulating ETH is now staked as restaking demand climbs.' },
    { source: 'Altcoins', time: '1h ago', tag: 'Solana', title: 'Solana DEX volume overtakes Ethereum for the week', summary: 'On-chain activity surged on the back of new memecoin and DePIN launches.' },
    { source: 'Regulation', time: '2h ago', tag: 'Policy', title: 'New stablecoin framework clears committee vote', summary: 'Issuers would face reserve and audit requirements under the proposed rules.' },
    { source: 'Layer 2', time: '3h ago', tag: 'Scaling', title: 'Rollup fees drop to record lows after blob upgrade', summary: 'Average L2 transaction costs fell below a cent across major networks.' },
    { source: 'NFT', time: '5h ago', tag: 'Culture', title: 'On-chain gaming token leads weekly gainers', summary: 'A breakout title pushed its in-game token up triple digits on the week.' },
    { source: 'Macro', time: '6h ago', tag: 'Markets', title: 'Risk assets rally as rate-cut odds firm up', summary: 'Crypto tracked equities higher after softer inflation data.' },
    { source: 'Security', time: '8h ago', tag: 'Safety', title: 'Bridge exploit recovered after white-hat negotiation', summary: 'Most of the affected funds were returned within 48 hours.' },
  ],
  articles: [
    { tag: 'Strategy', date: 'Jun 11, 2026', title: 'Cross-Exchange Arbitrage: A Practical 2026 Playbook', read: '8 min', blurb: 'How to size positions, account for withdrawal fees, and avoid the spread traps that erase profit.' },
    { tag: 'Analysis', date: 'Jun 10, 2026', title: 'Reading RSI Divergence Like a Pro', read: '6 min', blurb: 'Why price highs and momentum highs diverging is one of the most reliable reversal tells.' },
    { tag: 'Macro', date: 'Jun 9, 2026', title: 'Altseason Indicators: What the Data Says Now', read: '7 min', blurb: 'BTC dominance, ETH/BTC ratio and stablecoin supply — the three charts that matter.' },
    { tag: 'Airdrops', date: 'Jun 8, 2026', title: 'The Airdrop Farmer’s Risk Checklist', read: '5 min', blurb: 'Sybil detection, gas burn and opportunity cost — when farming is worth it and when it isn’t.' },
  ],
};
