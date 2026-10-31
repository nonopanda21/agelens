/* Home section "example" (order 15, right under the hero): what you get, shown on one fictional case. Static text, labelled
   "Example (fictional case)"; the person, the ad line and the question are written for this page, not taken from a real ad or person.
   The two chips lead to the Job Seeker page, where the real answer offers the brief download and human review. */
(function () {
  const AL = window.AgeLens, h = AL.h;
  const POINTS = ['What the ad says, quoted', 'What is clear and what is not', 'One question to ask the employer'];
  AL.home = AL.home || { sections: [] };
  AL.home.sections.push({ id: 'example', order: 15, rail: 'Example', render(el) {
    const finding = (tag, cls, title, text) => h('div.xex-f', {}, h('p.xex-fh', {}, h('span.xex-tag.' + cls, {}, tag), title), h('p', {}, text));
    el.append(h('div.wrap.xs.xex-wrap', {},
      h('div.xs-head.reveal', {}, h('h2', {}, 'What you get'),
        h('p', {}, 'Your answer is built from the ad you paste. Here is one, for a fictional case.')),
      h('ul.xex-points.reveal', {}, POINTS.map((t, i) => h('li', {}, h('span.xc-n', {}, String(i + 1).padStart(2, '0')), t))),
      h('article.xex.reveal', { 'aria-label': 'Example answer for a fictional case' },
        h('div.xex-top', {}, h('span.badge.sim', {}, 'Example (fictional case)'),
          h('p.xex-who', {}, 'Age 38 · 8 years in operations management · looking at an operations manager ad')),
        h('div.xex-quote', {}, h('span.xex-tag.ad', {}, 'Ad wording'),
          h('blockquote', {}, '“Applicants should normally be under 35. The limit can be relaxed for strong candidates.”'),
          h('p.xex-src', {}, 'Translated from the Chinese ad.')),
        h('div.xex-fs', {},
          finding('Clear', 'ok', 'What the ad states', 'An upper age of 35, and that exceptions are possible.'),
          finding('Unclear', 'open', 'What it leaves open', 'What counts as a “strong candidate”, who decides, and whether experience is weighed.')),
        h('div.xex-q', {}, h('p.xex-qh', {}, 'Your question for the employer'),
          h('p.xex-qt', {}, '“The ad says applicants are normally under 35, with exceptions for strong candidates. Would 8 years of operations management count as grounds for that exception for this role?”')),
        h('div.xex-next', {},
          h('a.xex-chip', { href: '#/seeker' }, 'Download the brief'),
          h('a.xex-chip', { href: '#/seeker' }, 'Send for human review'),
          h('span.xex-note', {}, 'Both are offered with your own answer. A pasted ad is never stored, so a reviewer looks at similar example ads.')))));
  } });
})();
