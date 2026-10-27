/* Evidence detail: verbatim Chinese text with age spans highlighted by offset, extracted conditions,
   labelled English gloss, and full traceability back to the import batch and raw row. */
(function () {
  const h = AgeLens.h;
  const KIND = { max: 'Maximum age', min: 'Minimum age', range: 'Age range', relaxable: 'Relaxable wording', ambiguous: 'Ambiguous wording' };

  /** Split text into [{text, term|null}] using term offsets; falls back to indexOf(snippet) if offsets are off. */
  function segments(text, terms) {
    const spans = [];
    for (const t of terms) {
      let s = t.start_offset, e = t.end_offset;
      if (!(Number.isInteger(s) && Number.isInteger(e) && e > s && text.slice(s, e) === t.snippet)) {
        const i = t.snippet ? text.indexOf(t.snippet) : -1;
        if (i < 0) { t._unlocated = true; continue; }
        s = i; e = i + t.snippet.length;
      }
      spans.push({ s, e, t });
    }
    spans.sort((a, b) => a.s - b.s || b.e - a.e);
    const out = []; let pos = 0;
    for (const sp of spans) {
      if (sp.s < pos) continue; // overlapping span: already covered by an earlier highlight
      if (sp.s > pos) out.push({ text: text.slice(pos, sp.s) });
      out.push({ text: text.slice(sp.s, sp.e), term: sp.t }); pos = sp.e;
    }
    if (pos < text.length) out.push({ text: text.slice(pos) });
    return out;
  }

  function gloss(t) {
    const parts = [];
    if (t.kind === 'max') parts.push('Maximum age ' + t.max_age + ' stated.');
    else if (t.kind === 'min') parts.push('Minimum age ' + t.min_age + ' stated.');
    else if (t.kind === 'range') parts.push('Age range ' + t.min_age + ' to ' + t.max_age + ' stated.');
    else if (t.kind === 'relaxable') parts.push('Wording suggests that an age requirement may be relaxed.');
    else parts.push('Age-related wording the rules could not interpret with confidence.');
    if (t.exception_text) parts.push(['Possible exception wording: “', h('span.zh-orig', { lang: 'zh-CN' }, t.exception_text), '”. The ad does not say how exceptions are decided.']);
    if (t.confidence === 'low') parts.push('Low confidence: check the original text.');
    return parts.flatMap((p, i) => (i ? [' '] : []).concat(p));
  }

  function kv(rows) {
    return h('dl.kv', {}, rows.filter(([, v]) => v !== null && v !== undefined && v !== '').flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, v.nodeType || Array.isArray(v) ? v : String(v))]));
  }

  AgeLens.pages.evidence = {
    title: 'Evidence',
    async render(el, params) {
      const h1 = h('h1', {}, 'Evidence');
      const wrap = h('div.wrap.section.evidence-page', {}, h('p.no-print', {}, h('a', { href: '#/seeker' }, '← Back to your answer'), ' · ', h('a', { href: '#/explore' }, 'Explore data')), h1);
      el.append(wrap);
      wrap.append(h('div', { role: 'status', 'aria-label': 'Loading the original ad' }, h('div.skel', { 'aria-hidden': 'true' }, h('i'), h('i'), h('i'))));
      let ad;
      try { ad = await AgeLens.api('/api/ads/' + encodeURIComponent(params.id)); }
      catch (e) {
        const gone = /not found/i.test(e.message);
        wrap.lastChild.replaceWith(h('div.problem', { role: 'alert' }, h('h3', {}, gone ? 'This ad was not found' : 'This ad could not be loaded'),
          h('p', {}, gone ? 'It may belong to a data set that is no longer loaded, or the link is wrong. Go back to your answer and open it from the list.' : e.message + (e.status === 0 ? '' : '')),
          gone ? null : h('div.row', {}, h('button.btn.btn-primary', { type: 'button', onclick: () => AgeLens.pages.evidence.render(el.replaceChildren() || el, params) }, 'Try again'))));
        return;
      }
      wrap.lastChild.remove();
      if (AgeLens.labels.ready) await AgeLens.labels.ready;
      const L = AgeLens.labels;
      const terms = ad.age_terms || [];
      h1.textContent = ad.title || '(untitled ad)'; h1.setAttribute('lang', 'zh-CN'); h1.className = 'ev-title';
      document.title = 'Evidence ' + ad.id + ' · AgeLens';

      const text = ad.description || '';
      const body = h('div.orig', { lang: 'zh-CN' }, segments(text, terms).map((s) => s.term
        ? h('mark.age', { title: (KIND[s.term.kind] || 'Age wording') + ' (' + s.term.confidence + ' confidence)' }, s.text) : s.text));
      const unlocated = terms.filter((t) => t._unlocated);

      const conds = terms.length ? h('div.terms', {}, terms.map((t) => h('div.term', {},
        h('div.term-top', {}, h('strong', {}, KIND[t.kind] || t.kind), h('span.badge.' + (t.confidence === 'high' ? 'mint' : 'sim'), {}, t.confidence + ' confidence')),
        kv([['Minimum age', t.min_age], ['Maximum age', t.max_age], ['Original wording', h('span.zh-orig', { lang: 'zh-CN' }, t.snippet)], ['Exception wording', t.exception_text ? h('span.zh-orig', { lang: 'zh-CN' }, t.exception_text) : null],
          ['Rule version', t.rule_version], ['Position in text', t.start_offset != null ? t.start_offset + '–' + t.end_offset : null]]))))
        : h('p', {}, 'No explicit age condition detected in this ad’s text' + (ad.rule_version ? ' by rule version ' + ad.rule_version : '') + '. This describes the text only; it does not say how the employer decides.');

      const raw = ad.raw_row && typeof ad.raw_row === 'object' ? Object.entries(ad.raw_row) : [];
      const sel = AgeLens.seeker;
      const pick = sel ? h('button.btn.btn-primary.no-print', { type: 'button', onclick: (e) => { sel.select(ad); e.target.textContent = 'Added to your selection'; e.target.disabled = true; } }, sel.isSelected(ad.id) ? 'Already selected' : 'Add to my selection for review') : null;
      if (pick && sel.isSelected(ad.id)) pick.disabled = true;

      wrap.append(
        h('div.ev-badges', {}, ad.is_demo ? h('span.badge.sim', {}, 'Demo · Synthetic data') : h('span.badge.sky', {}, 'Imported data'), ad.duplicate_count ? h('span.badge', {}, ad.duplicate_count + ' duplicate row(s) merged') : null),
        kv([['Company', ad.company ? h('span.zh-orig', { lang: 'zh-CN' }, ad.company) : null], ['Occupation', ad.occupation ? [L.occ(ad.occupation), ' ', L.orig(ad.occupation)] : null],
          ['Location', ad.province || ad.city ? [ad.province ? L.prov(ad.province) : 'Region not stated', ' ', L.orig([ad.province, ad.city].filter(Boolean).join(' · '))] : null],
          ['Posted', ad.posted_date || 'not given'], ['Source', ad.source ? [L.source(ad.source), ' ', L.source(ad.source) !== ad.source ? L.orig(ad.source) : null] : null],
          ['Link', ad.url && /^https?:\/\//i.test(ad.url) ? h('a', { href: ad.url, target: '_blank', rel: 'noopener noreferrer' }, ad.url) : ad.url]]),
        pick,
        h('section.card.ev-sec', {}, h('h2', {}, 'Original text'), h('p.hint', {}, 'Verbatim from the source. Highlighted passages are age-related wording found by rules.'), body,
          unlocated.length ? h('p.hint', {}, unlocated.length + ' detected passage(s) could not be located in the text: ' + h('span.zh-orig', { lang: 'zh-CN' }, unlocated.map((t) => t.snippet).join(' | '))) : null),
        h('section.card.ev-sec', {}, h('h2', {}, 'Extracted age conditions'), h('p.hint', {}, 'Rules flag wording to interpret. This is not a legal conclusion.'), conds),
        h('section.card.ev-sec', {}, h('h2', {}, 'English gloss (rules-based)'), h('p.hint', {}, 'A mechanical paraphrase of the extracted wording, not a translation of the whole ad.'),
          terms.length ? h('ul', {}, terms.map((t) => h('li', {}, gloss(t)))) : h('p', {}, 'No age wording to gloss.')),
        h('section.card.ev-sec', {}, h('h2', {}, 'Where this came from'),
          kv([['Ad ID', ad.id], ['Data', ad.is_demo ? 'Demo · Synthetic data (fictional ad)' : 'Imported data'], ['Data version', ad.data_version], ['Import batch', ad.batch_id], ['Source file', ad.filename], ['Source row', ad.raw_row && ad.source_row ? ad.source_row : null], ['Rule version', ad.rule_version], ['Duplicates merged', ad.duplicate_count]]),
          raw.length ? h('details', {}, h('summary', {}, 'Raw source row (' + raw.length + ' fields, original values)'), h('div.zh-orig', { lang: 'zh-CN' }, kv(raw.map(([k, v]) => [k, typeof v === 'string' ? v : JSON.stringify(v)])))) : null),
        h('p.no-print', {}, h('a', { href: '#/seeker' }, '← Back to your search')));
    },
  };
})();
