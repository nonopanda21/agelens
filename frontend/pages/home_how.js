/* Home section "how" (order 20, under the example): the three steps of Check an ad as numbered circles joined by a dashed line
   (reference "how to join"), then the CTA. One list only: the example above already shows what the answer looks like. */
(function () {
  const AL = window.AgeLens, h = AL.h;
  const STEPS = [
    ['Paste the ad', 'In Chinese or English. Add your role, age and experience if you like.'],
    ['Read what is clear and what is not', 'The age sentence is quoted whole. What the ad leaves open is listed, not guessed.'],
    ['Ask the employer one question', 'Copy the neutral question or download the brief. A person on the course team can check it first.'],
  ];
  AL.home = AL.home || { sections: [] };
  AL.home.sections.push({ id: 'how', order: 20, rail: 'How it works', render(el) {
    el.append(h('div.wrap.xs', {},
      h('div.xs-head.reveal', {}, h('h2', {}, 'How it works'),
        h('p', {}, AgeLens.byModel('Fixed rules read the wording; no AI model is connected yet, and nothing is decided for you.', 'Fixed rules read the wording, an AI model adds an explanation that code checks, and nothing is decided for you.'))),
      h('ol.xst', {}, STEPS.map(([t, p], i) => h('li.xst-i.reveal', { style: `--d:${i * 80}ms` }, h('span.xst-n', {}, String(i + 1).padStart(2, '0')), h('h3', {}, t), h('p', {}, p))))));
  } });
})();
