/* Pro (#/pro) and the report panel used by the Job Seeker page (AgeLens.reportPanel). Stage 1 of the paid plan: no payment;
   Pro codes come from the AgeLens team. Free: everything except the full Word report. Pro: the report, one credit each.
   The preview (outline + summary numbers) is free. The server checks the code and takes the credit (backend/api_pro.py). */
(function () {
  const h = AgeLens.h;

  function fmtDate(d) {
    if (!d) return 'no end date';
    const x = new Date(d + 'T00:00:00Z');
    return isNaN(x) ? d : x.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });  // the code's last valid day is a UTC date
  }

  /** A small "enter a Pro code" form. done(wallet) after a successful redeem. */
  function codeForm(done, idSuffix) {
    const id = 'pro-code-' + (idSuffix || 'x');
    const inp = h('input', { id, autocomplete: 'off', autocapitalize: 'characters', spellcheck: 'false', maxlength: 40, placeholder: 'PRO-XXXX-XXXX', required: true });
    const btn = h('button.btn.btn-primary', { type: 'submit' }, 'Unlock');
    const st = h('p.rq-status.hint', { 'aria-live': 'polite' });
    const f = h('form.pro-code', {}, h('label', { for: id }, 'Pro code'), h('div.pro-code-row', {}, inp, btn), st);
    f.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      if (!inp.value.trim()) { st.className = 'rq-status notice error'; st.textContent = 'Enter the Pro code first.'; inp.focus(); return; }
      btn.disabled = true; st.className = 'rq-status hint'; st.textContent = 'Checking…';
      try {
        const w = await AgeLens.api('/api/pro/redeem', { json: { code: inp.value } });
        inp.value = ''; AgeLens.pro.set(w.token, w.label); st.textContent = ''; done(w);
      } catch (e) { st.className = 'rq-status notice error'; st.setAttribute('role', 'alert'); st.textContent = e.message; inp.select(); }
      finally { btn.disabled = false; }
    });
    return f;
  }

  /** POST /api/report and save the .docx. -> {left} or throws Error(message) with .status / .data. */
  async function download(body) {
    const headers = Object.assign({ 'Content-Type': 'application/json' }, AgeLens.pro.headers());
    const sess = AgeLens.session && AgeLens.session.token();
    if (sess) headers.Authorization = 'Bearer ' + sess;  // public demo with invite codes
    let res;
    try { res = await fetch('/api/report', { method: 'POST', headers, body: JSON.stringify(body) }); }
    catch (e) { throw Object.assign(new Error('Cannot reach the AgeLens server. Try again.'), { status: 0 }); }
    if (!res.ok) { const d = await res.json().catch(() => ({})); throw Object.assign(new Error(d.error || 'The report could not be made (' + res.status + ').'), { status: res.status, data: d }); }
    const blob = await res.blob();
    const name = ((res.headers.get('Content-Disposition') || '').match(/filename="([^"]+)"/) || [])[1] || 'AgeLens-report.docx';
    const url = URL.createObjectURL(blob);
    const a = h('a', { href: url, download: name }); document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
    return { left: +(res.headers.get('X-Credits-Left') || 0), name };
  }

  /** Report panel for the Job Seeker answer: free preview, then unlock or generate. body = the same body /api/brief got. */
  AgeLens.reportPanel = async function (box, body) {
    box.replaceChildren(h('p.hint', { role: 'status' }, 'Preparing the report preview…'));
    let o;
    try { o = await AgeLens.api('/api/report/preview', { json: body }); }
    catch (e) { box.replaceChildren(h('p.notice.error', { role: 'alert' }, e.message)); return; }
    const sm = o.summary;
    const preview = h('div.pro-preview', {},
      h('p', {}, h('strong', {}, 'Full report (Word, about ' + o.pages_estimate + ' pages): '), sm.analysed + ' ads analysed, with every ad’s age wording quoted, region and occupation comparisons, and a draft message.'),
      h('ol.pro-toc', {}, o.sections.map((t, i) => h('li', { class: i === 0 ? 'open' : '' }, t))),
      h('div.pro-sum', {}, h('p.hint', {}, 'Preview of section 1 (free):'),
        h('ul', {}, Object.entries(sm.by_class).filter(([, v]) => v).map(([k, v]) => h('li', {}, k + ': ' + v + (v === 1 ? ' ad' : ' ads'))),
          sm.ads_stating_a_max_below_your_age != null ? h('li', {}, sm.ads_stating_a_max_below_your_age + ' of ' + sm.analysed + ' state a maximum age below the age you entered (wording only, not a decision about you)') : null)),
      h('p.hint', {}, o.data_label + ' · rules only, no AI model · the same question gives the same report'));
    const action = h('div.pro-action');
    const paint = async () => {
      let w = { active: false };
      try { w = await AgeLens.pro.status(); } catch (e) { /* treated as no Pro */ }
      if (!w.active) {
        action.replaceChildren(h('p', {}, h('span.badge.pro-badge', {}, 'Pro'), ' The full report needs a Pro code. In this course demo, codes come from the AgeLens team; no payment is taken. ',
          h('a', { href: '#/pro' }, 'What is in Pro?')), codeForm(() => paint(), 'panel'));
        return;
      }
      const st = h('p.rq-status.hint', { 'aria-live': 'polite' });
      const btn = h('button.btn.btn-primary', { type: 'button', disabled: w.credits_left < 1 }, w.credits_left < 1 ? 'No report credits left' : 'Generate the full report (uses 1 of ' + w.credits_left + ')');
      btn.addEventListener('click', async () => {
        btn.disabled = true; btn.textContent = 'Building the report…'; st.className = 'rq-status hint'; st.textContent = '';
        try { const r = await download(body); st.className = 'rq-status notice info'; st.textContent = 'Saved ' + r.name + '. ' + r.left + (r.left === 1 ? ' credit' : ' credits') + ' left.'; }
        catch (e) { st.className = 'rq-status notice error'; st.setAttribute('role', 'alert'); st.textContent = e.message; if (e.data && e.data.pro_required) AgeLens.pro.clear(); }
        const keep = st.cloneNode(true); await paint(); action.append(keep);
      });
      action.replaceChildren(h('p', {}, h('span.badge.pro-badge', {}, 'Pro'), ' ' + (w.label || 'Pro code') + ': ' + w.credits_left + ' of ' + w.credits_total + ' report credits left.'), btn, st);
    };
    box.replaceChildren(h('h3', {}, 'Full report'), preview, action);
    await paint();
  };

  async function render(el) {
    const wrap = h('div.wrap.section.rq.pro-page');
    el.replaceChildren(wrap);
    const table = h('table.pro-table', {}, h('thead', {}, h('tr', {}, h('th', { scope: 'col' }, 'Feature'), h('th', { scope: 'col' }, 'Free'), h('th', { scope: 'col' }, 'Pro'))),
      h('tbody', {}, [
        ['Overview, data explorer, regional map, original ad text', '✓', '✓'],
        ['Quick check of one line of age wording', '✓', '✓'],
        ['Job Seeker answer on the page, Markdown download', '✓', '✓'],
        ['Ask a human reviewer', '✓', '✓'],
        ['Full report preview (contents and summary numbers)', '✓', '✓'],
        ['Full Word report: every ad quoted, comparisons, draft message', '—', '✓ (one credit each)'],
      ].map(([f, a, b]) => h('tr', {}, h('th', { scope: 'row' }, f), h('td', {}, a), h('td', {}, b)))));
    const walletBox = h('section.card.pro-wallet', { 'aria-live': 'polite' });
    const paint = async () => {
      let w = { active: false };
      try { w = await AgeLens.pro.status(); } catch (e) { /* no Pro */ }
      if (!w.active) {
        walletBox.replaceChildren(h('h2', {}, 'Unlock Pro'), h('p', {}, 'In this course demo, Pro codes are handed out by the AgeLens team. No payment is taken and no card is needed.'), codeForm(() => paint(), 'page'));
        return;
      }
      const out = h('button.btn.btn-quiet', { type: 'button' }, 'Remove Pro from this browser');
      out.addEventListener('click', async () => { try { await AgeLens.api('/api/pro/signout', { method: 'POST', json: {}, headers: AgeLens.pro.headers() }); } catch (e) {} AgeLens.pro.clear(); paint(); });
      walletBox.replaceChildren(h('h2', {}, h('span.badge.pro-badge', {}, 'Pro'), ' ', w.label || 'Pro code'),
        h('dl.inv-dl', {}, h('dt', {}, 'Report credits'), h('dd', {}, w.credits_left + ' of ' + w.credits_total + ' left'), h('dt', {}, 'Valid until'), h('dd', {}, fmtDate(w.expires))),
        h('p.hint', {}, 'Credits belong to the code, so every browser that enters it shares them. Make a report from the Job Seeker answer.'),
        h('div.row', {}, h('a.btn.btn-primary', { href: '#/seeker' }, 'Go to Job Seeker'), out));
    };
    wrap.append(h('h1', {}, 'AgeLens ', h('span.ink-pink', {}, 'Pro')),
      h('p.hint.rq-lede', {}, 'Reading the data stays free. Pro adds a full Word report you can keep, print or send: every matching ad’s age wording quoted, what is explicit and what is unclear, how your region and occupation compare, and a draft message to the employer.'),
      table, walletBox,
      h('p.hint', {}, 'The report is built by fixed rules from the same evidence the free answer uses. It is not legal advice, does not say whether you qualify and does not predict any hiring outcome. All data in this demo is simulated.'));
    paint();
  }

  AgeLens.pages.pro = { title: 'Pro', render };
})();
