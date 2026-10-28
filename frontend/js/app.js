/* AgeLens shell: hash router + helpers + motion preference. Pages: AgeLens.pages[name] = {title, render(el, params)}. */
(function () {
  const AgeLens = (window.AgeLens = { pages: {} });

  /** h('div.card', {onclick}, 'text', child...) — safe DOM builder (text is never parsed as HTML; null/false kids skipped; arrays flattened). */
  AgeLens.h = function (sel, attrs, ...kids) {
    const idm = sel.match(/#([\w-]+)/);                 // 'p.hint#rvhelp' -> id="rvhelp"
    const [tag, ...cls] = sel.replace(/#[\w-]+/, '').split('.');
    const el = document.createElement(tag || 'div');
    if (cls.length) el.className = cls.join(' ');
    if (idm) el.id = idm[1];
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else if (k === 'text') el.textContent = v;
      else el.setAttribute(k, v === true ? '' : v);
    }
    // nested arrays of children are flattened at any depth (a stray array would otherwise render as "[object HTMLElement]")
    for (const kid of kids.flat(Infinity)) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(kid));
    return el;
  };

  /** api('/api/x', {method, json, headers, body}) -> parsed JSON; throws Error(message) with server's message; err.status set. */
  AgeLens.api = async function (path, opts = {}) {
    const init = { method: opts.method || (opts.json || opts.body ? 'POST' : 'GET'), headers: Object.assign({}, opts.headers) };
    const sess = AgeLens.session && AgeLens.session.token();
    if (sess && !init.headers.Authorization && path.startsWith('/api/')) init.headers.Authorization = 'Bearer ' + sess;
    if (opts.json) { init.body = JSON.stringify(opts.json); init.headers['Content-Type'] = 'application/json'; }
    else if (opts.body) init.body = opts.body;
    let res;
    try { res = await fetch(path, init); } catch (e) { const er = new Error('Cannot reach the AgeLens server. Check that it is still running, then try again.'); er.status = 0; throw er; }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      // public demo: the invite session is missing, expired or revoked: forget it and show the invite page
      if (res.status === 401 && data.invite_required) { AgeLens.session.clear(); AgeLens.access.signed_in = false; if (AgeLens.showGate) AgeLens.showGate(); }
      const er = new Error(data.error || 'Request failed (' + res.status + ').'); er.status = res.status; er.data = data; throw er;
    }
    return data;
  };

  const safeStore = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
  };
  AgeLens.store = safeStore;
  AgeLens.ownerTokens = {
    all() { try { return JSON.parse(safeStore.get('al_owner_tokens') || '{}'); } catch (e) { return {}; } },
    add(code, tok) { const a = this.all(); a[code] = tok; safeStore.set('al_owner_tokens', JSON.stringify(a)); },
  };

  /* Public demo only: the invite session (pages/access.js). This browser keeps the random session token and the code's
     label/role, never the invite code itself. AgeLens.access is the server's view, loaded at start. */
  const sessionListeners = [];
  AgeLens.access = { public: false, signed_in: false };
  AgeLens.session = {
    read() { try { const v = JSON.parse(safeStore.get('al_session') || 'null'); return v && v.token && (!v.expires_at || v.expires_at > new Date().toISOString()) ? v : null; } catch (e) { return null; } },
    token() { const v = this.read(); return v ? v.token : ''; },
    info() { return this.read() || {}; },
    set(token, info) { safeStore.set('al_session', JSON.stringify(Object.assign({ token }, info))); sessionListeners.forEach((f) => f()); },
    clear() { try { localStorage.removeItem('al_session'); } catch (e) {} sessionListeners.forEach((f) => f()); },
    onChange(fn) { sessionListeners.push(fn); },
  };
  /* Pro (pages/pro.js, backend/api_pro.py): this browser keeps the Pro session token and the code's label, never the code.
     status() asks the server for the wallet (credits left); the server alone decides whether a report may be made. */
  const proListeners = [];
  AgeLens.pro = {
    read() { try { return JSON.parse(safeStore.get('al_pro') || 'null'); } catch (e) { return null; } },
    token() { const v = this.read(); return v ? v.token : ''; },
    set(token, label) { safeStore.set('al_pro', JSON.stringify({ token, label })); proListeners.forEach((f) => f()); },
    clear() { try { localStorage.removeItem('al_pro'); } catch (e) {} proListeners.forEach((f) => f()); },
    onChange(fn) { proListeners.push(fn); },
    headers() { const t = this.token(); return t ? { 'X-Pro-Token': t } : {}; },
    async status() {
      if (!this.token()) return { active: false };
      const s = await AgeLens.api('/api/pro/status', { headers: this.headers() });
      if (!s.active) this.clear();  // revoked, expired or signed out elsewhere
      return s;
    },
  };
  /** True when the public demo needs an invite and this browser has no valid session. */
  AgeLens.needsInvite = () => !!AgeLens.access.invite && !AgeLens.session.token();

  /* ---- motion preference: OS setting OR the user's "Pause animation" toggle (a quiet link in the footers; it stays
     because the background animation runs continuously and WCAG 2.2.2 asks for a way to pause it) ---- */
  const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
  const sessionPaused = () => { try { return sessionStorage.getItem('al_motion_paused') === '1'; } catch (e) { return false; } };
  const setSessionPaused = (v) => { try { if (v) sessionStorage.setItem('al_motion_paused', '1'); else sessionStorage.removeItem('al_motion_paused'); } catch (e) {} };
  if (safeStore.get('al_motion') === 'paused') safeStore.set('al_motion', 'auto');   // migrate: an old persistent pause no longer applies
  const motionListeners = [];
  AgeLens.motion = {
    /* Motion plays by default. "Pause" lasts for this tab session only (sessionStorage), so a pause never silently
       sticks across visits; "on" (forcing motion despite an OS reduced-motion request) is remembered. */
    pref() { if (sessionPaused()) return 'paused'; return safeStore.get('al_motion') === 'on' ? 'on' : 'auto'; },
    userPaused() { return this.pref() === 'paused'; },
    reduced() { const p = this.pref(); return p === 'paused' || (p === 'auto' && mq.matches); },
    onChange(fn) { motionListeners.push(fn); },
    /** set(true) pauses; set(false) plays (forcing motion on if the OS asks for reduced motion). */
    set(paused) { setSessionPaused(paused); if (!paused) safeStore.set('al_motion', mq.matches ? 'on' : 'auto'); apply(); },
  };
  function apply() {
    const red = AgeLens.motion.reduced();
    document.documentElement.dataset.motion = red ? 'reduced' : 'full';
    document.querySelectorAll('.motion-toggle').forEach((b) => { b.setAttribute('aria-pressed', red ? 'true' : 'false'); b.textContent = red ? (AgeLens.motion.userPaused() ? 'Play animation' : 'Play animation (system: reduced)') : 'Pause animation'; });
    motionListeners.forEach((f) => { try { f(red); } catch (e) {} });
  }
  mq.addEventListener && mq.addEventListener('change', apply);
  /** A "Pause animation" / "Play animation" toggle; any number can exist (both footers), apply() keeps their labels in sync. */
  AgeLens.motionToggle = function () {
    const b = AgeLens.h('button.motion-toggle', { type: 'button', 'aria-pressed': 'false', onclick: () => AgeLens.motion.set(!AgeLens.motion.reduced()) }, 'Pause animation');
    setTimeout(apply, 0);
    return b;
  };
  AgeLens.reducedMotion = () => AgeLens.motion.reduced();

  /* ---- page-leave hooks: graphics modules register disposal here ---- */
  const leaveFns = [];
  AgeLens.onLeave = (fn) => leaveFns.push(fn);

  /** Scroll reveal: elements with .reveal fade in once; never re-hidden. */
  AgeLens.observeReveals = function (root) {
    const els = (root || document).querySelectorAll('.reveal:not(.in)');
    if (!('IntersectionObserver' in window)) return els.forEach((e) => e.classList.add('in'));
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }), { threshold: 0.12 });
    els.forEach((e) => io.observe(e));
  };

  const routes = [
    [/^\/?$/, 'home'], [/^\/explore$/, 'explore'], [/^\/seeker$/, 'seeker'],
    [/^\/evidence\/([\w-]+)$/, 'evidence'], [/^\/requests(?:\/([\w-]+))?$/, 'requests'], [/^\/reviewer(?:\/([\w-]+))?$/, 'reviewer'],
    [/^\/study\/score$/, 'score'], [/^\/study$/, 'study'], [/^\/about$/, 'about'], [/^\/access$/, 'access'], [/^\/pro$/, 'pro'],
  ];
  /** Small line icon for centred states (empty / sign-in / not found). Static SVG markup, no user text. */
  const ICONS = {
    search: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
    inbox: '<path d="M3.5 13.5l2.6-7.2A1.5 1.5 0 0 1 7.5 5.3h9a1.5 1.5 0 0 1 1.4 1l2.6 7.2v4.7a1.5 1.5 0 0 1-1.5 1.5h-14A1.5 1.5 0 0 1 3.5 18.2z"/><path d="M3.5 13.5H8l1.5 2.5h5l1.5-2.5h4.5"/>',
    lock: '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8.5 10.5V7.5a3.5 3.5 0 0 1 7 0v3"/>',
    compass: '<circle cx="12" cy="12" r="8.5"/><path d="M15.5 8.5l-2 5-5 2 2-5z"/>',
  };
  AgeLens.stateIcon = function (name) {
    const d = document.createElement('div'); d.className = 'state-ico'; d.setAttribute('aria-hidden', 'true');
    d.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' + (ICONS[name] || ICONS.search) + '</svg>';
    return d;
  };

  function setRoute(name, navKey, title) {
    document.querySelectorAll('[data-nav]').forEach((a) => { if (a.dataset.nav === navKey) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
    document.title = (title ? title + ' · ' : '') + 'AgeLens';
    document.body.dataset.route = name;
  }
  async function render() {
    const path = location.hash.replace(/^#/, '') || '/';
    const main = document.getElementById('main');
    while (leaveFns.length) { try { leaveFns.pop()(); } catch (e) {} }
    if (AgeLens.needsInvite() && AgeLens.pages.access) {  // public demo without a session: only the invite page, whatever the address
      setRoute('access', 'access', 'Invite code'); main.replaceChildren(); window.scrollTo(0, 0);
      AgeLens.pages.access.gate(main, () => render()); main.focus({ preventScroll: true }); return;
    }
    for (const [rx, name] of routes) {
      const m = path.split('?')[0].match(rx);
      if (!m) continue;
      const page = AgeLens.pages[name];
      setRoute(name, name === 'evidence' ? 'seeker' : name === 'score' ? 'study' : name, page && page.title);
      main.replaceChildren(); window.scrollTo(0, 0);
      try { await page.render(main, { id: m[1], query: new URLSearchParams(path.split('?')[1] || '') }); }
      catch (e) { main.replaceChildren(AgeLens.h('div.wrap.section', {}, AgeLens.h('div.notice.error', { role: 'alert' }, 'This page could not load: ' + e.message + ' Reload the page to try again.'))); }
      AgeLens.observeReveals(main); main.focus({ preventScroll: true });
      return;
    }
    setRoute('notfound', null, 'Page not found');
    main.replaceChildren(); window.scrollTo(0, 0);
    const h = AgeLens.h;
    main.append(h('div.wrap.section', {}, h('div.nf', { role: 'status' }, AgeLens.stateIcon('compass'), h('h1', {}, 'Page not found'),
      h('p.hint', {}, 'This address does not match a page in AgeLens. It may have been mistyped or come from an older link.'),
      h('a.btn.btn-primary', { href: '#/' }, 'Back to Overview'))));
    main.focus({ preventScroll: true });
  }
  /* Diagnostics: open #/?diag=1 to measure motion state, WebGL renderer and real frame rate in THIS browser.
     The result is shown in a small panel and posted to the local server (data/diag.json). */
  function runDiag() {
    const box = AgeLens.h('div', { style: 'position:fixed;right:12px;bottom:12px;z-index:99;max-width:420px;background:#fff;border:1px solid #CBD0D8;border-radius:10px;padding:10px 12px;font:12px/1.45 system-ui;box-shadow:0 8px 24px rgba(0,0,0,.12);white-space:pre-wrap' }, 'Diagnostics: measuring for 6 s…');
    document.body.append(box);
    setTimeout(() => {
      let n = 0, t0 = performance.now();
      const count = () => { n++; if (performance.now() - t0 < 3000) requestAnimationFrame(count); else finish(); };
      requestAnimationFrame(count);
      function finish() {
        let renderer = 'unknown', webgl = false;
        try { const c = document.createElement('canvas'), gl = c.getContext('webgl2') || c.getContext('webgl'); webgl = !!gl;
          const ext = gl && gl.getExtension('WEBGL_debug_renderer_info'); renderer = gl ? (ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)) : 'none';
          const lose = gl && gl.getExtension('WEBGL_lose_context'); if (lose) lose.loseContext(); } catch (e) { renderer = 'error: ' + e.message; }
        const neb = window.__nebula && window.__nebula.stats ? window.__nebula.stats() : null;
        const hero = document.querySelector('.xh');
        const d = { at: new Date().toISOString(), userAgent: navigator.userAgent, osReducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
          motionPref: AgeLens.motion.pref(), motionReduced: AgeLens.motion.reduced(), hidden: document.hidden, webgl, renderer,
          rafPerSecond: Math.round(n / 3), devicePixelRatio: window.devicePixelRatio, viewport: [innerWidth, innerHeight],
          heroState: hero ? hero.dataset.state : null, nebula: neb, gfxLog: AgeLens.gfx ? AgeLens.gfx.stats.log.slice(-8) : null };
        box.textContent = 'Diagnostics (sent to the local server):\n' + JSON.stringify(d, null, 1);
        fetch('/api/diag', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(d) }).catch(() => {});
      }
    }, 6000);
  }

  AgeLens.showGate = () => render();
  AgeLens.start = async function () {
    const nav = document.querySelector('#nav nav');
    const fl = document.querySelector('.foot .foot-links');
    if (fl) fl.insertBefore(AgeLens.motionToggle(), fl.querySelector('.foot-copy'));
    try { AgeLens.access = await AgeLens.api('/api/access/status'); } catch (e) { AgeLens.access = { public: false, signed_in: false }; }
    if (AgeLens.access.invite && !AgeLens.access.signed_in) AgeLens.session.clear();  // stale or revoked session
    // public demo: who you are signed in as, at the end of the nav; the Reviewer link only for reviewer codes
    const chip = AgeLens.h('a.nav-access', { href: '#/access', 'data-nav': 'access' });
    const paint = () => {
      const i = AgeLens.session.info(), on = !!AgeLens.access.invite && !!i.token;
      chip.hidden = !on; chip.textContent = on ? (i.label || 'Guest') + ' · ' + i.role : '';
      chip.setAttribute('aria-label', on ? 'Signed in with an invite code: ' + (i.label || 'guest') + ', ' + i.role : '');
      const rv = document.querySelector('.nav-reviewer'); if (rv) rv.hidden = !!AgeLens.access.public && i.role !== 'reviewer';  // public: desk not offered to visitors
    };
    if (nav) { nav.append(chip); AgeLens.session.onChange(paint); paint(); }
    // phones: the links fold into a "Menu" button; Quick check moves into the menu instead of floating over the page
    const header = document.getElementById('nav');
    if (nav && header) {
      nav.id = 'primary-nav';
      const menuBtn = AgeLens.h('button.nav-menu', { type: 'button', 'aria-expanded': 'false', 'aria-controls': 'primary-nav' },
        AgeLens.h('span.nav-menu-ico', { 'aria-hidden': 'true' }, AgeLens.h('i'), AgeLens.h('i'), AgeLens.h('i')), AgeLens.h('span.nav-menu-txt', {}, 'Menu'));
      const setMenu = (open) => { document.body.classList.toggle('nav-open', open); menuBtn.setAttribute('aria-expanded', String(open)); menuBtn.lastChild.textContent = open ? 'Close' : 'Menu'; };
      menuBtn.addEventListener('click', () => setMenu(!document.body.classList.contains('nav-open')));
      header.insertBefore(menuBtn, nav);
      const qc = AgeLens.h('button.nav-qc', { type: 'button' }, 'Quick check');
      qc.addEventListener('click', () => { setMenu(false); if (AgeLens.quickCheck) AgeLens.quickCheck.open(menuBtn); });
      nav.append(qc);
      nav.addEventListener('click', (e) => { if (e.target.closest('a')) setMenu(false); });
      addEventListener('hashchange', () => setMenu(false));
      addEventListener('keydown', (e) => { if (e.key === 'Escape' && document.body.classList.contains('nav-open')) { setMenu(false); menuBtn.focus(); } });
      document.addEventListener('click', (e) => { if (document.body.classList.contains('nav-open') && !header.contains(e.target)) setMenu(false); });
    }
    document.body.classList.toggle('public-demo', !!AgeLens.access.public);
    apply();
    // floating round "back to top" button (sketch style), shown after the first screen
    // back-to-top lives in js/fx.js (.x-top); this used to add a second, overlapping one
    const onScroll = () => { document.body.classList.toggle('nav-scrolled', window.scrollY > 24); };
    window.addEventListener('scroll', onScroll, { passive: true }); onScroll();
    window.addEventListener('hashchange', render); render();
    if (/[?&]diag=1/.test(location.hash)) runDiag();
  };
})();
