/* Home section "fit" (order 30): who AgeLens is for, what it does and what it does not do. Static text. */
(function () {
  const AL = window.AgeLens, h = AL.h;
  const DOES = ['Quotes the whole age sentence in English, exception included', 'Separates a firm cap, an exception and a soft preference', 'Lists what the ad leaves open instead of guessing', 'Drafts one neutral question you can send', 'Shows how often 10 million real ads state an age'];
  const DOESNT = ['Tell you whether you will be hired or qualify', 'Hide or rank jobs by your age', 'Judge whether an employer acts lawfully', 'Store the ad you paste or your CV file', AgeLens.byModel('Use an AI model (none is connected yet)', 'Let an AI model decide anything: it only adds statements that code checks')];
  AL.home = AL.home || { sections: [] };
  AL.home.sections.push({ id: 'fit', order: 30, rail: 'What it does', render(el) {
    const list = (cls, title, items) => h('div.xfit-col.' + cls + '.reveal', {}, h('h3', {}, title), h('ul', {}, items.map((t) => h('li', {}, t))));
    el.append(h('div.wrap.xs', {},
      h('div.xs-head.reveal', {}, h('h2', {}, 'What AgeLens ', h('span.xgrad', {}, 'does')),
        h('p', {}, 'For mid-career jobseekers, in any field, who meet an age line in a Chinese job ad. Job sites show the ad and lawyers cover rights; AgeLens is the step between.')),
      h('div.xfit-cols', {}, list('yes', 'AgeLens does', DOES), list('no', 'AgeLens does not', DOESNT))));
  } });
})();
