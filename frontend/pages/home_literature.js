/* Home section "Why it matters" (agent L; Lin card updated 2026-10-28 from the full text). Two literature cards, each
   with a figure redrawn from printed numbers only. Verification record: docs/LITERATURE.md. The "motivation" section
   (home_motivation.js) gives the one-line takeaways; this section holds the figures, estimates and limits.
   Literature motivates age thresholds; it is NOT an evaluation of AgeLens. */
AgeLens.home = AgeLens.home || { sections: [] };
AgeLens.home.sections.push({
  id: 'literature', order: 50,
  async render(el) {
    const h = AgeLens.h;
    const loadFig = async (src) => {
      const fig = h('div.lit-fig');
      try {
        const res = await fetch(src);
        if (!res.ok) throw new Error('missing');
        const doc = new DOMParser().parseFromString(await res.text(), 'image/svg+xml');
        const svg = doc.documentElement;
        if (svg.nodeName !== 'svg' || doc.querySelector('parsererror')) throw new Error('bad svg');
        svg.querySelectorAll('script,foreignObject').forEach((n) => n.remove());
        fig.append(document.importNode(svg, true));
      } catch (e) {
        fig.append(h('p.hint', { role: 'status' }, 'The figure could not load. Its numbers are in the table below.'));
      }
      return fig;
    };
    const [fig, linFig] = await Promise.all([loadFig('figures/feng2026_fig1_redrawn.svg'), loadFig('figures/lin2025_redrawn.svg')]);
    const rows = [['Applications per posting', '0.949', '−0.161 (0.043)', '17%'], ['Positive responses per posting', '0.323', '−0.062 (0.025)', 'nearly 20%'], ['Positive-response rate per application', '0.365', '−0.050 (0.021)', '13.7%']];
    const table = h('table.lit-table', {},
      h('caption.vh', {}, 'Estimates printed in Feng et al. (2026), Figure 1'),
      h('thead', {}, h('tr', {}, ['Outcome', 'Mean below limit', 'θ (SE)', 'Decline stated in text'].map((t) => h('th', { scope: 'col' }, t)))),
      h('tbody', {}, rows.map((r) => h('tr', {}, r.map((c, i) => h(i ? 'td' : 'th', i ? {} : { scope: 'row' }, c))))));

    const feng = h('article.lit-card', {},
      h('div.lit-head', {}, h('h3', {}, 'A posted age limit is binding'), h('span.lit-status.ok', {}, 'Checked against the full text')),
      h('p.lit-plain', {}, 'Applicants just above a posted maximum age get about 14–20% fewer applications and callbacks than those just below it.'),
      fig,
      h('p.lit-src', {}, 'Source: Feng, Lefgren, Liu, Platt and Xia (2026), “Signals, Steps, and Setbacks: Age Discrimination in a Laddered Labor Market”, NBER Working Paper 35709 (not peer-reviewed), Figure 1 (a–c). ',
        h('a', { href: 'https://www.nber.org/papers/w35709', target: '_blank', rel: 'noopener' }, 'nber.org/papers/w35709'), ' · DOI 10.3386/w35709. ',
        'Redrawn by the AgeLens team. No values were digitised; bars use only the printed estimates.'),
      h('details.lit-more', {}, h('summary', {}, 'Numbers behind the figure'), table,
        h('p.hint', {}, 'Data: one Chinese recruitment platform; 510,425 postings (Aug–Sep 2022) and 11,607 Guangdong applicants aged 21–45 with bachelor’s degrees. Regression discontinuity on applicant age in months relative to the posted limit. The paper’s own plot shows individual bins and 95% intervals; they are not reproduced here.')));

    const linRows = [['Linear, 45 months', '205,967', '0.1403 (0.0594)', '0.1396 (0.0594)'], ['Quadratic, 58 months', '267,139', '0.1838 (0.0771)', '0.1811 (0.0771)']];
    const linTable = h('table.lit-table', {},
      h('caption.vh', {}, 'Estimates printed in Lin (2025), Table 2'),
      h('thead', {}, h('tr', {}, ['Local regression, bandwidth', 'People', 'Jump at 35 (SE)', 'With controls'].map((t) => h('th', { scope: 'col' }, t)))),
      h('tbody', {}, linRows.map((r) => h('tr', {}, r.map((c, i) => h(i ? 'td' : 'th', i ? {} : { scope: 'row' }, c))))));
    const lin = h('article.lit-card.lin', {},
      h('div.lit-head', {}, h('h3', {}, '35 as a cliff in China'), h('span.lit-status.ok', {}, 'Checked against the full text')),
      h('p.lit-plain', {}, 'Ads name 35 as the cap more than any other age. In the 2015 census, people just over 35 had lost a job for an employer reason more often than people just under it: 0.54% against 0.40%, about a third more.'),
      linFig,
      h('p.lit-src', {}, 'Source: Lin Wenlian (2025), “Age discrimination causes unemployment: a regression discontinuity design” (Chinese-language article; English title as printed on p. 120), China Economic Quarterly 25(1): 103–120, Fig. 1 (p. 106) and Tables 1–2 (pp. 108–109). DOI ',
        h('a', { href: 'https://doi.org/10.13821/j.cnki.ceq.2025.01.07', target: '_blank', rel: 'noopener' }, '10.13821/j.cnki.ceq.2025.01.07'), '. ',
        'Redrawn by the AgeLens team from printed values only.'),
      h('details.lit-more', {}, h('summary', {}, 'Design, numbers and limits'), linTable,
        h('ul.lit-facts', {},
          h('li', {}, h('b', {}, 'Ads: '), '59.69 million postings from five job sites, 2016–2021: 18.95% state an age limit, 17.47% an upper limit (p. 105). A recheck on 41.59 million postings from 2022–2024 gives similar shares (p. 106).'),
          h('li', {}, h('b', {}, 'People: '), '2015 census (about 2 million records), working-age people only; regression discontinuity on age in months around 35, with county fixed effects (pp. 107–108).'),
          h('li', {}, h('b', {}, 'Checks: '), 'no bunching of birth dates at 35; most background traits are smooth at 35 (Table 3, p. 112); no jump at other ages from 21 to 49, and no jump in quitting, housework or other non-work reasons (p. 113).'),
          h('li', {}, h('b', {}, 'Who: '), 'the jump is significant for people with high school or less (0.1675) and for men and married people within that group; for college graduates it is not (−0.0569, SE 0.1854; Table 6, p. 117).'),
          h('li', {}, h('b', {}, 'When: '), 'also found in the 2005 census, but not significant in 2010 (p. 117).'),
          h('li', {}, h('b', {}, 'Limits: '), 'the outcome is a dismissal share among all working-age people, not an unemployment rate. The link to negative age stereotypes uses city-level keyword patterns in ads, which the author notes can be confounded by other city factors (p. 115). Whether the anchor at 35 comes from civil-service age limits is untested (p. 117). Robustness tables are in an online appendix we did not read.'))));

    el.append(h('div.wrap.section.lit-sec', {},
      h('h2', {}, 'Why it matters'),
      h('p.lit-lead', {}, 'In Chinese recruitment, a number such as 35 in an ad can decide who applies and who gets a reply. Two studies show how strongly stated age limits shape outcomes, which is why AgeLens asks what an ad’s age wording really means before you apply.'),
      h('p.hint', {}, 'This is background reading, not an evaluation of AgeLens.'),
      h('div.lit-grid', {}, feng, lin),
      h('details.lit-notes', {}, h('summary', {}, 'Notes and limits'),
        h('ul', {},
          h('li', {}, 'Feng et al. is a working paper and has not been peer-reviewed. Its sample is college-educated applicants in one province on one platform.'),
          h('li', {}, 'The paper warns that callback differences may partly reflect who stops applying above a limit, so they are not a clean measure of employer treatment.'),
          h('li', {}, 'The same paper finds a mirror image: younger applicants are less likely to be hired into managerial roles (stated in the abstract; Figure 2c shows the age slope differs by job level).'),
          h('li', {}, 'Lin (2025) measures job loss in census data, not what happens to a reader of one ad; its effect is clear for less-educated workers and not significant for college graduates.'),
          h('li', {}, 'Both studies use real platforms or census data. The AgeLens public demo runs on simulated ads and cannot show effects on unemployment or GDP.'),
          h('li', {}, 'Verification details, access dates and per-claim status: docs/LITERATURE.md, and on the Method and sources page.')))));
  },
});
