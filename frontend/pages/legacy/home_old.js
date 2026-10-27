/* AgeLens Home (#/): hero, data overview, province map, motivation, 3 steps, boundaries. */
(function () {
  const AL = window.AgeLens;
  const h = AL.h;
  const fmt = (n) => (typeof n === 'number' ? n.toLocaleString('en-US') : '–');
  const pct = (a, b) => (b ? Math.round((a / b) * 1000) / 10 + '%' : '–');
  const list = (x) => (Array.isArray(x) ? x : (x && (x.items || x.data || x.provinces || x.rows)) || []);

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

  function countUp(node, to) {
    const text = fmt(to);
    if (AL.reducedMotion() || !(to > 0)) { node.textContent = text; return; }
    const t0 = performance.now(), dur = 900;
    function step(now) {
      const k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      node.textContent = k < 1 ? fmt(Math.round(to * e)) : text;
      if (k < 1 && node.isConnected) requestAnimationFrame(step); else node.textContent = text;
    }
    requestAnimationFrame(step);
  }

  /* ---------- Hero ---------- */
  function hero() {
    const d = (n) => ({ style: '--d:' + n + 'ms' });
    const paper = h('div.hm-layer.hm-l1', {},
      h('div.hm-paper.hm-in', d(250),
        h('div.hm-paper-h', {}, h('span', {}, '招聘启事'), h('span.hm-chip', {}, '示例 · sample')),
        h('p.hm-paper-t', { lang: 'zh-CN' }, '运营专员（上海）'),
        h('ol.hm-paper-l', { lang: 'zh-CN' },
          h('li', {}, '本科及以上学历，3年以上运营经验；'),
          h('li.hm-focus', {}, h('span.hm-focus-ring', { 'aria-hidden': 'true' }), '年龄', h('mark.age', {}, '35岁以下，条件优秀者可适当放宽'), '；'),
          h('li', {}, '熟悉数据分析，沟通能力强。')),
        h('div.hm-skel', { 'aria-hidden': 'true' }, h('i'), h('i'), h('i'))));
    const callout = h('div.hm-layer.hm-l2', {}, h('div.hm-callout.hm-in', d(900),
      h('span.hm-lens', { 'aria-hidden': 'true' }),
      h('div', {}, h('strong', {}, 'Evidence callout'),
        h('p', {}, 'The age clause is quoted verbatim. Rules-based English gloss: ', h('em', {}, '"age under 35; may be relaxed for strong candidates."')))));
    const tl = h('div.hm-layer.hm-l3', {}, h('div.hm-tl.hm-in', Object.assign(d(1300), { role: 'img', 'aria-label': 'Illustrative timeline from age 22 to 50 with a marker at 35 in the ad wording and a longer experience bar' }),
      h('div.hm-tl-bar', { 'aria-hidden': 'true' }, h('span.hm-tl-exp'), h('span.hm-tl-35')),
      h('div.hm-tl-labels', { 'aria-hidden': 'true' }, h('span', {}, '22'), h('span.hm-tl-l35', {}, '35 in the ad wording'), h('span', {}, '50')),
      h('p.hm-tl-cap', { 'aria-hidden': 'true' }, 'Experience on one side, wording on the other: AgeLens helps you read the gap.')));
    const vis = h('div.hm-visual', { role: 'group', 'aria-label': 'Illustration: a recruitment ad with the age clause highlighted' }, paper, callout, tl,
      h('p.hm-illus', {}, 'Illustrative sample, not a real ad or real data.'));
    if (!AL.reducedMotion()) {
      const root = vis;
      root.addEventListener('pointermove', (e) => {
        const r = root.getBoundingClientRect();
        root.style.setProperty('--px', (((e.clientX - r.left) / r.width) * 2 - 1).toFixed(3));
        root.style.setProperty('--py', (((e.clientY - r.top) / r.height) * 2 - 1).toFixed(3));
      });
      root.addEventListener('pointerleave', () => { root.style.setProperty('--px', 0); root.style.setProperty('--py', 0); });
    }
    return h('section.hm-hero', { 'aria-labelledby': 'hm-h1' }, h('div.wrap.hm-hero-in', {},
      h('div.hm-copy', {},
        h('p.hm-eyebrow.hm-in', d(0), 'Age-related hiring wording, as evidence'),
        h('h1.hm-in', Object.assign({id:'hm-h1'}, d(80)), 'Read what the ad actually says about age.'),
        h('p.hm-lead.hm-in', d(160), 'Share your background and a specific question. AgeLens finds recruitment ads in its dataset, quotes the age wording in the original Chinese, separates what is explicit from what is uncertain, and helps you prepare questions for a human reviewer.'),
        h('div.hm-cta.hm-in', d(240), h('a.btn.btn-primary', { href: '#/seeker' }, 'Ask about my situation'), h('a.btn.btn-secondary', { href: '#/explore' }, 'Explore the evidence'))),
      vis));
  }

  /* ---------- Overview ---------- */
  function tile(label, valueNode, sub, cls) {
    return h('div.card.hm-tile.reveal' + (cls ? '.' + cls : ''), {}, h('p.hm-tl-label', {}, label), h('p.hm-tl-value', {}, valueNode), h('p.hint.hm-tl-sub', {}, sub));
  }
  function emptyState(host, demoCmd) {
    host.replaceChildren(h('div.card.hm-empty', {},
      h('h3', {}, 'No ad data has been imported yet'),
      h('p', {}, 'The dashboard stays empty on purpose: AgeLens does not invent numbers. Import a recruitment CSV to fill it, or load the clearly labelled demo set to try the pages.'),
      h('pre.hm-code', {}, '.venv/bin/python scripts/import_csv.py path/to/ads.csv\n.venv/bin/python scripts/import_csv.py data/demo/demo_ads.csv --demo'),
      h('p.hint', {}, 'Demo rows are flagged and never mixed into real statistics.')));
  }
  function renderOverview(host, ov) {
    const total = ov.unique_ads || 0;
    if (!total) return emptyState(host);
    const den = ov.denominator != null ? ov.denominator : total;
    const nums = [];
    const cnt = (n) => { const s = h('span', {}, '0'); nums.push([s, n]); return s; };
    const range = ov.date_min ? (ov.date_min === ov.date_max ? ov.date_min : ov.date_min + ' to ' + ov.date_max) : 'No usable dates';
    const top = (ov.top_max_ages || []).slice(0, 4);
    const tiles = [
      tile('Unique ads', cnt(total), fmt(ov.raw_rows) + ' raw rows, ' + fmt(ov.duplicates != null ? ov.duplicates : Math.max(0, (ov.raw_rows || 0) - total)) + ' duplicates folded together'),
      tile('Provinces covered', cnt(ov.provinces || 0), 'of 34 province-level units · ' + fmt(ov.occupations || 0) + ' occupation groups'),
      tile('Ad dates', h('span.hm-small', {}, range), 'Posting dates found in the data; ads with no date are not counted here'),
      tile('Explicit age wording', h('span', {}, pct(ov.explicit_count, den)), fmt(ov.explicit_count) + ' of ' + fmt(den) + ' unique ads state an age condition in the text; ' + fmt(ov.uncertain_count) + ' are uncertain, ' + fmt(ov.none_count) + ' show none detected. This is a share of these ads, not of the job market.'),
      tile('Most common stated limits', top.length ? h('ul.hm-top', {}, top.map((t) => h('li', {}, h('strong', {}, 'under ' + t.age), ' · ' + fmt(t.count) + ' of ' + fmt(den) + ' ads'))) : h('span.hm-small', {}, 'None stated'), 'Counts of ads whose stated maximum age equals each value'),
    ];
    host.replaceChildren(h('div.hm-tiles', {}, tiles));
    AL.observeReveals(host);
    nums.forEach(([n, v]) => countUp(n, v)); // once, after real data arrived
  }

  /* ---------- Map section ---------- */
  function mapSection(state) {
    const side = h('aside.card.hm-side', { 'aria-live': 'polite' }, h('h3', {}, 'Province details'), h('p.hint', {}, 'Select a province on the map or in the region list to see its ads.'));
    const mapHost = h('div.hm-maphost', {}, h('p.hint', {}, h('span.spinner', {}), ' Loading map…'));
    let view = null, rowsCache = [], canonCache = [], seq = 0;

    async function showProvince(name) {
      side.replaceChildren(h('h3', {}, name), h('p.hint', {}, h('span.spinner'), ' Loading ads…'));
      const my = ++seq;
      let data;
      try { data = await AL.api('/api/ads?province=' + encodeURIComponent(name) + '&page_size=5'); }
      catch (e) { if (my === seq) side.replaceChildren(h('h3', {}, name), h('div.notice.error', {}, e.message)); return; }
      if (my !== seq) return;
      const r = rowsCache.find((x) => x.province === name);
      const items = list(data.items ? data.items : data);
      const kids = [h('h3', {}, name, state.usingDemo ? h('span.badge.demo', { style: 'margin-left:8px' }, 'Demo data') : null)];
      if (r && r.ads) {
        kids.push(h('p', {}, h('strong', {}, fmt(r.ads)), ' unique ads in this province. Explicit age wording: ', h('strong', {}, fmt(r.explicit) + ' of ' + fmt(r.ads)), ' (' + pct(r.explicit, r.ads) + ').'));
        if (r.median_max_age != null) kids.push(h('p.hint', {}, 'Median stated maximum age: ' + r.median_max_age + ' (among ads that state one).'));
      } else kids.push(h('p', {}, 'No ads from this province in the current scope.'));
      if (items.length) {
        kids.push(h('p.hint', {}, 'Latest ' + items.length + ' of ' + fmt(data.total != null ? data.total : items.length) + ' ads:'));
        kids.push(h('ul.hm-adlist', {}, items.map((it) => {
          const t = (it.age_terms && it.age_terms[0]) || null;
          return h('li', {}, h('a', { href: '#/evidence/' + encodeURIComponent(it.id) }, it.title || it.id),
            h('span.hint', {}, [it.company, it.city, it.posted_date].filter(Boolean).join(' · ')),
            t ? h('span.hm-snip', { lang: 'zh-CN' }, '“', h('mark.age', {}, t.snippet), '”') : h('span.hint', {}, 'No explicit age wording detected (this is not a finding of no age preference).'));
        })));
      }
      kids.push(h('div.hm-sidebtns', {}, h('a.btn.btn-primary', { href: '#/explore?province=' + encodeURIComponent(name) }, 'Open in Explore'), h('button.btn.btn-quiet', { type: 'button', onclick: () => select(null) }, 'Clear selection')));
      side.replaceChildren.apply(side, kids);
    }
    function select(name) {
      state.selected = name;
      if (view) view.update({ selected: name });
      if (name) showProvince(name); else { seq++; side.replaceChildren(h('h3', {}, 'Province details'), h('p.hint', {}, 'Select a province on the map or in the region list to see its ads.')); }
    }
    async function init() {
      try {
        await AL.loadScript('js/map.js');
        const [pr, canon] = await Promise.all([AL.api('/api/stats/provinces'), AL.api('/api/provinces').catch(() => [])]);
        rowsCache = list(pr); canonCache = list(canon);
        if (!rowsCache.length) { mapHost.replaceChildren(h('p.notice', {}, 'No province data yet. Import ads (see the overview above) to colour the map.')); if (canonCache.length) { view = AL.mapView(mapHost, { onSelect: select }); view.update({ rows: [], canon: canonCache, selected: null, scopeLabel: 'no data imported', usingDemo: false }); mapHost.prepend(h('p.notice', {}, 'No province data yet. Import ads (see the overview above) to colour the map; all regions are shown as no data.')); } return; }
        view = AL.mapView(mapHost, { onSelect: select });
        view.update({ rows: rowsCache, canon: canonCache, selected: null, scopeLabel: state.usingDemo ? 'demo ads, all provinces' : 'all imported ads', usingDemo: state.usingDemo });
      } catch (e) { mapHost.replaceChildren(h('div.notice.error', { role: 'alert' }, 'Map could not load: ' + e.message)); }
    }
    const sec = h('section.hm-sec.wrap.section.reveal', { id: 'map' },
      h('div.hm-sec-h', {}, h('h2', {}, 'Where the ads come from'), h('p.hint', {}, 'Province-level map of the unique ads in the dataset. Colour shows the ad count; it says nothing about how many people are looking for work or how many are hired.')),
      h('div.hm-mapgrid', {}, h('div.card.hm-mapcard', {}, mapHost), side));
    return { node: sec, init };
  }

  function steps() {
    const st = [['1', 'Share your background', 'Age, occupation, years of experience and a specific question. Drop in a CV if you like; you confirm every extracted field.'], ['2', 'Explore relevant evidence', 'See matching ads with the original Chinese age wording quoted, and what stays uncertain.'], ['3', 'Get a clearer next step', 'An evidence brief with neutral questions to ask, and an optional request to a human reviewer.']];
    return h('section.wrap.section.reveal', { 'aria-labelledby': 'hm-steps' }, h('h2', Object.assign({id:'hm-steps'}, {}), 'Three steps'),
      h('ol.hm-steps', {}, st.map(([n, t, d]) => h('li.card.hoverable', {}, h('span.hm-num', { 'aria-hidden': 'true' }, n), h('h3', {}, t), h('p', {}, d)))));
  }

  AL.pages.home = {
    title: 'Overview',
    render(el) {
      const ovHost = h('div.hm-ovhost', {}, h('p.hint', {}, h('span.spinner'), ' Loading data overview…'));
      const demoBadge = h('span.badge.demo', { hidden: true, style: 'margin-left:10px' }, 'Demo data');
      const state = { usingDemo: false, selected: null };
      const ms = mapSection(state);
      el.append(hero(),
        h('section.wrap.section.hm-ov', { 'aria-labelledby': 'hm-ov-h' },
          h('div.hm-sec-h.reveal', {}, h('h2', Object.assign({id:'hm-ov-h'}, {}), 'The data at a glance', demoBadge), h('p.hint', {}, 'Every ratio shows its numerator and denominator. "Unique ads" are de-duplicated; raw rows are the original CSV lines.')),
          ovHost),
        ms.node,
        h('section.wrap.section.reveal', { 'aria-labelledby': 'hm-mot' },
          h('div.hm-mot', {}, h('h2', Object.assign({id:'hm-mot'}, {}), 'Why this exists'),
            h('div', {}, h('p', {}, 'Many experienced people in their thirties and beyond meet job ads that mention an age limit, sometimes with a softer clause such as "may be relaxed". It is hard to tell which wording is a firm condition, which is ambiguous, and what is worth asking about.'),
              h('p', {}, 'AgeLens does not score you or predict outcomes. It organises the wording of real ads as evidence you can read, quote and bring to a conversation.')))),
        steps(),
        h('section.wrap.section.reveal', { 'aria-labelledby': 'hm-bd' }, h('div.card.hm-bound', {},
          h('h2', Object.assign({id:'hm-bd'}, {}), 'What AgeLens is not'),
          h('ul', {}, h('li', {}, 'Not a legal conclusion: highlighted wording is observed text to interpret, not a finding about any employer.'),
            h('li', {}, 'Not a hiring decision, hire rate, or prediction of whether you would be rejected.'),
            h('li', {}, 'Statistics describe the imported ads only, not the whole job market.')),
          h('div.hm-cta', {}, h('a.btn.btn-primary', { href: '#/seeker' }, 'Job Seeker'), h('a.btn.btn-quiet', { href: '#/explore' }, 'Explore data'), h('a.btn.btn-quiet', { href: '#/reviewer' }, 'Reviewer entry (separate workspace)')))));

      AL.api('/api/overview').then((ov) => {
        state.usingDemo = !!ov.using_demo;
        if (state.usingDemo) demoBadge.hidden = false;
        renderOverview(ovHost, ov);
      }).catch((e) => ovHost.replaceChildren(h('div.notice.error', { role: 'alert' }, 'Could not load the overview: ' + e.message)))
        .then(() => ms.init());
    },
  };
})();
