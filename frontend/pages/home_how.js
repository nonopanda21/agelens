/* Home section "how" (order 20): centred heading + three numbered glass cards (what AgeLens does), reference card language. */
(function () {
  const AL = window.AgeLens, h = AL.h;
  const CARDS = [
    ['Quote what the ad actually says', 'Paste the ad you are looking at. AgeLens finds its age wording and puts the quoted sentence next to a plain-English reading. Fixed rules do this; no AI model is connected yet.', 'Nothing is summarised away: the whole age sentence, exception included, stays next to every finding.'],
    ['Separate what is clear from what is not', 'A stated cap, an exception for “strong candidates” and a soft preference are different things. AgeLens labels each one, and shows how similar ads word age.', 'What the ad does not say, such as who decides on the exception, is listed as unclear rather than guessed.'],
    ['Draft your question for the employer', 'You get one neutral question you can send. For example, a 38-year-old can ask whether 8 years of experience counts for the stated exception. A human reviewer can check it first.', 'AgeLens never decides whether you qualify. People answer; the tool prepares.'],
  ];
  AL.home = AL.home || { sections: [] };
  AL.home.sections.push({ id: 'how', order: 20, rail: 'What it does', render(el) {
    el.append(h('div.wrap.xs', {},
      h('div.xs-head.reveal', {}, h('h2', {}, 'From an age line, to a question you can ask'),
        // key phrases get a marker sweep once the heading is revealed (css/intro.css)
        h('p.xs-lead', {}, 'An age line in a job ad is short. What it means for you is not. AgeLens is for mid-career jobseekers. It keeps ', h('span.xw-mark', {}, 'the whole age sentence'),
          ' next to what is explicit and ', h('span.xw-mark', {}, 'what is still unclear'), ', helps you write a question an employer can answer, and leaves every decision to ',
          h('span.xw-mark', {}, 'a person'), '.')),
      h('div.xc-grid', {}, CARDS.map(([t, a, b], i) => h('article.xc.reveal', { style: `--d:${i * 70}ms` },
        h('h3.xc-title', {}, h('span.xc-n', {}, String(i + 1).padStart(2, '0')), t), h('p', {}, a), h('p', {}, b))))));
  } });
})();
