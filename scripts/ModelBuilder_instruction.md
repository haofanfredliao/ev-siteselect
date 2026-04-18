# ModelBuilder 手把手建模指南
**EV 充电站选址 SDSS | 成员 B 负责**

---

## 📖 使用说明

1. **左屏开 ArcGIS Pro，右屏开这份文档**，对着做
2. 每个"步骤"都标明了：**工具名 / 输入 / 参数 / 输出**
3. 💡 = 小贴士；⚠️ = 容易踩坑
4. 完成一个 Phase 就 `Ctrl+S` 保存一次模型
5. **你不一定要让模型跑通**，任务只要求"工具和参数正确连接，展示完整工作流"。所以遇到报错不必纠结太久，结构对就行

---

## Phase 0: 准备工作

### 0.1 新建模型

1. 打开 ArcGIS Pro，进入你复制的副本 `.aprx`
2. Catalog 面板 → Toolboxes → 找到 `7305_TeamProject.atbx`
3. 右键 → **New → Model**
4. 重命名为：`EV_Site_Selection_Model`
5. 双击打开模型画布

### 0.2 设置模型环境 (⭐ 这一步省掉后面 80% 的麻烦)

模型画布顶部菜单 → **ModelBuilder 选项卡 → Environments** (或 Model → Properties → Environments)

设置：

| 环境项 | 值 |
|---|---|
| **Workspace → Current Workspace** | `7305_TeamProject.gdb` (作为输出) |
| **Output Coordinate System** | `Hong Kong 1980 Grid` (EPSG:2326) |
| **Processing Extent** | `hki_4districts_shp` 文件夹里的 shp |
| **Raster Analysis → Cell Size** | `5` |
| **Raster Analysis → Mask** | `hki_4districts_shp` 里的 shp |

💡 设好之后，后面所有工具都会自动套用这些环境，你不用每个工具都单独配。

---

## Phase 1: 数据准备 (Data Preparation)

目标：把所有原始数据裁剪 / 对齐到港岛四区范围。

### 1.1 研究区边界作为输入

直接把 `hki_4districts_shp` 文件夹里的 `.shp` 拖进模型画布 → 椭圆变成蓝色，说明是**输入数据**。

### 1.2 裁剪矢量数据 (4 个 Pairwise Clip)

工具：**Analysis → Pairwise Clip** (比老版 Clip 快)

| # | Input Features | Clip Features | Output |
|---|---|---|---|
| 1.2.1 | `population_hk_hk80_shp` 里的 .shp | hki_4districts (研究区) | `Population_HKI` |
| 1.2.2 | `5_ev_chargingstation` 里的 .shp | hki_4districts | `Chargers_HKI` |
| 1.2.3 | `6_poi` 里的 .shp | hki_4districts | `POI_HKI` |
| 1.2.4 | `rdnet_irnp.gdb\CENTERLINE` | hki_4districts | `Roads_HKI_Clipped` |

💡 **偷懒方案**：路网那条 (1.2.4) 可以跳过，直接用 `phase2_analysis.gdb\Major_Roads_HKI` 作为输入 —— 这是队友已经筛好的主干道，你不用再研究怎么按道路等级筛选。

### 1.3 提取栅格数据 (2 个 Extract by Mask)

工具：**Spatial Analyst → Extraction → Extract by Mask**

| # | Input Raster | Mask | Output |
|---|---|---|---|
| 1.3.1 | `raster_data\Landuse_Raster_5m.tif` | hki_4districts | `Landuse_HKI` |
| 1.3.2 | `raster_data1\Digital Terrain Model.tif` | hki_4districts | `DTM_HKI` |

⚠️ DTM 文件名里有空格，拖进模型时如果报错，把 .tif **复制一份**重命名为 `DTM_5m.tif` 再用。

---

## Phase 2: 准则层生成 (Criterion Layer Generation)

6 个并列分支，每个生成一个连续值栅格。

### C1: 道路距离

**工具：Spatial Analyst → Distance → Euclidean Distance**

- Input: `Major_Roads_HKI` (或你 1.2.4 的输出)
- Output: `C1_Road_Dist`
- 其他参数留默认

### C2: 人口密度 (Polygon to Raster)

**工具：Conversion → To Raster → Polygon to Raster**

- Input Features: `Population_HKI`
- Value Field: 选表示**人口密度**的字段 (可能叫 `POP_DENSITY`、`DENSITY`、`PopDen` 之类，打开属性表确认)
- Cellsize: `5`
- Output: `C2_Pop_Density`

💡 如果找不到"密度"字段，只有"人口数"，就先用 **Calculate Field** 算一下 `pop / area_km2`，或者直接用人口数栅格化也能反映相对高低。

### C3: 充电站距离

**工具：Euclidean Distance**

- Input: `Chargers_HKI`
- Output: `C3_Charger_Dist`

### C4: 土地利用 (直接进 Phase 3，本阶段跳过)

土地利用已经是栅格 (`Landuse_HKI`)，不需要生成"距离"或"坡度"。直接在 Phase 3 里重分类。

### C5: 坡度

**工具：Spatial Analyst → Surface → Slope**

- Input Raster: `DTM_HKI`
- Output Measurement: **PERCENT_RISE** ⚠️ (Table 2 是百分比，不要选 DEGREE！)
- Output: `C5_Slope`

### C6: POI 距离

**工具：Euclidean Distance**

- Input: `POI_HKI`
- Output: `C6_POI_Dist`

---

## Phase 3: 重分类 (Reclassify)

6 个并列的 **Reclassify** 工具 (Spatial Analyst → Reclass → Reclassify)，把连续值转成 1-5 分。

### C1 重分类 → `C1_Reclass`

| Start | End | New |
|---|---|---|
| 0 | 250 | **5** |
| 250 | 500 | **4** |
| 500 | 800 | **3** |
| 800 | 1100 | **2** |
| 1100 | MAX (填一个很大的数，如 10000) | **1** |

### C2 重分类 → `C2_Reclass` (Natural Breaks 五分位)

这个要特殊处理：
1. 工具窗口里点 **"Classify..."** 按钮
2. Method 选 **Natural Breaks (Jenks)**
3. Classes = **5**
4. 确定后回到 Reclassify 主界面，把 5 档从低到高映射为 **1, 2, 3, 4, 5**

💡 想省事也可以打开 `phase2_analysis.gdb\C2_Reclass` 看原断点值，直接抄过来填。

### C3 重分类 → `C3_Reclass`

| Start | End | New |
|---|---|---|
| 0 | 150 | **1** |
| 150 | 300 | **2** |
| 300 | 500 | **3** |
| 500 | 800 | **4** |
| 800 | MAX | **5** |

### C4 重分类 → `C4_Reclass` (用 CSV 表)

**工具：Spatial Analyst → Reclass → Reclass by Table** (注意是 Reclass by Table，不是普通 Reclassify)

- Input Raster: `Landuse_HKI`
- Reclass Table: `teamwork\reclass_rule.csv`
- From Value Field / To Value Field / Output Value Field: 按 CSV 的列名对上就行
- Output: `C4_Reclass`

💡 如果 Reclass by Table 用 CSV 报错，退回用普通 Reclassify，手动按 Table 2 填：
```
11 → 5
32, 41 → 4
21, 22, 31 → 3
1, 2, 42 → 2
51, 61 → 1
71, 72, 73, 74, 83, 91, 92 → NoData
```

### C5 重分类 → `C5_Reclass`

| Start | End | New |
|---|---|---|
| 0 | 2 | **5** |
| 2 | 5 | **4** |
| 5 | 10 | **3** |
| 10 | 15 | **2** |
| 15 | MAX | **1** |

### C6 重分类 → `C6_Reclass`

| Start | End | New |
|---|---|---|
| 0 | 300 | **5** |
| 300 | 600 | **4** |
| 600 | 1000 | **3** |
| 1000 | 1500 | **2** |
| 1500 | MAX | **1** |

---

## Phase 4: 加权叠加 (Weighted Overlay × 3 情景)

6 个 Reclass 栅格同时接入 **3 个** Weighted Overlay 工具。

**工具：Spatial Analyst → Overlay → Weighted Overlay**

每个 Weighted Overlay 的通用设置：
- Evaluation Scale: `1 to 5 by 1`
- 逐个添加 6 个 Reclass 栅格 (C1–C6)
- 每个栅格的 Scale Value 保持原值 (1→1, 2→2, …, 5→5)
- ⚠️ NoData 的 Scale Value 保持为 **NoData** (别改成 Restricted 以外的值)

### 情景 A: 等权重 → `Scenario_A_EqualWeight`

| 准则 | % Influence |
|---|---|
| C1_Reclass | 17 |
| C2_Reclass | 17 |
| C3_Reclass | 17 |
| C4_Reclass | 16 |
| C5_Reclass | 16 |
| C6_Reclass | 17 |
| **合计** | **100** |

### 情景 B: 交通优先 → `Scenario_B_Transport`

| 准则 | % Influence |
|---|---|
| C1_Reclass | 30 |
| C2_Reclass | 10 |
| C3_Reclass | 10 |
| C4_Reclass | 7 |
| C5_Reclass | 5 |
| C6_Reclass | 38 |

### 情景 C: 公平覆盖 → `Scenario_C_Equity`

| 准则 | % Influence |
|---|---|
| C1_Reclass | 10 |
| C2_Reclass | 25 |
| C3_Reclass | 30 |
| C4_Reclass | 8 |
| C5_Reclass | 5 |
| C6_Reclass | 22 |

💡 Weighted Overlay 在画布上看起来很大，3 个并排挺壮观的。这也是建模过程中最核心的一步，汇报截图往往都是截这里。

---

## Phase 5: 候选站点提取 (3 条独立分支)

三个情景的提取逻辑**不一样**，分别处理：

### 情景 A: 7 个局部极值点

```
Scenario_A_EqualWeight 
    ↓ Focal Statistics (Circle 500m, MAXIMUM)
FocalMax_A
    ↓ Raster Calculator: (Scenario_A == FocalMax_A) & (Scenario_A == 5)
Peaks_A (0/1 栅格)
    ↓ Con (Peaks_A == 1, Scenario_A)
Peaks_A_final
    ↓ Raster to Point
CandidatePoints_A_all
    ↓ Sort (grid_code DESC)
Top7_Sites_A ← 最终输出
```

**具体工具：**

1. **Focal Statistics** (Spatial Analyst)
   - Input: `Scenario_A_EqualWeight`
   - Neighborhood: **Circle, Radius = 500, MAP units**
   - Statistics type: **MAXIMUM**
   - Output: `FocalMax_A`

2. **Raster Calculator** (Spatial Analyst → Map Algebra)
   - Expression: `Con(("Scenario_A_EqualWeight" == "FocalMax_A") & ("Scenario_A_EqualWeight" == 5), 1)`
   - Output: `Peaks_A`

3. **Raster to Point** (Conversion → From Raster)
   - Input: `Peaks_A`
   - Output: `CandidatePoints_A_all`

4. **Sort** (Data Management → General)
   - Input: `CandidatePoints_A_all`
   - Sort Field: `grid_code`, DESCENDING
   - Output: `CandidatePoints_A_sorted`

5. **Select** (直接拿前 7 个)
   - 或用 **Copy Features** + SQL `OBJECTID <= 7` 筛选
   - Output: `Top7_Sites_A`

### 情景 B: 10 个 top 聚类中心 (Score = 5)

```
Scenario_B_Transport
    ↓ Focal Statistics → FocalMax_B
    ↓ Raster Calculator (value == max AND value == 5) → Peaks_B
    ↓ Raster to Point → CandidatePoints_B_all
    ↓ Pairwise Buffer (250m) → Buffer_B
    ↓ Pairwise Dissolve (Multi-part 设 False) → Clusters_B
    ↓ Add Field + Calculate Field (面积字段) 
    ↓ Sort by area DESC + Select top 10
    ↓ Feature to Point (centroid) → ClusterCenters_B
    ↓ Top10_Sites_B ← 最终输出
```

**关键工具：**

1. **Focal Statistics** → `FocalMax_B` (同 A)
2. **Raster Calculator** → `Peaks_B`：`Con((Scenario_B == FocalMax_B) & (Scenario_B == 5), 1)`
3. **Raster to Point** → `CandidatePoints_B_all`
4. **Pairwise Buffer** (Analysis)
   - Input: `CandidatePoints_B_all`
   - Distance: **250 Meters** (如果跑出来跟 `Buffer_B` 不像，检查一下队友用的是多少)
   - Dissolve Type: **ALL**
   - Output: `Buffer_B`
5. **Multipart To Singlepart** (Data Management → Features)
   - 把融合的 buffer 炸成独立的多边形 → `Clusters_B`
6. **Calculate Geometry Attributes** (Data Management → Fields)
   - 加一个 `Area_m2` 字段 = `Area in square meters`
7. **Sort** → 按 `Area_m2` DESC
8. **Copy Features** with SQL `OBJECTID <= 10` → top 10 clusters
9. **Feature to Point** (Data Management → Features)
   - Inside = Checked (质心落在 polygon 内)
   - Output: `Top10_Sites_B`

### 情景 C: 10 个 top 聚类中心 (Score ≥ 4)

跟情景 B **完全一样**，只有一步不同：

- 第 2 步 Raster Calculator 表达式改成：
  `Con((Scenario_C == FocalMax_C) & (Scenario_C >= 4), 1)` ← **注意是 ≥ 4 不是 == 5**

其余工具名称、参数全部跟 B 一致，只是把 `_B` 改成 `_C`，最终输出 `Top10_Sites_C`。

💡 画布上这 3 条分支会比较壮观，排版建议把它们**上下平行**排列，视觉上一目了然。

---

## Phase 6 (可选加分项): 差异栅格

汇报时讲"情景对比"很加分：

1. **Raster Calculator**: `"Scenario_B_Transport" - "Scenario_A_EqualWeight"` → `Diff_B_minus_A`
2. **Raster Calculator**: `"Scenario_C_Equity" - "Scenario_A_EqualWeight"` → `Diff_C_minus_A`

正值 = B/C 比 A 更适宜；负值 = 反之。符号化用红蓝发散色带。

---

## 最终步骤：保存 + 验证 + 截图

### 保存
- `Ctrl+S` 存模型
- File → Save Project 存整个工程

### 验证 (任选一种)

**方案 A (最省事)**：点画布顶部的 **Validate** 按钮 (⚠️ 图标)。如果所有工具都变成彩色 (不是灰色)、没有红 X，就说明连接正确。**不需要真正 Run**。

**方案 B (更稳妥)**：真的点 Run 跑一次。因为环境和参数正确，理论上应该出结果，跑出来的 `C1_Reclass` 等栅格可以跟 `phase2_analysis.gdb` 里的对比 —— 一致就说明你搭的模型跟队友手动做的结果一致。

⚠️ 跑 Run 的话注意**输出位置** (会写到 `7305_TeamProject.gdb`)，别覆盖 `phase2_analysis.gdb` 里的原始结果。

### 截图清单 (给 PPT 用)

1. 整个模型画布的**全景图** (缩放到能看全 5 个 Phase)
2. 每个 Phase 的局部放大
3. 其中一个 Weighted Overlay 的参数面板 (展示权重配置)
4. Validate 通过的绿色√状态

---

## 🚧 常见坑

| 症状 | 原因 | 解法 |
|---|---|---|
| 工具一直灰色，拒绝连接 | 输入类型不对 (比如把矢量连到栅格工具) | 检查箭头两端的数据类型是否匹配 |
| Reclassify 输出全是 NoData | Reclass 范围没覆盖实际值域 | 把最后一档的 End 改大 (比如 99999) |
| Euclidean Distance 跑得超级慢 | Cell Size 没设 5m 导致精度过高 | 回 Phase 0 确认环境 Cell Size = 5 |
| Weighted Overlay 报错 "Scale values don't match" | 某个 Reclass 栅格有非 1-5 的值 | 检查该 Reclass 是不是把断点漏了一段 |
| 中文路径乱码 | ArcGIS Pro 对中文路径不友好 | 工程路径最好全英文 |
| DTM 文件名空格报错 | "Digital Terrain Model.tif" | 复制重命名为 `DTM_5m.tif` |

---

## 📋 自检清单

做完之后对着这个清单过一遍：

- [ ] 模型里有且仅有 **1 个研究区边界输入** (被多个工具共用)
- [ ] Phase 1 有 4 个 Clip + 2 个 Extract by Mask，共 **6 个数据准备工具**
- [ ] Phase 2 有 5 个准则层生成工具 (C4 跳过) → 5 个连续值栅格
- [ ] Phase 3 有 **6 个 Reclassify** → 6 个 1-5 分栅格
- [ ] Phase 4 有 **3 个 Weighted Overlay**，权重分别是 A/B/C 三组
- [ ] Phase 5 有 **3 条提取分支**，最终产出 Top7_Sites_A, Top10_Sites_B, Top10_Sites_C
- [ ] 模型 Validate 通过 (无红 X)
- [ ] 模型保存在 `7305_TeamProject.atbx` 里

完成 ✓ 恭喜，你的建模任务就搞定了！

---

## 💬 卡住了找我

遇到任何一步不确定的，截图发过来。特别是：
- 工具面板上哪个参数填什么
- 报错信息看不懂
- 连接出来的结果跟 gdb 里已有的对不上

我会基于你的具体情况给出针对性的下一步。
