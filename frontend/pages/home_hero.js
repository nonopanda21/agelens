/* Home hero (order 10), sketchbook style after the reference site: left-aligned hand-lettered title with a pink second line, an
   elliptical badge, sketch buttons, pixel-font stats from the live API, and a doodle (job ad with the age line circled, magnifier,
   star, heart, cloud, sparkles) on the right. Behind it the particle field (js/nebula.js) is recoloured as brown-ink and pastel
   speckles on paper, animated by default; a paper scrim under the copy keeps text contrast. Static paper + copy if WebGL is unavailable. */
(function () {
  const AL = window.AgeLens, h = AL.h;
  let introPlayed = false;
  const fmt = (n) => (typeof n === 'number' ? n.toLocaleString('en-US') : '–');
  // title letters as hop-in spans (visual only; the h1 carries the full text as its accessible name)
  const letters = (txt, base) => { let i = base; const out = []; txt.split(' ').forEach((w, wi) => { if (wi) { out.push(' '); i++; } out.push(h('span.xw', {}, [...w].map((c) => h('span.xch', { style: '--i:' + i++ }, c)))); }); return out; };
  // count a stat up from zero once the intro reaches it
  function countUp(node, to, delayMs) {
    if (typeof to !== 'number' || AL.reducedMotion()) { node.textContent = fmt(to); return; }
    node.textContent = '0';
    setTimeout(() => { const t0 = performance.now(), D = 1100;
      const step = (t) => { const k = Math.min(1, (t - t0) / D), e = 1 - Math.pow(1 - k, 4); node.textContent = fmt(Math.round(to * e)); if (k < 1) requestAnimationFrame(step); };
      requestAnimationFrame(step); }, delayMs);
  }

  // Doodle: static SVG markup written here (no user text). Brown ink strokes, pastel fills.
  const DOODLE = `<svg viewBox="0 0 380 360" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false" class="xh-art-svg">
  <g class="dd dd-card"><path d="M74 92c38-3 140-5 196 0 6 1 9 4 9 10l2 168c0 6-3 9-9 9-62 3-136 3-196 0-6 0-9-3-9-9l-2-169c0-6 3-9 9-9z" fill="#fff" stroke="#4A3728" stroke-width="3" stroke-linejoin="round"/>
    <path d="M70 92c40-2 142-4 200 0" fill="none" stroke="#4A3728" stroke-width="3"/>
    <rect x="66" y="93" width="214" height="30" rx="8" fill="#FFE6EA"/><circle cx="86" cy="108" r="5" fill="#FFB6C1" stroke="#4A3728" stroke-width="2"/><circle cx="102" cy="108" r="5" fill="#FFF5BA" stroke="#4A3728" stroke-width="2"/><circle cx="118" cy="108" r="5" fill="#B5EAD7" stroke="#4A3728" stroke-width="2"/>
    <path d="M92 146h120M92 166h150M92 226h132M92 246h96" stroke="#4A3728" stroke-width="3" stroke-linecap="round" opacity=".55"/>
    <path d="M92 196h46" stroke="#4A3728" stroke-width="3" stroke-linecap="round" opacity=".55"/>
    <text x="146" y="203" font-family="Press Start 2P, monospace" font-size="15" fill="#4A3728">35</text>
    <path d="M139 182c14-9 44-8 52 3 7 11-6 24-27 25-22 1-34-7-31-17 2-6 8-10 16-12" fill="none" stroke="#E0607E" stroke-width="3" stroke-linecap="round"/></g>
  <g class="dd dd-lens"><circle cx="268" cy="238" r="40" fill="#E3F3F9" fill-opacity=".75" stroke="#4A3728" stroke-width="3.5"/><path d="M250 222c6-7 16-10 25-8" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round"/>
    <path d="M297 268l38 38" stroke="#4A3728" stroke-width="11" stroke-linecap="round"/><path d="M297 268l38 38" stroke="#D5C6E0" stroke-width="5" stroke-linecap="round"/></g>
  <g class="dd dd-star"><path d="M318 34l10 22 24 3-18 16 5 24-21-12-21 12 5-24-18-16 24-3z" fill="#4A3728" stroke="#4A3728" stroke-width="2" stroke-linejoin="round"/></g>
  <g class="dd dd-heart"><path d="M40 62c-10-14 4-28 16-18 4 3 6 6 7 9 2-4 4-7 8-9 13-8 25 8 13 21L58 92z" fill="none" stroke="#E0607E" stroke-width="3" stroke-linejoin="round"/></g>
  <g class="dd dd-cloud"><path d="M196 52c-2-12 14-20 24-12 4-12 24-12 28 2 12-2 18 12 8 18h-56c-6 0-8-6-4-8z" fill="#fff" stroke="#4A3728" stroke-width="3" stroke-linejoin="round"/></g>
  <g class="dd dd-sp1"><path d="M30 196l4 10 10 4-10 4-4 10-4-10-10-4 10-4z" fill="#FFF5BA" stroke="#4A3728" stroke-width="2" stroke-linejoin="round"/></g>
  <g class="dd dd-sp2"><path d="M350 150l3 7 7 3-7 3-3 7-3-7-7-3 7-3z" fill="#B5EAD7" stroke="#4A3728" stroke-width="2" stroke-linejoin="round"/></g>
  <g class="dd dd-sp3"><path d="M150 318l3 7 7 3-7 3-3 7-3-7-7-3 7-3z" fill="#D5C6E0" stroke="#4A3728" stroke-width="2" stroke-linejoin="round"/></g>
  <path d="M40 344h300" stroke="#4A3728" stroke-width="3" stroke-dasharray="9 8" stroke-linecap="round"/>
</svg>`;

  AL.home = AL.home || { sections: [] };
  AL.home.sections.push({ id: 'hero', order: 10, async render(el) {
    const canvas = h('canvas.xh-canvas', { 'aria-hidden': 'true' });
    const glow = h('div.xh-glow', { 'aria-hidden': 'true' });
    const toHow = () => { const n = document.getElementById('how'); if (n) n.scrollIntoView({ behavior: AL.reducedMotion() ? 'auto' : 'smooth' }); };
    const stat = (n, label) => h('div.xh-stat', {}, h('p.xh-stat-n', {}, n), h('p.xh-stat-l', {}, label));
    const stats = h('div.xh-stats', { 'aria-label': 'Simulated dataset size' }, stat('–', 'Simulated ads'), stat('–', 'Regions'), stat('–', 'Occupations'));
    const art = h('div.xh-art'); art.innerHTML = DOODLE;
    // ink every outlined shape stroke by stroke, then colour it in (css/intro.css); the dashed ground line keeps its dashes
    let k = 0;
    art.querySelectorAll('.dd path, .dd circle, .dd rect').forEach((n) => {
      const st = n.getAttribute('stroke'), fl = n.getAttribute('fill');
      if (st && st !== 'none' && !n.getAttribute('stroke-dasharray')) { n.setAttribute('pathLength', '1'); n.classList.add('ink'); }
      if (fl && fl !== 'none') n.classList.add('fil');
      n.style.setProperty('--k', k++);
    });
    const hero = h('div.xh', { 'data-state': 'loading' },
      canvas, glow,
      h('div.wrap.xh-grid', {},
        h('div.xh-inner', {},
          h('p.xh-badge', {}, 'Template demo · simulated data'),
          h('h1.xh-title', { 'aria-label': 'Make sense of the age requirement' }, h('span.xh-l1', { 'aria-hidden': 'true' }, letters('Make sense of', 0)), h('span.xh-l2', { 'aria-hidden': 'true' }, letters('the age requirement', 14))),
          h('p.xh-sub', {}, 'Bring your experience and your question. AgeLens reads the original hiring evidence with you and helps you prepare what to ask a person.'),
          h('div.xh-actions', {}, h('a.xbtn.xbtn-lg', { href: '#/seeker' }, 'Ask about my situation'), h('button.xbtn.xbtn-2.xbtn-lg', { type: 'button', onclick: toHow }, 'See how it works')),
          stats,
          h('p.xh-fine', {}, 'Not legal advice. AgeLens never decides whether you qualify.'),
          h('p.xh-paused', { hidden: true, role: 'status' }, 'Animation is paused in this browser. ', h('button.xh-play', { type: 'button', onclick: () => AL.motion.set(false) }, 'Play animation'))),
        art));
    if (introPlayed || AL.reducedMotion()) hero.classList.add('no-intro'); introPlayed = true;
    const pausedNote = hero.querySelector('.xh-paused');
    const syncPaused = () => { pausedNote.hidden = !AL.motion.reduced(); pausedNote.firstChild.textContent = AL.motion.userPaused() ? 'Animation is paused in this browser. ' : 'Your system asks for reduced motion, so the animation is still. '; };
    syncPaused(); AL.motion.onChange(syncPaused);
    el.append(hero);

    AL.api('/api/overview').then((ov) => {
      if (!ov) return;
      const v = [ov.unique_ads, ov.provinces, ov.occupations];
      const play = !hero.classList.contains('no-intro');
      const lead = play ? (parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--intro-delay')) || 0) * 1000 + 850 : 0;
      stats.querySelectorAll('.xh-stat-n').forEach((n, i) => { if (play) countUp(n, v[i], lead + i * 120); else n.textContent = fmt(v[i]); });
    }).catch(() => { stats.hidden = true; });

    let neb = null, reg = null, disposed = false;
    AL.onLeave(() => { disposed = true; if (reg) reg.dispose(); if (neb) neb.dispose(); neb = null; });
    if (!AL.gfx || !AL.gfx.webgl()) { hero.dataset.state = 'fallback'; return; }
    try {
      const mod = await import('../js/nebula.js');
      const narrow = matchMedia('(max-width: 900px)').matches;
      const light = matchMedia('(max-width: 720px)').matches || matchMedia('(pointer:coarse)').matches;
      // thin the speckles behind the copy: left column on desktop, upper middle on phones
      const maskBox = narrow ? [0.5, 0.42, 0.62, 0.36] : [0.3, 0.5, 0.27, 0.34];
      const inst = await mod.createNebula({ canvas, host: hero, glow, variant: 'hero', light, maskBox, reduced: () => AL.reducedMotion() });
      if (disposed) { inst.dispose(); return; }
      neb = inst; hero.dataset.state = 'ready';
      const ro = new ResizeObserver(() => neb && neb.resize()); ro.observe(hero); AL.onLeave(() => ro.disconnect());
      hero.addEventListener('pointermove', (e) => { if (e.pointerType !== 'mouse' || !neb) return; const r = hero.getBoundingClientRect(); neb.pointer(e.clientX - r.left, e.clientY - r.top, true); });
      hero.addEventListener('pointerleave', () => neb && neb.pointer(0, 0, false));
      reg = AL.gfx.register('nebula-hero', { el: hero, start: () => neb && neb.start(), stop: () => neb && neb.stop() });
      AL.motion.onChange(() => { if (!disposed && neb && AL.reducedMotion()) neb.renderStatic(); });
      window.__nebula = { stats: () => neb && neb.stats() };
    } catch (e) {
      hero.dataset.state = 'fallback';
      if (window.console) console.info('Nebula: static background (' + (e && e.message) + ')');
    }
  } });
})();
