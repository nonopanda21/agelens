/* Margin widgets (css/sidekit.css).
   1. Section rail (home-layout pages, wide screens): a thin list of the page's sections in the left margin; the current one is
      marked as you scroll and a click jumps to it.
   2. "Check one line" (right edge, every route except the study and scoring pages): paste one line of age wording from an ad and see how
      the AgeLens rules read it (/api/age/check: rules only, no model, nothing stored). It never says whether someone qualifies.
      The reader is shared as AgeLens.lineCheck, which the Overview hero box (pages/home_hero.js) also uses.
   Loaded after app.js; uses AgeLens.h and AgeLens.api. */
(function () {
  const AL = window.AgeLens, h = AL.h;

  /* ---- 1. section rail ---- */
  // built from the sections of the composed page now showing (AL.home.current, set by pages/home.js)
  let SECTIONS = [];
  const rail = h('nav.sk-rail', { 'aria-label': 'Sections on this page' }, h('ol', {}));
  const buildRail = () => {
    SECTIONS = (AL.home && AL.home.current) || [];
    rail.firstChild.replaceChildren(...SECTIONS.map(([id, label]) => h('li', {}, h('a', { href: '#' + id, 'data-sec': id }, h('span.sk-dot', { 'aria-hidden': 'true' }), h('span.sk-lab', {}, label)))));
    route(); spy();
  };
  // the router owns the hash, so jump by scrolling instead of navigating
  rail.addEventListener('click', (e) => {
    const a = e.target.closest('a[data-sec]'); if (!a) return; e.preventDefault();
    const el = document.getElementById(a.dataset.sec); if (!el) return;
    // move focus first: focusing during a smooth scroll cancels the scroll in Chromium
    const f = el.querySelector('h1,h2'); if (f) { f.setAttribute('tabindex', '-1'); f.focus({ preventScroll: true }); }
    // a lazily mounted section (the map) can cut a long smooth scroll short; finish the trip when it stops early
    let tries = 2;
    const go = () => el.scrollIntoView({ behavior: AL.reducedMotion && AL.reducedMotion() ? 'auto' : 'smooth', block: 'start' });
    const settle = () => {
      const off = el.getBoundingClientRect().top - (parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0);
      if (Math.abs(off) > 8 && tries-- > 0 && Math.abs(innerHeight + scrollY - document.documentElement.scrollHeight) > 2) go(); else removeEventListener('scrollend', settle);
    };
    addEventListener('scrollend', settle); go();
    setTimeout(() => removeEventListener('scrollend', settle), 4000);
  });
  document.body.appendChild(rail);
  let sraf = 0;
  const spy = () => {
    sraf = 0;
    if (document.body.dataset.layout !== 'home' || !SECTIONS.length) return;
    let cur = SECTIONS[0][0];
    for (const [id] of SECTIONS) { const el = document.getElementById(id); if (el && el.getBoundingClientRect().top < innerHeight * 0.4) cur = id; }
    rail.querySelectorAll('a').forEach((a) => { if (a.dataset.sec === cur) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current'); });
  };
  addEventListener('scroll', () => { if (!sraf) sraf = requestAnimationFrame(spy); }, { passive: true });
  addEventListener('hashchange', () => setTimeout(spy, 300));
  setTimeout(spy, 800);
  document.addEventListener('agelens:composed', buildRail);

  /* ---- 2. check one line ---- */
  const LABEL = {
    hard_cap: ['Hard cap', 'The line states an age limit with no exception.'],
    cap_with_exception: ['Cap with an exception', 'The line states an age limit and also says it can be relaxed. Who decides, and on what basis, is usually not said.'],
    preference: ['Preference, not a rule', 'The line says an age is preferred. It does not say other ages are excluded.'],
    range_or_min: ['Range or minimum', 'The line states an age range or a minimum age.'],
    ambiguous: ['Unclear wording', 'The rules found age wording but could not read it as one clear condition.'],
    none: ['No age wording found', 'The rules found no age condition in this line. That is not proof the ad has none: other parts of the ad may still mention age.'],
  };
  /* Example chips (docs/ENGLISH_UI.md): the visible label is English. The rules read Chinese ad wording, so a click sends the
     Chinese test line to the checker directly, WITHOUT putting it in the input box: the page never shows Chinese, and the
     result names the example in English. Only text the user types or pastes goes through the box. */
  const EXAMPLES = [
    ['Under 35, up to 40 for strong candidates', '\u5e74\u9f8435\u5c81\u4ee5\u4e0b\uff0c\u7279\u522b\u4f18\u79c0\u8005\u53ef\u653e\u5bbd\u81f340\u5c81'],
    ['Under 35 preferred', '35\u5c81\u4ee5\u4e0b\u4f18\u5148'],
    ['Age 25 to 40', '\u5e74\u9f8425-40\u5c81'],
  ];
  const years = (t) => t.kind === 'range' ? `${t.min_age}–${t.max_age}` : t.max_age != null ? `up to ${t.max_age}` : t.min_age != null ? `${t.min_age} or older` : null;
  // reads one line with the rules and fills `out` with the result (shared with the Overview hero box)
  async function read(out, text, exampleLabel) {
    out.replaceChildren(h('p.hint', {}, 'Reading…'));
    let r;
    try { r = await AL.api('/api/age/check', { method: 'POST', json: { text } }); }
    catch (err) { out.replaceChildren(h('p.sk-err', { role: 'alert' }, err.message)); return; }
    const [name, why] = LABEL[r.age_class] || LABEL.ambiguous;
    out.replaceChildren(h('div.sk-res.sk-' + r.age_class, {},
      exampleLabel ? h('p.sk-exl', {}, 'Example: ' + exampleLabel) : null,
      h('p.sk-cls', {}, name), h('p.sk-why', {}, why),
      r.terms.length ? h('ul.sk-terms', {}, r.terms.map((t) => h('li', {},
        h('span.sk-gloss', {}, AL.labels.termGloss(t)),
        years(t) ? h('span.sk-age', {}, 'Ages: ' + years(t)) : null,
        AL.labels.en(t.exception_en) ? h('span.sk-age', {}, 'Exception: ' + AL.labels.en(t.exception_en)) : null))) : null,
      h('p.sk-ver', {}, 'Rule set ' + r.rule_version + ' · not stored')));
  }
  AgeLens.lineCheck = {
    examples: EXAMPLES.map(([label]) => label),
    read: (out, text) => read(out, text, null),
    readExample: (out, i) => (EXAMPLES[i] ? read(out, EXAMPLES[i][1], EXAMPLES[i][0]) : null),
  };

  const tab = h('button.sk-tab', { type: 'button', 'aria-expanded': 'false', 'aria-controls': 'sk-panel' }, h('span', {}, 'Check one line'));
  const input = h('textarea#sk-in', { rows: 3, maxlength: 300, placeholder: 'Paste one line from the ad, for example the age requirement', spellcheck: 'false' });
  const out = h('div.sk-out', { 'aria-live': 'polite' });
  const form = h('form.sk-form', {},
    h('label', { for: 'sk-in' }, 'One line of age wording'), input,
    h('div.sk-ex', {}, h('span', {}, 'Try an example:'), EXAMPLES.map(([label], i) => h('button.sk-chip', { type: 'button', 'data-ex': String(i) }, label))),
    h('p.sk-hint', {}, 'Each example checks a real-style line from a Chinese ad. The reading is shown in English.'),
    h('button.btn.sk-go', { type: 'submit' }, 'Read this line'));
  const panel = h('section#sk-panel.sk-panel', { 'aria-label': 'Check one line', hidden: '' },
    h('div.sk-head', {}, h('h2', {}, 'Check one line'), h('button.sk-x', { type: 'button', 'aria-label': 'Close the one-line check' }, '×')),
    h('p.sk-note', {}, 'Rules only, no AI. Nothing you paste is stored. This reads the wording; it does not say whether you qualify.'),
    form, out,
    h('a.sk-more', { href: '#/seeker' }, 'Check a whole ad', h('span.xarrow', { 'aria-hidden': 'true' }, '›')));
  document.body.append(tab, panel);

  let opener = tab;  // where focus returns on close: the edge tab, or the phone menu's "Check one line" item
  const setOpen = (open, from) => {
    if (open) opener = from || tab;
    panel.hidden = !open; tab.setAttribute('aria-expanded', String(open)); document.body.classList.toggle('sk-open', open);
    if (open) input.focus();
    else if (opener && opener.offsetParent) opener.focus();
    else { const m = document.getElementById('main'); if (m) m.focus({ preventScroll: true }); }
  };
  AgeLens.quickCheck = { open: (from) => setOpen(true, from), available: () => !tab.hidden };
  tab.addEventListener('click', () => setOpen(panel.hidden));
  panel.querySelector('.sk-x').addEventListener('click', () => setOpen(false));
  panel.querySelector('.sk-more').addEventListener('click', () => setOpen(false));
  addEventListener('keydown', (e) => { if (e.key === 'Escape' && !panel.hidden) setOpen(false); });
  form.addEventListener('click', (e) => { const c = e.target.closest('[data-ex]'); if (c && EXAMPLES[+c.dataset.ex]) { input.value = ''; AgeLens.lineCheck.readExample(out, +c.dataset.ex); } });
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); } });

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) { out.replaceChildren(h('p.sk-err', {}, 'Paste a line of age wording first.')); input.focus(); return; }
    read(out, text, null);
  });

  // the study must not be influenced by an extra reading aid; elsewhere the tab is always there
  const route = () => {
    const study = ['study', 'score'].includes(document.body.dataset.route);
    tab.hidden = study; if (study && !panel.hidden) setOpen(false);
    const item = document.querySelector('.nav-qc'); if (item) item.hidden = study;  // the phone menu's entry follows the same rule
    rail.hidden = document.body.dataset.layout !== 'home' || SECTIONS.length < 3;
  };
  addEventListener('hashchange', () => setTimeout(route, 0));
  new MutationObserver(route).observe(document.body, { attributes: true, attributeFilter: ['data-route', 'data-layout'] });
  route();
})();
