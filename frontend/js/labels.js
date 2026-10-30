/* English display labels for data values (lead-owned). The UI is English-only: no Chinese character is ever rendered,
   not even as quoted evidence (docs/ENGLISH_UI.md). The Chinese values stay in the data and are still what filters send
   to the API; only the visible text is English.
   AgeLens.labels.occ(name) · .prov(name) · .ageClass(key) · .ageStatus(key) · .source(name) · .ready (Promise; province names load from /api/provinces)
   English display fields from the API, with fallbacks that never show Chinese:
   .en(v) -> v when it is a non-empty string without Chinese, else null
   .termGloss(term) -> term.gloss_en, else a rules-based English sentence built from kind / min_age / max_age
   .exception(term) -> term.exception_en, else a neutral note when exception wording exists, else null
   .adTitle(ad) · .company(ad) · .city(ad) · .place(ad) · .ageLine(ad) · .quote(statement)
   .orig() -> null (kept so older callers do not break; originals are no longer shown). */
(function () {
  const AL = window.AgeLens;
  const OCC = {
    '销售': 'Sales', '工程技术': 'Engineering', '采购': 'Procurement', '客户服务': 'Customer service', '物流仓储': 'Logistics & warehousing',
    '财务': 'Finance', '运营管理': 'Operations', '市场营销': 'Marketing', '生产制造': 'Manufacturing', '行政': 'Administration',
    '人力资源': 'Human resources', '设计': 'Design', '数据分析': 'Data analysis', '教育培训': 'Education & training',
    '医疗护理': 'Healthcare & nursing', '法务合规': 'Legal & compliance',
    '其他': 'Other',
    // round-1 demo categories (kept so older data still reads in English)
    '运营': 'Operations', '技术': 'Engineering', '行政人事': 'Admin & HR', '市场': 'Marketing', '客服': 'Customer service',
  };
  const AGE_CLASS = { hard_cap: 'Hard cap', cap_with_exception: 'Cap with an exception', preference: 'Preference, not a rule', range_or_min: 'Range or minimum', ambiguous: 'Unclear wording', none: 'No age wording' };
  const AGE_STATUS = { explicit: 'Explicit age condition', uncertain: 'Age wording needs interpretation', none: 'No explicit age condition detected' };
  const SOURCE = { '合成示例数据': 'Synthetic sample data', '示例数据': 'Sample data' };
  const PROV = {};
  const has = (s) => (AL.hasCJK ? AL.hasCJK(s) : /[㐀-鿿]/.test(s || ''));
  const en = (v) => (typeof v === 'string' && v.trim() && !has(v) ? v.trim() : null);
  const NOT_SHOWN = 'Original wording not shown';

  /** Rules-based English reading of one age term; used when the API has no gloss_en yet. */
  function mechanical(t) {
    if (!t) return null;
    let s;
    if (t.kind === 'max' && t.max_age != null) s = 'Maximum age ' + t.max_age;
    else if (t.kind === 'min' && t.min_age != null) s = 'Minimum age ' + t.min_age;
    else if (t.kind === 'range' && t.min_age != null && t.max_age != null) s = 'Age ' + t.min_age + ' to ' + t.max_age;
    else if (t.kind === 'relaxable') s = 'The age requirement may be relaxed';
    else s = 'Age-related wording that needs interpretation';
    if (t.exception_text && t.kind !== 'relaxable') s += '; may be relaxed for some candidates (the ad does not say how)';
    return s;
  }

  const L = (AL.labels = {
    NOT_SHOWN,
    en,
    occ(v) { return v == null || v === '' ? 'Not stated' : (OCC[v] || (has(v) ? 'Other occupation' : v)); },
    prov(v) { return v == null || v === '' ? 'Unknown region' : (PROV[v] || (has(v) ? 'Unlisted region' : v)); },
    ageClass(k) { return AGE_CLASS[k] || k || '—'; },
    ageStatus(k) { return AGE_STATUS[k] || k || '—'; },
    source(v) { return v == null || v === '' ? '' : (SOURCE[v] || (has(v) ? 'Imported source' : v)); },
    termGloss(t) { return t ? en(t.gloss_en) || mechanical(t) : null; },
    exception(t) { return !t ? null : en(t.exception_en) || (t.exception_text ? 'Exceptions are possible; the ad does not say who decides or how' : null); },
    adTitle(ad) {
      if (!ad) return 'Job ad';
      return en(ad.title_en) || en(ad.title) || (ad.occupation && OCC[ad.occupation] ? OCC[ad.occupation] + ' job ad' : 'Job ad' + (ad.id ? ' ' + ad.id : ''));
    },
    company(ad) { return ad ? en(ad.company_en) || en(ad.company) : null; },
    city(ad) { return ad ? en(ad.city_en) || en(ad.city) : null; },
    /** "Sichuan" or "Panzhihua, Sichuan" (English only; a city without an English name is left out). */
    place(ad) {
      if (!ad || (!ad.province && !ad.city)) return null;
      const p = en(ad.province_en) || (ad.province ? L.prov(ad.province) : null), c = L.city(ad);
      return [c, p].filter(Boolean).join(', ') || 'Region not stated';
    },
    /** One English line for an ad's age wording: age_sentence_en, else the first term's gloss. */
    ageLine(ad) { return ad ? L.sentences(ad)[0] || L.termGloss((ad.age_terms || [])[0]) : null; },
    /** All English age sentences of an ad (age_sentences_en, else age_sentence_en split on newlines). */
    sentences(ad) {
      const list = ad && Array.isArray(ad.age_sentences_en) ? ad.age_sentences_en : ad && ad.age_sentence_en ? String(ad.age_sentence_en).split('\n') : [];
      return list.map(en).filter(Boolean);
    },
    /** Nodes for English text with every sentence highlighted as <mark class="age">; .found = how many were located. */
    highlight(text, sentences, title) {
      const spans = [];
      for (const s of sentences || []) { const i = text.indexOf(s); if (i >= 0) spans.push([i, i + s.length]); }
      spans.sort((a, b) => a[0] - b[0]);
      const nodes = []; let pos = 0, found = 0;
      for (const [s, e] of spans) { if (s < pos) continue; if (s > pos) nodes.push(text.slice(pos, s)); nodes.push(AL.h('mark.age', { title }, text.slice(s, e))); pos = e; found++; }
      if (pos < text.length) nodes.push(text.slice(pos));
      return { nodes, found };
    },
    /** English version of a brief statement's quote; null when there is no quote at all. */
    quote(st) { return !st || !st.quote ? null : en(st.quote_en) || NOT_SHOWN; },
    orig() { return null; },
    ready: null,
  });
  L.ready = fetch('/api/provinces').then((r) => r.json()).then((list) => { list.forEach((p) => { PROV[p.name] = p.en; if (p.full) PROV[p.full] = p.en; }); }).catch(() => {});
})();
