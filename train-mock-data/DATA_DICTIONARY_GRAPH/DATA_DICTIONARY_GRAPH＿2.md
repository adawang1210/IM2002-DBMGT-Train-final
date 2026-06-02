# 陳楷
# 🚇 TransitFlow 圖形資料庫 (Neo4j) Schema 設計 — 提案 2：統一模型

> **資料來源**：`metro_stations.json` (20 nodes / 42 adj edges) 與 `national_rail_stations.json` (10 nodes / 18 adj edges)。
> **跨網路轉乘車站對**：3 對 (MS01↔NR01, MS07↔NR03, MS15↔NR07)。
> **設計取向**：相對於提案 1 的「分離模型」，本提案採「**統一模型**」 — 用單一 Label `Station` + 單一 Edge `[:CONNECTS_TO]`，以 property 區分 network。優勢在於跨網路查詢 (`query_interchange_path`, `query_delay_ripple`) 寫起來更一致，APOC Dijkstra 的 `relationshipTypesAndDirections` 參數也更簡潔。

---

## 1. 節點設計 (Nodes)

### 🟦 Label：`Station`

代表所有車站，不論其屬於 metro 或 national rail。網路類型透過 `network` property 區分。

| 屬性名稱 | 資料型別 | 是否必填 | 範例值 | 來源 JSON 欄位 |
|---|---|---|---|---|
| `station_id` | String (PK, unique) | ✅ | `"MS01"` / `"NR01"` | `station_id` |
| `name` | String | ✅ | `"Central Square"` / `"Central Station"` | `name` |
| `network` | String enum (`"metro"` \| `"rail"`) | ✅ | `"metro"` | 由 JSON 檔案來源決定 |
| `lines` | List\<String\> | ✅ | `["M1", "M2"]` / `["NR1", "NR2"]` | `lines` |
| `is_metro_interchange` | Boolean | ⭕ (可選) | `true` | `is_interchange_metro` |
| `is_rail_interchange` | Boolean | ⭕ (可選) | `true` | `is_interchange_national_rail` |

**索引建議**：
- `CREATE CONSTRAINT station_id_unique FOR (s:Station) REQUIRE s.station_id IS UNIQUE;`
- `CREATE INDEX station_network FOR (s:Station) ON (s.network);`

> 為什麼把 `is_*_interchange` 留在節點上？這些欄位可加速 `query_interchange_path` 的起點/終點過濾 (`WHERE s.is_metro_interchange = true`)，避免每次都掃 INTERCHANGE 邊。

---

## 2. 關係設計 (Relationships)

### 🟩 Type：`[:CONNECTS_TO]` — 同網路相鄰邊

代表一段實體軌道區間，metro 與 rail 共用同一個 type，由 `network` property 區分。

| 屬性名稱 | 資料型別 | 是否必填 | 範例值 | 來源 JSON 欄位 |
|---|---|---|---|---|
| `network` | String enum (`"metro"` \| `"rail"`) | ✅ | `"metro"` | 由 JSON 檔案來源決定 |
| `line` | String | ✅ | `"M1"` / `"NR1"` | `adjacent_stations[].line` |
| `travel_time_min` | Integer (>0) | ✅ | `3` (metro), `18` (rail) | `adjacent_stations[].travel_time_min` |

**方向**：`(:Station)-[:CONNECTS_TO]->(:Station)`，**雙向各建一條** (見 Q3)。

### 🟪 Type：`[:INTERCHANGE]` — 跨網路轉乘邊

代表 metro 與 rail 兩站之間的步行轉乘 (例如 MS01↔NR01 同處 Central Square / Central Station)。

| 屬性名稱 | 資料型別 | 是否必填 | 範例值 | 來源 JSON 欄位 |
|---|---|---|---|---|
| `travel_time_min` | Integer | ✅ (預設 5) | `5` | ❌ 原始資料未提供 |
| `transfer_type` | String | ⭕ | `"walk"` | ❌ 衍生欄位 |

**方向**：`(:Station {network:"metro"})-[:INTERCHANGE]->(:Station {network:"rail"})` 與反向，**雙向各建一條**。

---

## 3. 設計決策

### Q1：節點標籤怎麼分？

- **選擇：B — 統一 `Station` label + `network` property**
- **理由**：
  1. **跨網路查詢一致性**：`query_interchange_path`、`query_delay_ripple` 需要無視網路邊界搜尋。統一 label 讓 `MATCH (s:Station)` 一次掃完整圖，無需在 Cypher 寫 `MATCH (s:MetroStation|NationalRailStation)` 這種笨拙語法。
  2. **APOC Dijkstra 介接更乾淨**：`apoc.algo.dijkstra(start, end, 'CONNECTS_TO|INTERCHANGE>', 'travel_time_min')` 不需要對 start/end 做 label 判斷，Python 層 (`network="auto"`) 只要從 ID 前綴推斷後設定 `network` 過濾即可。
  3. **資料規模小、語意一致**：只有 30 個節點，metro/rail 兩者語意都是「車站」，沒必要用 label 切割。
  4. **取捨**：Neo4j Browser 視覺化時兩種網路同色 — 可用 `style.grass` 依 `network` property 上色補償。
- **不選 A 的原因**：分離 label 讓跨網路 traversal 寫起來繁瑣 (e.g. `MATCH (s:MetroStation|NationalRailStation)` 在 Cypher 早期版本不支援，需用 `apoc.meta` 或 union)。
- **不選 C 的原因**：多 label (`:Station:MetroStation`) 是折衷方案，但統一 label 的好處 C 拿不到 (仍需在不同 label 間切換)，反而徒增 schema 複雜度。

### Q2：同網路相鄰邊用單一型還是分網路？

- **選擇：A — 統一 `[:CONNECTS_TO]` + `network` property**
- **理由**：
  1. **與 Q1 一致**：節點已統一，邊也統一才能維持模型對稱性。
  2. **`query_alternative_routes`、`query_delay_ripple` 簡潔**：這兩個查詢只在意「相鄰」，不在意 metro/rail 區別，單一 type 讓 `MATCH (a)-[:CONNECTS_TO*1..n]-(b)` 直接寫得出來。
  3. **APOC 參數簡單**：Dijkstra 的 relationship filter 寫成 `'CONNECTS_TO>|INTERCHANGE>'`，比 `'METRO_LINK>|RAIL_LINK>|INTERCHANGE_TO>'` 更短、更不易拼錯。
  4. **過濾仍可細緻**：要限定只走 metro，加 `WHERE r.network = 'metro'` 即可，沒有資訊損失。
- **不選 B 的原因**：分 type (`METRO_LINK`/`RAIL_LINK`) 在 Neo4j Browser 視覺差異更明顯，但本系統的 6 個查詢全是程式驅動，視覺化效益小於語法成本。

### Q3：跨網路轉乘關係的方向？

- **選擇：A — 雙向各建一條 (對稱建邊)**
- **理由**：
  1. **APOC Dijkstra 預設依方向 traverse**：用 `>` 後綴 (`'CONNECTS_TO>'`) 指定 outgoing 才能取得正確結果；雙向建邊讓查詢無論 metro→rail 還是 rail→metro 都同樣自然。
  2. **同網路相鄰邊也採雙向**：metro/rail 軌道實際上雙向通行，建模一致比較好理解。
  3. **明確優於隱式**：B 方案 (單向 + 查詢時強制無向) 需要每個查詢都記得寫 `-[:INTERCHANGE]-` (沒箭頭)，容易在某次補新查詢時忘記造成 bug。
  4. **儲存成本可忽略**：3 對轉乘 × 2 = 6 條邊，加上 60 條同網路雙向邊也才 120 條 relationship，遠低於 Neo4j 性能門檻。
- **不選 B 的原因**：單向儲存節省一半邊，但增加查詢心智負擔，且與其他查詢的方向慣例不一致。

### Q4：`INTERCHANGE` 的 `travel_time_min` 怎麼處理？

- **選擇：A — 預設 5 分鐘**
- **理由**：
  1. **Dijkstra 不容許 NULL**：APOC `apoc.algo.dijkstra` 在權重屬性為 NULL 時會把該邊視為極大值或直接跳過，造成 `query_shortest_route`/`query_cheapest_route` 結果失真。
  2. **5 分鐘是合理 baseline**：transfer between adjacent metro/rail platforms 通常 3–7 分鐘，取中位數作為 demo 預設值。
  3. **可調整**：未來若拿到實測資料，只需 `MATCH ()-[r:INTERCHANGE]-() SET r.travel_time_min = ...` 一條 Cypher 全圖更新。
  4. **註記透明度**：在 schema 屬性表已標示「來源 JSON 未提供」，提醒後續維護者。
- **不選 B 的原因**：留空雖然「資料更誠實」，但會直接打掉 6 個查詢中至少 3 個的可用性 (shortest/cheapest/interchange path)，違反「schema 必須能支援這 6 個查詢」的硬性約束。

---

## 4. Cypher 雛形

```cypher
// ─────────────────────────────────────────────────────────────
// 0. Constraints / Indexes (run once)
// ─────────────────────────────────────────────────────────────
CREATE CONSTRAINT station_id_unique IF NOT EXISTS
FOR (s:Station) REQUIRE s.station_id IS UNIQUE;

CREATE INDEX station_network IF NOT EXISTS
FOR (s:Station) ON (s.network);

// ─────────────────────────────────────────────────────────────
// 1. 節點建立 (MERGE 避免重複)
// ─────────────────────────────────────────────────────────────
// metro 站範例 (來自 metro_stations.json)
MERGE (s:Station {station_id: "MS01"})
SET s.name = "Central Square",
    s.network = "metro",
    s.lines = ["M1", "M2"],
    s.is_metro_interchange = true,
    s.is_rail_interchange = true;

// rail 站範例 (來自 national_rail_stations.json)
MERGE (s:Station {station_id: "NR01"})
SET s.name = "Central Station",
    s.network = "rail",
    s.lines = ["NR1", "NR2"],
    s.is_metro_interchange = true,
    s.is_rail_interchange = true;

// ─────────────────────────────────────────────────────────────
// 2. 同網路相鄰邊 [:CONNECTS_TO] (雙向各建一條)
// ─────────────────────────────────────────────────────────────
// metro 範例：MS01 <-> MS02 on line M1, 3 min
MATCH (a:Station {station_id: "MS01"}), (b:Station {station_id: "MS02"})
MERGE (a)-[r1:CONNECTS_TO {line: "M1"}]->(b)
  SET r1.network = "metro", r1.travel_time_min = 3
MERGE (b)-[r2:CONNECTS_TO {line: "M1"}]->(a)
  SET r2.network = "metro", r2.travel_time_min = 3;

// rail 範例：NR01 <-> NR02 on line NR1, 12 min
MATCH (a:Station {station_id: "NR01"}), (b:Station {station_id: "NR02"})
MERGE (a)-[r1:CONNECTS_TO {line: "NR1"}]->(b)
  SET r1.network = "rail", r1.travel_time_min = 12
MERGE (b)-[r2:CONNECTS_TO {line: "NR1"}]->(a)
  SET r2.network = "rail", r2.travel_time_min = 12;

// ─────────────────────────────────────────────────────────────
// 3. 跨網路轉乘邊 [:INTERCHANGE] (雙向各建一條, 預設 5 分鐘)
// ─────────────────────────────────────────────────────────────
// MS01 (Central Square) <-> NR01 (Central Station)
MATCH (m:Station {station_id: "MS01"}), (n:Station {station_id: "NR01"})
MERGE (m)-[r1:INTERCHANGE]->(n)
  SET r1.travel_time_min = 5, r1.transfer_type = "walk"
MERGE (n)-[r2:INTERCHANGE]->(m)
  SET r2.travel_time_min = 5, r2.transfer_type = "walk";

// ─────────────────────────────────────────────────────────────
// 4. (參考) 對應 6 個 query_ 函式的 Cypher 樣板
// ─────────────────────────────────────────────────────────────
// query_shortest_route — Dijkstra by travel_time_min
MATCH (start:Station {station_id: $origin}), (end:Station {station_id: $destination})
CALL apoc.algo.dijkstra(start, end, 'CONNECTS_TO>|INTERCHANGE>', 'travel_time_min')
YIELD path, weight
RETURN path, weight AS total_time_min;

// query_station_connections — 列出某站所有直連
MATCH (s:Station {station_id: $station_id})-[r:CONNECTS_TO|INTERCHANGE]->(neighbor:Station)
RETURN neighbor.station_id, neighbor.name, type(r) AS rel_type,
       r.line AS line, r.travel_time_min AS travel_time_min;

// query_delay_ripple — N hops 內受影響的站
MATCH (s:Station {station_id: $delayed_id})-[:CONNECTS_TO|INTERCHANGE*1..2]-(affected:Station)
RETURN DISTINCT affected.station_id, affected.name, affected.lines;
```

---

## 5. 提案 1 vs 提案 2 對照表

| 維度 | 提案 1 (分離模型) | 提案 2 (統一模型, 本檔) |
|---|---|---|
| Label | `MetroStation` / `NationalRailStation` | `Station` + `network` |
| 同網路邊 | `[:METRO_LINK]` / `[:RAIL_LINK]` | `[:CONNECTS_TO]` + `network` |
| 跨網路邊 | `[:INTERCHANGE_TO]` (雙向) | `[:INTERCHANGE]` (雙向) |
| Cypher 跨網路寫法 | 需 union 或多 label | 單一 `MATCH (s:Station)` |
| Browser 視覺差異 | 強 (不同 label 自動上色) | 弱 (需 grass 上色補償) |
| APOC Dijkstra 參數 | `'METRO_LINK>\|RAIL_LINK>\|INTERCHANGE_TO>'` | `'CONNECTS_TO>\|INTERCHANGE>'` |
| 適合場景 | 強調網路自治、各自演化 | 強調跨網路一體化路徑搜尋 |

選用建議：本系統 6 個 query 中有 4 個 (`shortest`, `cheapest`, `interchange_path`, `delay_ripple`) 都會跨網路 traversal — **本提案 (2) 在實作成本與查詢可讀性上整體較優**。
