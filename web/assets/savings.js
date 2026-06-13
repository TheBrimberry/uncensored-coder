/* ===== savings.js — renders the high-yield savings comparison ===== */
(function () {
  const data = Array.isArray(window.HYSA) ? window.HYSA.slice() : [];
  const body = document.getElementById('hy-body');
  const cards = document.getElementById('hy-cards');
  const search = document.getElementById('hy-search');
  const sortSel = document.getElementById('hy-sort');
  if (!body) return;

  const apy = (v) => `${v.toFixed(2)}%`;
  const money = (v) => v <= 0 ? 'None' : `$${v.toLocaleString('en-US')}`;
  const fee = (v) => v <= 0 ? '<span class="pos">$0</span>' : `$${v}`;

  function topApy() { return Math.max.apply(null, data.map((d) => d.apy)); }

  function renderCards() {
    if (!cards) return;
    // Pick a few standout "best for" picks.
    const byApy = data.slice().sort((a, b) => b.apy - a.apy);
    const noMin = data.filter((d) => d.min === 0).sort((a, b) => b.apy - a.apy);
    const picks = [
      { tag: 'Highest APY', c: byApy[0] },
      { tag: 'Best with no minimum', c: noMin[0] },
      { tag: 'Best for big balances', c: data.find((d) => d.name.indexOf('CIT') === 0) || byApy[1] },
      { tag: 'Safest (gov-backed)', c: data.find((d) => d.type === 'Government bond') || byApy[2] },
    ];
    cards.innerHTML = picks.map(({ tag, c }) => `
      <div class="hy-card">
        <span class="hy-card__tag">${tag}</span>
        <div class="hy-card__apy">${apy(c.apy)}<small> APY</small></div>
        <div class="hy-card__name">${c.name}</div>
        <div class="hy-card__type muted">${c.type}</div>
        <p class="hy-card__best">${c.best}</p>
      </div>`).join('');
  }

  function renderTable() {
    const q = (search && search.value || '').trim().toLowerCase();
    const mode = (sortSel && sortSel.value) || 'apy';
    let rows = data.filter((d) =>
      !q || d.name.toLowerCase().includes(q) || d.type.toLowerCase().includes(q) || d.best.toLowerCase().includes(q));
    rows.sort((a, b) =>
      mode === 'name' ? a.name.localeCompare(b.name)
        : mode === 'min' ? a.min - b.min || b.apy - a.apy
          : b.apy - a.apy);
    const max = topApy();
    body.innerHTML = rows.length ? rows.map((d) => `
      <tr>
        <td><b>${d.name}</b></td>
        <td>${d.type}</td>
        <td class="num"><span class="hy-apy ${d.apy >= max - 0.0001 ? 'hy-apy--best' : ''}">${apy(d.apy)}</span></td>
        <td class="num">${money(d.min)}</td>
        <td>${fee(d.fee)}</td>
        <td class="muted">${d.best}</td>
      </tr>`).join('') : '<tr><td class="empty" colspan="6">No matches.</td></tr>';
  }

  renderCards();
  renderTable();
  if (search) search.addEventListener('input', renderTable);
  if (sortSel) sortSel.addEventListener('change', renderTable);
})();
