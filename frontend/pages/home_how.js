/* Home section "how" (order 20): centred heading + three numbered glass cards (what AgeLens does), reference card language. */
(function () {
  const AL = window.AgeLens, h = AL.h;
  const CARDS = [
    ['Read what the ad actually says', 'You give your background and one ad. AgeLens shows the ad’s age wording in plain English, sentence by sentence, with its source. Fixed rules do this; no AI model is connected.', 'Nothing is summarised away: the whole age sentence, exception included, stays next to every finding.'],
    ['Separate rules from uncertainty', 'A stated cap, an exception for “outstanding” candidates and a soft preference are different things. AgeLens labels each one.', 'What the ad does not say, such as who decides, is listed as unknown rather than guessed.'],
    ['Turn it into a clear question', 'You get a neutral question you can send to the employer, built from a template. For example, a 38-year-old can ask whether their experience counts for the exception. A human reviewer can check the same evidence.', 'AgeLens never decides whether you qualify. People answer; the tool prepares.'],
  ];
  AL.home = AL.home || { sections: [] };
  AL.home.sections.push({ id: 'how', order: 20, rail: 'What it does', render(el) {
    el.append(h('div.wrap.xs', {},
      h('div.xs-head.reveal', {}, h('h2', {}, 'From an age requirement, to a question you can ask'),
        // key phrases get a marker sweep once the heading is revealed (css/intro.css)
        h('p.xs-lead', {}, 'An age line in a job ad is short. What it means for you is not. AgeLens is for people changing jobs or returning to work. It keeps ', h('span.xw-mark', {}, 'the whole age sentence'),
          ' next to what is explicit and ', h('span.xw-mark', {}, 'what is still unclear'), ', helps you write a question an employer can answer, and leaves every decision to ',
          h('span.xw-mark', {}, 'a person'), '.')),
      h('div.xc-grid', {}, CARDS.map(([t, a, b], i) => h('article.xc.reveal', { style: `--d:${i * 70}ms` },
        h('h3.xc-title', {}, h('span.xc-n', {}, String(i + 1).padStart(2, '0')), t), h('p', {}, a), h('p', {}, b))))));
  } });
})();
