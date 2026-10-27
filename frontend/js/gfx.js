/* Graphics coordinator. Rule: at most ONE heavy WebGL loop runs at a time — the registered view that is most visible.
   Hidden tab, paused/reduced motion, or off-screen => all loops stopped (last frame stays drawn).
   Usage: const h = AgeLens.gfx.register('hero', {el, start(), stop()}); ...; h.dispose();
   Modules draw one static frame themselves when motion is reduced; start() should begin requestAnimationFrame, stop() cancel it. */
(function () {
  const items = new Map();
  const stats = { switches: 0, log: [] };
  function evaluate() {
    const blocked = document.hidden || (window.AgeLens && AgeLens.motion && AgeLens.motion.reduced());
    let best = null, br = 0.05;
    if (!blocked) for (const [n, it] of items) if (it.ratio > br) { best = n; br = it.ratio; }
    for (const [n, it] of items) {
      const want = n === best;
      if (want && !it.running) { it.running = true; stats.switches++; stats.log.push('start ' + n); try { it.opts.start(); } catch (e) {} }
      else if (!want && it.running) { it.running = false; stats.log.push('stop ' + n); try { it.opts.stop(); } catch (e) {} }
    }
    if (stats.log.length > 50) stats.log.splice(0, stats.log.length - 50);
  }
  const io = 'IntersectionObserver' in window ? new IntersectionObserver((es) => {
    es.forEach((e) => { for (const it of items.values()) if (it.opts.el === e.target) it.ratio = e.isIntersecting ? e.intersectionRatio : 0; });
    evaluate();
  }, { threshold: [0, 0.05, 0.1, 0.25, 0.5, 0.75, 1] }) : null;
  document.addEventListener('visibilitychange', evaluate);
  window.AgeLens = window.AgeLens || {};
  AgeLens.gfx = {
    stats,
    register(name, opts) {
      const it = { opts, ratio: io ? 0 : 1, running: false };
      items.set(name, it);
      if (io) io.observe(opts.el);
      if (AgeLens.motion) AgeLens.motion.onChange(evaluate);
      evaluate();
      return { dispose() { if (it.running) { try { opts.stop(); } catch (e) {} } items.delete(name); if (io) io.unobserve(opts.el); } };
    },
    /** true when this view should run its animation loop right now */
    running(name) { const it = items.get(name); return !!(it && it.running); },
    /** Safe pixel ratio cap for all WebGL canvases */
    pixelRatio() { return Math.min(window.devicePixelRatio || 1, 1.5); },
    /** True if WebGL is usable. */
    /** True if WebGL is usable. Probed ONCE and the probe context is released immediately: every getContext() is a real
        context and browsers cap live contexts (~16), so re-probing on each page visit would leak them. */
    webgl() {
      if (this._webgl !== undefined) return this._webgl;
      try {
        const c = document.createElement('canvas'), gl = c.getContext('webgl2') || c.getContext('webgl');
        this._webgl = !!gl;
        const ext = gl && gl.getExtension('WEBGL_lose_context'); if (ext) ext.loseContext();
      } catch (e) { this._webgl = false; }
      return this._webgl;
    },
  };
})();
