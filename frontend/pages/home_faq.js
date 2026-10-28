/* Home section "faq" (order 60): three boundary cards (reference three-card section) + a compact FAQ, including the honest evaluation note. */
(function () {
  const AL = window.AgeLens, h = AL.h;
  const CARDS = [
    ['Not legal advice', 'Highlighted wording is observed text to interpret. It is not a finding about any employer and not a legal conclusion.'],
    ['No hiring decisions', 'AgeLens never says whether you qualify or predicts whether you would be rejected. Your age is used only to explain a stated condition.'],
    ['Honest about what runs', 'Home-page statistics come from real Zhaopin ads (counts only); the ads you can open and the demo cases are simulated. Answers come from fixed rules (“Template demo”); no AI model is connected. The planned evaluation has not been run.'],
  ];
  const FAQ = [
    ['Where does the data come from?', 'Two sources, always labelled. The statistics and the map summarise about 10 million real job ads posted on Zhaopin in 2021–2024 (counts only; no ad text, company or contact is published). The ads you can open, the Job Seeker answers and the demo cases use a fictional, reproducible set, marked “Demo · Synthetic data”, so every example can be shown in full.'],
    ['What happens to my CV?', 'It is read in memory to suggest fields you can edit and confirm. The file itself is not stored, and it is never sent to an outside model.'],
    ['Is AI used?', 'Not yet. Briefs are produced by fixed rules and templates. If a model is connected later, its output is checked against the quoted evidence and labelled.'],
    ['Can text in an ad or a CV change how the system behaves?', 'No. Ads and CVs are treated as data to analyse, never as instructions.'],
    ['How will you test whether this helps?', 'We plan a small classroom study: each person writes four questions about fictional ads, two with the ad alone and two with AgeLens’s evidence check, and blind raters score them. It has not been run yet, and it cannot show effects on unemployment or hiring.'],
  ];
  AL.home = AL.home || { sections: [] };
  AL.home.sections.push({ id: 'faq', order: 60, render(el) {
    el.append(h('div.wrap.xs', {},
      h('div.xs-head.reveal', {}, h('h2', {}, 'Clear about ', h('span.xgrad', {}, 'what it is not')),
        h('p', {}, 'AgeLens helps you read evidence and prepare questions. The final answer always comes from a person.')),
      h('div.xc-grid', {}, CARDS.map(([t, p], i) => h('article.xc.reveal', { style: `--d:${i * 70}ms` }, h('h3.xc-title', {}, t), h('p', {}, p)))),
      h('div.xfaq.reveal', {}, FAQ.map(([q, a]) => h('details.xfaq-i', {}, h('summary', {}, q), h('p', {}, a)))),
      h('p.xs-more.reveal', {}, h('a', { href: '#/about' }, 'Method, sources and limits', h('span.xarrow', { 'aria-hidden': 'true' }, '›')))));
  } });
})();
