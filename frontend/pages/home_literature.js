/* Home section "Why it matters" (agent L). Two literature cards: one redrawn figure, one honest "to be verified" state.
   Verification record: docs/LITERATURE.md. Literature motivates age thresholds; it is NOT an evaluation of AgeLens. */
AgeLens.home = AgeLens.home || { sections: [] };
AgeLens.home.sections.push({
  id: 'literature', order: 50,
  async render(el) {
    const h = AgeLens.h;
    const fig = h('div.lit-fig');
    let svgOk = false;
    try {
      const res = await fetch('figures/feng2026_fig1_redrawn.svg');
      if (!res.ok) throw new Error('missing');
      const doc = new DOMParser().parseFromString(await res.text(), 'image/svg+xml');
      const svg = doc.documentElement;
      if (svg.nodeName !== 'svg' || doc.querySelector('parsererror')) throw new Error('bad svg');
      svg.querySelectorAll('script,foreignObject').forEach((n) => n.remove());
      fig.append(document.importNode(svg, true)); svgOk = true;
    } catch (e) {
      fig.append(h('p.hint', { role: 'status' }, 'The figure could not load. Its numbers are in the table below.'));
    }
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

    const lin = h('article.lit-card.pending', {},
      h('div.lit-head', {}, h('h3', {}, '35 as a cliff in China'), h('span.lit-status.todo', {}, 'To be verified')),
      h('p.lit-plain', {}, 'Lin (2025) reports that people just past 35 are more often unemployed because of their employer (abstract: 0.40% rising to 0.54%).'),
      h('div.lit-todo', {}, h('p', {}, h('strong', {}, 'No figure shown. '), 'Only the abstract and metadata were readable. The full text is behind CNKI access, so the figure number, sample and estimate are not confirmed.'),
        h('p', {}, h('strong', {}, 'Needed: '), 'a team member with CNKI access to check the full text and choose the figure to redraw.')),
      h('p.lit-src', {}, 'Source: Lin Wenlian (2025), “Age discrimination causes unemployment: a regression discontinuity design” (Chinese-language article; title translated by the AgeLens team), China Economic Quarterly 25(1): 103–120. DOI ',
        h('a', { href: 'https://doi.org/10.13821/j.cnki.ceq.2025.01.07', target: '_blank', rel: 'noopener' }, '10.13821/j.cnki.ceq.2025.01.07'), '.'));

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
          h('li', {}, 'Both studies concern real platforms or surveys. AgeLens runs on simulated ads only and cannot show effects on unemployment or GDP.'),
          h('li', {}, 'Verification details, access dates and per-claim status: docs/LITERATURE.md, and on the Method and sources page.')))));
  },
});
