/* Home section "footer" (order 90): sketchbook footer (dashed rule, pixel stats, link columns) over a brown-ink / pastel particle wave. The global
   footer is hidden on home-layout pages (body[data-layout="home"]) so the page ends here. */
(function () {
  const AL = window.AgeLens, h = AL.h;
  AL.home = AL.home || { sections: [] };
  AL.home.sections.push({ id: 'footer', order: 90, page: '*', async render(el) {
    const canvas = h('canvas.xf-canvas', { 'aria-hidden': 'true' });
    const col = (title, links) => h('div.xf-col', {}, h('p.xf-h', {}, title), h('ul', {}, links.map(([t, href]) => h('li', {}, h('a', { href }, t)))));
    const note = h('p.xf-note', {}, 'Northwestern SEPOL 425 course project. Statistics come from real recruitment ads; the example ads and cases are fictional. AgeLens cannot tell you whether you will be hired, and it is not legal advice.');
    const barData = h('span', {}, 'Demo · Synthetic data');
    // real recruitment statistics when the server has them (the examples and cases stay simulated), otherwise the simulated set
    AL.realSummary().then((real) => {
      if (real) AL.heteroData().then((hd) => { if (hd) note.textContent = note.textContent.replace('Statistics come from real recruitment ads (' + real.years + ')', 'Statistics come from real recruitment ads (' + real.years + '), including required experience and stated gender requirements'); });
      if (real) {
        note.textContent = 'Northwestern SEPOL 425 course project. Statistics come from real recruitment ads (' + real.years + '); the example ads and cases are fictional. AgeLens cannot tell you whether you will be hired, and it is not legal advice.';
        barData.textContent = 'Real ad statistics · simulated examples';
      }
    }).catch(() => {});
    const foot = h('footer.xf', {}, canvas,
      h('div.wrap.xf-inner', {},
        h('div.xf-brand', {}, h('p.xf-logo', {}, 'AgeLens'), h('p.xf-tag', {}, 'An evidence-grounded clarification assistant for mid-career jobseekers.')),
        col('Product', [['Check an ad', '#/seeker'], ['Human review', '#/requests'], ['Full report', '#/pro'], ['Reviewer', '#/reviewer']]),
        col('Project', [['Why it matters', '#/why'], ['Findings', '#/findings'], ['Method and sources', '#/about'], ['Project status', '#/status'], ['Study tools', '#/study'], ['Scoring', '#/study/score']]),
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
