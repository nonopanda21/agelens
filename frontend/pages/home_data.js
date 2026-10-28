/* Home section "data" (order 40): simulated-data overview + featured regional/industry map (open by default, created lazily when it
   first scrolls into view, collapsible, stops when collapsed, disposed on leave). */
(function () {
  const AL = window.AgeLens;
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
  AL.home = AL.home || { sections: [] };
  AL.home.sections.push({
    id: 'data', order: 40,
    async render(el) {
      const h = AL.h;
      let ov, status = null;
      try { ov = await AL.api('/api/overview'); } catch (e) { ov = null; }
      try { status = await AL.api('/api/status'); } catch (e) { status = null; }
      const version = (ov && ov.data_version) || (status && status.data && status.data.version) || null;

      const tile = (label, value, sub) => h('div.dt-tile', {}, h('p.dt-value', {}, value), h('p.dt-label', {}, label), h('p.hint.dt-sub', {}, sub));
      let tiles;
      if (!ov || !ov.unique_ads) {
        tiles = h('div.card.dt-empty', { role: 'status' }, h('p', {}, ov ? 'No ads are loaded yet, so there is nothing to summarise.' : 'The data overview could not be loaded. The rest of the page still works; reload to try again.'));
      } else {
        const den = ov.denominator != null ? ov.denominator : ov.unique_ads;
        const aw = (ov.explicit_count || 0) + (ov.uncertain_count || 0);
        const top = (ov.top_max_ages || [])[0];
        tiles = h('div.dt-tiles', {},
          tile('Simulated ads', fmt(ov.unique_ads), fmt(ov.raw_rows) + ' raw rows, ' + fmt(ov.duplicates != null ? ov.duplicates : 0) + ' duplicates merged'),
          tile('Regions and occupations', fmt(ov.provinces) + ' / ' + fmt(ov.occupations), 'regions with ads (of 34) / occupation groups'),
          tile('Ads with age wording', pct(aw, den), fmt(aw) + ' of ' + fmt(den) + ' ads (explicit or uncertain)'),
          tile('Most common stated limit', top ? 'under ' + top.age : 'None', top ? fmt(top.count) + ' of ' + fmt(den) + ' ads state this maximum age' : 'no maximum age stated'));
      }

      // ---- featured regional + industry map: open by default, WebGL created only when it first scrolls into view
      const panelId = 'data-map-panel';
      const holder = h('div.dt-mapholder', {}, h('p.hint.dt-wait', { role: 'status' }, 'The map loads when you scroll to it.'));
      const panel = h('div.dt-panel', { id: panelId, role: 'region', 'aria-label': 'Regional and industry map' }, holder);
      const collapse = h('button.btn.btn-quiet.dt-collapse', { type: 'button', 'aria-expanded': 'true', 'aria-controls': panelId }, 'Collapse map');
      const jump = h('button.btn.btn-primary.dt-toggle', { type: 'button' }, 'Explore the regional map');
      let view = null, loading = false, expanded = true, gone = false, seen = false;
      async function load() {
        if (view || loading || gone) return;
        loading = true;
        holder.replaceChildren(h('p.hint.dt-wait', { role: 'status' }, h('span.spinner'), ' Loading the map…'));
        try {
          await AL.loadScript('js/mapcore.js');
          if (gone) return;
          const v = await AL.mapView(holder);
          if (gone) { v.dispose(); return; }
          view = v; AL._mapView = v; view.setVisible(expanded);
        } catch (e) {
          holder.replaceChildren(h('div.notice.error', { role: 'alert' }, 'The map could not load: ' + e.message + ' Use the evidence explorer instead, or reload to try again.'));
        } finally { loading = false; }
      }
      function setExpanded(v) {
        expanded = v;
        collapse.setAttribute('aria-expanded', String(v));
        collapse.textContent = v ? 'Collapse map' : 'Expand map';
        panel.hidden = !v;
        if (view) view.setVisible(v);
        else if (v && seen) load();
      }
      collapse.addEventListener('click', () => setExpanded(!expanded));
      jump.addEventListener('click', async () => {
        if (!expanded) setExpanded(true);
        panel.scrollIntoView({ behavior: AL.motion.reduced() ? 'auto' : 'smooth', block: 'start' });
        seen = true; await load();
        const st = holder.querySelector('.mp-stage'); if (st) st.focus({ preventScroll: true });
      });
      const io = 'IntersectionObserver' in window ? new IntersectionObserver((es) => {
        if (es.some((e) => e.isIntersecting)) { seen = true; io.disconnect(); if (expanded) load(); }
      }, { rootMargin: '0px 0px 240px 0px' }) : null;
      if (io) io.observe(panel); else { seen = true; load(); }
      AL.onLeave(() => { gone = true; if (io) io.disconnect(); if (view) { view.dispose(); view = null; AL._mapView = null; } });

      // the tiles and the explorer use the simulated set; the map below can also show the real-data aggregate (mapcore.js)
      const realBadge = h('span.badge.mint', { hidden: true });  // same style as the map's real-data badge
      const realLine = h('span');
      AL.api('/api/real/status').then((st) => {
        if (!st || !st.available) return;
        const y = Array.isArray(st.years) && st.years.length ? st.years[0] + '–' + st.years[st.years.length - 1] : '';
        realBadge.textContent = 'Map: real data'; realBadge.hidden = false;
        realLine.textContent = ' The map defaults to ' + (st.rows_used / 1e6).toFixed(1) + ' million real Zhaopin job ads posted ' + y + '; you can switch it back to the simulated set.';
      }).catch(() => {});
      el.append(h('div.wrap.section.dt', {},
        h('div.dt-head', {}, h('h2', {}, 'The data at a glance'), h('span.badge.sim', {}, 'Demo · Synthetic data'), realBadge),
        h('p.dt-lead', {}, 'The tiles below and the evidence explorer use a fictional, reproducible set of job ads built for this demo' + (version ? ' (data version ' + version + ')' : '') + '.', realLine, ' All of these are counts of ad wording, not unemployment, hiring or rejection rates.'),
        tiles,
        h('div.dt-actions', {}, jump, h('a.btn.btn-secondary', { href: '#/explore' }, 'Open the evidence explorer')),
        h('div.dt-maphead', {}, h('div', {}, h('h3', {}, 'Where and in which jobs age wording appears'),
          h('p.hint', {}, 'Compare regions within one industry, or industries within one region. Pick a metric and an industry, then select a region.')), collapse),
        panel));
    },
  });
})();
