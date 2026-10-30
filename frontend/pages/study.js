/* Participant side of the evaluation (#/study). Anonymous code, concealed allocation, same time limit and layout in both arms.
   Shared helpers live on AgeLens.studyUi so score.js can reuse them. Never uses innerHTML. */
(function () {
  const h = AgeLens.h;
  const ss = {
    get(k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { sessionStorage.setItem(k, v); } catch (e) {} },
    del(k) { try { sessionStorage.removeItem(k); } catch (e) {} },
  };
  const SK = 'al_study_session';
  const mmss = (ms) => { const s = Math.max(0, Math.ceil(ms / 1000)); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };

  function banner(cfg) {
    if (cfg.simulated) return h('div.st-banner.sim', { role: 'status' }, h('strong', {}, 'Simulation, not study data.'),
      h('span', {}, cfg.conditions ? ' Practice run of the study tools; nothing here is study data.'
        : cfg.model.connected ? ' Pilot of the tools only.' : ' No model is connected, so the drafted help comes from a labelled simulated provider.'));
    return h('div.st-banner.formal', { role: 'status' }, h('strong', {}, 'Formal study session'), h('span', {}, ' Approved protocol in force.'));
  }

  /* English only (docs/ENGLISH_UI.md): the ad is shown as ad_text_en; until a task has it, the study team's English
     gloss stands in. The Chinese ad_text is never rendered. */
  const en = (v) => (AgeLens.labels ? AgeLens.labels.en(v) : (typeof v === 'string' && !AgeLens.hasCJK(v) ? v : null));
  const jobTitle = (task) => en(task.job_title_en) || en(task.job_title) || 'Fictional job';
  function adText(task) {
    const t = en(task.ad_text_en);
    if (t) return h('pre.st-adtext', {}, t);
    const g = en(task.gloss);
    return g ? h('div', {}, h('p.hint', {}, 'English version of the fictional ad:'), h('p.st-gloss.st-adtext', {}, g.replace(/^Study-team English gloss:\s*/, '')))
      : h('p.hint', {}, 'The English text of this ad is not available.');
  }

  function taskFacts(task) {
    const p = task.profile;
    return h('div.st-facts', {},
      h('section.card.st-ad', { 'aria-labelledby': 'ad-h' },
        h('h2', { id: 'ad-h' }, 'The ad'), h('p.hint', {}, task.ad_id + ' · ' + jobTitle(task) + ' · fictional, written for this study'),
        adText(task)),
      h('section.card', { 'aria-labelledby': 'bg-h' },
        h('h2', { id: 'bg-h' }, 'The job seeker'),
        h('dl.st-dl', {}, h('dt', {}, 'Age'), h('dd', {}, String(p.age)), h('dt', {}, 'Experience'), h('dd', {}, p.years_experience + ' years'),
          h('dt', {}, 'Field'), h('dd', {}, p.occupation), h('dt', {}, 'Region'), h('dd', {}, p.region), p.note ? h('dt', {}, 'Note') : null, p.note ? h('dd', {}, p.note) : null),
        h('p.st-q', {}, h('strong', {}, 'Their question: '), task.question)));
  }

  AgeLens.studyUi = { h, ss, banner, taskFacts, mmss };

  AgeLens.pages.study = {
    title: 'Study',
    async render(el) {
      const api = (path, opts = {}) => {
        const s = JSON.parse(ss.get(SK) || 'null');
        const headers = Object.assign({}, opts.headers, s ? { 'X-Participant-Code': s.code, 'X-Participant-Token': s.token } : {});
        return AgeLens.api(path, Object.assign({}, opts, { headers }));
      };
      const cfg = await AgeLens.api('/api/study/config');
      let timer = null;
      const stopTimer = () => { if (timer) { clearInterval(timer); timer = null; } };
      AgeLens.onLeave(stopTimer);
      const root = h('div.wrap.section.st-page');
      el.replaceChildren(h('div', {}, banner(cfg), root));
      const show = (...kids) => { stopTimer(); root.replaceChildren(...kids); };

      function withdrawBtn(after) {
        return h('button.btn.btn-quiet.st-withdraw', { type: 'button', onclick: async () => {
          if (!confirm('Withdraw from the study? The text you wrote is deleted; only the fact that you withdrew is kept.')) return;
          try { await api('/api/study/withdraw', { method: 'POST', json: {} }); } catch (e) { alert(e.message); return; }
          ss.del(SK); show(h('h1', {}, 'You have withdrawn'), h('p', {}, 'The text you wrote was deleted. Thank you for your time.'), h('a.btn.btn-secondary', { href: '#/' }, 'Back to Overview'));
        } }, 'Withdraw and delete my text');
      }

      function intro() {
        const agree = h('input', { type: 'checkbox', id: 'st-agree' });
        const err = h('p.notice.error', { role: 'alert', hidden: true });
        const go = h('button.btn.btn-primary', { type: 'button', onclick: async () => {
          err.hidden = true;
          if (!agree.checked) { err.textContent = 'Tick the box to confirm you agree to take part. Nothing has been recorded.'; err.hidden = false; return; }
          go.disabled = true; go.textContent = 'Enrolling…';
          try {
            const r = await AgeLens.api('/api/study/enrol', { json: { consent: true } });
            ss.set(SK, JSON.stringify({ code: r.code, token: r.token }));
            nextTask(r.session);
          } catch (e) { err.textContent = e.message; err.hidden = false; go.disabled = false; go.textContent = 'Begin'; }
        } }, 'Begin');
        show(h('h1', {}, 'Write a clarification request'),
          h('p.lead', {}, 'You will read four short fictional job ads and write the message a job seeker could send to ask the employer about the age wording. About 7 minutes per task.'),
          h('section.card.st-consent', { 'aria-labelledby': 'cons-h' },
            h('span.badge.sim', {}, 'Draft · awaiting teacher and ethics approval'), h('h2', { id: 'cons-h' }, 'Information and consent'),
            String(cfg.consent_draft || '').split(/\n\s*\n|\n/).filter((t) => t.trim()).map((t) => h('p', {}, t.trim())),
            h('p.hint', {}, 'Tasks: ' + cfg.tasks_version + ' (' + cfg.tasks_status.split('.')[0] + '). ' + (cfg.conditions
              ? 'On two tasks you see the ad only; on the other two you also see AgeLens’s evidence check. Which tasks, and in which order, is assigned at random after you agree.'
              : 'You are assigned a writing aid at random after you agree.') + ' Every task has the same time limit (' + Math.round(cfg.time_limit_s / 60 * 10) / 10 + ' min) and layout.'),
            h('div.st-check', {}, agree, h('label', { for: 'st-agree' }, 'I have read this and agree to take part.')), err, go),
          h('p.hint', {}, 'Raters: ', h('a', { href: '#/study/score' }, 'scoring desk')));
      }

      async function nextTask(sess) {
        const step = sess.steps.find((s) => s.state !== 'submitted');
        if (!step) return done(sess);
        let t;
        try { t = await api('/api/study/task/' + step.task_id + '/start', { method: 'POST', json: {} }); }
        catch (e) { if (e.status === 401) { ss.del(SK); return intro(); } show(h('div.notice.error', { role: 'alert' }, e.message)); return; }
        taskView(sess, t);
      }

      function taskView(sess, t) {
        const key = 'al_study_draft_' + t.task.id + '_' + sess.code;
        const area = h('textarea', { id: 'st-answer', rows: 9, maxlength: 6000, 'aria-describedby': 'st-count', placeholder: 'Write the message here…' });
        area.value = ss.get(key) || '';
        const count = h('p.hint', { id: 'st-count' }, '');
        const upd = () => { count.textContent = area.value.trim().length + ' characters'; ss.set(key, area.value); };
        area.addEventListener('input', upd); upd();
        let inserted = false, submitted = false;
        const live = h('p.vh', { 'aria-live': 'polite', role: 'status' });
        const clock = h('span.st-clock', { role: 'timer', 'aria-label': 'Time left for this task' }, mmss(t.remaining_ms));
        const err = h('p.notice.error', { role: 'alert', hidden: true });
        const aid = t.aid;
        const insertBtn = aid.text ? h('button.btn.btn-quiet', { type: 'button', onclick: () => {
          if (area.value.trim() && !confirm('Replace what you have written with the aid text?')) return;
          area.value = aid.text; inserted = true; upd(); area.focus();
        } }, 'Insert into my answer') : null;
        const aidCard = aid.kind === 'none'
          ? h('section.card.st-aid.st-aid-none', { 'aria-labelledby': 'aid-h' }, h('h2', { id: 'aid-h' }, 'No extra help on this task'),
              h('p', {}, 'Use the ad text and the background shown. On some other tasks you see AgeLens’s evidence check instead.'))
          : aid.kind === 'agelens'
          ? h('section.card.st-aid', { 'aria-labelledby': 'aid-h' }, h('h2', { id: 'aid-h' }, 'AgeLens evidence check'),
              h('p', {}, h('span.badge', {}, 'AgeLens · rules only')),
              aid.failed ? h('p.notice', { role: 'status' }, 'The evidence check could not be produced for this task. Write your request without it; this has been recorded.')
                : h('pre.st-aidtext', {}, aid.text),
              h('p.hint', {}, 'This is what AgeLens shows for this ad: the wording it found, what is unclear, and questions you could ask. It is not a message; write your own and copy parts if useful. It can miss things, so check it against the ad.'))
          : h('section.card.st-aid', { 'aria-labelledby': 'aid-h' },
          h('h2', { id: 'aid-h' }, 'Writing aid'), h('p', {}, h('span.badge' + (aid.simulated ? '.sim' : ''), {}, aid.kind === 'template' ? 'Fixed template' : (aid.simulated ? 'Drafted help · SIMULATED provider' : 'Drafted help'))),
          aid.failed ? h('p.notice', { role: 'status' }, 'The drafted help could not be produced for this task. Write your request without it; this has been recorded.')
            : h('pre.st-aidtext', {}, aid.text),
          h('p.hint', {}, aid.kind === 'template' ? 'The same template is shown for every task. Fill the bracketed parts and edit freely.' : 'A starting point only. Check it against the ad; edit freely. It may contain mistakes.'),
          insertBtn);
        const submitBtn = h('button.btn.btn-primary', { type: 'button', onclick: () => send(false) }, t.position < t.total ? 'Submit and continue' : 'Submit');
        const t0 = performance.now(), rem0 = t.remaining_ms, limit = t.limit_ms;
        async function send(timedOut) {
          if (submitted) return; submitted = true; stopTimer(); submitBtn.disabled = true; area.readOnly = true;
          try {
            const r = await api('/api/study/task/' + t.task.id + '/submit', { json: { answer: area.value, aid_inserted: inserted, timed_out: timedOut, client_elapsed_ms: Math.round(limit - Math.max(0, rem0 - (performance.now() - t0))) } });
            ss.del(key);
            if (timedOut) { show(h('div.notice', { role: 'status' }, 'Time is up. What you had written was saved.'), h('button.btn.btn-primary', { type: 'button', onclick: () => nextTask(r.session) }, r.session.done < r.session.total ? 'Next task' : 'Finish')); }
            else nextTask(r.session);
          } catch (e) { submitted = false; submitBtn.disabled = false; area.readOnly = false; err.textContent = e.message + ' Your text is still here; try again.'; err.hidden = false; }
        }
        const tick = () => {
          const left = rem0 - (performance.now() - t0);
          clock.textContent = mmss(left);
          clock.classList.toggle('low', left < 60000);
          const s = Math.ceil(left / 1000);
          if (s === 60) live.textContent = 'One minute left.'; else if (s === 30) live.textContent = 'Thirty seconds left.';
          if (left <= 0) send(true);
        };
        show(h('header.st-head', {}, h('div', {}, h('p.hint', {}, 'Task ' + t.position + ' of ' + t.total), h('h1', {}, t.task.title)),
            h('div.st-timer', {}, h('span.hint', {}, 'Time left'), clock)),
          h('p.lead', {}, 'Write the clarification request this job seeker would send to the employer before applying. 3 to 8 sentences. No real personal information.'),
          live, h('div.st-grid', {}, taskFacts(t.task), h('div.st-write', {}, aidCard,
            h('div.card', {}, h('label', { for: 'st-answer' }, 'The clarification request you would send'), area, count, err, h('div.st-actions', {}, submitBtn, withdrawBtn())))));
        timer = setInterval(tick, 250); // after show(), which clears any previous timer
        area.focus({ preventScroll: true });
      }

      function done(sess) {
        ss.del(SK);
        show(h('h1', {}, 'Thank you — all four tasks are done'),
          h('p.lead', {}, 'Your participant code is ', h('strong.st-code', {}, sess.code), '. Keep it if you want to ask for your data to be removed later; nobody can look up your identity from it.'),
          cfg.simulated ? h('p.notice', { role: 'status' }, 'This was a simulation session. It is stored separately and excluded from any formal export.') : null,
          h('p', {}, 'Your texts will be scored by two raters who do not know which aid you had. Results are reported in aggregate only.'),
          h('a.btn.btn-secondary', { href: '#/' }, 'Back to Overview'));
      }

      const saved = JSON.parse(ss.get(SK) || 'null');
      if (saved) {
        try { const sess = await api('/api/study/session'); if (sess.status === 'withdrawn') { ss.del(SK); return intro(); } return nextTask(sess); }
        catch (e) { ss.del(SK); }
      }
      intro();
    },
  };
})();
