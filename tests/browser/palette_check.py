"""Colour check for the map / heatmap / charts area (sketchbook palette): every visible text meets WCAG AA.
Usage: ~/agelens-tools/pw/bin/python tests/browser/palette_check.py [base-url]   (default http://127.0.0.1:8765)
The earlier rule ("no warm hues") belonged to the white/blue/violet style and was retired with the 2026-10-27 restyle
(warm paper + brown ink is now the palette). What still matters is legibility: for every element that renders its own
text inside the home data section (.dt: all five metrics, one industry, a selection) and the Explore charts, the text
colour is compared with the nearest opaque background colour behind it (alpha-composited up the ancestor chain).
FAILS (exit 1) if any text is below 4.5:1, or any filled heatmap cell is below 4.5:1."""
import json, re, sys
from playwright.sync_api import sync_playwright
OPEN_MORE = "new MutationObserver(() => document.querySelectorAll('details.mp-more:not([data-t])').forEach((d) => { d.open = true; d.dataset.t = '1'; })).observe(document, {childList: true, subtree: true})"  # the map's extra views sit under "More views" (closed by default); these checks need them open

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
ARGS = ["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"]
TEXT = """(root) => { const out = [];
  const rgba = (s) => { const m = s.match(/[\\d.]+/g); if (!m) return [0, 0, 0, 0]; return [+m[0], +m[1], +m[2], m[3] != null ? +m[3] : 1]; };
  const over = (top, bot) => { const a = top[3]; return [0, 1, 2].map((i) => top[i] * a + bot[i] * (1 - a)).concat(1); };
  function bgOf(el) {   // composite background colours from the element up to the first opaque one (page paper as the floor)
    const layers = [];
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) { const c = rgba(getComputedStyle(e).backgroundColor); if (c[3] > 0.01) { layers.push(c); if (c[3] >= 0.99) break; } }
    let col = [255, 249, 245, 1];
    for (let i = layers.length - 1; i >= 0; i--) col = over(layers[i], col);
    return col;
  }
  document.querySelectorAll(root).forEach((top) => [top, ...top.querySelectorAll('*')].forEach((el) => {
    if (!el.childNodes || ![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) return;
    if (el.closest('svg') || el.closest('[hidden]') || el.closest('details:not([open]) > :not(summary)')) return;
    const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity < 0.05) return;
    const r = el.getBoundingClientRect(); if (r.width < 1 || r.height < 1) return;
    const fg = rgba(cs.color), bg = bgOf(el);
    out.push({ cls: String(el.className).slice(0, 40), text: el.textContent.trim().slice(0, 24), fg: over(fg, bg).slice(0, 3), bg: bg.slice(0, 3) });
  })); return out; }"""


def lum(r, g, b):
    c = [(v / 255) / 12.92 if v / 255 <= 0.03928 else (((v / 255) + 0.055) / 1.055) ** 2.4 for v in (r, g, b)]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    l1, l2 = lum(*a), lum(*b)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


low, n_text, cells = [], 0, []


def scan(rows, where):
    global n_text
    for r in rows:
        n_text += 1
        cr = ratio(r["fg"], r["bg"])
        if cr < 4.5:
            low.append({"where": where, "class": r["cls"], "text": r["text"], "ratio": round(cr, 2)})


with sync_playwright() as p:
    b = p.chromium.launch(args=ARGS)
    pg = b.new_page(viewport={"width": 1440, "height": 900}); pg.add_init_script(OPEN_MORE)
    pg.goto(BASE + "/#/"); pg.wait_for_timeout(1200)
    pg.evaluate("document.getElementById('data-map-panel').scrollIntoView({block:'start'})")
    pg.wait_for_function("window.AgeLens._mapView && AgeLens._mapView.state()", timeout=20000); pg.wait_for_timeout(3500)
    pg.evaluate("document.querySelector('.mp-heat').scrollIntoView()"); pg.wait_for_timeout(1500)
    for key in ("ads", "aw", "cap", "exc", "med"):
        pg.evaluate(f"AgeLens._mapView.setMetric('{key}')"); pg.wait_for_timeout(1300)
        scan(pg.evaluate(TEXT, ".dt"), "home:" + key)
        cells += pg.evaluate("""() => [...document.querySelectorAll('.mp-hm-cell:not(.nd)')].map((c) => [getComputedStyle(c).backgroundColor, getComputedStyle(c).color])""")
    pg.locator(".mp-chip", has_text="Sales").click(); pg.wait_for_timeout(1200)
    pg.locator(".mp-rankbtn").first.click(); pg.wait_for_timeout(1500)
    pg.locator(".mp-guide summary").click(); pg.wait_for_timeout(300)
    scan(pg.evaluate(TEXT, ".dt"), "home:sales+selected+notes")
    pg.goto(BASE + "/#/explore"); pg.wait_for_timeout(3000)
    scan(pg.evaluate(TEXT, ".ex-charts"), "explore")
    pg.locator(".ex-charts .ch-bar").nth(1).click(); pg.wait_for_timeout(2000)
    scan(pg.evaluate(TEXT, ".ex-charts"), "explore:selected")
    b.close()

worst, bad = 99, []
for bg, fg in cells:
    x = [float(v) for v in re.findall(r"[\d.]+", bg)[:3]]; y = [float(v) for v in re.findall(r"[\d.]+", fg)[:3]]
    cr = ratio(x, y); worst = min(worst, cr)
    if cr < 4.5: bad.append([bg, fg, round(cr, 2)])
print(json.dumps({"text_elements_checked": n_text, "low_contrast_text": len(low), "examples": low[:10],
                  "heatmap_cells_checked": len(cells), "lowest_cell_text_contrast": round(worst, 2), "low_cells": bad[:5]}, indent=1))
sys.exit(1 if (low or worst < 4.5) else 0)
