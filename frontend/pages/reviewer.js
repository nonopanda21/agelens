/* Reviewer workspace (#/reviewer, #/reviewer/<code>). Demo-grade sign-in: the server checks X-Reviewer-Token on every call. */
(function () {
  const U = () => AgeLens.reqUi;
  const KEY = 'al_reviewer_token', TAB = 'al_reviewer_tab', PAGE = 12;
  const ss = {
    get(k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { sessionStorage.setItem(k, v); } catch (e) {} },
    del(k) { try { sessionStorage.removeItem(k); } catch (e) {} },
  };
  const unsaved = {};   // code -> reply fields typed but not yet saved/published; survives re-renders and a sign-in detour
  let host = null, offset = 0;

  /** All reviewer calls go through here. A 401 sends the reviewer back to sign-in with a clear message. */
  async function api(path, json) {
    try { return await AgeLens.api(path, { json, method: json ? 'POST' : 'GET', headers: { 'X-Reviewer-Token': ss.get(KEY) || '' } }); }
    catch (e) {
      if (e.status === 401 || (e.status === 429 && /token/i.test(e.message))) {
        ss.del(KEY);
        if (host) signIn(host, e.message + (Object.keys(unsaved).length ? ' Text you typed is kept in this tab and will still be there after you sign in.' : ''));
        e.handled = true;
      }
      throw e;
    }
  }
  const hashCode = () => (location.hash.match(/^#\/reviewer\/([\w-]+)/) || [])[1] || null;
  // public demo: a reviewer invite code is the sign-in (the server accepts it in place of the shared token)
  const viaInvite = () => !!AgeLens.access.invite && AgeLens.session.info().role === 'reviewer';

  function signIn(el, note) {
    const { h, busy } = U();
    const inp = h('input', { id: 'rvtok', type: 'password', autocomplete: 'off', spellcheck: 'false', required: true, 'aria-describedby': 'rvhelp' });
    const btn = h('button.btn.btn-primary', { type: 'submit' }, 'Sign in');
    const st = h('p.rq-status.hint', { 'aria-live': 'polite' }, note || '');
    if (note) { st.className = 'rq-status field-err'; st.setAttribute('role', 'alert'); inp.setAttribute('aria-invalid', 'true'); }
    inp.addEventListener('input', () => inp.removeAttribute('aria-invalid'));
    el.replaceChildren(h('div.wrap.section.rq.rq-center', {}, h('p.rv-kicker', {}, 'Reviewer workspace'), h('h1', {}, 'Reviewer sign-in'),
      h('div.notice.info.rv-demo-note', {}, h('strong', {}, 'Demo-grade access. '),
        'One shared token, no personal accounts, no record of which person acted, and no password recovery. It keeps this demo’s reviewer side apart from seekers on the server, but it is not production authentication and must not be used with real personal data.'),
      h('form.card.rv-signin', { onsubmit: async (ev) => {
        ev.preventDefault();
        ss.set(KEY, inp.value.trim());
        const ok = await busy(btn, 'Checking…', st, () => api('/api/reviewer/requests?limit=1'));
        if (ok) workspace(el, hashCode()); else ss.del(KEY);
      } },
      AgeLens.stateIcon('lock'),
      h('label', { for: 'rvtok' }, 'Demo reviewer token'), inp, st,
      h('p.hint#rvhelp', {}, 'The token is kept in this tab’s session storage only and is forgotten when the tab closes.'),
      btn,
      h('details.ops', {}, h('summary', {}, 'For operators'), h('div', {}, h('p', {}, 'The token is in the file ', h('code', {}, 'data/reviewer_token'), ' in the AgeLens folder, or in the ', h('code', {}, 'AGELENS_REVIEWER_TOKEN'), ' environment variable.'))))));
  }

  function emptyQueue(tab, total) {
    const { h, REV_LABELS } = U();
    if (!total) return h('div.card.rv-empty', {}, AgeLens.stateIcon('inbox'), h('h3', {}, 'No requests yet'), h('p', {}, 'Requests appear here when a job seeker submits one from the Job Seeker page. You can try the whole loop yourself: ask a question there, then come back.'), h('a.btn.btn-primary', { href: '#/seeker' }, 'Open the Job Seeker page'));
    const msg = { pending: 'Nothing is waiting for review. Check Needs information for requests where the seeker is still answering.', needs_info: 'No request is waiting on a seeker answer.', replied: 'No published replies yet.', closed: 'No closed requests yet.' };
    return h('div.rv-empty.quiet', {}, h('p', {}, msg[tab] || 'No requests with status "' + REV_LABELS[tab] + '".'));
  }

  async function workspace(el, code) {
    host = el;
    const { h, fmt, statusBadge, simBadge, errorPanel, REV_LABELS } = U();
    let tab = ss.get(TAB) || 'pending';
    if (!REV_LABELS[tab]) tab = 'pending';
    const queue = h('div.rv-queue'), pane = h('div.rv-detail');
    const root = h('div.wrap.section.rq', {}, h('header.rq-head.rv-top', {}, h('div', {}, h('p.rv-kicker', {}, 'Reviewer workspace'), h('h1', {}, 'Review ', h('span.ink-pink', {}, 'queue'))),
      viaInvite() ? null : h('button.btn.btn-quiet', { type: 'button', onclick: () => { ss.del(KEY); signIn(el); } }, 'Sign out')),
      h('p.hint.rv-demo-line', {}, h('span.badge.demo', {}, 'Demo-grade sign-in'), viaInvite() ? ' Signed in with your reviewer invite code. Not for real personal data.' : ' Shared token, no personal accounts, not for real personal data.'),
      h('div.rv-layout', {}, queue, pane));
    el.replaceChildren(root);

    async function loadQueue() {
      queue.replaceChildren(h('p.hint', { role: 'status' }, 'Loading queue…'));
      let res;
      try { res = await api('/api/reviewer/requests?status=' + encodeURIComponent(tab) + '&limit=' + PAGE + '&offset=' + offset); }
      catch (e) { if (!e.handled) queue.replaceChildren(errorPanel(e, loadQueue)); return; }
      if (!res.requests.length && offset > 0) { offset = 0; return loadQueue(); }
      const tabs = h('div.rv-tabs', { role: 'group', 'aria-label': 'Filter by status' }, Object.keys(REV_LABELS).map((s) =>
        h('button.rv-tab', { type: 'button', 'aria-pressed': String(s === tab), onclick: () => { tab = s; offset = 0; ss.set(TAB, s); loadQueue(); } },
          REV_LABELS[s] + ' ', h('span.rv-count', {}, String(res.counts[s] || 0)))));
      const items = res.requests.length ? h('ul.rq-list', {}, res.requests.map((r) => h('li', {}, h('a.rv-item' + (r.code === code ? '.cur' : ''), { href: '#/reviewer/' + r.code, 'aria-current': r.code === code ? 'true' : null },
        h('span.rq-top', {}, h('span.rq-code', {}, r.code), statusBadge(r.status, REV_LABELS), r.is_demo ? simBadge() : null),
        h('span.rq-q', {}, r.question), h('span.hint', {}, 'Updated ' + fmt(r.updated_at)))))) : emptyQueue(tab, res.total);
      const first = res.matching ? offset + 1 : 0;
      const pager = res.matching > PAGE ? h('div.rv-pager', {}, 
        h('button.btn.btn-quiet', { type: 'button', disabled: offset === 0, onclick: () => { offset = Math.max(0, offset - PAGE); loadQueue(); } }, 'Previous'),
        h('span.hint', { role: 'status' }, first + '–' + (offset + res.requests.length) + ' of ' + res.matching),
        h('button.btn.btn-quiet', { type: 'button', disabled: !res.has_more, onclick: () => { offset += PAGE; loadQueue(); } }, 'Next')) : null;
      queue.replaceChildren(...[tabs, items, pager].filter(Boolean));
    }

    async function loadDetail() {
      if (!code) { pane.replaceChildren(h('div.card.rv-empty.quiet', {}, h('p', {}, 'Select a request from the queue to read the question, the evidence and the background the seeker agreed to share.'))); return; }
      pane.replaceChildren(h('p.hint', { role: 'status' }, 'Loading…'));
      let r;
      try { r = await api('/api/reviewer/requests/' + encodeURIComponent(code)); }
      catch (e) { if (!e.handled) pane.replaceChildren(e.status === 404 ? h('div.card', {}, h('h3', {}, 'Request not found'), h('p', {}, e.message), h('a', { href: '#/reviewer' }, 'Back to the queue')) : errorPanel(e, loadDetail)); return; }
      if (AgeLens.labels && AgeLens.labels.ready) await AgeLens.labels.ready;
      pane.replaceChildren(detailView(r, async () => { await Promise.all([loadQueue(), loadDetail()]); }));
    }
    await Promise.all([loadQueue(), loadDetail()]);
  }

  /** Inline confirmation instead of a blocking browser dialog. */
  function confirmBar(slot, message, confirmLabel, onConfirm) {
    const { h } = U();
    const back = document.activeElement;              // return focus here on Cancel / Escape (no focus loss to <body>)
    const cancel = () => { slot.replaceChildren(); if (back && back.isConnected) back.focus(); };
    const yes = h('button.btn.btn-primary', { type: 'button' }, confirmLabel);
    const no = h('button.btn.btn-quiet', { type: 'button', onclick: cancel }, 'Cancel');
    yes.onclick = () => { slot.replaceChildren(); onConfirm(); };
    const mid = 'rvc-' + Math.random().toString(36).slice(2, 8);
    const box = h('div.rv-confirm', { role: 'alertdialog', 'aria-label': confirmLabel, 'aria-describedby': mid, onkeydown: (e) => { if (e.key === 'Escape') { e.preventDefault(); cancel(); } } },
      h('div', { id: mid }, message), h('div.rv-actions', {}, yes, no));
    slot.replaceChildren(box);
    yes.focus();
  }

  function detailView(r, reload) {
    const { h, fmt, statusBadge, simBadge, REV_LABELS, evidenceCard, profileList, consentBlock, timeline, busy, okStatus, lines } = U();
    const base = '/api/reviewer/requests/' + encodeURIComponent(r.code);
    const draft = r.messages.filter((m) => m.kind === 'draft').pop();
    const reply = r.messages.filter((m) => m.kind === 'reply').pop();
    const box = h('div.rv-body', {});
    const who = { question: 'Seeker question', info_request: 'Information requested', answer: 'Seeker answer', reply: 'Published reply' };
    box.append(h('header.rq-head', {}, h('h2', {}, r.code), statusBadge(r.status, REV_LABELS), r.is_demo ? simBadge() : null),
      h('p.hint', {}, 'Submitted ' + fmt(r.created_at) + ' · updated ' + fmt(r.updated_at) + (r.published_at ? ' · published ' + fmt(r.published_at) : '') + (r.closed_at ? ' · closed ' + fmt(r.closed_at) : '')),
      r.is_demo ? h('div.notice.info', {}, 'Simulated case: the ad evidence below comes from synthetic demo data, not from real postings or a real person.') : null,
      h('section.card', {}, h('h3', {}, 'Question'), h('p.rq-question', {}, r.question)),
      h('section.card', {}, h('h3', {}, 'Shared with consent'), consentBlock(r.consent, 'reviewer'), profileList(r.profile)),
      h('section', {}, h('h3', {}, 'Evidence (' + r.evidence.length + ')'), h('p.hint', {}, 'The ads and their age wording as snapshotted at submission, shown in English. Review actions never edit them.'),
        h('div.rq-evs', {}, r.evidence.map((e, i) => evidenceCard(e, false, i === 0)))),
      h('section', {}, h('h3', {}, 'Conversation'), h('ol.rq-log', {}, r.messages.filter((m) => m.kind !== 'draft').map((m) =>
        h('li.' + m.author, {}, h('strong', {}, who[m.kind] || m.kind), ' ', h('span.hint', {}, fmt(m.created_at)),
          h('p', {}, m.body), m.kind === 'reply' ? h('ul', {}, m.facts.map((x) => h('li', {}, 'Fact: ' + x)), m.to_verify.map((x) => h('li', {}, 'To verify: ' + x)), m.rewrite_suggestion ? h('li', {}, 'Neutral rewrite suggestion: ' + m.rewrite_suggestion) : null) : null)))),
      h('section', {}, h('h3', {}, 'Status history'), h('div.card', {}, timeline(r.events, 'reviewer'))));

    if (r.status === 'closed') { box.append(h('div.notice.info', {}, 'This request is closed. No further actions are available.')); return box; }

    const editable = r.status === 'pending' || r.status === 'needs_info';
    if (editable) {
      const it = h('textarea', { id: 'infobody', maxlength: 8000, rows: 3 });
      const ib = h('button.btn.btn-secondary', { type: 'button' }, 'Ask for more information');
      const ist = h('p.rq-status.hint', { 'aria-live': 'polite' });
      ib.onclick = async () => {
        if (!it.value.trim()) { ist.className = 'rq-status notice error'; ist.textContent = 'Write what you need to know first.'; it.focus(); return; }
        const ok = await busy(ib, 'Sending…', ist, () => api(base + '/info-request', { body: it.value }));
        if (ok) reload();
      };
      box.append(h('section.card.rv-info', {}, h('h3', {}, 'Ask the seeker for more information'),
        r.status === 'needs_info' ? h('p.hint', {}, 'Already waiting for the seeker. Sending another message adds to the conversation.') : null,
        h('label', { for: 'infobody' }, 'Message to the seeker (status becomes Needs information)'), it, ib, ist));

      const init = unsaved[r.code] || { body: draft ? draft.body : '', facts: draft ? draft.facts.join('\n') : '', verify: draft ? draft.to_verify.join('\n') : '', rewrite: draft ? draft.rewrite_suggestion : '' };
      const body = h('textarea', { id: 'rbody', maxlength: 8000, rows: 4 }, init.body);
      const facts = h('textarea', { id: 'rfacts', maxlength: 8000, rows: 4 }, init.facts);
      const verify = h('textarea', { id: 'rverify', maxlength: 8000, rows: 4 }, init.verify);
      const rewrite = h('textarea', { id: 'rrewrite', maxlength: 8000, rows: 3 }, init.rewrite);
      const payload = () => ({ body: body.value, facts: lines(facts.value), to_verify: lines(verify.value), rewrite_suggestion: rewrite.value });
      const db = h('button.btn.btn-secondary', { type: 'button' }, 'Save draft');
      const pb = h('button.btn.btn-primary', { type: 'button' }, 'Review and publish');
      const st = h('p.rq-status.hint', { 'aria-live': 'polite' }, draft ? 'Draft last saved ' + fmt(draft.created_at) + '. Not visible to the seeker.' : 'No draft saved yet. Nothing here is visible to the seeker until you publish.');
      const slot = h('div');
      const markDirty = () => { unsaved[r.code] = { body: body.value, facts: facts.value, verify: verify.value, rewrite: rewrite.value }; if (!st.classList.contains('error')) { st.className = 'rq-status hint dirty'; st.textContent = 'Unsaved changes. Save a draft to keep them on the server.'; } };
      [body, facts, verify, rewrite].forEach((t) => t.addEventListener('input', markDirty));
      db.onclick = async () => {
        const ok = await busy(db, 'Saving draft…', st, () => api(base + '/draft', payload()));
        if (ok) { delete unsaved[r.code]; okStatus(st, 'Draft saved ' + fmt(ok.draft_saved_at) + '. Not visible to the seeker.'); }
      };
      pb.onclick = () => {
        const p = payload();
        const problems = [];
        if (!p.body.trim()) problems.push('Write a reply summary.');
        if (!p.facts.length) problems.push('List at least one fact that the ad text directly supports.');
        const inval = (t, bad) => (bad ? t.setAttribute('aria-invalid', 'true') : t.removeAttribute('aria-invalid'));
        inval(body, !p.body.trim()); inval(facts, !p.facts.length);
        if (problems.length) { st.className = 'rq-status notice error'; st.setAttribute('role', 'alert'); st.textContent = problems.join(' '); (!p.body.trim() ? body : facts).focus(); return; }
        st.className = 'rq-status hint'; st.textContent = '';
        confirmBar(slot, h('div', {}, h('p', {}, h('strong', {}, 'Publish this reply to the seeker now?')),
          h('p.hint', {}, p.facts.length + ' fact(s) and ' + p.to_verify.length + ' judgement(s) to verify' + (p.rewrite_suggestion.trim() ? ', plus a neutral rewrite suggestion shown separately' : '') + '. The seeker sees it immediately and a published reply cannot be edited. The draft is removed.')),
          'Publish reply', async () => {
            const ok = await busy(pb, 'Publishing…', st, () => api(base + '/publish', p));
            if (ok) { delete unsaved[r.code]; reload(); }
          });
      };
      box.append(h('section.card.rv-reply', {}, h('h3', {}, 'Reply to the seeker'),
        h('p.hint', {}, 'Describe what the ad text says and what it leaves open. Avoid conclusions about legality, motive or hiring chances. Keep facts and judgements apart; the seeker sees them in separate boxes.'),
        h('label', { for: 'rbody' }, 'Reply summary'), body,
        h('div.rv-split', {}, h('div.rv-col.facts', {}, h('label', { for: 'rfacts' }, 'Facts directly supported by the ad text'), h('p.hint', {}, 'One per line. At least one is required.'), facts),
          h('div.rv-col.verify', {}, h('label', { for: 'rverify' }, 'Judgements that need verification'), h('p.hint', {}, 'One per line. Optional.'), verify)),
        h('label', { for: 'rrewrite' }, 'Optional neutral rewrite of the wording'), h('p.hint', {}, 'Shown to the seeker separately as a suggestion. It never replaces the original ad text.'), rewrite,
        h('div.rv-actions', {}, db, pb), slot, st));
    } else if (reply) {
      box.append(h('div.notice.info', {}, 'A reply has been published. Close the request when the conversation is finished.'));
    }

    const cb = h('button.btn.btn-quiet', { type: 'button' }, 'Close request');
    const cst = h('p.rq-status.hint', { 'aria-live': 'polite' });
    const cslot = h('div');
    cb.onclick = () => confirmBar(cslot, h('p', {}, h('strong', {}, 'Close this request?'), ' The seeker will see it as closed and nobody can add to it. This cannot be undone.'), 'Close request', async () => {
      const ok = await busy(cb, 'Closing…', cst, () => api(base + '/close', {}));
      if (ok) reload();
    });
    box.append(h('div.rv-actions', {}, cb), cslot, cst);
    return box;
  }

  AgeLens.pages.reviewer = {
    title: 'Reviewer',
    async render(el, params) {
      host = el;
      if (!ss.get(KEY) && !viaInvite()) return signIn(el);
      return workspace(el, params.id || null);
    },
  };
})();
