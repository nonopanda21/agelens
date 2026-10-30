/* Ambient interaction layer (lead-owned): the steps line drawing itself, a thin reading-progress bar (home only; hidden
   elsewhere by home-x.css), a floating round back-to-top button (all routes, after scrolling), and Apple-style
   scroll-linked effects on home (css/intro.css "apple" block):
     - hero exit: copy drifts up, shrinks and fades; the doodle moves faster (parallax); the particle canvas eases in;
     - zoom-in: [data-zoom] panels stand up from a tipped-back 3D tilt and grow to full size as they enter the viewport.
   All of it is transform/opacity on rAF, scroll-driven (no timers), and off under reduced motion. Hover states are plain CSS. */
(function () {
  const bar = document.createElement('div'); bar.className = 'x-progress'; bar.setAttribute('aria-hidden', 'true'); document.body.appendChild(bar);
  const top = document.createElement('button'); top.type = 'button'; top.className = 'x-top'; top.setAttribute('aria-label', 'Back to top'); top.tabIndex = -1;
  top.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V6M6 11l6-6 6 6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const reduced = () => !!(window.AgeLens && AgeLens.reducedMotion && AgeLens.reducedMotion());
  top.addEventListener('click', () => window.scrollTo({ top: 0, behavior: reduced() ? 'auto' : 'smooth' }));
  document.body.appendChild(top);
  const clamp = (v) => (v < 0 ? 0 : v > 1 ? 1 : v);
  const ease = (k) => 1 - Math.pow(1 - k, 3);

  function heroExit(still) {
    const hero = document.querySelector('.xh'); if (!hero) return;
    const inner = hero.querySelector('.xh-inner'), art = hero.querySelector('.xh-art'), cv = hero.querySelector('.xh-canvas');
    const p = still ? 0 : clamp(scrollY / (hero.offsetHeight || 1));
    if (inner) {
      inner.style.transform = p ? `translate3d(0,${(-70 * p).toFixed(1)}px,0) scale(${(1 - 0.07 * p).toFixed(4)})` : ''; inner.style.opacity = p ? clamp(1 - p * 1.25).toFixed(3) : '';
      inner.style.filter = p > 0.02 ? `blur(${(p * 7).toFixed(2)}px)` : ''; // copy goes out of focus as it leaves
    }
    if (art) { art.style.transform = p ? `translate3d(0,${(-150 * p).toFixed(1)}px,0) rotate(${(-4 * p).toFixed(2)}deg)` : ''; art.style.opacity = p ? clamp(1 - p * 1.1).toFixed(3) : ''; }
    if (cv) cv.style.transform = p ? `scale(${(1 + 0.12 * p).toFixed(4)})` : '';
  }
  function zooms(still) {
    document.querySelectorAll('[data-zoom]').forEach((el) => {
      if (still) { el.style.transform = ''; return; }
      const r = el.getBoundingClientRect();
      const k = ease(clamp((innerHeight - r.top) / (innerHeight * 0.75)));
      // the panel starts tipped back like a laptop lid and stands up to face the reader as it arrives
      el.style.transform = k >= 1 ? '' : `perspective(1600px) rotateX(${(24 * (1 - k)).toFixed(2)}deg) scale(${(0.88 + 0.12 * k).toFixed(4)})`;
    });
  }

  let praf = 0;
  const check = () => {
    praf = 0;
    const show = scrollY > innerHeight * 0.8; top.classList.toggle('show', show); top.tabIndex = show ? 0 : -1;
    if (document.body.dataset.layout !== 'home') return;
    const max = document.documentElement.scrollHeight - innerHeight;
    bar.style.setProperty('--p', max > 0 ? (scrollY / max).toFixed(4) : '0');
    document.querySelectorAll('.xst:not(.drawn)').forEach((el) => { const r = el.getBoundingClientRect(); if (r.top < innerHeight * 0.8 && r.bottom > 0) el.classList.add('drawn'); });
    const still = reduced();
    heroExit(still); zooms(still);
  };
  const onScroll = () => { if (!praf) praf = requestAnimationFrame(check); };
  window.addEventListener('scroll', onScroll, { passive: true }); window.addEventListener('resize', onScroll);
  window.addEventListener('hashchange', () => { setTimeout(onScroll, 50); setTimeout(onScroll, 600); });
  if (window.AgeLens && AgeLens.motion && AgeLens.motion.onChange) AgeLens.motion.onChange(onScroll);
  // home sections render asynchronously; re-check once they have laid out
  setTimeout(onScroll, 400); setTimeout(onScroll, 1500);
  onScroll();
})();
