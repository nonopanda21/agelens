/* Home composer (lead-owned). Sections register themselves: AgeLens.home.sections.push({id, order, page?, rail?, render(el)}).
   page: 'home' (default), 'why', 'findings', or '*' (every composed page, e.g. the footer). rail: label in the section rail.
   Overview stays short (hero, how, data, steps, more); detail lives on Why it matters (#/why) and Findings (#/findings).
   A section that throws is replaced by a quiet notice; others still render. */
AgeLens.home = AgeLens.home || { sections: [] };
(function () {
  const AL = AgeLens;
  /** Render every section registered for `page` into el, in order. */
  AL.home.compose = async function (el, page) {
    const h = AL.h;
    const list = AL.home.sections.filter((s) => (s.page || 'home') === page || s.page === '*').sort((a, b) => a.order - b.order);
    AL.home.current = list.filter((s) => s.rail).map((s) => [s.id, s.rail]);
    for (const s of list) {
      const holder = h('section', { id: s.id, class: 'home-sec home-' + s.id });
      el.append(holder);
      try { await s.render(holder); }
      catch (e) { holder.replaceChildren(h('div.wrap.section', {}, h('p.hint', { role: 'status' }, 'This section could not load. The rest of the page still works.'))); }
    }
    if (AL.home.pendingScroll) {
      const t = document.getElementById(AL.home.pendingScroll); AL.home.pendingScroll = null;
      if (t) setTimeout(() => t.scrollIntoView({ block: 'start' }), 60);
    }
    document.dispatchEvent(new CustomEvent('agelens:composed'));
  };
  /** Go to a section, on this page if it is here, otherwise on the composed page that holds it. */
  AL.home.goto = function (id, route) {
    const t = document.getElementById(id);
    if (t) return t.scrollIntoView({ behavior: AL.reducedMotion && AL.reducedMotion() ? 'auto' : 'smooth', block: 'start' });
    AL.home.pendingScroll = id; location.hash = route;
  };
  const page = (key, title) => ({ title, layout: 'home', render: (el) => AL.home.compose(el, key) });
  AL.pages.home = page('home', 'Overview');
  AL.pages.why = page('why', 'Why it matters');
  AL.pages.findings = page('findings', 'Findings');
})();
