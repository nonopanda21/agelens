/* AgeLens map core: geometry projection, the province x industry metric model, and the map UI controller shared by the
   3D (Three.js) and 2D (SVG) engines.
   AgeLens.mapView(host, {force?: '2d'|'3d'}) -> Promise<{setVisible(bool), dispose(), engineName(), stats(), select(name), state()}>
   Data: ONE call to /api/stats/matrix (province x occupation cells + row/column totals); every view (map, ranking, spread,
   detail, heatmap) is derived from it in the browser, so they always agree. When /api/real/status says a precomputed real
   matrix exists (Zhaopin ads), a "Data" pill switch offers it (?source=real) and is the default; the choice is kept per tab
   (sessionStorage al_map_source). Switching re-fetches the matrix and re-renders every view.
   Engines (map3d.js / map2d.js) load on demand: AgeLens.map3d.create(opts) / AgeLens.map2d.create(opts) ->
   {setModel(model), setSelected(name, {fly}), setHover(name), resetView(), zoom(f), rotate(dx,dy), setActive(bool), resize(),
    noteInteraction(), dispose(), stats, name}. Keyboard handling lives here (one behaviour for both engines). */
(function () {
  const AL = (window.AgeLens = window.AgeLens || { pages: {} });
  const h = (...a) => AL.h(...a);
  const fmt = (n) => (typeof n === 'number' ? n.toLocaleString('en-US') : '–');
  const pct = (a, b) => (b ? (Math.round((a / b) * 1000) / 10).toFixed(1) + '%' : '–');

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

  /* ---------- geometry ---------- */
  let geoPromise = null;
  function loadGeo() {
    if (!geoPromise) geoPromise = fetch('geo/china_provinces.json').then((r) => { if (!r.ok) throw new Error('map geometry ' + r.status); return r.json(); }).catch((e) => { geoPromise = null; throw e; });
    return geoPromise;
  }
  /* Albers equal-area conic (standard parallels 25N/47N, centre 105E/35N): the usual look for China maps. Units: 100 * radians. */
  const D = Math.PI / 180;
  const P1 = 25 * D, P2 = 47 * D, P0 = 35 * D, L0 = 105 * D;
  const N = (Math.sin(P1) + Math.sin(P2)) / 2, C = Math.cos(P1) ** 2 + 2 * N * Math.sin(P1);
  const RHO0 = Math.sqrt(C - 2 * N * Math.sin(P0)) / N;
  function project(lon, lat) {
    const rho = Math.sqrt(C - 2 * N * Math.sin(lat * D)) / N, th = N * (lon * D - L0);
    return [100 * rho * Math.sin(th), 100 * (RHO0 - rho * Math.cos(th))]; // x east, y north
  }
  /** -> regions [{name, polys:[[ring,...holes]], center:[x,y], bbox:[x0,y0,x1,y1]}] ; rings are arrays of [x,y] (north up), closing point dropped */
  function buildRegions(geo) {
    return geo.features.map((f) => {
      const g = f.geometry;
      const polys = (g.type === 'Polygon' ? [g.coordinates] : g.coordinates).map((poly) => poly.map((ring) => {
        const pts = ring.map((c) => project(c[0], c[1]));
        const a = pts[0], b = pts[pts.length - 1];
        if (pts.length > 1 && a[0] === b[0] && a[1] === b[1]) pts.pop();
        return pts;
      }).filter((r) => r.length >= 3)).filter((p) => p.length);
      let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
      polys.forEach((p) => p[0].forEach(([x, y]) => { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }));
      const c = f.properties.center;
      return { name: f.properties.name, polys, center: c ? project(c[0], c[1]) : [(x0 + x1) / 2, (y0 + y1) / 2], bbox: [x0, y0, x1, y1] };
    });
  }

  /* ---------- metrics ---------- */
  // denominators below SMALL are flagged as unstable; below TINY drawn palest. They depend on the data source: 10/5 suit the
  // 960 simulated ads, but on 10M real ads a region with 46 ads would top a ranking, so real data uses 500/100
  // (docs/REAL_DATA_YEARS.md: Hong Kong, Macao and Taiwan are "few ads").
  let SMALL = 10, TINY = 5;
  const setThresholds = (src) => { if (src === 'real') { SMALL = 500; TINY = 100; } else { SMALL = 10; TINY = 5; } };
  const AGE_BASE = 18;          // median-age bars are measured from age 18 (the legend says so)
  const METRICS = {
    ads: { short: 'Ad count', title: 'Ad count', scale: 'count', num: (c) => c.ads, den: (c) => c.ads,
      unit: 'simulated ads', desc: 'Number of simulated ads (duplicates merged). Counts are not estimates, so there is no small-sample flag.',
      realDesc: 'Number of real Zhaopin ads in the dataset. Counts are not estimates, so there is no small-sample flag.' },
    aw: { short: 'Any age wording', title: 'Share of ads with any age wording', scale: 'share', num: (c) => c.age_wording, den: (c) => c.ads,
      unit: '% of ads', numWord: 'with age wording', desc: 'Ads containing any age wording (an explicit condition, unclear wording or a preference) ÷ all ads in scope.' },
    cap: { short: 'Explicit cap', title: 'Share of ads stating an explicit maximum age', scale: 'share', num: (c) => c.cap, den: (c) => c.ads,
      unit: '% of ads', numWord: 'state a maximum age', desc: 'Ads stating a maximum age (a hard cap, or a cap with an exception) ÷ all ads in scope.' },
    exc: { short: 'Mentions an exception', title: 'Share of ads whose age wording mentions an exception', scale: 'share', num: (c) => c.with_exception, den: (c) => c.ads,
      unit: '% of ads', numWord: 'mention an exception', desc: 'Ads whose age wording allows an exception or relaxation (for example for strong experience) ÷ all ads in scope.' },
    med: { short: 'Median max age', title: 'Median stated maximum age', scale: 'age', num: (c) => c.median_max_age, den: (c) => c.n_max_age,
      unit: 'years', desc: 'Middle value of the maximum age written in ads that state one. Denominator: ads that state a maximum age.' },
  };
  const METRIC_KEYS = ['ads', 'aw', 'cap', 'exc', 'med'];
  /* Pastel sequential scales (sketchbook palette). Every stop keeps relative luminance >= 0.39, so dark-brown ink text
     stays >= 4.5:1 on any fill and the darkest end still reads as "most". */
  const SCALES = {
    count: ['#EEF8FC', '#A8D8EA', '#7DB5D5'],   // paper blue -> sky -> deep sky (ad counts)
    share: ['#FFF5BA', '#FFB6C1', '#CF97C4'],   // butter -> pink -> orchid (age-wording shares)
    age: ['#EEFAF4', '#B5EAD7', '#7CC6A9'],     // paper mint -> mint -> deep mint (median stated max age)
  };
  const hex = (s) => [1, 3, 5].map((i) => parseInt(s.slice(i, i + 2), 16));
  const toHex = (c) => '#' + c.map((v) => Math.round(v).toString(16).padStart(2, '0')).join('');
  function scaleColor(scale, t) {
    const st = SCALES[scale].map(hex); t = Math.max(0, Math.min(1, t));
    const k = t * (st.length - 1), i = Math.min(st.length - 2, Math.floor(k)), f = k - i;
    return toHex(st[i].map((v, j) => v + (st[i + 1][j] - v) * f));
  }
  function mixWhite(c, k) { return toHex(hex(c).map((v) => v + (255 - v) * k)); }
  /** hatched fill for a horizontal bar (the reference's sketch bars): brown pen strokes over the value colour */
  const barGrad = (c) => 'repeating-linear-gradient(-35deg,rgba(74,55,40,.5) 0 1.5px,transparent 1.5px 5px),' + c;
  /** Text colour for a filled cell: brown ink (#4A3728) if it reaches 4.5:1 on the background, otherwise white (WCAG relative luminance). */
  function inkOn(bg) {
    const L = (rgb) => { const c = rgb.map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; };
    const lb = L(hex(bg)), ink = 0.0434;   // luminance of #4A3728
    return (lb + 0.05) / (ink + 0.05) >= 4.5 ? '#4A3728' : '#FFFFFF';
  }
  const tierOf = (den, scale) => (scale === 'count' ? 0 : den >= SMALL ? 0 : den >= TINY ? 1 : 2);
  const PALE = [0, 0.35, 0.6];
  function fmtVal(metric, v, long) {
    if (v == null) return '–';
    const s = METRICS[metric].scale;
    if (s === 'count') return fmt(v) + (long ? (v === 1 ? ' ad' : ' ads') : '');
    if (s === 'share') return long ? (Math.round(v * 1000) / 10).toFixed(1) + '%' : Math.round(v * 100) + '%';
    return (Math.round(v * 10) / 10) + (long ? ' years' : '');
  }
  /** Score one aggregate row ({ads, age_wording, cap, ...}) for a metric. */
  function score(row, metric) {
    const M = METRICS[metric], ads = row ? row.ads | 0 : 0;
    if (!ads) return { ads: 0, num: 0, den: 0, value: null, state: 'nodata', tier: 0 };
    const den = M.den(row) | 0, num = M.num(row);
    let value = null, state = 'value';
    if (M.scale === 'count') value = ads;
    else if (M.scale === 'share') { value = den ? (num | 0) / den : null; if (!(num | 0)) state = 'zero'; }
    else { value = den ? num : null; if (!den) state = 'nostated'; }
    return { ads, num: M.scale === 'age' ? den : num | 0, den, value, state, tier: tierOf(den, M.scale) };
  }
  function denText(metric, it) {
    const M = METRICS[metric];
    if (it.state === 'nodata') return 'no ads';
    if (M.scale === 'count') return fmt(it.ads) + ' ads';
    if (M.scale === 'share') return fmt(it.num) + ' of ' + fmt(it.den) + ' ads';
    return it.den ? 'from ' + fmt(it.den) + ' of ' + fmt(it.ads) + ' ads that state a maximum' : 'none of ' + fmt(it.ads) + ' ads states a maximum';
  }

  /** Index the matrix: rows (province totals), per-industry province rows, per-province industry rows. */
  function indexMatrix(mx) {
    const byOcc = new Map(), byProv = new Map(), rowTot = new Map();
    (mx.cells || []).forEach((c) => {
      if (!byOcc.has(c.occupation)) byOcc.set(c.occupation, new Map()); byOcc.get(c.occupation).set(c.province, c);
      if (!byProv.has(c.province)) byProv.set(c.province, new Map()); byProv.get(c.province).set(c.occupation, c);
    });
    (mx.provinces || []).forEach((r) => rowTot.set(r.province, r));
    // "Other" (titles the keyword rules could not place) is listed last, whatever its size
    const occs = (mx.occupations || []).filter((o) => o.occupation != null && o.ads > 0).sort((a, b) => (a.occupation === '其他') - (b.occupation === '其他'));
    return { byOcc, byProv, rowTot, occs, colTot: new Map((mx.occupations || []).map((o) => [o.occupation, o])), total: mx.total || { ads: 0 } };
  }
  /** Colour/height domain: items in the most reliable tier that still has >= 3 regions (fewer -> widen). */
  function domainOf(list, scale) {
    let tierUsed = 2;
    for (const T of [0, 1, 2]) { if (list.filter((i) => i.tier <= T).length >= 3) { tierUsed = T; break; } }
    const ref = list.filter((i) => i.tier <= tierUsed);
    const vals = (ref.length ? ref : list).map((i) => i.value);
    return { lo: vals.length ? Math.min(...vals) : 0, hi: vals.length ? Math.max(...vals) : 0, tierUsed, nRef: ref.length, scale };
  }
  /** Model for metric x industry (industry null = all industries). States: value | zero | nostated | nodata | unmatched. */
  function buildModel(ix, canon, regions, metric, industry) {
    const M = METRICS[metric], src = industry == null ? ix.rowTot : (ix.byOcc.get(industry) || new Map());
    const canonBy = new Map((canon || []).map((c) => [c.name, c]));
    const geoNames = new Set(regions.map((r) => r.name));
    const items = new Map();
    regions.forEach((rg) => {
      const c = canonBy.get(rg.name), s = score(src.get(rg.name), metric);
      if (canon && canon.length && !c) { s.state = 'unmatched'; s.value = null; }
      items.set(rg.name, Object.assign(s, { name: rg.name, en: c ? c.en : enName(rg.name) }));
    });
    const valued = [...items.values()].filter((i) => i.value != null);
    const dom = domainOf(valued, M.scale);
    const maxV = valued.length ? Math.max(...valued.map((i) => i.value)) : 0;
    items.forEach((it) => {
      it.t = 0; it.c = 0; it.color = null; it.top = null;
      if (it.value == null) return;
      it.t = M.scale === 'age' ? (maxV > AGE_BASE ? Math.max(0, it.value - AGE_BASE) / (maxV - AGE_BASE) : 0) : (maxV ? it.value / maxV : 0);
      it.c = dom.hi > dom.lo ? Math.max(0, Math.min(1, (it.value - dom.lo) / (dom.hi - dom.lo))) : 0.6;
      it.color = mixWhite(scaleColor(M.scale, 0.12 + 0.88 * it.c), PALE[it.tier]);
    });
    const ranked = valued.slice().sort((a, b) => (a.tier - b.tier) || (b.value - a.value) || (b.den - a.den) || a.en.localeCompare(b.en));
    ranked.forEach((it, i) => { it.rank = i + 1; });
    // highest / lowest BY VALUE among the comparison set (the ranking itself lists reliable regions first)
    const ref = ranked.filter((i) => i.tier <= dom.tierUsed).sort((a, b) => (b.value - a.value) || (b.den - a.den) || a.en.localeCompare(b.en));
    const spread = ref.length >= 2 ? { hi: ref[0], lo: ref[ref.length - 1], n: ref.length, range: ref[0].value - ref[ref.length - 1].value } : null;
    const unplaced = [...src.values()].filter((r) => r.ads > 0 && !geoNames.has(r.province)).reduce((a, r) => a + r.ads, 0);
    const scopeRow = industry == null ? ix.total : (ix.colTot.get(industry) || { ads: 0 });
    return { metric, industry, items, ranked, dom, maxV, spread, unplaced, scope: score(scopeRow, metric), regions };
  }
  const enName = (n) => (AL.labels ? AL.labels.prov(n) : n);
  const occName = (o) => (AL.labels ? AL.labels.occ(o) : o);
  /** Tooltip / announcement lines for one region. */
  function tipLines(it, model) {
    if (!it) return null;
    const m = model.metric;
    if (it.state === 'unmatched') return [it.en, 'Unmatched: this map region is not in the data names'];
    if (it.state === 'nodata') return [it.en, 'No data: 0 ads' + (model.industry ? ' in ' + occName(model.industry) : '')];
    if (it.state === 'nostated') return [it.en, 'No stated maximum age in ' + fmt(it.ads) + ' ads'];
    return [it.en, METRICS[m].short + ': ' + fmtVal(m, it.value, true), denText(m, it) + (it.tier ? ' · small sample, unstable' : '')];
  }

  /* ---------- data source (real vs simulated), remembered per tab ---------- */
  const SRC_KEY = 'al_map_source';
  function readSource() { try { return sessionStorage.getItem(SRC_KEY); } catch (e) { return null; } }
  function writeSource(v) { try { sessionStorage.setItem(SRC_KEY, v); } catch (e) { /* storage blocked: choice lasts for this view only */ } }
  /** "2021–2024" from meta.years (list of years, [from, to], or a string) */
  function realYears(meta) {
    const y = meta && meta.years;
    if (Array.isArray(y) && y.length) { const ns = y.map(Number).filter((v) => !isNaN(v)); if (!ns.length) return ''; const a = Math.min(...ns), b = Math.max(...ns); return a === b ? String(a) : a + '–' + b; }
    return typeof y === 'string' ? y.replace('-', '–') : '';
  }

  /* ---------- controller ---------- */
  async function mapView(host, o) {
    o = o || {};
    const [geo, canonRaw, status, realRaw] = await Promise.all([loadGeo(), AL.api('/api/provinces').catch(() => []), AL.api('/api/status').catch(() => null),
      AL.api('/api/real/status').catch(() => null)]);
    const real = realRaw && realRaw.available ? realRaw : null;
    let source = real ? (readSource() === 'demo' ? 'demo' : 'real') : 'demo';
    let mx = null;
    if (source === 'real') { try { mx = await AL.api('/api/stats/matrix?source=real'); } catch (e) { mx = null; source = 'demo'; } }
    if (!mx) mx = await AL.api('/api/stats/matrix');
    const canon = Array.isArray(canonRaw) ? canonRaw : [];
    setThresholds(source);
    const S = { regions: buildRegions(geo), ix: indexMatrix(mx), mx, source, real, canon, metric: 'aw', industry: null, selected: null, hover: null,
      engine: null, engineName: null, visible: true, destroyed: false, model: null, token: 0, kbd: -1, srcTok: 0 };
    const isReal = () => S.source === 'real';
    const dataWord = () => (isReal() ? 'real Zhaopin' : 'simulated');
    const canonBy = new Map(canon.map((c) => [c.name, c]));
    const provEn = (n) => (canonBy.get(n) || {}).en || enName(n);
    const inGeo = new Set(S.regions.map((r) => r.name));
    const reduced = () => AL.motion.reduced();

    // ---- motion helpers (Web Animations on transform/opacity only; nothing runs under reduced motion; no rAF loops)
    const canAnim = () => !reduced() && typeof Element.prototype.animate === 'function';
    const SPRING = 'cubic-bezier(.22,.9,.3,1)';
    /** bar growth with a short overshoot. Bars are sized by width (so the hatching is not stretched at rest); the animation
        scales from the old width to the new one (+6 % of the change) and settles at scaleX(1). */
    function grow(el, from, to, delay) {
      if (!canAnim() || Math.abs(to - from) < 0.004 || to <= 0) return;
      const f = (v) => 'scaleX(' + Math.max(0, v / to).toFixed(4) + ')';
      el.animate([{ transform: f(from) }, { transform: f(to + (to - from) * 0.06), offset: 0.7 }, { transform: 'none' }],
        { duration: 720, delay: delay || 0, easing: SPRING, fill: 'backwards' });
    }
    /** FLIP: remember positions of keyed nodes, then glide the new nodes from where the old ones were */
    function snap(root, sel) { const m = new Map(); root.querySelectorAll(sel).forEach((el) => { const r = el.getBoundingClientRect(); m.set(el.dataset.k, { x: r.left, y: r.top, s: el.dataset.s != null ? +el.dataset.s : null }); }); return m; }
    function flip(root, sel, prev, enterDelay) {
      if (!canAnim()) return;
      let i = 0;
      root.querySelectorAll(sel).forEach((el) => {
        const p = prev.get(el.dataset.k), r = el.getBoundingClientRect();
        if (p) {
          const dx = p.x - r.left, dy = p.y - r.top;
          if (Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5) el.animate([{ transform: 'translate(' + dx + 'px,' + dy + 'px)' }, { transform: 'none' }], { duration: 640, easing: SPRING });
        } else if (prev.size) el.animate([{ opacity: 0, transform: 'translateY(8px)' }, { opacity: 1, transform: 'none' }], { duration: 420, delay: (enterDelay || 30) * i++, easing: SPRING, fill: 'backwards' });
      });
    }

    // ---- controls: pill button groups (the pressed pill is filled pink, like the reference's tab buttons)
    const seg = (label, items, cur, on, cls) => {
      const g = h('div.mp-seg' + (cls ? '.' + cls : ''), { role: 'group', 'aria-label': label });
      const bs = items.map(([v, t, tip]) => h('button.mp-segbtn', { type: 'button', 'data-v': v, title: tip || null, onclick: () => on(v) }, t));
      g.append(...bs);
      g.sync = (c) => { bs.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v === c))); };
      g.sync(cur); return g;
    };
    const yrs = realYears(S.mx.meta || real);
    const sourceSeg = real ? seg('Data source', [['real', 'Real (Zhaopin' + (yrs ? ' ' + yrs : '') + ')', 'Aggregates of real Zhaopin job ads' + (real.rows_used ? ' (' + fmt(real.rows_used) + ' ads)' : '')],
      ['demo', 'Simulated demo', 'The simulated sample used everywhere else in the app']], S.source, (v) => setSource(v), 'mp-source') : null;
    const badge = h('span.badge');
    const realCap = h('p.mp-realcap', { hidden: '' });
    const metricSeg = seg('Metric', METRIC_KEYS.map((k) => [k, METRICS[k].short, METRICS[k].title]), S.metric, (v) => setMetric(v), 'mp-metrics');
    const viewSeg = seg('Map view', [['3d', '3D'], ['2d', '2D']], '3d', (v) => switchEngine(v, true));
    const chips = h('div.mp-chips', { role: 'group', 'aria-label': 'Industry' });
    // phones: the same choice as a compact select (18 chips would take many rows above the map); CSS shows one or the other
    const chipSel = h('select.mp-chip-sel', { 'aria-label': 'Industry' });
    chipSel.addEventListener('change', () => setIndustry(chipSel.value === '' ? null : chipSel.value));
    let chipBtns = [];
    function buildChips() {
      chipBtns = [[null, 'All industries', S.ix.total.ads]].concat(S.ix.occs.map((r) => [r.occupation, occName(r.occupation), r.ads]))
        .map(([v, t, n]) => { const b = h('button.mp-chip', { type: 'button', 'aria-pressed': 'false', title: fmt(n) + ' ads', onclick: () => setIndustry(v) }, t, h('span.mp-chip-n', { 'aria-hidden': 'true' }, fmt(n))); b._v = v; return b; });
      chips.replaceChildren(...chipBtns);
      chipSel.replaceChildren(...[[null, 'All industries', S.ix.total.ads]].concat(S.ix.occs.map((r) => [r.occupation, occName(r.occupation), r.ads]))
        .map(([v, t, n]) => h('option', { value: v == null ? '' : v }, t + ' (' + fmt(n) + ' ads)')));
      chipSel.value = S.industry == null ? '' : S.industry;
    }
    buildChips();
    const metricDesc = h('p.mp-mdesc');
    const explain = h('p.mp-explain');
    const explainTxt = (is3) => (is3 ? 'Each province rises from the same paper base; its extra height and top colour show the selected metric.' : 'Fill colour shows the selected metric.') + (isReal() ? ' Every number is a count of age wording in real Zhaopin job ads, not a hiring, rejection or unemployment rate.' : ' Every number is a simulated count of ad wording, not a hiring, rejection or unemployment rate.');
    explain.textContent = explainTxt(true);
    const btn = (label, txt, fn, cls) => h('button.btn.btn-quiet.mp-ib' + (cls ? '.' + cls : ''), { type: 'button', 'aria-label': label, title: label, onclick: () => { fn(); if (S.engine) S.engine.noteInteraction(); } }, txt);
    const tools = h('div.mp-tools', { role: 'group', 'aria-label': 'Map controls' },
      btn('Rotate left', '⟲', () => S.engine && S.engine.rotate(-1, 0), 'mp-3only'), btn('Rotate right', '⟳', () => S.engine && S.engine.rotate(1, 0), 'mp-3only'),
      btn('Tilt up', '▲', () => S.engine && S.engine.rotate(0, -1), 'mp-3only'), btn('Tilt down', '▼', () => S.engine && S.engine.rotate(0, 1), 'mp-3only'),
      btn('Zoom out', '−', () => S.engine && S.engine.zoom(0.8)), btn('Zoom in', '+', () => S.engine && S.engine.zoom(1.25)),
      h('button.btn.btn-quiet.mp-reset', { type: 'button', onclick: () => resetAll() }, 'Reset view'));
    const stage = h('div.mp-stage', { tabindex: '0', role: 'group', 'aria-roledescription': 'interactive map',
      'aria-label': 'Map of China by province. Left and right arrow keys step through provinces in rank order, Enter selects, Escape resets. Shift with arrows rotates, plus and minus zoom. The ranking, detail panel and tables below hold the same numbers.' });
    const kbdHint = h('p.mp-kbd', { 'aria-hidden': 'true' }, 'Keys: ← → step by rank · Enter select · Esc reset · Shift+arrows rotate');
    const note = h('p.hint.mp-note', { role: 'status' });
    const live = h('p.vh', { role: 'status', 'aria-live': 'polite' });
    const legend = h('div.mp-legend');
    const legendMore = h('div.mp-legmore');
    const detail = h('section.mp-detail', { 'aria-live': 'polite', 'aria-label': 'Selected region' });
    const spreadEl = h('section.mp-spread', { 'aria-label': 'Spread across regions' });
    const rankEl = h('section.mp-rank', { 'aria-label': 'Ranked regions' });
    const heatEl = h('section.mp-heat', { 'aria-label': 'Industry by region' });
    const tbody = h('tbody');
    const tableHead = h('tr');
    const table = h('details.mp-tbl', {}, h('summary', {}, 'All regions as a table (same numbers as the map)'),
      h('div.mp-tablewrap', { tabindex: '0', role: 'region', 'aria-label': 'Region table' }, h('table.mp-table', {}, h('thead', {}, tableHead), tbody)));
    const src = h('p.hint.mp-src');
    function renderSource() {
      const meta = S.mx.meta || {};
      badge.className = 'badge ' + (isReal() ? 'mint' : 'sim');
      badge.textContent = S.mx.label || (isReal() ? 'Real data' : 'Demo · Synthetic data');
      if (sourceSeg) sourceSeg.sync(S.source);
      const n = meta.rows_used != null ? meta.rows_used : (S.mx.total || {}).ads, y = realYears(meta);
      realCap.hidden = !isReal();
      realCap.textContent = isReal() ? 'Counts of age wording in ' + fmt(n) + ' real Zhaopin job ads' + (y ? ' posted ' + y : '') + '. They describe this dataset only, not hiring or unemployment rates.' : '';  // striping is explained in the legend
      src.textContent = 'Boundaries: Alibaba Cloud DataV GeoAtlas (areas_v3), simplified, province level; licence not yet verified, so local demonstration only and not an authoritative map. ' +
        (isReal() ? 'Numbers: Zhaopin job ads supplied by the team' +  /* meta.source holds the Chinese platform name; the map UI stays English */ (y ? ', ' + y : '') + (n != null ? ', ' + fmt(n) + ' ads used' : '') + (meta.rule_version ? ', rules ' + meta.rule_version : '') + (meta.generated_at ? ', computed ' + String(meta.generated_at).slice(0, 10) : '') + '. Precomputed aggregates; filters elsewhere in the app do not apply to them.'
          : 'Numbers: simulated ads' + (status && status.data && status.data.version ? ' (data version ' + status.data.version + ')' : '') + '.');
      explain.textContent = explainTxt(S.engineName ? S.engineName === '3d' : true);
    }
    renderSource();

    // one disclosure holds the long reading notes (definitions, states, keys, sources); the short legend stays visible
    const guide = h('details.mp-guide', {}, h('summary', {}, 'How to read this map'),
      h('div.mp-guide-body', {}, explain, metricDesc, legendMore, kbdHint, src));

    host.replaceChildren(h('div.mp', { 'data-zoom': '' },
      h('div.mp-bar', {}, h('div.mp-grp.mp-grp-metric', {}, h('span.mp-lab', {}, 'Metric'), metricSeg), h('div.mp-grp', {}, h('span.mp-lab', {}, 'View'), viewSeg),
        sourceSeg ? h('div.mp-grp.mp-grp-src', {}, h('span.mp-lab', {}, 'Data'), sourceSeg) : null, badge),
      h('div.mp-grp.mp-grp-ind', {}, h('span.mp-lab', {}, 'Industry'), chips, chipSel),
      note,
      h('div.mp-main', {}, h('div.mp-left', {}, stage, h('div.mp-under', {}, legend, tools), realCap), detail),
      // the extra views stay one click away so the overview is the map, its legend and the selected region
      h('details.mp-more', {}, h('summary', {}, 'More views: spread, top 10 regions, industry × region'),
        h('div.mp-row2', {}, spreadEl, rankEl), heatEl),
      h('div.mp-foot', {}, table, guide), live));

    // heatmap: cells fade-scale in by diagonal stagger the first time it scrolls into view
    let heatSeen = reduced() || !('IntersectionObserver' in window);
    const heatIO = heatSeen ? null : new IntersectionObserver((es) => {
      if (!es.some((e) => e.isIntersecting)) return;
      heatSeen = true; heatIO.disconnect();
      const w = heatEl.querySelector('.mp-hm-wrap'); if (w) { w.classList.remove('hm-pre'); if (!reduced()) w.classList.add('hm-go'); }
    }, { threshold: 0.12 });
    if (heatIO) heatIO.observe(heatEl);
    // any input anywhere in the map panel counts as interaction (stops / postpones the idle orbit)
    const mpRoot = host.querySelector('.mp');
    ['pointerdown', 'keydown', 'pointermove', 'focusin', 'wheel'].forEach((ev) => mpRoot.addEventListener(ev, () => { if (S.engine) S.engine.noteInteraction(); }, { passive: true }));
    // ---- state changes
    function setMetric(m) { if (!METRICS[m]) return; S.metric = m; refreshModel(); }
    function setIndustry(v) { S.industry = v; refreshModel(); }
    /** switch the data source: re-fetch the matrix, rebuild the index and industry chips, re-render every view */
    async function setSource(v) {
      if (v === S.source || (v === 'real' && !real)) { if (sourceSeg) sourceSeg.sync(S.source); return; }
      const tok = ++S.srcTok;
      mpRoot.setAttribute('aria-busy', 'true');
      let next;
      try { next = await AL.api('/api/stats/matrix' + (v === 'real' ? '?source=real' : '')); }
      catch (e) { if (tok === S.srcTok) { mpRoot.removeAttribute('aria-busy'); note.textContent = 'Could not load the ' + (v === 'real' ? 'real' : 'simulated') + ' data (' + e.message + ').'; if (sourceSeg) sourceSeg.sync(S.source); } return; }
      if (tok !== S.srcTok || S.destroyed) return;
      mpRoot.removeAttribute('aria-busy');
      S.source = v; setThresholds(v); S.mx = next; S.ix = indexMatrix(next); writeSource(v);
      if (S.industry != null && !S.ix.occs.some((r) => r.occupation === S.industry)) S.industry = null;
      if (S.selected && !S.ix.rowTot.has(S.selected)) { S.selected = null; if (S.engine) S.engine.setSelected(null, { fly: false }); }
      buildChips(); renderSource(); refreshModel();
      announce('Showing ' + (isReal() ? 'real Zhaopin data' : 'the simulated demo data'));
    }
    function announce(t) { live.textContent = t; }
    function choose(name, opt) {
      opt = opt || {};
      const next = opt.toggle === false ? name : (name === S.selected ? null : name);
      S.selected = next;
      if (S.engine) S.engine.setSelected(next, { fly: !!next && opt.fly !== false });
      const it = next && S.model.items.get(next);
      announce(it ? 'Selected ' + tipLines(it, S.model).join('. ') : 'Selection cleared');
      renderDetail(); syncMarks();
    }
    function setHover(name, from) {
      if (name === S.hover) return;
      S.hover = name;
      if (S.engine && from !== 'engine') S.engine.setHover(name);
      syncMarks();
    }
    function resetAll() {
      S.selected = null; S.kbd = -1; setHover(null);
      if (S.engine) { S.engine.setSelected(null, { fly: false }); S.engine.resetView(); }
      renderDetail(); syncMarks(); announce('View reset, selection cleared');
    }
    /** class toggles only (no rebuild) so hover feels instant */
    function syncMarks() {
      host.querySelectorAll('[data-prov]').forEach((el) => {
        const n = el.dataset.prov;
        el.classList.toggle('is-hover', n === S.hover); el.classList.toggle('is-sel', n === S.selected);
        if (el.hasAttribute('aria-pressed')) el.setAttribute('aria-pressed', String(n === S.selected));
      });
    }

    // ---- renderers
    function renderControls() {
      metricSeg.sync(S.metric);
      chipBtns.forEach((b) => b.setAttribute('aria-pressed', String(b._v === S.industry)));
      chipSel.value = S.industry == null ? '' : S.industry;
      const M = METRICS[S.metric], sc = S.model.scope;
      metricDesc.replaceChildren(h('strong', {}, M.title + (S.industry ? ' · ' + occName(S.industry) : ' · all industries') + '. '), isReal() && M.realDesc ? M.realDesc : M.desc,
        ' Overall: ' + fmtVal(S.metric, sc.value, true) + ' (' + denText(S.metric, sc) + ').',
        M.scale !== 'count' ? ' Regions with fewer than ' + SMALL + ' ads behind a value are drawn paler and striped, and marked as unstable.' : '');
    }
    function renderLegend() {
      const m = S.metric, M = METRICS[m], is3 = S.engineName === '3d', d = S.model.dom;
      const grad = 'linear-gradient(90deg,' + [0.12, 0.4, 0.7, 1].map((t) => scaleColor(M.scale, t)).join(',') + ')';
      const heightTxt = M.scale === 'age' ? 'Height above the paper base is measured from age ' + AGE_BASE + ', so it does not start at zero years.' : 'Height above the paper base is proportional to the value, from zero; the tallest province is the largest value shown.';
      legend.replaceChildren(
        h('div.mp-leg-bar', {}, h('span.mp-leg-t', {}, M.short + (M.scale === 'count' ? '' : ' · ' + M.unit)), h('span', {}, fmtVal(m, d.lo)), h('span.mp-grad', { 'aria-hidden': 'true', style: 'background:' + grad }), h('span', {}, fmtVal(m, d.hi))),
        h('p.mp-leg-h', {}, is3 ? 'Colour and height above the paper base show the value.' : 'Darker fill means a larger value.' , M.scale !== 'count' ? ' Striped: fewer than ' + SMALL + ' ads.' : ''));
      legendMore.replaceChildren(
        h('p.mp-leg-h', {}, h('strong', {}, is3 ? 'Height and colour: ' : 'Fill colour: '), M.title.toLowerCase() + (M.scale === 'count' ? '' : ' (' + M.unit + ')') + '. ' + (is3 ? heightTxt : '')),
        h('p.mp-leg-deco', {}, h('strong', {}, is3 ? 'Province thickness is decoration. ' : 'Only colour encodes data. '),
          is3 ? 'Every province stands on the same paper base; only the height above it and the top colour carry the value. Colour runs from the lowest to the highest value among regions with enough ads.' : 'Darker means a larger value, from the lowest to the highest among regions with enough ads.'),
        h('ul.mp-states', {},
          h('li', {}, h('span.mp-sw.nodata', { 'aria-hidden': 'true' }), 'No data: 0 ads in scope'),
          M.scale === 'share' ? h('li', {}, h('span.mp-sw.zero', { 'aria-hidden': 'true' }), 'Zero: ads exist, none counted (ring marker)') : null,
          M.scale === 'age' ? h('li', {}, h('span.mp-sw.nodata', { 'aria-hidden': 'true' }), 'No stated maximum: ads exist but none states one') : null,
          M.scale !== 'count' ? h('li', {}, h('span.mp-sw.small', { 'aria-hidden': 'true' }), 'Striped and paler' + '' + ': fewer than ' + SMALL + ' ads behind the value (palest' + '' + ' under ' + TINY + '), unstable') : null,
          h('li', {}, h('span.mp-sw.unm', { 'aria-hidden': 'true' }), 'Unmatched: map region not found in the data names')));
    }
    function renderSpread() {
      const m = S.metric, M = METRICS[m], md = S.model, sp = md.spread;
      const scopeTxt = S.industry ? occName(S.industry) : 'all industries';
      const head = h('h3', {}, 'Spread across regions');
      if (!sp) {
        spreadEl.replaceChildren(head, h('p', {}, 'Fewer than two regions have a value for ' + M.short.toLowerCase() + ' in ' + scopeTxt + ', so there is no spread to show.'));
        return;
      }
      const tierTxt = M.scale === 'count' ? 'all ' + sp.n + ' regions with ads' : md.dom.tierUsed === 0 ? sp.n + ' regions with at least ' + SMALL + ' ads' : md.dom.tierUsed === 1 ? sp.n + ' regions with at least ' + TINY + ' ads' : sp.n + ' regions with any ads';
      const rangeTxt = M.scale === 'share' ? Math.round(sp.range * 100) + ' percentage points' : M.scale === 'age' ? (Math.round(sp.range * 10) / 10) + ' years' : fmt(sp.range) + ' ads';
      const who = (it) => h('button.mp-link', { type: 'button', 'data-prov': it.name, onclick: () => choose(it.name, { toggle: false }), onmouseenter: () => setHover(it.name), onmouseleave: () => setHover(null) }, it.en);
      const stats = h('dl.mp-sp', {},
        h('div', {}, h('dt', {}, 'Highest'), h('dd', {}, who(sp.hi), ' ', h('strong', {}, fmtVal(m, sp.hi.value, true)), h('span.mp-n', {}, ' ' + denText(m, sp.hi)))),
        h('div', {}, h('dt', {}, 'Lowest'), h('dd', {}, who(sp.lo), ' ', h('strong', {}, fmtVal(m, sp.lo.value, true)), h('span.mp-n', {}, ' ' + denText(m, sp.lo)))),
        h('div', {}, h('dt', {}, 'Range'), h('dd', {}, h('strong', {}, rangeTxt), h('span.mp-n', {}, ' across ' + tierTxt))));
      const caution = md.dom.tierUsed > 0 && M.scale !== 'count'
        ? h('p.mp-caution', {}, 'Few ads per region in ' + scopeTxt + ': no ' + (md.dom.tierUsed === 1 ? '' : 'or almost no ') + 'region reaches ' + SMALL + ' ads here, so highest and lowest are compared among ' + tierTxt + '. Treat the gap as illustrative; one ad can move a share a lot.')
        : null;
      // dot strip: each dot = one region; position = value; paler/hollow = small sample
      const list = md.ranked;
      const lo = M.scale === 'age' ? Math.min(...list.map((i) => i.value)) : 0, hi = Math.max(...list.map((i) => i.value), lo + 1e-9);
      const pos = (v) => (hi > lo ? (v - lo) / (hi - lo) : 0.5);
      const lanes = [], track = h('div.mp-strip-track', { style: '--g:linear-gradient(90deg,' + scaleColor(M.scale, 0.15) + ',' + scaleColor(M.scale, 0.6) + ',' + scaleColor(M.scale, 1) + ')' });
      const byVal = list.slice().sort((a, b) => a.value - b.value);
      const dots = byVal.map((it) => {
        const x = pos(it.value); let lane = lanes.findIndex((lx) => x - lx > 0.024); if (lane < 0) { if (lanes.length < 4) { lane = lanes.length; lanes.push(-1); } else lane = lanes.indexOf(Math.min(...lanes)); } lanes[lane] = x;
        const b = h('button.mp-dot' + (it.tier ? '.t' + it.tier : ''), { type: 'button', tabindex: '-1', 'data-prov': it.name, 'data-k': it.name, 'aria-pressed': 'false',
          'aria-label': it.en + ': ' + fmtVal(m, it.value, true) + ', ' + denText(m, it) + (it.tier ? ', small sample' : ''),
          style: 'left:' + (x * 100).toFixed(2) + '%;top:' + (lane * 13 + 6) + 'px;--dot:' + (it.color || '#ccc'),
          onclick: () => choose(it.name, { toggle: false }), onmouseenter: () => setHover(it.name), onmouseleave: () => setHover(null), onfocus: () => setHover(it.name), onblur: () => setHover(null) });
        b.title = it.en + ' · ' + fmtVal(m, it.value, true) + ' · ' + denText(m, it);
        return b;
      });
      track.style.height = Math.max(1, lanes.length) * 13 + 14 + 'px';
      track.append(...dots);
      roving(dots, 'h');
      if (dots.length) dots[dots.length - 1].tabIndex = 0;
      const prevDots = snap(spreadEl, '.mp-dot');
      spreadEl.replaceChildren(...[head, stats, caution].filter(Boolean),
        h('div.mp-strip', { role: 'group', 'aria-label': 'Every region on one axis, ' + M.short.toLowerCase() + '. Use arrow keys to move between regions.' },
          track, h('div.mp-strip-axis', { 'aria-hidden': 'true' }, h('span', {}, fmtVal(m, lo, false)), h('span', {}, M.scale === 'count' ? 'each dot is one region' : 'each dot is one region · hollow = fewer than ' + SMALL + ' ads'), h('span', {}, fmtVal(m, hi, false)))));
      flip(spreadEl, '.mp-dot', prevDots, 8);
    }
    function renderRank() {
      const m = S.metric, list = S.model.ranked.slice(0, 10);
      const prevRows = snap(rankEl, '.mp-rankli'), prevBars = snap(rankEl, '.mp-rfill');
      const maxV = Math.max(...S.model.ranked.map((i) => i.value), 1e-9);
      const items = [];
      let lastTier = 0;
      list.forEach((it) => {
        if (METRICS[m].scale !== 'count' && it.tier !== lastTier && it.tier > 0) items.push(h('li.mp-rank-div', { 'aria-hidden': 'true' }, it.tier === 1 ? TINY + '–' + (SMALL - 1) + ' ads: unstable' : 'Under ' + TINY + ' ads: very unstable'));
        lastTier = it.tier;
        const w = METRICS[m].scale === 'age' ? Math.max(0.04, (it.value - AGE_BASE) / Math.max(1, maxV - AGE_BASE)) : Math.max(0.02, it.value / maxV);
        items.push(h('li.mp-rankli', { 'data-k': it.name }, h('button.mp-rankbtn' + (it.tier ? '.t' + it.tier : ''), { type: 'button', 'data-prov': it.name, 'aria-pressed': 'false',
          onclick: () => choose(it.name, { toggle: false }), onmouseenter: () => setHover(it.name), onmouseleave: () => setHover(null), onfocus: () => setHover(it.name), onblur: () => setHover(null) },
          h('span.mp-rk', {}, String(it.rank)), h('span.mp-rname', {}, it.en),
          h('span.mp-rbar' + (S.changing && canAnim() ? '.sweep' : ''), { 'aria-hidden': 'true', style: '--i:' + items.length },
            h('span.mp-rfill', { 'data-k': it.name, 'data-s': w.toFixed(4), style: 'width:' + (w * 100).toFixed(1) + '%;background:' + barGrad(it.color) })),
          h('span.mp-rval', {}, fmtVal(m, it.value)), h('span.mp-rn', {}, 'n=' + fmt(it.den)))));
      });
      rankEl.replaceChildren(h('h3', {}, 'Top 10 regions'), h('p.hint.mp-rank-sub', {}, METRICS[m].short + (S.industry ? ' · ' + occName(S.industry) : ' · all industries') + '. Regions with enough ads are ranked first; n = ads behind the value.'),
        list.length ? h('ol.mp-ranklist', {}, items) : h('p', {}, 'No region has a value in this view.'));
      flip(rankEl, '.mp-rankli', prevRows, 40);
      rankEl.querySelectorAll('.mp-rfill').forEach((el, i) => { const p = prevBars.get(el.dataset.k); grow(el, p ? p.s : 0, +el.dataset.s, p ? 0 : 60 + i * 35); });
    }
    function renderDetail() {
      const m = S.metric, M = METRICS[m], nm = S.selected, it = nm && S.model.items.get(nm);
      const scopeTxt = S.industry ? occName(S.industry) : 'all industries';
      const kids = [];
      // which rows feed the industry breakdown: the selected province's cells, or all-region column totals
      let rowsMap, where;
      if (it) { rowsMap = S.ix.byProv.get(nm) || new Map(); where = it.en; }
      else { rowsMap = S.ix.colTot; where = 'all regions'; }
      if (it) {
        kids.push(h('h3', {}, it.en), h('p.mp-dsub', {}, scopeTxt));
        if (it.state === 'unmatched') kids.push(h('p', {}, 'This map region could not be matched to a province name in the data, so no numbers are shown for it.'));
        else if (it.state === 'nodata') kids.push(h('p', {}, 'No ads in ' + it.en + (S.industry ? ' for ' + scopeTxt : '') + ' in the ' + dataWord() + ' data (0 ads). That is an absence of records' + (isReal() ? ' in this dataset, not evidence that no such jobs exist.' : ', not evidence about the real world.')));
        else {
          kids.push(it.state === 'nostated' ? h('p.mp-big.mp-big-txt', {}, h('strong', {}, 'No stated maximum')) : h('p.mp-big', {}, h('strong', {}, fmtVal(m, it.value, true)), h('span', {}, ' ' + M.short.toLowerCase())),
            h('p.mp-n', {}, denText(m, it) + (it.rank ? ' · rank ' + it.rank + ' of ' + S.model.ranked.length : '')));
          if (it.state === 'zero') kids.push(h('p.hint', {}, 'Zero, not missing: ads exist here but none is counted for this metric.'));
          if (it.tier) kids.push(h('p.mp-caution', {}, 'Small sample: fewer than ' + SMALL + ' ads behind this value, so a single ad moves it a lot.'));
          const row = S.industry ? (S.ix.byOcc.get(S.industry) || new Map()).get(nm) : S.ix.rowTot.get(nm);
          if (row) kids.push(h('dl.mp-dl', {},
            h('dt', {}, 'Ads'), h('dd', {}, fmt(row.ads)),
            h('dt', {}, 'Any age wording'), h('dd', {}, pct(row.age_wording, row.ads) + ' · ' + fmt(row.age_wording) + ' of ' + fmt(row.ads)),
            h('dt', {}, 'Explicit cap'), h('dd', {}, pct(row.cap, row.ads) + ' · ' + fmt(row.cap) + ' of ' + fmt(row.ads)),
            h('dt', {}, 'Mentions an exception'), h('dd', {}, pct(row.with_exception, row.ads) + ' · ' + fmt(row.with_exception) + ' of ' + fmt(row.ads)),
            h('dt', {}, 'Median max age'), h('dd', {}, row.median_max_age != null ? row.median_max_age + ' · from ' + fmt(row.n_max_age) + ' ads' : 'none stated')));
        }
      } else {
        kids.push(h('h3', {}, 'All regions'), h('p.mp-dsub', {}, scopeTxt),
          h('p.mp-big', {}, h('strong', {}, fmtVal(m, S.model.scope.value, true)), h('span', {}, ' ' + M.short.toLowerCase())),
          h('p.mp-n', {}, denText(m, S.model.scope)),
          h('p.hint', {}, 'Select a region on the map, in the ranking or in the table to compare its industries.'));
      }
      // industry breakdown for the current metric
      const occRows = S.ix.occs.map((r) => ({ occ: r.occupation, s: score(rowsMap.get(r.occupation), m) })).filter((x) => x.s.ads > 0);
      if (occRows.length && (!it || (it.state !== 'unmatched'))) {
        const vals = occRows.filter((x) => x.s.value != null).map((x) => x.s.value);
        const mx2 = Math.max(...vals, 1e-9), lo2 = Math.min(...vals);
        occRows.sort((a, b) => (b.s.value == null) - (a.s.value == null) || (b.s.value || 0) - (a.s.value || 0) || b.s.den - a.s.den);
        kids.push(h('h4.mp-bh', {}, 'By industry in ' + where), h('ul.mp-occ', {}, occRows.map((x) => {
          const v = x.s.value, w = v == null ? 0 : M.scale === 'age' ? Math.max(0.04, (v - AGE_BASE) / Math.max(1, mx2 - AGE_BASE)) : Math.max(0.02, v / mx2);
          const col = v == null ? '#EDE4DC' : mixWhite(scaleColor(M.scale, 0.12 + 0.88 * (mx2 > lo2 ? (v - lo2) / (mx2 - lo2) : 0.6)), PALE[x.s.tier]);
          return h('li', {}, h('button.mp-occbtn' + (x.s.tier ? '.t' + x.s.tier : '') + (x.occ === S.industry ? '.on' : ''), { type: 'button', 'aria-pressed': String(x.occ === S.industry),
            title: 'Show ' + occName(x.occ) + ' on the map', onclick: () => setIndustry(x.occ === S.industry ? null : x.occ) },
            h('span.mp-oname', {}, occName(x.occ)), h('span.mp-obar', { 'aria-hidden': 'true' }, h('span.mp-ofill', { 'data-k': x.occ, 'data-s': w.toFixed(4), style: 'width:' + (w * 100).toFixed(1) + '%;background:' + (v == null ? col : barGrad(col)) })),
            h('span.mp-oval', {}, v == null ? '–' : fmtVal(m, v)), h('span.mp-on', {}, 'n=' + fmt(x.s.den))));
        })), h('p.hint.mp-ohint', {}, 'Paler bars: fewer than ' + SMALL + ' ads. Click an industry to show it on the map.'));
      }
      if (it && it.ads && isReal()) kids.push(h('p.hint.mp-go-note', {}, 'Only these aggregate counts of the real ads are in the app; the explorer lists the simulated sample, not these ads.'));
      else if (it && it.ads) kids.push(h('a.btn.btn-secondary.mp-go', { href: '#/explore?province=' + encodeURIComponent(it.name) + (S.industry ? '&occupation=' + encodeURIComponent(S.industry) : '') }, 'Show these ads in the explorer'));
      if (M.scale !== 'count') kids.push(h('p.hint.mp-not', {}, 'A share of ' + dataWord() + ' ads with this wording. It is not a discrimination rate, a rejection rate or a measure of the job market.'));
      const prevOcc = snap(detail, '.mp-ofill');
      detail.replaceChildren(...kids);
      detail.querySelectorAll('.mp-ofill').forEach((el, i) => { const p = prevOcc.get(el.dataset.k); grow(el, p ? p.s : 0, +el.dataset.s, p ? 0 : i * 22); });
      syncMarks();
    }
    function renderHeat() {
      const m = S.metric, M = METRICS[m];
      const cols = S.ix.byProv ? [...S.ix.rowTot.values()].filter((r) => r.province && inGeo.has(r.province)).sort((a, b) => b.ads - a.ads).slice(0, 12).map((r) => r.province) : [];
      const rows = S.ix.occs.map((r) => r.occupation);
      const sc = [];
      rows.forEach((oc) => cols.forEach((pv) => { const s = score((S.ix.byOcc.get(oc) || new Map()).get(pv), m); if (s.value != null) sc.push(s); }));
      const dom = domainOf(sc, M.scale);
      const cells = [], prevC = S.heatCols || new Map(), nextC = new Map(), xf = heatSeen && canAnim();
      const thead = h('tr', {}, h('th.mp-hm-corner', { scope: 'col' }, h('span.vh', {}, 'Industry'), h('span', { 'aria-hidden': 'true' }, 'Industry ↓ / region →')),
        cols.map((pv) => h('th.mp-hm-col', { scope: 'col', 'data-prov': pv }, h('span', {}, provEn(pv)))));
      const body = rows.map((oc, ri) => h('tr' + (oc === S.industry ? '.on' : ''), {}, h('th', { scope: 'row' }, occName(oc)), cols.map((pv, ci) => {
        const s = score((S.ix.byOcc.get(oc) || new Map()).get(pv), m);
        const c = s.value == null ? null : (dom.hi > dom.lo ? Math.max(0, Math.min(1, (s.value - dom.lo) / (dom.hi - dom.lo))) : 0.6);
        const bg = c == null ? null : mixWhite(scaleColor(M.scale, 0.12 + 0.88 * c), PALE[s.tier]);
        const dark = bg != null && inkOn(bg) === '#FFFFFF';
        const txt = s.state === 'nodata' ? '·' : s.value == null ? '–' : M.scale === 'share' ? String(Math.round(s.value * 100)) : M.scale === 'age' ? String(Math.round(s.value)) : fmt(s.value);
        const label = occName(oc) + ' in ' + provEn(pv) + ': ' + (s.state === 'nodata' ? 'no ads' : s.state === 'nostated' ? 'no stated maximum age in ' + fmt(s.ads) + ' ads' : fmtVal(m, s.value, true) + ', ' + denText(m, s)) + (s.tier && s.state !== 'nodata' ? ', small sample' : '');
        const key = oc + '|' + pv, was = prevC.get(key), now = bg || (s.state === 'nodata' ? '#F7F8FA' : '#F3F5F8'); nextC.set(key, now);
        const fade = xf && was && was !== now;   // colour cross-fade: the old colour sits on top and fades out (opacity only)
        const b = h('button.mp-hm-cell' + (s.state === 'nodata' ? '.nd' : '') + (s.tier ? '.t' + s.tier : '') + (dark ? '.dk' : '') + (fade ? '.mp-xf' : ''), { type: 'button', tabindex: '-1', 'data-prov': pv, 'aria-label': label, title: label,
          style: (bg ? '--c:' + bg + ';--t:' + inkOn(bg) + ';' : '') + '--d:' + Math.min(900, (ri + ci) * 26) + 'ms' + (fade ? ';--c0:' + was : ''),
          onclick: () => { S.industry = oc; refreshModel(); choose(pv, { toggle: false }); },
          onmouseenter: () => setHover(pv), onmouseleave: () => setHover(null), onfocus: () => setHover(pv), onblur: () => setHover(null) }, h('span', {}, txt));
        b._r = ri; b._c = ci; cells.push(b);
        return h('td', {}, b);
      })));
      gridRoving(cells, rows.length, cols.length);
      S.heatCols = nextC;
      heatEl.replaceChildren(h('h3', {}, 'Industry × region'),
        h('p.hint.mp-heat-sub', {}, M.short + ' for every industry in the ' + cols.length + ' regions with the most ads' + (M.scale === 'share' ? ' (values in %)' : M.scale === 'age' ? ' (years)' : ' (ads)') + '. Striped, paler cells rest on fewer than ' + SMALL + ' ads; “·” means no ads. Click a cell to show that industry and region on the map.'),
        h('div.mp-hm-wrap' + (heatSeen ? '' : '.hm-pre'), { role: 'region', 'aria-label': 'Industry by region table', tabindex: '-1' }, h('table.mp-hm', {}, h('caption.vh', {}, M.title + ' by industry and region, ' + dataWord() + ' data'), h('thead', {}, thead), h('tbody', {}, body))));
    }
    function renderTable() {
      const m = S.metric, M = METRICS[m];
      tableHead.replaceChildren(h('th', { scope: 'col' }, 'Region'), h('th.num', { scope: 'col' }, 'Ads'), h('th.num', { scope: 'col' }, M.short), h('th.num', { scope: 'col' }, M.scale === 'count' ? 'Rank' : 'Denominator'));
      const items = [...S.model.items.values()].sort((a, b) => (a.rank || 999) - (b.rank || 999) || b.ads - a.ads || a.en.localeCompare(b.en));
      tbody.replaceChildren(...items.map((it) => h('tr' + (it.ads ? '' : '.nodata'), { 'data-prov': it.name },
        h('th', { scope: 'row' }, h('button.mp-rowbtn', { type: 'button', 'data-prov': it.name, 'aria-pressed': 'false', onclick: () => choose(it.name) }, it.en)),
        h('td.num', {}, it.state === 'unmatched' ? 'Unmatched' : fmt(it.ads)),
        h('td.num', {}, it.state === 'nodata' ? 'No data' : it.state === 'unmatched' ? '–' : it.state === 'nostated' ? 'None stated' : fmtVal(m, it.value, true) + (it.tier ? ' (small n)' : '')),
        h('td.num', {}, M.scale === 'count' ? (it.rank ? String(it.rank) : '–') : it.den ? fmt(it.den) : '–'))));
    }
    function refreshModel() {
      S.model = buildModel(S.ix, S.canon, S.regions, S.metric, S.industry);
      S.kbd = -1;
      if (S.engine) S.engine.setModel(S.model);
      S.changing = !!S.rendered;   // metric / industry change (not the first render): sweep highlights run
      renderControls(); renderLegend(); renderDetail(); renderSpread(); renderRank(); renderHeat(); renderTable();
      S.changing = false; S.rendered = true;
      if (!note.dataset.fixed) note.textContent = S.model.unplaced ? fmt(S.model.unplaced) + ' ads in this scope have no province that can be placed on the map; they are counted in the totals only.' : '';
      syncMarks();
      announce(METRICS[S.metric].title + ', ' + (S.industry ? occName(S.industry) : 'all industries'));
    }

    // ---- roving focus helpers (one tab stop per widget; arrows move)
    function roving(btns, dir) {
      btns.forEach((b, i) => b.addEventListener('keydown', (e) => {
        const k = e.key; let j = -1;
        if (k === 'ArrowRight' || (dir === 'v' && k === 'ArrowDown')) j = Math.min(btns.length - 1, i + 1);
        else if (k === 'ArrowLeft' || (dir === 'v' && k === 'ArrowUp')) j = Math.max(0, i - 1);
        else if (k === 'Home') j = 0; else if (k === 'End') j = btns.length - 1;
        if (j < 0) return; e.preventDefault(); btns.forEach((x) => { x.tabIndex = -1; }); btns[j].tabIndex = 0; btns[j].focus();
      }));
    }
    function gridRoving(cells, R, Cn) {
      if (!cells.length) return;
      const at = (r, c) => cells[r * Cn + c];
      const start = cells.find((c) => !c.classList.contains('nd')) || cells[0]; start.tabIndex = 0;
      cells.forEach((b) => b.addEventListener('keydown', (e) => {
        let r = b._r, c = b._c;
        if (e.key === 'ArrowRight') c = Math.min(Cn - 1, c + 1); else if (e.key === 'ArrowLeft') c = Math.max(0, c - 1);
        else if (e.key === 'ArrowDown') r = Math.min(R - 1, r + 1); else if (e.key === 'ArrowUp') r = Math.max(0, r - 1);
        else if (e.key === 'Home') c = 0; else if (e.key === 'End') c = Cn - 1; else return;
        e.preventDefault(); const t = at(r, c); cells.forEach((x) => { x.tabIndex = -1; }); t.tabIndex = 0; t.focus();
      }));
    }

    // ---- keyboard on the map stage (both engines)
    stage.addEventListener('keydown', (e) => {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      const k = e.key, list = S.model.ranked; let hit = true;
      if (S.engine) S.engine.noteInteraction();
      if (e.shiftKey && /^Arrow/.test(k)) {
        if (!S.engine) return;
        if (k === 'ArrowLeft') S.engine.rotate(-1, 0); else if (k === 'ArrowRight') S.engine.rotate(1, 0);
        else if (k === 'ArrowUp') S.engine.rotate(0, -1); else S.engine.rotate(0, 1);
      } else if (k === 'ArrowRight' || k === 'ArrowDown' || k === 'ArrowLeft' || k === 'ArrowUp') {
        if (!list.length) return;
        const fwd = k === 'ArrowRight' || k === 'ArrowDown';
        S.kbd = S.kbd < 0 ? (fwd ? 0 : list.length - 1) : (S.kbd + (fwd ? 1 : -1) + list.length) % list.length;
        const it = list[S.kbd]; setHover(it.name);
        announce('Rank ' + it.rank + ' of ' + list.length + ': ' + tipLines(it, S.model).join('. ') + '. Press Enter to select.');
      } else if (k === 'Enter' || k === ' ') { if (S.hover) choose(S.hover, { toggle: false }); else hit = false; }
      else if (k === 'Escape') resetAll();
      else if (k === '+' || k === '=') S.engine && S.engine.zoom(1.25);
      else if (k === '-' || k === '_') S.engine && S.engine.zoom(0.8);
      else if (k === '0') S.engine && S.engine.resetView();
      else hit = false;
      if (hit) e.preventDefault();
    });

    // ---- engines
    async function switchEngine(which, user) {
      const tok = ++S.token;
      if (S.engine) { S.engine.dispose(); S.engine = null; }
      stage.querySelectorAll('canvas,svg,.mp-lbls,.mp-tip').forEach((n) => n.remove());
      let eng = null;
      if (which === '3d') {
        if (!AL.gfx.webgl()) { note.textContent = 'WebGL is not available in this browser, so the interactive 2D map is shown. Every control below works the same.'; note.dataset.fixed = '1'; which = '2d'; }
        else {
          try {
            await AL.loadScript('js/map3d.js');
            if (tok !== S.token || S.destroyed) return;
            eng = await AL.map3d.create(engineOpts());
          } catch (e) { note.textContent = 'The 3D map could not start (' + e.message + '), so the 2D map is shown.'; note.dataset.fixed = '1'; which = '2d'; eng = null; }
        }
      }
      if (which === '2d') {
        await AL.loadScript('js/map2d.js');
        if (tok !== S.token || S.destroyed) return;
        eng = AL.map2d.create(engineOpts());
      }
      if (tok !== S.token || S.destroyed) { if (eng) eng.dispose(); return; }
      S.engine = eng; S.engineName = which;
      if (user) { delete note.dataset.fixed; note.textContent = ''; AL.store.set('al_map_view', which); }
      viewSeg.sync(which);
      explain.textContent = explainTxt(which === '3d');
      host.querySelector('.mp').dataset.engine = which;
      host.querySelectorAll('.mp-3only').forEach((b) => { b.hidden = which !== '3d'; });
      kbdHint.textContent = which === '3d' ? 'Keys: ← → step by rank · Enter select · Esc reset · Shift+arrows rotate · + − zoom' : 'Keys: ← → step by rank · Enter select · Esc reset · Shift+arrows pan · + − zoom';
      eng.setModel(S.model); eng.setSelected(S.selected, { fly: false });
      eng.setActive(S.visible); if (S.visible) eng.resize();
      renderLegend();
    }
    function engineOpts() {
      return {
        stage, regions: S.regions, reduced, pixelRatio: () => AL.gfx.pixelRatio(), gfx: AL.gfx, tipLines,
        onSelect: (n) => { if (n) choose(n); },
        onHover: (n) => setHover(n, 'engine'),
        onFail: (why) => { if (S.destroyed) return; note.textContent = 'The 3D view stopped (' + why + '), so the 2D map is shown.'; note.dataset.fixed = '1'; switchEngine('2d', false); },
      };
    }

    refreshModel();
    const pref = AL.store.get('al_map_view');
    await switchEngine(o.force || (pref === '2d' ? '2d' : '3d'), false);
    return {
      setVisible(v) { S.visible = v; if (S.engine) { S.engine.setActive(v); if (v) S.engine.resize(); } },
      dispose() { S.destroyed = true; S.token++; if (heatIO) heatIO.disconnect(); if (S.engine) S.engine.dispose(); S.engine = null; },
      engineName: () => S.engineName,
      stats: () => (S.engine ? S.engine.stats : null),
      _debug: () => S.engine && S.engine._debug,
      select: (n) => choose(n, { toggle: false }),
      setMetric, setIndustry,
      setSource,
      state: () => ({ source: S.source, label: S.mx.label, metric: S.metric, industry: S.industry, selected: S.selected, hover: S.hover, engine: S.engineName, ranked: S.model.ranked.map((i) => i.name), spread: S.model.spread && { hi: S.model.spread.hi.name, lo: S.model.spread.lo.name, range: S.model.spread.range, n: S.model.spread.n } }),
    };
  }
  AL.mapView = mapView;
  AL.mapCore = { project, buildRegions, buildModel, indexMatrix, scaleColor, mixWhite, fmtVal, tipLines, fmt, pct, METRICS, get SMALL() { return SMALL; }, get TINY() { return TINY; } };
})();
