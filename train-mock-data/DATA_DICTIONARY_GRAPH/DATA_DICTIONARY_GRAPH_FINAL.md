# 🚇 TransitFlow 圖形資料庫 (Neo4j) Schema — 最終版

> **狀態:** 三份提案 (`DD_1` 分離模型 / `DD_2` 統一模型 / `DD_3` 三層模型) 比對後的團隊定案。
> **資料來源:** `metro_stations.json` (20 站、42 條相鄰邊) + `national_rail_stations.json` (10 站、18 條相鄰邊),跨網路轉乘 3 對 (MS01↔NR01、MS07↔NR03、MS15↔NR07)。
> **支援查詢:** `databases/graph/queries.py` 中 6 個 `query_` 函式。
>
> **原則:** 不是一定要從三份提案裡選一份全採用。圖形 schema 的核心約束很清楚 (6 個 `query_` 必須能跑、APOC Dijkstra 不容許 NULL 權重、跨網路 traversal 要簡潔),三位都不夠完整時,直接給出新組合才是負責任的整合 — 例如本檔的 INTERCHANGE 邊就是 DD_1/DD_2 的「雙向 + 預設 5 分鐘」加上 DD_3 提案的 `transfer_note` 屬性。

---

## Part A — 三份提案比對報告

### A.1 設計四問選擇對照

| 問題 | DD_1 (Xan) | DD_2 (陳楷) | DD_3 (張恩家) | 最終決定 |
|---|---|---|---|---|
| **Q1** 節點 label | A. 分離 `MetroStation` / `NationalRailStation` | B. 統一 `Station` + `network` | B. 統一 `Station` + `network` (+ 額外 `Line` / `Network` 節點) | **B. 統一 `Station`** |
| **Q2** 同網路邊 type | B. 分 `[:METRO_LINK]` / `[:RAIL_LINK]` | A. 統一 `[:CONNECTS_TO]` | A. 統一 `[:CONNECTS_TO]` | **A. 統一 `[:CONNECTS_TO]`** |
| **Q3** 跨網路邊方向 | A. 雙向各建一條 | A. 雙向各建一條 | (未交代,Cypher 實作為單向) | **A. 雙向各建一條** |
| **Q4** INTERCHANGE 時間 | A. 預設 5 分鐘 | A. 預設 5 分鐘 | (未交代,Cypher 完全省略此屬性) | **A. 預設 5 分鐘** |

### A.2 三份提案優缺點

| 維度 | DD_1 分離模型 | DD_2 統一模型 | DD_3 三層模型 |
|---|---|---|---|
| **跨網路查詢可讀性** | 🟡 需 `MATCH (s:MetroStation\|NationalRailStation)` | 🟢 單一 `MATCH (s:Station)` | 🟢 同 DD_2 |
| **APOC Dijkstra filter** | `METRO_LINK>\|RAIL_LINK>\|INTERCHANGE_TO>` | `CONNECTS_TO>\|INTERCHANGE>` | 同 DD_2 (但邊單向會壞) |
| **Browser 視覺差異** | 🟢 不同 label 自動上色 | 🟡 需 grass 補色 | 🟡 同 DD_2 |
| **支援 6 個 `query_`** | ✅ 全支援 | ✅ 全支援 | ❌ shortest/cheapest/interchange 因 (1)(2)(3) 失效 |
| **設計規格完整度** | ✅ 屬性表 + 4 問俱全 | ✅ 屬性表 + 4 問俱全 | ❌ 缺 Q1~Q4、屬性表少 2 欄 |
| **複雜度** | 🟢 低 | 🟢 低 | 🟡 多 `Line` / `Network` / `SERVES` / `PART_OF` 但對 6 query 無增益 |
| **可圈點之處** | 視覺直觀 | 跨網路查詢最簡潔 | 提出 Line/Network 抽象 (對未來擴充有價值) |

### A.3 最終決策依據

1. **Q1、Q2 採 DD_2/DD_3 立場**:6 個 `query_` 中有 4 個跨網路 traversal,統一 label/edge 在 Cypher 寫起來明顯較短。
2. **Q3、Q4 採 DD_1/DD_2 立場**:DD_3 在這兩題的具體 Cypher 實作有 bug,直接會打死 Dijkstra 類查詢。
3. **`Line` / `Network` 節點不納入最終版**:6 個 `query_` 沒有任何一個需要 traverse 到這兩種節點 — 路線/系統判斷全部靠 Station 與 Edge 上的 property 即可。為避免 seed 腳本與查詢函式變得複雜,採 KISS 原則。但保留為 §Part E 「可選擴充」 供未來需要 line-level 分析時加上。
4. **DD_3 的 `transfer_note` 屬性納入**:DD_3 在 INTERCHANGE 邊上加了 `transfer_note` 是 nice-to-have (例如 `"Central transfer"`),除錯時很有用,最終版保留。

---

## Part B — 最終 Schema (團隊鎖定)

> 以下為團隊鎖定,任何欄位/節點/邊 type 命名變更必須整組同意,並同步更新 `AI_SESSION_CONTEXT.md`、`skeleton/seed_neo4j.py`、`databases/graph/queries.py`。

### B.1 節點 (Nodes)

#### Label: `Station`

代表所有車站,不論 metro 或 rail,以 `network` property 區分。

| 屬性名稱 | 資料型別 | 是否必填 | 範例值 | 來源 JSON 欄位 |
|---|---|---|---|---|
| `station_id` | String (PK, unique) | ✅ | `"MS01"` / `"NR01"` | `station_id` |
| `name` | String | ✅ | `"Central Square"` | `name` |
| `network` | String enum (`"metro"` \| `"rail"`) | ✅ | `"metro"` | 由來源檔案決定 |
| `lines` | List\<String\> | ✅ | `["M1", "M2"]` | `lines` |
| `is_interchange_metro` | Boolean | ⭕ | `true` | `is_interchange_metro` |
| `is_interchange_national_rail` | Boolean | ⭕ | `true` | `is_interchange_national_rail` |

**索引/約束:**
```cypher
CREATE CONSTRAINT station_id_unique IF NOT EXISTS
  FOR (s:Station) REQUIRE s.station_id IS UNIQUE;
CREATE INDEX station_network IF NOT EXISTS
  FOR (s:Station) ON (s.network);
```

### B.2 關係 (Relationships)

#### Type: `[:CONNECTS_TO]` — 同網路相鄰邊

| 屬性名稱 | 資料型別 | 是否必填 | 範例值 | 來源 JSON 欄位 |
|---|---|---|---|---|
| `network` | String enum | ✅ | `"metro"` / `"rail"` | 由來源檔案決定 |
| `line` | String | ✅ | `"M1"` / `"NR1"` | `adjacent_stations[].line` |
| `travel_time_min` | Integer (>0) | ✅ | `3` (metro) / `18` (rail) | `adjacent_stations[].travel_time_min` |

**方向:** `(:Station)-[:CONNECTS_TO]->(:Station)`,**雙向各建一條**。

#### Type: `[:INTERCHANGE]` — 跨網路轉乘邊

| 屬性名稱 | 資料型別 | 是否必填 | 範例值 | 來源 JSON 欄位 |
|---|---|---|---|---|
| `travel_time_min` | Integer | ✅ (預設 `5`) | `5` | ❌ 原始資料未提供 |
| `transfer_type` | String | ⭕ | `"metro_rail"` | ❌ 衍生欄位 |
| `transfer_note` | String | ⭕ | `"Central transfer"` | ❌ 衍生欄位 (DD_3 提案) |

**方向:** `(:Station)-[:INTERCHANGE]->(:Station)`,**雙向各建一條**。

> ⚠️ **`travel_time_min` 必填且必須 > 0**:APOC Dijkstra 對 NULL 權重會異常,團隊定 `5` 為 baseline,未來實測再批次 update。

---

## Part C — Cypher 雛形

### C.1 Constraints / Indexes (跑一次)

```cypher
CREATE CONSTRAINT station_id_unique IF NOT EXISTS
  FOR (s:Station) REQUIRE s.station_id IS UNIQUE;
CREATE INDEX station_network IF NOT EXISTS
  FOR (s:Station) ON (s.network);
```

### C.2 節點建立 (`MERGE` 確保 idempotent)

```cypher
// metro 站範例
MERGE (s:Station {station_id: "MS01"})
SET s.name = "Central Square",
    s.network = "metro",
    s.lines = ["M1", "M2"],
    s.is_interchange_metro = true,
    s.is_interchange_national_rail = true;

// rail 站範例
MERGE (s:Station {station_id: "NR01"})
SET s.name = "Central Station",
    s.network = "rail",
    s.lines = ["NR1", "NR2"],
    s.is_interchange_metro = true,
    s.is_interchange_national_rail = true;
```

### C.3 同網路邊 `[:CONNECTS_TO]` (雙向)

```cypher
// metro: MS01 <-> MS02 on line M1, 3 min
MATCH (a:Station {station_id: "MS01"}), (b:Station {station_id: "MS02"})
MERGE (a)-[r1:CONNECTS_TO {line: "M1"}]->(b)
  SET r1.network = "metro", r1.travel_time_min = 3
MERGE (b)-[r2:CONNECTS_TO {line: "M1"}]->(a)
  SET r2.network = "metro", r2.travel_time_min = 3;

// rail: NR01 <-> NR02 on line NR1, 12 min
MATCH (a:Station {station_id: "NR01"}), (b:Station {station_id: "NR02"})
MERGE (a)-[r1:CONNECTS_TO {line: "NR1"}]->(b)
  SET r1.network = "rail", r1.travel_time_min = 12
MERGE (b)-[r2:CONNECTS_TO {line: "NR1"}]->(a)
  SET r2.network = "rail", r2.travel_time_min = 12;
```

### C.4 跨網路邊 `[:INTERCHANGE]` (雙向 + 預設 5 分鐘)

```cypher
// MS01 (Central Square) <-> NR01 (Central Station)
MATCH (m:Station {station_id: "MS01"}), (n:Station {station_id: "NR01"})
MERGE (m)-[r1:INTERCHANGE]->(n)
  SET r1.travel_time_min = 5,
      r1.transfer_type = "metro_rail",
      r1.transfer_note = "Central transfer"
MERGE (n)-[r2:INTERCHANGE]->(m)
  SET r2.travel_time_min = 5,
      r2.transfer_type = "metro_rail",
      r2.transfer_note = "Central transfer";

// 同樣套用到 MS07<->NR03 (Old Town transfer) 與 MS15<->NR07 (Ferndale transfer)
```

### C.5 對應 6 個 `query_` 的 Cypher 樣板

```cypher
// query_shortest_route — Dijkstra by travel_time_min
MATCH (start:Station {station_id: $origin}), (end:Station {station_id: $destination})
CALL apoc.algo.dijkstra(start, end, 'CONNECTS_TO>|INTERCHANGE>', 'travel_time_min')
YIELD path, weight
RETURN path, weight AS total_time_min;

// query_alternative_routes — 排除某站的 K shortest paths
MATCH (start:Station {station_id: $origin}), (end:Station {station_id: $destination}),
      path = (start)-[:CONNECTS_TO|INTERCHANGE*..15]->(end)
WHERE NONE(n IN nodes(path) WHERE n.station_id = $avoid_id)
RETURN path, reduce(t = 0, r IN relationships(path) | t + r.travel_time_min) AS total_time
ORDER BY total_time LIMIT $max_routes;

// query_interchange_path — metro <-> rail 跨網路最短路徑
MATCH (start:Station {station_id: $origin}), (end:Station {station_id: $destination})
WHERE start.network <> end.network
CALL apoc.algo.dijkstra(start, end, 'CONNECTS_TO>|INTERCHANGE>', 'travel_time_min')
YIELD path, weight
RETURN path, weight AS total_time_min,
       [n IN nodes(path) WHERE n.is_interchange_metro AND n.is_interchange_national_rail
        | n.station_id] AS interchange_points;

// query_delay_ripple — N hops 內受影響的站 (不分網路、不分方向)
MATCH (s:Station {station_id: $delayed_id})-[:CONNECTS_TO|INTERCHANGE*1..2]-(affected:Station)
RETURN DISTINCT affected.station_id, affected.name, affected.lines;

// query_station_connections — 列出某站所有直連
MATCH (s:Station {station_id: $station_id})-[r:CONNECTS_TO|INTERCHANGE]->(neighbor:Station)
RETURN neighbor.station_id, neighbor.name, type(r) AS rel_type,
       r.line AS line, r.travel_time_min AS travel_time_min;

// query_cheapest_route — 同 shortest_route 但 weight 改為 fare
// (fare 計算邏輯由查詢函式注入,可在邊上加 .fare property 或在 Python 側用 schedule table)
```

---

## Part D — 整體決議摘要

| Schema 元素 | 主要採用 | 來源 | 關鍵理由 |
|---|---|---|---|
| **Label `Station`** | 統一 label + `network` property | DD_2 / DD_3 共識 | 6 個 `query_` 中 4 個跨網路 traversal,單一 label Cypher 最簡潔 |
| **`station_id` / `name` / `lines`** | 三家共識 | 三份都同 | 對應 JSON 主 key |
| **`is_interchange_*` 旗標** | DD_2 / DD_3 提案 | DD_2 / DD_3 | 加速 `query_interchange_path` 起終點過濾,免掃 INTERCHANGE 邊 |
| **`network` property on Station** | DD_2 / DD_3 共識 | DD_2 / DD_3 | 配合統一 label 區分系統,對應 `query_interchange_path` 的 `WHERE start.network <> end.network` |
| **Edge `[:CONNECTS_TO]`** | 統一 type + `network` property | DD_2 / DD_3 共識 | 跨網路查詢統一 filter,APOC Dijkstra 參數較短 |
| **Edge 雙向建立** | 雙向各建一條 | DD_1 / DD_2 共識 | APOC Dijkstra `>` filter 依方向 traverse,單向會打壞反向查詢 (DD_3 在此踩雷) |
| **Edge `[:INTERCHANGE]`** | 新命名 | 整合修飾 | DD_3 用 `INTERCHANGES_WITH` 太長,DD_1 用 `INTERCHANGE_TO`;最終取單字 `INTERCHANGE` |
| **`INTERCHANGE.travel_time_min`** | 預設 `5` | DD_1 / DD_2 共識 | NULL 會打死 Dijkstra,5 分鐘是合理 baseline (DD_3 漏設) |
| **`INTERCHANGE.transfer_note`** | DD_3 提案保留 | DD_3 | 除錯與 UI 顯示有用 (例如 "Central transfer") |
| **`Line` / `Network` 節點** | **不納入** 最終 schema | (DD_3 提案,移到 Part E) | 6 個 `query_` 不 traverse,KISS 原則先排除,未來可後補不影響相容 |
| **Constraint `station_id` unique** | 新增 | 整合補強 | 三家都沒寫,但配合 `MERGE` idempotent 必要 |
| **Index on `network`** | 新增 | 整合補強 | `query_interchange_path` 有 `WHERE start.network <> end.network`,可加速 |
| **Seed 用 `MERGE` 不是 `CREATE`** | DD_1 / DD_2 共識 | DD_1 / DD_2 | DD_3 用 `CREATE` 重跑會炸 unique;`MERGE` 才能 idempotent |

最終 schema 是「以 6 個 `query_` 合約為基準確保可實作 + 借用 DD_2 的統一模型架構 + 補上三家都沒做的 constraint/index 工程實踐 + 吸收 DD_3 提案的 `transfer_note` 細節」的混合體。

---

## Part E — 可選擴充 (來自 DD_3 的 `Line` / `Network` 模型)

> 6 個 `query_` 不需要這層,**最終版不納入**。但若日後出現以下需求,可以加上:
> - 「列出 M1 路線經過的所有車站,且依停靠順序」
> - 「找出 metro 與 rail 之間缺少的轉乘點」
> - 路線級的維運分析 (例如 M1 路線整段停駛影響哪些站)

```cypher
// 可選: 加入 Line 節點與 SERVES 邊
MERGE (l:Line {line_id: "M1"})
  SET l.name = "Metro Line 1", l.network = "metro";
MATCH (l:Line {line_id: "M1"}), (s:Station {station_id: "MS01"})
MERGE (l)-[:SERVES]->(s);

// 可選: 加入 Network 節點與 PART_OF 邊
MERGE (n:Network {type: "metro"}) SET n.name = "Metro";
MATCH (l:Line {line_id: "M1"}), (n:Network {type: "metro"})
MERGE (l)-[:PART_OF]->(n);
```

加上去後不會破壞既有 6 個 `query_` 的查詢結果 (它們從不 traverse 到 `Line` / `Network`),所以可以安全地後補。

---

## Part F — 給三位的回饋

### 給 Xan (DD_1 — 分離模型)

**強項:** 嚴格對應 JSON 來源,不發明額外抽象 — 兩個 station JSON 對映兩個 label,乾淨直觀。屬性表完整、雙向邊、INTERCHANGE 預設 5 分鐘三件「會打到實作」的細節都有顧到。在 Neo4j Browser 視覺化時,不同 label 自動上色,demo 與除錯時可讀性比 DD_2 高。

**待改進:** 對 6 個 `query_` 中跨網路查詢佔 4 個沒有預先盤點 — 分離 label 讓 `MATCH (s:MetroStation|NationalRailStation)` 寫起來繁瑣,且 APOC Dijkstra filter 要寫三段 `METRO_LINK>|RAIL_LINK>|INTERCHANGE_TO>`,容易拼錯。

**建議:** 設計 graph schema 時先讀過所有 `query_` docstring,分類出「同網路 vs 跨網路」查詢比例。當跨網路超過一半時,統一 label 通常更划算。**先看查詢再決定 schema,不要先正規化再硬塞查詢**。

---

### 給 陳楷 (DD_2 — 統一模型)

**強項:** 直接從 6 個 `query_` 的 Cypher 寫法反推 schema,Q1~Q4 每題的選擇都有附理由與不選的反例,設計品質最接近本案最終版。INTERCHANGE 邊預設 5 分鐘搭配「APOC Dijkstra 不容許 NULL」的工程約束說明清楚,後續維護者一看就懂為什麼是 5。

**待改進:** 沒有處理「Browser 視覺單色」的對策建議 (例如 `:style` grass file)。屬性表的 `is_interchange_*` 標為 ⭕ 可選,但實作 `query_interchange_path` 時會用到 — 應該分清楚「JSON 可選」與「查詢必填」的差異,後者建議在 seed 時補預設值 (`false`) 而不是留 NULL。

**建議:** 下次寫 schema 文件時,把每個屬性的「使用者」(seed 腳本 / 哪個 `query_` 函式 / Browser 顯示) 在屬性表多一欄列出,可選/必填的判斷會更精準。

---

### 給張恩家 (DD_3 — 三層模型)

**強項:** 唯一提出 `Line` / `Network` 抽象的人,這個方向對未來「路線級維運分析」(例如 M1 整線停駛影響哪些站) 很有價值,因此最終版把它收進 §Part E 「可選擴充」而非直接捨棄。`transfer_note` 屬性 ("Central transfer") 也是 DD_1/DD_2 都沒想到的好提案,最終版保留。

**待改進 (8 點 — 以 PR review 細項列出):**

| # | 問題 | 修正方式 |
|---|---|---|
| 1 | `CONNECTS_TO` 只建單向 | 每對相鄰站補建反向 `MERGE`,參考 §C.3 |
| 2 | `INTERCHANGES_WITH` 缺 `travel_time_min` | 補預設 `5`,參考 §B.2 與 §C.4 |
| 3 | `INTERCHANGES_WITH` 只建單向 | 同 (1),補反向 `MERGE` |
| 4 | 缺 Q1~Q4 設計決策章節 | 勾選定案 (Q1=B、Q2=A、Q3=A、Q4=A) 並補理由 |
| 5 | 屬性表缺「資料型別 / 是否必填 / 來源 JSON 欄位」3 欄 | 補齊 5 欄;定為 PK 的 `station_id` 標 unique |
| 6 | 用 `CREATE` 不是 `MERGE` | 改 `MERGE`,確保 `seed_neo4j.py` 重跑不會炸 unique |
| 7 | 邊 type 命名過長 | `INTERCHANGES_WITH` → `INTERCHANGE`,Cypher 寫起來短一截 |
| 8 | `Line` / `Network` 節點納入主 schema | 移到「可選擴充」(§Part E),最小可行 schema 先過,擴充再加 |

**建議:** 你的設計直覺很好 (抽象層次、`transfer_note`),但下一步要練習「用查詢驗證 schema」— 寫完 schema 後,把 6 個 `query_` 的 Cypher 各打一次,看哪些寫不出來、哪些跑了會炸,通常 (1)(2)(3) 這類方向/權重 bug 在 dry-run 時就能抓到。**設計之後跑一次模擬,比 review 時被退好**。

---

### 給整合者 (本檔的整合工作)

最終 schema 不需要強迫採用任何一份提案。圖形 schema 的整合原則:

1. **以查詢合約為基準確保可實作**:6 個 `query_` 是死的合約。schema 必須能跑出每一個查詢,沒商量。三家不齊全時 (例如 DD_3 漏 `travel_time_min`),直接從合約反推必要欄位。
2. **採用好的架構選擇**:DD_2 的統一 `Station` label、DD_1/DD_2 的雙向邊、DD_3 的 `transfer_note` 與 `Line` 抽象,都各有亮點。混合著用,不需二選一。
3. **加上三家都沒做的工程實踐**:`station_id` unique constraint、`network` index、`MERGE` 不是 `CREATE` — 這些是 idempotent seed 與查詢效能的基本盤,設計者常會忽略,整合者要補。
4. **可擴充但不過度**:`Line` / `Network` 節點對 6 個 `query_` 無增益 → 進「可選擴充」,給未來留路但不污染最小 schema。

**最終 schema 應是「以 6 個 query 合約為基準確保可實作 + 借用 DD_2 的統一架構 + 吸收 DD_3 的細節亮點 + 補上三家都沒做的工程約束」的混合體。**

---

## Part G — 後續任務 owner

| 檔案 | 動作 | Owner |
|---|---|---|
| `AI_SESSION_CONTEXT.md` | 將 Part B 的 schema 貼進 **Graph Schema** 區段 | (隨手 merge 的人) |
| `skeleton/seed_neo4j.py` | 依 §C.1~C.4 實作 seeder,讀 `metro_stations.json` + `national_rail_stations.json` | 陳楷 (graph schema owner) |
| `databases/graph/queries.py` | 依 §C.5 實作 6 個 `query_` 函式 | 陳楷 |
| `DD_3` (張恩家檔) | 依 §Part F 「給張恩家」8 點修正後重提 PR | 張恩家 |
| `seed_neo4j.py` 驗證 | 跑兩次測 idempotent,Cypher 對 row 數 (Station=30、CONNECTS_TO=60、INTERCHANGE=6) | Carol |

> 數字推導:metro JSON 已將每對相鄰邊從兩端各列一次 (42 entries = 21 pairs × 2 directions);rail 同理 (18 entries = 9 pairs × 2 directions)。逐筆 MERGE 後正好 60 條 directed edges,符合 §B.2「雙向各建一條」的要求。INTERCHANGE 為 3 對轉乘 × 雙向 = 6。
