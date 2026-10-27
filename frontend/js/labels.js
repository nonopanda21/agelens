/* English display labels for data values (lead-owned). Original Chinese ad text stays untouched as evidence;
   only category labels shown in the English UI are translated here.
   AgeLens.labels.occ(name) · .prov(name) · .ageClass(key) · .ageStatus(key) · .source(name) · .ready (Promise; province names load from /api/provinces).
   .orig(text) -> muted <span class="zh-orig" lang="zh-CN"> holding an original value (only for evidence metadata lines; never in charts, menus, maps or tables).
   Filters keep sending the ORIGINAL value to the API; only the visible text is English. */
(function () {
  const OCC = {
    '销售': 'Sales', '工程技术': 'Engineering', '采购': 'Procurement', '客户服务': 'Customer service', '物流仓储': 'Logistics & warehousing',
    '财务': 'Finance', '运营管理': 'Operations', '市场营销': 'Marketing', '生产制造': 'Manufacturing', '行政': 'Administration',
    '人力资源': 'Human resources', '设计': 'Design', '数据分析': 'Data analysis', '教育培训': 'Education & training',
    '医疗护理': 'Healthcare & nursing', '法务合规': 'Legal & compliance',
    // round-1 demo categories (kept so older data still reads in English)
    '运营': 'Operations', '技术': 'Engineering', '行政人事': 'Admin & HR', '市场': 'Marketing', '客服': 'Customer service',
  };
  const AGE_CLASS = { hard_cap: 'Hard cap', cap_with_exception: 'Cap with an exception', preference: 'Preference, not a rule', range_or_min: 'Range or minimum', ambiguous: 'Unclear wording', none: 'No age wording' };
  const AGE_STATUS = { explicit: 'Explicit age condition', uncertain: 'Age wording needs interpretation', none: 'No explicit age condition detected' };
  const SOURCE = { '合成示例数据': 'Synthetic sample data', '示例数据': 'Sample data' };
  const PROV = {};
  const L = (window.AgeLens.labels = {
    occ(v) { return v == null || v === '' ? 'Not stated' : (OCC[v] || v); },
    prov(v) { return v == null || v === '' ? 'Unknown region' : (PROV[v] || v); },
    ageClass(k) { return AGE_CLASS[k] || k || '—'; },
    ageStatus(k) { return AGE_STATUS[k] || k || '—'; },
    source(v) { return v == null || v === '' ? '' : (SOURCE[v] || v); },
    /** Muted original value next to its English label (e.g. company name, "四川 攀枝花"). City names are not translated. */
    orig(text) {
      if (text == null || text === '') return null;
      const sp = document.createElement('span'); sp.className = 'zh-orig hint'; sp.lang = 'zh-CN'; sp.textContent = text; return sp;
    },
    ready: null,
  });
  L.ready = fetch('/api/provinces').then((r) => r.json()).then((list) => { list.forEach((p) => { PROV[p.name] = p.en; if (p.full) PROV[p.full] = p.en; }); }).catch(() => {});
})();
