/* Home section "footer" (order 90): sketchbook footer (dashed rule, pixel stats, link columns) over a brown-ink / pastel particle wave. The global
   footer is hidden on the home route (body[data-route="home"]) so the page ends here. */
(function () {
  const AL = window.AgeLens, h = AL.h;
  AL.home = AL.home || { sections: [] };
  AL.home.sections.push({ id: 'footer', order: 90, async render(el) {
    const canvas = h('canvas.xf-canvas', { 'aria-hidden': 'true' });
    const col = (title, links) => h('div.xf-col', {}, h('p.xf-h', {}, title), h('ul', {}, links.map(([t, href]) => h('li', {}, h('a', { href }, t)))));
    const fstat = (label) => h('div.xf-stat', {}, h('p.xf-stat-n', {}, '–'), h('p.xf-stat-l', {}, label));
    const stats = h('div.wrap.xf-stats', { 'aria-label': 'Simulated dataset size' }, fstat('Simulated ads'), fstat('Regions with ads'), fstat('Occupation groups'));
    AL.api('/api/overview').then((ov) => { if (!ov) return; const v = [ov.unique_ads, ov.provinces, ov.occupations];
      stats.querySelectorAll('.xf-stat-n').forEach((n, i) => { n.textContent = typeof v[i] === 'number' ? v[i].toLocaleString('en-US') : '–'; }); }).catch(() => { stats.hidden = true; });
    const foot = h('footer.xf', {}, canvas, stats,
      h('div.wrap.xf-inner', {},
        h('div.xf-brand', {}, h('p.xf-logo', {}, 'AgeLens'), h('p.xf-tag', {}, 'Age requirements in job ads, read as evidence.')),
        col('Product', [['Job Seeker', '#/seeker'], ['Explore data', '#/explore'], ['My requests', '#/requests'], ['Reviewer', '#/reviewer']]),
        col('Project', [['Method and sources', '#/about'], ['Study tools', '#/study'], ['Scoring', '#/study/score']]),
        h('div.xf-col', {}, h('p.xf-h', {}, 'About'), h('p.xf-note', {}, 'Northwestern SEPOL 425 course project. All ads and cases are simulated. Not legal advice; no hiring decisions.'))),
      h('div.xf-bar', {}, h('div.wrap', {}, h('span', {}, 'AgeLens · local prototype'), AL.motionToggle(), h('span', {}, 'Demo · Synthetic data'))));
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
