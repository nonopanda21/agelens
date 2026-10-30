/* Home section "motivation" (order 25, right after "how"): why the problem matters (literature, page-referenced) and why
   AgeLens is built the way it is (design decisions from the team's design pitch). "How" says WHAT the tool does; this
   section says WHY. Figures and detailed numbers live in the "Why it matters" section (home_literature.js, order 50);
   full text with citations: docs/MOTIVATION.md. Verification of every number: docs/LITERATURE.md.
   English only: the ad line is shown in English translation (docs/ENGLISH_UI.md). */
(function () {
  const AL = window.AgeLens, h = AL.h;

  // [decision, because, source]
  const DECISIONS = [
    ['Keep the whole sentence',
      'The meaning sits in the exact wording. A short summary can silently drop “may be relaxed”, and that clause is what a 38-year-old needs to see.',
      'Pitch, slide 3: connect original ad excerpts and make evidence and uncertainty explicit.'],
    ['Separate explicit, exception and unclear',
      'A hard cap, an exception for strong candidates and a soft preference lead to different next steps. Caps are binding in practice, so it matters which one an ad states.',
      'Feng et al. (2026), pp. 10–11; pitch, slide 4: conditions, exceptions, unknowns.'],
    ['Start from the person’s question',
      'The same line reads differently for different people. The pitch’s user asks: “I am 38 with eight years in operations. Does ‘normally under 35; exceptions possible’ rule me out?”',
      'Pitch, slide 2: background, target role and location.'],
    ['Prepare a question, not a verdict',
      'Only the employer knows how its rule is applied. AgeLens never decides eligibility; it lowers the cost of asking a clear, neutral question.',
      'Pitch, slide 4: reduce information and preparation costs.'],
    ['Keep a person in the loop, and claims small',
      'A human reviewer looks at the same evidence. Effects on jobs are untested; a short pilot can only show whether people understand the ad and ask better questions.',
      'Pitch, slides 2–3 (human review) and 5 (claims limited to task outcomes).'],
  ];

  /* ---- two intuitive figures, modelled on the design pitch's first two slides ----
     Pitch slide 2 (the bar chart of upper age limits) becomes "35 is the number employers pick", drawn from our own
     aggregate of real Zhaopin ads (meta.max_age_counts of /api/stats/matrix?source=real; falls back to Lin's printed
     shares). Pitch slide 1 (two regression-discontinuity scatter plots) becomes two "just below vs just above the line"
     pictures using only printed estimates, with a plain-language note on how to read them. */
  const dots = (n, extra, cls) => h('div.mv-dots.' + cls, { 'aria-hidden': 'true' },
    Array.from({ length: n }, (_, i) => h('i' + (i >= n - extra ? '.x' : ''))));
  const ghost = (n, missing) => h('div.mv-dots.sq', { 'aria-hidden': 'true' },
    Array.from({ length: n }, (_, i) => h('i' + (i >= n - missing ? '.gone' : ''))));

  function lineFigure() {
    const col = (label, big, pic) => h('div.mv-col', {}, h('p.mv-col-k', {}, label), h('p.mv-big', {}, big), pic);
    const lin = h('div.mv-panel', { role: 'img', 'aria-label': 'Out of every 10,000 people a few months younger than 35, about 40 had lost a job because the employer ended it; a few months older than 35, about 54.' },
      h('h4', {}, 'Just past 35, more people lose their job'),
      h('p.mv-q', {}, 'Out of every 10,000 working-age people, how many lost a job because the employer ended it?'),
      h('div.mv-pair', {}, col('A few months younger than 35', 'about 40', dots(40, 0, 'c')), col('A few months older than 35', 'about 54', dots(54, 14, 'c'))),
      h('p.mv-take', {}, h('b', {}, '14 more people per 10,000'), ', about a third more, right at the 35 line.'),
      h('p.mv-cite', {}, 'Lin (2025), China Economic Quarterly 25(1), Tables 1–2, pp. 108–109: 0.40% vs 0.54% (+0.14 points, SE 0.059).'),
      h('p.mv-lim', {}, h('b', {}, 'Limit: '), '2015 data. Clear for people with high school or less; not significant for college graduates (p. 117).'));
    const feng = h('div.mv-panel', { role: 'img', 'aria-label': 'For every 100 positive replies to applicants just under an ad’s posted age limit, applicants just over get about 81.' },
      h('h4', {}, 'Just past an ad’s age limit, fewer replies'),
      h('p.mv-q', {}, 'For every 100 positive replies that applicants just under the posted limit receive, how many do applicants just over it receive?'),
      h('div.mv-pair', {}, col('Just under the limit', '100', ghost(100, 0)), col('Just over the limit', 'about 81', ghost(100, 19))),
      h('p.mv-take', {}, h('b', {}, 'About 1 in 5 replies disappears'), ' once you are past the age the ad states. Applications from that age also drop by about 17%.'),
      h('p.mv-cite', {}, 'Feng, Lefgren, Liu, Platt & Xia (2026), NBER WP 35709, Fig. 1, pp. 10–11 (printed estimates; “nearly 20 percent”).'),
      h('p.mv-lim', {}, h('b', {}, 'Limit: '), 'Working paper, not peer-reviewed; one platform. The gap may partly reflect who still applies.'));
    return h('figure.mv-fig.mv-line.reveal', {},
      h('figcaption.mv-fig-t', {}, h('span.mv-fig-n', {}, 'Figure 2'), 'Crossing the line changes what happens'),
      h('div.mv-how', {}, h('b', {}, 'How to read these two pictures. '),
        'Each one compares two groups of people who are almost the same: only a few months apart in age. The one real difference is which side of a line they are on, age 35 or the age written in the ad. When the result jumps exactly at the line, the line itself is the most likely reason. (Economists call this a regression discontinuity design.)'),
      h('div.mv-panels', {}, lin, feng));
  }

  const CAP_AGES = [25, 28, 30, 32, 35, 38, 40, 45, 50];
  function capFigure() {
    const body = h('div.mv-cap-body', {}, h('p.hint', {}, 'Loading…'));
    const cap = h('p.mv-cite');
    const trendBox = h('div.mv-trend-box');
    const title = h('span', {}, '35 is the age limit employers pick most often');  // sharpened below only if the real data shows 45 overtaking
    const fig = h('figure.mv-fig.mv-cap.reveal', {},
      h('figcaption.mv-fig-t', {}, h('span.mv-fig-n', {}, 'Figure 1'), title),
      body, trendBox, cap);
    const draw = (rows, n35share, srcLabel, citeText) => {
      const max = Math.max(...rows.map((r) => r.share));
      const ten = Math.round(n35share * 10);
      body.replaceChildren(
        h('div.mv-cap-grid', {},
          h('div.mv-bars', { role: 'img', 'aria-label': 'Share of ads with an upper age limit, by the limit: ' + rows.map((r) => r.label + ' ' + (100 * r.share).toFixed(1) + '%').join(', ') },
            rows.map((r) => h('div.mv-bar' + (r.hot ? '.hot' : ''), { 'aria-hidden': 'true' },
              h('span.mv-bar-k', {}, r.label), h('span.mv-bar-t', {}, h('span.mv-bar-f', { style: `--w:${(100 * r.share / max).toFixed(1)}%` })),
              h('span.mv-bar-v', {}, (100 * r.share).toFixed(1) + '%')))),
          h('div.mv-ten', {},
            h('p.mv-q', {}, 'Of every 10 ads that set an upper age limit…'),
            h('div.mv-ads', { role: 'img', 'aria-label': 'About ' + ten + ' in 10 say 35.' }, Array.from({ length: 10 }, (_, i) => h('span.mv-adi' + (i < ten ? '.on' : ''), { 'aria-hidden': 'true' }, i < ten ? '35' : '·'))),
            h('p.mv-take', {}, h('b', {}, 'about ' + ten + ' say 35'), ', more than any other age.'))),
        h('p.mv-src-l', {}, srcLabel));
      cap.textContent = citeText;
    };
    // ask first, so a server without the real aggregate never logs a 404 in the console
    AL.api('/api/real/status').then((st) => { if (!st || !st.available) throw new Error('no real data'); return AL.api('/api/stats/matrix?source=real'); }).then((m) => {
      const meta = m.meta || {}, c = meta.max_age_counts, n = meta.ads_with_max_age;
      if (!c || !n) throw new Error('no distribution');
      const by = (a) => +(c[String(a)] || 0) / n;
      const rows = CAP_AGES.map((a) => ({ label: String(a), share: by(a), hot: a === 35 }));
      const ys = Array.isArray(meta.years) ? meta.years : [];
      const years = ys.length ? ys[0] + '–' + ys[ys.length - 1] : String(meta.years || '');
      // the trend matters: 35 is the most common over the whole range, but 45 overtakes it in the latest year
      const byYear = meta.max_age_counts_by_year || {};
      const trend = Object.keys(byYear).sort().map((yr) => {
        const cy = byYear[yr], tot = Object.values(cy).reduce((a, b) => a + b, 0) || 1;
        return [yr, (cy['35'] || 0) / tot, (cy['45'] || 0) / tot];
      });
      if (trend.length) {
        trendBox.replaceChildren(h('p.mv-q', {}, 'Year by year, the share that says 35 is falling, and 45 is rising:'),
          h('table.mv-trend', {}, h('thead', {}, h('tr', {}, h('th', { scope: 'col' }, 'Year'), h('th', { scope: 'col' }, 'Says 35'), h('th', { scope: 'col' }, 'Says 45'))),
            h('tbody', {}, trend.map(([yr, a, b]) => h('tr', { class: b > a ? 'flip' : '' }, h('th', { scope: 'row' }, yr), h('td', {}, (100 * a).toFixed(1) + '%'), h('td', {}, (100 * b).toFixed(1) + '%'))))),
          trend.some(([, a, b]) => b > a) && (title.textContent = '35 is the most common age limit, but 45 is catching up') ? h('p.mv-take', {}, h('b', {}, 'In ' + trend.filter(([, a, b]) => b > a).map((t) => t[0]).join(', ') + ', 45 overtook 35.'), ' The “35 line” is still the most common over the whole period, but it is not fixed.') : null);
      }
      draw(rows, by(35), 'Real data · ' + n.toLocaleString('en-US') + ' Zhaopin job ads posted ' + years + ' that state a maximum age (AgeLens count with fixed rules ' + (meta.rule_version || '') + '; the top of a range such as 18–45 counts as its maximum).',
        'Lin (2025, pp. 105–106) found the same pattern across 59.69 million postings on five Chinese job sites in 2016–2021: about 1 in 5 stated an age limit, and 35 was the most common upper limit on every site (Zhaopin 27.9%).');
    }).catch(() => {
      // no real-data aggregate on this server: Lin's printed shares of 35 among capped ads, 2016–2021 (p. 106)
      draw([{ label: '51job', share: 0.3074, hot: true }, { label: 'Liepin', share: 0.3206, hot: true }, { label: 'Zhaopin', share: 0.2788, hot: true }], 0.30,
        'Share of capped ads whose upper limit is 35, by job site, 2016–2021. Only the printed values are shown.',
        'Lin (2025), China Economic Quarterly 25(1), pp. 105–106, Fig. 1: about 1 in 5 of 59.69 million postings stated an age limit, and 35 was the most common upper limit on every site.');
    });
    return fig;
  }

  /* Theory of change: a plain chain of four steps (an ordered list, so it reads in order without the arrows), what the
     cited studies suggest, what is NOT shown, and one neutral worked example. Studies: docs/LITERATURE.md. */
  function theoryFigure() {
    const STEPS = [
      ['Hard-to-read age wording', 'An ad says “normally under 35; exceptions possible” and does not say what that means.'],
      ['Better interpretation', 'AgeLens reads the ad and lists what is explicit and what is unclear.'],
      ['Cheaper to ask', 'A targeted question is ready to send, so asking takes less effort.'],
      ['Better-informed application decision', 'You decide whether to apply, and what to ask first, knowing more.'],
    ];
    const SUGGESTS = [
      ['Feng et al. (2026): ', 'older applicants can face a disadvantage in entry-level hiring on one Chinese platform, while experience helps in higher-level positions.'],
      ['Lin (2025): ', 'in China, job loss for an employer reason jumps at age 35.'],
      ['Neumark et al. (2019): ', 'in a US experiment, callbacks fall with age, more clearly for women.'],
      ['Burn et al. (2022): ', 'ageist wording in ads lowers the share of applicants over 40.'],
      ['Belot et al. (2019): ', 'in a UK lab study, tailored search information raised interviews for some jobseekers.'],
    ];
    const NOT_SHOWN = [
      'That AgeLens changes interviews, hiring or employment.',
      'That employers answer clarification requests.',
      'That the tool removes a binding age limit. It cannot.',
    ];
    return h('figure.mv-fig.mv-toc.reveal', {},
      h('figcaption.mv-fig-t', {}, h('span.mv-fig-n', {}, 'Figure 3'), 'From clearer reading to a better-informed choice'),
      h('ol.mv-chain', {}, STEPS.map(([t, d], i) => h('li.mv-step', {},
        h('span.mv-step-n', { 'aria-hidden': 'true' }, String(i + 1)), h('b.mv-step-t', {}, t), h('span.mv-step-d', {}, d)))),
      h('p.mv-take', {}, 'Our first claim is limited to ', h('b', {}, 'better decision support'), '. Hiring effects and wider economic effects are left for future evaluation.'),
      h('div.mv-cols', {},
        h('section.mv-colbox.sug', { 'aria-labelledby': 'toc-sug' }, h('h4#toc-sug', {}, 'What the evidence suggests'),
          h('ul', {}, SUGGESTS.map(([a, b]) => h('li', {}, h('b', {}, a), b))),
          h('p.mv-cite', {}, 'These findings motivate our approach but do not establish its effectiveness.')),
        h('section.mv-colbox.not', { 'aria-labelledby': 'toc-not' }, h('h4#toc-not', {}, 'What we have NOT shown'),
          h('ul', {}, NOT_SHOWN.map((t) => h('li', {}, t))))),
      h('aside.mv-example', { 'aria-labelledby': 'toc-ex' },
        h('h4#toc-ex', {}, 'A worked example'),
        h('p', {}, 'A 38-year-old applicant sees “normally under 35; exceptions possible”. AgeLens marks the cap at 35 as explicit and the exception as unclear. It then drafts a neutral question: “Does eight years of operations experience qualify for the advertised exception?”'),
        h('p.mv-cite', {}, 'The employer decides what happens next. The question may get no answer, and the answer may be no.')));
  }

  const toLit = () => {
    const t = document.getElementById('literature');
    if (t) t.scrollIntoView({ behavior: AL.motion && AL.motion.reduced() ? 'auto' : 'smooth', block: 'start' });
  };

  AL.home = AL.home || { sections: [] };
  AL.home.sections.push({ id: 'motivation', order: 25, render(el) {
    const ad = h('figure.mv-ad.reveal', {},
      h('p.mv-ad-k', {}, 'A line from a job ad'),
      h('blockquote.mv-ad-q', {}, h('p', {}, '“Under 35; may be relaxed for outstanding candidates.”')),
      h('figcaption.mv-ad-en', {}, 'English translation of a typical requirement line in a Chinese job ad.'),
      h('ul.mv-tags', { 'aria-label': 'How AgeLens reads it' },
        h('li.mv-tag.t-exp', {}, h('b', {}, 'Explicit: '), 'a cap at 35'),
        h('li.mv-tag.t-exc', {}, h('b', {}, 'Exception: '), 'it may be relaxed'),
        h('li.mv-tag.t-unk', {}, h('b', {}, 'Unclear: '), 'what counts as outstanding, and who decides')));

    el.append(h('div.wrap.xs.mv', {},
      h('div.xs-head.reveal', {}, h('h2', {}, 'The motivation'),
        h('p', {}, 'Many Chinese job ads put an age in the requirements. For someone in their late 30s, one short line can decide whether they apply at all. This is why we built AgeLens, and why it works the way it does.')),

      // 1 · the problem
      h('div.mv-block.mv-problem', {},
        h('div.mv-copy.reveal', {},
          h('h3.mv-h', {}, h('span.xc-n', {}, '01'), 'The problem'),
          h('p', {}, 'High earnings in mid-career can go together with real difficulty getting a new job. AgeLens is for workers who are changing jobs or returning to work.'),
          h('p', {}, 'Age limits in Chinese recruitment are common, and 35 is the usual number. Many ads soften the cap with an exception, but rarely say what the exception means.'),
          h('p', {}, 'Mid-career job seekers in engineering, operations, sales and professional services are left to guess. Some may rule themselves out of jobs they could get; others apply without knowing where they stand.')),
        ad),

      // 2 · the literature
      h('h3.mv-h.reveal', {}, h('span.xc-n', {}, '02'), 'What the research shows'),
      capFigure(), lineFigure(),
      h('p.mv-note.reveal', {}, 'Neither study tells us whether a given ad’s exception will be applied to a given person, and neither evaluates a tool like AgeLens. ',
        h('button.mv-jump', { type: 'button', onclick: toLit }, 'See the redrawn figures below'), '.'),

      // 3 · the gap
      h('h3.mv-h.reveal', {}, h('span.xc-n', {}, '03'), 'The gap'),
      h('div.mv-gap.reveal', {},
        h('div.mv-gap-col', {}, h('h4', {}, 'What existing tools do'),
          h('ul', {},
            h('li', {}, h('b', {}, 'Textio, Applied: '), 'help employers write fairer ads, for example by flagging age-related wording for the writer.'),
            h('li', {}, h('b', {}, 'Job boards and resume tools: '), 'help seekers find jobs, set alerts or match keywords.'))),
        h('div.mv-gap-arrow', { 'aria-hidden': 'true' }, '→'),
        h('div.mv-gap-col.need', {}, h('h4', {}, 'What the reader of one ad needs'),
          h('ul', {},
            h('li', {}, 'What this ad’s age line actually says, in its own words.'),
            h('li', {}, 'Which part is a rule, an exception or simply unknown, for their own background.'),
            h('li', {}, 'A clear question to send the employer before deciding.')))),

      // 4 · theory of change
      h('h3.mv-h.reveal', {}, h('span.xc-n', {}, '04'), 'How we expect it to help'),
      theoryFigure(),

      // 5 · design decisions
      h('h3.mv-h.reveal', {}, h('span.xc-n', {}, '05'), 'Why AgeLens is designed this way'),
      h('div.mv-dec', {}, DECISIONS.map(([t, b, s], i) => h('article.xc.mv-dec-card.reveal', { style: `--d:${i * 60}ms` },
        h('h4.xc-title', {}, t), h('p', {}, h('b', {}, 'Because: '), b), h('p.mv-src', {}, s)))),

      h('div.mv-foot.reveal', {},
        h('p', {}, h('b', {}, 'Where it stands today. '), 'AgeLens reads ads with fixed rules; no AI model is connected. The statistics and the map summarise about 10 million real Zhaopin job ads (2021–2024, counts only); the ads you can open are simulated. Whether it improves job outcomes has not been tested.'),
        h('a.xbtn.xbtn-2', { href: '#/about' }, 'Method and sources', h('span.xarrow', { 'aria-hidden': 'true' }, '→')))));
  } });
})();
