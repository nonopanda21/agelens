/* Home section "fields" (order 45): three occupation-group cards with dot lists (reference "all fields" card layout). */
(function () {
  const AL = window.AgeLens, h = AL.h;
  const GROUPS = [
    ['Operations, procurement & logistics', 'Roles where ads often pair experience requirements with an age guideline.', ['Procurement and supply chain', 'Operations management', 'Logistics and warehousing'], 'Typical wording: a cap at 35 with an exception for strong experience.'],
    ['Engineering, data & design', 'Technical roles where seniority and age wording can point in different directions.', ['Engineering and manufacturing', 'Data analysis', 'Design'], 'Typical wording: a stated range, or a preference for “young, energetic” teams.'],
    ['Sales, service & office roles', 'Customer-facing and administrative roles with frequent soft age preferences.', ['Sales and marketing', 'Customer service', 'Finance, HR and administration'], 'Typical wording: “preferably under 35”, which is a preference rather than a rule.'],
  ];
  AL.home = AL.home || { sections: [] };
  AL.home.sections.push({ id: 'fields', order: 45, render(el) {
    el.append(h('div.wrap.xs', {},
      h('div.xs-head.reveal', {}, h('h2', {}, 'For mid-career job seekers in every field'),
        h('p', {}, 'Not only lawyers or specialists. If an ad’s age wording affects your next move, you can bring your own role and question.')),
      h('div.xc-grid', {}, GROUPS.map(([t, d, list, fit], i) => h('article.xc.xc-tall.reveal', { style: `--d:${i * 70}ms` },
        h('h3.xc-title', {}, t), h('p', {}, d), h('ul.xc-dots', {}, list.map((x) => h('li', {}, x))), h('p.xc-fit', {}, fit))))));
  } });
})();
