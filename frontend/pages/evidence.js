/* Evidence detail: the ad in English (description_en) with the English age sentence highlighted, the extracted conditions
   in plain English (gloss_en), and full traceability back to the import batch and raw row. No Chinese is rendered
   (docs/ENGLISH_UI.md): fields without an English version fall back to a rules-based gloss or "Original wording not shown". */
(function () {
  const h = AgeLens.h;
  const KIND = { max: 'Maximum age', min: 'Minimum age', range: 'Age range', relaxable: 'Relaxable wording', ambiguous: 'Ambiguous wording' };


  function gloss(t) {
    const L = AgeLens.labels;
    const parts = [];
    if (t.kind === 'max') parts.push('Maximum age ' + t.max_age + ' stated.');
    else if (t.kind === 'min') parts.push('Minimum age ' + t.min_age + ' stated.');
    else if (t.kind === 'range') parts.push('Age range ' + t.min_age + ' to ' + t.max_age + ' stated.');
    else if (t.kind === 'relaxable') parts.push('Wording suggests that an age requirement may be relaxed.');
    else parts.push('Age-related wording the rules could not interpret with confidence.');
    const exEn = L.en(t.exception_en);
    if (exEn) parts.push('Possible exception: ' + exEn.replace(/\.$/, '') + '. The ad does not say how exceptions are decided.');
    else if (t.exception_text) parts.push('The ad also has exception wording; it does not say how exceptions are decided.');
    if (t.confidence === 'low') parts.push('Low confidence: read the whole ad before relying on it.');
    return parts.join(' ');
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
      h1.textContent = L.adTitle(ad); h1.className = 'ev-title';
      document.title = 'Evidence ' + ad.id + ' · AgeLens';

      const textEn = L.en(ad.description_en);
      const sents = L.sentences(ad);
      const t0 = terms[0];
      const markTitle = t0 ? (KIND[t0.kind] || 'Age wording') + ' (' + t0.confidence + ' confidence)' : 'Age wording';
      const hl = textEn ? L.highlight(textEn, sents, markTitle) : null;
      const body = textEn
        ? h('div.orig.ad-en', {}, hl.nodes)
        : h('div.problem.soft.ad-missing', { role: 'note' }, h('p', {}, h('strong', {}, 'English text not available yet. '),
          'The ad was written in Chinese and its English version has not been added to this data set, so the full text is not shown here. ',
          'The age conditions below are read from the original text by the rules.'));
      const ageBox = sents.length && !(hl && hl.found) ? h('p.ev-age-sent', {}, h('strong', {}, sents.length > 1 ? 'Age sentences: ' : 'Age sentence: '), sents.map((x, i) => [i ? ' ' : '', h('mark.age', { title: markTitle }, x)])) : null;

      const conds = terms.length ? h('div.terms', {}, terms.map((t) => h('div.term', {},
        h('div.term-top', {}, h('strong', {}, KIND[t.kind] || t.kind), h('span.badge.' + (t.confidence === 'high' ? 'mint' : 'sim'), {}, t.confidence + ' confidence')),
        kv([['In plain English', L.termGloss(t)], ['Minimum age', t.min_age], ['Maximum age', t.max_age], ['Exception', L.exception(t)],
          ['Rule version', t.rule_version], ['Position in the original text', t.start_offset != null ? 'characters ' + t.start_offset + '–' + t.end_offset : null]]))))
        : h('p', {}, 'No explicit age condition detected in this ad’s text' + (ad.rule_version ? ' by rule version ' + ad.rule_version : '') + '. This describes the text only; it does not say how the employer decides.');

      const raw = ad.raw_row && typeof ad.raw_row === 'object' ? Object.keys(ad.raw_row) : [];
      const sel = AgeLens.seeker;
      const pick = sel ? h('button.btn.btn-primary.no-print', { type: 'button', onclick: (e) => { sel.select(ad); e.target.textContent = 'Added to your selection'; e.target.disabled = true; } }, sel.isSelected(ad.id) ? 'Already selected' : 'Add to my selection for review') : null;
      if (pick && sel.isSelected(ad.id)) pick.disabled = true;

      wrap.append(
        h('div.ev-badges', {}, ad.is_demo ? h('span.badge.sim', {}, 'Demo · Synthetic data') : h('span.badge.sky', {}, 'Imported data'), ad.duplicate_count ? h('span.badge', {}, ad.duplicate_count + ' duplicate row(s) merged') : null),
        kv([['Company', ad.company ? L.company(ad) || (ad.is_demo ? 'Fictional company (name not shown in English)' : 'Name not shown in English') : null], ['Occupation', ad.occupation ? L.occ(ad.occupation) : null],
          ['Location', L.place(ad)],
          ['Posted', ad.posted_date || 'not given'], ['Source', ad.source ? L.source(ad.source) : null],
          ['Link', ad.url && /^https?:\/\//i.test(ad.url) ? h('a', { href: ad.url, target: '_blank', rel: 'noopener noreferrer' }, ad.url) : ad.url]]),
        pick,
        h('section.card.ev-sec', {}, h('h2', {}, 'The ad in English'),
          textEn ? h('p.hint', {}, 'English version of the ad text' + (ad.is_demo ? ' (a fictional ad written for this demo)' : '') + '. Highlighted: the age wording the rules found.') : null,
          body, ageBox),
        h('section.card.ev-sec', {}, h('h2', {}, 'Extracted age conditions'), h('p.hint', {}, 'Rules flag wording to interpret. This is not a legal conclusion.'), conds),
        h('section.card.ev-sec', {}, h('h2', {}, 'English gloss (rules-based)'), h('p.hint', {}, 'A mechanical paraphrase of the extracted numbers and wording, produced by code.'),
          terms.length ? h('ul', {}, terms.map((t) => h('li', {}, gloss(t)))) : h('p', {}, 'No age wording to gloss.')),
        h('section.card.ev-sec', {}, h('h2', {}, 'Where this came from'),
          kv([['Ad ID', ad.id], ['Data', ad.is_demo ? 'Demo · Synthetic data (fictional ad)' : 'Imported data'], ['Data version', ad.data_version], ['Import batch', ad.batch_id], ['Source file', ad.filename], ['Source row', ad.raw_row && ad.source_row ? ad.source_row : null], ['Rule version', ad.rule_version], ['Duplicates merged', ad.duplicate_count]]),
          raw.length ? h('p.hint', {}, 'The raw source row (' + raw.length + ' fields) is kept on the server in its original language and is not shown in this English interface.') : null),
        h('p.no-print', {}, h('a', { href: '#/seeker' }, '← Back to your search')));
    },
  };
})();
