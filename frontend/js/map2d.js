/* AgeLens 2D map engine: interactive SVG with the same projected geometry and metric model as the 3D map, drawn like an
   ink sketch: brown outlines, flat pastel fills, a hard offset shadow under the country, pen hatching on low-n regions.
   Used when WebGL is unavailable/lost or via the 3D/2D toggle. No render loop: the DOM changes only on interaction.
   Motion: fill colours cross-fade with a CSS transition, fly-to tweens the viewBox (~600 ms), the selected region gets
   one CSS pulse ring. All of it is skipped under reduced motion. Keyboard is handled by mapcore.js. */
(function () {
  const AL = (window.AgeLens = window.AgeLens || { pages: {} });
  const NS = 'http://www.w3.org/2000/svg';
  const TOP = '#F4EEE9', TOP_ZERO = '#FFFFFF', INK = '#4A3728', PINK_INK = '#B23A5E';   // paper regions, brown ink edges
  const sv = (tag, attrs) => { const e = document.createElementNS(NS, tag); for (const k in attrs || {}) if (attrs[k] != null) e.setAttribute(k, attrs[k]); return e; };
  const ease = (k) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);

  AL.map2d = {
    create(o) {
      const stage = o.stage, stats = { updates: 0, frames: 0, draws: 0, flies: 0, disposedAll: false };
      let X0 = 1e9, Y0 = 1e9, X1 = -1e9, Y1 = -1e9;
      o.regions.forEach((r) => { X0 = Math.min(X0, r.bbox[0]); Y0 = Math.min(Y0, r.bbox[1]); X1 = Math.max(X1, r.bbox[2]); Y1 = Math.max(Y1, r.bbox[3]); });
      const MW = X1 - X0, MH = Y1 - Y0, PAD = 3;
      const full = { x: X0 - PAD, y: -Y1 - PAD, w: MW + 2 * PAD, h: MH + 2 * PAD };
      let vb = { ...full }, home = { ...full }, model = null, selected = null, hover = null, disposed = false, ptr = null, W = 0, H = 0, flyRaf = 0;
      const svg = sv('svg', { class: 'mp-svg', 'aria-hidden': 'true', focusable: 'false', preserveAspectRatio: 'xMidYMid meet' });
      const defs = sv('defs');
      const pat = sv('pattern', { id: 'mp-hatch', width: 0.9, height: 0.9, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' });
      pat.append(sv('rect', { width: 0.9, height: 0.9, fill: '#EDE4DC' }), sv('line', { x1: 0, y1: 0, x2: 0, y2: 0.9, stroke: '#8B7B6A', 'stroke-width': 1.4, 'vector-effect': 'non-scaling-stroke' }));
      // low-n overlay: light pen strokes laid over the region's own fill
      const low = sv('pattern', { id: 'mp-lown', width: 0.8, height: 0.8, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(-35)' });
      low.append(sv('line', { x1: 0, y1: 0, x2: 0, y2: 0.8, stroke: '#FFFFFF', 'stroke-width': 1.6, 'stroke-opacity': 0.75, 'vector-effect': 'non-scaling-stroke' }));
      defs.append(pat, low); svg.append(defs);
      const gS = sv('g', { 'pointer-events': 'none', class: 'mp-shadow' }), gR = sv('g'), gLow = sv('g', { 'pointer-events': 'none' }), gTop = sv('g', { 'pointer-events': 'none' }), gM = sv('g', { 'pointer-events': 'none' }), gL = sv('g', { 'pointer-events': 'none' });
      svg.append(gS, gR, gLow, gTop, gM, gL);
      const paths = new Map();
      const byName = new Map(o.regions.map((r) => [r.name, r]));
      o.regions.forEach((rg) => {
        const d = rg.polys.map((poly) => poly.map((ring) => 'M' + ring.map((p) => p[0].toFixed(2) + ' ' + (-p[1]).toFixed(2)).join('L') + 'Z').join('')).join('');
        const p = sv('path', { d, 'fill-rule': 'evenodd', stroke: INK, 'stroke-width': 1.3, 'vector-effect': 'non-scaling-stroke', 'stroke-linejoin': 'round', class: 'mp-path' });
        p.style.fill = TOP; p.dataset.name = rg.name; gR.append(p); paths.set(rg.name, p);
        gS.append(sv('path', { d, 'fill-rule': 'evenodd', fill: INK, stroke: INK, 'stroke-width': 1.3, 'vector-effect': 'non-scaling-stroke' }));
      });
      // hover/selection outline drawn on top of all regions (a <use> clone keeps neighbours from covering the stroke)
      const hovUse = sv('use', { class: 'mp-hov', fill: 'none', stroke: INK, 'stroke-width': 3, 'vector-effect': 'non-scaling-stroke' });
      const selUse = sv('use', { class: 'mp-selo', fill: 'none', stroke: PINK_INK, 'stroke-width': 3.4, 'vector-effect': 'non-scaling-stroke' });
      gTop.append(selUse, hovUse);
      const tipEl = document.createElement('div'); tipEl.className = 'mp-tip'; tipEl.hidden = true; tipEl.setAttribute('aria-hidden', 'true');
      stage.prepend(svg); stage.append(tipEl);
      const on = [];
      const listen = (t, ev, fn, opt) => { t.addEventListener(ev, fn, opt); on.push([t, ev, fn, opt]); };

      function applyVB() {
        svg.setAttribute('viewBox', vb.x.toFixed(2) + ' ' + vb.y.toFixed(2) + ' ' + vb.w.toFixed(2) + ' ' + vb.h.toFixed(2));
        const k = 3 / pxPerUnit(); gS.setAttribute('transform', 'translate(' + k.toFixed(3) + ' ' + k.toFixed(3) + ')');   // shadow: 3 px down-right at any zoom
      }
      function pxPerUnit() { return Math.min(W / vb.w, H / vb.h) || 1; }
      function style(name) {
        const p = paths.get(name), it = model && model.items.get(name); if (!p) return;
        let fill = TOP;
        if (it) fill = it.state === 'value' ? it.color : it.state === 'unmatched' ? 'url(#mp-hatch)' : it.state === 'zero' ? TOP_ZERO : TOP;
        if (p.style.fill !== fill) p.style.fill = fill;
      }
      function outlines() {
        const id = (n) => { const p = paths.get(n); if (!p) return null; if (!p.id) p.id = 'mp-r-' + o.regions.findIndex((r) => r.name === n); return '#' + p.id; };
        const hv = hover && hover !== selected ? id(hover) : null, sl = selected ? id(selected) : null;
        if (hv) { hovUse.setAttribute('href', hv); hovUse.style.display = ''; } else hovUse.style.display = 'none';
        if (sl) { selUse.setAttribute('href', sl); selUse.style.display = ''; } else selUse.style.display = 'none';
      }
      function markers() {
        gM.replaceChildren();
        if (!model) return;
        const u = pxPerUnit();
        model.items.forEach((it, name) => {
          if (it.state !== 'zero') return; const rg = byName.get(name);
          gM.append(sv('circle', { cx: rg.center[0], cy: -rg.center[1], r: 5 / u, fill: 'none', stroke: INK, 'stroke-width': 1.8, 'vector-effect': 'non-scaling-stroke' }));
        });
        const rg = selected && byName.get(selected);
        if (rg) {
          const cx = rg.center[0], cy = -rg.center[1];
          gM.append(sv('circle', { cx, cy, r: 6 / u, fill: '#FFB6C1', stroke: INK, 'stroke-width': 2, 'vector-effect': 'non-scaling-stroke' }));
          if (!o.reduced()) gM.append(sv('circle', { cx, cy, r: 6 / u, fill: 'none', stroke: PINK_INK, 'stroke-width': 1.8, 'vector-effect': 'non-scaling-stroke', class: 'mp-pulse' }));
        }
      }
      function labels() {
        gL.replaceChildren();
        if (!model) return;
        const want = []; const add = (n) => { if (n && want.indexOf(n) < 0) want.push(n); };
        add(selected); add(hover);
        model.ranked.slice(0, 5).forEach((i) => add(i.name));
        const k = 1 / pxPerUnit(), placed = [];
        want.forEach((n) => {
          const it = model.items.get(n), rg = byName.get(n); if (!it || !rg) return;
          const txt = it.en + (it.state === 'value' || it.state === 'zero' ? ' ' + AL.mapCore.fmtVal(model.metric, it.value) + (it.tier ? '*' : '') : '');
          const w = (txt.length * 7 + 12) * k, hh = 20 * k, cx = rg.center[0], cy = -rg.center[1] - 8 * k;
          const r = [cx - w / 2, cy - hh, cx + w / 2, cy];
          const strong = n === selected || n === hover;
          if (!strong && placed.some((p) => r[0] < p[2] && r[2] > p[0] && r[1] < p[3] && r[3] > p[1])) return;
          placed.push(r);
          const t = sv('text', { x: cx, y: cy - 3 * k, 'text-anchor': 'middle', 'font-size': 14 * k, class: 'mp-svgl' + (strong ? ' strong' : ''), 'stroke-width': 4 * k });
          t.textContent = txt; gL.append(t);
        });
      }
      function lowN() {   // pen hatching over regions whose value rests on few ads
        gLow.replaceChildren();
        if (!model) return;
        model.items.forEach((it, name) => {
          if (it.state !== 'value' || !it.tier) return; const p = paths.get(name);
          gLow.append(sv('path', { d: p.getAttribute('d'), 'fill-rule': 'evenodd', fill: 'url(#mp-lown)' }));
        });
      }
      function redrawAll() { stats.updates++; o.regions.forEach((r) => style(r.name)); lowN(); outlines(); markers(); labels(); }
      function placeTip(kbd) {
        if (tipEl.hidden) return;
        let x, y;
        if (kbd || !ptr) { const rg = byName.get(hover), u = pxPerUnit(); if (!rg) return; x = (rg.center[0] - vb.x) * u + 14; y = (-rg.center[1] - vb.y) * u - 10; }
        else { const r = stage.getBoundingClientRect(); x = ptr[0] - r.left + 14; y = ptr[1] - r.top + 14; }
        const w = tipEl.offsetWidth, hh = tipEl.offsetHeight;
        tipEl.style.transform = 'translate(' + Math.round(Math.max(4, Math.min(W - w - 4, x))) + 'px,' + Math.round(Math.max(4, Math.min(H - hh - 4, y))) + 'px)';
      }
      function setHover(n, fromPointer) {
        if (n === hover) return; hover = n;
        const t = n && model && o.tipLines(model.items.get(n), model);
        if (!t) tipEl.hidden = true;
        else { tipEl.replaceChildren(...t.map((s, i) => { const d = document.createElement(i ? 'div' : 'strong'); d.textContent = s; return d; })); tipEl.hidden = false; placeTip(!fromPointer); }
        outlines(); labels();
      }
      function clampVB() { vb.x = Math.max(full.x - vb.w * 0.2, Math.min(full.x + full.w - vb.w * 0.8, vb.x)); vb.y = Math.max(full.y - vb.h * 0.2, Math.min(full.y + full.h - vb.h * 0.8, vb.y)); }
      function animateVB(to, dur) {
        if (flyRaf) cancelAnimationFrame(flyRaf); flyRaf = 0;
        if (o.reduced() || !dur) { vb = { ...to }; applyVB(); redrawAll(); return; }
        const from = { ...vb }, t0 = performance.now();
        const step = () => {
          const k = Math.min(1, (performance.now() - t0) / dur), e = ease(k);
          vb = { x: from.x + (to.x - from.x) * e, y: from.y + (to.y - from.y) * e, w: from.w + (to.w - from.w) * e, h: from.h + (to.h - from.h) * e };
          applyVB(); stats.frames++;
          if (k < 1) flyRaf = requestAnimationFrame(step); else { flyRaf = 0; redrawAll(); }
        };
        flyRaf = requestAnimationFrame(step);
      }
      function zoomAt(f, fx, fy) {
        const nw = Math.max(home.w / 6, Math.min(home.w, vb.w / f)), r = nw / vb.w;
        const cx = vb.x + vb.w * fx, cy = vb.y + vb.h * fy;
        const to = { x: cx - (cx - vb.x) * r, y: cy - (cy - vb.y) * r, w: nw, h: vb.h * r };
        const keep = vb; vb = to; clampVB(); const t = { ...vb }; vb = keep; animateVB(t, 220);
      }
      function fitBox() {
        const a = W / H || 1.4; let w = full.w, h = full.h;
        if (w / h < a) w = h * a; else h = w / a;
        home = { x: full.x - (w - full.w) / 2, y: full.y - (h - full.h) / 2, w, h };
      }
      function pan(dx, dy) { vb = { ...vb, x: vb.x + dx * vb.w, y: vb.y + dy * vb.h }; clampVB(); applyVB(); redrawAll(); }
      function flyTo(n) {
        const rg = byName.get(n); if (!rg) return;
        stats.flies++;
        const w = Math.max(home.w / 2.6, Math.min(home.w, (rg.bbox[2] - rg.bbox[0]) * 3.2)), hh = w * (home.h / home.w);
        animateVB({ x: rg.center[0] - w / 2, y: -rg.center[1] - hh / 2, w, h: hh }, 620);
      }

      let down = null;
      listen(svg, 'pointerdown', (e) => { down = { x: e.clientX, y: e.clientY, vx: vb.x, vy: vb.y, moved: false }; try { svg.setPointerCapture(e.pointerId); } catch (er) { /* ignore */ } });
      listen(svg, 'pointermove', (e) => {
        ptr = [e.clientX, e.clientY];
        if (down && e.buttons) {
          const dx = e.clientX - down.x, dy = e.clientY - down.y;
          if (Math.hypot(dx, dy) > 4) down.moved = true;
          if (down.moved) { const u = pxPerUnit(); vb.x = down.vx - dx / u; vb.y = down.vy - dy / u; clampVB(); applyVB(); if (hover) { setHover(null, true); o.onHover(null); } }
          return;
        }
        if (e.pointerType === 'touch') return;
        const el = document.elementFromPoint(e.clientX, e.clientY), t = el && el.closest ? el.closest('.mp-path') : null, n = t ? t.dataset.name : null;
        if (n !== hover) { setHover(n, true); o.onHover(n); } else placeTip(false);
      });
      listen(svg, 'pointerup', (e) => {
        const d = down; down = null; if (d && d.moved) { redrawAll(); return; }
        const el = document.elementFromPoint(e.clientX, e.clientY), t = el && el.closest ? el.closest('.mp-path') : null; if (t) o.onSelect(t.dataset.name);
      });
      listen(svg, 'pointerleave', () => { ptr = null; if (hover) { setHover(null, true); o.onHover(null); } });
      listen(stage, 'wheel', (e) => {
        if (document.activeElement !== stage && !e.ctrlKey && !e.metaKey) return;
        e.preventDefault(); const r = svg.getBoundingClientRect(); zoomAt(e.deltaY < 0 ? 1.2 : 1 / 1.2, (e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height);
      }, { passive: false });

      function resize() {
        if (disposed) return; const w = stage.clientWidth, h = stage.clientHeight; if (w < 10 || h < 10) return;
        const atHome = vb.w === home.w && vb.x === home.x;
        W = w; H = h; fitBox(); if (atHome || !svg.hasAttribute('viewBox')) vb = { ...home }; applyVB(); redrawAll();
      }
      function resetView() { animateVB({ ...home }, 520); }
      const ro = 'ResizeObserver' in window ? new ResizeObserver(() => resize()) : null; if (ro) ro.observe(stage);
      return {
        stats, name: '2d',
        setModel(m) { model = m; redrawAll(); },
        setSelected(n, opt) { selected = n; redrawAll(); if (n && opt && opt.fly) flyTo(n); },
        setHover(n) { setHover(n, false); },
        resetView, zoom(f) { zoomAt(f, 0.5, 0.5); }, rotate(dx, dy) { pan(dx * 0.06, dy * 0.06); }, resize, noteInteraction() {},
        setActive() {},
        dispose() { if (disposed) return; disposed = true; if (flyRaf) cancelAnimationFrame(flyRaf); on.forEach(([t, ev, fn, opt]) => t.removeEventListener(ev, fn, opt)); if (ro) ro.disconnect(); svg.remove(); tipEl.remove(); stats.disposedAll = true; },
      };
    },
  };
})();
