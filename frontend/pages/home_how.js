/* Home section "how" (order 20, under the example): the three steps of Check an ad as numbered circles joined by a dashed line
   (reference "how to join"), then the CTA. One list only: the example above already shows what the answer looks like. */
(function () {
  const AL = window.AgeLens, h = AL.h;
  const STEPS = [
    ['Paste the ad', 'Paste the ad you are looking at, in Chinese, as it was posted. Add your role, age and experience if you like; a CV can fill them in and you confirm every field.'],
    ['Read what is clear and what is not', 'The age sentence is quoted whole, exception included. AgeLens separates what the ad states from what it leaves open, and never guesses the open part.'],
    ['Ask the employer one question', 'Copy the neutral question, or download the brief. If you want a second pair of eyes, a person on the course team can check it first.'],
  ];
  AL.home = AL.home || { sections: [] };
  AL.home.sections.push({ id: 'how', order: 20, rail: 'How it works', render(el) {
    el.append(h('div.wrap.xs', {},
      h('div.xs-head.reveal', {}, h('h2', {}, 'How it works'),
        h('p', {}, 'Three steps, a few minutes. ', AgeLens.byModel('Fixed rules read the wording; no AI model is connected yet, and nothing is decided for you.', 'Fixed rules read the wording, an AI model adds an explanation that code checks, and nothing is decided for you.'))),
      h('ol.xst', {}, STEPS.map(([t, p], i) => h('li.xst-i.reveal', { style: `--d:${i * 80}ms` }, h('span.xst-n', {}, String(i + 1).padStart(2, '0')), h('h3', {}, t), h('p', {}, p)))),
      h('p.xst-cta.reveal', {}, h('a.xbtn.xbtn-lg', { href: '#/seeker' }, 'Check an ad'))));
  } });
})();
