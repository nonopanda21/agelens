/* Evidence lens scene (ES module, loaded lazily by pages/home_hero.js).
   Perspective Three.js scene; world units = CSS px on the z=0 plane (origin = canvas centre, y up).
   - ~5k soft shader particles morph between four layouts (scatter galaxy, orbit around the lens, rows of "text" on an ad sheet, funnel -> three lanes)
   - a glass lens that glides to the evidence and MAGNIFIES the real clause (English, crisp canvas texture, 2x resolution)
   - an arc drawn between the age condition and its exception, sonar ripples on stage change, bounded pointer parallax/repel
   Decorative only: the real, selectable text lives in the page HTML. Light palette; no Chinese text. Adaptive resolution (<=2x) protects slow machines. */

function rng(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const FONT = 'system-ui,-apple-system,"Segoe UI","Noto Sans","Helvetica Neue",Arial,sans-serif';
const BLUE = '#2563EB', BLUE_D = '#1D4ED8', AMBER = '#B7791F', INK = '#1D1D1F', SLATE = '#5B6472';

/* ---------------- particles ---------------- */
const WIND = 7.5;    // spiral winding (radians per unit radius), shared by particles, nebula texture and stars
const GAL_ROT = 0.03; // rad/s, shared by particles, nebula and star glints
const VERT_POINTS = /* glsl */`
#define GAL_ROT ${GAL_ROT.toFixed(4)}
attribute vec3 aB; attribute vec3 aC; attribute vec3 aD; attribute vec4 aSeed; attribute float aHi;
uniform vec4 uW; uniform float uTime, uIntro, uPx, uCam, uDrift, uLr;
uniform vec3 uLens; uniform vec2 uMouse; uniform float uMouseOn; uniform vec2 uGal;
varying vec3 vCol; varying float vA;
mat2 rot(float a){ float s = sin(a), c = cos(a); return mat2(c, -s, s, c); }
void main(){
  float chaos = uW.x;
  vec3 pA = position;
  float rad = length(pA.xy);
  float swirl = (1.0 - uIntro) * (1.0 - uIntro) * 2.6;
  pA.xy = rot(swirl * (0.35 + 0.9 / (1.0 + rad / (uLr * 2.4))) + uTime * GAL_ROT * uDrift) * pA.xy;
  pA *= mix(1.5, 1.0, uIntro);
  pA.xy += uGal;
  vec3 pB = aB; vec2 rel = pB.xy;
  pB.xy = rot(uTime * 0.28 * uDrift / max(0.7, length(rel) / uLr)) * rel + uLens.xy; pB.z += uLens.z;
  vec3 pD = aD + vec3(uLens.xy, 0.0);
  vec3 p = pA * uW.x + pB * uW.y + aC * uW.z + pD * uW.w;
  float amb = step(0.3, aSeed.w);          // ambient dust: always part of the slowly turning galaxy, whatever the stage
  p = mix(p, pA, amb);
  float amp = uDrift * (1.2 + chaos * 9.0);
  p.xy += vec2(sin(uTime * 0.6 + aSeed.x * 6.283), cos(uTime * 0.5 + aSeed.y * 6.283)) * amp * (0.4 + aSeed.w);
  p.z += sin(uTime * 0.4 + aSeed.z * 6.283) * amp * 2.2;
  vec2 d = p.xy - uMouse; float f = exp(-dot(d, d) / (2.0 * 95.0 * 95.0)) * uMouseOn;
  p.xy += d / (length(d) + 1.0) * f * 30.0;
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  float dl = length(p.xy - uLens.xy);
  float foc = 1.0 - smoothstep(uLr * 0.7, uLr * 1.02, dl);
  float organised = 1.0 - chaos;
  float hi = clamp(aHi, 0.0, 1.0) * uW.z;
  float bok = step(0.962, aSeed.x) * amb;     // a few big soft discs = depth of field
  float rr = clamp(length(position.xy) / (uLr * 5.2), 0.0, 1.0);
  float size = (2.1 + aSeed.x * 3.1) * (1.0 + foc * (0.2 + 0.45 * organised)) * mix(1.0, 1.0 + (1.0 - rr) * 0.55, amb) * mix(1.0, 9.0, bok) + hi * 2.0;
  gl_PointSize = size * uPx * (uCam / max(1.0, -mv.z));
  vec3 slate = vec3(0.36, 0.43, 0.56), blue = vec3(0.145, 0.388, 0.92), violet = vec3(0.50, 0.42, 0.90), amber = vec3(0.80, 0.49, 0.10);
  vec3 base = aSeed.z < 0.16 ? violet : (aSeed.z < 0.46 ? mix(slate, blue, 0.55) : slate);
  vec3 hc = aHi > 1.5 ? amber : blue;
  vCol = mix(mix(base, hc, hi), blue, foc * 0.55);
  vec3 coreC = vec3(0.09, 0.26, 0.86), armC = vec3(0.47, 0.36, 0.93), tipC = vec3(0.84, 0.40, 0.80);
  vec3 gal = mix(coreC, mix(armC, tipC, smoothstep(0.5, 1.0, rr) * 0.6), smoothstep(0.0, 0.55, rr));
  vCol = mix(vCol, gal, amb * (1.0 - foc * 0.8));
  float depthFade = clamp(1.0 - (-mv.z - uCam) / 760.0, 0.3, 1.0);
  float tw = 0.78 + 0.22 * sin(uTime * 1.7 * uDrift + aSeed.w * 40.0);
  vA = (0.34 + aSeed.y * 0.5) * depthFade * tw * mix(1.0, 1.25, amb) * mix(1.0, 0.2, bok) + amb * (1.0 - rr) * 0.3 + foc * 0.16 + hi * 0.4;
  vA *= 1.0 - amb * uW.z * 0.5;
  vA *= smoothstep(0.0, 0.5, uIntro * 1.4 - aSeed.w * 0.6);
}`;
const FRAG_POINTS = /* glsl */`
varying vec3 vCol; varying float vA;
void main(){
  float d = length(gl_PointCoord - 0.5) * 2.0;
  float a = (exp(-d * d * 7.0) + exp(-d * d * 2.4) * 0.32) * vA;
  a *= 1.0 - smoothstep(0.92, 1.0, d);
  if (a < 0.012) discard;
  gl_FragColor = vec4(vCol, min(a, 1.0));
}`;

/* ---------------- lens glass / rings / ripples ---------------- */
const VERT_UV = 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }';
const FRAG_GLASS = /* glsl */`
varying vec2 vUv; uniform float uTime, uFocus, uAlpha;
void main(){
  vec2 p = vUv * 2.0 - 1.0; float r = length(p);
  float inside = smoothstep(1.0, 0.985, r);
  float edge = smoothstep(0.5, 1.0, r);
  vec3 col = mix(vec3(1.0), vec3(0.72, 0.82, 1.0), edge);
  float sheen = smoothstep(0.0, 1.0, 1.0 - abs(p.x * 0.78 + p.y * 0.62 - 0.30 + 0.12 * sin(uTime * 0.45)) * 3.2) * 0.38 * (1.0 - r * 0.6);
  float band = exp(-pow(p.y - 0.85 * sin(uTime * 0.8), 2.0) * 55.0) * 0.3 * uFocus;
  col += vec3(0.0, 0.06, 0.22) * band;
  float a = (0.2 + edge * 0.3 + sheen * 0.5 + band) * inside * uAlpha;
  gl_FragColor = vec4(col + sheen * 0.4, a);
}`;
const FRAG_DASH = /* glsl */`
varying vec2 vUv; uniform vec3 uColor; uniform float uDash, uRot, uOp, uTime;
void main(){
  vec2 p = vUv * 2.0 - 1.0; float r = length(p); float ang = atan(p.y, p.x) + uRot;
  float ring = smoothstep(0.972, 0.982, r) * smoothstep(1.0, 0.992, r);
  float dash = smoothstep(0.4, 0.46, fract(ang * uDash / 6.2831853));
  gl_FragColor = vec4(uColor, ring * dash * uOp);
}`;
const FRAG_RIPPLE = /* glsl */`
varying vec2 vUv; uniform float uP, uOp;
void main(){
  float r = length(vUv * 2.0 - 1.0); float c = mix(0.28, 0.96, 1.0 - pow(1.0 - uP, 2.2));
  float a = smoothstep(0.022, 0.0, abs(r - c)) * pow(1.0 - uP, 1.6) * uOp;
  gl_FragColor = vec4(0.15, 0.39, 0.92, a * 0.42);
}`;
const FRAG_CLIP = /* glsl */`
varying vec2 vUv; uniform sampler2D uTex; uniform float uAlpha;
void main(){
  vec2 p = vUv * 2.0 - 1.0; float r = length(p);
  vec4 t = texture2D(uTex, vUv);
  float m = smoothstep(0.94, 0.86, r);
  gl_FragColor = vec4(t.rgb, t.a * m * uAlpha);
}`;

/* ---------------- crisp canvas textures (drawn at >= 2x, mipmapped) ---------------- */
function mkCanvas(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; return [c, c.getContext('2d')]; }
function rr(g, x, y, w, h, r) { g.beginPath(); g.roundRect ? g.roundRect(x, y, w, h, r) : g.rect(x, y, w, h); }
function finish(THREE, c, renderer) {
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = renderer.capabilities.getMaxAnisotropy();
  t.minFilter = THREE.LinearMipmapLinearFilter; t.generateMipmaps = true; return t;
}
function cardTexture(THREE, renderer, text, kind) { // kind: 0 neutral · 1 condition (blue) · 2 exception (amber) · 3 question chip
  const S = 2, w = 560 * S, h = 100 * S; const [c, g] = mkCanvas(w, h);
  const pal = kind === 1 ? ['#EAF1FF', '#7AA2F7', BLUE_D] : kind === 2 ? ['#FFF4E3', '#E3B97A', '#8A5A12'] : kind === 3 ? ['#FFFFFF', '#9DB8F5', INK] : ['#FFFFFF', '#CBD0D8', SLATE];
  g.shadowColor = 'rgba(29,29,31,.14)'; g.shadowBlur = 14 * S; g.shadowOffsetY = 4 * S;
  g.fillStyle = pal[0]; rr(g, 14 * S, 10 * S, w - 28 * S, h - 30 * S, 18 * S); g.fill(); g.shadowColor = 'transparent';
  g.strokeStyle = pal[1]; g.lineWidth = 2 * S; g.stroke();
  let tx = w / 2;
  if (kind === 3) { g.fillStyle = BLUE; g.beginPath(); g.arc(46 * S, 41 * S, 17 * S, 0, 6.283); g.fill(); g.fillStyle = '#fff'; g.font = `700 ${24 * S}px ${FONT}`; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('?', 46 * S, 42 * S); tx = (w + 40 * S) / 2; }
  g.fillStyle = pal[2]; g.font = `600 ${30 * S}px ${FONT}`; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(text, tx, 42 * S, w - (kind === 3 ? 120 : 70) * S);
  return finish(THREE, c, renderer);
}
function paperTexture(THREE, renderer) {
  const S = 2, w = 520 * S, h = 640 * S; const [c, g] = mkCanvas(w, h);
  g.shadowColor = 'rgba(29,40,70,.22)'; g.shadowBlur = 36 * S; g.shadowOffsetY = 12 * S;
  const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, '#FFFFFF'); gr.addColorStop(1, '#F6F8FC');
  g.fillStyle = gr; rr(g, 36 * S, 30 * S, w - 72 * S, h - 80 * S, 20 * S); g.fill(); g.shadowColor = 'transparent';
  g.strokeStyle = '#DDE3EE'; g.lineWidth = 2 * S; g.stroke();
  g.fillStyle = BLUE; rr(g, 64 * S, 56 * S, 26 * S, 26 * S, 7 * S); g.fill();
  g.fillStyle = '#C9D2E2'; rr(g, 100 * S, 60 * S, 120 * S, 8 * S, 4 * S); g.fill(); rr(g, 100 * S, 74 * S, 76 * S, 6 * S, 3 * S); g.fill();
  g.fillStyle = '#E4E9F2'; rr(g, w - 148 * S, 58 * S, 84 * S, 22 * S, 11 * S); g.fill();
  return finish(THREE, c, renderer);
}
function glowTexture(THREE) {
  const [c, g] = mkCanvas(256, 256); const gr = g.createRadialGradient(128, 128, 0, 128, 128, 128);
  gr.addColorStop(0, 'rgba(120,150,255,.55)'); gr.addColorStop(0.45, 'rgba(165,150,255,.2)'); gr.addColorStop(1, 'rgba(165,150,255,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 256, 256); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
function fit(g, text, maxW, size, weight) { // shrink the font until the text fits (system fallback fonts can be much wider than expected)
  let sz = size; for (let i = 0; i < 24; i++) { g.font = `${weight} ${sz}px ${FONT}`; if (g.measureText(text).width <= maxW) break; sz *= 0.93; } return sz;
}
function lensTexture(THREE, renderer, kind) { // magnified evidence shown inside the lens (English, fictional)
  const S = 2, N = 512 * S; const [c, g] = mkCanvas(N, N); g.textAlign = 'center'; g.textBaseline = 'middle';
  const hl = (cxm, y, w, h, col) => { g.fillStyle = col; rr(g, cxm - w / 2, y - h / 2, w, h, 14 * S); g.fill(); };
  const line = (text, y, size, weight, color, maxW, bar) => {
    fit(g, text, maxW, size * S, weight); const w = g.measureText(text).width, sz = parseFloat(g.font.split('px')[0].split(' ').pop());
    if (bar) hl(N / 2, y, w + 28 * S, sz * 1.32, bar);
    g.fillStyle = color; g.fillText(text, N / 2, y + sz * 0.04);
  };
  if (kind === 0) { // your question
    g.fillStyle = BLUE; g.font = `300 ${280 * S}px ${FONT}`; g.fillText('?', N / 2, N / 2 - 62 * S);
    line('Start with your question', N / 2 + 126 * S, 26, 600, SLATE, N * 0.6);
  } else if (kind === 1) { // original wording: condition in blue, exception in amber (same colours as the panel below)
    const mw = N * 0.68;
    line('Applicants should normally be', N / 2 - 112 * S, 44, 600, INK, mw);
    line('under 35', N / 2 - 44 * S, 60, 700, BLUE_D, N * 0.44, 'rgba(37,99,235,.17)');
    line('but exceptions may be made', N / 2 + 38 * S, 44, 600, INK, mw);
    line('for outstanding candidates', N / 2 + 104 * S, 44, 700, '#8A5A12', N * 0.66, 'rgba(183,121,31,.2)');
  } else { // what to clarify (one shared font size so the three lines match)
    const items = ['Who decides exceptions?', 'What counts as outstanding?', 'Cut-off, or a guideline?'];
    const sz = Math.min(...items.map((t) => fit(g, t, N * 0.6, 42 * S, 600)));
    items.forEach((t, i) => {
      const y = N / 2 + (i - 1) * 104 * S, x0 = N / 2 - 190 * S;
      g.fillStyle = BLUE; g.beginPath(); g.arc(x0, y, 24 * S, 0, 6.283); g.fill();
      g.fillStyle = '#fff'; g.font = `700 ${28 * S}px ${FONT}`; g.fillText(String(i + 1), x0, y + 1 * S);
      g.textAlign = 'left'; g.font = `600 ${sz}px ${FONT}`; g.fillStyle = INK; g.fillText(t, x0 + 38 * S, y + 1 * S); g.textAlign = 'center';
    });
  }
  return finish(THREE, c, renderer);
}

const FRAGMENTS = [
  { t: 'Normally under 35', k: 1 }, { t: 'Exceptions may apply', k: 2 }, { t: 'Bachelor’s degree or above', k: 0 },
  { t: '3+ years in procurement', k: 0 }, { t: 'Competitive salary', k: 0 }, { t: 'Location: Shanghai', k: 0 },
];
const CHIPS = ['Who decides exceptions?', 'What counts as outstanding?', 'Cut-off or guideline?'];

/** createLens({canvas, host, slot, light, reduced, maxDpr}) -> controller. Throws if WebGL is unavailable. */
export async function createLens(opts) {
  const THREE = await import('three');
  const { canvas, host, slot } = opts; const light = !!opts.light;
  const N = light ? 1900 : 5400, ROWS = 15, FOV = 38;
  let dpr = Math.min(window.devicePixelRatio || 1, opts.maxDpr || (light ? 1.5 : 2));
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: !light, powerPreference: 'default' });
  renderer.setClearColor(0x000000, 0);
  const camera = new THREE.PerspectiveCamera(FOV, 1, 10, 4000);
  const scene = new THREE.Scene();

  /* per-particle constants (seeded: identical every load) */
  const R = rng(20261023);
  const A = new Float32Array(N * 3), B = new Float32Array(N * 3), C = new Float32Array(N * 3), D = new Float32Array(N * 3);
  const seed = new Float32Array(N * 4), hi = new Float32Array(N);
  for (let i = 0; i < N * 4; i++) seed[i] = R();
  const seed0 = Float32Array.from(seed);
  const geo = new THREE.BufferGeometry();
  const attrs = { position: new THREE.BufferAttribute(A, 3), aB: new THREE.BufferAttribute(B, 3), aC: new THREE.BufferAttribute(C, 3), aD: new THREE.BufferAttribute(D, 3), aSeed: new THREE.BufferAttribute(seed, 4), aHi: new THREE.BufferAttribute(hi, 1) };
  for (const k in attrs) geo.setAttribute(k, attrs[k]);
  geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1e5);
  const U = {
    uW: { value: new THREE.Vector4(1, 0, 0, 0) }, uTime: { value: 0 }, uIntro: { value: 0 }, uPx: { value: dpr }, uCam: { value: 1000 }, uDrift: { value: 1 }, uLr: { value: 120 },
    uLens: { value: new THREE.Vector3() }, uGal: { value: new THREE.Vector2() }, uMouse: { value: new THREE.Vector2(1e4, 1e4) }, uMouseOn: { value: 0 },
  };
  const pmat = new THREE.ShaderMaterial({ uniforms: U, vertexShader: VERT_POINTS, fragmentShader: FRAG_POINTS, transparent: true, depthTest: false, depthWrite: false });
  const points = new THREE.Points(geo, pmat); points.frustumCulled = false; points.renderOrder = 2;

  /* nebula: baked ONCE on the GPU into a 1024² texture (fbm noise along the same two-arm spiral the particles follow).
     Per frame it is only a textured quad, so it costs no noise maths. Two copies at different scales give parallax depth. */
  const BAKE_FRAG = `varying vec2 vUv;
    float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
    float noise(vec2 p){ vec2 i = floor(p), f = fract(p); vec2 u = f * f * (3.0 - 2.0 * f);
      return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y); }
    float fbm(vec2 p){ float v = 0.0, a = 0.5; for (int k = 0; k < 6; k++){ v += a * noise(p); p = p * 2.03 + vec2(1.7, 9.2); a *= 0.5; } return v; }
    void main(){
      vec2 p = vUv * 2.0 - 1.0; float r = length(p), th = atan(p.y, p.x);
      float tt = r * 1.05 - 0.025;                         // same radius->winding mapping as the particle arms
      float ph = 2.0 * (th - ${WIND.toFixed(2)} * tt);
      vec2 q = p * 2.6; float n = fbm(q + vec2(fbm(q * 0.8), fbm(q * 0.8 + 3.1)) * 1.6);
      float arm = pow(0.5 + 0.5 * cos(ph + (n - 0.5) * 2.2), 5.0);
      float clump = smoothstep(0.48, 0.78, fbm(q * 1.7 + 7.0));            // bright knots break up continuous bands
      float lane = pow(0.5 + 0.5 * cos(ph - 1.05 + (n - 0.5) * 1.2), 18.0);   // thin dust lane beside each arm
      float radial = exp(-r * r * 3.8), core = exp(-r * r * 36.0), bulge = exp(-r * r * 9.0);
      float d = (arm * (0.45 + 0.9 * n + clump * 0.8) * radial * 1.35 + bulge * 0.5 + core * 0.9 + n * n * radial * 0.35) * (1.0 - lane * radial * 0.75);
      d *= smoothstep(1.0, 0.72, r);
      vec3 deep = vec3(0.17, 0.33, 0.93), vio = vec3(0.50, 0.38, 0.95), rose = vec3(0.92, 0.50, 0.80), pearl = vec3(0.93, 0.95, 1.0);
      vec3 col = mix(deep, vio, smoothstep(0.08, 0.62, r));
      col = mix(col, rose, smoothstep(0.42, 0.9, r) * smoothstep(0.45, 0.8, n) * 0.85);
      col = mix(col, pearl, core * 0.85);
      gl_FragColor = vec4(col, clamp(d, 0.0, 1.0) * 0.9);
    }`;
  const nebRT = new THREE.WebGLRenderTarget(1024, 1024, { depthBuffer: false });
  nebRT.texture.generateMipmaps = true; nebRT.texture.minFilter = THREE.LinearMipmapLinearFilter;
  {
    const bs = new THREE.Scene(), bc = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    const bm = new THREE.ShaderMaterial({ vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }', fragmentShader: BAKE_FRAG, blending: THREE.NoBlending, depthTest: false, depthWrite: false });
    const bq = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), bm); bs.add(bq);
    renderer.setRenderTarget(nebRT); renderer.setClearColor(0x000000, 0); renderer.clear(); renderer.render(bs, bc); renderer.setRenderTarget(null);
    bq.geometry.dispose(); bm.dispose();
  }
  const NEB_FRAG = 'varying vec2 vUv; uniform sampler2D uTex; uniform float uOp; void main(){ vec4 t = texture2D(uTex, vUv); gl_FragColor = vec4(t.rgb, t.a * uOp); }';
  const hazes = [{ s: 1.0, op: 0.62, z: -120 }, { s: 0.74, op: 0.3, z: -40, spin: 0.35 }].map((hz) => {
    const mat = new THREE.ShaderMaterial({ uniforms: { uTex: { value: nebRT.texture }, uOp: { value: hz.op } }, vertexShader: VERT_UV, fragmentShader: NEB_FRAG, transparent: true, depthTest: false, depthWrite: false });
    const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), mat); m.renderOrder = 0; scene.add(m); return Object.assign(hz, { m, mat });
  });
  // soft core bloom + twinkling four-point stars that ride the arms
  function starTexture() {
    const [c, g] = mkCanvas(128, 128), cg = g.createRadialGradient(64, 64, 0, 64, 64, 30);
    cg.addColorStop(0, 'rgba(255,255,255,1)'); cg.addColorStop(0.25, 'rgba(120,140,255,.85)'); cg.addColorStop(1, 'rgba(120,120,255,0)');
    g.fillStyle = cg; g.fillRect(0, 0, 128, 128);
    for (const [dx, dy] of [[1, 0], [0, 1]]) { const lg = g.createLinearGradient(64 - dx * 64, 64 - dy * 64, 64 + dx * 64, 64 + dy * 64); lg.addColorStop(0, 'rgba(80,100,240,0)'); lg.addColorStop(0.5, 'rgba(70,95,235,.9)'); lg.addColorStop(1, 'rgba(80,100,240,0)'); g.fillStyle = lg; g.fillRect(dx ? 0 : 62, dx ? 62 : 0, dx ? 128 : 4, dx ? 4 : 128); }
    const t2 = new THREE.CanvasTexture(c); t2.colorSpace = THREE.SRGBColorSpace; return t2;
  }
  const starTex = starTexture(), sq = rng(4242);
  const stars = Array.from({ length: light ? 5 : 13 }, (_, k) => {
    const mat = new THREE.MeshBasicMaterial({ map: starTex, transparent: true, opacity: 0, depthTest: false, depthWrite: false });
    const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), mat); m.renderOrder = 2; scene.add(m);
    return { m, mat, tt: 0.12 + sq() * 0.7, arm: k % 2, off: (sq() - 0.5) * 0.25, ph: sq() * 6.28, sp: 0.8 + sq() * 1.4, size: 12 + sq() * 16 };
  });
  const coreTex = glowTexture(THREE);
  const coreGlow = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: coreTex, transparent: true, opacity: 0.7, depthTest: false, depthWrite: false })); coreGlow.renderOrder = 0; scene.add(coreGlow);

  /* sheet, glow, ripples, link arc */
  const paperTex = paperTexture(THREE, renderer);
  const paper = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: paperTex, transparent: true, opacity: 0, depthTest: false, depthWrite: false })); paper.renderOrder = 0;
  const glowTex = glowTexture(THREE);
  const glow = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: glowTex, transparent: true, opacity: 0.8, depthTest: false, depthWrite: false })); glow.renderOrder = 0;
  const rippleMat = new THREE.ShaderMaterial({ uniforms: { uP: { value: 1 }, uOp: { value: 1 } }, vertexShader: VERT_UV, fragmentShader: FRAG_RIPPLE, transparent: true, depthTest: false, depthWrite: false });
  const ripple = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), rippleMat); ripple.renderOrder = 1;
  const arcMat = new THREE.MeshBasicMaterial({ color: 0x2563eb, transparent: true, opacity: 0, depthTest: false, depthWrite: false });
  let arc = null;
  scene.add(glow, paper, ripple, points);

  /* fragments (English, crisp) + question chips */
  const frags = FRAGMENTS.slice(0, light ? 4 : 6).map((f, k) => {
    const tex = cardTexture(THREE, renderer, f.t, f.k), mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false, opacity: 0 });
    const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 100 / 560), mat); m.renderOrder = 3; scene.add(m);
    return { f, m, mat, tex, k, pos: [[0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0]], op: f.k ? [0.95, 0.55, 0.0, 0.0] : [0.85, 0.5, 0.0, 0.0] };
  });
  const chips = CHIPS.map((t, k) => {
    const tex = cardTexture(THREE, renderer, t, 3), mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false, opacity: 0 });
    const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 100 / 560), mat); m.renderOrder = 3; scene.add(m); return { m, mat, tex, k };
  });

  /* lens */
  const lensG = new THREE.Group(); scene.add(lensG);
  const glassMat = new THREE.ShaderMaterial({ uniforms: { uTime: U.uTime, uFocus: { value: 0 }, uAlpha: { value: 1 } }, vertexShader: VERT_UV, fragmentShader: FRAG_GLASS, transparent: true, depthTest: false, depthWrite: false });
  const glass = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), glassMat); glass.renderOrder = 4; lensG.add(glass);
  const clip = [0, 1, 2].map((kind) => {
    const tex = lensTexture(THREE, renderer, kind);
    const mat = new THREE.ShaderMaterial({ uniforms: { uTex: { value: tex }, uAlpha: { value: 0 } }, vertexShader: VERT_UV, fragmentShader: FRAG_CLIP, transparent: true, depthTest: false, depthWrite: false });
    const m = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat); m.renderOrder = 5; lensG.add(m); return { m, mat, tex };
  });
  const dashMk = (color, dash, op, s) => {
    const mat = new THREE.ShaderMaterial({ uniforms: { uColor: { value: new THREE.Color(color) }, uDash: { value: dash }, uRot: { value: 0 }, uOp: { value: op }, uTime: U.uTime }, vertexShader: VERT_UV, fragmentShader: FRAG_DASH, transparent: true, depthTest: false, depthWrite: false });
    const m = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat); m.renderOrder = 6; m.scale.setScalar(s); lensG.add(m); return { m, mat };
  };
  const ringSolid = dashMk(0x2563eb, 1, 0.95, 1.0), ringDash = dashMk(0x2563eb, 44, 0.75, 1.13), ringDash2 = dashMk(0x8b7be8, 18, 0.55, 1.26);
  ringSolid.mat.fragmentShader = FRAG_DASH.replace('smoothstep(0.4, 0.46, fract(ang * uDash / 6.2831853))', '1.0'); ringSolid.mat.needsUpdate = true;
  
  /* ---------------- layout (px) ---------------- */
  let GR = 400, W = 1, H = 1, cx = 0, cy = 0, lr = 110, camD = 1000, px = 0, py = 0, pw = 300, ph = 380, rowYs = [];
  const lensPos = [[0, 0], [0, 0], [0, 0]];
  let rowTop = 0, rowBot = 0;
  const rowY = (r) => rowTop + (rowBot - rowTop) * r / (ROWS - 1);
  function layout() {
    const rows = ROWS, share = 0.42, per = Math.floor(N * share / rows), COND = 5, EXC = 8;
    rowYs = []; for (let r = 0; r < rows; r++) rowYs.push(rowY(r));
    const segsOf = (r) => { const q = rng(900 + r), out = []; let u = 0.0; while (u < 0.9) { const w = 0.07 + q() * 0.17; out.push([u, Math.min(0.92, u + w)]); u += w + 0.035 + q() * 0.03; } return out; };
    const segs = []; for (let r = 0; r < rows; r++) segs.push(segsOf(r));
    for (let i = 0; i < N; i++) {
      const onRows = i < per * rows; if (onRows) seed[i * 4 + 3] = seed0[i * 4 + 3] * 0.28; else seed[i * 4 + 3] = seed0[i * 4 + 3];
      const o = i * 3, s0 = seed[i * 4], s1 = seed[i * 4 + 1], s2 = seed[i * 4 + 2], s3 = seed[i * 4 + 3], t = i / N; hi[i] = 0;
      // A: two-arm spiral galaxy with a dense bright core (relative to the galaxy centre uGal), tilted
      { const core = s0 < 0.2, tt = core ? Math.pow(s1, 2.0) * 0.1 : Math.pow(s0, 1.3), arm = i % 2;
        const ang = core ? s2 * 6.2832 : tt * WIND + arm * Math.PI + (s1 + s2 - 1.0) * (0.22 + tt * 0.42), rad = (0.025 + tt) * GR;
        const gx = Math.cos(ang) * rad, gy = Math.sin(ang) * rad * 0.62, th = -0.38;
        A[o] = gx * Math.cos(th) - gy * Math.sin(th); A[o + 1] = gx * Math.sin(th) + gy * Math.cos(th); A[o + 2] = (s2 - 0.5) * (core ? 140 : 260) * (0.4 + tt); }
      // B: three tilted orbits around the lens (offsets from the lens)
      const orb = i % 3, a2 = s1 * 6.2832 + orb * 2.1, rb = lr * (1.12 + orb * 0.34 + (s2 - 0.5) * 0.22);
      B[o] = Math.cos(a2) * rb; B[o + 1] = Math.sin(a2) * rb * (0.9 - orb * 0.08); B[o + 2] = Math.sin(a2 * 2 + orb) * 90 + (s3 - 0.5) * 26;
      // C: rows of "text" on the sheet, plus dust around it
      if (i < per * rows) {
        const row = Math.floor(i / per), sg = segs[row], seg = sg[Math.floor(s0 * sg.length) % sg.length], u = seg[0] + (seg[1] - seg[0]) * s1;
        C[o] = px - pw / 2 + 36 + u * (pw - 72); C[o + 1] = rowYs[row] + (s2 - 0.5) * 3.2; C[o + 2] = 12 + (s3 - 0.5) * 8;
        if (row === COND && u > 0.06 && u < 0.62) hi[i] = 1;
        if (row === EXC && u > 0.1 && u < 0.88) hi[i] = 2;
      } else {
        const g = (s0 - 0.5) + (s1 - 0.5); C[o] = px + g * pw * 1.1; C[o + 1] = py + ((s2 - 0.5) + (s3 - 0.5)) * ph * 0.8; C[o + 2] = (s3 - 0.5) * 220;
      }
      // D: funnel (offsets from the lens) -> three clear lanes on the right
      const xx = (t - 0.5) * W * 0.98 - 0;
      if (xx < 0) { const kk = Math.min(1, -xx / (W * 0.45)); D[o + 1] = (s1 - 0.5) * 2 * (lr * 0.2 + (H * 0.34 - lr * 0.2) * Math.pow(kk, 1.35)); }
      else { const lane = Math.floor(s3 * 3); D[o + 1] = (lane - 1) * lr * 0.5 + (s1 - 0.5) * 6; }
      D[o] = xx + 0; D[o + 2] = (s2 - 0.5) * 120;
    }
    for (const k in attrs) attrs[k].needsUpdate = true;
    // fragments
    frags.forEach((fr, k) => {
      const fw = Math.min(210, W * 0.36), q = rng(77 + k), a = (k / frags.length) * 6.2832 + 0.5;
      fr.w = fw; fr.m.scale.set(fw, fw, 1);
      fr.pos[0] = [(q() - 0.5) * W * 0.88, (q() - 0.5) * H * 0.82, (q() - 0.5) * 200];
      fr.pos[1] = [Math.cos(a) * (lr * 1.2 + fw * 0.55), Math.sin(a) * lr * 1.6, 30 + (k % 3) * 25];       // offsets from lens
      fr.pos[2] = [px + (k % 2 ? 1 : -1) * pw * 0.62, py + (k - 2) * ph * 0.17, 20];
      fr.pos[3] = [fr.pos[2][0], fr.pos[2][1], 0];
    });
    chips.forEach((c, k) => { const cw = Math.min(236, W * 0.38); c.w = cw; c.m.scale.set(cw, cw, 1); const lx2 = cx - W * 0.17, maxX = W / 2 - cw / 2 - 12; c.pos = [Math.min((lr * 1.12) + cw * 0.5 + 6, maxX - lx2), (1 - k) * (lr * 0.62), 40]; });
    // lens waypoints per stage
    lensPos[0] = [cx, cy]; lensPos[1] = [px + 6, (rowYs[COND] + rowYs[EXC]) / 2]; lensPos[2] = [cx - W * 0.17, cy];
    // arc linking condition and exception (drawn on in stage 1)
    if (arc) { scene.remove(arc); arc.geometry.dispose(); }
    const x0 = px - pw * 0.5 + 36 + pw * 0.62 * 0.9, x1 = px - pw * 0.5 + 36 + pw * 0.45;
    const curve = new THREE.QuadraticBezierCurve3(new THREE.Vector3(px + pw * 0.14, rowYs[COND], 16), new THREE.Vector3(px + pw * 0.46, (rowYs[COND] + rowYs[EXC]) / 2, 30), new THREE.Vector3(px - pw * 0.04, rowYs[EXC], 16));
    arc = new THREE.Mesh(new THREE.TubeGeometry(curve, 48, 1.4, 6, false), arcMat); arc.renderOrder = 4; arc.frustumCulled = false; scene.add(arc);
    arcCount = arc.geometry.index.count;
  }
  let arcCount = 0;
  function measure() {
    const hr = host.getBoundingClientRect(), sr = slot.getBoundingClientRect();
    W = Math.max(1, hr.width); H = Math.max(1, hr.height);
    renderer.setPixelRatio(dpr); renderer.setSize(W, H, false); U.uPx.value = dpr;
    camD = (H / 2) / Math.tan((FOV * Math.PI / 180) / 2); camera.aspect = W / H; camera.fov = FOV; camera.position.set(0, 0, camD); camera.near = 10; camera.far = camD + 2200; camera.updateProjectionMatrix(); U.uCam.value = camD;
    cx = sr.left + sr.width / 2 - hr.left - W / 2; cy = H / 2 - (sr.top + sr.height / 2 - hr.top);
    lr = Math.max(52, Math.min(sr.width * 0.3, sr.height * 0.33)); U.uLr.value = lr;
    pw = Math.min(W * 0.66, 380); const planeW = pw * 1.14, planeH = planeW * (640 / 520), pcy = H / 2 - 30 - planeH / 2;
    px = cx; py = pcy; ph = planeH * 0.85; rowTop = H / 2 - 30 - 0.2 * planeH; rowBot = cy - sr.height / 2 + 14;
    paper.scale.set(planeW, planeH, 1); paper.position.set(px, pcy, -20);
    glow.scale.set(lr * 9, lr * 9, 1); glow.position.set(cx, cy, -60);
    GR = Math.min(Math.max(W, H) * 0.55, 480); U.uGal.value.set(W * 0.24, cy + H * 0.04);   // core sits up-right of the lens so it is not hidden
    const NS = 2 * GR * 1.05; hazes.forEach((hz) => { hz.m.scale.set(NS * hz.s, NS * hz.s * 0.62, 1); hz.m.position.set(U.uGal.value.x, U.uGal.value.y, hz.z); });
    coreGlow.scale.set(GR * 0.55, GR * 0.4, 1); coreGlow.position.set(U.uGal.value.x, U.uGal.value.y, -30);
    layout(); placeLens(true);
  }

  /* ---------------- state ---------------- */
  const target = [0, 1, 0, 0]; const LENS_SCALE = [1, 0.92, 1]; let lsc = 1, stage = 0, introT = -1, pulse = 0, rippleT = 1;
  const w = U.uW.value;
  const L = { x: 0, y: 0 };
  let mouseOn = 0, tmx = 0, tmy = 0, par = [0, 0], tpar = [0, 0], lastPointer = -1e9, hover = 0;
  let frames = 0, cpuMs = 0, running = false, raf = 0, last = 0, idleSkip = 0, disposed = false, t = 0, dtSum = 0, dtN = 0, qualityDrops = 0, winSum = 0, winN = 0;
  const stats = () => ({ frames, cpuMs: +cpuMs.toFixed(1), perFrameMs: frames ? +(cpuMs / frames).toFixed(3) : 0, particles: N, fragments: frags.length + chips.length, pixelRatio: +dpr.toFixed(2), qualityDrops, avgFrameDtMs: dtN ? +(dtSum / dtN).toFixed(1) : 0 });
  function placeLens(snap) { const p = lensPos[stage]; if (snap) { L.x = p[0]; L.y = p[1]; } }
  const mix4 = (arr) => [w.x, w.y, w.z, w.w].reduce((s, wt, i) => s + wt * arr[i], 0);

  function applyFrame() {
    const lensS = lr * lsc * (1 + pulse * 0.07 + hover * 0.025 - (introT >= 0 ? (1 - Math.min(1, introT / 1.8)) * 0.35 : 0));
    const lx = L.x + par[0] * 10, ly = L.y - par[1] * 10;
    lensG.position.set(lx, ly, 60); lensG.scale.setScalar(lensS); U.uLens.value.set(lx, ly, 0); U.uLr.value = lr * lsc;
    ringDash.mat.uniforms.uRot.value = t * 0.35; ringDash2.mat.uniforms.uRot.value = -t * 0.22;
    glassMat.uniforms.uFocus.value = Math.min(1, w.y + w.z + w.w); glassMat.uniforms.uAlpha.value = 1 - w.x * 0.8;
    clip[0].mat.uniforms.uAlpha.value = w.y * 0.95; clip[1].mat.uniforms.uAlpha.value = w.z; clip[2].mat.uniforms.uAlpha.value = w.w;
    [ringSolid.mat, ringDash.mat, ringDash2.mat].forEach((m, i) => { m.uniforms.uOp.value = (i === 0 ? 0.95 : i === 1 ? 0.75 : 0.5) * (1 - w.x * 0.7); });
    // paper, glow, ripple, arc
    paper.material.opacity = w.z * 0.97 + w.y * 0.05; paper.position.x = px + par[0] * -6;
    glow.material.opacity = 0.55 + 0.45 * (1 - w.x); glow.position.set(lx * 0.4 + cx * 0.6, ly * 0.4 + cy * 0.6, -60);
    ripple.position.set(lx, ly, 20); ripple.scale.set(lr * 7, lr * 7, 1); rippleMat.uniforms.uP.value = Math.min(1, rippleT);
    arcMat.opacity = w.z * 0.85; arc.geometry.setDrawRange(0, Math.floor(arcCount * Math.min(1, Math.max(0, (w.z - 0.25) / 0.6)) / 3) * 3);
    // fragments & chips
    frags.forEach((fr) => {
      let X = 0, Y = 0, Z = 0;
      for (let s = 0; s < 4; s++) { const wt = [w.x, w.y, w.z, w.w][s], q = fr.pos[s]; X += (s === 1 ? q[0] + lx : q[0]) * wt; Y += (s === 1 ? q[1] + ly : q[1]) * wt; Z += q[2] * wt; }
      const mx = W / 2 - fr.w / 2 - 10, my = H / 2 - 118;
      fr.m.position.set(Math.max(-mx, Math.min(mx, X)) + par[0] * -0.6 * Z * 0.05, Math.max(-my, Math.min(my - 20, Y + Math.sin(t * 0.5 + fr.k) * 3 * (0.3 + w.x))), Z); fr.mat.opacity = mix4(fr.op);
    });
    chips.forEach((c) => { c.m.position.set(lx + c.pos[0], ly + c.pos[1] + Math.sin(t * 0.6 + c.k) * 2, c.pos[2]); c.mat.opacity = w.w * 0.98; });
    const gA = -0.38 - t * GAL_ROT * U.uDrift.value, fade = (1 - 0.6 * w.z) * (0.6 + 0.4 * Math.min(1, Math.max(0, U.uIntro.value)));
    hazes.forEach((hz) => { hz.m.rotation.z = gA * (hz.spin ? 1 + hz.spin : 1); hz.mat.uniforms.uOp.value = hz.op * fade; });
    coreGlow.material.opacity = 0.7 * fade;
    stars.forEach((st) => {
      const ang = st.tt * WIND + st.arm * Math.PI + st.off, rad = (0.025 + st.tt) * GR, gx = Math.cos(ang) * rad, gy = Math.sin(ang) * rad * 0.62;
      const c = Math.cos(gA), sn = Math.sin(gA);
      st.m.position.set(U.uGal.value.x + gx * c - gy * sn, U.uGal.value.y + gx * sn + gy * c, 10);
      const tw = Math.pow(Math.max(0, Math.sin(t * st.sp + st.ph)), 3); st.m.scale.setScalar(st.size * (0.7 + 0.5 * tw));
      st.mat.opacity = (0.25 + 0.75 * tw) * fade * (U.uDrift.value ? 1 : 0.6);
    });
    // camera parallax (bounded)
    camera.position.x = par[0] * 16; camera.position.y = -par[1] * 10; camera.lookAt(0, 0, 0);
    renderer.render(scene, camera);
  }
  function settled() { return Math.abs(w.x - target[0]) + Math.abs(w.y - target[1]) + Math.abs(w.z - target[2]) + Math.abs(w.w - target[3]) < 0.004 && introT < 0 && pulse < 0.01 && rippleT >= 1 && Math.abs(L.x - lensPos[stage][0]) + Math.abs(L.y - lensPos[stage][1]) < 0.6; }
  function step(dt, still) {
    t += still ? 0 : dt; U.uTime.value = t;
    const k = introT >= 0 ? 1.0 : 2.9, f = 1 - Math.exp(-dt * k);
    w.x += (target[0] - w.x) * f; w.y += (target[1] - w.y) * f; w.z += (target[2] - w.z) * f; w.w += (target[3] - w.w) * f;
    if (introT >= 0) { introT += dt; U.uIntro.value = Math.max(0, Math.min(1, introT / 2.6)); if (introT > 2.8) { introT = -1; U.uIntro.value = 1; } }
    pulse *= Math.exp(-dt * 3.5); if (rippleT < 1) rippleT = Math.min(1, rippleT + dt / 1.5);
    const lf = 1 - Math.exp(-dt * 4.2), p = lensPos[stage]; L.x += (p[0] - L.x) * lf; L.y += (p[1] - L.y) * lf; lsc += (LENS_SCALE[stage] - lsc) * lf;
    const pf = 1 - Math.exp(-dt * 6);
    mouseOn += ((performance.now() - lastPointer < 1500 ? 1 : 0) - mouseOn) * pf;
    U.uMouseOn.value = mouseOn; U.uMouse.value.x += (tmx - U.uMouse.value.x) * pf; U.uMouse.value.y += (tmy - U.uMouse.value.y) * pf;
    par[0] += (tpar[0] - par[0]) * pf; par[1] += (tpar[1] - par[1]) * pf;
    const dl = Math.hypot(U.uMouse.value.x - L.x, U.uMouse.value.y - L.y); hover += ((mouseOn > 0.5 && dl < lr ? 1 : 0) - hover) * pf;
  }
  function adapt(dtMs) { // adaptive resolution: every 30 animated frames, if the average frame time is above ~32 ms (<31 fps), step the pixel ratio down by 0.25 (floor 1.0)
    dtSum += dtMs; dtN++; winSum += dtMs; winN++;
    if (winN >= 30) {
      const avg = winSum / winN; winSum = 0; winN = 0;
      if (avg > 32 && dpr > 1.01) { dpr = Math.max(1, dpr - 0.25); qualityDrops++; renderer.setPixelRatio(dpr); renderer.setSize(W, H, false); U.uPx.value = dpr; }
    }
  }
  function tick(now) {
    if (!running || disposed) return;
    raf = requestAnimationFrame(tick);
    const dt = Math.max(0, Math.min(0.05, (now - last) / 1000)); // rAF timestamps can precede performance.now(): never negative
    const idle = settled() && now - lastPointer > 2500 && mouseOn < 0.01;
    if (idle) { idleSkip += now - last; if (idleSkip < 30) { last = now; return; } idleSkip = 0; } // idle: ~30 fps drift
    if (!idle) adapt(now - last);   // judge speed only while actually animating
    last = now;
    const t0 = performance.now(); step(dt, false); applyFrame(); cpuMs += performance.now() - t0; frames++;
  }
  function snapshot() { // static frame: fixed clock, no animation
    w.set(target[0], target[1], target[2], target[3]); introT = -1; U.uIntro.value = 1; pulse = 0; rippleT = 1; U.uDrift.value = 0; t = 4.2; U.uTime.value = t;
    mouseOn = 0; U.uMouseOn.value = 0; par = [0, 0]; hover = 0; L.x = lensPos[stage][0]; L.y = lensPos[stage][1]; lsc = LENS_SCALE[stage];
    const t0 = performance.now(); applyFrame(); cpuMs += performance.now() - t0; frames++;
  }

  const api = {
    THREE, stats,
    resize() { if (disposed) return; measure(); if (!running) { if (opts.reduced()) snapshot(); else applyFrame(); } },
    setStage(n, instant) {
      stage = n; target[0] = 0; target[1] = n === 0 ? 1 : 0; target[2] = n === 1 ? 1 : 0; target[3] = n === 2 ? 1 : 0;
      pulse = 1; rippleT = 0;
      if (instant || opts.reduced()) { if (instant) { L.x = lensPos[n][0]; L.y = lensPos[n][1]; lsc = LENS_SCALE[n]; } snapshot(); }
      else if (!running) { for (let i = 0; i < 120 && !settled(); i++) step(1 / 30, true); applyFrame(); }
    },
    /** choreographed intro: scattered galaxy swirls in and organises. Plays once (caller guards). */
    intro() { if (opts.reduced()) { w.set(0, 1, 0, 0); snapshot(); return; } w.set(1, 0, 0, 0); introT = 0; U.uIntro.value = 0; U.uDrift.value = 1; rippleT = 0; if (!running) applyFrame(); },
    pointer(x, y, on) {
      if (!on) { lastPointer = -1e9; return; }
      lastPointer = performance.now(); tmx = x - W / 2; tmy = H / 2 - y;
      tpar = [Math.max(-1, Math.min(1, (x / W) * 2 - 1)), Math.max(-1, Math.min(1, (y / H) * 2 - 1))];
    },
    start() { if (running || disposed) return; U.uDrift.value = 1; running = true; last = performance.now(); raf = requestAnimationFrame(tick); },
    stop() { running = false; cancelAnimationFrame(raf); },
    isRunning: () => running,
    renderOnce() { if (opts.reduced()) snapshot(); else applyFrame(); },
    dispose() {
      disposed = true; running = false; cancelAnimationFrame(raf);
      geo.dispose(); pmat.dispose(); paper.geometry.dispose(); paper.material.dispose(); paperTex.dispose(); glow.geometry.dispose(); glow.material.dispose(); glowTex.dispose();
      ripple.geometry.dispose(); rippleMat.dispose(); if (arc) arc.geometry.dispose(); arcMat.dispose();
      frags.concat(chips).forEach((f) => { f.m.geometry.dispose(); f.mat.dispose(); f.tex.dispose(); });
      lensG.children.forEach((c) => { c.geometry.dispose(); c.material.dispose(); });
      clip.forEach((c) => c.tex.dispose()); hazes.forEach((hz) => { hz.m.geometry.dispose(); hz.mat.dispose(); }); nebRT.dispose(); stars.forEach((st) => { st.m.geometry.dispose(); st.mat.dispose(); }); starTex.dispose(); coreGlow.geometry.dispose(); coreGlow.material.dispose(); coreTex.dispose();
      renderer.dispose(); try { renderer.forceContextLoss(); } catch (e) {}
    },
  };
  measure();
  U.uDrift.value = opts.reduced() ? 0 : 1;
  return api;
}
