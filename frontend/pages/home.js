/* Home composer (lead-owned). Sections register themselves: AgeLens.home.sections.push({id, order, render(el)}).
   Orders: hero 10 · literature 20 · steps 30 · data 40 · faq 50. A section that throws is replaced by a quiet notice; others still render. */
AgeLens.home = AgeLens.home || { sections: [] };
AgeLens.pages.home = {
  title: 'Overview',
  async render(el) {
    const h = AgeLens.h;
    for (const s of AgeLens.home.sections.slice().sort((a, b) => a.order - b.order)) {
      const holder = h('section', { id: s.id, class: 'home-sec home-' + s.id });
      el.append(holder);
      try { await s.render(holder); }
      catch (e) { holder.replaceChildren(h('div.wrap.section', {}, h('p.hint', { role: 'status' }, 'This section could not load. The rest of the page still works.'))); }
    }
  },
};
