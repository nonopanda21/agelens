"""Data-source interface: the importer reads ads through a DataSource and never knows which kind it is.

    DataSource.metadata()  -> {source, simulated, label, seed, version, data_version, ...}  (stored in the batch log)
    DataSource.fingerprint() -> stable hash of the content (idempotent re-import)
    DataSource.describe()  -> {encoding, delimiter, header, suggested_mapping, mapping}
    DataSource.iter_ads()  -> yields (source_row, raw_dict, fields) where `fields` holds the CANONICAL keys
                              (title, company, city, province, date, description, category, url, source, salary), stripped strings.
    DataSource.stats       -> counters filled while iterating (source_rows_read, blank_rows_skipped)
    DataSource.warnings    -> list of strings (e.g. required field not mapped)

Switching source (see docs/REAL_DATA.md):
    scripts/import_csv.py --source sim            # SimulatedSource(seed) -> is_demo=1
    scripts/import_csv.py FILE.csv [--demo]       # CsvSource(FILE, mapping)
Business logic (dedupe, age parsing, indexing, API) only sees rows already in the database.
"""
import csv, hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ALIASES = {
    "title": "title job_title jobtitle position name 职位名称 职位 岗位名称 岗位 招聘职位 职位名 标题 招聘岗位",
    "company": "company company_name employer 公司 公司名称 企业名称 企业 单位名称 招聘单位 公司名",
    "city": "city work_city location work_location 城市 工作城市 工作地点 工作地址 地点 所在城市 工作地区 地区",
    "province": "province state region 省份 省 所在省份 工作省份",
    "date": "date post_date posted_date publish_date published_at created_at time 发布日期 发布时间 日期 发布于 更新时间 职位发布时间",
    "description": "description job_description desc details requirement requirements responsibilities 职位描述 岗位职责 岗位描述 任职要求 职位详情 工作内容 职位要求 岗位要求 招聘要求 详情",
    "category": "category job_category type industry occupation 职位类别 职位类型 职能 职能类别 类别 职业 行业 岗位类别 职位分类",
    "url": "url link job_url href 链接 职位链接 网址 详情链接",
    "source": "source site platform 来源 数据来源 平台 来源网站 招聘网站",
    "salary": "salary pay wage compensation 薪资 薪酬 工资 月薪 薪水 薪资范围",
}
ALIAS_MAP = {a.lower(): k for k, v in ALIASES.items() for a in v.split()}
FIELDS = list(ALIASES)


def detect_encoding(path):
    with open(path, "rb") as f:
        sample = f.read(1 << 20)
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        for cut in range(4):  # tolerate a multibyte char split at the sample edge
            try:
                sample[:len(sample) - cut].decode(enc); return enc
            except UnicodeDecodeError:
                continue
    return "gb18030"


def detect_delimiter(path, enc):
    with open(path, encoding=enc, errors="replace", newline="") as f:
        head = f.read(65536)
    first = head.split("\n", 1)[0]
    counts = {d: first.count(d) for d in [",", "\t", ";", "|"]}
    best = max(counts, key=counts.get)
    return best if counts[best] else ","


def suggest_mapping(header):
    m, used = {}, set()
    for col in header:
        k = ALIAS_MAP.get(col.strip().lower().lstrip("﻿"))
        if k and k not in used:
            m[col] = k; used.add(k)
    return m


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 22)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


class DataSource:
    """Base class. Subclasses implement describe(), iter_ads(), fingerprint(), metadata()."""
    name = "source"
    filename = "source"

    def __init__(self):
        self.stats = {"source_rows_read": 0, "blank_rows_skipped": 0}
        self.warnings = []

    def metadata(self):
        raise NotImplementedError

    def fingerprint(self):
        raise NotImplementedError

    def describe(self):
        raise NotImplementedError

    def iter_ads(self):
        raise NotImplementedError


class _RowSource(DataSource):
    """Shared row -> canonical-fields mapping for sources that deliver header + rows."""

    def _prepare(self, header, mapping):
        auto = suggest_mapping(header)
        self.mapping = {k: v for k, v in (mapping or auto).items() if k in header}
        self.header, self.auto = header, auto
        rev = {}
        for col, fld in self.mapping.items():
            rev.setdefault(fld, col)
        self.idx = {fld: header.index(col) for fld, col in rev.items()}
        self.warnings = [f"No column mapped to '{x}'." for x in ("title", "description") if x not in rev]

    def _emit(self, rows):
        for row_no, row in rows:
            self.stats["source_rows_read"] = row_no
            if not any((c or "").strip() for c in row):
                self.stats["blank_rows_skipped"] += 1
                continue
            raw = {h: (row[i] if i < len(row) else "") for i, h in enumerate(self.header)}
            if len(row) > len(self.header):
                raw["_extra"] = row[len(self.header):]
            fields = {}
            for fld in FIELDS:
                i = self.idx.get(fld)
                fields[fld] = row[i].strip() if i is not None and i < len(row) and row[i] is not None else ""
            yield row_no, raw, fields


class CsvSource(_RowSource):
    """A CSV file on disk, read as a stream (never loaded whole). Encoding and delimiter are detected."""
    name = "csv"

    def __init__(self, path, mapping=None):
        super().__init__()
        self.path = Path(path)
        self.filename = self.path.name
        self.encoding = detect_encoding(self.path)
        self.delimiter = detect_delimiter(self.path, self.encoding)
        with open(self.path, encoding=self.encoding, errors="replace", newline="") as f:
            csv.field_size_limit(min(sys.maxsize, 2 ** 31 - 1))
            try:
                header = [h.strip().lstrip("﻿") for h in next(csv.reader(f, delimiter=self.delimiter))]
            except StopIteration:
                raise SystemExit("Empty file.")
        self._prepare(header, mapping)
        self._sha = None

    def describe(self):
        return {"encoding": self.encoding, "delimiter": self.delimiter, "header": self.header,
                "suggested_mapping": self.auto, "mapping": self.mapping}

    def fingerprint(self):
        if self._sha is None:
            self._sha = sha256_file(self.path)
        return self._sha

    def metadata(self):
        """Optional sidecar <file>.meta.json (written by the simulator) tells us the file is synthetic."""
        side = self.path.with_suffix(".meta.json")
        meta = {"source": "csv", "simulated": False, "label": None, "file_bytes": self.path.stat().st_size}
        if side.exists():
            try:
                meta.update(json.loads(side.read_text(encoding="utf-8")))
            except ValueError:
                pass
        return meta

    def iter_ads(self):
        csv.field_size_limit(min(sys.maxsize, 2 ** 31 - 1))
        with open(self.path, encoding=self.encoding, errors="replace", newline="") as f:
            rd = csv.reader(f, delimiter=self.delimiter)
            next(rd, None)
            yield from self._emit(enumerate(rd, 1))


class SimulatedSource(_RowSource):
    """Deterministic fictional ads from scripts/make_sim_data.py (in memory; ~1000 rows)."""
    name = "simulated"

    def __init__(self, seed=None, n=None):
        super().__init__()
        sys.path.insert(0, str(ROOT / "scripts"))
        import make_sim_data as gen
        self._gen = gen
        self.rows, self.meta = gen.build(gen.DEFAULT_SEED if seed is None else int(seed), n or gen.DEFAULT_N)
        self.filename = f"sim_ads_{self.meta['data_version']}.csv"
        self._prepare(list(gen.HEADER), None)

    def describe(self):
        return {"encoding": "memory", "delimiter": None, "header": self.header,
                "suggested_mapping": self.auto, "mapping": self.mapping}

    def fingerprint(self):
        # equals the sha256 of the CSV file the generator writes, so sim file and in-memory import are the same batch
        return hashlib.sha256(("\ufeff" + self._gen.csv_text(self.rows)).encode("utf-8")).hexdigest()

    def metadata(self):
        return dict(self.meta)

    def iter_ads(self):
        yield from self._emit(enumerate(self.rows, 1))
