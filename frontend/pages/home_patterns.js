/* Findings section "patterns" (order 20, after the headline cards): how STATED age requirements vary across real Zhaopin ads, by required experience,
   occupation group and explicit gender requirements. Data: GET /api/stats/hetero?source=real (contract: docs/HETERO_CONTRACT.md).
   Renders nothing until that endpoint answers (the 404 is caught quietly). Counts of how ads are worded, not hiring, rejection or pay.
   Every bar has at least MIN ads behind it; smaller groups are listed in a note, not drawn. */
(function () {
  const AL = window.AgeLens, h = AL.h;
  const MIN = 5000;
  const fmt = (n) => n.toLocaleString('en-US');
  const pct = (x) => (100 * x).toFixed(1) + '%';
  // single-sex requirements are rare (a few per 10,000 ads), so a percentage would round to 0.0%
  const p10k = (x) => (10000 * x).toFixed(1) + ' per 10,000 ads';
  const p10kShort = (x) => (10000 * x).toFixed(1) + ' / 10k';  // bar labels: the column is narrow
  const sh = (a, n) => (n ? a / n : 0);
  const EXPLICIT_G = ['male_only', 'female_only', 'male_preferred', 'female_preferred'];
  const DATA_NOTE = 'Zhaopin job ads, 2021–2024. These are counts of how ads are worded. They are not hiring, rejection or pay.';

  // one chart: headline, "how to read", rows of bars, a legend, a count table, the dataset note
  function chart({ id, title, headline, how, series, rows, note, legend, val = pct, short = val }) {
    const max = Math.max(0.0001, ...rows.flatMap((r) => series.map((s) => r[s.key])));
    const bars = h('div.pt-rows', { role: 'list' }, rows.map((r) => h('div.pt-row', { role: 'listitem', title: r.label + ': ' + fmt(r.ads) + ' ads' },
      h('span.pt-k', {}, r.label, h('small', {}, fmt(r.ads) + ' ads')),
      h('span.pt-bars', {}, series.map((s) => h('span.pt-line', {},
        h('span.pt-track', { 'aria-hidden': 'true' }, h('span.pt-fill.' + s.cls, { style: `--w:${(100 * r[s.key] / max).toFixed(1)}%` })),
        h('span.pt-v', {}, short(r[s.key]), h('span.vh', {}, ' ' + s.name))))))));
    const table = h('details.pt-tab', {}, h('summary', {}, 'Show the counts as a table'),
      h('div.pt-scroll', {}, h('table', {}, h('caption.vh', {}, title),
        h('thead', {}, h('tr', {}, h('th', { scope: 'col' }, 'Group'), h('th', { scope: 'col' }, 'Ads'), series.map((s) => h('th', { scope: 'col' }, s.name + ' (share)')))),
        h('tbody', {}, rows.map((r) => h('tr', {}, h('th', { scope: 'row' }, r.label), h('td', {}, fmt(r.ads)), series.map((s) => h('td', {}, val(r[s.key])))))))));
    return h('figure.mv-fig.pt-fig' + (short !== pct ? '.pt-wide' : ''), { id },
      h('figcaption.mv-fig-t', {}, title),
      h('p.pt-head', {}, headline),
      h('p.mv-how.pt-how', {}, h('b', {}, 'How to read this. '), how),
      legend ? h('ul.pt-legend', {}, series.map((s) => h('li', {}, h('i.pt-sw.' + s.cls, { 'aria-hidden': 'true' }), s.name))) : null,
      bars, table, note ? h('p.pt-note', {}, note) : null, h('p.mv-cite', {}, DATA_NOTE));
  }

  const rowOf = (label, o) => ({ label, ads: o.ads, any: sh(o.age_wording, o.ads), cap: sh(o.cap, o.ads) });
  const SER2 = [{ key: 'any', name: 'Any age wording', cls: 'a' }, { key: 'cap', name: 'States a maximum age', cls: 'c' }];

  function extremes(rows, key, what, val = pct) {
    if (rows.length < 2) return '';
    const s = rows.slice().sort((x, y) => y[key] - x[key]), hi = s[0], lo = s[s.length - 1];
    return `${what} is highest for ${hi.label} (${val(hi[key])}) and lowest for ${lo.label} (${val(lo[key])}).`;
  }

  function build(d) {
    const meta = d.meta || {};
    const bands = meta.experience_bands || (d.by_experience || []).map((r) => r.band);
    const small = [];
    const byExp = (d.by_experience || []).filter((r) => (r.ads >= MIN ? true : (small.push(r.band), false)));
    const expRows = byExp.map((r) => rowOf(r.band, r));
    const figA = chart({
      id: 'pt-exp', title: 'Age wording by required experience',
      headline: extremes(expRows.filter((r) => r.label !== 'Not stated'), 'any', 'The share of ads with any age wording') || 'Age wording by required experience.',
      how: 'Each group is the ads that ask for that much experience. A purple bar is the share of those ads with any age wording. A pink striped bar is the share that state a maximum age.',
      series: SER2, rows: expRows, legend: true,
      note: small.length ? 'Not drawn, fewer than ' + fmt(MIN) + ' ads: ' + small.join(', ') + '.' : null });

    // (b) occupations inside one band
    const sel = h('select#pt-band', {}, bands.filter((b) => byExp.some((r) => r.band === b)).map((b) => h('option', { value: b }, b)));
    const holder = h('div.pt-holder', { 'aria-live': 'polite' });
    const draw = () => {
      const b = sel.value;
      const all = (d.by_experience_occupation || []).filter((r) => r.band === b);
      const rows = all.filter((r) => r.ads >= MIN).sort((x, y) => sh(y.age_wording, y.ads) - sh(x.age_wording, x.ads)).map((r) => rowOf(r.occupation, r));
      const hidden = all.length - rows.length;
      holder.replaceChildren(rows.length < 2
        ? h('p.hint', { role: 'status' }, 'Fewer than two occupation groups have at least ' + fmt(MIN) + ' ads in this group, so no comparison is drawn.')
        : chart({ id: 'pt-occ', title: 'Occupation groups: ads asking for “' + b + '”',
          headline: extremes(rows, 'any', 'Among ads asking for ' + b.toLowerCase() + ', the share with any age wording') ,
          how: 'Pick a group of required experience. Each bar is an occupation group inside it. Bars are sorted from most to least age wording.',
          series: SER2, rows, legend: true,
          note: hidden > 0 ? hidden + ' occupation group' + (hidden > 1 ? 's' : '') + ' with fewer than ' + fmt(MIN) + ' ads here ' + (hidden > 1 ? 'are' : 'is') + ' not drawn.' : null }));
    };
    sel.addEventListener('change', draw);
    if (bands.includes('1–3 years') && byExp.some((r) => r.band === '1–3 years')) sel.value = '1–3 years';
    draw();
    const figB = h('div.pt-b', {}, h('div.pt-pick', {}, h('label', { for: 'pt-band' }, 'Required experience'), sel), holder);

    // (c) gender
    const g = d.gender || {};
    const gShare = (r) => EXPLICIT_G.reduce((a, k) => a + (r[k] || 0), 0);
    const gRow = (label, r) => ({ label, ads: r.ads, st: sh(gShare(r), r.ads) });
    const occG = (g.by_occupation || []).filter((r) => r.ads >= MIN).sort((a, b) => b.ads - a.ads).slice(0, 8).map((r) => gRow(r.occupation, r));
    const expG = (g.by_experience || []).filter((r) => r.ads >= MIN).map((r) => gRow(r.band, r));
    const S1 = [{ key: 'st', name: 'States a gender requirement', cls: 'g' }];
    const figC1 = occG.length ? chart({ id: 'pt-gocc', title: 'Gender requirements by occupation group',
      headline: extremes(occG, 'st', 'Among the 8 largest occupation groups, stating a gender requirement', p10k),
      how: 'Each bar is how many ads in that group name a gender they want, either “only” or “preferred”. Ads that say “men and women welcome” do not count. Such requirements are rare, so the bars are scaled to the largest value in this chart.',
      series: S1, rows: occG, val: p10k, short: p10kShort }) : null;
    const figC2 = expG.length ? chart({ id: 'pt-gexp', title: 'Gender requirements by required experience',
      headline: extremes(expG.filter((r) => r.label !== 'Not stated'), 'st', 'Stating a gender requirement', p10k),
      how: 'Same measure as above, grouped by how much experience the ad asks for. Bars are scaled to the largest value in this chart.', series: S1, rows: expG, val: p10k, short: p10kShort }) : null;

    const ag = g.age_by_gender || [];
    const one = (c) => ag.find((r) => r.gender_class === c);
    const sum = (cs) => { const rs = cs.map(one).filter(Boolean); const t = { ads: 0, age_wording: 0, cap: 0 }; rs.forEach((r) => { t.ads += r.ads; t.age_wording += r.age_wording; t.cap += r.cap; }); return t; };
    const ageG = [['Ads that state a gender requirement', sum(EXPLICIT_G)], ['Ads that say gender does not matter', sum(['no_limit'])], ['Ads with no gender wording', sum(['none'])]]
      .filter(([, o]) => o.ads >= MIN).map(([l, o]) => rowOf(l, o));
    const first = ageG.find((r) => r.label.startsWith('Ads that state')), last = ageG.find((r) => r.label.startsWith('Ads with no'));
    const figC3 = ageG.length ? chart({ id: 'pt-gage', title: 'Age wording in ads with and without a gender requirement',
      headline: first && last ? `Age wording appears in ${pct(first.any)} of ads that state a gender requirement and in ${pct(last.any)} of ads with no gender wording.` : 'Age wording by gender wording.',
      how: 'Each group is a type of gender wording. The bars show how many of its ads also have age wording. The two kinds of wording appear together or apart in ads. This does not say why.',
      series: SER2, rows: ageG, legend: true }) : null;
    const gSet = [figC1, figC2, figC3].filter(Boolean);

    return h('div.wrap.xs.mv.pt', {},
      h('div.xs-head.reveal', {}, h('h2', {}, 'How age requirements vary across ads'),
        h('p', {}, 'Age wording is not the same in every ad. It differs with the experience an ad asks for, the occupation, and whether the ad also names a gender. These are patterns in how ads are written. They do not show who gets hired.'),
        h('p.hint', {}, 'Based on ' + fmt(meta.rows_used || 0) + ' Zhaopin ads (including ads whose city could not be placed in a province), ' + (Array.isArray(meta.years) && meta.years.length ? meta.years[0] + '–' + meta.years[meta.years.length - 1] : '2021–2024') + '. Groups with fewer than ' + fmt(MIN) + ' ads are not drawn.')),
      h('h3.mv-h', {}, h('span.xc-n', {}, 'A'), 'By experience'), figA,
      h('h3.mv-h', {}, h('span.xc-n', {}, 'B'), 'By occupation'), figB,
      gSet.length ? h('h3.mv-h', {}, h('span.xc-n', {}, 'C'), 'Gender requirements') : null, ...gSet,
      h('p.mv-note', {}, 'AgeLens reads each ad with fixed rules, and the rules make mistakes (see Method and sources). Some wording is read wrongly.'));
  }

  // memoised: the hetero data, or null when the server does not have it (used by the section and by the data tiles / footer / FAQ wording)
  AL.heteroData = function () {
    if (!AL._heteroP) AL._heteroP = AL.api('/api/real/status').then((st) => (st && st.available && st.hetero ? AL.api('/api/stats/hetero?source=real') : null))
      .then((d) => (d && Array.isArray(d.by_experience) && d.by_experience.length ? d : null)).catch(() => null);
    return AL._heteroP;
  };
  AL.home = AL.home || { sections: [] };
  AL.home.sections.push({ id: 'patterns', order: 20, page: 'findings', rail: 'By experience and gender', async render(el) {
    try {
      const d = await AL.heteroData();
      if (d) el.append(build(d));
    } catch (e) { /* the endpoint is not there yet: show nothing */ }
  } });
})();
