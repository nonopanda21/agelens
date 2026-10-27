/* Particle nebula (ES module) for the home hero and footer: a dense, drifting dune of points in perspective, light background.
   Own implementation. The expensive part (value-noise terrain, lanes, ridges, colour) is computed ONCE per particle in JS, in chunks
   over the first frames (the field visibly fills in during the intro), and stored as attributes; the per-frame vertex shader only does
   cheap maths (sideways flow, two crossing waves, drift, twinkle, pointer lift). That makes ~300k points affordable, even on software
   rasterisers. Palette follows the sketchbook site: brown-ink speckles on paper (normal blending, not additive), with pastel pink,
   lavender, sky-blue and mint accents, so it reads as ink and pastel dust rather than a glowing nebula.
   Loop driven by AgeLens.gfx (one heavy loop at a time); adaptive pixel ratio, then adaptive point count. */

const VERT = /* glsl */`
attribute vec4 aP;   // x0 (-1..1), base height, z, random
attribute vec4 aC;   // rgb, base alpha (negative alpha marks a haze disc)
uniform float uTime, uIntro, uPx, uSpanX, uSpanZ, uBase, uDrift, uMask; uniform vec4 uMaskBox;
uniform vec2 uMouse, uRes; uniform float uMouseOn;
varying vec3 vCol; varying float vA; varying float vHaze;
void main(){
  float r = aP.w, haze = step(aC.a, 0.0), a0 = abs(aC.a);
  float t = uTime * uDrift;
  float x = mod(aP.x * uSpanX + t * 34.0 + uSpanX, 2.0 * uSpanX) - uSpanX;     // stream to the right, wrapping
  float z = aP.z;
  float y = mix(uBase, aP.y, 0.3 + 0.7 * uIntro);
  y += sin(x * 0.0042 + z * 0.002 + t * 0.85) * 26.0 + sin(x * 0.0019 - z * 0.0034 + t * 0.47) * 20.0;   // two crossing waves
  x += sin(t * 0.9 + r * 40.0) * 7.0; y += cos(t * 0.75 + r * 23.0) * 6.0;                              // per-point drift
  vec4 mv = modelViewMatrix * vec4(x, y, z, 1.0);
  vec4 clip = projectionMatrix * mv;
  vec2 scr = (clip.xy / clip.w * 0.5 + 0.5) * uRes;
  float dm = length(scr - uMouse);
  float mf = exp(-dm * dm / (2.0 * 105.0 * 105.0)) * uMouseOn;
  mv.y += mf * 30.0;
  gl_Position = projectionMatrix * mv;
  float persp = min(2.1, 760.0 / max(80.0, -mv.z));
  float spark = step(0.96, fract(r * 47.1));
  gl_PointSize = (1.15 + fract(r * 13.7) * 1.7 + spark * 1.3) * (1.0 + mf * 1.6) * mix(1.0, 16.0, haze) * uPx * persp;
  float tw = mix(0.66 + 0.34 * sin(t * 1.7 + r * 61.0), 0.35 + 0.65 * pow(max(0.0, sin(t * 2.4 + r * 97.0)), 4.0), spark);
  float depth = smoothstep(-uSpanZ * 1.35, -uSpanZ * 0.75, z) * smoothstep(uSpanZ * 0.235, uSpanZ * 0.13, z);
  vec2 c = (scr - uRes * uMaskBox.xy) / (uRes * uMaskBox.zw);
  float textMask = mix(uMask, 1.0, smoothstep(0.55, 1.15, length(c)));
  float appear = clamp(uIntro * 1.7 - r * 0.7, 0.0, 1.0);
  vCol = mix(aC.rgb, vec3(0.70, 0.23, 0.37), mf * 0.75);
  vA = (a0 * tw * depth * textMask * mix(1.0, 0.06, haze) + mf * 0.55 * (1.0 - haze)) * appear;
  vHaze = haze;
}`;
const FRAG = /* glsl */`
varying vec3 vCol; varying float vA; varying float vHaze;
void main(){
  float d = length(gl_PointCoord - 0.5) * 2.0;
  float a = mix(1.0 - smoothstep(0.35, 1.0, d), exp(-d * d * 4.5) * (1.0 - smoothstep(0.8, 1.0, d)), vHaze) * vA;
  if (a < 0.008) discard;
  gl_FragColor = vec4(vCol, min(a, 1.0));
}`;

/* ---- CPU-side value noise (integer hash; deterministic) ---- */
function hash3(x, y, z) {
  let h = Math.imul(x, 0x27d4eb2d) ^ Math.imul(y, 0x165667b1) ^ Math.imul(z, 0x1b873593);
  h = Math.imul(h ^ (h >>> 15), 0x85ebca6b); h ^= h >>> 13; h = Math.imul(h, 0xc2b2ae35); h ^= h >>> 16;
  return (h >>> 0) / 4294967296;
}
function vnoise(x, y, z) {
  const ix = Math.floor(x), iy = Math.floor(y), iz = Math.floor(z);
  let fx = x - ix, fy = y - iy, fz = z - iz;
  fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy); fz = fz * fz * (3 - 2 * fz);
  const l = (a, b, t) => a + (b - a) * t;
  return l(l(l(hash3(ix, iy, iz), hash3(ix + 1, iy, iz), fx), l(hash3(ix, iy + 1, iz), hash3(ix + 1, iy + 1, iz), fx), fy),
           l(l(hash3(ix, iy, iz + 1), hash3(ix + 1, iy, iz + 1), fx), l(hash3(ix, iy + 1, iz + 1), hash3(ix + 1, iy + 1, iz + 1), fx), fy), fz);
}
const DUST = [0.74, 0.66, 0.60], INK = [0.36, 0.27, 0.20], DEEP = [0.29, 0.22, 0.16], LAV = [0.60, 0.49, 0.74];
/* pastel accents, slightly deepened so they read on paper #FFF9F5: pink #FFB6C1, lav #D5C6E0, blue #A8D8EA, mint #B5EAD7 */
const PASTELS = [[0.96, 0.56, 0.64], [0.66, 0.55, 0.80], [0.46, 0.72, 0.86], [0.43, 0.79, 0.65]];
const mix3 = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];

/** createNebula({canvas, host, glow, variant: 'hero'|'footer', light, reduced}) */
export async function createNebula(opts) {
  const THREE = await import('three');
  const { canvas, host, glow } = opts; const light = !!opts.light; const footer = opts.variant === 'footer';
  const N = footer ? (light ? 40000 : 120000) : (light ? 80000 : 320000);
  const SZ = 2300, BASE = footer ? -40 : -150, AMP = 230, REF_SPAN = 2600;
  let dpr = Math.min(window.devicePixelRatio || 1, light ? 1.5 : 2);
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: false, powerPreference: 'default' });
  renderer.setClearColor(0x000000, 0);
  let soft = false;   // software rasterisers (llvmpipe, SwiftShader…) are common on remote desktops
  try { const gl = renderer.getContext(), ext = gl.getExtension('WEBGL_debug_renderer_info');
    soft = /llvmpipe|swiftshader|softpipe|software|or similar/i.test(String(ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER))); } catch (e) {}
  if (soft) dpr = Math.min(dpr, 1);
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(footer ? 42 : 46, 1, 1, 9000);

  const P = new Float32Array(N * 4), C = new Float32Array(N * 4);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(N * 3), 3));   // unused by the shader; sized so three draws N vertices
  const aP = new THREE.BufferAttribute(P, 4), aC = new THREE.BufferAttribute(C, 4);
  geo.setAttribute('aP', aP); geo.setAttribute('aC', aC);
  geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1e5);
  const U = {
    uTime: { value: 0 }, uIntro: { value: 0 }, uPx: { value: dpr }, uSpanX: { value: 2400 }, uSpanZ: { value: SZ }, uBase: { value: BASE },
    uDrift: { value: 1 }, uMask: { value: footer ? 1 : 0.22 }, uMaskBox: { value: new THREE.Vector4(...(opts.maskBox || [0.5, 0.53, 0.33, 0.19])) }, uMouse: { value: new THREE.Vector2(-1e4, -1e4) }, uRes: { value: new THREE.Vector2(1, 1) }, uMouseOn: { value: 0 },
  };
  const mat = new THREE.ShaderMaterial({ uniforms: U, vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthTest: false, depthWrite: false });
  const pts = new THREE.Points(geo, mat); pts.frustumCulled = false; scene.add(pts);

  // ---- particle generation, in chunks (the field fills in during the intro instead of blocking the page) ----
  let s = 1234567; const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
  let built = 0;
  let drawN = soft ? Math.floor(N * 0.6) : N;
  function buildChunk(count) {
    const end = Math.min(N, built + count);
    for (let i = built; i < end; i++) {
      const r = rnd(), sky = ((r * 7.13) % 1) >= 0.55; let x0, y0;
      for (let k = 0; k < 12; k++) {   // bias positions toward the lanes so points are not wasted where they would be invisible
        x0 = rnd() * 2 - 1; y0 = sky ? rnd() * 2 - 1 : Math.pow(rnd(), 0.85) * 2 - 1;   // ground slightly near-biased: fills the lower screen
        const ln = sky ? x0 * 0.62 - y0 * 0.55 + 0.18 : x0 * 0.78 + y0 * 0.5 - 0.02;
        if (rnd() < 0.35 + 0.65 * Math.exp(-Math.pow(ln / 0.8, 2))) break;
      }
      const xw = x0 * REF_SPAN, z = (-SZ + (SZ * 1.22) * (y0 * 0.5 + 0.5)) - (sky ? SZ * 0.35 : 0);
      const qx = xw * 0.0015, qz = z * 0.0015;
      const n = vnoise(qx, qz, 0) * 0.62 + vnoise(qx * 2.13 + 7.3, qz * 2.13 + 7.3, 7.3) * 0.28 + vnoise(qx * 4.7 + 1.9, qz * 4.7 + 1.9, 1.9) * 0.10;
      const y = BASE + (n - 0.5) * AMP * 2 + (sky ? 760 + (n - 0.5) * 420 : 0);
      const ridge = Math.pow(1 - Math.abs(vnoise(xw * 0.001 + 3 + (sky ? 9 : 0), z * 0.001, 0) * 2 - 1), 1.6);
      const lane = sky ? x0 * 0.62 - y0 * 0.55 + 0.18 : x0 * 0.78 + y0 * 0.5 - 0.02;
      const band = Math.exp(-Math.pow((lane + (n - 0.5) * 0.8) / 0.95, 2));
      const spark = ((r * 47.1) % 1) >= 0.96, haze = ((r * 29.3) % 1) >= 0.982;
      const lanes = Math.min(1, ridge * band * 1.6 + band * 0.35);
      const pastel = PASTELS[Math.floor(((r * 3.7) % 1) * 4)], tinted = ((r * 11.3) % 1) < 0.16;
      let col = mix3(DUST, mix3(INK, DEEP, ridge), lanes);
      if (sky) col = mix3(col, LAV, 0.45 + 0.4 * band);
      if (tinted) col = mix3(col, pastel, 0.8);           // a sprinkle of pastel dust among the ink
      if (spark) col = pastel;                             // twinkling pastel confetti
      const far = Math.min(1, Math.max(0, (-SZ * 0.35 - z) / (SZ * 0.85)));
      col = mix3(col, DUST, far * 0.5 * (spark ? 0 : 1));
      if (haze) col = PASTELS[Math.floor(((r * 5.9) % 1) * 4)];
      let a = (0.2 + 1.1 * ridge * band + 0.34 * band + (spark ? 0.75 : 0) + (tinted ? 0.2 : 0)) * (sky ? 0.75 : 1) * (1 - 0.3 * far);
      if (haze) a = -(0.5 + band);   // negative = haze disc (soft, faint pastel wash)
      const o = i * 4;
      P[o] = x0; P[o + 1] = y; P[o + 2] = z; P[o + 3] = r;
      C[o] = col[0]; C[o + 1] = col[1]; C[o + 2] = col[2]; C[o + 3] = a;
    }
    const from = built; built = end;
    if (aP.addUpdateRange) { aP.clearUpdateRanges(); aP.addUpdateRange(from * 4, (end - from) * 4); aC.clearUpdateRanges(); aC.addUpdateRange(from * 4, (end - from) * 4); }
    aP.needsUpdate = true; aC.needsUpdate = true;
    geo.setDrawRange(0, Math.min(built, drawN));
  }

  let W = 1, H = 1, running = false, raf = 0, last = 0, t = 0, intro = 0, disposed = false, frames = 0, cpu = 0, winSum = 0, winN = 0, drops = 0;
  let mx = -1e4, my = -1e4, tmx = -1e4, tmy = -1e4, mOn = 0, lastPtr = -1e9, par = 0, tpar = 0;
  function measure() {
    const rc = host.getBoundingClientRect(); W = Math.max(1, rc.width); H = Math.max(1, rc.height);
    renderer.setPixelRatio(dpr); renderer.setSize(W, H, false); U.uPx.value = dpr; U.uRes.value.set(W, H);
    camera.aspect = W / H; U.uSpanX.value = Math.max(1900, W * 2.1);
    if (footer) { camera.position.set(0, 150, 900); camera.lookAt(0, 40, -700); } else { camera.position.set(0, 330, 980); camera.lookAt(0, -30, -520); }
    camera.updateProjectionMatrix();
  }
  function frame() {
    U.uTime.value = t; U.uIntro.value = Math.min(1, intro);
    const sway = Math.sin(t * 0.18) * 40 * U.uDrift.value;
    camera.position.x = par * 60 + sway; camera.lookAt(par * 20 + sway * 0.4, footer ? 40 : -30, footer ? -700 : -520);
    renderer.render(scene, camera);
    if (glow) { glow.style.transform = `translate3d(${mx}px,${my}px,0)`; glow.style.opacity = String(mOn * 0.9); }
  }
  function step(dt) {
    if (built < N) buildChunk(Math.ceil(N / 24));   // ~24 frames to build everything
    t += dt; if (intro < 1) intro = Math.min(1, intro + dt / 2.4);
    const f = 1 - Math.exp(-dt * 7);
    mOn += ((performance.now() - lastPtr < 1600 ? 1 : 0) - mOn) * f;
    mx += (tmx - mx) * f; my += (tmy - my) * f; par += (tpar - par) * (1 - Math.exp(-dt * 2.5));
    U.uMouse.value.set(mx, H - my); U.uMouseOn.value = mOn;
  }
  function adapt(ms) {   // pixel ratio first (fill cost), then point count (vertex cost); never below 30% of the points
    winSum += ms; winN++;
    if (winN >= 30) {
      const avg = winSum / winN; winSum = 0; winN = 0;
      if (avg > 32 && dpr > 1.01) { dpr = Math.max(1, dpr - 0.25); drops++; renderer.setPixelRatio(dpr); renderer.setSize(W, H, false); U.uPx.value = dpr; }
      else if (avg > 40 && drawN > N * 0.3) { drawN = Math.max(Math.floor(N * 0.3), Math.floor(drawN * 0.8)); geo.setDrawRange(0, Math.min(built, drawN)); drops++; }
    }
  }
  function tick(now) {
    if (!running || disposed) return;
    raf = requestAnimationFrame(tick);
    const ms = Math.max(0, now - last); last = now; const dt = Math.min(0.05, ms / 1000);
    if (built >= N) adapt(ms);
    const t0 = performance.now(); step(dt); frame(); cpu += performance.now() - t0; frames++;
  }
  const api = {
    stats: () => ({ particles: N, built, drawn: Math.min(built, drawN), softwareRenderer: soft, frames, perFrameMs: frames ? +(cpu / frames).toFixed(3) : 0, pixelRatio: dpr, qualityDrops: drops, running }),
    start() { if (running || disposed) return; running = true; U.uDrift.value = 1; last = performance.now(); raf = requestAnimationFrame(tick); },
    stop() { running = false; cancelAnimationFrame(raf); },
    isRunning: () => running,
    resize() { if (disposed) return; measure(); frame(); },
    renderStatic() { while (built < N) buildChunk(N); t = 6; intro = 1; U.uDrift.value = 0; mOn = 0; U.uMouseOn.value = 0; frame(); },
    pointer(x, y, on) { if (!on) { lastPtr = -1e9; return; } lastPtr = performance.now(); tmx = x; tmy = y; if (mx < -1e3) { mx = x; my = y; } tpar = Math.max(-1, Math.min(1, (x / W) * 2 - 1)); },
    dispose() { disposed = true; running = false; cancelAnimationFrame(raf); geo.dispose(); mat.dispose(); renderer.dispose(); try { renderer.forceContextLoss(); } catch (e) {} },
  };
  measure();
  buildChunk(Math.ceil(N / 24));
  if (opts.reduced()) api.renderStatic(); else frame();
  return api;
}
