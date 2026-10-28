/* About: Method and sources (agent L). Plain English, short. Literature status mirrors docs/LITERATURE.md. */
AgeLens.pages.about = {
  title: 'Method and sources',
  render(el) {
    const h = AgeLens.h;
    const sec = (title, ...kids) => h('section.ab-sec', {}, h('h2', {}, title), ...kids);
    const lit = [
      ['Feng, Lefgren, Liu, Platt, Xia (2026), NBER Working Paper 35709', 'https://www.nber.org/papers/w35709', 'Full text read. Figure 1 estimates checked against the PDF and redrawn. Working paper, not peer-reviewed.', 'ok', 'Checked in full text'],
      [['Lin Wenlian (2025), China Economic Quarterly 25(1) ', h('span.zh-orig', { lang: 'zh-CN' }, '(林文炼, 经济学（季刊）)'), ', DOI 10.13821/j.cnki.ceq.2025.01.07'], 'https://doi.org/10.13821/j.cnki.ceq.2025.01.07', 'Full text read (supplied by the team, 2026-10-28). The 0.40% to 0.54% jump at age 35 (Tables 1–2, pp. 108–109) and the ad shares (pp. 105–106) checked against the printed pages; the figure on the home page uses printed values only. Not significant for college graduates (p. 117).', 'ok', 'Checked in full text'],
    ];
    el.append(h('div.wrap.section.ab', {},
      h('h1', {}, 'Method and ', h('span.ink-pink', {}, 'sources')),
      h('p.ab-lead', {}, 'AgeLens helps you read the age wording in a job ad and prepare a question a person can answer. This page says what does the work, what the data is, and what it cannot do.'),
      sec('Who does what',
        h('dl.ab-dl', {},
          h('dt', {}, 'Rules and the database'), h('dd', {}, 'Find ads, pull out the exact age wording, count and compare. These steps are fixed and repeatable.'),
          h('dt', {}, 'A language model'), h('dd', {}, 'Only explains and drafts wording. No model is connected right now, so the app shows ', h('span.badge', {}, 'Template demo'), ' and uses fixed templates. Nothing here claims an AI call happened.'),
          h('dt', {}, 'People'), h('dd', {}, 'A human reviewer gives the final reply. AgeLens never answers for an employer.'))),
      sec('What “simulated data” means',
        h('p', {}, h('span.badge.sim', {}, 'Demo · Synthetic data'), ' Every ad and case you see was generated for this course project. None comes from a real employer or a real person, and the counts say nothing about real job markets. Chinese ad text is kept so the wording can be read as evidence.')),
      sec('Literature behind the idea',
        h('p', {}, 'Both papers were checked before use. Status is stated per source; the full record, with access dates and what could not be read, is in docs/LITERATURE.md.'),
        h('ul.ab-lit', {}, lit.map(([name, href, note, cls, status]) => h('li', {},
          h('a', { href, target: '_blank', rel: 'noopener' }, name), ' ', h('span.lit-status.' + cls, {}, status), h('p.hint', {}, note)))),
        h('p.hint', {}, 'The literature shows why age thresholds matter. It is not an evaluation of AgeLens.')),
      sec('Privacy',
        h('ul', {}, h('li', {}, 'A CV you upload is read in memory to suggest profile fields that you confirm. The file and its text are not stored.'),
          h('li', {}, 'Names, phone numbers and emails are not extracted, and age is never guessed from a CV.'),
          h('li', {}, 'Request codes and owner tokens are kept in your browser so you can come back to your requests.'))),
      sec('Boundaries',
        h('ul', {}, h('li', {}, 'This is not legal advice and gives no legal conclusion about any ad.'),
          h('li', {}, 'It does not make or support hiring decisions. Age wording found in an ad is not a rate of discrimination or rejection.'),
          h('li', {}, 'A classroom-scale study can test whether clarification requests become more usable. It cannot show changes in unemployment or GDP; that would need long-run data.'))),
      h('p.hint', {}, h('a', { href: '#/' }, 'Back to Overview'))));
  },
};
