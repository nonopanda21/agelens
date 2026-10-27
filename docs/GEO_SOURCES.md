# Geographic and vendor sources (agent D)

## Province boundaries
- Source URL: https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json (Alibaba Cloud DataV GeoAtlas, "areas_v3").
- Retrieved: 2026-10-22. Saved verbatim as `frontend/geo/china_100000_full.json` (sha256 99adfede...ac275).
- Derived file used by the site: `frontend/geo/china_provinces.json` = the same geometry with (a) the unnamed 35th feature (adcode `100000_JD`, the nine-dash line overlay) dropped, and (b) properties rewritten to `name` (canonical short name, e.g. 北京, 内蒙古, 新疆), `fullName`, `adcode`, `center`. Short names were made by stripping the 省/市/自治区/特别行政区 and ethnic-group suffixes; the geometry itself is unmodified.
- Join check (run 2026-10-22 against `GET /api/provinces`): 34 of 34 units match by name in both directions, no extras either side.
- Licence status: UNCERTAIN. No licence file was found at the URL, and the DataV terms of use were not verified. The data appears to derive from Chinese official administrative boundary data; map-approval (审图号) requirements for public use were not checked. Treat as suitable for local demonstration only until the licence/permission is confirmed; replace with a source of known licence before any public release. Boundaries are simplified and are not an authoritative map; Taiwan, Hong Kong and Macau are separate units to match the 34-unit province list.

## Vendored libraries
Round 2: the ECharts / ECharts-GL bundles and the old `js/map.js` were removed (nothing references them). The map is now Three.js 0.160.0 (`frontend/vendor/three/`, MIT, vendored by the lead) via `js/map3d.js`, with an SVG fallback in `js/map2d.js`; shared projection (Albers conic, 25N/47N) and metric code is in `js/mapcore.js`. Geometry and its licence status (UNCERTAIN, local demonstration only) are unchanged.
