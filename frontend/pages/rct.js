/* The randomized test (#/study) and its desk (#/study/admin). One group answers alone, the other may open AgeLens.
   The server holds the group, the clock and the answers; this page only shows what it is given. Never uses innerHTML. */
(function () {
  const h = AgeLens.h;
  const SK = 'al_rct_session', TK = 'al_rct_desk_token';
  const store = {
    get() { try { return JSON.parse(localStorage.getItem(SK) || 'null'); } catch (e) { return null; } },
    set(v) { try { localStorage.setItem(SK, JSON.stringify(v)); } catch (e) {} },
    del() { try { localStorage.removeItem(SK); } catch (e) {} },
  };
  const LABEL_HELP = {
    Match: 'The CV meets the age condition the ad states, or the ad states none.',
    Conflict: 'The CV does not meet an age condition the ad requires.',
    Unknown: 'The ad and the CV do not give enough to decide.',
  };
  const mmss = (ms) => { const s = Math.max(0, Math.ceil(ms / 1000)); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };
  const banner = (cfg) => (cfg.simulated
    ? h('div.st-banner.sim', { role: 'status' }, h('strong', {}, 'SIMULATED run, not study data.'), h('span', {}, cfg.set_source === 'rehearsal' ? ' The ads and CVs are fictional, written to rehearse the test.' : ' A pilot of the test.'))
    : h('div.st-banner.formal', { role: 'status' }, h('strong', {}, 'Formal test session')));

  const off = () => h('div.wrap.section', {}, h('h1', {}, 'Page not found'), h('a.btn.btn-primary', { href: '#/' }, 'Back to Overview'));

  AgeLens.pages.rct = {
    title: 'Test',
    async render(el) {
      const cfg = await AgeLens.api('/api/rct/config');
      if (!cfg.enabled) { el.replaceChildren(off()); return; }
      const api = (path, opts = {}) => {
        const s = store.get();
        return AgeLens.api(path, Object.assign({}, opts, { headers: Object.assign({}, opts.headers, s ? { 'X-Participant-Code': s.code, 'X-Participant-Token': s.token } : {}) }));
      };
      const root = h('div.wrap.section.st-page.rct-page');
      el.replaceChildren(h('div', {}, banner(cfg), root));
      let timer = null;
      const stopTimer = () => { if (timer) { clearInterval(timer); timer = null; } };
      // while someone is being tested, the site's own tools are out of reach: the control group must not meet them by accident
      let alive = true;  // a reply that lands after leaving this page must not start a clock or hide the site's menu
      const focus = (on) => document.documentElement.classList.toggle('rct-focus', on && alive);
      AgeLens.onLeave(() => { alive = false; stopTimer(); focus(false); });
      const show = (...kids) => { if (!alive) return; stopTimer(); root.replaceChildren(...kids); window.scrollTo({ top: 0, behavior: 'instant' }); };
      const withdraw = () => h('button.btn.btn-quiet.st-withdraw', { type: 'button', id: 'rct-withdraw', onclick: async () => {
        if (!confirm('Withdraw from the test? Your answers are deleted; only the fact that you withdrew is kept.')) return;
        try { await api('/api/rct/withdraw', { method: 'POST', json: {} }); } catch (e) { alert(e.message); return; }
        store.del(); focus(false);
        show(h('h1', {}, 'You have withdrawn'), h('p', {}, 'Your answers were deleted. Thank you for your time.'), h('a.btn.btn-secondary', { href: '#/' }, 'Back to Overview'));
      } }, 'Withdraw and delete my answers');
      const fail = (e, retry) => show(h('div.problem', { role: 'alert' }, h('h2', {}, 'That did not go through'), h('p', {}, e.message),
        h('button.btn.btn-primary', { type: 'button', onclick: retry }, 'Try again')));

      function intro() {
        focus(false);
        const agree = h('input', { type: 'checkbox', id: 'rct-agree' });
        const code = h('input', { id: 'rct-code', type: 'text', autocomplete: 'off', placeholder: cfg.code_required ? 'Your code' : 'Optional', maxlength: 20 });
        const err = h('p.notice.error', { role: 'alert', hidden: true });
        const go = h('button.btn.btn-primary', { type: 'button', id: 'rct-begin', onclick: async () => {
          err.hidden = true;
          const typed = code.value.trim();
          if (!agree.checked && !typed) { err.textContent = 'Tick the box to confirm you agree. Nothing has been recorded.'; err.hidden = false; return; }
          go.disabled = true;
          try {
            const r = await AgeLens.api('/api/rct/enrol', { json: { consent: agree.checked, code: typed } });
            store.set({ code: r.code, token: r.token });
            route(r.session, !r.resumed);
          } catch (e) { err.textContent = e.message; err.hidden = false; go.disabled = false; }
        } }, 'Begin');
        const step = (n, title, text) => h('li.st-step', {}, h('span.st-step-n', { 'aria-hidden': 'true' }, String(n)), h('h3', {}, title), h('p', {}, text));
        show(h('h1', {}, 'Can you spot an age condition in a job ad?'),
          h('p.lead', {}, 'You see a job ad and a fictional CV, then decide whether the CV meets the ad’s age condition. This test measures whether AgeLens helps people answer more accurately and faster.'),
          h('ol.st-steps', {},
            step(1, 'Get your version', 'The server picks at random: half answer on their own, half can also open AgeLens.'),
            step(2, 'Practise', cfg.n_practice + ' practice cases that do not count.'),
            step(3, 'Answer', cfg.n_scored + ' cases, up to ' + cfg.time_limit_s + ' seconds each. You will not see the answers.')),
          h('section.card.st-consent', { 'aria-labelledby': 'rct-cons' },
            cfg.simulated ? h('span.badge.sim', {}, 'Draft · awaiting teacher approval') : null,
            h('h2', { id: 'rct-cons' }, 'Before you start'),
            h('ul.st-keypoints', {},
              h('li', {}, h('strong', {}, 'Your choice. '), 'You can stop at any time. If you withdraw, your answers are deleted.'),
              h('li', {}, h('strong', {}, 'Anonymous. '), 'We record a code, your group, each answer and the seconds it took. Not your name, email or IP address.'),
              h('li', {}, h('strong', {}, 'Fictional people. '), 'The CVs are made up. Please do not type real personal information.'),
              h('li', {}, h('strong', {}, 'On your own. '), 'Please do not share answers, or use any other AI or search tool.'),
              h('li', {}, h('strong', {}, 'Limited. '), 'This tests reading ads under time limits. It says nothing about hiring or real job outcomes.')),
            h('div.rct-code', {}, h('label', { for: 'rct-code' }, cfg.code_required ? 'Code you were given' : 'Coming back? Your code'), code),
            h('div.st-check', {}, agree, h('label', { for: 'rct-agree' }, 'I have read this and agree to take part.')), err, go));
      }

      function route(session, fresh) {
        focus(!session.finished);
        if (session.finished) return thanks();
        if (session.done) return finish();
        if (fresh) return welcome(session);
        if (session.open_case) return runCase();
        if (session.in_practice) return between('Practice', 'Ready for the next practice case?', 'The clock starts when you continue.');
        return session.scored_done === 0 ? startScored(session) : between('Paused', 'Ready for the next case?', 'The clock starts when you continue.');
      }

      function labelsHelp() {
        return h('dl.st-dl.rct-labels', {}, cfg.labels.map((l) => [h('dt', {}, l), h('dd', {}, LABEL_HELP[l])]));
      }
      function welcome(session) {
        show(h('h1', {}, session.tool ? 'You can use AgeLens' : 'You will answer on your own'),
          h('p.lead', {}, session.tool
            ? 'On each case, you may open AgeLens’s analysis of the ad. It explains the wording but does not give the answer. The clock keeps running while it works.'
            : 'Use only the ad and the CV. Please do not open AgeLens or any other tool.'),
          h('p', {}, 'Your code is ', h('strong.st-code', {}, session.code), '. Keep it if you need to come back: your place and your clock are kept.'),
          h('h2', {}, 'The three answers'), labelsHelp(),
          h('button.btn.btn-primary', { type: 'button', id: 'rct-go', onclick: runCase }, 'Start practice'), h('div.st-actions', {}, withdraw()));
      }
      function between(kicker, title, text) {
        show(h('p.hint', {}, kicker), h('h1', {}, title), h('p', {}, text), h('button.btn.btn-primary', { type: 'button', id: 'rct-go', onclick: runCase }, 'Continue'), h('div.st-actions', {}, withdraw()));
      }
      function startScored(session) {
        show(h('h1', {}, 'Practice is over'), h('p.lead', {}, 'The ' + session.scored_total + ' cases now count. Each has up to ' + cfg.time_limit_s + ' seconds, and you cannot go back.'),
          labelsHelp(), h('button.btn.btn-primary', { type: 'button', id: 'rct-go', onclick: runCase }, 'Start the test'), h('div.st-actions', {}, withdraw()));
      }

      function cvCard(c) {
        const cv = c.cv || {};
        const row = (k, v) => (v ? [h('dt', {}, k), h('dd', {}, v)] : null);
        return h('section.card', { 'aria-labelledby': 'rct-cv' }, h('h2', { id: 'rct-cv' }, 'The CV'), h('p.hint', {}, 'Fictional'),
          h('dl.st-dl', {}, row('Name', cv.name), row('Born', cv.birth_date), row('Graduated', cv.graduation_date), row('Education', cv.education), row('Starts on', c.entry_date)),
          (cv.experience || []).length ? h('ul.rct-exp', {}, cv.experience.map((x) => h('li', {}, x))) : null);
      }
      function toolPanel(view) {
        const list = (title, items) => ((items || []).length ? [h('h3', {}, title), h('ul', {}, items.map((x) => h('li', {}, x)))] : null);
        return h('div.rct-tool-out', {},
          view.note ? h('p.notice', { role: 'alert' }, view.note) : null,
          view.states ? h('p', {}, h('strong', {}, 'What the ad says: '), view.states) : null,
          view.relates ? h('p', {}, h('strong', {}, 'How it relates: '), view.relates) : null,
          list('In the ad', view.stated), list('For this CV', view.related), list('Left open', view.unclear),
          h('p.hint', {}, '“You” here means the person in the CV. AgeLens explains wording. The decision is yours.'));
      }

      async function runCase() {
        let d;
        try { d = await api('/api/rct/next', { method: 'POST', json: {} }); } catch (e) { return !alive ? null : e.status === 401 ? (store.del(), intro()) : fail(e, runCase); }
        if (!alive) return;
        if (d.done) return route(d.session);
        const c = d.case, s = d.session;
        const t0 = performance.now();
        let sent = false;
        const clock = h('span.st-clock', { id: 'rct-clock', role: 'timer', 'aria-label': 'Time left on this case' }, mmss(d.remaining_ms));
        const err = h('p.notice.error', { role: 'alert', hidden: true });
        const send = async (label) => {
          if (sent) return;
          sent = true;
          stopTimer();
          let r;
          try { r = await api('/api/rct/answer', { method: 'POST', json: { case_id: c.id, label, client_elapsed_ms: Math.round(performance.now() - t0) } }); } catch (e) {
            if (!alive) return;
            sent = false;
            err.textContent = e.message + ' Your clock is still running on the server.';
            err.hidden = false;
            return;
          }
          if (!alive) return;
          if (s.in_practice && !r.session.in_practice && !r.session.done) return startScored(r.session);
          return r.session.done ? finish() : runCase();
        };
        const picks = cfg.labels.map((l) => h('label.rct-pick', {}, h('input', { type: 'radio', name: 'rct-label', value: l }), h('span', {}, h('strong', {}, l), h('span.hint', {}, LABEL_HELP[l]))));
        const submit = h('button.btn.btn-primary', { type: 'button', id: 'rct-submit', onclick: () => {
          const v = root.querySelector('input[name=rct-label]:checked');
          if (!v) { err.textContent = 'Choose an answer first.'; err.hidden = false; return; }
          err.hidden = true;
          send(v.value);
        } }, 'Submit answer');
        let tool = null;
        if (d.tool) {
          const out = h('div', { id: 'rct-tool-out', 'aria-live': 'polite' });
          const open = h('button.btn.btn-secondary', { type: 'button', id: 'rct-tool', onclick: async () => {
            open.disabled = true;
            out.replaceChildren(h('p.hint', {}, 'AgeLens is reading this ad. The clock keeps running.'));
            try { const v = await api('/api/rct/tool', { method: 'POST', json: { case_id: c.id } }); open.remove(); out.replaceChildren(toolPanel(v)); } catch (e) {
              open.disabled = false; out.replaceChildren(h('p.notice', { role: 'alert' }, e.message));
            }
          } }, 'Open AgeLens analysis');
          if (d.tool_view) out.replaceChildren(toolPanel(d.tool_view));
          tool = h('section.card.rct-tool', { 'aria-labelledby': 'rct-tool-h' }, h('h2', { id: 'rct-tool-h' }, 'AgeLens'), d.tool_view ? null : open, out);
        }
        const progress = s.in_practice ? 'Practice' : 'Case ' + (s.scored_done + 1) + ' of ' + s.scored_total;
        show(h('div.st-head', {}, h('h1', {}, progress), h('div.st-timer', {}, clock)),
          h('div.st-grid', {},
            h('div.st-facts', {},
              h('section.card.st-ad', { 'aria-labelledby': 'rct-ad' }, h('h2', { id: 'rct-ad' }, c.job_title || 'The ad'), h('pre.st-adtext', {}, c.ad_text), c.ad_text_en ? h('pre.st-adtext', {}, c.ad_text_en) : null),
              cvCard(c)),
            h('div.st-write', {}, tool,
              h('section.card', { 'aria-labelledby': 'rct-ans' }, h('h2', { id: 'rct-ans' }, 'Your answer'), h('div.rct-picks', { role: 'radiogroup', 'aria-labelledby': 'rct-ans' }, picks), err, h('div.st-actions', {}, submit, withdraw())))));
        focus(true);
        window.scrollTo({ top: 0, behavior: 'instant' });
        const tick = () => {
          const left = d.remaining_ms - (performance.now() - t0);
          clock.textContent = mmss(left);
          clock.classList.toggle('low', left < 20000);
          if (left <= 0) send(null);
        };
        timer = setInterval(tick, 500);
        tick();
      }

      function finish() {
        const err = h('p.notice.error', { role: 'alert', hidden: true });
        const pick = (v, t) => h('button.btn.btn-secondary', { type: 'button', 'data-other': v, onclick: async () => {
          try { await api('/api/rct/finish', { method: 'POST', json: { used_other_tools: v } }); focus(false); thanks(); } catch (e) { err.textContent = e.message; err.hidden = false; }
        } }, t);
        focus(true);
        show(h('h1', {}, 'One last question'), h('p.lead', {}, 'Did you use any tool you were not asked to use, such as a search engine or another AI? Your answer does not change anything.'),
          h('div.st-actions', {}, pick('no', 'No'), pick('yes', 'Yes')), err);
      }
      function thanks() {
        const code = (store.get() || {}).code;
        show(h('h1', {}, 'Thank you'), h('p.lead', {}, 'Your answers are recorded. The answers and results are published only after everyone has finished.'),
          code ? h('p', {}, 'Your code: ', h('strong.st-code', {}, code)) : null,
          cfg.simulated ? h('button.btn.btn-secondary', { type: 'button', id: 'rct-again', onclick: () => { store.del(); intro(); } }, 'Run the rehearsal again') : null,
          h('a.btn.btn-quiet', { href: '#/' }, 'Back to Overview'));
      }

      if (store.get()) {
        try { route(await api('/api/rct/session')); } catch (e) {
          if (e.status === 401 && !(e.data && e.data.invite_required)) { store.del(); intro(); } else fail(e, () => AgeLens.pages.rct.render(el));
        }
      } else intro();
    },
  };

  AgeLens.pages.rctAdmin = {
    title: 'Test desk',
    async render(el) {
      const cfg = await AgeLens.api('/api/rct/config');
      if (!cfg.enabled) { el.replaceChildren(off()); return; }
      const root = h('div.wrap.section.st-page.ab');
      el.replaceChildren(root);
      const tokenOf = () => { try { return sessionStorage.getItem(TK) || ''; } catch (e) { return ''; } };
      const api = (path, opts = {}) => AgeLens.api(path, Object.assign({}, opts, { headers: { 'X-Study-Token': tokenOf() } }));

      function signin(msg) {
        const t = h('input', { id: 'rct-token', type: 'password', autocomplete: 'off' });
        const go = h('button.btn.btn-primary', { type: 'button', id: 'rct-signin', onclick: () => { try { sessionStorage.setItem(TK, t.value.trim()); } catch (e) {} draw(); } }, 'Open the desk');
        root.replaceChildren(h('h1', {}, 'Test desk'), h('p.lead', {}, 'For the people running the test.'), msg ? h('p.notice.error', { role: 'alert' }, msg) : null,
          h('div.st-signin', {}, h('label', { for: 'rct-token' }, 'Study token'), t, h('div.st-actions', {}, go)));
      }

      async function draw(note) {
        if (!tokenOf()) return signin();
        let s;
        try { s = await api('/api/rct/admin/status'); } catch (e) { try { sessionStorage.removeItem(TK); } catch (x) {} return signin(e.message); }
        const msg = h('p.notice', { role: 'status', hidden: !note, id: 'rct-msg' }, note || '');
        const say = (t) => { msg.textContent = t; msg.hidden = false; };
        const readFile = (input) => new Promise((ok, no) => { const f = input.files[0]; if (!f) return no(new Error('Choose both files first.')); const r = new FileReader(); r.onload = () => { try { ok(JSON.parse(r.result)); } catch (e) { no(new Error(f.name + ' is not valid JSON.')); } }; r.readAsText(f); });
        const fCases = h('input', { type: 'file', id: 'rct-cases', accept: '.json' }), fKey = h('input', { type: 'file', id: 'rct-key', accept: '.json' });
        const doImport = async () => {
          try {
            const [cases, answer_key] = [await readFile(fCases), await readFile(fKey)];
            const r = await api('/api/rct/admin/import', { json: { cases, answer_key } });
            draw('Imported. Fingerprint ' + r.case_set_sha256.slice(0, 12) + '. ' + (r.formal_problems.length ? r.formal_problems.length + ' problems before it can be used formally.' : 'It meets the formal design.'));
          } catch (e) { say((e.data && e.data.problems ? e.data.problems.join(' ') : e.message)); }
        };
        const nCodes = h('input', { type: 'number', id: 'rct-ncodes', min: 1, max: 500, value: 10 });
        const codesOut = h('pre.st-adtext', { hidden: true, id: 'rct-codes' });
        const makeCodes = async () => { try { const r = await api('/api/rct/admin/codes', { json: { n: Number(nCodes.value) } }); codesOut.textContent = r.codes.join('\n'); codesOut.hidden = false; } catch (e) { say(e.message); } };
        const benchBtn = h('button.btn.btn-secondary', { type: 'button', id: 'rct-bench', onclick: async () => {
          benchBtn.disabled = true;
          const seen = {};
          for (let i = 0; i < s.case_ids.length; i++) {
            say('AI answering case ' + (i + 1) + ' of ' + s.case_ids.length + '…');
            try { const r = await api('/api/rct/admin/benchmark', { json: { case_id: s.case_ids[i] } }); seen[r.status] = (seen[r.status] || 0) + 1; } catch (e) { say(e.message); benchBtn.disabled = false; return; }
          }
          draw('AI answers finished: ' + Object.entries(seen).map(([k, v]) => v + ' ' + k).join(', ') + '.');
        } }, 'Run the AI answers');
        const download = async (scope, table) => {
          try {
            const res = await fetch('/api/rct/admin/export?scope=' + scope + '&table=' + table, { headers: Object.assign({ 'X-Study-Token': tokenOf() }, AgeLens.session && AgeLens.session.token() ? { Authorization: 'Bearer ' + AgeLens.session.token() } : {}) });
            if (!res.ok) throw new Error('Export failed (' + res.status + ').');
            const a = h('a', { href: URL.createObjectURL(await res.blob()), download: 'agelens_rct_' + scope + '_' + table + '.csv' });
            a.click(); URL.revokeObjectURL(a.href);
          } catch (e) { say(e.message); }
        };
        const formal = s.mode === 'formal';
        root.replaceChildren(h('h1', {}, 'Test desk'),
          h('p.lead', {}, 'Mode: ', h('strong', { id: 'rct-mode' }, formal ? 'Formal' : 'Simulation'), '. Test set: ' + (s.set_source === 'rehearsal' ? 'fictional rehearsal set' : s.set_version) + ', ' + s.n_scored + ' cases. Model: ' + s.model + '.'), msg,
          h('section.ab-sec', {}, h('h2', {}, 'Who has taken part'), h('p.hint', {}, 'Counts only. Scores stay out of this page, so nobody can watch the result and decide when to stop.'),
            s.counts.length ? h('table.st-table', { id: 'rct-counts' }, h('thead', {}, h('tr', {}, ['Mode', 'Group', 'Status', 'People'].map((x) => h('th', { scope: 'col' }, x)))),
              h('tbody', {}, s.counts.map((r) => h('tr', {}, [r.mode, r.assigned_group, r.status, r.n].map((x) => h('td', {}, String(x))))))) : h('p', {}, 'Nobody yet.')),
          h('section.ab-sec', {}, h('h2', {}, 'Formal mode'),
            s.formal_allowed ? h('button.btn.btn-primary', { type: 'button', onclick: async () => { try { await api('/api/rct/admin/mode', { json: { mode: formal ? 'simulation' : 'formal' } }); draw(); } catch (e) { say(e.message); } } }, formal ? 'Back to simulation' : 'Switch to formal')
              : [h('p', {}, 'Refused until these are in place:'), h('ul', { id: 'rct-blockers' }, s.formal_blockers.map((x) => h('li', {}, x)))]),
          h('section.ab-sec', {}, h('h2', {}, 'Import the frozen test set'), h('p.hint', {}, 'cases.json holds what people see; answer_key.json stays on the server.'),
            h('div.rct-files', {}, h('label', { for: 'rct-cases' }, 'cases.json'), fCases, h('label', { for: 'rct-key' }, 'answer_key.json'), fKey),
            h('div.st-actions', {}, h('button.btn.btn-secondary', { type: 'button', id: 'rct-import', onclick: doImport }, 'Import')),
            s.set_problems && s.set_problems.length ? h('ul', {}, s.set_problems.map((x) => h('li', {}, x))) : null),
          h('section.ab-sec', {}, h('h2', {}, 'Participant codes'), h('div.st-actions', {}, h('label', { for: 'rct-ncodes' }, 'How many'), nCodes, h('button.btn.btn-secondary', { type: 'button', id: 'rct-mkcodes', onclick: makeCodes }, 'Create codes')), codesOut,
            h('p.hint', {}, s.codes_issued + ' issued so far. Codes are shown once.')),
          h('section.ab-sec', {}, h('h2', {}, 'AI answering alone'), h('p.hint', {}, 'The model answers each scored case once, for comparison with the control group. These calls cost money. ' + s.model_answers + ' of ' + s.n_scored + ' done.'), h('div.st-actions', {}, benchBtn)),
          h('section.ab-sec', {}, h('h2', {}, 'Export'), h('p.hint', {}, 'Answers per case, one row per person, and the AI’s answers.'),
            ['simulation', 'formal'].map((scope) => h('div.st-actions', {}, h('strong', {}, scope === 'formal' ? 'Formal' : 'Simulation'), ['items', 'persons'].map((t) => h('button.btn.btn-quiet', { type: 'button', 'data-export': scope + '-' + t, onclick: () => download(scope, t) }, t)))),
            h('div.st-actions', {}, h('button.btn.btn-quiet', { type: 'button', 'data-export': 'model', onclick: () => download('simulation', 'model') }, 'AI answers'))));
      }
      draw();
    },
  };
})();
