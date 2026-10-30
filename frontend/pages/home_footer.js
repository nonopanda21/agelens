/* Home section "footer" (order 90): sketchbook footer (dashed rule, pixel stats, link columns) over a brown-ink / pastel particle wave. The global
   footer is hidden on home-layout pages (body[data-layout="home"]) so the page ends here. */
(function () {
  const AL = window.AgeLens, h = AL.h;
  AL.home = AL.home || { sections: [] };
  AL.home.sections.push({ id: 'footer', order: 90, page: '*', async render(el) {
    const canvas = h('canvas.xf-canvas', { 'aria-hidden': 'true' });
    const col = (title, links) => h('div.xf-col', {}, h('p.xf-h', {}, title), h('ul', {}, links.map(([t, href]) => h('li', {}, h('a', { href }, t)))));
    const fstat = (label) => h('div.xf-stat', {}, h('p.xf-stat-n', {}, '–'), h('p.xf-stat-l', {}, label));
    const stats = h('div.wrap.xf-stats', { 'aria-label': 'Dataset size' }, fstat('Job ads'), fstat('Regions with ads'), fstat('Occupation groups'));
    const note = h('p.xf-note', {}, 'Northwestern SEPOL 425 course project. Statistics come from real Zhaopin job ads; the examples and cases are simulated. Not legal advice; no hiring decisions.');
    const barData = h('span', {}, 'Demo · Synthetic data');
    // real Zhaopin statistics when the server has them (the examples and cases stay simulated), otherwise the simulated set
    Promise.all([AL.realSummary(), AL.api('/api/overview').catch(() => null)]).then(([real, ov]) => {
      const v = real ? [real.ads, real.regions, real.occupations] : ov ? [ov.unique_ads, ov.provinces, ov.occupations] : null;
      if (!v) { stats.hidden = true; return; }
      stats.querySelector('.xf-stat-l').textContent = real ? 'Real job ads, ' + real.years : 'Simulated ads';
      stats.querySelectorAll('.xf-stat-n').forEach((n, i) => { n.textContent = typeof v[i] === 'number' ? v[i].toLocaleString('en-US') : '–'; });
      if (real) AL.heteroData().then((hd) => { if (hd) note.textContent = note.textContent.replace('Statistics come from real Zhaopin job ads (' + real.years + ')', 'Statistics come from real Zhaopin job ads (' + real.years + '), including required experience and stated gender requirements'); });
      if (real) {
        note.textContent = 'Northwestern SEPOL 425 course project. Statistics come from real Zhaopin job ads (' + real.years + '); the examples and cases are simulated. Not legal advice; no hiring decisions.';
        barData.textContent = 'Real ad statistics · simulated examples';
      }
    }).catch(() => { stats.hidden = true; });
    const foot = h('footer.xf', {}, canvas, stats,
      h('div.wrap.xf-inner', {},
        h('div.xf-brand', {}, h('p.xf-logo', {}, 'AgeLens'), h('p.xf-tag', {}, 'Age requirements in job ads, read as evidence.')),
        col('Product', [['Job Seeker', '#/seeker'], ['Explore data', '#/explore'], ['My requests', '#/requests'], ['Reviewer', '#/reviewer']]),
        col('Project', [['Why it matters', '#/why'], ['Findings', '#/findings'], ['Method and sources', '#/about'], ['Study tools', '#/study'], ['Scoring', '#/study/score']]),
        h('div.xf-col', {}, h('p.xf-h', {}, 'About'), note)),
      h('div.xf-bar', {}, h('div.wrap', {}, h('span', {}, 'AgeLens · course prototype'), AL.motionToggle(), barData)));
    el.append(foot);
    let neb = null, reg = null, disposed = false;
    AL.onLeave(() => { disposed = true; if (reg) reg.dispose(); if (neb) neb.dispose(); neb = null; });
    if (!AL.gfx || !AL.gfx.webgl()) return;
    try {
      const mod = await import('../js/nebula.js');
      const light = matchMedia('(max-width: 720px)').matches || matchMedia('(pointer:coarse)').matches;
      neb = await mod.createNebula({ canvas, host: foot, variant: 'footer', light, reduced: () => AL.reducedMotion() });
      if (disposed) { neb.dispose(); neb = null; return; }
      foot.classList.add('ready');
      const ro = new ResizeObserver(() => neb && neb.resize()); ro.observe(foot); AL.onLeave(() => ro.disconnect());
      foot.addEventListener('pointermove', (e) => { if (e.pointerType !== 'mouse' || !neb) return; const r = foot.getBoundingClientRect(); neb.pointer(e.clientX - r.left, e.clientY - r.top, true); });
      foot.addEventListener('pointerleave', () => neb && neb.pointer(0, 0, false));
      reg = AL.gfx.register('nebula-footer', { el: foot, start: () => neb && neb.start(), stop: () => neb && neb.stop() });
    } catch (e) { if (window.console) console.info('Footer nebula unavailable (' + (e && e.message) + ')'); }
  } });
})();
