/* Home section "steps" (order 30, right after "how"): three numbered circles joined by a gradient line + centred CTA (reference "how to join"). */
(function () {
  const AL = window.AgeLens, h = AL.h;
  const STEPS = [
    ['Paste the ad and your background', 'Paste the ad you are looking at, write your question, and add your role and experience. A CV can fill these in; you confirm every field.'],
    ['Read what is clear and what is not', 'The age wording is quoted as written. AgeLens separates what the ad states from what it leaves open, and shows how similar ads word age.'],
    ['Send one neutral question', 'Download the brief with your question for the employer, or ask a human reviewer to check it first.'],
  ];
  AL.home = AL.home || { sections: [] };
  AL.home.sections.push({ id: 'steps', order: 30, rail: 'How to use', render(el) {
    el.append(h('div.wrap.xs', {},
      h('div.xs-head.reveal', {}, h('h2', {}, 'How to use AgeLens'), h('p', {}, 'Three steps, a few minutes. Nothing is decided for you.')),
      h('ol.xst', {}, STEPS.map(([t, p], i) => h('li.xst-i.reveal', { style: `--d:${i * 80}ms` }, h('span.xst-n', {}, String(i + 1).padStart(2, '0')), h('h3', {}, t), h('p', {}, p)))),
      h('p.xst-cta.reveal', {}, h('a.xbtn.xbtn-lg', { href: '#/seeker' }, 'Check an ad'))));
  } });
})();
