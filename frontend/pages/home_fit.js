/* Home section "fit" (order 30): where AgeLens sits next to the tools a jobseeker already has (job sites show the ad, legal advice
   covers rights; AgeLens covers the step in between), then what it does and does not do. Static text; no claims about other products
   beyond what they are for. */
(function () {
  const AL = window.AgeLens, h = AL.h;
  const LANES = [
    ['Job sites', 'show you the ad', 'You see the age line, but not what it means for you or how firm it is.', false],
    ['AgeLens', 'helps you read the age line and ask about it', 'The step between reading an ad and deciding to apply: quote, clarify, ask.', true],
    ['Legal advice', 'tells you your rights', 'For a dispute or a complaint. AgeLens is not legal advice and does not judge employers.', false],
  ];
  const DOES = ['Quotes the whole age sentence in English, exception included', 'Separates a firm cap, an exception and a soft preference', 'Lists what the ad leaves open instead of guessing', 'Drafts one neutral question you can send', 'Puts the line in context: how often 10 million real ads state an age'];
  const DOESNT = ['Tell you whether you will be hired or qualify', 'Hide or rank jobs by your age', 'Judge whether an employer acts lawfully', 'Store the ad you paste or your CV file', 'Use an AI model (none is connected yet)'];
  AL.home = AL.home || { sections: [] };
  AL.home.sections.push({ id: 'fit', order: 30, rail: 'Where it fits', render(el) {
    const list = (cls, title, items) => h('div.xfit-col.' + cls + '.reveal', {}, h('h3', {}, title), h('ul', {}, items.map((t) => h('li', {}, t))));
    el.append(h('div.wrap.xs', {},
      h('div.xs-head.reveal', {}, h('h2', {}, 'Where AgeLens ', h('span.xgrad', {}, 'fits')),
        h('p', {}, 'For mid-career jobseekers, in any field, who meet an age line in a Chinese job ad and want to know where they stand before applying.')),
      h('ol.xfit-lanes', { 'aria-label': 'Where AgeLens sits among the tools a jobseeker uses' }, LANES.map(([name, verb, note, me], i) =>
        h('li.xfit-lane.reveal' + (me ? '.me' : ''), { style: `--d:${i * 70}ms` }, h('p.xfit-name', {}, name), h('p.xfit-verb', {}, verb), h('p.xfit-note', {}, note)))),
      h('div.xfit-cols', {}, list('yes', 'AgeLens does', DOES), list('no', 'AgeLens does not', DOESNT))));
  } });
})();
