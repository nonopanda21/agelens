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

  const plainNotice = (t) => { const x = String(t || 'No AI model was used; text drafted by a script for the rehearsal.').replace(/^SIMULATED( rehearsal)?:\s*/, ''); return x.charAt(0).toUpperCase() + x.slice(1); };

  function banner(cfg) {
    if (cfg.simulated && cfg.ai_design) return h('div.st-banner.sim', { role: 'status' }, h('strong', {}, 'SIMULATED practice run, not study data.'),
      h('span', {}, ' ' + plainNotice(cfg.sim_notice)));
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
        const mins = Math.round(cfg.time_limit_s / 60 * 10) / 10;
        const fine = h('p.hint', {}, 'Tasks: ' + cfg.tasks_version + ' (' + cfg.tasks_status.split('.')[0] + '). ' + (cfg.ai_design ? 'Tool A and Tool B are two different writing tools that get the same evidence from the ad. Which is which is explained after the last task. The order is assigned at random after you agree.'
          : cfg.conditions
          ? 'On two tasks you see the ad only; on the other two you also see AgeLens’s evidence check. Which tasks, and in which order, is assigned at random after you agree.'
          : 'You are assigned a writing aid at random after you agree.') + ' Every task has the same time limit (' + mins + ' min) and layout.');
        const fullText = [String(cfg.consent_draft || '').split(/\n\s*\n|\n/).filter((t) => t.trim()).map((t) => h('p', {}, t.trim())), fine];
        const consent = h('section.card.st-consent', { 'aria-labelledby': 'cons-h' },
          cfg.simulated ? h('span.badge.sim', {}, 'Draft · awaiting teacher and ethics approval') : null, h('h2', { id: 'cons-h' }, 'Information and consent'),
          cfg.ai_design ? [h('ul.st-keypoints', {},
              h('li', {}, h('strong', {}, 'Your choice. '), 'You can stop at any time. If you withdraw, the text you wrote is deleted.'),
              h('li', {}, h('strong', {}, 'Anonymous. '), 'We record a random code, the tool used on each task, timing and what you write. Not your name, email or IP address.'),
              h('li', {}, h('strong', {}, 'Fictional. '), 'All ads and job seekers are made up. Please do not type real personal information.'),
              h('li', {}, h('strong', {}, 'Scored blind. '), 'Two people score your text without seeing which tool you used. Results are reported only in aggregate.'),
              h('li', {}, h('strong', {}, 'Limited. '), 'This measures reading and question writing only. It cannot show effects on interviews, hiring or employment.')),
            h('details.st-full', { open: !cfg.simulated }, h('summary', {}, 'Read the full text'), h('div', {}, fullText))] : fullText,
          h('div.st-check', {}, agree, h('label', { for: 'st-agree' }, 'I have read this and agree to take part.')), err, go);
        if (!cfg.ai_design) {
          show(h('h1', {}, 'Write a clarification request'),
            h('p.lead', {}, 'You will read four short fictional job ads and write the message a job seeker could send to ask the employer about the age wording. About 7 minutes per task.'),
            consent, h('p.hint', {}, 'Raters: ', h('a', { href: '#/study/score' }, 'scoring desk')));
          return;
        }
        const step = (n, title, text) => h('li.st-step', {}, h('span.st-step-n', { 'aria-hidden': 'true' }, String(n)), h('h3', {}, title), h('p', {}, text));
        show(h('h1', {}, 'Two writing tools, one job ad'),
          h('p.lead', {}, 'Job ads often mention age in unclear ways. This study compares two writing tools, to see how well people then understand the wording and what they would ask the employer. It tests the tools, not you.'),
          h('ol.st-steps', {},
            step(1, 'Read', 'A short fictional job ad, and the job seeker asking about it.'),
            step(2, 'Check the tool', 'See what it suggests. Tool A on the first two ads, Tool B on the last two.'),
            step(3, 'Write', 'How you read the age wording, and one question for the employer.')),
          h('p.st-meta', {}, h('span', {}, '4 ads'), h('span', {}, 'up to ' + mins + ' minutes each'), h('span', {}, 'about 30 minutes in total')),
          consent,
          h('p.hint', {}, 'Just looking? ', h('a', { href: '#/status' }, 'See the evaluation plan and its limits'), '. Raters: ', h('a', { href: '#/study/score' }, 'scoring desk'), '.'));
      }

      async function nextTask(sess) {
        const step = sess.steps.find((s) => s.state !== 'submitted');
        if (!step) return done(sess);
        let t;
        try { t = await api('/api/study/task/' + step.task_id + '/start', { method: 'POST', json: {} }); }
        catch (e) { if (e.status === 401) { ss.del(SK); return intro(); } show(h('div.notice.error', { role: 'alert' }, e.message)); return; }
        taskView(sess, t);
      }

      function toolCard(aid) {
        const tool = aid.tool || {};
        const list = (title, items) => items && items.length ? h('div', {}, h('h3', {}, title), h('ul', {}, items.map((x) => h('li', {}, x)))) : null;
        return h('section.card.st-aid', { 'aria-labelledby': 'aid-h' }, h('h2', { id: 'aid-h' }, aid.label),
          aid.sim_notice ? h('p', {}, h('span.badge.sim', {}, aid.sim_notice)) : null,
          aid.failed ? h('p.notice', { role: 'status' }, 'This tool could not produce a draft for this task. Write your reading and question yourself; this has been recorded.')
            : h('div.st-tool', {}, tool.reading ? h('div', {}, h('h3', {}, 'Reading of the age wording'), h('p', {}, tool.reading)) : null,
                list('What the ad says explicitly', tool.explicit), list('What is unclear', tool.unclear), list('Checklist to confirm with the employer', tool.checklist),
                tool.question ? h('div', {}, h('h3', {}, 'Question to the employer'), h('p', {}, tool.question)) : null),
          h('p.hint', {}, 'A draft only. It can be wrong or incomplete: check it against the ad and edit freely.'));
      }

      function evidenceCard(ev) {
        return h('section.card.st-evidence', { 'aria-labelledby': 'ev-h' }, h('h2', { id: 'ev-h' }, 'Evidence package'),
          h('p.hint', {}, 'The same for both tools. Found by fixed rules (' + (ev.rule_version || 'rules') + '); no AI model.'),
          h('p', {}, ev.wording_line), h('ul', {}, ev.items.map((x) => h('li', {}, x))));
      }

      /* The reading material behind three tabs, so the writing box stays in view. Arrow keys move between tabs (WAI-ARIA tabs pattern). */
      function refTabs(items) {
        const btns = [], panels = [], seen = new Set();
        const select = (i, focus) => {
          seen.add(i);
          btns.forEach((b, k) => { const on = k === i; b.setAttribute('aria-selected', on ? 'true' : 'false'); b.tabIndex = on ? 0 : -1; panels[k].hidden = !on; });
          if (focus) btns[i].focus({ preventScroll: focus === 'quiet' });
        };
        items.forEach((it, i) => {
          const next = items[i + 1];
          btns.push(h('button.st-rtab', { type: 'button', role: 'tab', id: 'tab-' + it.id, 'aria-controls': 'panel-' + it.id, onclick: () => select(i),
            onkeydown: (e) => {
              const to = e.key === 'ArrowRight' ? (i + 1) % items.length : e.key === 'ArrowLeft' ? (i + items.length - 1) % items.length : e.key === 'Home' ? 0 : e.key === 'End' ? items.length - 1 : -1;
              if (to >= 0) { e.preventDefault(); select(to, true); }
            } }, h('span.st-rtab-n', { 'aria-hidden': 'true' }, String(i + 1)), it.label));
          panels.push(h('div.st-rpanel', { role: 'tabpanel', id: 'panel-' + it.id, 'aria-labelledby': 'tab-' + it.id }, it.body,
            next ? h('button.btn.btn-quiet.st-rnext', { type: 'button', onclick: () => { select(i + 1, 'quiet'); requestAnimationFrame(() => { const head = document.querySelector('.st-head'); window.scrollBy({ top: wrap.getBoundingClientRect().top - (head ? head.getBoundingClientRect().bottom : 0) - 8, behavior: 'instant' }); }); } }, 'Next: ' + next.label) : null));
        });
        const wrap = h('div.st-refs', {}, h('div.st-rtabs', { role: 'tablist', 'aria-label': 'Reading material' }, btns), panels);
        select(0);
        wrap.first = () => btns[0];
        wrap.allSeen = () => seen.size === items.length;
        return wrap;
      }

      function aiTaskView(sess, t) {
        const kr = 'al_study_draft_r_' + t.task.id + '_' + sess.code, kq = 'al_study_draft_q_' + t.task.id + '_' + sess.code;
        const reading = h('textarea', { id: 'st-reading', rows: 5, maxlength: 3000, placeholder: 'How do you read the age wording? What does the ad say, and what is unclear?' });
        const question = h('textarea', { id: 'st-question', rows: 3, maxlength: 3000, placeholder: 'The question you would send the employer…' });
        reading.value = ss.get(kr) || ''; question.value = ss.get(kq) || '';
        const count = h('p.hint', { id: 'st-count' }, '');
        const upd = () => { count.textContent = (reading.value.trim().length + question.value.trim().length) + ' characters'; ss.set(kr, reading.value); ss.set(kq, question.value); };
        reading.addEventListener('input', upd); question.addEventListener('input', upd); upd();
        let inserted = false, submitted = false;
        const live = h('p.vh', { 'aria-live': 'polite', role: 'status' });
        const clock = h('span.st-clock', { role: 'timer', 'aria-label': 'Time left for this task' }, mmss(t.remaining_ms));
        const err = h('p.notice.error', { role: 'alert', hidden: true });
        const tool = t.aid.tool || {};
        const useDraft = (!t.aid.failed && (tool.reading || tool.question)) ? h('button.btn.btn-quiet', { type: 'button', onclick: () => {
          if ((reading.value.trim() || question.value.trim()) && !confirm('Replace what you have written with the tool\'s draft?')) return;
          reading.value = tool.reading || ''; question.value = tool.question || ''; inserted = true; upd(); reading.focus();
        } }, 'Use the tool\'s draft as my starting point') : null;
        const submitBtn = h('button.btn.btn-primary', { type: 'button', onclick: () => {
          if (!reading.value.trim() && !question.value.trim() && !confirm('Your answer is empty. Submit it anyway?')) return;
          if (!refs.allSeen() && !confirm('You have not opened all three tabs. Submit anyway?')) return;
          send(false);
        } }, t.position < t.total ? 'Submit and continue' : 'Submit');
        const t0 = performance.now(), rem0 = t.remaining_ms, limit = t.limit_ms;
        async function send(timedOut) {
          if (submitted) return; submitted = true; stopTimer(); submitBtn.disabled = true; reading.readOnly = true; question.readOnly = true;
          try {
            const r = await api('/api/study/task/' + t.task.id + '/submit', { json: { reading: reading.value, question: question.value, aid_inserted: inserted, timed_out: timedOut, client_elapsed_ms: Math.round(limit - Math.max(0, rem0 - (performance.now() - t0))) } });
            ss.del(kr); ss.del(kq);
            if (timedOut) { show(h('div.notice', { role: 'status' }, 'Time is up. What you had written was saved.'), h('button.btn.btn-primary', { type: 'button', onclick: () => nextTask(r.session) }, r.session.done < r.session.total ? 'Next task' : 'Finish')); }
            else nextTask(r.session);
          } catch (e) { submitted = false; submitBtn.disabled = false; reading.readOnly = false; question.readOnly = false; err.textContent = e.message + ' Your text is still here; try again.'; err.hidden = false; }
        }
        const tick = () => {
          const left = rem0 - (performance.now() - t0);
          clock.textContent = mmss(left); clock.classList.toggle('low', left < 60000);
          const sec = Math.ceil(left / 1000);
          if (sec === 60) live.textContent = 'One minute left.'; else if (sec === 30) live.textContent = 'Thirty seconds left.';
          if (left <= 0) send(true);
        };
        const refs = refTabs([{ id: 'ad', label: 'Ad and job seeker', body: taskFacts(t.task) }, { id: 'ev', label: 'Evidence', body: evidenceCard(t.evidence) }, { id: 'tool', label: t.aid.label, body: toolCard(t.aid) }]);
        // the heading is the job title, not the task's internal title: "Hard age cap" would hand over the answer being scored
        show(h('header.st-head', {}, h('div', {}, h('p.st-prog', {}, h('span.st-dots', { 'aria-hidden': 'true' }, Array.from({ length: t.total }, (_, i) => h('i' + (i < t.position - 1 ? '.done' : i === t.position - 1 ? '.now' : '')))), 'Task ' + t.position + ' of ' + t.total + ' · ' + t.aid.label), h('h1', {}, jobTitle(t.task))),
            h('div.st-timer', {}, h('span.hint', {}, 'Time left'), clock)),
          h('p.st-how', {}, 'Go through the three tabs, then write your answer. Please use no real personal information.'),
          live, h('div.st-work', {}, refs, h('div.st-write.st-side', {},
            h('section.card', { 'aria-labelledby': 'ans-h' }, h('h2', { id: 'ans-h' }, 'Your answer'), h('label', { for: 'st-reading' }, 'How you read the age wording'), reading,
              h('label', { for: 'st-question' }, 'The question you would send the employer'), question, h('div.st-tools', {}, count, useDraft), err, h('div.st-actions', {}, submitBtn, withdrawBtn())))));
        timer = setInterval(tick, 250);
        refs.first().focus({ preventScroll: true });
      }

      function taskView(sess, t) {
        if (cfg.ai_design) return aiTaskView(sess, t);
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
        show(h('header.st-head', {}, h('div', {}, h('p.hint', {}, 'Task ' + t.position + ' of ' + t.total), h('h1', {}, jobTitle(t.task))),
            h('div.st-timer', {}, h('span.hint', {}, 'Time left'), clock)),
          h('p.lead', {}, 'Write the clarification request this job seeker would send to the employer before applying. 3 to 8 sentences. No real personal information.'),
          live, h('div.st-grid', {}, taskFacts(t.task), h('div.st-write', {}, aidCard,
            h('div.card', {}, h('label', { for: 'st-answer' }, 'The clarification request you would send'), area, count, err, h('div.st-actions', {}, submitBtn, withdrawBtn())))));
        timer = setInterval(tick, 250); // after show(), which clears any previous timer
        area.focus({ preventScroll: true });
      }

      function done(sess) {
        ss.del(SK);
        const rev = sess.reveal;
        show(h('h1', {}, 'Thank you — all four tasks are done'),
          rev ? h('section.card', {}, h('h2', {}, 'Which tool was which'), h('p', {}, 'Tool A: ' + rev.A), h('p', {}, 'Tool B: ' + rev.B)) : null,
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
