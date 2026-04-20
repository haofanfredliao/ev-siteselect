## Plan: EV Siting MVP — Feature Integration & Visualization

整合 ModelBuilder 改进（加权 POI KDE、DistanceAccumulation 路网、18 区 study area 过滤）到现有 arcpy_engine + React 前端，并新增完整的图层可视化系统。

---

### Phase 1: Study Area — 18 区选择 (backend)

1. **新增 `GET /api/districts`** — 读取 `AdminArea_DCD_20230609.gdb_converted.shp`，返回 18 区名称列表
2. **新增 `GET /api/districts/geojson?names=...`** — 返回选中区的多边形 GeoJSON (WGS84)，用于前端渲染边界
3. **修改 `run_suitability_model()`** — 新增 `study_area: list[str]` 参数，分析时用 `ExtractByMask` 裁剪到选定区域
4. 预处理**不受影响** — 始终覆盖全港，裁剪只在分析阶段

**文件**: arcpy_engine.py (新增 `list_districts()`, `get_districts_geojson()`, 改 `run_suitability_model`), main.py (新增 2 endpoint, 改 `SitingRequest`)

### Phase 2: POI 分类加权 KDE (backend)

5. **定义 TYPE→权重映射** — 基于 iGeoCom TYPE 字段和 EV 充电停留时间逻辑：
   - 权重 5: MAL/ROI/SMK/HTL/CPO（商场/酒店/停车场）
   - 权重 4: CHL/PFM/EXB/TNC/IGH/STD/SPL（娱乐/体育）
   - 权重 3: HOS/CLI/TEI/RSN/MTA/FET/CMC（医院/交通枢纽）
   - 权重 2: PRS/SES/KDG/POF/LIB/GOF（学校/办公）
   - 权重 1: CVS/TOI/POB/BUS/MIN（便利店/公厕）
   - 排除 0: PAK/BGD/TRF(部分)/UTI(部分)
6. **改造 `preprocess_poi()`** — `AddField("WEIGHT")` + `CalculateField` 基于 TYPE 查表 → `KernelDensity(poi_lyr, "WEIGHT", cell, 800)`

**文件**: arcpy_engine.py — `preprocess_poi()`, 新增 `POI_TYPE_WEIGHTS` 字典

### Phase 3: 道路 DistanceAccumulation + 坡度摩擦 (backend)

7. **改造 `preprocess_road()`** — 用 `slope.tif` 构建摩擦面 `cost = 1 + slope * 0.05`，替换 `EucDistance` → `DistanceAccumulation(centerline, in_cost_raster=cost)`

**文件**: arcpy_engine.py — `preprocess_road()`

### Phase 4: 图层服务 API (backend)

8. **栅格图层端点** `GET /api/layer/raster/{name}` — 将 preprocessed tif 降采样→着色→导出 PNG + 返回 bounds，前端用 `ImageOverlay` 渲染
9. **矢量图层端点** `GET /api/layer/vector/{name}` — 将原始 shp/csv 转 GeoJSON (WGS84)，限制最大要素数 ~5000
10. **图层注册表** — raw 层 6 个 + intermediate 层 6 个 + final_score 1 个

**文件**: arcpy_engine.py (新函数), main.py (新 endpoint)

### Phase 5: 区域选择器 (frontend)

11. **新组件 `DistrictSelector.jsx`** — 18 个 checkbox，默认全选，全选/取消全选按钮
12. **传 `study_area` 到 siting 请求**
13. **地图上渲染区界** — `GeoJSON` 图层，只有边框无填充，和数据图层不冲突

**文件**: 新建 `DistrictSelector.jsx`; 改 `AnalysisTab.jsx`, `MapView.jsx`, `App.jsx`, `api.js`

### Phase 6: 图层可视化系统 (frontend)

14. **`activeLayer` 状态** — `App.jsx` 管理，全局只能显示一个数据图层（单选互斥）
15. **`FactorModule.jsx` 增加两个按钮** — "Raw" 和 "Score"，点击切换显示该因素的源数据 / 中间态栅格
16. **分析结果栅格** — 在 `RunAnalysisSection` 下方加 checkbox "Show suitability heatmap"
17. **`MapView.jsx` 渲染** — 栅格用 `ImageOverlay`，矢量用 `GeoJSON` 图层；图层叠放顺序：basemap → 数据图层 → 区界 → 结果标记点

**文件**: 改 `App.jsx`, `FactorModule.jsx`, `MapView.jsx`, `RunAnalysisSection.jsx`; 新增 `api.js` 函数

### Phase 7: 底图切换 (frontend)

18. **3 个底图**: OpenStreetMap (默认), Esri Topographic, Esri Light Gray Canvas
19. **`MapView.jsx`** 中添加浮动切换控件或在 sidebar 底部添加底图选择

**文件**: `MapView.jsx`, `App.jsx`

---

### Verification
1. `GET /api/districts` → 返回 18 个区名
2. `GET /api/districts/geojson` → 有效 WGS84 GeoJSON
3. POI 预处理 → 输出 `poi_heat.tif` 分布与之前不同（加权 vs 等权）
4. Road 预处理 → 输出反映地形摩擦（非纯欧氏距离）
5. `POST /api/siting` with `study_area: ["Central and Western"]` → 结果点全部落在该区内
6. 图层切换 → 原始 POI 点/中间态栅格/最终栅格均可正确渲染
7. 区界 + 数据图层 + 结果标记点可同时共存
8. 底图切换无缝

### Decisions
- POI 按 **TYPE** (3 字母码) 加权，不用 CLASS（太粗）或 SUBCAT（缺失太多）
- 道路摩擦面: `1 + slope * 0.05`（平地 cost≈1, 20% 坡度 → cost 2）
- 栅格渲染用 **ImageOverlay**（降采样 PNG + bounds），不搭 tile server
- Study area 只影响分析阶段，不影响预处理
- Esri 公共底图服务（免费，无需 API key）
- 不改动: slope/landuse/population 预处理逻辑、AI chat tab

### Open Question
- 栅格 overlay 的全港 5m 数据太大（~3000×2200px），建议降采样到 ~50m 生成 PNG。如果效果不够可以后续升级为 tile 方案。需要先试验确认。