"""Helpers for the real Zhaopin (智联招聘) recruitment export: city -> province, job title -> occupation, contact masking,
and per-ad age measures computed with the same semantics as evidence.matrix().

- city_to_province(city): canonical short province name (as in evidence.PROVINCES) or None. The city list was built
  from the 714 distinct 工作城市 values in data/raw/zhaopin_2016-2025.7.csv; values that are not a Chinese place
  (foreign countries, 全国, 其他, 国外, 城区, a stray URL, empty) map to None on purpose.
- occupation_of(title): one of the 16 app categories, or '其他'. Ordered keyword rules on the job title only.
  Conservative: a title that does not clearly name a function stays 其他 (项目经理, 总经理, 区域经理, 司机, 保安 ...).
- mask_contacts(text): replaces mobile numbers, landlines and emails with [phone] / [tel] / [email].
- ad_measures(text): per-ad fields that evidence.matrix() aggregates (see AD_FIELDS below).
"""
import importlib.util
import re
from pathlib import Path

from .ageparse import ad_class, age_status, parse_age
from .evidence import PROVINCES

_PROV_NAMES = {p["name"] for p in PROVINCES}

# ---------------------------------------------------------------- city -> province
_CITIES = {
    "北京": "", "天津": "", "上海": "", "重庆": "",
    "河北": "石家庄 唐山 秦皇岛 邯郸 邢台 保定 张家口 承德 沧州 廊坊 衡水 雄安 雄安新区",
    "山西": "太原 大同 阳泉 长治 晋城 朔州 晋中 运城 忻州 临汾 吕梁",
    "内蒙古": "呼和浩特 包头 乌海 赤峰 通辽 鄂尔多斯 呼伦贝尔 巴彦淖尔 乌兰察布 兴安盟 兴安 锡林郭勒盟 锡林郭勒 阿拉善盟 阿拉善",
    "辽宁": "沈阳 大连 鞍山 抚顺 本溪 丹东 锦州 营口 阜新 辽阳 盘锦 铁岭 朝阳 葫芦岛",
    "吉林": "长春 吉林 四平 辽源 通化 白山 松原 白城 延边",
    "黑龙江": "哈尔滨 齐齐哈尔 鸡西 鹤岗 双鸭山 大庆 伊春 佳木斯 七台河 牡丹江 黑河 绥化 大兴安岭",
    "江苏": "南京 无锡 徐州 常州 苏州 南通 连云港 淮安 盐城 扬州 镇江 泰州 宿迁 昆山 张家港 常熟 江阴 太仓 宜兴",
    "浙江": "杭州 宁波 温州 嘉兴 湖州 绍兴 金华 衢州 舟山 台州 丽水 义乌",
    "安徽": "合肥 芜湖 蚌埠 淮南 马鞍山 淮北 铜陵 安庆 黄山 滁州 阜阳 宿州 六安 亳州 池州 宣城 巢湖",
    "福建": "福州 厦门 莆田 三明 泉州 漳州 南平 龙岩 宁德 福鼎 晋江",
    "江西": "南昌 景德镇 萍乡 九江 新余 鹰潭 赣州 吉安 宜春 抚州 上饶",
    "山东": "济南 青岛 淄博 枣庄 东营 烟台 潍坊 济宁 泰安 威海 日照 临沂 德州 聊城 滨州 菏泽 莱芜",
    "河南": "郑州 开封 洛阳 平顶山 安阳 鹤壁 新乡 焦作 濮阳 许昌 漯河 三门峡 南阳 商丘 信阳 周口 驻马店 济源 巩义",
    "湖北": "武汉 黄石 十堰 宜昌 襄阳 襄樊 鄂州 荆门 孝感 荆州 黄冈 咸宁 随州 恩施 仙桃 潜江 天门 神农架 神农架林区",
    "湖南": "长沙 株洲 湘潭 衡阳 邵阳 岳阳 常德 张家界 益阳 郴州 永州 怀化 娄底 湘西 长沙县",
    "广东": "广州 韶关 深圳 珠海 汕头 佛山 江门 湛江 茂名 肇庆 惠州 梅州 汕尾 河源 阳江 清远 东莞 中山 潮州 揭阳 云浮",
    "广西": "南宁 柳州 桂林 梧州 北海 防城港 钦州 贵港 玉林 百色 贺州 河池 来宾 崇左",
    "海南": "海口 三亚 三沙 儋州 五指山 琼海 文昌 万宁 东方 定安 屯昌 澄迈 临高 白沙 昌江 乐东 陵水 保亭 琼中 洋浦 "
            "洋浦经济开发区 洋浦市/洋浦经济开发区",
    "四川": "成都 自贡 攀枝花 泸州 德阳 绵阳 广元 遂宁 内江 乐山 南充 眉山 宜宾 广安 达州 雅安 巴中 资阳 阿坝 甘孜 凉山 西昌",
    "贵州": "贵阳 六盘水 遵义 安顺 毕节 铜仁 黔西南 黔东南 黔南",
    "云南": "昆明 曲靖 玉溪 保山 昭通 丽江 普洱 思茅 临沧 楚雄 红河 文山 西双版纳 大理 德宏 怒江 迪庆 景洪",
    "西藏": "拉萨 日喀则 昌都 林芝 山南 那曲 阿里",
    "陕西": "西安 铜川 宝鸡 咸阳 渭南 延安 汉中 榆林 安康 商洛 西咸新区 杨凌",
    "甘肃": "兰州 嘉峪关 金昌 白银 天水 武威 张掖 平凉 酒泉 庆阳 定西 陇南 临夏 甘南",
    "青海": "西宁 海东 海北 黄南 海南州 果洛 玉树 海西 格尔木",
    "宁夏": "银川 石嘴山 吴忠 固原 中卫",
    "新疆": "乌鲁木齐 克拉玛依 吐鲁番 哈密 昌吉 博尔塔拉 巴音郭楞 阿克苏 克孜勒苏柯尔克孜 克孜勒苏 喀什 和田 伊犁 塔城 阿勒泰 "
            "石河子 阿拉尔 图木舒克 五家渠 北屯 铁门关 双河 可克达拉 昆玉 胡杨河 新星 白杨",
    "香港": "", "澳门": "", "台湾": "",
}
# district-level values seen in the export (only full forms, so 朝阳 stays the Liaoning prefecture)
_DISTRICTS = {"海淀区": "北京", "朝阳区": "北京", "丰台区": "北京", "东城区": "北京", "西城区": "北京",
              "浦东新区": "上海", "奉贤区": "上海", "虹口区": "上海", "松江区": "上海", "闵行区": "上海",
              "南开区": "天津", "滨海新区": "天津", "大渡口区": "重庆", "渝北区": "重庆", "思茅区": "云南", "广安区": "四川"}
CITY_PROVINCE = {}
for _prov, _names in _CITIES.items():
    CITY_PROVINCE[_prov] = _prov
    for _c in _names.split():
        CITY_PROVINCE[_c] = _prov
for _p in PROVINCES:  # 广东省 / 内蒙古自治区 / Guangdong
    CITY_PROVINCE.setdefault(_p["full"], _p["name"])
CITY_PROVINCE.update(_DISTRICTS)


def _geo_table():
    """Fallback: the project's district table (scripts/geo_table.py), e.g. 浦东 / 海淀 / 南山. Our own entries win, so the
    Zhaopin prefecture 朝阳 stays 辽宁 (the export's 工作城市 is prefecture level)."""
    try:
        spec = importlib.util.spec_from_file_location("_agelens_geo_table", Path(__file__).resolve().parent.parent / "scripts" / "geo_table.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return dict(mod.CITY_TO_PROVINCE)
    except (OSError, AttributeError, ImportError):
        return {}


for _c, _p in _geo_table().items():
    CITY_PROVINCE.setdefault(_c, _p)
_SUFFIXES = ("自治州", "地区", "林区", "新区", "市", "盟", "州", "县", "区")


def city_to_province(city):
    """Canonical short province name for a 工作城市 value, or None (foreign, nationwide, unknown, empty)."""
    if city is None:
        return None
    c = str(city).strip().replace("　", "")
    if not c:
        return None
    if c in CITY_PROVINCE:
        return CITY_PROVINCE[c]
    for suf in _SUFFIXES:
        if c.endswith(suf) and len(c) > len(suf) + 1 and c[:-len(suf)] in CITY_PROVINCE:
            return CITY_PROVINCE[c[:-len(suf)]]
    # full autonomous-prefecture names, e.g. 延边朝鲜族自治州 / 阿克苏地区 / 黔东南苗族侗族自治州
    if c.endswith(("自治州", "地区", "盟", "自治县")):
        for n in range(min(len(c), 9), 1, -1):
            if c[:n] in CITY_PROVINCE and c[:n] not in _PROV_NAMES:
                return CITY_PROVINCE[c[:n]]
    return None


# ---------------------------------------------------------------- job title -> occupation
OCCUPATIONS = ("销售", "工程技术", "采购", "客户服务", "物流仓储", "财务", "运营管理", "市场营销", "生产制造", "行政",
               "人力资源", "设计", "数据分析", "教育培训", "医疗护理", "法务合规")
OTHER = "其他"
# engineering disciplines: '设计' together with one of these is engineering design, not graphic/interior design
_ENG_DESIGN = re.compile(r"机械|电气|结构|暖通|给排水|水电|电路|硬件|模具|工艺|电子|自动化|土建|机电|PCB|芯片|版图|IC|化工|电力|"
                         r"弱电|强电|管道|光学|仪表|工程师|线路|管网|桥梁|道路|市政|岩土|传输|电讯|通信|通讯|智能化")
_RULES = [  # (category, include regex, exclude regex or None); first match wins
    # a title naming 销售 is sales unless it names a back-office function too (销售会计, 销售行政专员, 销售培训师)
    ("销售", r"销售", r"会计|出纳|核算|财务|审计|培训|讲师|数据分析|人事|行政|采购|客服|仓|物流|设计|法务"),
    ("法务合规", r"法务|律师|法律|合规|知识产权|专利|合同管理|证券事务", None),
    ("人力资源", r"人力资源|人力行政|人力专员|人力经理|人力主管|人资|人事|招聘(?:专员|主管|经理|助理|负责人|总监|官|顾问|$)|(?<![A-Za-z])HR|薪酬|绩效|猎头|员工关系|"
                 r"培训(?:专员|主管|经理|总监|助理|负责人)|组织发展", None),
    ("财务", r"会计|出纳|财务|审计|税务|总账|核算|资金(?:专员|主管|经理)|费用(?:专员|会计)|结算(?:专员|会计|主管)", None),
    ("采购", r"采购|采买|买手|供应商管理|供应商开发", None),
    ("销售", r"销售|电销|业务员|业务代表|业务(?:经理|主管|专员|助理|总监)|客户经理|大客户|置业顾问|房产经纪|经纪人|招商|渠道|"
             r"(?<![A-Za-z])BD(?![A-Za-z])|商务拓展|市场拓展|地推|导购|营业员|店员|电话营销|医药代表|医疗器械代表|理财顾问|理财经理|"
             r"保险顾问|保险代理|外贸(?:业务|经理|专员|主管|销售)", None),
    ("教育培训", r"教师|老师|讲师|教员|助教|班主任|教务|校长|课程顾问|课程规划|招生|培训师|家教|辅导员|幼教|保育员|早教|教研|学管|"
                 r"学习管理师|教学", None),
    ("医疗护理", r"护士|护理|医生|医师|药师|药剂|药房|康复|理疗|口腔|牙科|临床|医助|医学|检验科|麻醉|护工(?!程)|月嫂|育婴|医务|放射|"
                 r"超声|B超|中医|推拿|针灸|健康管理师|营养师|心理咨询师|验光", r"销售|代表|招商|工程师|医学信息|推广|沟通|保护"),
    ("客户服务", r"客服|客户服务|售后服务(?!工程)|售后专员|客户成功|呼叫中心|话务|热线|接线员|客户关系", None),
    ("物流仓储", r"仓库|仓管|库管|仓储|库房|物流|理货|分拣|快递|配送|叉车|装卸|搬运|供应链|报关|单证|货运|运输|"
                 r"(?:物流|车辆|运输)调度|收发货|发货员|海运|空运|货代|货车|送货", None),
    ("数据分析", r"数据分析|数据挖掘|数据科学|数据运营|数据专员|商业分析|(?<![A-Za-z])BI(?![A-Za-z])|报表|统计分析|数据统计|数据治理", None),
    ("设计", r"设计|美工|(?<![A-Za-z])UI|(?<![A-Za-z])UE(?![A-Za-z])|视觉|平面|插画|原画|CAD|制图|3D|三维|建模|动画|排版|剪辑|"
             r"后期制作|绘图|视频编辑|视频剪辑", _ENG_DESIGN.pattern),
    ("市场营销", r"市场|营销|品牌|媒介|策划|文案|新媒体|推广|公关|广告|企划|(?<![A-Za-z])SE[OM](?![A-Za-z])|内容运营|短视频运营|"
                 r"抖音运营|直播运营|小红书", r"游戏策划"),
    ("运营管理", r"运营|营运|店长|门店经理|门店主管|电商|电子商务", r"主播"),
    ("行政", r"行政|前台|文员|秘书|文秘|办公室|内勤|档案|后勤|总经理助理|董事长助理|总裁助理", None),
    ("生产制造", r"普工|操作工|作业员|生产|车间|质检|品质|品管|质量|(?<![A-Za-z])(?:QC|QE|SQE|IQC|IPQC|OQC|PMC)(?![A-Za-z])|检验员|"
                 r"化验|工艺|钳工|焊工|电焊|氩弧焊|车工(?!程)|铣工|磨工|数控|CNC|机修|维修电工|电工(?!程)|装配|包装工|厂长|"
                 r"注塑|冲压|喷涂|喷漆|模具工|设备维修|IE工程师|物料员|品控|品检|(?<![A-Za-z])IE(?![A-Za-z])", None),
    ("工程技术", r"工程师|程序员|测试|运维|架构师|技术员|技术支持|技术(?:总监|经理|主管|负责人)|总工|算法|前端|后端|全栈|"
                 r"(?<![A-Za-z])(?:java|python|php|golang|android|ios|web|c\+\+|\.net|dba|it)(?![A-Za-z])|"
                 r"(?:软件|程序|系统|游戏|app|大数据|嵌入式|硬件)开发|嵌入式|硬件|软件|网络管理|网管|研发|施工|土建|监理|测量员|"
                 r"机电|电气|自动化|(?:机械|结构|暖通|给排水|电气|水电|电路|硬件|模具|电子)(?:设计|制图)", r"养殖|养猪|种植|美容|美发|美甲"),
]
_COMPILED = [(cat, re.compile(inc, re.I), re.compile(exc, re.I) if exc else None) for cat, inc, exc in _RULES]


def occupation_of(title):
    """One of OCCUPATIONS for a job title, or '其他' when no rule clearly applies."""
    t = str(title or "").strip()
    if not t:
        return OTHER
    for cat, inc, exc in _COMPILED:
        if inc.search(t) and not (exc and exc.search(t)):
            return cat
    return OTHER


# ---------------------------------------------------------------- contact masking
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")
_MOBILE = re.compile(r"(?<![\d])(?:(?:\+|00)?86[\s\-]?)?1[3-9]\d(?:[\s\-]?\d{4}){2}(?!\d)")
_TEL = re.compile(r"(?<![\d])(?:\(?0\d{2,3}\)?[\s\-－—]?\d{7,8}|\（0\d{2,3}\）\d{7,8}|400[\s\-]?\d{3}[\s\-]?\d{4})"
                  r"(?:\s*(?:-|转|ext\.?)\s*\d{1,6})?(?!\d)")
_TEL_KW = re.compile(r"((?:电话|座机|固话|tel|Tel|TEL|联系方式)\s*[:：]?\s*)\d{7,8}(?!\d)")


def mask_contacts(text):
    """Replace emails with [email], mobile numbers with [phone], landlines / 400 numbers with [tel]."""
    if not text:
        return text
    s = _EMAIL.sub("[email]", str(text))
    s = _MOBILE.sub("[phone]", s)
    s = _TEL.sub("[tel]", s)
    s = _TEL_KW.sub(lambda m: m.group(1) + "[tel]", s)
    return s


# ---------------------------------------------------------------- per-ad measures (evidence.matrix semantics)
AD_FIELDS = ("explicit", "cap", "age_wording", "with_exception", "preference")


def measures_from_terms(terms):
    """Per-ad values exactly as evidence.matrix() derives them from the stored ad row and its age_terms:
    explicit = age_status == 'explicit'; cap = ad_class in (hard_cap, cap_with_exception);
    age_wording = age_status != 'none'; with_exception = any term with exception_text or kind 'relaxable';
    preference = ad_class == 'preference';
    max_age = MIN(max_age) over terms with max_age, confidence 'high' and kind != 'preference' (evidence.MAXAGE_SQL), else None.
    Returns (dict of 0/1 for AD_FIELDS, max_age, ad_class)."""
    st, cls = age_status(terms), ad_class(terms)
    ages = [t["max_age"] for t in terms if t.get("max_age") is not None and t.get("confidence") == "high"
            and t.get("kind") != "preference"]
    m = {"explicit": int(st == "explicit"), "cap": int(cls in ("hard_cap", "cap_with_exception")),
         "age_wording": int(st != "none"),
         "with_exception": int(any(t.get("exception_text") is not None or t.get("kind") == "relaxable" for t in terms)),
         "preference": int(cls == "preference")}
    return m, (min(ages) if ages else None), cls


def ad_text(title, description):
    """Text the aggregate parses: job title + newline + description."""
    return (title or "") + "\n" + (description or "")


def ad_measures(title, description):
    return measures_from_terms(parse_age(ad_text(title, description)))
