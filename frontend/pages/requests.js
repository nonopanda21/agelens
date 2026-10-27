/* My requests (#/requests, #/requests/<code>). Also exports shared UI helpers as AgeLens.reqUi (used by reviewer.js). */
(function () {
  const h = AgeLens.h;
  const LABELS = { pending: 'Pending review', needs_info: 'Needs your information', replied: 'Replied', closed: 'Closed' };
  const REV_LABELS = { pending: 'Pending', needs_info: 'Needs information', replied: 'Replied', closed: 'Closed' };
  const SIM = 'Demo · Synthetic data';
  const EVENT_LABELS = {
    created: 'Request submitted', info_requested: 'Reviewer asked for more information', answered: 'Seeker answered',
    draft_saved: 'Reply draft saved (reviewer only)', published: 'Reply published', closed: 'Request closed',
  };

  const store = {
    get(k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { sessionStorage.setItem(k, v); } catch (e) {} },
    del(k) { try { sessionStorage.removeItem(k); } catch (e) {} },
  };

  function fmt(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
  }
  function statusBadge(status, labels) {
    return h('span.badge.rqst.rqst-' + status, {}, (labels || LABELS)[status] || status);
  }
  function simBadge() { return h('span.badge.sim', { title: 'This case was built from simulated, synthetic ad data' }, SIM); }

  /** Original text with the age sentences highlighted (<mark class="age">). Text only, never HTML. */
  function highlighted(text, terms) {
    text = text || '';
    const spans = [];
    for (const t of terms || []) {
      let s = t.start_offset, e = t.end_offset;
      if (!(Number.isInteger(s) && Number.isInteger(e) && e > s && text.slice(s, e) === t.snippet)) {
        const i = t.snippet ? text.indexOf(t.snippet) : -1;
        if (i < 0) continue;
        s = i; e = i + t.snippet.length;
      }
      spans.push([s, e]);
    }
    spans.sort((a, b) => a[0] - b[0]);
    const out = []; let pos = 0;
    for (const [s, e] of spans) {
      if (s < pos) continue;
      if (s > pos) out.push(text.slice(pos, s));
      out.push(h('mark.age', {}, text.slice(s, e)));
      pos = e;
    }
    if (pos < text.length) out.push(text.slice(pos));
    return h('p.orig', { lang: 'zh-CN' }, out);
  }

  function ageTermLine(t) {
    const kinds = { max: 'Upper limit', min: 'Lower limit', range: 'Range', relaxable: 'Relaxable', ambiguous: 'Uncertain' };
    let range = '';
    if (t.min_age != null && t.max_age != null) range = t.min_age + '-' + t.max_age;
    else if (t.max_age != null) range = 'up to ' + t.max_age;
    else if (t.min_age != null) range = 'from ' + t.min_age;
    return h('li', {}, (kinds[t.kind] || t.kind || 'Age wording') + (range ? ' (' + range + ')' : '') + (t.exception_text ? ' · exception wording: ' : ''),
      t.exception_text ? h('span.zh-orig', { lang: 'zh-CN' }, t.exception_text) : null);
  }

  function evidenceCard(ev, withLink, open) {
    // English province / source; company and original location stay as muted original text (evidence matching).
    const L = AgeLens.labels, metaKids = [];
    const addM = (...n) => { if (metaKids.length) metaKids.push(' · '); metaKids.push(...n.filter((x) => x != null)); };
    if (ev.company) addM(h('span.zh-orig', { lang: 'zh-CN' }, ev.company));
    if (ev.province || ev.city) addM(ev.province ? L.prov(ev.province) : 'Region not stated', ' ', L.orig([ev.province, ev.city].filter(Boolean).join(' ')));
    if (ev.occupation) addM(L.occ(ev.occupation));
    if (ev.posted_date) addM(ev.posted_date);
    if (ev.source) addM(L.source(ev.source));
    const meta = metaKids.length ? metaKids : null;
    const terms = ev.age_terms || [];
    return h('details.card.rq-ev', { open: open !== false }, 
      h('summary', {}, h('span.rq-ev-title', { lang: 'zh-CN' }, ev.title || ev.id), ev.is_demo ? simBadge() : null),
      meta ? h('p.hint', {}, meta) : null,
      h('p.hint', {}, 'Original ad text (Chinese, unaltered). Age wording is highlighted.'),
      highlighted(ev.description || (terms[0] && terms[0].snippet) || '', terms),
      terms.length ? h('ul.rq-terms', {}, terms.map(ageTermLine)) : h('p.hint', {}, 'No explicit age wording detected in this ad (this is not a statement that none exists).'),
      withLink ? h('a', { href: '#/evidence/' + encodeURIComponent(ev.id) }, 'Open full evidence page') : null);
  }

  const PROFILE_LABELS = { age: 'Age', occupation: 'Occupation', years_experience: 'Years of experience', skills: 'Skills', region: 'Target region', education: 'Education', summary: 'Summary' };
  function profileList(p) {
    const keys = Object.keys(PROFILE_LABELS).filter((k) => p && p[k] != null && p[k] !== '');
    if (!keys.length) return h('p.hint', {}, 'No background fields were shared.');
    return h('dl.rq-dl', {}, keys.flatMap((k) => [h('dt', {}, PROFILE_LABELS[k]), h('dd', {}, Array.isArray(p[k]) ? p[k].join(', ') : k === 'occupation' ? AgeLens.labels.occ(String(p[k])) : k === 'region' ? AgeLens.labels.prov(String(p[k])) : String(p[k]))]));
  }

  /** Consent record. who = 'seeker' | 'reviewer' only changes the wording. */
  function consentBlock(c, who) {
    const title = who === 'seeker' ? 'Shared with your consent' : 'Shared with the seeker’s consent';
    if (!c || c.legacy || !c.fields) {
      return h('p.hint.rq-consent', {}, 'No consent record exists for this request (it was created before consent was recorded).');
    }
    const names = c.fields.map((f) => PROFILE_LABELS[f] || f);
    return h('div.rq-consent', {},
      h('p', {}, h('strong', {}, title + ': '), names.length ? names.join(', ') : 'no background fields', ' + the selected ad evidence.'),
      h('p.hint', {}, 'Recorded ' + fmt(c.recorded_at) + '. Background fields not listed here were not sent to the server' + (who === 'seeker' ? '.' : ' and must not be asked for outside this request.')));
  }

  /** Status history. Events carry roles and times only, never message text. */
  function timeline(events, who) {
    if (!events || !events.length) return h('p.hint', {}, 'No history recorded.');
    const actor = (a) => (who === 'seeker' ? (a === 'seeker' ? 'You' : 'Reviewer') : (a === 'seeker' ? 'Seeker' : 'Reviewer'));
    const lab = who === 'seeker'
      ? { ...EVENT_LABELS, created: 'You submitted this request', answered: 'You answered' }
      : EVENT_LABELS;
    const names = who === 'seeker' ? LABELS : REV_LABELS;
    return h('ol.rq-tl', {}, events.map((e) => h('li.' + e.actor, {},
      h('span.rq-tl-dot', { 'aria-hidden': 'true' }),
      h('div', {}, h('strong', {}, lab[e.event] || e.event), ' ', h('span.hint', {}, '· ' + actor(e.actor) + ' · ' + fmt(e.at)),
        e.from_status && e.from_status !== e.to_status ? h('div.hint', {}, names[e.from_status] + ' → ' + names[e.to_status]) : null))));
  }

  /** Error panel; offers Retry for network/server problems. */
  function errorPanel(err, retry, extra) {
    const net = err.status === 0 || err.status >= 500;
    return h('div.notice.error.rq-err', { role: 'alert' }, h('p', {}, h('strong', {}, net ? 'Could not reach the server. ' : ''), err.message),
      extra || null, net && retry ? h('button.btn.btn-quiet', { type: 'button', onclick: retry }, 'Try again') : null);
  }

  /** Run fn while the button shows a real saving state; errors go to the status line. Input is never cleared here. */
  async function busy(btn, label, statusEl, fn) {
    const orig = btn.textContent;
    btn.disabled = true; btn.textContent = label; btn.setAttribute('aria-busy', 'true');
    statusEl.className = 'rq-status hint'; statusEl.textContent = '';
    try { return await fn(); }
    catch (e) {
      if (e && e.handled) return null;
      statusEl.className = 'rq-status notice error'; statusEl.setAttribute('role', 'alert');
      statusEl.textContent = e.message + (e.status === 0 || e.status >= 500 ? ' Your text is still here; try again.' : '');
      return null;
    } finally { btn.disabled = false; btn.textContent = orig; btn.removeAttribute('aria-busy'); }
  }
  function okStatus(el, msg) { el.className = 'rq-status hint ok'; el.removeAttribute('role'); el.textContent = msg; }
  function lines(v) { return v.split('\n').map((x) => x.trim()).filter(Boolean); }

  AgeLens.reqUi = { h, fmt, statusBadge, simBadge, highlighted, evidenceCard, profileList, consentBlock, timeline, errorPanel, busy, okStatus, lines, store, LABELS, REV_LABELS, SIM };

  // ---- pages ----
  function replyBlock(m) {
    const list = (items) => h('ul', {}, items.map((x) => h('li', {}, x)));
    return h('section.card.rq-reply', {},
      h('h2', {}, 'Reviewer reply'), h('p.hint', {}, 'Published ' + fmt(m.created_at) + ' · written and confirmed by a human reviewer'),
      m.body ? h('p', {}, m.body) : null,
      h('div.rq-two', {},
        h('div.rq-facts', {}, h('h3', {}, 'Facts directly supported by the ad text'), m.facts.length ? list(m.facts) : h('p.hint', {}, 'None listed.')),
        h('div.rq-verify', {}, h('h3', {}, 'Judgements that need further verification'), m.to_verify.length ? list(m.to_verify) : h('p.hint', {}, 'None listed.'))),
      m.rewrite_suggestion ? h('div.rq-rewrite', {}, h('h3', {}, 'Suggested neutral wording'), h('p.hint', {}, 'A suggestion only. The original ad text is unchanged.'), h('p', {}, m.rewrite_suggestion)) : null);
  }

  function convo(messages) {
    const who = { question: 'You asked', info_request: 'Reviewer asks for more information', answer: 'You answered' };
    const items = messages.filter((m) => who[m.kind]);
    return h('ol.rq-log', {}, items.map((m) => h('li.' + m.author, {}, h('strong', {}, who[m.kind]), ' ', h('span.hint', {}, fmt(m.created_at)), h('p', {}, m.body))));
  }

  function noTokenPanel(code) {
    return h('div.card.rq-recover', {}, h('h2', {}, 'This browser cannot open ' + code),
      h('p', {}, 'Your private access key for a request is created when you submit it and is kept only in the browser where you submitted it. This browser does not have the key for ' + code + '.'),
      h('ul', {}, h('li', {}, 'Open My requests in the browser (and browser profile) you used to submit. The request will be listed there.'),
        h('li', {}, 'If site data was cleared or you used a private window, the key is gone and cannot be recovered, because the server only stores a one-way hash of it.'),
        AgeLens.access.invite ? h('li', {}, 'On the public demo, requests sent with a personal invite code open in any browser where you enter that code.') : null,
        h('li', {}, 'You can ask your question again with a new request. Nothing here is visible to anyone who lacks the key.')),
      h('div.rv-actions', {}, h('a.btn.btn-primary', { href: '#/seeker' }, 'Start a new request'), h('a.btn.btn-quiet', { href: '#/requests' }, 'My requests')));
  }

  async function detail(el, code) {
    if (AgeLens.labels && AgeLens.labels.ready) await AgeLens.labels.ready;
    const tok = AgeLens.ownerTokens.all()[code];
    // without the key in this browser, a personal invite code the request is kept on can open it instead (public demo)
    const auth = tok ? { 'X-Owner-Token': tok } : {};
    const wrap = h('div.wrap.section.rq');
    el.replaceChildren(wrap);
    wrap.append(h('p', {}, h('a', { href: '#/requests' }, '← All my requests')));
    if (!tok && !AgeLens.session.info().personal) { wrap.append(noTokenPanel(code)); return; }
    const body = h('div', {}, h('p.hint', { role: 'status' }, 'Loading…'));
    wrap.append(body);
    let r;
    try { r = await AgeLens.api('/api/requests/' + encodeURIComponent(code), { headers: auth }); }
    catch (e) {
      if (e.status === 404 || e.status === 401) body.replaceChildren(h('div', {}, h('div.notice.error', { role: 'alert' }, e.message + (tok ? ' The key stored in this browser does not match this request.' : ' It is not kept on your invite code.')), noTokenPanel(code)));
      else body.replaceChildren(errorPanel(e, () => detail(el, code)));
      return;
    }
    const reply = r.messages.filter((m) => m.kind === 'reply').pop();
    body.replaceChildren(h('header.rq-head', {}, h('h1', {}, r.code), statusBadge(r.status), r.is_demo ? simBadge() : null),
      h('p.hint', {}, 'Submitted ' + fmt(r.created_at) + ' · last update ' + fmt(r.updated_at) + (r.published_at ? ' · reply published ' + fmt(r.published_at) : '') + (r.closed_at ? ' · closed ' + fmt(r.closed_at) : '')));
    if (r.status === 'pending') body.append(h('div.notice.info', {}, 'Waiting for a human reviewer. Nothing has been published yet. You can close this page and come back from this browser' + (AgeLens.session.info().personal ? ' or any browser where you enter your invite code.' : '.')));
    if (r.status === 'closed' && !reply) body.append(h('div.notice.info', {}, 'This request was closed without a published reply.'));
    if (reply) body.append(replyBlock(reply));
    if (r.status === 'needs_info') {
      const last = r.messages.filter((m) => m.kind === 'info_request').pop();
      const key = 'al_ans_' + code;
      const ta = h('textarea', { id: 'ans', maxlength: 8000, required: true, rows: 5 }, store.get(key) || '');
      ta.addEventListener('input', () => store.set(key, ta.value));
      const btn = h('button.btn.btn-primary', { type: 'submit' }, 'Send answer');
      const st = h('p.rq-status.hint', { 'aria-live': 'polite' });
      body.append(h('form.card.rq-answer', { onsubmit: async (ev) => {
        ev.preventDefault();
        if (!ta.value.trim()) { st.className = 'rq-status notice error'; st.textContent = 'Please write an answer first.'; ta.focus(); return; }
        const ok = await busy(btn, 'Sending…', st, () => AgeLens.api('/api/requests/' + encodeURIComponent(code) + '/answer', { json: { body: ta.value }, headers: auth }));
        if (ok) { store.del(key); detail(el, code); }
      } }, h('h2', {}, 'The reviewer needs more information'), last ? h('blockquote.rq-quote', {}, last.body) : null,
      h('label', { for: 'ans' }, 'Your answer'), ta,
      h('p.hint', {}, 'Only share what you are comfortable with. Do not include phone numbers or ID numbers. Your draft is kept in this tab until you send it.'), btn, st));
    }
    body.append(h('section', {}, h('h2', {}, 'Conversation'), convo(r.messages)),
      h('section', {}, h('h2', {}, 'History'), h('div.card', {}, timeline(r.events, 'seeker'))),
      h('section', {}, h('h2', {}, 'Background you shared'), h('div.card', {}, consentBlock(r.consent, 'seeker'), profileList(r.profile))),
      h('section', {}, h('h2', {}, 'Evidence you submitted (' + r.evidence.length + ')'), h('p.hint', {}, 'A snapshot taken at submission time; it does not change if the dataset changes later.'),
        h('div.rq-evs', {}, r.evidence.map((e, i) => evidenceCard(e, true, i === 0)))));
    if (r.scope) body.append(h('details.rq-scope-box', {}, h('summary', {}, 'Search scope snapshot'), h('pre.rq-scope', {}, JSON.stringify(r.scope, null, 2))));
  }

  async function list(el) {
    const tokens = AgeLens.ownerTokens.all(), codes = Object.keys(tokens);
    const personal = !!AgeLens.access.invite && AgeLens.session.info().personal;  // public demo, personal invite code
    const wrap = h('div.wrap.section.rq', {}, h('h1', {}, 'My ', h('span.ink-pink', {}, 'requests')),
      personal ? h('p.hint.rq-lede', {}, 'Requests you send with your personal invite code are kept on the code, so they open in any browser where you enter it. Requests sent from this browser earlier are listed too.')
        : h('p.hint.rq-lede', {}, 'Each request has a private access key that stays in this browser only. Another browser, a private window or cleared site data cannot open these requests, and the key cannot be recovered.'));
    el.replaceChildren(wrap);
    let onAccount = [];
    if (personal) {
      try { onAccount = (await AgeLens.api('/api/access/requests')).requests; } catch (e) { /* the list below still shows this browser's requests */ }
    }
    if (!codes.length && !onAccount.length) {
      wrap.append(h('div.card.rq-empty', {}, AgeLens.stateIcon('inbox'), h('h2', {}, 'No requests from this browser yet'),
        h('p', {}, 'Ask about an ad’s age wording, choose the evidence and background you are happy to share, and a human reviewer will reply. Your request will be listed here.'),
        h('p.hint', {}, 'Submitted from another browser? Open My requests there; the key is not stored on the server.'),
        h('a.btn.btn-primary', { href: '#/seeker' }, 'Ask about my situation')));
      return;
    }
    const holder = h('div', {}, h('p.hint', { role: 'status' }, 'Loading…'));
    wrap.append(holder);
    let res = { requests: [], unavailable: [] };
    if (codes.length) {
      try { res = await AgeLens.api('/api/requests/mine', { headers: { 'X-Owner-Tokens': codes.map((c) => c + '=' + tokens[c]).join(',') } }); }
      catch (e) { holder.replaceChildren(errorPanel(e, () => list(el))); return; }
    }
    // one list: requests kept on the personal code plus this browser's, without duplicates, newest first
    const seen = new Set(res.requests.map((r) => r.code));
    res.requests = res.requests.concat(onAccount.filter((r) => !seen.has(r.code))).sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
    const accCodes = new Set(onAccount.map((r) => r.code));
    holder.replaceChildren();
    if (res.unavailable.length) holder.append(h('div.notice', {}, 'Not found on the server for the key stored here: ' + res.unavailable.join(', ') + '. The local database may have been reset.'));
    if (!res.requests.length) holder.append(h('div.card.rq-empty', {}, AgeLens.stateIcon('search'), h('p', {}, 'None of the keys stored in this browser match a request on this server.'), h('a.btn.btn-primary', { href: '#/seeker' }, 'Start a new request')));
    holder.append(h('ul.rq-list', {}, res.requests.map((r) => h('li', {}, h('a.rq-item', { href: '#/requests/' + r.code },
      h('span.rq-top', {}, h('span.rq-code', {}, r.code), statusBadge(r.status), r.is_demo ? simBadge() : null, accCodes.has(r.code) ? h('span.badge.rq-acc', {}, 'Kept on your code') : null),
      h('span.rq-q', {}, r.question), h('span.hint', {}, 'Submitted ' + fmt(r.created_at) + ' · updated ' + fmt(r.updated_at) + ' · ' + r.evidence_count + (r.evidence_count === 1 ? ' evidence item' : ' evidence items')))))));
  }

  AgeLens.pages.requests = { title: 'My requests', render(el, params) { return params.id ? detail(el, params.id) : list(el); } };
})();
