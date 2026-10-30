/* About: Method and sources (agent L). Plain English, short. Literature status mirrors docs/LITERATURE.md. */
AgeLens.pages.about = {
  title: 'Method and sources',
  render(el) {
    const h = AgeLens.h;
    const sec = (title, ...kids) => h('section.ab-sec', {}, h('h2', {}, title), ...kids);
    const lit = [
      ['Feng, Lefgren, Liu, Platt, Xia (2026), NBER Working Paper 35709', 'https://www.nber.org/papers/w35709', 'Full text read. Figure 1 estimates checked against the PDF and redrawn. Working paper, not peer-reviewed.', 'ok', 'Checked in full text'],
      ['Lin Wenlian (2025), China Economic Quarterly 25(1), DOI 10.13821/j.cnki.ceq.2025.01.07', 'https://doi.org/10.13821/j.cnki.ceq.2025.01.07', 'Full text read (supplied by the team, 2026-10-28). The 0.40% to 0.54% jump at age 35 (Tables 1–2, pp. 108–109) and the ad shares (pp. 105–106) checked against the printed pages; the figure on the Why it matters page uses printed values only. Not significant for college graduates (p. 117).', 'ok', 'Checked in full text'],
      ['Neumark, Burn, Button (2019), NBER Working Paper 21669', 'https://www.nber.org/papers/w21669', 'Working paper version, full text read. US resume experiment, 40,223 applications, four occupations: callbacks fall with age, with stronger and more robust evidence of age discrimination against women than against men. US only; callbacks, not hires; no ad text. Journal text not read.', 'ok', 'Checked in full text (working paper version)'],
      ['Burn, Firoozi, Ladd, Neumark (2022), NBER Working Paper 30287', 'https://www.nber.org/papers/w30287', 'Working paper version, full text read. Randomised artificial ads for three occupations: ageist wording lowers the average age of applicants and the share over 40. It measures who applies, not who is hired. A related paper, Burn, Button, Munguia Corella, Neumark (NBER Working Paper 26552), links ad wording to employer callbacks. Journal details for both were not verified.', 'ok', 'Checked in full text (working paper version)'],
      ['Belot, Kircher, Muller (2019), IZA Discussion Paper 10068 (July 2016)', 'https://docs.iza.org/dp10068.pdf', 'Earlier working paper version, full text read; the journal text was not. About 300 unemployed jobseekers in Edinburgh, lab experiment: a tool suggesting related occupations broadened search and raised interviews (about 44%, only marginally significant). No effect shown on offers or employment. Nothing on age, China, ad wording or chatbots.', 'ok', 'Checked in full text (working paper version)'],
    ];
    el.append(h('div.wrap.section.ab', {},
      h('h1', {}, 'Method and ', h('span.ink-pink', {}, 'sources')),
      h('p.ab-lead', {}, 'AgeLens is an evidence-grounded clarification assistant for mid-career jobseekers: people changing jobs or returning to work. Given your background and one job ad, it lists the age conditions and exceptions the ad states, says what is still unclear, and prepares a question a person can answer. This page says what does the work, what the data is, and what it cannot do.'),
      sec('Who does what',
        h('dl.ab-dl', {},
          h('dt', {}, 'Rules and the database'), h('dd', {}, 'Find ads, pull out the exact age wording, count and compare. These steps are fixed and repeatable.'),
          h('dt', {}, 'A language model'), h('dd', {}, 'Only explains and drafts wording. No model is connected right now, so the app shows ', h('span.badge', {}, 'Template demo'), ' and uses fixed templates. Nothing here claims an AI call happened.'),
          h('dt', {}, 'People'), h('dd', {}, 'A human reviewer gives the final reply. AgeLens never answers for an employer.'))),
      sec('Two data sources',
        h('p', {}, h('span.badge.mint', {}, 'Real data · Zhaopin job ads 2021–2024'), ' The statistics on the Overview and Findings pages and the regional map summarise job ads posted on Zhaopin in 2021–2024: 10,058,826 ads were read, and 10,054,663 of them have a recognised province, from an export supplied by the team. Each ad’s title and description were read by the same fixed rules AgeLens uses everywhere; cities were mapped to provinces and job titles to 16 occupation groups by keyword rules (27.9% of titles fit none and are shown as “Other”). Only counts are published: no ad text, company or contact detail leaves the team’s computer.'),
        h('ul', {},
          h('li', {}, 'Why 2021–2024: earlier years have descriptions cut at 240 characters (so age wording is undercounted), 2019–2020 are almost empty, and 2025 is partial and abridged. Details: docs/REAL_DATA_YEARS.md.'),
          h('li', {}, 'How accurate the age rules are (version age-rules-2.1.0, docs/RULES_2_1_0.md): they were corrected for salary digits read as ages, ranges with unusual separators, team-culture wording and Chinese numerals. On a hand-labelled set of 415 real ads, class accuracy went from 75.7% to 94.9%. That set over-samples hard cases on purpose, and one annotator labelled it with no second person, so the figures are approximate. On 150 random ads accuracy was 98.7%.'),
          h('li', {}, 'Known errors that remain: an exception clause that names a second age range can make an ad look contradictory, and the filter for team-culture wording is keyword-based. Wording about graduate cohorts is not counted as an age condition. The published numbers come from the 2.1.0 run.'),
          h('li', {}, 'Gender wording: explicit gender requirements are read by separate fixed rules (gender-rules-1.0.0, docs/GENDER_RULES.md). Only 24 of the 415 hand-labelled ads carried a one-sided requirement, so the accuracy of those rules is rough. Single-sex requirements are rare, about 3,000 of 10 million ads. This describes how ads are worded, not hiring.'),
          h('li', {}, 'What the counts are: how ads are worded on one platform. They are not hiring, rejection or unemployment rates.')),
        h('p', {}, h('span.badge.sim', {}, 'Demo · Synthetic data'), ' The ads you can open (Explore, Job Seeker answers, demo cases, the study tasks) come from a fictional, reproducible set generated for this course project, so every example can be shown in full. None comes from a real employer or a real person. The ads are written in Chinese; this interface shows them in English, with the age wording highlighted. The Chinese text stays in the data, and it is what the rules read.')),
      sec('Literature behind the idea',
        h('p', {}, 'All five papers were checked before use. Status is stated per source; the full record, with access dates and what could not be read, is in docs/LITERATURE.md.'),
        h('ul.ab-lit', {}, lit.map(([name, href, note, cls, status]) => h('li', {},
          h('a', { href, target: '_blank', rel: 'noopener' }, name), ' ', h('span.lit-status.' + cls, {}, status), h('p.hint', {}, note)))),
        h('p.hint', {}, 'The literature motivates our approach but does not establish its effectiveness. It is not an evaluation of AgeLens.')),
      sec('Privacy',
        h('ul', {}, h('li', {}, 'A CV you upload is read in memory to suggest profile fields that you confirm. The file and its text are not stored.'),
          h('li', {}, 'Names, phone numbers and emails are not extracted, and age is never guessed from a CV.'),
          h('li', {}, 'Request codes and owner tokens are kept in your browser so you can come back to your requests.'))),
      sec('Boundaries',
        h('ul', {}, h('li', {}, 'This is not legal advice and gives no legal conclusion about any ad.'),
          h('li', {}, 'It does not make or support hiring decisions. Age wording found in an ad is not a rate of discrimination or rejection.'),
          h('li', {}, 'The first claim is better decision support: a clearer reading of an ad and a ready question. AgeLens cannot remove a binding age restriction. Any benefit for getting a job needs an employer to respond. Effects on hiring and on the wider economy are left for future evaluation.'),
          h('li', {}, 'A classroom-scale study can test whether clarification requests become more usable. It cannot show changes in unemployment or GDP; that would need long-run data.'))),
      h('p.hint', {}, h('a', { href: '#/' }, 'Back to Overview'))));
  },
};
