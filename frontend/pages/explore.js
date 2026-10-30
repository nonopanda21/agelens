/* AgeLens Explore (#/explore): filters, three SVG charts, server-paginated evidence list. */
(function () {
  const AL = window.AgeLens;
  const h = AL.h;
  const fmt = (n) => (typeof n === 'number' ? n.toLocaleString('en-US') : '–');
  const pct = (a, b) => (b ? Math.round((a / b) * 1000) / 10 + '%' : '–');
  const list = (x) => (Array.isArray(x) ? x : (x && (x.items || x.data || x.provinces || x.rows)) || []);
  const KEYS = ['province', 'occupation', 'age_status', 'max_age_gte', 'max_age_lte', 'date_from', 'date_to'];
  const LB = () => AL.labels || { occ: (v) => v, prov: (v) => v, source: (v) => v, orig: () => null };
  /** English display text for a filter value; the value itself (sent to the API) stays original. */
  const show = (k, v) => (k === 'province' ? LB().prov(v) : k === 'occupation' ? LB().occ(v) : k === 'age_status' ? (STATUS[v] || v) : v);
  const STATUS = { explicit: 'Explicit age wording', uncertain: 'Age wording uncertain', none: 'No age wording detected' };

  AL.loadScript = AL.loadScript || function (src) {
    AL._scripts = AL._scripts || {};
    if (AL._scripts[src]) return AL._scripts[src];
    AL._scripts[src] = new Promise((res, rej) => {
      const t = document.createElement('script');
      t.src = src; t.async = false; t.onload = res;
      t.onerror = () => { delete AL._scripts[src]; rej(new Error('Could not load ' + src)); };
      document.head.appendChild(t);
    });
    return AL._scripts[src];
  };

  function qs(f, omit, extra) {
    const p = new URLSearchParams();
    KEYS.forEach((k) => { if (omit && omit.indexOf(k) >= 0) return; if (f[k] !== '' && f[k] != null) p.set(k, f[k]); });
    Object.keys(extra || {}).forEach((k) => p.set(k, extra[k]));
    const s = p.toString();
    return s ? '?' + s : '';
  }
  function scopeText(f) {
    const parts = [];
    if (f.province) parts.push('province ' + show('province', f.province));
    if (f.occupation) parts.push('occupation ' + show('occupation', f.occupation));
    if (f.age_status) parts.push((STATUS[f.age_status] || f.age_status).toLowerCase());
    if (f.max_age_gte !== '' && f.max_age_lte !== '' && f.max_age_gte === f.max_age_lte) parts.push('stated max age exactly ' + f.max_age_gte);
    else {
      if (f.max_age_gte !== '') parts.push('stated max age at least ' + f.max_age_gte);
      if (f.max_age_lte !== '') parts.push('stated max age at most ' + f.max_age_lte);
    }
    if (f.date_from) parts.push('from ' + f.date_from);
    if (f.date_to) parts.push('to ' + f.date_to);
    return parts.length ? parts.join(' · ') : 'all ads in the default scope';
  }

  /** Compact metadata line, English only: company (when it has an English name), place, occupation, date, source. */
  function metaLine(it) {
    const L = LB(), kids = [], sep = () => (kids.length ? ' · ' : null);
    const add = (...n) => { const s = sep(); if (s) kids.push(s); kids.push(...n.filter((x) => x != null)); };
    const co = L.company ? L.company(it) : null;
    if (co) add(co);
    if (it.province || it.city) add(L.place ? L.place(it) : L.prov(it.province));
    if (it.occupation) add(L.occ(it.occupation));
    if (it.posted_date) add(it.posted_date);
    if (it.source && !it.is_demo) add(L.source(it.source));   // synthetic labelling is shown once per view, not per card
    return h('p.hint.ex-meta', {}, kids);
  }

  AL.pages.explore = {
    title: 'Explore data',
    async render(el, params) {
      const f = {}; KEYS.forEach((k) => { f[k] = (params && params.query && params.query.get(k)) || ''; });
      let page = 1; const PAGE = 15; let sort = 'date_desc';
      let seqCharts = 0, seqList = 0, usingDemo = false, distCtl = null;
      const canonP = AL.api('/api/provinces').then(list).catch(() => []);
      const occP = AL.api('/api/stats/occupations?limit=200').then(list).catch(() => []);

      // ---- controls
      const inp = (id, type, ph, extra) => h('input', Object.assign({ id, type, placeholder: ph || null, autocomplete: 'off' }, extra || {}));
      const fProv = h('select', { id: 'ex-prov' }, h('option', { value: '' }, 'All provinces'));
      const fOcc = h('select', { id: 'ex-occ' }, h('option', { value: '' }, 'All occupations'));
      const fStat = h('select', { id: 'ex-stat' }, h('option', { value: '' }, 'Any'), ['explicit', 'uncertain', 'none'].map((v) => h('option', { value: v }, STATUS[v])));
      const fGte = inp('ex-gte', 'number', 'from', { 'aria-label': 'Stated max age from (years)', min: 16, max: 80, inputmode: 'numeric' });
      const fLte = inp('ex-lte', 'number', 'to', { 'aria-label': 'Stated max age to (years)', min: 16, max: 80, inputmode: 'numeric' });
      const fDf = inp('ex-df', 'date', null, { 'aria-label': 'Ad date from' }); const fDt = inp('ex-dt', 'date', null, { 'aria-label': 'Ad date to' });
      const fld = (label, id, node, hint) => h('div.ex-f', {}, h('label', { for: id }, label), node, hint ? h('span.hint', {}, hint) : null);
      const form = h('form.card.ex-filters', { onsubmit: (e) => { e.preventDefault(); readForm(); changed(); }, 'aria-label': 'Filters' },
        fld('Province', 'ex-prov', fProv), fld('Occupation group', 'ex-occ', fOcc), fld('Age wording', 'ex-stat', fStat),
        h('div.ex-f', { role: 'group', 'aria-labelledby': 'ex-age-l' }, h('label#ex-age-l', {}, 'Stated max age (years)'), h('div.ex-pair', {}, h('span', {}, fGte), h('span', {}, fLte)), h('span.hint', {}, 'e.g. 35 to 35 for exactly 35')),
        h('div.ex-f.ex-dates', { role: 'group', 'aria-labelledby': 'ex-date-l' }, h('label#ex-date-l', {}, 'Ad date range'), h('div.ex-pair', {}, h('span', {}, fDf), h('span', {}, fDt))),
        h('div.ex-f.ex-btns', {}, h('button.btn.btn-primary', { type: 'submit' }, 'Apply'), h('button.btn.btn-quiet', { type: 'button', onclick: () => { KEYS.forEach((k) => { f[k] = ''; }); writeForm(); changed(); } }, 'Reset')));
      [fProv, fOcc, fStat, fGte, fLte, fDf, fDt].forEach((n) => n.addEventListener('change', () => { readForm(); changed(); }));
      function readForm() { f.province = fProv.value; f.occupation = fOcc.value; f.age_status = fStat.value; f.max_age_gte = fGte.value; f.max_age_lte = fLte.value; f.date_from = fDf.value; f.date_to = fDt.value; }
      function writeForm() { fProv.value = f.province; fOcc.value = f.occupation; fStat.value = f.age_status; fGte.value = f.max_age_gte; fLte.value = f.max_age_lte; fDf.value = f.date_from; fDt.value = f.date_to; }

      // ---- output areas
      const demoBadge = h('span.badge.sim', { hidden: true }, 'Demo \u00B7 Synthetic data');
      const listBadge = h('span.badge.sim', { hidden: true }, 'Demo \u00B7 Synthetic data');
      const scopeEl = h('p.ex-scope', { 'aria-live': 'polite' });
      const kpi = h('p.ex-kpi', { 'aria-live': 'polite' });
      const chips = h('div.ex-chips');
      const dHost = h('div.ex-chart'); const pHost = h('div.ex-chart.ex-scroll'); const oHost = h('div.ex-chart.ex-scroll');
      const card = (title, note, host) => h('section.card.ex-card.reveal', {}, h('h3', {}, title), h('p.hint', {}, note), host);
      const listHost = h('div.ex-list'); const pager = h('div.ex-pager');
      const listHead = h('h2', { tabindex: '-1' }, 'Evidence list');
      const sortSel = h('select', { id: 'ex-sort', 'aria-label': 'Sort order' }, [['date_desc', 'Newest first'], ['date_asc', 'Oldest first']].map(([v, t]) => h('option', { value: v }, t)));
      sortSel.addEventListener('change', () => { sort = sortSel.value; page = 1; loadList(); });

      el.append(h('div.wrap.section.ex', {},
        h('div.reveal.in', {}, h('h1', {}, 'Explore the ', h('span.ink-pink', {}, 'evidence'), demoBadge), h('p.lead', {}, 'Filter the imported ads, compare charts, then read each ad’s age wording in plain English. Counts describe the ads in this dataset only. They are not unemployment rates, hiring rates or the chance that anyone is rejected.')),
        form, scopeEl, kpi, chips,
        h('div.ex-charts', {},
          card('Stated maximum age', 'Number of ads per stated upper age limit; 35 is highlighted. Click a column to filter. (Ignores the max-age filter so you can compare.)', dHost),
          card('Provinces', 'Unique ads per province, with explicit-wording share. Click to filter. (Ignores the province filter.)', pHost),
          card('Occupations', 'Unique ads per occupation group. Click to filter. (Ignores the occupation filter.)', oHost)),
        h('div.ex-listhead', {}, h('div.ex-lh', {}, listHead, listBadge), h('div.ex-sort', {}, h('label.hint', { for: 'ex-sort' }, 'Sort'), sortSel)),
        listHost, pager));

      const [canon, occs] = await Promise.all([canonP, occP]);
      if (AL.labels && AL.labels.ready) await AL.labels.ready;
      // English text, original value (the API and the map join use the Chinese canonical names)
      canon.slice().sort((a, b) => (a.en || a.name).localeCompare(b.en || b.name)).forEach((c) => fProv.append(h('option', { value: c.name }, c.en || LB().prov(c.name))));
      occs.map((r) => r.occupation).filter(Boolean).sort((a, b) => LB().occ(a).localeCompare(LB().occ(b))).forEach((o) => fOcc.append(h('option', { value: o }, LB().occ(o))));
      if (f.province && ![...fProv.options].some((o) => o.value === f.province)) fProv.append(h('option', { value: f.province }, LB().prov(f.province)));
      if (f.occupation && ![...fOcc.options].some((o) => o.value === f.occupation)) fOcc.append(h('option', { value: f.occupation }, LB().occ(f.occupation)));
      writeForm();

      function changed() {
        page = 1;
        try { history.replaceState(null, '', '#/explore' + qs(f)); } catch (e) { /* ignore */ }
        refresh();
      }
      function setFilter(patch) { Object.assign(f, patch); writeForm(); changed(); }

      function renderChips() {
        chips.replaceChildren();
        const defs = [['province', 'Province'], ['occupation', 'Occupation'], ['age_status', 'Age wording'], ['max_age_gte', 'Max age ≥'], ['max_age_lte', 'Max age ≤'], ['date_from', 'From'], ['date_to', 'To']];
        defs.forEach(([k, l]) => { if (f[k] !== '') chips.append(h('button.ex-chip', { type: 'button', 'aria-label': 'Remove filter ' + l + ' ' + show(k, f[k]), onclick: () => setFilter({ [k]: '' }) }, l + ': ' + show(k, f[k]) + ' ×')); });
      }

      async function refresh() {
        const my = ++seqCharts;
        renderChips();
        scopeEl.textContent = 'Scope: ' + scopeText(f);
        kpi.replaceChildren(h('span.spinner'), ' Updating…');
        loadList();
        const get = (path, omit) => AL.api(path + qs(f, omit));
        try {
          const [ov, dist, prov, occ] = await Promise.all([get('/api/overview'), get('/api/stats/max-age', ['max_age_gte', 'max_age_lte']), get('/api/stats/provinces', ['province']), get('/api/stats/occupations', ['occupation'])]);
          if (my !== seqCharts) return;
          usingDemo = !!ov.using_demo; demoBadge.hidden = !usingDemo; listBadge.hidden = !usingDemo;
          const total = ov.unique_ads || 0;
          if (!total) {
            kpi.replaceChildren(h('span', {}, 'No ads match this scope. Remove a filter to broaden it.'),
              h('details.ops', {}, h('summary', {}, 'For operators'), h('div', {}, h('p', {}, 'If nothing has been imported yet, run ', h('code', {}, '.venv/bin/python scripts/import_csv.py <file.csv>'), ' (add ', h('code', {}, '--demo'), ' for the labelled sample set).'))));
          } else {
            const den = ov.denominator != null ? ov.denominator : total;
            kpi.replaceChildren(h('strong.pix', {}, fmt(total)), ' unique ads in scope (from ', h('span.tnum', {}, fmt(ov.raw_rows)), ' raw rows). Explicit age wording: ', h('strong.pix', {}, fmt(ov.explicit_count)), ' of ', h('strong.tnum', {}, fmt(den)), ' (', h('span.tnum', {}, pct(ov.explicit_count, den)), ' of these ads).');
          }
          await AL.loadScript('js/charts.js');
          if (my !== seqCharts) return;
          if (distCtl) distCtl.destroy();
          const sel = f.max_age_gte !== '' && f.max_age_gte === f.max_age_lte ? +f.max_age_gte : null;
          distCtl = AL.charts.distribution(dHost, list(dist), { highlight: 35, selected: sel, onSelect: (a) => (sel === a ? setFilter({ max_age_gte: '', max_age_lte: '' }) : setFilter({ max_age_gte: String(a), max_age_lte: String(a) })) });
          const rowSub = (r) => 'explicit wording ' + fmt(r.explicit) + ' of ' + fmt(r.ads) + ' (' + pct(r.explicit, r.ads) + ')';
          AL.charts.bars(pHost, list(prov).filter((r) => r.ads > 0).sort((a, b) => b.ads - a.ads).map((r) => ({ key: r.province, label: LB().prov(r.province), value: r.ads, sub: rowSub(r) })), { selected: f.province || null, onSelect: (k) => setFilter({ province: f.province === k ? '' : k }), empty: 'No provinces in this scope.' });
          AL.charts.bars(oHost, list(occ).filter((r) => r.ads > 0).map((r) => ({ key: r.occupation, label: LB().occ(r.occupation), value: r.ads, sub: rowSub(r) })), { selected: f.occupation || null, onSelect: (k) => setFilter({ occupation: f.occupation === k ? '' : k }), empty: 'No occupations in this scope.' });
          AL.observeReveals(el);
        } catch (e) {
          if (my === seqCharts) kpi.replaceChildren(h('span.notice.error', { role: 'alert' }, 'Could not load statistics: ' + e.message));
        }
      }

      async function loadList() {
        const my = ++seqList;
        listHost.replaceChildren(h('div.card.ex-loading', { role: 'status', 'aria-label': 'Loading ads' }, h('div.skel', { 'aria-hidden': 'true' }, h('i'), h('i'), h('i'))));
        let data;
        try { data = await AL.api('/api/ads' + qs(f, null, { page, page_size: PAGE, sort })); }
        catch (e) { if (my === seqList) { listHost.replaceChildren(h('div.notice.error', { role: 'alert' }, e.message)); pager.replaceChildren(); } return; }
        if (my !== seqList) return;
        const items = list(data.items ? data.items : data);
        const total = data.total != null ? data.total : items.length;
        listHead.textContent = 'Evidence list · ' + fmt(total) + ' ad' + (total === 1 ? '' : 's');
        listHead.classList.add('tnum');
        if (!items.length) {
          listHost.replaceChildren(h('div.card', {}, h('p', {}, 'No ads match: ' + scopeText(f) + '.'), h('p.hint', {}, 'Nothing is silently widened. Remove a filter above to broaden the scope yourself.')));
          pager.replaceChildren(); return;
        }
        listHost.replaceChildren(h('ul.ex-ads', {}, items.map((it) => {
          const t = (it.age_terms && it.age_terms[0]) || null;
          const href = '#/evidence/' + encodeURIComponent(it.id);
          // whole card is clickable (the title link stretches over it); one trailing text link
          return h('li.card.ex-ad', {}, h('div.ex-ad-h', {},
            h('a.ex-ad-t', { href }, LB().adTitle ? LB().adTitle(it) : it.id),
            h('span.ex-stat.st-' + (it.age_status === 'explicit' ? 'exp' : it.age_status === 'uncertain' ? 'unc' : 'none'), {}, STATUS[it.age_status] || it.age_status)),
            metaLine(it),
            t ? h('p.ex-snip', {}, h('mark.age', {}, LB().ageLine(it)), LB().en(t.exception_en) ? h('span.hint', { style: 'display:block' }, 'Exception: ' + LB().en(t.exception_en)) : null)
              : h('p.hint', {}, 'No explicit age condition detected in this text (this does not mean there is no age preference).'),
            h('span.ex-more', { 'aria-hidden': 'true' }, 'View the ad ›'));
        })));
        const pages = Math.max(1, Math.ceil(total / PAGE));
        const go = (p) => { page = p; loadList(); listHead.focus({ preventScroll: false }); };
        if (pages <= 1) { pager.replaceChildren(h('span.hint.tnum', {}, fmt(total) + (total === 1 ? ' ad in scope' : ' ads in scope'))); return; }
        pager.replaceChildren(h('button.btn.btn-quiet', { type: 'button', disabled: page <= 1, onclick: () => go(page - 1) }, 'Previous'),
          h('span.hint.tnum', {}, 'Page ' + page + ' of ' + pages + ' · ' + fmt(total) + ' ads in scope'),
          h('button.btn.btn-quiet', { type: 'button', disabled: page >= pages, onclick: () => go(page + 1) }, 'Next'));
      }

      refresh();
    },
  };
})();
