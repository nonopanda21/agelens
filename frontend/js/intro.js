/* Loading splash, once per browser session (see css/intro.css). Decorative: aria-hidden, pointer-events none, removed after
   ~1.8 s or on the first key/click/wheel. Skipped under reduced motion. While it plays, --intro-delay on <html> makes the
   hero intro wait for the sheet to lift. Loaded after app.js and before AgeLens.start(). */
(function () {
  const AL = window.AgeLens;
  const KEY = 'al_splash_seen';
  let seen = false;
  try { seen = sessionStorage.getItem(KEY) === '1'; sessionStorage.setItem(KEY, '1'); } catch (e) { /* storage blocked: show once per load */ }
  if (seen || (AL && AL.reducedMotion && AL.reducedMotion())) return;

  const COLORS = ['#FFB6C1', '#D5C6E0', '#A8D8EA', '#FFF5BA', '#B5EAD7'];
  const conf = [];
  for (let i = 0; i < 26; i++) {
    const a = (i / 26) * Math.PI * 2 + (i % 3) * 0.2, d = 110 + ((i * 37) % 90);
    conf.push(`<i style="--c:${COLORS[i % 5]};--x:${Math.round(Math.cos(a) * d * 1.5)}px;--y:${Math.round(Math.sin(a) * d)}px;--r:${(i * 47) % 360}deg"></i>`);
  }
  const word = [...'AgeLens'].map((c, i) => `<span style="--i:${i}">${c}</span>`).join('');
  const el = document.createElement('div');
  el.className = 'al-splash'; el.setAttribute('aria-hidden', 'true');
  el.innerHTML = `<div class="sp-box"><div class="sp-conf">${conf.join('')}</div>
    <svg class="sp-book" viewBox="0 0 150 120" fill="none" stroke="#4A3728" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">
      <path class="pg-l" d="M75 26C58 15 36 13 12 16v82c24-3 46-1 63 10z" fill="#fff"/>
      <path class="pg-r" d="M75 26c17-11 39-13 63-10v82c-24-3-46-1-63 10z" fill="#FFE6EA"/>
      <path class="ink" pathLength="1" d="M75 26v82"/>
      <path class="ink" pathLength="1" d="M26 40c11-1 21 0 30 4M26 58c11-1 21 0 30 4M94 44c9-4 19-5 30-4" stroke="#FFB6C1" stroke-width="4"/>
    </svg><div class="sp-word">${word}</div></div>`;
  document.body.appendChild(el);
  document.documentElement.style.setProperty('--intro-delay', '1.3s');

  let done = false;
  const end = () => {
    if (done) return; done = true;
    el.classList.add('gone'); el.remove();
    ['keydown', 'pointerdown', 'wheel'].forEach((t) => removeEventListener(t, skip, true));
  };
  // a skip removes the sheet at once and lets the hero start right away
  const skip = () => { document.documentElement.style.setProperty('--intro-delay', '0s'); end(); };
  ['keydown', 'pointerdown', 'wheel'].forEach((t) => addEventListener(t, skip, { capture: true, passive: true }));
  el.addEventListener('animationend', (e) => { if (e.target === el) end(); });
  setTimeout(end, 2200); // safety net
  // after the splash the delay is no longer needed (later route visits start at once)
  setTimeout(() => document.documentElement.style.setProperty('--intro-delay', '0s'), 4000);
})();
