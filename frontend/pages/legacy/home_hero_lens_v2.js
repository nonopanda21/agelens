/* Home hero: copy + interactive "Evidence lens" scene (Three.js via js/lens.js, with static SVG/HTML fallback).
   The real, selectable text is HTML; WebGL only draws particles, lines, decorative ad fragments and the lens. */
(function () {
  const AL = window.AgeLens, h = AL.h;
  const STAGES = [
    { id: 'question', name: 'Your question', live: 'Step 1 of 3, Your question: a fictional 38-year-old procurement job seeker writes down what they want to know.' },
    { id: 'wording', name: 'Original wording', live: 'Step 2 of 3, Original wording: the ad sets a guideline of 35 and mentions an exception for outstanding candidates. The two are shown linked.' },
    { id: 'clarify', name: 'What to clarify', live: 'Step 3 of 3, What to clarify: neutral questions the job seeker could ask the employer. Nothing here says whether they qualify.' },
  ];
  let introPlayed = false; // the intro choreography plays once per page load, not on every visit to Overview

  function panels() {
    const q = h('div.lp', { 'data-i': 0 },
      h('blockquote.lp-quote', {}, '“I’m 38, with eight years in procurement. The ad says applicants should normally be under 35, but exceptions are possible. What should I clarify before applying?”'),
      h('p.lp-note', {}, 'Written by a fictional job seeker. AgeLens starts from your own question and background.'));
    const w = h('div.lp', { 'data-i': 1 },
      h('div.lp-ad', {},
        h('p.lp-line', {}, h('mark.cond', {}, 'Applicants should normally be under 35,'), h('span.tag', {}, 'Condition')),
        h('p.lp-line', {}, h('mark.exc', {}, 'but exceptions may be made for outstanding candidates.'), h('span.tag', {}, 'Exception'))),
      h('p.lp-note', {}, 'The ad does not say who decides, or what counts as “outstanding”. The two statements are shown linked.'));
    const c = h('div.lp', { 'data-i': 2 },
      h('ul.lp-qs', {},
        h('li', {}, 'How are exceptions to the age guideline decided, and who decides?'),
        h('li', {}, 'What would count as “especially outstanding” for this role?'),
        h('li', {}, 'Is 35 a screening cut-off, or a general guideline?')),
      h('p.lp-note', {}, 'Questions for the employer to answer. AgeLens does not judge whether anyone is eligible.'));
    return [q, w, c];
  }

  function fallbackSvg() {
    const ns = 'http://www.w3.org/2000/svg';
    const s = document.createElementNS(ns, 'svg');
    s.setAttribute('class', 'scene-svg'); s.setAttribute('viewBox', '0 0 400 260'); s.setAttribute('aria-hidden', 'true'); s.setAttribute('preserveAspectRatio', 'xMidYMin meet');
    let d = '';
    for (let i = 0; i < 46; i++) { const a = i * 2.399, r = 30 + (i * 37 % 150); d += `<circle cx="${200 + Math.cos(a) * r * 1.3}" cy="${130 + Math.sin(a) * r * 0.8}" r="${1.2 + (i % 3) * .5}" fill="#8A95A8" opacity=".5"/>`; }
    s.innerHTML = d + '<circle cx="200" cy="130" r="74" fill="#fff" fill-opacity=".35" stroke="#2563EB" stroke-width="2"/>'
      + '<path d="M150 112h100M150 130h100M150 148h100" stroke="#8A95A8" stroke-width="2" opacity=".6"/>'
      + '<path d="M150 112h46M204 148h46" stroke="#2563EB" stroke-width="4"/><path d="M196 112q16 18 8 36" fill="none" stroke="#2563EB" stroke-width="1.5" stroke-dasharray="3 3"/>';
    return s;
  }

  AL.home = AL.home || { sections: [] };
  AL.home.sections.push({ id: 'hero', order: 10, async render(el) {
    const mq = window.matchMedia('(max-width: 720px)');
    const tabs = STAGES.map((s, i) => h('button.lt', { type: 'button', role: 'tab', id: 'lt-' + s.id, 'aria-selected': i === 0 ? 'true' : 'false', 'aria-controls': 'lp-' + s.id, tabindex: i === 0 ? '0' : '-1', 'data-i': i },
      h('span.lt-n', { 'aria-hidden': 'true' }, String(i + 1)), s.name));
    const pans = panels().map((p, i) => { p.id = 'lp-' + STAGES[i].id; p.setAttribute('role', 'tabpanel'); p.setAttribute('aria-labelledby', 'lt-' + STAGES[i].id); p.tabIndex = 0; return p; });
    const live = h('p.lp-live', { 'aria-live': 'polite' }, STAGES[0].live);
    const pauseBtn = h('button.lens-pause', { type: 'button', 'aria-pressed': 'false' }, 'Pause motion');
    const canvas = h('canvas.scene-canvas', { 'aria-hidden': 'true' });
    const slot = h('div.lens-slot', { 'aria-hidden': 'true' });
    const svg = fallbackSvg();
    const card = h('div.lens-card', {}, h('div.lt-list', { role: 'tablist', 'aria-label': 'Evidence lens stages' }, tabs), h('div.lp-stack', {}, pans), live);
    const scene = h('div.hero-scene', { role: 'group', 'aria-label': 'Evidence lens, an illustrative example', 'data-state': 'loading' },
      svg, canvas,
      h('div.scene-top', {}, h('span.badge.ill', {}, 'Illustrative example'), pauseBtn, h('span.vh', {}, 'Fictional job seeker and ad wording. Not a real analysis.')),
      slot, card);
    const seeBtn = h('button.btn.btn-secondary', { type: 'button', onclick: () => { const t = document.getElementById('steps'); if (t) t.scrollIntoView({ behavior: AL.reducedMotion() ? 'auto' : 'smooth', block: 'start' }); } }, 'See how it works');
    el.append(h('div.wrap.hero', {},
      h('div.hero-copy', {},
        h('h1', {}, 'Make sense of the age requirement.'),
        h('p.hero-sub', {}, 'Bring your experience and your question. AgeLens reads the hiring evidence with you and helps you prepare what to ask.'),
        h('div.hero-actions', {}, h('a.btn.btn-primary', { href: '#/seeker' }, 'Ask about my situation'), seeBtn),
        h('p.hint.hero-fine', {}, 'Template demo, simulated data. Not legal advice.')),
      scene));

    // ---- stages (work with or without WebGL) ----
    let cur = 0, lens = null, disposed = false, reg = null;
    function setStage(i, focus, instant) {
      cur = i;
      tabs.forEach((b, k) => { const on = k === i; b.setAttribute('aria-selected', on ? 'true' : 'false'); b.tabIndex = on ? 0 : -1; });
      pans.forEach((p, k) => p.classList.toggle('on', k === i));
      scene.dataset.stage = STAGES[i].id; live.textContent = STAGES[i].live;
      if (focus) tabs[i].focus();
      if (lens) lens.setStage(i, instant);
    }
    tabs.forEach((b, i) => b.addEventListener('click', () => setStage(i, false)));
    tabs.forEach((b, i) => b.addEventListener('keydown', (e) => {
      const k = { ArrowRight: (i + 1) % 3, ArrowDown: (i + 1) % 3, ArrowLeft: (i + 2) % 3, ArrowUp: (i + 2) % 3, Home: 0, End: 2 }[e.key];
      if (k == null) return; e.preventDefault(); setStage(k, true);
    }));
    setStage(0, false);

    // ---- local pause control ----
    const syncPause = () => { const p = AL.motion.userPaused(); pauseBtn.setAttribute('aria-pressed', p ? 'true' : 'false'); pauseBtn.textContent = p ? 'Motion paused' : 'Pause motion'; scene.classList.toggle('still', AL.reducedMotion()); };
    pauseBtn.addEventListener('click', () => AL.motion.set(!AL.motion.userPaused()));
    AL.motion.onChange(() => { if (!disposed) syncPause(); }); syncPause();

    // ---- scroll recede: transform/opacity only, native scroll ----
    let rafS = 0;
    const onScroll = () => { if (rafS) return; rafS = requestAnimationFrame(() => { rafS = 0; const hh = el.offsetHeight || 1; const p = AL.reducedMotion() ? 0 : Math.max(0, Math.min(1, (window.scrollY - hh * 0.12) / (hh * 0.8))); scene.style.setProperty('--rec', p.toFixed(3)); }); };
    window.addEventListener('scroll', onScroll, { passive: true }); onScroll();
    AL.onLeave(() => { disposed = true; window.removeEventListener('scroll', onScroll); cancelAnimationFrame(rafS); if (reg) reg.dispose(); if (lens) lens.dispose(); lens = null; });

    // ---- WebGL scene (lazy; any failure leaves the static diagram) ----
    if (!AL.gfx || !AL.gfx.webgl()) { scene.dataset.state = 'fallback'; return; }
    try {
      const mod = await import('../js/lens.js');
      const inst = await mod.createLens({ canvas, host: scene, slot, light: mq.matches || matchMedia('(pointer:coarse)').matches, maxDpr: (mq.matches || matchMedia('(pointer:coarse)').matches) ? 1.5 : 2, reduced: () => AL.reducedMotion() });
      if (disposed) { inst.dispose(); return; }
      lens = inst; scene.dataset.state = 'ready';
      lens.setStage(cur, true);
      if (!introPlayed) { introPlayed = true; lens.intro(); } else lens.setStage(cur, true);
      const ro = new ResizeObserver(() => lens && lens.resize()); ro.observe(scene);
      AL.onLeave(() => ro.disconnect());
      const onMove = (e) => { if (e.pointerType !== 'mouse' || !lens) return; const r = scene.getBoundingClientRect(); lens.pointer(e.clientX - r.left, e.clientY - r.top, true); };
      const onOut = () => lens && lens.pointer(0, 0, false);
      scene.addEventListener('pointermove', onMove); scene.addEventListener('pointerleave', onOut);
      reg = AL.gfx.register('hero', { el: scene, start: () => lens && lens.start(), stop: () => lens && lens.stop() });
      AL.motion.onChange(() => { if (!disposed && lens && AL.reducedMotion()) lens.renderOnce(); });
      window.__lens = { stats: () => lens && lens.stats(), setStage, running: () => lens && lens.isRunning() };
    } catch (e) {
      scene.dataset.state = 'fallback';
      if (window.console) console.info('Evidence lens: using static diagram (' + (e && e.message) + ')');
    }
  } });
})();
