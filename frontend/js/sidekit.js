/* Margin widgets (css/sidekit.css).
   1. Section rail (home only, wide screens): a thin list of the home sections in the left margin; the current one is
      marked as you scroll and a click jumps to it.
   2. Quick check (right edge, every route except the study and scoring pages): paste one line of age wording from an ad and see how the
      AgeLens rules read it (/api/age/check: rules only, no model, nothing stored). It never says whether someone qualifies.
   Loaded after app.js; uses AgeLens.h and AgeLens.api. */
(function () {
  const AL = window.AgeLens, h = AL.h;

  /* ---- 1. section rail ---- */
  const SECTIONS = [['hero', 'Top'], ['how', 'What it does'], ['marquee', 'The evidence'], ['data', 'Data map'], ['fields', 'Every field'],
    ['literature', 'Why it matters'], ['faq', 'What it is not'], ['steps', 'How to use']];
  const rail = h('nav.sk-rail', { 'aria-label': 'Sections on this page' },
    h('ol', {}, SECTIONS.map(([id, label]) => h('li', {}, h('a', { href: '#' + id, 'data-sec': id }, h('span.sk-dot', { 'aria-hidden': 'true' }), h('span.sk-lab', {}, label))))));
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
    if (document.body.dataset.route !== 'home') return;
    let cur = SECTIONS[0][0];
    for (const [id] of SECTIONS) { const el = document.getElementById(id); if (el && el.getBoundingClientRect().top < innerHeight * 0.4) cur = id; }
    rail.querySelectorAll('a').forEach((a) => { if (a.dataset.sec === cur) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current'); });
  };
  addEventListener('scroll', () => { if (!sraf) sraf = requestAnimationFrame(spy); }, { passive: true });
  addEventListener('hashchange', () => setTimeout(spy, 300));
  setTimeout(spy, 800);

  /* ---- 2. quick check ---- */
  const LABEL = {
    hard_cap: ['Hard cap', 'The line states an age limit with no exception.'],
    cap_with_exception: ['Cap with an exception', 'The line states an age limit and also says it can be relaxed. Who decides, and on what basis, is usually not said.'],
    preference: ['Preference, not a rule', 'The line says an age is preferred. It does not say other ages are excluded.'],
    range_or_min: ['Range or minimum', 'The line states an age range or a minimum age.'],
    ambiguous: ['Unclear wording', 'The rules found age wording but could not read it as one clear condition.'],
    none: ['No age wording found', 'The rules found no age condition in this line. That is not proof the ad has none: other parts of the ad may still mention age.'],
  };
  const EXAMPLES = ['年龄35岁以下，特别优秀者可放宽至40岁', '35岁以下优先', '年龄25-40岁'];
  const tab = h('button.sk-tab', { type: 'button', 'aria-expanded': 'false', 'aria-controls': 'sk-panel' }, h('span', {}, 'Quick check'));
  const input = h('textarea#sk-in', { rows: 3, maxlength: 300, placeholder: 'Paste one line from the ad, for example the age requirement', spellcheck: 'false' });
  const out = h('div.sk-out', { 'aria-live': 'polite' });
  const form = h('form.sk-form', {},
    h('label', { for: 'sk-in' }, 'One line of age wording'), input,
    h('div.sk-ex', {}, h('span', {}, 'Try:'), EXAMPLES.map((t) => h('button.sk-chip', { type: 'button', lang: 'zh', 'data-ex': t }, t))),
    h('button.btn.sk-go', { type: 'submit' }, 'Read this line'));
  const panel = h('section#sk-panel.sk-panel', { 'aria-label': 'Quick check', hidden: '' },
    h('div.sk-head', {}, h('h2', {}, 'Quick check'), h('button.sk-x', { type: 'button', 'aria-label': 'Close quick check' }, '×')),
    h('p.sk-note', {}, 'Rules only, no AI. Nothing you paste is stored. This reads the wording; it does not say whether you qualify.'),
    form, out,
    h('a.sk-more', { href: '#/seeker' }, 'Check a whole ad and ask a reviewer', h('span.xarrow', { 'aria-hidden': 'true' }, '›')));
  document.body.append(tab, panel);

  const setOpen = (open) => {
    panel.hidden = !open; tab.setAttribute('aria-expanded', String(open)); document.body.classList.toggle('sk-open', open);
    if (open) input.focus(); else tab.focus();
  };
  tab.addEventListener('click', () => setOpen(panel.hidden));
  panel.querySelector('.sk-x').addEventListener('click', () => setOpen(false));
  panel.querySelector('.sk-more').addEventListener('click', () => setOpen(false));
  addEventListener('keydown', (e) => { if (e.key === 'Escape' && !panel.hidden) setOpen(false); });
  form.addEventListener('click', (e) => { const c = e.target.closest('[data-ex]'); if (c) { input.value = c.dataset.ex; form.requestSubmit(); } });
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); } });

  const years = (t) => t.kind === 'range' ? `${t.min_age}–${t.max_age}` : t.max_age != null ? `up to ${t.max_age}` : t.min_age != null ? `${t.min_age} or older` : null;
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) { out.replaceChildren(h('p.sk-err', {}, 'Paste a line of age wording first.')); input.focus(); return; }
    out.replaceChildren(h('p.hint', {}, 'Reading…'));
    let r;
    try { r = await AL.api('/api/age/check', { method: 'POST', json: { text } }); }
    catch (err) { out.replaceChildren(h('p.sk-err', { role: 'alert' }, err.message)); return; }
    const [name, why] = LABEL[r.age_class] || LABEL.ambiguous;
    out.replaceChildren(h('div.sk-res.sk-' + r.age_class, {},
      h('p.sk-cls', {}, name), h('p.sk-why', {}, why),
      r.terms.length ? h('ul.sk-terms', {}, r.terms.map((t) => h('li', {},
        h('q.quote', { lang: 'zh' }, t.snippet),
        years(t) ? h('span.sk-age', {}, 'Ages: ' + years(t)) : null,
        t.exception_text ? h('span.sk-age', {}, 'Exception: ', h('span', { lang: 'zh' }, t.exception_text)) : null))) : null,
      h('p.sk-ver', {}, 'Rule set ' + r.rule_version + ' · not stored')));
  });

  // the study must not be influenced by an extra reading aid; elsewhere the tab is always there
  const route = () => {
    const study = ['study', 'score'].includes(document.body.dataset.route);
    tab.hidden = study; if (study && !panel.hidden) setOpen(false);
    rail.hidden = document.body.dataset.route !== 'home';
  };
  addEventListener('hashchange', () => setTimeout(route, 0));
  new MutationObserver(route).observe(document.body, { attributes: true, attributeFilter: ['data-route'] });
  route();
})();
