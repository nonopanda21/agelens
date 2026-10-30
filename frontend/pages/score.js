/* Scoring + operator desk (#/study/score). Blinded to arm and to the other rater. Demo-grade access: local study token + rater label. */
(function () {
  const U = () => AgeLens.studyUi;
  const TK = 'al_study_token', RK = 'al_study_rater';

  AgeLens.pages.score = {
    title: 'Scoring',
    async render(el) {
      const { h, ss, banner, taskFacts } = U();
      const hdr = () => ({ 'X-Study-Token': ss.get(TK) || '', 'X-Rater-Id': ss.get(RK) || '' });
      const api = (path, json) => AgeLens.api(path, { json, method: json ? 'POST' : 'GET', headers: hdr() });
      const cfg = await AgeLens.api('/api/study/config');
      const root = h('div.wrap.section.st-page');
      el.replaceChildren(h('div', {}, banner(cfg), root));

      function signIn(note) {
        const tok = h('input', { id: 'sc-tok', type: 'password', autocomplete: 'off', spellcheck: 'false', required: true });
        const sel = h('fieldset.st-raters', {}, h('legend', {}, 'Rater label (anonymous)'),
          ['R1', 'R2', 'R3'].map((r, i) => h('label.st-radio', {}, h('input', { type: 'radio', name: 'rater', value: r, checked: i === 0 ? true : null }), ' ' + r + (r === 'R3' ? ' (adjudicator: disagreements only)' : ''))));
        const err = h('p.notice.error', { role: 'alert', hidden: !note }, note || '');
        root.replaceChildren(h('h1', {}, 'Scoring ', h('span.ink-pink', {}, 'desk')),
          h('form.card.st-signin', { onsubmit: async (ev) => {
            ev.preventDefault();
            ss.set(TK, tok.value.trim()); ss.set(RK, sel.querySelector('input:checked').value);
            try { await api('/api/study/rater/status'); main('score'); } catch (e) { ss.del(TK); err.textContent = e.message; err.hidden = false; }
          } },
          h('span.badge.sim', {}, 'Demo-grade access — not production authentication'),
          h('p', {}, cfg.ai_design ? 'Raters score each answer on three things: which key facts the reading states correctly, four yes/no checks on the question, and a count of unsupported statements. You will not see which tool the author used, who the author is, or any other rater\'s scores.'
            : 'Raters score each answer on four yes/no criteria plus a severe-error flag. You will not see which writing aid the author had, who the author is, or any other rater\'s scores.'),
          h('p.hint', {}, 'The token stays in this tab\'s session storage.'),
          h('label', { for: 'sc-tok' }, 'Study token'), tok, sel, err, h('button.btn.btn-primary', { type: 'submit' }, 'Sign in'),
          h('details.ops', {}, h('summary', {}, 'For operators'), h('div', {}, h('p', {}, 'The token is in ', h('code', {}, 'data/study/study_token'), ' (or the ', h('code', {}, 'AGELENS_STUDY_TOKEN'), ' environment variable).')))));
      }

      async function main(tab) {
        let st;
        try { st = await api('/api/study/rater/status'); } catch (e) { return signIn(e.status === 401 || e.status === 400 ? e.message : e.message); }
        const tabs = [['calibration', 'Calibration'], ['score', 'Score answers'], ['disagreements', 'Disagreement log'], ['operator', 'Operator']];
        const pane = h('div.st-pane', { 'aria-live': 'polite' });
        const nav = h('div.st-tabs', { role: 'group', 'aria-label': 'Scoring sections' }, tabs.map(([k, label]) =>
          h('button.rv-tab.st-tab', { type: 'button', 'aria-pressed': String(k === tab), onclick: () => main(k) }, label)));
        root.replaceChildren(h('header.st-head', {}, h('div', {}, h('h1', {}, 'Scoring ', h('span.ink-pink', {}, 'desk')),
          h('p.hint', {}, 'Rater ' + st.rater + ' · ' + (st.calibration_done ? 'calibration done' : 'calibration ' + st.calibration_scored + '/' + st.calibration_items) + ' · scored ' + st.scored_by_me + ' of ' + st.scorable_items + ' answers')),
          h('button.btn.btn-quiet', { type: 'button', onclick: () => { ss.del(TK); ss.del(RK); signIn(); } }, 'Sign out')), nav, pane);
        if (tab === 'calibration') calibration(pane, st); else if (tab === 'score') scoring(pane, st);
        else if (tab === 'disagreements') disagreements(pane); else operator(pane);
      }

      /* crossover-ai-v1: the rater sees the two texts only (never the tool, the arm or the author) */
      const answerBlock = (it) => st0.ai
        ? h('section.card.st-answer', {}, h('h2', {}, 'Texts to score'), h('h3', {}, 'Reading of the age wording'), h('blockquote.st-quote', {}, it.reading || '(empty)'),
            h('h3', {}, 'Question to the employer'), h('blockquote.st-quote', {}, it.question || '(empty)'))
        : h('section.card.st-answer', {}, h('h2', {}, 'Answer to score'), h('blockquote.st-quote', {}, it.answer));
      const st0 = { ai: !!cfg.ai_design };

      function aiScoreForm(st, task, onSubmit, label) {
        const R = st.rubric, fget = {}, qget = {};
        const yn = (name, a, b) => h('div.st-yn', {}, [['yes', a], ['no', b]].map(([v, l]) => h('label.st-radio', {}, h('input', { type: 'radio', name, value: v, required: true }), ' ' + l)));
        const pick = (box) => { const x = box.querySelector('input:checked'); return x ? x.value === 'yes' : null; };
        const facts = h('fieldset.st-crit', {}, h('legend', {}, 'Interpretation accuracy: key facts'), h('p.hint', {}, R.facts_rule),
          (task.key_facts || []).map((f) => { const box = h('div.st-fact', {}, h('p', {}, h('strong', {}, f.id + ': '), f.text), yn('f-' + f.id, 'Stated correctly', 'Missing or wrong')); fget[f.id] = () => pick(box); return box; }));
        const qs = R.question_criteria.map((c) => { const fs = h('fieldset.st-crit', {}, h('legend', {}, 'Question: ' + c.id + ' ' + c.name), h('p.hint', {}, c.definition),
            h('details', {}, h('summary', {}, 'Examples'), h('p', {}, h('strong', {}, 'Met: '), c.met_example), h('p', {}, h('strong', {}, 'Not met: '), c.not_met_example)), yn('f-' + c.id, 'Met', 'Not met')); qget[c.id] = () => pick(fs); return fs; });
        const un = h('input', { id: 'f-unsup', type: 'number', min: 0, max: 10, step: 1, value: 0, required: true });
        const unsup = h('fieldset.st-crit.st-severe', {}, h('legend', {}, 'Unsupported statements'), h('p.hint', {}, R.unsupported.definition),
          h('ul.st-sev', {}, R.unsupported.types.map((t) => h('li', {}, h('strong', {}, t.id + ' ' + t.name + ': '), t.definition + ' e.g. ' + t.example))), h('label', { for: 'f-unsup' }, 'Count (0-10)'), un);
        const notes = h('textarea', { id: 'f-notes', rows: 3, maxlength: 500, placeholder: 'Optional. No names or personal details.' });
        const err = h('p.notice.error', { role: 'alert', hidden: true });
        const btn = h('button.btn.btn-primary', { type: 'submit' }, label);
        return h('form.st-scoreform', { onsubmit: async (ev) => {
          ev.preventDefault(); err.hidden = true;
          const body = { facts: {}, notes: notes.value, unsupported: parseInt(un.value, 10) };
          for (const id of Object.keys(fget)) { body.facts[id] = fget[id](); if (body.facts[id] === null) { err.textContent = 'Mark every key fact.'; err.hidden = false; return; } }
          for (const id of Object.keys(qget)) { body[id] = qget[id](); if (body[id] === null) { err.textContent = 'Answer all four question checks.'; err.hidden = false; return; } }
          if (!(body.unsupported >= 0 && body.unsupported <= 10)) { err.textContent = 'Enter a count from 0 to 10.'; err.hidden = false; return; }
          btn.disabled = true;
          try { await onSubmit(body); } catch (e) { err.textContent = e.message; err.hidden = false; btn.disabled = false; }
        } }, facts, qs, unsup, h('label', { for: 'f-notes' }, 'Notes'), notes, err, btn);
      }

      /* ---- rubric form shared by calibration and live scoring ---- */
      function scoreForm(st, onSubmit, label, task) {
        if (st.rubric.kind === 'ai') return aiScoreForm(st, task, onSubmit, label);
        const yn = {};
        const fields = st.rubric.criteria.map((c) => {
          const name = 'f-' + c.id;
          const fs = h('fieldset.st-crit', {}, h('legend', {}, c.id.replace('c', '') + '. ' + c.name),
            h('p.hint', {}, c.definition),
            h('details', {}, h('summary', {}, 'Examples'), h('p', {}, h('strong', {}, 'Met: '), c.met_example), h('p', {}, h('strong', {}, 'Not met: '), c.not_met_example)),
            h('div.st-yn', {}, ['yes', 'no'].map((v) => h('label.st-radio', {}, h('input', { type: 'radio', name, value: v, required: true }), ' ' + (v === 'yes' ? 'Met' : 'Not met')))));
          yn[c.id] = () => { const x = fs.querySelector('input:checked'); return x ? x.value === 'yes' : null; };
          return fs;
        });
        const sev = h('input', { type: 'checkbox', id: 'f-sev' });
        const notes = h('textarea', { id: 'f-notes', rows: 3, maxlength: 500, placeholder: 'Optional. No names or personal details.' });
        const err = h('p.notice.error', { role: 'alert', hidden: true });
        const btn = h('button.btn.btn-primary', { type: 'submit' }, label);
        const form = h('form.st-scoreform', { onsubmit: async (ev) => {
          ev.preventDefault(); err.hidden = true;
          const body = { severe: sev.checked, notes: notes.value };
          for (const c of st.rubric.criteria) { body[c.id] = yn[c.id](); if (body[c.id] === null) { err.textContent = 'Answer all four criteria.'; err.hidden = false; const first = form.querySelector('input[name="f-' + c.id + '"]'); if (first) first.focus(); return; } }
          btn.disabled = true;
          try { await onSubmit(body); } catch (e) { err.textContent = e.message; err.hidden = false; btn.disabled = false; }
        } }, fields,
        h('fieldset.st-crit.st-severe', {}, h('legend', {}, 'Severe unsupported claim'),
          h('p.hint', {}, st.rubric.severe_error.definition),
          h('ul.st-sev', {}, st.rubric.severe_error.types.map((t) => h('li', {}, h('strong', {}, t.id + ' ' + t.name + ': '), t.definition + ' e.g. ' + t.example))),
          h('div.st-check', {}, sev, h('label', { for: 'f-sev' }, 'Yes, a severe error is present'))),
        h('label', { for: 'f-notes' }, 'Notes'), notes, err, btn);
        return form;
      }

      async function calibration(pane, st) {
        const { items } = await api('/api/study/calibration');
        const pending = items.filter((i) => !i.scored);
        pane.replaceChildren(h('p', {}, 'Score the frozen calibration examples first. After each one you see the reference scores and the reasoning. ' + (st.rubric.usable_rule || st.rubric.how)));
        pane.append(h('details', {}, h('summary', {}, 'Calibration target and rule'), h('p', {}, 'See rubric: calibration_rule in data/study/tasks.json.')));
        if (!pending.length) {
          const s = await api('/api/study/calibration/summary');
          pane.append(h('div.card', {}, h('h2', {}, 'Calibration complete'), h('p', {}, 'Agreement with the reference: ' + Math.round(s.agreement * 100) + '% of ' + s.judgements + ' judgements' + (cfg.ai_design ? '' : '; severe-flag mismatches: ' + s.severe_mismatches) + '. Target (90%' + (cfg.ai_design ? '' : ' and no severe mismatch') + '): ' + (s.target_met ? 'met.' : 'NOT met — discuss the rubric wording with the team before scoring real answers.')),
            h('button.btn.btn-primary', { type: 'button', onclick: () => main('score') }, 'Go to scoring')));
          return;
        }
        const it = pending[0];
        const box = h('div');
        box.append(h('p.hint', {}, 'Example ' + (items.length - pending.length + 1) + ' of ' + items.length + ' (frozen, synthetic)'), taskFacts(it.task),
          answerBlock(it),
          scoreForm(st, async (body) => {
            const r = await api('/api/study/calibration/' + it.id, body);
            const lab = (k) => k === 'severe' ? 'Severe flag' : k === 'unsupported' ? 'Unsupported count' : /^F\d/.test(k) ? 'Key fact ' + k : /^q\d/.test(k) ? 'Question check ' + k : 'Criterion ' + k.slice(1);
            const refTxt = (k) => cfg.ai_design ? (k === 'unsupported' ? String(r.reference[k]) : (r.reference[k] ? 'yes' : 'no')) : (r.reference[k] ? (k === 'severe' ? 'present' : 'met') : (k === 'severe' ? 'absent' : 'not met'));
            const rows = Object.entries(r.match).map(([k, ok]) => h('li', {}, lab(k) + ': reference ' + refTxt(k) + ' — ' + (ok ? 'you agreed' : 'you differed')));
            box.replaceChildren(h('div.card', {}, h('h2', {}, 'You agreed on ' + r.agreed + ' of ' + (r.of || 5)), h('ul', {}, rows), h('p', {}, h('strong', {}, 'Reasoning: '), r.rationale),
              h('button.btn.btn-primary', { type: 'button', onclick: () => main('calibration') }, 'Next')));
          }, 'Submit and see reference', it.task));
        pane.append(box);
      }

      async function scoring(pane, st) {
        if (!st.calibration_done) { pane.replaceChildren(h('div.notice', { role: 'status' }, 'Finish calibration first.'), h('button.btn.btn-primary', { type: 'button', onclick: () => main('calibration') }, 'Go to calibration')); return; }
        let r;
        try { r = await api('/api/study/rater/next'); } catch (e) { pane.replaceChildren(h('div.notice.error', { role: 'alert' }, e.message)); return; }
        if (!r.item) {
          pane.replaceChildren(h('div.card', {}, h('h2', {}, 'Nothing left to score'), h('p', {}, st.rater === 'R3' ? 'No open disagreements for you.' : 'You have scored every available answer' + (st.mode === 'simulation' ? ' (simulated sessions only).' : '.') + ' New answers appear as participants finish.'),
            h('button.btn.btn-quiet', { type: 'button', onclick: () => main('score') }, 'Check again')));
          return;
        }
        pane.replaceChildren(h('p.hint', {}, r.remaining + ' answer' + (r.remaining === 1 ? '' : 's') + ' left for you. Item ' + r.item.item_key), taskFacts(r.item.task),
          answerBlock(r.item),
          scoreForm(st, async (body) => { body.item_key = r.item.item_key; await api('/api/study/rater/score', body); main('score'); }, 'Submit score and next', r.item.task));
      }

      async function disagreements(pane) {
        const d = await api('/api/study/disagreements');
        pane.replaceChildren(h('p', {}, d.rule), h('p', {}, d.n + ' disagreement' + (d.n === 1 ? '' : 's') + ' logged; ' + d.open + ' awaiting R3.'),
          d.n ? h('div.st-tablewrap', {}, h('table.st-table', {}, h('thead', {}, h('tr', {}, ['Item', 'Fields that differ', 'R3 scored'].map((x) => h('th', { scope: 'col' }, x)))),
            h('tbody', {}, d.log.map((x) => h('tr', {}, h('td', {}, x.item), h('td', {}, x.fields.join(', ')), h('td', {}, x.r3_done ? 'yes' : 'no')))))) : h('p.hint', {}, 'No disagreements yet.'));
      }

      async function operator(pane) {
        const c = await AgeLens.api('/api/study/config');
        const msg = h('div', { 'aria-live': 'polite' });
        const download = async (scope, format, level) => {
          try {
            const res = await fetch('/api/study/export?scope=' + scope + '&format=' + format + '&level=' + level, { headers: hdr() });
            if (!res.ok) { const j = await res.json().catch(() => ({})); throw new Error((j.error || 'Export failed') + (j.blockers ? ' ' + j.blockers.join(' ') : '')); }
            const blob = await res.blob(); const a = h('a', { href: URL.createObjectURL(blob), download: (scope === 'simulated' ? 'SIMULATED_' : '') + 'agelens_study_' + level + '.' + format });
            document.body.append(a); a.click(); a.remove(); msg.replaceChildren(h('p.notice', { role: 'status' }, 'Downloaded ' + a.download + '.'));
          } catch (e) { msg.replaceChildren(h('p.notice.error', { role: 'alert' }, e.message)); }
        };
        const modeBtn = h('button.btn.btn-secondary', { type: 'button', onclick: async () => {
          try { await api('/api/study/mode', { mode: 'formal' }); main('operator'); }
          catch (e) {
            const res = await fetch('/api/study/mode', { method: 'POST', headers: Object.assign({ 'Content-Type': 'application/json' }, hdr()), body: JSON.stringify({ mode: 'formal' }) });
            const j = await res.json().catch(() => ({}));
            msg.replaceChildren(h('div.notice.error', { role: 'alert' }, h('strong', {}, j.error || e.message), h('ul', {}, (j.blockers || []).map((b) => h('li', {}, b)))));
          }
        } }, 'Try to switch to formal mode');
        pane.replaceChildren(
          h('section.card', {}, h('h2', {}, 'Study mode'), h('p', {}, 'Current mode: ', h('strong', {}, c.mode), '. Model: ', h('strong', {}, c.model.label), '.'),
            h('p.hint', {}, cfg.ai_design ? 'Formal mode is refused by the server unless data/study/APPROVAL.json holds the teacher approval and preregistration reference, the task file hash matches, AND an AI model is connected for the contextual AI arm. This page cannot create that file. ' + (c.ai_arm && c.ai_arm.note ? c.ai_arm.note : '')
              : 'Formal mode is refused by the server unless data/study/APPROVAL.json holds the teacher approval and preregistration reference, the task file hash matches, and a model is connected. This page cannot create that file.'),
            c.formal_blockers.length ? h('ul', {}, c.formal_blockers.map((b) => h('li', {}, b))) : h('p', {}, 'All formal-mode conditions are currently met.'), modeBtn),
          h('section.card', {}, h('h2', {}, 'Anonymous export'), h('p.hint', {}, 'Participant codes only. Answers and rater notes are not exported. Simulated sessions export only as SIMULATED; the formal export refuses until the gate above is open.'),
            h('div.st-actions', {}, [['simulated', 'json', 'task', 'Simulated · tasks JSON'], ['simulated', 'csv', 'task', 'Simulated · tasks CSV'], ['simulated', 'csv', 'participant', 'Simulated · participants CSV'], ['formal', 'csv', 'task', 'Formal · tasks CSV']].map(([s, f, l, t]) =>
              h('button.btn.btn-quiet', { type: 'button', onclick: () => download(s, f, l) }, t)))),
          h('section.card', {}, h('h2', {}, 'Simulated data'), h('p.hint', {}, 'Deletes simulated participants and scores only. Formal data is never touched.'),
            h('button.btn.btn-quiet', { type: 'button', onclick: async () => { if (!confirm('Delete all simulated study sessions and scores?')) return; try { const r = await api('/api/study/simulated/clear', {}); msg.replaceChildren(h('p.notice', { role: 'status' }, 'Deleted ' + r.deleted_participants + ' simulated participants.')); } catch (e) { msg.replaceChildren(h('p.notice.error', {}, e.message)); } } }, 'Delete simulated sessions')),
          msg);
      }

      if (ss.get(TK) && ss.get(RK)) main('score'); else signIn();
    },
  };
})();
