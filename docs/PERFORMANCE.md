# Performance and render loops (measured 2026-10-24)

**Environment:** headless Chromium with **software WebGL (SwiftShader)** on the course server, 1440×900, device scale 1. Software rasterisation runs on the CPU, so these numbers are **not a real GPU** and are not representative of a laptop or desktop GPU. No frames-per-second claim is made for real devices. Re-run: `~/agelens-tools/pw/bin/python tests/browser/perf.py [base-url]` (exit 0 = all hard checks pass).

## Design rules being checked
- At most ONE heavy WebGL loop at a time (`frontend/js/gfx.js`): the most visible registered view runs; others stop. Hidden tab, paused motion or OS reduced motion stop everything.
- The regional map renders on demand (only while dragging/hovering/animating its damping), and never while collapsed.
- Leaving the page disposes geometries/materials/renderers and releases WebGL contexts.
- Adaptive quality: hero nebula and lens step the pixel ratio down (2 → 1, by 0.25) when a 30-frame average exceeds ~32 ms; the nebula then thins its particle count (to ≥ 40 %).

## Measured (requestAnimationFrame callbacks counted by an injected wrapper)
| Scene | rAF / s | Notes |
|---|---|---|
| Hero nebula visible | 60.4 | 90,000 points configured, 67,500 drawn after one adaptive step; JS 0.14 ms/frame |
| Evidence lens visible (hero off-screen) | 60.4 | nebula stopped (one loop only); 5,400 points; JS 0.63 ms/frame |
| No graphics on screen | 0.0 | |
| Regional map collapsed | 0.0 | |
| Regional map expanded, idle | 0.0 | render on demand |
| Map drag, 20 pointer moves | 86 frames total | includes damping tail |
| Tab hidden | 0.0 | nebula reports not running |
| "Pause motion" / "Play motion" | stopped / restarted | |
| Route change to #/explore | contexts made 5, released 5 | 0 canvases left |

## Bug found by this check (fixed)
`AgeLens.gfx.webgl()` created a new real WebGL context on every call to test support (four calls per home visit) and never released it, so contexts accumulated across navigation (browsers cap live contexts, about 16 in Chrome, then force-lose the oldest). It now probes once, caches the result and releases the probe context. Before: made 8 / released 4 per visit; after: made 5 / released 5.

## Not measured
Real-GPU frame times, battery/thermal behaviour, Firefox and Safari, remote-desktop compositing cost, and memory over long sessions.
