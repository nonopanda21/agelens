/* AgeLens 3D map engine (Three.js 0.160), "papercraft" style: real province boundaries cut from thick paper (constant,
   DECORATIVE thickness), tops filled flat with the metric colour, dark-brown ink outlines, a hard offset shadow plate under
   the country, and provinces that rise from a common paper base by their value (height + top colour carry the metric). Toon shading on the sides only, so the
   flat tops match the legend exactly.
   Motion (all skipped when AgeLens.motion.reduced(): final state is drawn at once):
     - intro, once on first view: slabs pop up from flat (west -> east), then provinces rise to their value in rank order;
     - metric / industry change: province heights and colours tween (~750 ms, small rank stagger);
     - hover: the slab lifts a little and gets a thicker ink outline; selection: lifts higher, pink outline, one ring pulse,
       eased fly-to;
     - idle sway: very slow (+-13 degrees, one 36 s cycle), only while this view is the active gfx loop and after 8 s
       without interaction anywhere in the map panel; any pointer/key/wheel input stops it at once.
   Rendering is on demand: frames run only while a tween, damping, fly or the idle sway is active.
   AgeLens.map3d.create(opts) -> Promise<engine>. Engine API documented in mapcore.js. */
(function () {
  const AL = (window.AgeLens = window.AgeLens || { pages: {} });
  const DEPTH = 1.1;        // the common paper base every province stands on (same for all, no data)
  const MAXBAR = 4.6;       // extra height of the largest value above the base, map units
  const LIFT = 0.55, SEL_LIFT = 1.1;   // hover / selection lift (decoration)
  const INK = '#4A3728', PINK_INK = '#B23A5E', PINK = '#FFB6C1';
  const TOP_NODATA = '#F4EEE9', TOP_UNM = '#EDE4DC', BAR0 = '#F4EEE9';
  const OUTLINE_W = 0.13, HOVER_W = 0.3, SEL_W = 0.36;   // half-widths of the ink ribbons, map units
  const SPECK = 1.4;        // rings smaller than this (map units) are islets: no ink ribbon / shadow, or the ink would swallow them
  const ringSize = (ring) => { let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9; ring.forEach(([x, y]) => { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }); return Math.max(x1 - x0, y1 - y0); };
  const IDLE_MS = 8000, ORBIT_MAX_MS = 36000, ORBIT_AMP = 0.22;
  const E = {
    inOut: (k) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2),
    out: (k) => 1 - Math.pow(1 - k, 3),
    outBack: (k) => { const c1 = 1.4, c3 = c1 + 1; return 1 + c3 * Math.pow(k - 1, 3) + c1 * Math.pow(k - 1, 2); },
    spring: (k) => { const c1 = 1.05, c3 = c1 + 1; return 1 + c3 * Math.pow(k - 1, 3) + c1 * Math.pow(k - 1, 2); },
  };

  AL.map3d = {
    async create(o) {
      const THREE = await import('three');
      const { OrbitControls } = await import('three/addons/controls/OrbitControls.js');
      const stage = o.stage;
      const stats = { frames: 0, draws: 0, picks: 0, tweensRun: 0, intro: 'pending', orbitMs: 0, flies: 0,
        created: { geometries: 0, materials: 0, textures: 0 }, disposed: { geometries: 0, materials: 0, textures: 0 },
        buildMs: 0, lastDrawMs: 0, drawMsSum: 0, disposedAll: false, gfxLog: [] };
      const owned = { geometries: [], materials: [], textures: [] };
      const own = (kind, obj) => { owned[kind].push(obj); stats.created[kind]++; return obj; };
      let disposed = false, visible = false, onscreen = false, dirty = true, raf = 0, pickRaf = 0, userMoved = false, sizeW = 0, sizeH = 0;
      let orbitBase = 0, gfxOn = false, lastInteract = performance.now(), orbitSpent = 0, orbiting = false, wakeT = 0, lastFrameT = 0, dragging = false;

      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' });
      renderer.setPixelRatio(o.pixelRatio());
      renderer.setClearColor(0x000000, 0);
      const canvas = renderer.domElement;
      canvas.className = 'mp-canvas';
      canvas.setAttribute('aria-hidden', 'true');
      stage.prepend(canvas);

      const scene = new THREE.Scene();
      scene.add(new THREE.HemisphereLight(0xffffff, 0xE9DDD2, 1.25));
      const sun = new THREE.DirectionalLight(0xffffff, 1.7); sun.position.set(-40, 70, 60); scene.add(sun);
      const camera = new THREE.PerspectiveCamera(30, 1, 1, 1000);
      const controls = new OrbitControls(camera, canvas);
      controls.enableDamping = !o.reduced();
      controls.dampingFactor = 0.12;
      controls.rotateSpeed = 0.7; controls.panSpeed = 0.7; controls.zoomSpeed = 0.8;
      controls.maxPolarAngle = 1.32; controls.minPolarAngle = 0.08;
      controls.screenSpacePanning = false;
      controls.touches = { ONE: THREE.TOUCH.ROTATE, TWO: THREE.TOUCH.DOLLY_PAN };
      canvas.style.touchAction = 'pan-y'; // one-finger vertical swipes keep scrolling the page; two fingers pan/zoom, buttons tilt

      // ---- bounds + home view
      let X0 = 1e9, Y0 = 1e9, X1 = -1e9, Y1 = -1e9;
      // frame the camera on the larger land masses; far-flung islets would otherwise shrink the whole map
      o.regions.forEach((r) => r.polys.forEach((poly) => { if (ringSize(poly[0]) < SPECK * 3) return; poly[0].forEach(([x, y]) => { X0 = Math.min(X0, x); Y0 = Math.min(Y0, y); X1 = Math.max(X1, x); Y1 = Math.max(Y1, y); }); }));
      const CX = (X0 + X1) / 2, CY = (Y0 + Y1) / 2, MW = X1 - X0, MH = Y1 - Y0;
      const HOME_PHI = 0.86, HOME_THETA = 0.0;
      let homeDist = 150;
      const wx = (x) => x - CX, wz = (y) => -(y - CY); // world from projected (north = -z)
      function fit() {
        const t = Math.tan((camera.fov * Math.PI) / 360);
        const ev = MH * Math.cos(HOME_PHI) + (MAXBAR + 3) * Math.sin(HOME_PHI);
        homeDist = 0.96 * Math.max(ev / (2 * t), MW / (camera.aspect * 2 * t));
        controls.minDistance = homeDist * 0.28; controls.maxDistance = homeDist * 1.45;
      }

      // ---- tweens (keyed: a new tween with the same key replaces the old one, starting from the current value)
      const tweens = new Map();
      let tweenSeq = 0;
      function tween(key, dur, step, opt) {
        opt = opt || {};
        if (o.reduced() || dur <= 0) { step(1); if (opt.done) opt.done(); requestRender(); return; }
        tweens.set(key || 'tw' + (++tweenSeq), { t0: performance.now() + (opt.delay || 0), dur, step, ease: opt.ease || E.inOut, done: opt.done });
        stats.tweensRun++; requestRender();
      }
      function runTweens(now) {
        if (!tweens.size) return false;
        for (const [k, tw] of tweens) {
          if (now < tw.t0) continue;
          const p = Math.min(1, (now - tw.t0) / tw.dur);
          tw.step(tw.ease(p));
          if (p >= 1) { tweens.delete(k); if (tw.done) tw.done(); }
        }
        return true;
      }

      // ---- shared resources
      const toonRamp = (() => {   // three flat tones on the province walls: the cut-paper look
        const t = own('textures', new THREE.DataTexture(new Uint8Array([150, 205, 255]), 3, 1, THREE.RedFormat));
        t.minFilter = t.magFilter = THREE.NearestFilter; t.generateMipmaps = false; t.needsUpdate = true; return t;
      })();
      function stripeTex(bg, ink, w) {   // diagonal hatch on a canvas; repeats in map units on the slab tops
        const c = document.createElement('canvas'); c.width = c.height = 16; const g = c.getContext('2d');
        g.fillStyle = bg; g.fillRect(0, 0, 16, 16); g.strokeStyle = ink; g.lineWidth = w;
        g.beginPath(); g.moveTo(-2, 18); g.lineTo(18, -2); g.moveTo(-2, 10); g.lineTo(10, -2); g.moveTo(6, 18); g.lineTo(18, 6); g.stroke();
        const t = own('textures', new THREE.CanvasTexture(c)); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(0.7, 0.7); t.colorSpace = THREE.SRGBColorSpace;
        return t;
      }
      let unmTex = null, lowTex = null;
      const unmatchedTex = () => unmTex || (unmTex = stripeTex(TOP_UNM, '#8B7B6A', 2));
      const lowNTex = () => lowTex || (lowTex = stripeTex('#FFFFFF', '#E2D6CB', 2.2));   // white x colour = colour; light stripes read as "unstable"

      // ---- province slabs (one group per region: lift moves the whole group; intro scales it from flat)
      const t0 = performance.now();
      const R = new Map(), meshes = [];
      const root = new THREE.Group(); scene.add(root);
      const labelsEl = document.createElement('div'); labelsEl.className = 'mp-lbls'; labelsEl.setAttribute('aria-hidden', 'true');
      const tipEl = document.createElement('div'); tipEl.className = 'mp-tip'; tipEl.hidden = true; tipEl.setAttribute('aria-hidden', 'true');
      stage.append(labelsEl, tipEl);
      const inkMat = own('materials', new THREE.MeshBasicMaterial({ color: INK, side: THREE.DoubleSide }));
      const inkLineMat = own('materials', new THREE.LineBasicMaterial({ color: INK }));
      const ringGeo = own('geometries', new THREE.RingGeometry(1.25, 1.62, 40)); ringGeo.rotateX(-Math.PI / 2);
      const zeroGeo = own('geometries', new THREE.RingGeometry(0.5, 0.82, 28)); zeroGeo.rotateX(-Math.PI / 2);
      const zeroMat = own('materials', new THREE.MeshBasicMaterial({ color: INK, side: THREE.DoubleSide }));
      const hovMat = own('materials', new THREE.MeshBasicMaterial({ color: INK, transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide }));
      const selMat = own('materials', new THREE.MeshBasicMaterial({ color: PINK_INK, transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide }));
      const ringMat = own('materials', new THREE.MeshBasicMaterial({ color: PINK_INK, transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide }));
      const pulseMat = own('materials', new THREE.MeshBasicMaterial({ color: PINK, transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide }));
      const ring = new THREE.Mesh(ringGeo, ringMat); ring.visible = false; ring.raycast = () => {}; ring.renderOrder = 4;
      const pulse = new THREE.Mesh(ringGeo, pulseMat); pulse.visible = false; pulse.raycast = () => {}; pulse.renderOrder = 4;

      /** flat ink ribbon along every ring of a region (an outline that keeps its width in map units, unlike GL lines) */
      function ribbon(rg, w, y, lo, hi) {   // rings with lo <= size < hi (default: every ring that is not a speck)
        lo = lo || SPECK; hi = hi || Infinity;
        const pos = [];
        rg.polys.forEach((poly) => poly.forEach((ring2) => {
          const rs = ringSize(ring2); if (rs < lo || rs >= hi) return;
          for (let i = 0; i < ring2.length; i++) {
            const a = ring2[i], b = ring2[(i + 1) % ring2.length];
            const ax = wx(a[0]), az = wz(a[1]), bx = wx(b[0]), bz = wz(b[1]);
            let nx = -(bz - az), nz = bx - ax; const L = Math.hypot(nx, nz) || 1; nx = (nx / L) * w; nz = (nz / L) * w;
            // segment quad, extended by w along the segment so neighbouring quads overlap at the joints
            const ex = ((bx - ax) / L) * w, ez = ((bz - az) / L) * w;
            const a0x = ax - ex, a0z = az - ez, b0x = bx + ex, b0z = bz + ez;
            pos.push(a0x - nx, y, a0z - nz, b0x - nx, y, b0z - nz, b0x + nx, y, b0z + nz, a0x - nx, y, a0z - nz, b0x + nx, y, b0z + nz, a0x + nx, y, a0z + nz);
          }
        }));
        const g = own('geometries', new THREE.BufferGeometry()); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
        return g;
      }

      // hard offset shadow plate (the reference's "2px 2px 0 brown" card shadow, in map units), drawn under every slab
      const allShapes = [];
      o.regions.forEach((rg) => {
        const shapes = rg.polys.map((poly) => {
          const s = new THREE.Shape(poly[0].map((p) => new THREE.Vector2(p[0] - CX, p[1] - CY)));
          for (let i = 1; i < poly.length; i++) s.holes.push(new THREE.Path(poly[i].map((p) => new THREE.Vector2(p[0] - CX, p[1] - CY))));
          return s;
        });
        rg._shapes = shapes; allShapes.push(...shapes.filter((sh, i) => ringSize(rg.polys[i][0]) >= SPECK));
      });
      {
        const sg = own('geometries', new THREE.ShapeGeometry(allShapes, 1)); sg.rotateX(-Math.PI / 2);
        const plate = new THREE.Mesh(sg, own('materials', new THREE.MeshBasicMaterial({ color: INK })));
        plate.position.set(0.9, -0.04, 1.1); plate.raycast = () => {}; scene.add(plate);
      }

      o.regions.forEach((rg) => {
        // islets stay at base height (rising tiny shapes would turn them into needles); the main land masses carry the value
        const big = rg._shapes.filter((sh, i) => ringSize(rg.polys[i][0]) >= SPECK * 2), isles = rg._shapes.filter((sh, i) => ringSize(rg.polys[i][0]) < SPECK * 2);
        const geo = own('geometries', new THREE.ExtrudeGeometry(big.length ? big : rg._shapes, { depth: DEPTH, bevelEnabled: false, curveSegments: 1 }));
        geo.rotateX(-Math.PI / 2); // extrude along +y, north becomes -z
        const isleGeo = big.length && isles.length ? own('geometries', new THREE.ExtrudeGeometry(isles, { depth: DEPTH, bevelEnabled: false, curveSegments: 1 })) : null;
        if (isleGeo) isleGeo.rotateX(-Math.PI / 2);
        delete rg._shapes;
        const top = own('materials', new THREE.MeshBasicMaterial({ color: TOP_NODATA }));
        const side = own('materials', new THREE.MeshToonMaterial({ color: TOP_NODATA, gradientMap: toonRamp }));
        const grp = new THREE.Group(); root.add(grp);
        const mesh = new THREE.Mesh(geo, [top, side]); mesh.userData.name = rg.name; grp.add(mesh); meshes.push(mesh);
        if (isleGeo) { const isle = new THREE.Mesh(isleGeo, [top, side]); isle.userData.name = rg.name; grp.add(isle); meshes.push(isle); }
        const cap = new THREE.Group(); grp.add(cap);   // everything on the top face rides up with the value height
        const outline = new THREE.Mesh(ribbon(rg, OUTLINE_W, DEPTH + 0.04, big.length ? SPECK * 2 : SPECK), inkMat); outline.raycast = () => {}; outline.renderOrder = 1; cap.add(outline);
        if (isleGeo) { const io = new THREE.Mesh(ribbon(rg, OUTLINE_W, DEPTH + 0.04, SPECK, SPECK * 2), inkMat); io.raycast = () => {}; io.renderOrder = 1; grp.add(io); }
        { // ink line round the foot of the slab
          const pos = [];
          rg.polys.forEach((poly) => poly.forEach((ring2) => { if (ringSize(ring2) < SPECK) return; for (let i = 0; i < ring2.length; i++) { const a = ring2[i], b = ring2[(i + 1) % ring2.length]; pos.push(wx(a[0]), 0.01, wz(a[1]), wx(b[0]), 0.01, wz(b[1])); } }));
          const lg = own('geometries', new THREE.BufferGeometry()); lg.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
          const foot = new THREE.LineSegments(lg, inkLineMat); foot.raycast = () => {}; grp.add(foot);
        }
        const cx = wx(rg.center[0]), cz = wz(rg.center[1]);
        const zero = new THREE.Mesh(zeroGeo, zeroMat); zero.position.set(cx, DEPTH + 0.07, cz); zero.visible = false; zero.raycast = () => {}; cap.add(zero);
        R.set(rg.name, { rg, grp, cap, mesh, top, side, zero, cx, cz, h: 0, hT: 0, lift: 0, hov: null, sel: null,
          col: new THREE.Color(BAR0), topCol: new THREE.Color(TOP_NODATA), it: null });
      });
      stats.buildMs = Math.round(performance.now() - t0);

      function hovFor(r) {
        if (!r.hov) { r.hov = new THREE.Mesh(ribbon(r.rg, HOVER_W, DEPTH + 0.06), hovMat); r.hov.raycast = () => {}; r.hov.renderOrder = 2; r.hov.visible = false; r.cap.add(r.hov); }
        return r.hov;
      }
      function selFor(r) {
        if (!r.sel) { r.sel = new THREE.Mesh(ribbon(r.rg, SEL_W, DEPTH + 0.08), selMat); r.sel.raycast = () => {}; r.sel.renderOrder = 3; r.sel.visible = false; r.cap.add(r.sel); }
        return r.sel;
      }

      // ---- model
      let model = null, selected = null, hover = null, ptr = null, introDone = false, introStarted = false, hovOwner = null;
      function targetsFor(it) {
        const hT = it && (it.state === 'value') && it.value > 0 ? Math.max(0.35, MAXBAR * it.t) : 0;
        const col = it && it.color ? it.color : BAR0;
        const top = !it ? TOP_NODATA : it.state === 'unmatched' ? TOP_UNM : it.state === 'zero' ? '#FFFFFF' : it.color || TOP_NODATA;
        return { hT, col, top };
      }
      const sideCol = new THREE.Color();
      function applyBar(r) {
        // the province itself rises: base sheet + value height; walls are the top colour a shade deeper (cut-paper sides)
        r.mesh.scale.y = (DEPTH + r.h) / DEPTH; r.cap.position.y = r.h;
        r.top.color.copy(r.topCol); r.side.color.copy(sideCol.copy(r.topCol).lerp(new THREE.Color(INK), 0.14));
      }
      function liftTarget(name) { return name === selected ? SEL_LIFT : name === hover ? LIFT : 0; }
      function finishIntro() { // a model change during the intro: jump to the end, then tween normally
        [...tweens.keys()].forEach((k) => { if (/^(rise|bar):|^intro-end$/.test(k)) tweens.delete(k); });
        R.forEach((r) => { r.grp.scale.y = 1; r.h = r.hT; r.col.set(r.colT || BAR0); r.topCol.set(r.topT || TOP_NODATA); applyBar(r); });
        introDone = true; stats.intro = 'done'; labelsEl.classList.add('in');
      }
      function setTopMap(r, it) {
        const want = it && it.state === 'unmatched' ? unmatchedTex() : it && it.state === 'value' && it.tier ? lowNTex() : null;
        if (r.top.map !== want) { r.top.map = want; r.top.needsUpdate = true; }
      }
      function setModel(m) {
        if (introStarted && !introDone) finishIntro();
        model = m;
        const order = m.ranked.map((i) => i.name);
        R.forEach((r, name) => {
          const it = m.items.get(name); r.it = it;
          const T = targetsFor(it);
          setTopMap(r, it);
          r.zero.visible = !!it && it.state === 'zero';
          r.hT = T.hT;
          if (!introDone) { r.colT = T.col; r.topT = T.top; return; } // intro will animate to these
          const h0 = r.h, c0 = r.col.clone(), tc0 = r.topCol.clone(), c1 = new THREE.Color(T.col), tc1 = new THREE.Color(T.top);
          const rk = order.indexOf(name), delay = rk < 0 ? 0 : Math.min(rk, 30) * 12;
          tween('bar:' + name, 760, (k) => { r.h = Math.max(0, h0 + (T.hT - h0) * k); const kc = Math.min(1, Math.max(0, k)); r.col.copy(c0).lerp(c1, kc); r.topCol.copy(tc0).lerp(tc1, kc); applyBar(r); dirty = true; }, { delay, ease: E.spring });
        });
        if (selected) placeRing();
        requestRender();
      }
      function runIntro() {
        if (introStarted || !model) return;
        introStarted = true; stats.intro = 'running';
        const order = model.ranked.map((i) => i.name);
        const finish = () => { introDone = true; stats.intro = 'done'; labelsEl.classList.add('in'); requestRender(); };
        R.forEach((r) => { r.col.set(r.colT || BAR0); r.topCol.set(TOP_NODATA); });
        if (o.reduced()) {
          R.forEach((r) => { r.grp.scale.y = 1; r.h = r.hT; r.topCol.set(r.topT || TOP_NODATA); applyBar(r); });
          finish(); return;
        }
        let last = 0;
        R.forEach((r, name) => {
          r.grp.scale.y = 0.02; r.h = 0; applyBar(r);
          const d = ((r.cx + MW / 2) / MW) * 420;
          const tc0 = new THREE.Color(TOP_NODATA), tc1 = new THREE.Color(r.topT || TOP_NODATA);
          tween('rise:' + name, 620, (k) => { r.grp.scale.y = Math.max(0.02, k); r.topCol.copy(tc0).lerp(tc1, Math.min(1, Math.max(0, k * 1.2))); applyBar(r); dirty = true; }, { delay: d, ease: E.outBack });
          const rk = order.indexOf(name), bd = 640 + (rk < 0 ? 0 : Math.min(rk, 33) * 38);
          last = Math.max(last, bd + 700);
          if (r.hT > 0) tween('bar:' + name, 760, (k) => { r.h = Math.max(0, r.hT * k); applyBar(r); dirty = true; }, { delay: bd, ease: E.spring });
        });
        tween('intro-end', 1, () => {}, { delay: last, done: finish });
      }

      // ---- render loop (on demand)
      const allowed = () => visible && onscreen && !document.hidden && !disposed;
      function requestRender() { dirty = true; schedule(); }
      function schedule() { if (!raf && allowed()) raf = requestAnimationFrame(frame); }
      function canOrbit(now) {
        return gfxOn && introDone && !o.reduced() && !hover && !dragging && !tweens.has('cam') && now - lastInteract > IDLE_MS && orbitSpent < ORBIT_MAX_MS;
      }
      function frame(now) {
        raf = 0; if (!allowed()) return;
        now = performance.now();
        const dt = lastFrameT ? Math.min(100, now - lastFrameT) : 16; lastFrameT = now;
        stats.frames++;
        let again = false;
        if (runTweens(now)) { dirty = true; again = tweens.size > 0; }
        if (canOrbit(now)) {
          if (!orbiting) orbitBase = ORBIT_AMP * Math.sin((2 * Math.PI * orbitSpent) / ORBIT_MAX_MS); // resume without a jump
          orbiting = true; const prevA = orbitBase; orbitSpent = Math.min(ORBIT_MAX_MS, orbitSpent + dt); stats.orbitMs = Math.round(orbitSpent);
          orbitBase = ORBIT_AMP * Math.sin((2 * Math.PI * orbitSpent) / ORBIT_MAX_MS);
          spin(orbitBase - prevA, 0); again = true;
        } else orbiting = false;
        const moved = controls.update();
        if (moved) { clampPan(); again = true; }
        if (dirty) { draw(); dirty = false; }
        if (again) schedule(); else lastFrameT = 0;
      }
      function clampPan() {
        const t = controls.target, mx = MW / 2, mz = MH / 2;
        const nx = Math.max(-mx, Math.min(mx, t.x)), nz = Math.max(-mz, Math.min(mz, t.z));
        if (nx !== t.x || nz !== t.z) { const d = new THREE.Vector3(nx - t.x, 0, nz - t.z); t.add(d); camera.position.add(d); }
      }
      controls.addEventListener('change', () => { requestRender(); });
      controls.addEventListener('start', () => { dragging = true; interact(); tweens.delete('cam'); userMoved = true; });
      controls.addEventListener('end', () => { dragging = false; interact(); });
      const v3 = new THREE.Vector3();
      function toScreen(x, y, z) { v3.set(x, y, z).project(camera); return [(v3.x * 0.5 + 0.5) * sizeW, (-v3.y * 0.5 + 0.5) * sizeH, v3.z]; }
      function draw() {
        const t = performance.now();
        renderer.render(scene, camera);
        updateLabels(); if (hover && !tipEl.hidden && (!ptr || tweens.has('cam'))) moveTip(true);
        stats.draws++; stats.lastDrawMs = Math.round((performance.now() - t) * 10) / 10; stats.drawMsSum += stats.lastDrawMs;
      }
      let labelEls = [];
      function labelText(it) {
        if (it.state === 'value' || it.state === 'zero') return it.en + ' ' + AL.mapCore.fmtVal(model.metric, it.value) + (it.tier ? '*' : '');
        return it.en;
      }
      function updateLabels() {
        if (!model) return;
        const want = [];
        const add = (n) => { if (n && want.indexOf(n) < 0) want.push(n); };
        add(selected); add(hover);
        model.ranked.slice(0, 5).forEach((i) => add(i.name));
        const placed = [], out = [];
        want.forEach((n) => {
          const it = model.items.get(n), r = R.get(n); if (!it || !r) return;
          const y = (DEPTH + r.h) * r.grp.scale.y + r.lift + 0.4;
          const [sx, sy, sz] = toScreen(r.cx, y, r.cz);
          if (sz > 1 || sx < -20 || sx > sizeW + 20 || sy < -10 || sy > sizeH + 10) return;
          const txt = labelText(it);
          const w = txt.length * 7.4 + 18, hh = 24, lx = Math.max(2, Math.min(sizeW - w - 2, sx - w / 2)), rc = [lx, sy - hh - 6, lx + w, sy - 6];
          const strong = n === selected || n === hover;
          if (!strong && placed.some((p) => rc[0] < p[2] + 4 && rc[2] > p[0] - 4 && rc[1] < p[3] + 2 && rc[3] > p[1] - 2)) return;
          placed.push(rc); out.push([txt, rc[0], rc[1], strong, n === selected]);
        });
        while (labelEls.length < out.length) { const d = document.createElement('span'); d.className = 'mp-lbl'; labelsEl.append(d); labelEls.push(d); }
        labelEls.forEach((d, i) => {
          const L = out[i]; if (!L) { d.hidden = true; return; }
          d.hidden = false; if (d.textContent !== L[0]) d.textContent = L[0];
          d.style.transform = 'translate(' + Math.round(L[1]) + 'px,' + Math.round(L[2]) + 'px)'; d.classList.toggle('strong', L[3]); d.classList.toggle('sel', L[4]);
        });
      }

      // ---- picking, hover, selection
      const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
      function pick(cx, cy) {
        const rc = canvas.getBoundingClientRect();
        ndc.set(((cx - rc.left) / rc.width) * 2 - 1, -((cy - rc.top) / rc.height) * 2 + 1);
        ray.setFromCamera(ndc, camera);
        const hits = ray.intersectObjects(meshes, false);
        stats.picks++;
        return hits.length ? hits[0].object.userData.name : null;
      }
      function liftTo(r) {
        const a = r.lift, v = liftTarget(r.rg.name);
        if (a === v) return;
        tween('lift:' + r.rg.name, 260, (k) => { r.lift = a + (v - a) * k; r.grp.position.y = r.lift; dirty = true; }, { ease: E.outBack });
      }
      function setHover(n, fromPointer) {
        if (n === hover) return;
        const prev = hover; hover = n;
        if (prev && R.get(prev)) liftTo(R.get(prev));
        if (n && R.get(n)) {
          const r = R.get(n); liftTo(r);
          if (hovOwner && hovOwner !== r && hovOwner.hov) hovOwner.hov.visible = false;
          hovFor(r).visible = true; hovOwner = r;
          const a0 = hovMat.opacity;
          tween('hov', 180, (k) => { hovMat.opacity = a0 + (1 - a0) * k; dirty = true; }, { ease: E.out });
        } else if (hovOwner) {
          const a0 = hovMat.opacity, owner = hovOwner;
          tween('hov', 160, (k) => { hovMat.opacity = a0 * (1 - k); dirty = true; }, { ease: E.out, done: () => { if (owner.hov && !hover) owner.hov.visible = false; } });
        }
        canvas.style.cursor = n && fromPointer ? 'pointer' : '';
        showTip(n, !fromPointer); requestRender();
      }
      function showTip(n, kbd) {
        const t = n && model && o.tipLines(model.items.get(n), model);
        if (!t) { tipEl.hidden = true; return; }
        tipEl.replaceChildren(...t.map((s, i) => { const d = document.createElement(i ? 'div' : 'strong'); d.textContent = s; return d; }));
        tipEl.hidden = false; moveTip(kbd);
      }
      function moveTip(kbd) {
        let x, y;
        if (kbd || !ptr) { const r = R.get(hover); const s = r ? toScreen(r.cx, (DEPTH + r.h) * r.grp.scale.y + r.lift + 1, r.cz) : [sizeW / 2, sizeH / 2]; x = s[0] + 16; y = s[1] - 10; }
        else { const rc = stage.getBoundingClientRect(); x = ptr[0] - rc.left + 14; y = ptr[1] - rc.top + 14; }
        const w = tipEl.offsetWidth, hh = tipEl.offsetHeight;
        tipEl.style.transform = 'translate(' + Math.round(Math.max(4, Math.min(sizeW - w - 4, x))) + 'px,' + Math.round(Math.max(4, Math.min(sizeH - hh - 4, y))) + 'px)';
      }
      function placeRing() {
        const r = selected && R.get(selected);
        if (!r) { ring.visible = pulse.visible = false; return; }
        if (ring.parent !== r.cap) { r.cap.add(ring); r.cap.add(pulse); }
        ring.position.set(r.cx, DEPTH + 0.1, r.cz); pulse.position.copy(ring.position);
        ring.visible = true;
      }
      function setSelected(n, opt) {
        opt = opt || {};
        const prev = selected; selected = n;
        if (prev && R.get(prev)) { const pr = R.get(prev); liftTo(pr); if (pr.sel) pr.sel.visible = false; }
        placeRing();
        if (n && R.get(n)) {
          const r = R.get(n);
          liftTo(r);
          selFor(r).visible = true;
          const a0 = ringMat.opacity, s0 = selMat.opacity;
          tween('ring', 280, (k) => { ringMat.opacity = a0 + (1 - a0) * k; ring.scale.setScalar(0.6 + 0.4 * k); selMat.opacity = s0 + (1 - s0) * k; dirty = true; }, { ease: E.outBack });
          if (!o.reduced()) {
            pulse.visible = true;
            tween('pulse', 1100, (k) => { pulse.scale.setScalar(1 + k * 2.4); pulseMat.opacity = 0.7 * (1 - k); dirty = true; },
              { ease: E.out, done: () => { pulse.visible = false; pulseMat.opacity = 0; } });
          }
          if (opt.fly) flyTo(n);
        } else { ringMat.opacity = 0; ring.visible = false; pulse.visible = false; selMat.opacity = 0; tweens.delete('pulse'); }
        requestRender();
      }

      // ---- camera: spherical tweens for fly-to / reset; spin for buttons, keys and the idle sway
      const sph = new THREE.Spherical();
      function camState() { sph.setFromVector3(camera.position.clone().sub(controls.target)); return { t: controls.target.clone(), r: sph.radius, phi: sph.phi, theta: sph.theta }; }
      function setCam(t, r, phi, theta) {
        controls.target.copy(t);
        camera.position.copy(t).add(new THREE.Vector3().setFromSphericalCoords(r, phi, theta));
        camera.lookAt(t);
      }
      function camTo(t1, r1, phi1, theta1, dur) {
        const a = camState();
        let dth = theta1 - a.theta; dth = ((dth + Math.PI) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI) - Math.PI;
        tween('cam', dur, (k) => { setCam(a.t.clone().lerp(t1, k), a.r + (r1 - a.r) * k, a.phi + (phi1 - a.phi) * k, a.theta + dth * k); dirty = true; }, { ease: E.inOut });
      }
      function flyTo(n) {
        const r = R.get(n); if (!r) return;
        stats.flies++; interact();
        const a = camState();
        camTo(new THREE.Vector3(r.cx * 0.85, 1, r.cz * 0.85), Math.max(controls.minDistance, homeDist * 0.8), Math.min(a.phi, 0.78), a.theta, 900);
        userMoved = true;
      }
      function goHome(instant) {
        const t = new THREE.Vector3(0, 1, 0);
        if (instant) { tweens.delete('cam'); setCam(t, homeDist, HOME_PHI, HOME_THETA); controls.update(); requestRender(); }
        else camTo(t, homeDist, HOME_PHI, HOME_THETA, 800);
        userMoved = false; orbitSpent = 0;
      }
      function spin(dTheta, dPhi) {
        const off = camera.position.clone().sub(controls.target);
        sph.setFromVector3(off);
        sph.theta += dTheta; sph.phi = Math.max(controls.minPolarAngle, Math.min(controls.maxPolarAngle, sph.phi + dPhi));
        off.setFromSpherical(sph); camera.position.copy(controls.target).add(off); camera.lookAt(controls.target); dirty = true;
      }
      function rotate(dx, dy) {
        interact();
        const a = camState();
        const phi1 = Math.max(controls.minPolarAngle, Math.min(controls.maxPolarAngle, a.phi + dy * 0.12));
        camTo(a.t, a.r, phi1, a.theta + dx * 0.25, 360); userMoved = true;
      }
      function zoom(f) {
        interact();
        const a = camState();
        camTo(a.t, Math.max(controls.minDistance, Math.min(controls.maxDistance, a.r / f)), a.phi, a.theta, 300); userMoved = true;
      }

      // ---- interaction bookkeeping for the idle sway
      function interact() {
        lastInteract = performance.now(); orbiting = false;
        clearTimeout(wakeT);
        if (!disposed) wakeT = setTimeout(() => { if (canOrbit(performance.now())) schedule(); }, IDLE_MS + 50);
      }
      const on = [];
      function listen(t, ev, fn, opt) { t.addEventListener(ev, fn, opt); on.push([t, ev, fn, opt]); }
      let down = null;
      listen(canvas, 'pointerdown', (e) => { interact(); down = [e.clientX, e.clientY]; });
      listen(canvas, 'pointerup', (e) => {
        if (!down) return; const moved = Math.hypot(e.clientX - down[0], e.clientY - down[1]); down = null;
        if (moved > 5) return;
        const n = pick(e.clientX, e.clientY); if (n) o.onSelect(n);
      });
      listen(canvas, 'pointermove', (e) => {
        if (e.pointerType === 'touch') return;
        interact();
        ptr = [e.clientX, e.clientY];
        if (e.buttons) { if (hover) { setHover(null, true); o.onHover(null); } return; }
        if (pickRaf) return;
        pickRaf = requestAnimationFrame(() => {
          pickRaf = 0; if (!allowed() || !ptr) return;
          const n = pick(ptr[0], ptr[1]);
          if (n !== hover) { setHover(n, true); o.onHover(n); } else if (!tipEl.hidden) moveTip(false);
        });
      });
      listen(canvas, 'pointerleave', () => { ptr = null; if (hover) { setHover(null, true); o.onHover(null); } });
      listen(canvas, 'webglcontextlost', (e) => { e.preventDefault(); o.onFail('graphics context lost'); });
      listen(stage, 'wheel', (e) => { interact(); if (document.activeElement !== stage && !e.ctrlKey && !e.metaKey) e.stopPropagation(); }, { capture: true, passive: true });
      listen(stage, 'keydown', () => interact());
      listen(stage, 'focusin', () => interact());

      // ---- size, visibility, lifecycle
      function resize() {
        if (disposed) return;
        const w = stage.clientWidth, hh = stage.clientHeight; if (w < 10 || hh < 10) return;
        if (w === sizeW && hh === sizeH) { maybeIntro(); return; }
        const first = !sizeW; sizeW = w; sizeH = hh;
        renderer.setPixelRatio(o.pixelRatio());
        renderer.setSize(w, hh, false); camera.aspect = w / hh; camera.updateProjectionMatrix();
        fit(); if (first || !userMoved) goHome(true);
        requestRender(); maybeIntro();
      }
      function maybeIntro() { if (!introStarted && model && sizeW && allowed()) runIntro(); }
      const ro = 'ResizeObserver' in window ? new ResizeObserver(() => { if (visible) resize(); }) : null; if (ro) ro.observe(stage);
      const io = 'IntersectionObserver' in window ? new IntersectionObserver((es) => {
        onscreen = es[es.length - 1].isIntersecting;
        if (onscreen) { resize(); requestRender(); maybeIntro(); } else if (raf) { cancelAnimationFrame(raf); raf = 0; }
      }, { threshold: 0.15 }) : null;
      if (io) io.observe(stage); else onscreen = true;
      listen(document, 'visibilitychange', () => { if (!document.hidden) requestRender(); });
      const gh = o.gfx ? o.gfx.register('map', { el: stage,
        start() { gfxOn = true; stats.gfxLog.push('start'); interactSoft(); },
        stop() { gfxOn = false; orbiting = false; stats.gfxLog.push('stop'); } }) : null;
      function interactSoft() { clearTimeout(wakeT); const wait = Math.max(0, IDLE_MS - (performance.now() - lastInteract)) + 50; wakeT = setTimeout(() => { if (canOrbit(performance.now())) schedule(); }, wait); }

      function dispose() {
        if (disposed) return; disposed = true;
        clearTimeout(wakeT); tweens.clear();
        if (raf) cancelAnimationFrame(raf); if (pickRaf) cancelAnimationFrame(pickRaf); raf = pickRaf = 0;
        on.forEach(([t, ev, fn, opt]) => t.removeEventListener(ev, fn, opt));
        controls.dispose(); if (ro) ro.disconnect(); if (io) io.disconnect(); if (gh) gh.dispose();
        stats.infoBefore = { geometries: renderer.info.memory.geometries, textures: renderer.info.memory.textures, programs: renderer.info.programs ? renderer.info.programs.length : 0 };
        owned.geometries.forEach((g) => { g.dispose(); stats.disposed.geometries++; });
        owned.materials.forEach((m) => { m.dispose(); stats.disposed.materials++; });
        owned.textures.forEach((t) => { t.dispose(); stats.disposed.textures++; });
        stats.infoAfter = { geometries: renderer.info.memory.geometries, textures: renderer.info.memory.textures, programs: renderer.info.programs ? renderer.info.programs.length : 0 };
        owned.geometries.length = owned.materials.length = owned.textures.length = 0;
        scene.clear(); renderer.dispose(); try { renderer.forceContextLoss(); } catch (e) { /* ignore */ }
        canvas.remove(); labelsEl.remove(); tipEl.remove(); stats.disposedAll = true;
      }
      return {
        stats, name: '3d',
        setModel, setSelected, setHover: (n) => setHover(n, false),
        resetView: () => { interact(); goHome(false); }, zoom, rotate, resize, dispose, noteInteraction: interact,
        setActive(v) {
          visible = !!v;
          if (!v) { if (raf) cancelAnimationFrame(raf); raf = 0; if (pickRaf) cancelAnimationFrame(pickRaf); pickRaf = 0; }
          else { dirty = true; resize(); schedule(); maybeIntro(); }
        },
        _debug: { renderer, scene, camera, controls, state: () => ({ introDone, orbiting, tweens: tweens.size, hover, selected, orbitMs: Math.round(orbitSpent) }),
          /** stage-relative pixel position of a province's top centre (test hook) */
          screenOf: (n) => { const r = R.get(n); if (!r) return null; const s2 = toScreen(r.cx, DEPTH * r.grp.scale.y + r.lift, r.cz); return [s2[0], s2[1]]; } },
      };
    },
  };
})();
