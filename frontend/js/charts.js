/* AgeLens charts: small dependency-free SVG charts. window.AgeLens.charts */
(function () {
  const AL = (window.AgeLens = window.AgeLens || { pages: {} });
  const NS = 'http://www.w3.org/2000/svg';
  function s(tag, attrs, kids) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs || {}) if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    (kids || []).forEach((c) => e.append(c));
    return e;
  }
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  const fmt = (n) => (typeof n === 'number' ? n.toLocaleString('en-US') : '–');
  /* Motion: Web Animations on transform/opacity only (bars grow with a short overshoot, rows glide to new places = FLIP);
     nothing animates under AgeLens.motion.reduced(). Colours: white -> blue -> violet, from the design tokens. */
  const motionOK = () => !(AL.motion && AL.motion.reduced()) && typeof Element.prototype.animate === 'function';
  const SPRING = 'cubic-bezier(.22,.9,.3,1)';
  function grow(node, axis, from, to, delay) {
    if (!motionOK() || Math.abs(to - from) < 0.004) return;
    const f = (v) => 'scale' + axis + '(' + Math.max(0, v).toFixed(4) + ')';
    node.animate([{ transform: f(from) }, { transform: f(to + (to - from) * 0.06), offset: 0.7 }, { transform: f(to) }], { duration: 700, delay: delay || 0, easing: SPRING, fill: 'backwards' });
  }
  let gid = 0;

  /**
   * Max-age distribution as SVG columns. rows: [{max_age, count}]. opts: {highlight:35, selected:n|null, onSelect(age), label}
   * Column click/Enter/Space selects an age. Redraws on container resize.
   */
  function distribution(host, rows, opts) {
    opts = opts || {};
    const hl = opts.highlight == null ? 35 : opts.highlight;
    host.replaceChildren();
    const data = (rows || []).filter((r) => r && r.max_age != null).map((r) => ({ age: +r.max_age, n: +r.count || 0 }));
    if (!data.length) { host.append(el('p', 'hint', 'No ads with a stated maximum age in this scope.')); return { destroy() {} }; }
    const map = new Map(data.map((d) => [d.age, d.n]));
    let lo = Math.min.apply(null, data.map((d) => d.age)), hi = Math.max.apply(null, data.map((d) => d.age));
    if (hi - lo > 60) { lo = hi - 60; }
    const ages = [];
    for (let a = lo; a <= hi; a++) ages.push(a);
    const max = Math.max.apply(null, data.map((d) => d.n)) || 1;
    let ro = null, lastW = 0;
    const prevH = host._chPrev || new Map();   // previous column heights (per host) so a refresh grows from where it was
    const nextH = new Map();
    const id = 'chg' + (++gid);

    function draw(animate) {
      const W = Math.max(280, host.clientWidth || 320), H = 220;
      lastW = W;
      const padL = 34, padR = 8, padT = 22, padB = 30;
      const iw = W - padL - padR, ih = H - padT - padB;
      const step = iw / ages.length, bw = Math.max(2, Math.min(28, step * 0.72));
      const svg = s('svg', { width: W, height: H, viewBox: '0 0 ' + W + ' ' + H, role: 'group', 'aria-label': opts.label || 'Distribution of stated maximum age' });
      const grad = (gidn, a, b) => s('linearGradient', { id: gidn, x1: 0, y1: 1, x2: 0, y2: 0 }, [s('stop', { offset: 0, 'stop-color': a }), s('stop', { offset: 1, 'stop-color': b })]);
      svg.append(s('defs', {}, [grad(id + 'n', '#A8D8EA', '#C9E8F3'), grad(id + 'h', '#FF9FB0', '#FFC4CE')]));
      // gridlines + y ticks
      [0, 0.5, 1].forEach((f) => {
        const y = padT + ih - ih * f;
        svg.append(s('line', { x1: padL, x2: W - padR, y1: y, y2: y, stroke: 'var(--line)', 'stroke-width': 1 }));
        const t = s('text', { x: padL - 6, y: y + 4, 'text-anchor': 'end', 'font-size': 11, fill: 'var(--ink-soft)' });
        t.textContent = fmt(Math.round(max * f));
        svg.append(t);
      });
      const every = step < 14 ? 5 : step < 22 ? 2 : 1;
      ages.forEach((a, i) => {
        const n = map.get(a) || 0;
        const x = padL + i * step + (step - bw) / 2;
        const h = Math.max(n ? 2 : 0, (n / max) * ih);
        const isHl = a === hl, isSel = opts.selected === a;
        const g = s('g', { tabindex: n ? 0 : null, role: n ? 'button' : null, 'aria-label': n ? 'Stated maximum age ' + a + ': ' + fmt(n) + ' ads' + (isSel ? ' (selected)' : '') : null, 'aria-pressed': n ? String(isSel) : null, class: 'ch-col' + (n ? ' has' : '') });
        const title = s('title'); title.textContent = 'Max age ' + a + ': ' + fmt(n) + ' ads'; g.append(title);
        const r = s('rect', { x, width: bw, y: padT + ih - h, height: h, rx: Math.min(4, bw / 2), fill: 'url(#' + id + (isHl ? 'h' : 'n') + ')', stroke: isSel ? '#B23A5E' : '#4A3728', 'stroke-width': isSel ? 3 : 1.8, class: 'ch-rect' + (isHl ? ' hl' : '') });
        nextH.set(a, h);
        g.append(r);
        if (n) {
          // generous hit area
          g.append(s('rect', { x: padL + i * step, width: step, y: padT, height: ih, fill: 'transparent' }));
          const act = () => opts.onSelect && opts.onSelect(a);
          g.addEventListener('click', act);
          g.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); act(); } });
        }
        svg.append(g);
        if (animate && h > 0) { const p = prevH.get(a); grow(r, 'Y', p != null ? Math.min(3, p / h) : 0, 1, p != null ? 0 : 120 + i * 9); }
        if (a % every === 0 || isHl) {
          const t = s('text', { x: padL + i * step + step / 2, y: H - 12, 'text-anchor': 'middle', 'font-size': 11, fill: isHl ? 'var(--ink)' : 'var(--ink-soft)', 'font-weight': isHl ? 700 : 400 });
          t.textContent = a; svg.append(t);
        }
        if (isHl && n) {
          const t = s('text', { x: padL + i * step + step / 2, y: Math.max(12, padT + ih - h - 6), 'text-anchor': 'middle', 'font-size': 11, 'font-weight': 700, fill: 'var(--ink)' });
          t.textContent = fmt(n); svg.append(t);
        }
      });
      const xl = s('text', { x: padL + iw / 2, y: H - 0.5, 'text-anchor': 'middle', 'font-size': 10.5, fill: 'var(--ink-soft)' });
      xl.textContent = 'Stated maximum age (years)'; svg.append(xl);
      host.replaceChildren(svg);
      host._chPrev = nextH;
    }
    draw(true);
    if ('ResizeObserver' in window) {
      let t = null;
      ro = new ResizeObserver(() => { if (Math.abs((host.clientWidth || 0) - lastW) > 8) { clearTimeout(t); t = setTimeout(() => draw(false), 120); } });
      ro.observe(host);
    }
    return { destroy() { if (ro) ro.disconnect(); } };
  }

  /**
   * Horizontal comparison bars (HTML label + SVG bar). items: [{key,label,value,share,num,den,sub}]
   * opts: {selected:key|null, onSelect(key), unit:'ads', empty:'text', valueText(item)}
   */
  function bars(host, items, opts) {
    opts = opts || {};
    // FLIP: remember where each keyed row and its bar were
    const prev = new Map();
    host.querySelectorAll('.ch-bars > li').forEach((li) => { prev.set(li.dataset.k, { y: li.getBoundingClientRect().top, s: +li.dataset.s }); });
    host.replaceChildren();
    if (!items || !items.length) { host.append(el('p', 'hint', opts.empty || 'No data in this scope.')); return; }
    const max = Math.max.apply(null, items.map((i) => i.value)) || 1;
    const list = el('ul', 'ch-bars');
    const fills = [];
    items.forEach((it) => {
      const li = el('li');
      const frac = Math.max(it.value > 0 ? 0.015 : 0, it.value / max);
      li.dataset.k = String(it.key); li.dataset.s = frac.toFixed(4);
      const sel = opts.selected != null && opts.selected === it.key;
      const b = el('button', 'ch-bar' + (sel ? ' selected' : ''));
      b.type = 'button';
      b.setAttribute('aria-pressed', String(sel));
      const txt = opts.valueText ? opts.valueText(it) : fmt(it.value) + ' ' + (opts.unit || 'ads');
      b.setAttribute('aria-label', it.label + ': ' + txt + (it.sub ? '; ' + it.sub : '') + (sel ? ' (selected, click to clear)' : ''));
      const name = el('span', 'ch-name', it.label);
      name.title = it.label; // full label when the column truncates it
      const fill = el('span', 'ch-fill' + (sel ? ' sel' : ''));
      fill.style.transform = 'scaleX(' + frac.toFixed(4) + ')';
      const svg = el('span', 'ch-track'); svg.setAttribute('aria-hidden', 'true'); svg.append(fill);
      fills.push([li, fill, frac]);
      const val = el('span', 'ch-val', txt);
      b.append(name, svg, val);
      if (it.sub) b.append(el('span', 'ch-sub', it.sub));
      b.addEventListener('click', () => opts.onSelect && opts.onSelect(it.key));
      li.append(b); list.append(li);
    });
    host.append(list);
    if (!motionOK()) return;
    let n = 0;
    fills.forEach(([li, fill, frac], i) => {
      const p = prev.get(li.dataset.k);
      if (p) {
        const dy = p.y - li.getBoundingClientRect().top;
        if (Math.abs(dy) > 0.5) li.animate([{ transform: 'translateY(' + dy + 'px)' }, { transform: 'none' }], { duration: 620, easing: SPRING });
        grow(fill, 'X', p.s, frac, 0);
      } else {
        if (prev.size) li.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 360, delay: 20 * n++, fill: 'backwards' });
        grow(fill, 'X', 0, frac, Math.min(i, 24) * 28);
      }
    });
  }

  AL.charts = { distribution, bars, fmt };
})();
