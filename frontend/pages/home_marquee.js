/* Home section "marquee" (order 35): an Apple-style paddle carousel of data cards with ranked bars (three per row on desktop).
   Every number comes from the live simulated-data API (same source as Explore and the map). Scroll-snap row, swipe/scroll or the
   prev/next buttons; no auto-scroll. English labels only (province English names from /api/provinces; occupation map below). */
(function () {
  const AL = window.AgeLens, h = AL.h;
  const OCC = { '销售': 'Sales', '工程技术': 'Engineering', '采购': 'Procurement', '客户服务': 'Customer service', '物流仓储': 'Logistics & warehousing', '财务': 'Finance',
    '运营管理': 'Operations', '市场营销': 'Marketing', '生产制造': 'Manufacturing', '行政': 'Administration', '人力资源': 'Human resources', '设计': 'Design',
    '数据分析': 'Data analysis', '教育培训': 'Education & training', '医疗护理': 'Healthcare & nursing', '法务合规': 'Legal & compliance' };
  const CLASS = { hard_cap: 'Hard cap', cap_with_exception: 'Cap with an exception', preference: 'Preference, not a rule', range_or_min: 'Range or minimum', ambiguous: 'Unclear wording', none: 'No age wording' };
  const pc = (x) => (Math.round(x * 1000) / 10).toFixed(1) + '%';
  const occName = (o) => OCC[o] || 'Other occupation';

  // toMap: real-data cards point to the map (the explorer holds only the simulated ads)
  const toMapLink = (title) => h('a.xm-link', { href: '#/', 'aria-label': 'See the map: ' + title, onclick: (e) => { e.preventDefault(); const d = document.getElementById('data'); if (d) d.scrollIntoView({ behavior: AL.reducedMotion() ? 'auto' : 'smooth' }); } }, 'See the map', h('span.xarrow', { 'aria-hidden': 'true' }, '›'));
  function card(kicker, title, desc, rows, foot, toMap) {
    const max = Math.max(...rows.map((r) => r.v), 1e-9);
    return h('article.xm-card', {},
      h('p.xm-kick', {}, kicker), h('h3.xm-title', {}, title), h('p.xm-desc', {}, desc),
      h('ol.xm-rows', {}, rows.map((r, i) => h('li', {}, h('span.xm-i', {}, String(i + 1)), h('span.xm-name', {}, r.name),
        h('span.xm-bar', { 'aria-hidden': 'true' }, h('span', { style: `--w:${(r.v / max * 100).toFixed(1)}%` })), h('span.xm-v', {}, r.label)))),
      h('div.xm-foot', {}, h('span.xm-n', {}, foot), toMap ? toMapLink(title) : h('a.xm-link', { href: '#/explore', 'aria-label': 'Explore: ' + title }, 'Explore', h('span.xarrow', { 'aria-hidden': 'true' }, '›'))));
  }

  AL.home = AL.home || { sections: [] };
  AL.home.sections.push({ id: 'marquee', order: 35, async render(el) {
    const head = h('div.wrap.xs-head.reveal', {}, h('h2', {}, 'The evidence, ', h('span.xgrad', {}, 'ad by ad')),
      h('p', {}, 'Counts of age wording in a reproducible set of simulated job ads. They describe this dataset only, not hiring or unemployment rates.'),
      h('p.xm-head', {}, h('span.badge.sim', {}, 'Demo · Synthetic data')));
    const band = h('div.xm-band.reveal', { 'data-zoom': '', role: 'region', 'aria-label': 'Simulated data cards' }, h('p.hint', {}, 'Loading simulated data…'));
    el.append(h('div.xs.xs-tight', {}, head, band));
    const real = await AL.realSummary();
    let cards;
    if (real) {
      // real Zhaopin aggregate: the same six questions, answered from 10M+ real ads (counts only, no ad text)
      head.querySelector('p').textContent = 'Counts of age wording in ' + (real.ads / 1e6).toFixed(2) + ' million real Zhaopin job ads posted ' + real.years + '. They describe these ads only, not hiring or unemployment rates.';
      const bd = head.querySelector('.badge'); bd.className = 'badge mint'; bd.textContent = real.label;
      band.setAttribute('aria-label', 'Real data cards');
      let names2 = [];
      try { names2 = await AL.api('/api/provinces'); } catch (e) { names2 = []; }
      const en2 = Object.fromEntries(names2.map((p) => [p.name, p.en]));
      const sh = (a, b) => (b ? a / b : 0);
      const top2 = (arr, f, n) => arr.slice().sort((a, b) => f(b) - f(a)).slice(0, n);
      const big2 = real.provinces.filter((p) => p.ads >= 500);
      const fmtN = (n) => n.toLocaleString('en-US');
      cards = [
        card('Stated limits', 'Most common maximum age', 'Among real ads that state a maximum age.', real.maxAges.slice(0, 5).map(([a, c]) => ({ name: 'Under ' + a, v: c, label: pc(sh(c, real.nMax)) })), `${fmtN(real.nMax)} of ${fmtN(real.ads)} ads state a maximum`, true),
        card('By occupation', 'Explicit age limits', 'Share of ads in each occupation group with an explicit age condition.', top2(real.occs, (r) => sh(r.explicit, r.ads), 5).map((r) => ({ name: occName(r.occupation), v: sh(r.explicit, r.ads), label: pc(sh(r.explicit, r.ads)) })), `${real.occupations} occupation groups`, true),
        card('How it is phrased', 'How age is written', 'Share of all ads. One ad can mention an exception and state a cap.', [
          ['A maximum age (cap)', real.cap], ['A range or a minimum age', real.explicit - real.cap], ['Mentions an exception', real.withException], ['A preference, not a rule', real.preference]].map(([n, v]) => ({ name: n, v, label: pc(sh(v, real.ads)) })), `${fmtN(real.ads)} ads`, true),
        card('By region', 'Age wording by province', 'Share of ads with any age wording, provinces with at least 500 ads.', top2(big2, (r) => sh(r.age_wording, r.ads), 5).map((r) => ({ name: en2[r.province] || 'Province', v: sh(r.age_wording, r.ads), label: pc(sh(r.age_wording, r.ads)) })), `${big2.length} provinces with 500+ ads`, true),
        card('By region', 'Where the ads are', 'Number of real ads per province.', top2(real.provinces, (r) => r.ads, 5).map((r) => ({ name: en2[r.province] || 'Province', v: r.ads, label: fmtN(r.ads) })), `${real.regions} regions with ads`, true),
        card('Exceptions', 'Exceptions mentioned', 'Ads whose age wording includes an exception or flexibility clause, provinces with at least 500 ads.', top2(big2, (r) => sh(r.with_exception, r.ads), 5).map((r) => ({ name: en2[r.province] || 'Province', v: sh(r.with_exception, r.ads), label: pc(sh(r.with_exception, r.ads)) })), `${fmtN(real.withException)} ads mention one`, true),
      ];
    }
    if (!cards) {  // no real aggregate on this server: the simulated set, as before
    let occ, prov, maxAge, names;
    try { [occ, prov, maxAge, names] = await Promise.all(['/api/stats/occupations?limit=200', '/api/stats/provinces', '/api/stats/max-age', '/api/provinces'].map((u) => AL.api(u))); }
    catch (e) { band.replaceChildren(h('p.notice.error', { role: 'alert' }, 'The simulated data could not be loaded: ' + e.message)); return; }
    const en = Object.fromEntries(names.map((p) => [p.name, p.en]));
    const nAds = occ.reduce((s, r) => s + r.ads, 0);
    const withMax = maxAge.reduce((s, r) => s + r.count, 0);
    const classTot = {}; prov.forEach((p) => Object.entries(p.age_class_counts || {}).forEach(([k, v]) => { classTot[k] = (classTot[k] || 0) + v; }));
    const top = (arr, k, n) => arr.slice().sort((a, b) => b[k] - a[k]).slice(0, n);
    const big = prov.filter((p) => p.ads >= 20);
    cards = [
      card('Stated limits', 'Most common maximum age', 'Among simulated ads that state a maximum age.', top(maxAge, 'count', 5).map((r) => ({ name: 'Under ' + r.max_age, v: r.count, label: r.count + ' ads' })), `${withMax} of ${nAds} ads state a maximum`),
      card('By occupation', 'Explicit age limits', 'Share of ads in each occupation with an explicit age condition.', top(occ, 'explicit_share', 5).map((r) => ({ name: occName(r.occupation), v: r.explicit_share, label: pc(r.explicit_share) })), `${nAds} ads · ${occ.length} occupations`),
      card('How it is phrased', 'Kinds of age wording', 'A cap, a cap with an exception and a preference are different things.', Object.entries(classTot).filter(([k]) => k !== 'none').sort((a, b) => b[1] - a[1]).slice(0, 5).map(([k, v]) => ({ name: CLASS[k] || k, v, label: v + ' ads' })), `${nAds} ads`),
      card('By region', 'Age wording by province', 'Share of ads with any age wording, provinces with at least 20 ads.', top(big, 'age_wording_share', 5).map((r) => ({ name: en[r.province] || 'Province', v: r.age_wording_share, label: pc(r.age_wording_share) })), `${big.length} provinces with 20+ ads`),
      card('By region', 'Where the ads are', 'Number of simulated ads per province.', top(prov, 'ads', 5).map((r) => ({ name: en[r.province] || 'Province', v: r.ads, label: r.ads + ' ads' })), `${prov.filter((p) => p.ads > 0).length} provinces with ads`),
      card('Exceptions', 'Exceptions mentioned', 'Ads whose age wording includes an exception or flexibility clause.', top(prov.map((p) => ({ ...p, ex: p.ads ? p.with_exception / p.ads : 0 })).filter((p) => p.ads >= 20), 'ex', 5).map((r) => ({ name: en[r.province] || 'Province', v: r.ex, label: pc(r.ex) })), `${big.length} provinces with 20+ ads`),
    ];
    }
    const track = h('div.xm-track', { tabindex: '0', 'aria-label': 'Data cards. Scroll sideways or use the buttons below.' }, cards);
    const chev = (d) => { const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('aria-hidden', 'true');
      const p = document.createElementNS('http://www.w3.org/2000/svg', 'path'); p.setAttribute('d', d); p.setAttribute('fill', 'none'); p.setAttribute('stroke', 'currentColor'); p.setAttribute('stroke-width', '2.2'); p.setAttribute('stroke-linecap', 'round'); p.setAttribute('stroke-linejoin', 'round'); s.append(p); return s; };
    const step = (dir) => { const c = track.firstElementChild; const w = c ? c.getBoundingClientRect().width + parseFloat(getComputedStyle(track).columnGap || 0) : track.clientWidth;
      track.scrollBy({ left: dir * w, behavior: AL.reducedMotion() ? 'auto' : 'smooth' }); };
    const prev = h('button.xm-nav', { type: 'button', 'aria-label': 'Previous cards', onclick: () => step(-1) }, chev('M15 5l-7 7 7 7'));
    const next = h('button.xm-nav', { type: 'button', 'aria-label': 'Next cards', onclick: () => step(1) }, chev('M9 5l7 7-7 7'));
    const sync = () => { const max = track.scrollWidth - track.clientWidth - 2; prev.disabled = track.scrollLeft <= 2; next.disabled = track.scrollLeft >= max; };
    track.addEventListener('scroll', () => requestAnimationFrame(sync), { passive: true });
    const ro = new ResizeObserver(sync); ro.observe(track); AL.onLeave(() => ro.disconnect());
    band.replaceChildren(track, h('div.xm-ctrl', {}, prev, next));
    sync();
  } });
})();
