/* Page heads for the two detail pages (Why it matters #/why, Findings #/findings) and the Overview's "read more" strip (order 60).
   The detail sections themselves are the former home sections, registered with page: 'why' / 'findings' (pages/home.js). */
(function () {
  const AL = window.AgeLens, h = AL.h;
  AL.home = AL.home || { sections: [] };
  const head = (page, title, lead) => ({ id: page + '-head', order: 1, page, render(el) {
    el.append(h('div.wrap.xpg-head', {}, h('h1', {}, title), h('p', {}, lead)));
  } });
  AL.home.sections.push(head('why', 'Why it matters',
    'What research shows about age lines in job ads, how we expect AgeLens to help, and what it does not do.'));
  AL.home.sections.push(head('findings', 'Findings',
    'What real recruitment ads from 2021–2024 say about age. These are counts of ad wording, not differences in who is hired. Differences by location are on the Overview map.'));

  const MORE = [
    ['#/why', 'Why it matters', 'The research, and how AgeLens is meant to help.'],
    ['#/findings', 'Findings', 'How age wording varies across about 10 million real ads.'],
    ['#/about', 'Method and sources', 'The rules, the data, accuracy and privacy.'],
  ];
  AL.home.sections.push({ id: 'more', order: 60, rail: 'Read more', render(el) {
    el.append(h('div.wrap.xs', {},
      h('div.xs-head.reveal', {}, h('h2', {}, 'Read more')),
      h('div.xc-grid', {}, MORE.map(([href, t, p], i) => h('a.xc.xmore.reveal', { href, style: `--d:${i * 70}ms` },
        h('h3.xc-title', {}, t), h('p', {}, p), h('span.xmore-go', { 'aria-hidden': 'true' }, 'Open ›')))),
      h('p.xst-cta.reveal', {}, h('a.xbtn.xbtn-lg', { href: '#/seeker' }, 'Check an ad'))));
  } });
})();
