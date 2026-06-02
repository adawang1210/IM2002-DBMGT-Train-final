# Xan
# 🚇 TransitFlow 圖形資料庫 (Neo4j) Schema 設計

> **資料來源**：`metro_stations.json` 與 `national_rail_stations.json`。

---

## 1. 節點設計 (Nodes)

將車站定義為圖形中的節點 (Nodes)，並利用標籤 (Labels) 區分系統。轉乘資訊將轉換為關係 (Edges)，不作為節點實體的屬性。

### 🔵 標籤 1：`MetroStation` (地鐵站)
* **來源**：`metro_stations.json`
* **屬性 (Properties)**：
  * `station_id` (String)：車站唯一識別碼，例如 `"MS01"`。
  * `name` (String)：車站名稱，例如 `"Central Square"`。
  * `lines` (List of Strings)：行經該站的路線陣列，例如 `["M1", "M2"]`。

### 🔴 標籤 2：`NationalRailStation` (國鐵站)
* **來源**：`national_rail_stations.json`
* **屬性 (Properties)**：
  * `station_id` (String)：車站唯一識別碼，例如 `"NR01"`。
  * `name` (String)：車站名稱，例如 `"Central Station"`。
  * `lines` (List of Strings)：行經該站的路線陣列，例如 `["NR1", "NR2"]`。

---

## 2. 關係設計 (Relationships / Edges)

關係具有方向性與屬性，`travel_time_min` 是最短路徑演算法（如 Dijkstra）計算權重的核心屬性。

### 🟢 關係 1：地鐵軌道 `[:METRO_LINK]`
* **方向**：`(MetroStation) ➡️ (MetroStation)`
* **資料來源**：由 `metro_stations.json` 的 `adjacent_stations` 陣列解析生成。
* **屬性 (Properties)**：
  * `line` (String)：行駛路線，例如 `"M1"`。
  * `travel_time_min` (Integer)：相鄰兩站間的行駛時間。

### 🟤 關係 2：國鐵軌道 `[:RAIL_LINK]`
* **方向**：`(NationalRailStation) ➡️ (NationalRailStation)`
* **資料來源**：由 `national_rail_stations.json` 的 `adjacent_stations` 陣列解析生成。
* **屬性 (Properties)**：
  * `line` (String)：行駛路線，例如 `"NR1"`。
  * `travel_time_min` (Integer)：相鄰兩站間的行駛時間。

### 🟣 關係 3：跨系統轉乘通道 `[:INTERCHANGE_TO]`
* **方向**：`(MetroStation) ↔️ (NationalRailStation)` （根據對應 ID 雙向建立）
* **資料來源**：透過判斷 `is_interchange_national_rail: true` 與 `interchange_metro_station_id` 等欄位，找到對應的跨系統車站 ID 進行連結。
* **屬性 (Properties)**：
  * `travel_time_min` (Integer)：跨系統轉乘的步行時間。*(註：原始資料未提供，實作寫入時建議給予預設值，例如 `5`)*。

---

## 3. Cypher 實作架構雛形參考

設計定案後，後續寫入資料庫的 Cypher 邏輯架構如下：

```cypher
// 1. 建立節點 (使用 MERGE 避免重複)
MERGE (m:MetroStation {station_id: "MS01"})
SET m.name = "Central Square", m.lines = ["M1", "M2"]

// 2. 建立同系統連線 (METRO_LINK / RAIL_LINK)
MATCH (a:MetroStation {station_id: "MS01"})
MATCH (b:MetroStation {station_id: "MS02"})
MERGE (a)-[r:METRO_LINK {line: "M1"}]->(b)
SET r.travel_time_min = 3

// 3. 建立跨系統轉乘連線 (INTERCHANGE_TO)
MATCH (m:MetroStation {station_id: "MS01"})
MATCH (nr:NationalRailStation {station_id: "NR01"})
MERGE (m)-[r1:INTERCHANGE_TO]->(nr)
MERGE (nr)-[r2:INTERCHANGE_TO]->(m)
SET r1.travel_time_min = 5, r2.travel_time_min = 5
```