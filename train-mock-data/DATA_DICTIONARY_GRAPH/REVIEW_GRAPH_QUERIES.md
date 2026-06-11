# Code Review — `databases/graph/queries.py`

> **分支:** `feat/neo4j-queries` (commit `a2db799`)
> **Reviewer:** adawang
> **驗證方式:** 對 seed 過的真實 Neo4j 資料 (Station=30、CONNECTS_TO=60、INTERCHANGE=6) 跑 10 個 smoke test
> **總體結論:** 整體結構與 `DATA_DICTIONARY_GRAPH_FINAL.md §C.5` 對齊,**6 個函式都有實作**。但 1 個會 100% 崩潰、3 個有規格偏離、3 個小細節可以更好。修完上面 4 個就能 ship。

---

## ✅ 做得好的地方

先說亮點,再給回饋:

1. **Driver/session 模式正確** — 每個函式都用 `with _driver() as driver, driver.session() as session`,沒有 leak connection。
2. **邊界情況優雅處理** — 找不到 station / 找不到 path 時回傳 `{"found": False}` 而非丟 exception,Agent 端用起來安全。
3. **`query_cheapest_route` 用 `shortestPath()` 取代 Dijkstra by fare 是好決策** — fare 不在邊上,改成「最少站數 ≈ 最便宜」是合理 fallback,而且註解寫得清楚。
4. **`query_delay_ripple` 用 f-string 注入 `hops` 並附安全註解** — 點明「Cypher 變長路徑不能參數化」,有安全意識。
5. **`query_interchange_path` 的 same-network 過濾** — `WHERE start.network <> end.network` 直接讓同網路呼叫回 `{"found": False}`,語意正確。

---

## 🔴 Critical — 一定要修 (函式無法使用)

### Bug #1 `query_cheapest_route` — `NameError: 'start_id'`

**位置:** `queries.py` 第 79 行

```python
def query_cheapest_route(origin_id: str, destination_id: str, ...):
    ...
    approx_fare = 2.50 + (stops * 1.50) if start_id.startswith("NR") else 0.80 + (stops * 0.30)
                                            ^^^^^^^^
                                            未定義 — 參數叫 origin_id
```

**現象:** 任何呼叫都立刻 `NameError: name 'start_id' is not defined`,函式 100% 不可用。

**修法:**
```python
approx_fare = 2.50 + (stops * 1.50) if origin_id.startswith("NR") else 0.80 + (stops * 0.30)
```

**Smoke test 證據:**
```
❌ query_cheapest_route('MS01','MS09')   NameError: 'start_id'
❌ query_cheapest_route('NR01','NR05')   NameError: 'start_id'
```

---

## 🟡 規格偏離 (Agent 拿到的回傳鍵跟 docstring 不一致)

### Issue #2 `query_cheapest_route` 回傳鍵與 docstring 不符

**Docstring 說:**
```python
Returns:
    dict with found, total_fare_usd (approximate), stations, legs
```

**實作回傳:**
```python
{
    "found": True,
    "total_fare_usd_approx": ...,   # ← 應為 total_fare_usd
    "stops": ...,                    # ← docstring 沒這個鍵
    "stations": ...
    # ← 缺 legs (在 query_shortest_route 也缺,可能整體未實作 legs 概念)
}
```

**建議:** 統一鍵名為 `total_fare_usd`(去掉 `_approx`),或更新 docstring 把契約寫成 `total_fare_usd_approx`。兩種都行,但要對齊。

也建議補上 `origin_id` / `destination_id`,跟 `query_shortest_route` 對稱:
```python
return {
    "found": True,
    "origin_id": origin_id,
    "destination_id": destination_id,
    "total_fare_usd": round(approx_fare, 2),
    "stops": stops,
    "stations": stations,
}
```

### Issue #3 `query_delay_ripple` 缺 `hops_away`、鍵名不一致

**Docstring 說:**
```python
Returns:
    List of dicts: {station_id, name, hops_away, lines_affected}
```

**實作回傳:**
```python
{"station_id": ..., "name": ..., "lines": [...]}
# ← 缺 hops_away,lines 應為 lines_affected
```

**為什麼重要:** Agent (或 Agent 對應的 LLM tool description) 預期看到 `hops_away` 就能回答「離出事站幾跳」。沒這個欄位的話,Agent 只能說「這幾站可能受影響」,失去距離感。

**修法:** 在 Cypher 用 `length(path)` 或變長路徑搭 `apoc.path.subgraphAll` 取每個點的距離。
最簡單的版本:
```cypher
MATCH path = (s:Station {station_id: $delayed_id})-[:CONNECTS_TO|INTERCHANGE*1..%d]-(affected:Station)
WHERE affected.station_id <> $delayed_id
WITH affected, min(length(path)) AS hops_away
RETURN affected.station_id AS station_id,
       affected.name       AS name,
       hops_away,
       affected.lines      AS lines_affected
ORDER BY hops_away, station_id
""" % hops
```
注意 `min(length(path))` — 同一站可能透過多條路徑被找到,取最短跳數。

### Issue #4 `query_interchange_path` 的 `interchange_points` 過濾太鬆

**現在的 Cypher:**
```cypher
[n IN nodes(path) WHERE n.is_interchange_metro = true
                    AND n.is_interchange_national_rail = true | n.station_id]
```

**問題:** 這條件框出「這個 station 同時被標為兩種網路的轉乘點」,但實際 `interchange points` 應該是「路徑上**真的跨網路**的那兩端」 — 也就是 `:INTERCHANGE` 邊的兩端。

**Smoke test 證據 — 結果不正確:**
```
query_interchange_path('MS03','NR05')
  path: MS03 → MS02 → MS01 → MS07 → NR03 → NR04 → NR05
  interchange_points: ['MS01']      ← 但實際跨網路發生在 MS07 ↔ NR03
```
MS01 雖然旗標為 `is_interchange_metro=true AND is_interchange_national_rail=true`,但這條路徑根本沒走 MS01↔NR01 的 INTERCHANGE 邊。

**修法 — 改用邊型別過濾:**
```cypher
[i IN range(0, length(path)-1)
 WHERE type(relationships(path)[i]) = 'INTERCHANGE'
 | [nodes(path)[i].station_id, nodes(path)[i+1].station_id]] AS interchange_pairs
```
或更簡單 — 看路徑上 `:INTERCHANGE` 邊兩端:
```cypher
[r IN relationships(path) WHERE type(r) = 'INTERCHANGE'
 | startNode(r).station_id + '<->' + endNode(r).station_id] AS interchange_points
```

---

## 🟢 細節改善 (不阻擋運作,但建議跟著修一起 PR)

### Suggestion #5 `query_alternative_routes` 回空 list 時可加備註

**現象:** `query_alternative_routes('NR01','NR05','NR03')` 回傳 `[]`。
**原因:** 國鐵 NR1 線是線型 (NR01-NR02-NR03-NR04-NR05),要從 NR01 到 NR05 必經 NR03,沒有替代路徑。**邏輯正確**,但 Agent 收到空 list 可能誤以為 query 壞掉。

**建議改回 `dict` 包進詳細資訊** (但這會改 stub 簽名,要先跟團隊討論):
```python
return {
    "found": len(routes) > 0,
    "routes": routes,
    "note": "no alternative path avoiding ..." if not routes else None,
}
```
若不想改簽名,**至少在 docstring 加一段「empty list = no alternative exists, not an error」** 提醒呼叫端。

### Suggestion #6 `query_station_connections` 的 `line` 對 INTERCHANGE 是 `None`

**Smoke test 結果:**
```
{'station_id': 'NR01', 'rel_type': 'INTERCHANGE', 'line': None, 'travel_time_min': 5}
```

**為什麼是 None:** INTERCHANGE 邊沒有 `line` property (合理,跨網路沒線路概念)。

**建議:** 用 `coalesce` 補一個易讀標籤:
```cypher
RETURN ..., coalesce(r.line, 'transfer') AS line, ...
```
或在 Python 層整理:
```python
return [
    {**r.data(), "line": r.data().get("line") or "transfer"}
    for r in results
]
```

### Suggestion #7 `query_alternative_routes` 的 hops 上限 15 對小圖過大

**現在:** `*..15` — 30 個節點的圖,15 跳幾乎能繞遍全圖,容易找到「繞遠路也算替代路徑」的長路徑。

**建議:** 改成 `*..10` 或更貼近實際使用的 8。同時建議在排序後 dedupe 路徑(用節點集合判)以免回 3 條幾乎相同的路徑。

---

## ⚪ Style / Housekeeping

### Item #8 模組頂部的 docstring 被砍光

**Before (`feat/graph-seeder` 上的版本):**
```python
"""
TransitFlow — Neo4j Graph Database Layer
=========================================
GRAPH ROLE:
  - Model the dual transit network (city metro M1–M4 + national rail NR1–NR2)
  - Find fastest routes (Dijkstra by travel_time_min via APOC)
  - ...
"""
```

**After (現在的版本):**
```python
"""
TransitFlow — Neo4j Graph Database Layer
=========================================
This module handles all queries to Neo4j.
"""
```

**建議:** 把 GRAPH ROLE 那段加回去,或改成「對應 6 個 query 的一句話 summary」清單。新人讀檔需要這層 high-level 介紹。

### Item #9 `Optional` 進來沒用到

```python
from typing import Optional   # ← 沒有任何函式用到
```
**修法:** 直接刪這一行,或留著但用在某處 (例如 `query_alternative_routes(... avoid_station_id: Optional[str] = None)`)。

### Item #10 `query_alternative_routes` return type vs docstring 不一致

```python
def query_alternative_routes(...) -> list[list[dict]]:
    """Returns: List of routes, each route is a list of leg dicts"""
```

**實作:** 每個 route 是 list of **station dicts** (`{station_id, name}`),不是 leg dicts (應有 `from`, `to`, `line`, `travel_time_min` 之類)。

**建議二擇一:**
- 若維持目前實作:把 docstring 改成 "list of station dicts"
- 若要產 legs:在 Cypher 裡 unwind `relationships(path)`,每個 leg 包含 `from_station_id` / `to_station_id` / `line` / `travel_time_min`

對 Agent 而言,**legs 比 stations 更實用** (告訴使用者「在 X 站搭 M1 線,3 分鐘到 Y 站」),建議走 legs 路線。

---

## 📋 Smoke Test 總表 (對應上面每個 issue)

| # | Test Case | Result | 對應 Issue |
|---|---|---|---|
| 1 | `query_shortest_route('MS01','MS09')` | ✅ 11 min, 5 站 | — |
| 2 | `query_shortest_route('NR01','NR05')` | ✅ 47 min, 6 站 | — |
| 3 | `query_cheapest_route('MS01','MS09')` | ❌ NameError | #1 |
| 4 | `query_cheapest_route('NR01','NR05')` | ❌ NameError | #1 |
| 5 | `query_alternative_routes(NR01→NR05 avoid NR03)` | ✅ `[]` | #5 (邏輯正確,可加 note) |
| 6 | `query_interchange_path('MS03','NR05')` | ✅ 但 interchange_points 不正確 | #4 |
| 7 | `query_interchange_path('MS01','MS09')` | ✅ found=False | — |
| 8 | `query_delay_ripple('NR03', hops=2)` | ✅ 8 站,但缺 hops_away | #3 |
| 9 | `query_station_connections('MS01')` | ✅ 5 直連,但 line 對 INTERCHANGE 是 None | #6 |
| 10 | `query_shortest_route('XX99','MS09')` | ✅ found=False | — |

**8/10 通過 (沒丟 exception)**,但 issue #1 是 critical bug,issues #2~#4 是 contract 問題。

---

## 🎯 建議 PR 修法順序

優先級高→低:

1. **修 #1** — `start_id` → `origin_id` (1 行,5 秒)
2. **修 #2** — `query_cheapest_route` 回傳鍵對齊 docstring (3 行)
3. **修 #3** — `query_delay_ripple` 補 `hops_away` 與改名 `lines_affected` (改 Cypher,5 行)
4. **修 #4** — `query_interchange_path` 改用邊型別過濾 (改 Cypher,3 行)
5. **加 #5 docstring 註解** — 說明 empty list 含意
6. **修 #10 + #6 + #7 + #8 + #9** — style + 細節
7. **重跑 smoke test** 確認 10/10 通過

第 1~4 修完整個函式集就可以 merge。第 5~7 可以拆下一個 PR 處理。

---

## 💬 給 reviewer 自己的 note

整體骨架很好,沒踩到大坑 (driver 管理、empty result 處理、Cypher 安全)。最大問題是 #1 的 typo 沒在本機跑過就 push,**建議在 PR description 附 smoke test log** 證明每個函式都至少跑過一次成功。

`AI_SESSION_CONTEXT.md` 有同步更新嗎?如果這支 PR 改了 query 簽名/回傳結構,記得也更新 context 檔讓下次 AI session 有正確上下文。
