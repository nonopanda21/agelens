/* Home section "steps" (order 70): three numbered circles joined by a gradient line + centred CTA (reference "how to join"). */
(function () {
  const AL = window.AgeLens, h = AL.h;
  const STEPS = [
    ['Share your background', 'Write your question first, then add your role and experience, or drop in a CV you can edit.'],
    ['Explore the evidence', 'See matching ads with the age wording quoted, what is explicit, and what stays uncertain.'],
    ['Get a clearer next step', 'Download a short brief with neutral questions, or send it to a human reviewer.'],
  ];
  AL.home = AL.home || { sections: [] };
  AL.home.sections.push({ id: 'steps', order: 70, render(el) {
    el.append(h('div.wrap.xs', {},
      h('div.xs-head.reveal', {}, h('h2', {}, 'How to use AgeLens'), h('p', {}, 'Three steps, a few minutes, and nothing is decided for you.')),
      h('ol.xst', {}, STEPS.map(([t, p], i) => h('li.xst-i.reveal', { style: `--d:${i * 80}ms` }, h('span.xst-n', {}, String(i + 1).padStart(2, '0')), h('h3', {}, t), h('p', {}, p)))),
      h('p.xst-cta.reveal', {}, h('a.xbtn.xbtn-lg', { href: '#/seeker' }, 'Ask about my situation'))));
  } });
})();
