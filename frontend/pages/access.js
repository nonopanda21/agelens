/* Invite code (#/access). Public demo only (server started with --public; backend/api_access.py):
   gate(el, done) is shown instead of every page while this browser has no invite session; render(el) shows the
   current code's label, role and expiry with a sign-out button. Locally it only says that no code is needed.
   The browser keeps the session token and the code's label/role, never the invite code itself. */
(function () {
  const h = AgeLens.h;

  function fmt(iso) {
    if (!iso) return 'no end date';
    const d = new Date(iso.length === 10 ? iso + 'T00:00:00Z' : iso);
    return isNaN(d) ? iso : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  function gate(el, done) {
    const inp = h('input', { id: 'inv-code', autocomplete: 'off', autocapitalize: 'characters', spellcheck: 'false', maxlength: 40, placeholder: 'AL-XXXX-XXXX', required: true, 'aria-describedby': 'inv-help' });
    const btn = h('button.btn.btn-primary', { type: 'submit' }, 'Enter');
    const st = h('p.rq-status.hint', { 'aria-live': 'polite' });
    const form = h('form.card.inv-form', {}, AgeLens.stateIcon('lock'),
      h('label', { for: 'inv-code' }, 'Invite code'), inp,
      h('p.hint#inv-help', {}, 'You received it from the AgeLens team. Capital letters and dashes are optional.'), st, btn);
    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      if (!inp.value.trim()) { st.className = 'rq-status notice error'; st.textContent = 'Enter the invite code first.'; inp.focus(); return; }
      btn.disabled = true; btn.textContent = 'Checking…'; st.className = 'rq-status hint'; st.textContent = '';
      try {
        const r = await AgeLens.api('/api/access/redeem', { json: { code: inp.value } });
        inp.value = '';
        AgeLens.session.set(r.token, { label: r.label, role: r.role, personal: r.personal, expires_at: r.expires_at });
        AgeLens.access = Object.assign({}, AgeLens.access, { signed_in: true, role: r.role, label: r.label, personal: r.personal });
        done();
      } catch (e) {
        st.className = 'rq-status notice error'; st.setAttribute('role', 'alert'); st.textContent = e.message;
        btn.disabled = false; btn.textContent = 'Enter'; inp.select();
      }
    });
    el.replaceChildren(h('div.wrap.section.rq.rq-center.inv', {},
      h('p.rv-kicker', {}, 'Course project demo'), h('h1', {}, 'Welcome to AgeLens'),
      h('p.hint.inv-lede', {}, 'This is the public demo of a Northwestern SEPOL 425 course project. It is open by invitation. All job ads in it are simulated, and it gives no legal advice and makes no hiring decisions.'),
      form,
      h('ul.inv-facts', {}, h('li', {}, 'No sign-up, no email: the code is all you need.'),
        h('li', {}, 'Please do not enter real personal information anywhere in the demo.'),
        h('li', {}, 'Data on the demo can be reset at any time.'))));
    inp.focus({ preventScroll: true });
  }

  function render(el) {
    const a = AgeLens.access, i = AgeLens.session.info();
    if (!a.invite) {
      el.replaceChildren(h('div.wrap.section.rq.rq-center', {}, h('h1', {}, 'No invite code needed'),
        h('p.hint', {}, a.public ? 'This public demo is open to everyone, so no invite code is needed. All data in it is simulated; please do not enter real personal information.'
          : 'This copy of AgeLens runs on your own computer, so everything is open. Invite codes are used only on a public demo that has them switched on.'),
        h('a.btn.btn-primary', { href: '#/' }, 'Back to Overview')));
      return;
    }
    const out = h('button.btn.btn-quiet', { type: 'button' }, 'Sign out of this browser');
    out.addEventListener('click', async () => {
      out.disabled = true;
      try { await AgeLens.api('/api/access/signout', { method: 'POST', json: {} }); } catch (e) { /* cleared locally either way */ }
      AgeLens.session.clear(); AgeLens.access.signed_in = false; location.hash = '#/';
      AgeLens.showGate();
    });
    el.replaceChildren(h('div.wrap.section.rq.inv', {}, h('p.rv-kicker', {}, 'Your invite'), h('h1', {}, i.label || 'Guest'),
      h('section.card.inv-card', {},
        h('dl.inv-dl', {}, h('dt', {}, 'Access'), h('dd', {}, i.role === 'reviewer' ? 'Reviewer: everything, plus the reviewer workspace' : 'Viewer: everything a job seeker can do'),
          h('dt', {}, 'Requests you send'), h('dd', {}, i.personal ? 'Kept on this code: open them from any browser with the same code' : 'Kept in this browser only (a shared code never shows one person’s requests to another)'),
          h('dt', {}, 'Signed in until'), h('dd', {}, fmt(i.expires_at))),
        h('div.row', {}, h('a.btn.btn-primary', { href: '#/' }, 'Overview'), out))));
  }

  AgeLens.pages.access = { title: 'Invite code', gate, render };
})();
