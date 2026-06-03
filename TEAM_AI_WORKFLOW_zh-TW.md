🌐 [English Version](TEAM_AI_WORKFLOW.md)

# 團隊 AI 工作流程指南 — TransitFlow

三位學生使用任何 AI 編碼助手（Claude Code、GitHub Copilot、Cursor、Gemini Code Assist 等）協作 TransitFlow 的實用指南。

**在你寫任何一行程式碼之前先讀這份文件。**

---

## 目錄

- [Part 0：寫程式碼之前 — Schema 優先原則](#part-0寫程式碼之前--schema-優先原則)
- [Part 1：團隊與 AI 的協調](#part-1團隊與-ai-的協調)
- [Part 2：AI 整合工作流程循環](#part-2ai-整合工作流程循環)
- [Part 3：小型實作範例](#part-3小型實作範例)
- [Part 4：有效的提示詞](#part-4有效的提示詞)
- [附錄：工作階段前檢查清單](#附錄工作階段前檢查清單)

---

## Part 0：寫程式碼之前 — Schema 優先原則

> **關鍵：** `databases/relational/queries.py` 和 `databases/graph/queries.py` 中的每個查詢函式都對你的資料庫執行 SQL 或 Cypher。那些 SQL 引用的資料表名稱和欄位名稱是**你**設計的。如果一個人的 AI 產生 `SELECT * FROM stations`，另一個人的產生 `SELECT * FROM metro_stations`，什麼都無法一起運作。
>
> **規則：在任何人實作查詢函式之前，團隊先統一 `databases/relational/schema.sql`。**

### 步驟 0.1 — 一起進行 Schema 設計工作坊

團隊一起做一次，在分工之前。大約需要 90 分鐘。

**準備工作（每個人，會議前）：**
1. 閱讀 `train-mock-data/metro_stations.json` 和 `train-mock-data/bookings.json`
2. 閱讀 `databases/relational/queries.py` 中的 stub 函式簽名 — 函式名稱和 docstring 告訴你查詢需要回傳什麼資料
3. 瀏覽 `train-mock-data/national_rail_schedules.json`、`train-mock-data/registered_users.json`、`train-mock-data/payments.json`

**工作坊期間：**
1. 每個人問自己的 AI 助手：*「給定這些 JSON 資料 [貼上 10–20 行]，你會設計什麼 SQL 資料表？」*
2. 團隊比較三個 AI 的輸出 — 它們會不同
3. 一起討論並決定（AI 提出選項；人類做決定）
4. 將同意的 schema 寫入 `databases/relational/schema.sql`

具體走查請見 Part 3 的[範例 1](#範例-1schema-設計工作坊)。

### 步驟 0.2 — 提交並鎖定 Schema

團隊同意 schema 後，一個人提交它：

```bash
git checkout -b feature/schema-design
git add databases/relational/schema.sql
git commit -m "Add agreed relational schema - team reviewed"
```

開一個 Pull Request 並讓三位隊友都批准後再合併到 main。合併後，**不要在未告知整個團隊的情況下重新命名資料表或欄位** — 這會破壞其他人的查詢。

### 步驟 0.3 — 對圖形 Schema 做同樣的事

`databases/graph/queries.py` 中的圖形查詢（例如 `query_shortest_route`、`query_station_connections`）需要 Neo4j 節點/關係 schema。閱讀 `train-mock-data/metro_stations.json` 和 `train-mock-data/national_rail_stations.json`，在實作圖形查詢之前，團隊先決定節點標籤（`Station`、`MetroStation` 等）和關係類型（`CONNECTS_TO`、`INTERCHANGE` 等）。

---

## Part 1：團隊與 AI 的協調

### 1.1 — 誰負責什麼

以此作為起點。根據你的團隊調整。

| 領域 | 要實作的檔案 | 共享相依性 |
|---|---|---|
| 關聯式 schema | `databases/relational/schema.sql` | **整個團隊 — 一起同意** |
| 關聯式查詢 | `databases/relational/queries.py` | Schema 必須先確定 |
| 圖形 schema + 查詢 | `databases/graph/queries.py` | 來自關聯式 schema 的車站 ID |
| 匯入與測試 | `skeleton/seed_postgres.py`、`skeleton/seed_neo4j.py` | 兩個 schema |

**記錄你們的分工。** 在專案根目錄建立 `TEAM.md` 檔案：

```markdown
# 團隊分工

| 姓名  | 主要責任                          |
|-------|-------------------------------------------------|
| Alice | 關聯式 schema + 關聯式查詢函式  |
| Bob   | 圖形 schema + 圖形查詢函式            |
| Carol | 匯入腳本 + 整合測試           |
```

### 1.2 — Git 基礎（逐步說明）

如果你是 Git 新手，每次開始工作時遵循這個模式：

**一次性設定：**
```bash
# 複製共享儲存庫（做一次）
git clone <your-repo-url>
cd transitflow-demo
```

**每次開始工作階段時：**
```bash
# 1. 確保你有隊友的最新程式碼
git checkout main
git pull origin main

# 2. 為你即將做的事建立分支
git checkout -b feature/alice/metro-schedules-query
```

**工作中：**
```bash
# 經常儲存你的進度
git add databases/relational/queries.py
git commit -m "Implement query_metro_schedules - returns schedules by origin/destination"
```

**完成一個功能時：**
```bash
# 將你的分支推送到 GitHub
git push origin feature/alice/metro-schedules-query
# 然後在 GitHub 上開一個 Pull Request 並請隊友審查
```

**分支命名慣例：** `feature/<你的名字>/<你在做什麼>`

範例：
- `feature/alice/relational-schema`
- `feature/bob/graph-shortest-route`
- `feature/carol/seed-postgres`

### 1.3 — 共享 AI 上下文檔案

> **你能做的最有影響力的一件事來保持一致性。**

在儲存庫根目錄建立 `AI_SESSION_CONTEXT.md`（已提供範本 — 見 [AI_SESSION_CONTEXT.md](AI_SESSION_CONTEXT.md)）。每次有人開啟 AI 聊天工作階段時，他們**將此檔案的內容作為第一則訊息貼上**。

此檔案包含：
- 專案同意的編碼慣例
- 你們確定的 schema（一旦決定）
- 你們正在實作的函式簽名
- 你們團隊的決策日誌

AI 就會知道你的資料表名稱、欄位名稱、回傳類型和風格 — 並產生符合你程式碼庫的程式碼，而非發明自己的慣例。

**誰更新它：** 誰合併了 schema 變更或做了架構決策，就在同一個 commit 中更新 `AI_SESSION_CONTEXT.md`。把它當作活文件對待。

### 1.4 — 開始前的儀式

每次工作階段開啟 AI 助手前：

1. `git pull origin main` — 取得隊友最新合併的工作
2. 檢查 GitHub 上的 Pull Request — 有什麼等待你審查的嗎？
3. 告訴隊友（透過團隊聊天）你即將做什麼：*「今天在做 query_metro_schedules」*
4. 將 `AI_SESSION_CONTEXT.md` 貼到你的 AI 聊天作為第一則訊息

這花兩分鐘，卻能防止三個人讓 AI 用三種不同方式解決同一個問題。

### 1.5 — 為每個 Stub 同意完成定義

在實作任何 stub 函式之前，團隊回答這些問題：

- 它接收什麼輸入？（已記錄在 docstring 中）
- 它應該回傳什麼？（已記錄 — 看 `Returns:` 區段）
- 對於已知輸入，正確的輸出長什麼樣？

寫下來。例如，對於 `query_metro_schedules("MS01", "MS09")`：
- *「應回傳至少一個時刻表。每個 dict 必須有 `schedule_id`、`line`、`departure_time`、`stops_list` 鍵。」*

這是你的驗收標準。當你的 AI 產生程式碼時，在標記任務完成前用此標準測試它。

---

## Part 2：AI 整合工作流程循環

對於你實作的每個功能或函式，遵循這個五階段循環。永遠不要直接跳到實作。

```
分析與規劃 → 選項評估 → 最小實作 → 測試 → 合併
     ↑                                          |
     └──────────────────────────────────────────┘
                  （如果測試失敗或揭示新需求則回到開頭）
```

### 階段 1 — 分析與規劃

**你做什麼：** 在要求 AI 解決問題之前先理解問題。

1. 閱讀 stub 函式的 docstring — 它告訴你函式必須做什麼
2. 查看函式將查詢的模擬資料
3. 追蹤你需要哪些資料表（從你同意的 schema）

**AI 在此階段的角色：** 要求 AI *解釋*，而非產生程式碼。範例：

> *「我需要實作 `query_metro_schedules(origin_id, destination_id)`。它應回傳以正確順序服務兩個車站的時刻表。我的 schema 有一個 `metro_schedules` 資料表，欄位為：`schedule_id, line, direction, stops (JSONB array)`。你能解釋我會用什麼 SQL 方法來找到兩個車站 ID 都以正確順序出現在 stops 陣列中的時刻表嗎？」*

**人類決策點：** 你在繼續之前理解方法了嗎？如果沒有，要求 AI 進一步解釋 — 還不要要求它產生程式碼。

### 階段 2 — 選項評估

**你做什麼：** 要求 AI 提供 2–3 種方法並與隊友比較。

範例提示：

> *「給我兩種不同的 SQL 方法來找到 MS01 在 MS09 之前出現在 JSONB 車站 ID 陣列中的地鐵時刻表。展示取捨。」*

AI 可能提出：
- 選項 A：使用 `jsonb_array_elements` 搭配位置追蹤
- 選項 B：使用 `@>` 包含運算子 + 位置比較

與隊友比較。選擇符合你的 schema 和團隊 SQL 熟悉度的那個。在 `AI_SESSION_CONTEXT.md` 中記錄決策：
> *「地鐵時刻表停靠順序檢查：使用 jsonb_array_elements 方法（選項 A）— 更容易閱讀，更容易除錯」*

### 階段 3 — 最小實作

**你做什麼：** 一次實作一個函式。讓它運作後再進入下一個。

**產生程式碼前，準備你的提示：**
1. 貼上你的 `AI_SESSION_CONTEXT.md` 內容（如果還沒有的話）
2. 貼上確切的 stub 函式簽名和 docstring
3. 貼上 schema 中相關的資料表定義

範例提示結構（見 [Part 4](#part-4有效的提示詞) 的範本）：

> *[貼上 AI_SESSION_CONTEXT.md]*
>
> *現在實作這個函式。完全匹配簽名 — 不要變更參數名稱或回傳類型：*
> *[貼上 stub 函式]*
>
> *我的相關資料表 schema：*
> *[貼上 CREATE TABLE 語句]*

**使用前審查 AI 輸出：**
- 它使用你 schema 中的資料表名稱嗎？（不是發明的）
- 它匹配 docstring 中描述的回傳類型嗎？
- 它遵循 `example_query()` 中的 `_connect()` / `RealDictCursor` 模式嗎？

完整走查見 Part 3 的[範例 2](#範例-2實作關聯式查詢-stub)。

### 階段 4 — 測試

**你做什麼：** 手動執行函式並驗證它回傳你預期的結果。

你不需要正式的測試框架。開啟 Python shell：

```python
# 從專案根目錄，虛擬環境已啟動
python

>>> from databases.relational.queries import query_metro_schedules
>>> result = query_metro_schedules("MS01", "MS09")
>>> print(result)
>>> # 它回傳 list 嗎？每個項目有預期的鍵嗎？
>>> # 對於存在的路線，結果非空嗎？
```

**要檢查什麼：**
- 它回傳 list（不是 None，不是錯誤）嗎？
- 每個 dict 有 agent 預期的鍵嗎？
- 對於你知道存在的車站對，它回傳合理的結果嗎？
- 對於不存在的車站對，它回傳空 list（不是崩潰）嗎？

如果函式拋出錯誤，將錯誤和你的程式碼貼回 AI 聊天並要求它修復問題。

### 階段 5 — 合併

**你做什麼：** 讓隊友審查你的工作並合併。

1. 推送你的分支：`git push origin feature/alice/metro-schedules-query`
2. 在 GitHub 上開一個 Pull Request
3. 請隊友審查 — 見 Part 3 的[範例 4](#範例-4pr-審查與合併)
4. 處理任何回饋
5. 批准後合併
6. 如果任何架構決策改變了，更新 `AI_SESSION_CONTEXT.md`

**合併後更新 main 分支：**
```bash
git checkout main
git pull origin main
```

---

## Part 3：小型實作範例

### 範例 1：Schema 設計工作坊

**情境：** 你的團隊正在從模擬資料設計 `metro_stations` 資料表。

**步驟 1 — 查看模擬資料**（`train-mock-data/metro_stations.json`）：

```json
{
  "station_id": "MS01",
  "name": "Central Square",
  "lines": ["M1", "M2"],
  "is_interchange_metro": true,
  "interchange_metro_lines": ["M1", "M2"],
  "is_interchange_national_rail": true,
  "interchange_national_rail_station_id": "NR01",
  "adjacent_stations": [
    { "station_id": "MS05", "line": "M1", "travel_time_min": 3 },
    { "station_id": "MS02", "line": "M1", "travel_time_min": 3 }
  ]
}
```

**步驟 2 — 要求 AI 提出 schema：**

> *「這是我們地鐵車站資料的一個條目：[貼上上面的 JSON]。設計一個 PostgreSQL schema 來儲存這些資料。注意 `adjacent_stations` 代表圖形關係 — 我們有獨立的 Neo4j 資料庫處理那些，所以你不需要在 SQL 中儲存它們。專注於關聯式資料庫需要什麼。」*

**步驟 3 — AI 可能產生類似這樣的東西：**

```sql
CREATE TABLE metro_stations (
    station_id          VARCHAR(10) PRIMARY KEY,
    name                TEXT NOT NULL,
    is_interchange_metro         BOOLEAN DEFAULT FALSE,
    is_interchange_national_rail BOOLEAN DEFAULT FALSE,
    interchange_nr_station_id    VARCHAR(10) REFERENCES national_rail_stations(station_id)
);

CREATE TABLE metro_station_lines (
    station_id  VARCHAR(10) REFERENCES metro_stations(station_id),
    line        VARCHAR(5) NOT NULL,
    PRIMARY KEY (station_id, line)
);
```

**步驟 4 — 團隊討論問題：**
- 我們需要 `metro_station_lines` 作為獨立資料表，還是可以將 lines 儲存為簡單陣列？（提示：看看哪些查詢需要按路線篩選）
- `interchange_nr_station_id` 現在就應該是外鍵約束，還是等兩個資料表都存在後再加？
- `query_metro_schedules` 需要從這個資料表取得什麼？

**人類決策：** 團隊決定 — AI 提出選項。正規化選擇影響每個人的查詢函式，所以每個人都必須同意。

---

### 範例 2：實作關聯式查詢 Stub

**情境：** Alice 正在實作 `query_metro_schedules`。

**步驟 1 — Alice 閱讀 stub**（`databases/relational/queries.py`）：

```python
def query_metro_schedules(origin_id: str, destination_id: str) -> list[dict]:
    """
    Return metro schedules that serve both origin and destination in the correct order.

    Args:
        origin_id:       e.g. "MS01"
        destination_id:  e.g. "MS09"
    """
    raise NotImplementedError("TODO: implement after designing your schema")
```

**步驟 2 — Alice 準備她的提示：**

```
[先貼上 AI_SESSION_CONTEXT.md]

現在實作這個 Python 函式。規則：
- 使用 example_query() 中展示的 _connect() 輔助函式和 psycopg2.extras.RealDictCursor 模式
- 完全匹配 stub 的簽名 — 不要變更參數名稱或回傳類型
- 只使用下方 schema 中的資料表/欄位名稱

要實作的 Stub：
[貼上上面的 stub]

我的 schema（相關資料表）：
CREATE TABLE metro_schedules (
    schedule_id  VARCHAR(20) PRIMARY KEY,
    line         VARCHAR(5) NOT NULL,
    direction    VARCHAR(10),
    stops        JSONB NOT NULL   -- ordered list of station_ids, e.g. ["MS01","MS02","MS09"]
);
```

**步驟 3 — AI 產生程式碼。Alice 檢查：**
- 它使用模組中的 `_connect()` 嗎？✓ 或 ✗
- 它使用 `RealDictCursor` 嗎？✓ 或 ✗
- 它回傳 `list[dict]`，不是單一列嗎？✓ 或 ✗
- 它引用 `metro_schedules`（不是發明的資料表名稱）嗎？✓ 或 ✗

**步驟 4 — Alice 測試它：**

```python
python

>>> from databases.relational.queries import query_metro_schedules
>>> result = query_metro_schedules("MS01", "MS09")
>>> print(type(result))      # 應該是 <class 'list'>
>>> print(result)            # 應該顯示 schedule dicts
>>> print(result[0].keys())  # 檢查鍵名
```

---

### 範例 3：實作圖形查詢 Stub

**情境：** Bob 正在實作 `query_station_connections`。

**Stub**（`databases/graph/queries.py`）：

```python
def query_station_connections(station_id: str) -> list[dict]:
    """
    List all direct connections from a given station.

    Args:
        station_id: e.g. "MS01" or "NR01"
    """
    raise NotImplementedError("TODO: implement after designing your graph schema")
```

**Bob 的提示：**

```
[先貼上 AI_SESSION_CONTEXT.md]

實作這個 Neo4j 查詢函式。規則：
- 使用 example_count_nodes() 中展示的 _driver() 輔助函式和 session 模式
- 完全匹配 stub 的簽名
- 使用下方我們同意的圖形 schema 中的節點標籤和關係類型

要實作的 Stub：
[貼上上面的 stub]

我們的圖形 schema：
- 節點標籤：Station，屬性：{station_id, name, network}
- 關係：CONNECTS_TO，屬性：{line, travel_time_min}
```

**Bob 檢查 AI 輸出：**
- 它使用模組中的 `_driver()` 嗎？✓ 或 ✗
- 它使用 `with driver.session() as session:` 嗎？✓ 或 ✗
- Cypher 使用 `Station` 作為節點標籤（不是 `Node` 或 `stop`）嗎？✓ 或 ✗
- 它回傳 `list[dict]` 嗎？✓ 或 ✗

**Bob 測試它：**

```python
python

>>> from databases.graph.queries import query_station_connections
>>> result = query_station_connections("MS01")
>>> print(result)
>>> # MS01 (Central Square) 根據模擬資料連接到 MS05、MS02、MS06、MS07
>>> # 檢查你的結果是否匹配
```

---

### 範例 4：PR 審查與合併

**情境：** Alice 已推送 `feature/alice/metro-schedules-query` 並開了一個 PR。

**Bob 審查 PR。他檢查：**

1. 函式匹配 stub 的簽名嗎？（沒有額外或變更的參數）
2. 它使用同意的 schema 中的資料表/欄位名稱嗎？
3. 它遵循 `_connect()` / `RealDictCursor` 模式嗎？
4. 它處理空結果的情況（找不到時刻表）嗎？

**如果 Bob 發現問題**，他在 GitHub 上留下評論：
> *「第 45 行：你的查詢使用 `stations` 但我們的 schema 稱這個資料表為 `metro_stations`。另外回傳的 dict 缺少 `query_metro_fare` 預期的 `departure_time` 鍵。」*

**Alice 修復它**，推送新的 commit，並回覆評論。

**Bob 批准後**，Alice 合併 PR：
- 在 GitHub 上點擊「Merge Pull Request」
- 然後在本機：`git checkout main && git pull origin main`

---

### 範例 5：捕捉 AI 不一致

**情境：** Carol 要求她的 AI 實作 `query_national_rail_fare`。AI 產生：

```python
cur.execute("SELECT * FROM fares WHERE route_id = %s", (schedule_id,))
```

但同意的 schema 沒有 `fares` 資料表 — 票價是從 `national_rail_schedules.base_fare_usd` 和 `national_rail_schedules.per_stop_rate_usd` 計算的。

**如何捕捉：**
- 程式碼執行了，但回傳 `[]` 或拋出 `psycopg2.errors.UndefinedTable` 錯誤
- Carol 將 AI 輸出中的資料表名稱與她的 schema 比較 — 發現不匹配

**修復：** Carol 更新她的提示，貼上確切的 `CREATE TABLE` 語句並說：
> *「不要發明資料表或欄位名稱。只使用下方 schema 中出現的。」*

**教訓：** 始終將你的 schema 貼到 AI 提示中。如果你不給 AI 真實的名稱，它會編造聽起來合理的名稱。

---

## Part 4：有效的提示詞

這些是工具無關的範本。貼到任何 AI 助手中（Claude、Copilot、Cursor、Gemini 等）。

### 範本 A：Schema 設計

```
我是一個正在做資料庫專案的學生。這是我們原始資料檔案 [檔名] 中的一個範例條目：

[貼上模擬資料中的 1–3 個 JSON 物件]

設計一個 PostgreSQL schema 來儲存這些資料。約束：
- 所有資料表和欄位名稱使用 snake_case
- ID 使用 VARCHAR（它們看起來像 "MS01"、"NR_SCH01"）
- 避免儲存圖形/網路關係（那些放在 Neo4j）
- 適當包含 PRIMARY KEY 和 NOT NULL
- 只顯示 CREATE TABLE 語句，不要解釋

注意：這個 schema 將與兩位隊友共享。在任何人撰寫查詢函式之前，
資料表名稱必須先同意。
```

### 範本 B：查詢函式實作

```
我正在為一個 PostgreSQL 資料庫專案實作 Python 函式。
嚴格遵循這些規則：
- 只使用下方 schema 中的資料表和欄位名稱 — 不要發明名稱
- 使用模組中已定義的 _connect() 輔助函式
- 使用 psycopg2.extras.RealDictCursor（這樣列會以 dict 回傳）
- 完全匹配 stub 簽名 — 不要變更參數名稱或回傳類型
- 找不到列時回傳空 list []（不是 None）
- 除非 docstring 明確要求錯誤處理，否則不要加 try/except

[在此貼上 AI_SESSION_CONTEXT.md]

要實作的 Stub：
[貼上帶有 docstring 的 stub 函式]

Schema（僅相關資料表）：
[貼上你的函式將查詢的 CREATE TABLE 語句]
```

### 範本 C：程式碼審查

```
根據下方的 stub 合約和 schema 審查這個 Python 資料庫函式。
檢查：
1. 它只使用 schema 中的資料表/欄位名稱嗎？
2. 它匹配 stub 的回傳類型和鍵名嗎？
3. 它遵循 _connect() / RealDictCursor 模式嗎？
4. 它優雅地處理空結果的情況嗎？
5. 有 SQL 注入風險嗎（所有使用者輸入都用 %s 參數化了嗎）？

只報告真正的問題 — 不要風格建議。

Stub（合約）：
[貼上原始 stub]

要審查的實作：
[貼上你的程式碼]

Schema：
[貼上相關 CREATE TABLE 語句]
```

### 範本 D：除錯

```
這個 Python 函式拋出了錯誤。幫我修復它。

錯誤：
[貼上完整的 traceback]

函式：
[貼上你的程式碼]

Schema：
[貼上相關 CREATE TABLE 語句]

我預期它做什麼：
[一句話]
```

### 範本 E：Seeder 函式實作（JSON → PostgreSQL）

> **使用時機：** 實作 `skeleton/seed_postgres.py` 中的 `seed_*` 函式時。每個函式負責讀取一份 JSON、整理成 row tuple、用 `insert_many()` 批次插入。這個範本內含的設計約束是從實際跑通整套 seeder 萃取出來的,直接遵循能避開常見的對欄位錯、保留字衝突、polymorphic 約束失敗等問題。

```
我正在實作 TransitFlow 的 PostgreSQL seeder 函式之一。
嚴格遵循這些規則:
- 只讀取下方 schema 列出的欄位 — 不要發明欄位名稱
- 一律用模組已提供的 insert_many(cur, table, columns, rows) 輔助函式
  (它已內建 ON CONFLICT DO NOTHING, 不要自己寫 INSERT)
- columns list 的順序必須與 row tuple 的元素順序一一對應
- 對 JSON 中可能不存在或為 null 的欄位用 .get() 取值, 不要用 [..]
- 完全匹配 stub 的函式簽名 — 函式名稱、參數一字不變
- 函式最後 print 一行 "  <table_name>: {n} rows" 方便驗證

[在此貼上 AI_SESSION_CONTEXT.md]

要實作的 Stub:
[貼上 seed_xxx() 函式骨架]

對應的 schema:
[貼上目標表的 CREATE TABLE 語句, 含所有 CHECK / FK / 索引]

來源 JSON 範例 (1-2 筆):
[貼上 train-mock-data/xxx.json 的前幾筆紀錄]

請依下方檢查清單處理特殊情況。每一條若不適用就跳過, 但不要省略思考。

(1) 巢狀結構: JSON 若有 list of list (例如 schedule.stops_in_order /
    seat_layout.coaches[].seats[]), 用雙層 for 攤平成 row 並填 stop_order /
    seat_id 等子表 PK。
(2) Parent + 子表: schedule 類資料先插 parent table, 再用 enumerate() 產
    stop_order 插子表; 子表的 schedule_id 必須先在 parent 存在 (FK)。
(3) 巢狀 dict 攤平: 若 schema 把 JSON 的巢狀 dict (例如 fare_classes.standard.base_fare_usd)
    攤平成多個 column, 函式內也要攤平, 不要保留 dict。
(4) SQL 保留字: 若 schema 把保留字改名 (例如 row→row_number, column→column_letter),
    columns list 用 schema 的新名, 但從 JSON 取值仍用原 key。
(5) Polymorphic / CHECK 約束: 若 schema 有衍生欄位 (例如 transaction_type),
    從另一個欄位推導 (例如 booking_id 前綴 BK→NR, MT→Metro),
    確保符合 CHECK 約束, 不要硬編 None。
(6) NULL FK / 自參照: 若欄位是自參照 FK (例如 day_pass_ref) 或 JSON 中該欄
    為 null, .get() 取出 None 即可, psycopg2 會正確轉 SQL NULL。
(7) Idempotent: 不要在函式內 commit 或 rollback (main() 已處理),
    也不要做 DELETE — 重跑時讓 ON CONFLICT 自動跳過。

實作完成後請對自己回答:
- columns list 的每個欄位都在 schema 裡嗎? (沒拼錯/沒發明)
- columns list 順序與 row tuple 順序完全一致嗎?
- 對 JSON 中可能 missing 的 key, 是否一律用 .get()?
- 是否處理了上述 7 點中所有適用的情況?
```

**驗證 (寫完後跑這幾條):**

```bash
# 第一次跑: 應看到每張表的 row 數
.venv/bin/python skeleton/seed_postgres.py

# 第二次跑: 所有表應顯示 0 rows (證明 ON CONFLICT 有效, idempotent)
.venv/bin/python skeleton/seed_postgres.py

# 進 DB 對 row 數
docker compose exec -T postgres psql -U transitflow -d transitflow \
    -c "SELECT 'metro_stations', COUNT(*) FROM metro_stations
        UNION ALL SELECT 'national_rail_seats', COUNT(*) FROM national_rail_seats
        ORDER BY 1;"
```

**常見錯誤對應:**

| 錯誤訊息 | 原因 | 解法 |
|---|---|---|
| `column "..." of relation "..." does not exist` | columns list 與 schema 不符 | 對照 schema.sql 校正欄位名 |
| `null value in column "..." violates not-null constraint` | JSON 該欄位缺失或為 null, 但 schema 設了 NOT NULL | schema 改可空,或在 seeder 提供預設值 |
| `insert or update ... violates foreign key constraint` | 子表先於 parent 插入, 或 station_id 不存在 | 確認 main() 的呼叫順序符合相依關係 |
| `new row ... violates check constraint "chk_..."` | 衍生欄位推導錯 (例如 transaction_type) | 對照 schema 的 CHECK 條件重推 |

### 範本 F：圖形資料庫 (Neo4j) Schema 設計

> **使用時機：** 為 `databases/graph/queries.py` 的 6 個 `query_` 函式設計 Neo4j schema 字典時。這個範本內建硬性約束 (只用 station JSON、必須支援所有 6 個查詢) 與 4 個必答的設計問題,確保產出的 schema 文件可以直接進入 PR review,而不只是天馬行空的腦力激盪。
>
> **產出檔案位置:** `train-mock-data/DATA_DICTIONARY_GRAPH/DATA_DICTIONARY_GRAPH_<n>.md` (團隊每位成員產一份, 工作坊時三份對照)。

```
================================================================
TASK: 設計 TransitFlow 圖形資料庫 (Neo4j) Schema
================================================================

我要為 TransitFlow 設計圖形資料庫的 schema 字典提案。
資料來源只用 metro_stations.json + national_rail_stations.json 兩個檔案。

【硬性約束】

1. 只能用兩個 station JSON 設計 schema, 不要把 schedules / bookings 等
   資料拉進 graph (那些是 PostgreSQL 的職責)。

2. Schema 必須能支援 databases/graph/queries.py 已定義的 6 個查詢函式:
   - query_shortest_route       (Dijkstra by travel_time_min)
   - query_cheapest_route       (Dijkstra by 票價)
   - query_alternative_routes   (繞過某站的其他路徑)
   - query_interchange_path     (跨網路 metro <-> NR 轉乘)
   - query_delay_ripple         (N hops 延誤連帶影響)
   - query_station_connections  (列出某站的所有直連)

3. 必須回答下面 4 個設計問題, 每題寫出選擇 + 理由:

   Q1: 節點標籤怎麼分?
       A. 兩個分離 label: MetroStation / NationalRailStation
       B. 統一 Station + property network
       C. 多 label 並用 Station:MetroStation

   Q2: 同網路相鄰邊用單一型還是分網路?
       A. 統一 [:CONNECTS_TO] + property 區分 network
       B. 分 [:METRO_LINK] / [:RAIL_LINK]

   Q3: 跨網路轉乘關係的方向?
       A. 雙向各建一條
       B. 單向 + 查詢時用無向

   Q4: INTERCHANGE 的 travel_time_min (JSON 沒提供) 怎麼處理?
       A. 預設 5 分鐘
       B. 留空 + 註記未來補充

4. 屬性表必須列出: 名稱 / 資料型別 / 是否必填 / 範例值 / 來源 JSON 欄位。

5. 結尾附 Cypher 雛形, 包含節點建立、同網路邊、跨網路邊三段。

【貼上的資料】

metro_stations.json 第一筆紀錄:
[貼入完整 JSON]

national_rail_stations.json 第一筆紀錄:
[貼入完整 JSON]

【統計參考】
- metro_stations: 20 個節點, 42 條相鄰邊
- national_rail_stations: 10 個節點, 18 條相鄰邊
- 跨網路轉乘車站對: 3 對

【輸出格式】

直接寫一份 markdown 到
/path/to/train-mock-data/DATA_DICTIONARY_GRAPH/DATA_DICTIONARY_GRAPH_<n>.md:

# TransitFlow 圖形資料庫 (Neo4j) Schema 設計

## 1. 節點設計 (Nodes)
[逐個 Label 列出 + 屬性表]

## 2. 關係設計 (Relationships)
[逐個 Type 列出 + 屬性表]

## 3. 設計決策
### Q1: 節點標籤
- 選擇: ...
- 理由: ...
### Q2 ~ Q4: ... (同上格式)

## 4. Cypher 雛形
```cypher
// 節點 / 同網路邊 / 跨網路邊 各一段
```
```

**用法 (團隊工作坊):**

1. 三位隊友各自帶這份範本去問自己的 AI, 各產一份 `DATA_DICTIONARY_GRAPH_1.md` / `_2.md` / `_3.md`。
2. 比較三份在 Q1–Q4 上的選擇差異 — 通常會分別出現分離模型 vs 統一模型 vs 多 label 折衷。
3. 看 6 個 `query_` 的 Cypher 雛形哪份寫起來最短、最不容易出錯,以此作為決策依據。
4. 團隊投票決定一份, 將最終決定的 schema 寫進 `AI_SESSION_CONTEXT.md` 的 **Graph Schema** 區段, 後續 `seed_neo4j.py` 與 `query_*` 都依此 schema 實作。

**驗證 (寫完後對自己回答):**

- [ ] 屬性表是否列齊「名稱 / 型別 / 必填 / 範例值 / 來源 JSON 欄位」5 欄?
- [ ] 6 個 `query_` 函式是否都能用提案的 schema 寫出來? (尤其 `query_interchange_path` 跨網路、`query_delay_ripple` 不分網路 N hops)
- [ ] Cypher 雛形的關係方向是否符合 Q3 的選擇? (雙向就要建兩條 `MERGE`)
- [ ] `INTERCHANGE` 邊有 `travel_time_min` 嗎? (NULL 會讓 Dijkstra 失準)
- [ ] 是否避免把 `adjacent_stations` 以外的資料 (例如 schedules / fares) 帶進 graph?

**常見偏離 (PR review 抓這幾點):**

| 症狀 | 原因 | 修正 |
|---|---|---|
| AI 在節點上加了 `schedules` 或 `bookings` 欄位 | 沒嚴守「只用兩個 station JSON」 | 把那些屬性砍掉, 留給 PostgreSQL |
| 跨網路邊只建單向, 但 Cypher 樣板用 `-[:INTERCHANGE]->` | Q3 選 A 卻只寫一條 `MERGE` | 補第二條 `MERGE` 或改 Q3 為 B |
| `INTERCHANGE` 沒有 `travel_time_min` | Q4 選了 B 但忘了 Dijkstra 不容許 NULL | 改回 A 給預設值 (例如 5) |
| 同時用 `MetroStation` label 又有 `network: "metro"` property | Q1 選 A 卻又抄 B 的屬性 | 二擇一,保持一致 |

### 範本 G:NLU 測資產生 (自然語言 → 工具呼叫對照表)

> **使用時機:** 想驗證「使用者輸入的自然語言 → agent 真的有觸發正確的 tool」整條鏈路是否運作時。
> 這份範本會請 AI 產一份結構化的測試集,每筆測試含「輸入字串 + 預期 tool 呼叫 + 預期回答要點」,
> 你拿這份清單去手動或自動跑 agent,逐筆比對輸出,就能精確指出哪一類自然語言路由錯了。
>
> **產出檔案位置:** `tests/agent_nlu/AGENT_NLU_TEST_CASES.md` (團隊共用一份, 任何人新增測例就 commit;搭配同資料夾的自動化腳本 `run_nlu_tests.py` 使用)。

```
================================================================
TASK: 為 TransitFlow agent 產生 NLU → Tool 路由測試集
================================================================

我要驗證 skeleton/agent.py 的 LLM 是否能把使用者自然語言輸入,
正確路由到對應的 tool 呼叫並產生合理回答。請產一份 markdown 測試集。

【可用的 tools (來自 skeleton/agent.py 的 TOOLS_SCHEMA, 不要發明新的)】

find_route(origin_id, destination_id, optimise_by?)
check_national_rail_availability(origin_id, destination_id, travel_date?)
get_national_rail_fare(schedule_id, fare_class, stops_travelled)
check_metro_availability(origin_id, destination_id)
calculate_metro_fare(schedule_id, stops_travelled)
get_metro_fare(origin_id, destination_id)
get_available_seats(schedule_id, travel_date, fare_class)
make_booking(schedule_id, origin_station_id, destination_station_id, travel_date, fare_class, seat_id, ticket_type?)
cancel_booking(booking_id)
get_user_bookings()
search_policy(query)
find_alternative_routes(origin_id, destination_id, avoid_station_id, network?)
get_delay_ripple(station_id, hops?)

【已知世界 (從 SYSTEM_PROMPT 摘錄)】
- Metro: MS01–MS20, 路線 M1–M4
- National Rail: NR01–NR10, 路線 NR1–NR2
- 跨網路轉乘: Central=MS01/NR01, Old Town=MS07/NR03, Ferndale=MS15/NR07
- 需登入的 tool: make_booking, cancel_booking, get_user_bookings (其餘不必)

【硬性要求】

1. 至少 24 筆測例, 平均涵蓋下面 9 大類, 每類 ≥ 2 筆 (登入相關類 ≥ 1):
   - Routing (find_route)
   - Availability (check_national_rail_availability / check_metro_availability)
   - Fare (get_metro_fare / calculate_metro_fare / get_national_rail_fare)
   - Booking flow (get_available_seats → make_booking)
   - Cancellation (cancel_booking)
   - User history (get_user_bookings)
   - Policy / refund / compensation (search_policy)
   - Disruption (find_alternative_routes / get_delay_ripple)
   - Out-of-scope / 灰色地帶 (例如「今天天氣?」應該回沒有 tool, 或登入前的 booking)

2. 中英文各占約一半 (zh-TW + en), 並包含至少 2 筆口語、不完整或代名詞句子
   (例如 "幫我看 NR01 到 NR05" / "cheapest one please" / "cancel the last one")

3. 每一筆必須有下列 8 欄, 一欄都不能少:

   id              T01, T02, ... 連號
   category        上面 9 類其中之一
   language        zh-TW 或 en
   requires_login  true 或 false (對應該觸發的 tool 是否需要登入)
   user_input      使用者實際打的字串 (一句話, 不要過度精緻)
   expected_tool_calls   list of {name, params}, 順序就是預期呼叫順序;
                         若不該呼叫任何 tool, 寫 []
   expected_answer_must_contain      list[str], 答案必須出現的關鍵字
   expected_answer_must_not_contain  list[str], 答案不該出現的反例
                                     (例如 RF005 45 分鐘延遲就不該出現
                                      "no compensation" / "0% refund")

4. 至少 3 筆鎖定已知 bug 的 regression case:
   (a) 延遲 30–59 分鐘 → 必須命中 RF005_R1 50% 退款 (search_policy)
   (b) travel_date 給字串 'null' → 仍應正確路由到 check_national_rail_availability
       (params 中 travel_date 為 null 或省略, 不要硬把 'null' 當日期)
   (c) 未登入時要求訂票 → expected_tool_calls 為 [] 或不含 make_booking;
       answer_must_contain 包含「登入」/ "log in"

5. 不要在 expected_tool_calls 內塞 schedule_id 等需要先查才能拿到的值;
   若一個輸入是兩步驟流程 (例如先 availability 再 fare), 兩個 tool 都列,
   後一個的 schedule_id 寫成 "<from_previous_result>" 標記就好。

【輸出格式】

直接寫一份 markdown 到
/path/to/tests/agent_nlu/AGENT_NLU_TEST_CASES.md, 結構如下:

# TransitFlow Agent — NLU 測資集

## 摘要
- 測例總數: N
- 中文 / 英文比例: ...
- 類別分布: ...
- 已知 bug regression: T0X, T0Y, T0Z

## 測試矩陣

每筆用以下 markdown 區塊呈現 (不要塞進 table, 欄位太多會難讀):

### T01 · <category> · <language>

- requires_login: ...
- user_input:
  > <一行 user 輸入>
- expected_tool_calls:
  ```json
  [
    {"name": "...", "params": {...}}
  ]
  ```
- expected_answer_must_contain: [...]
- expected_answer_must_not_contain: [...]
- notes (選填): 一句話說明這筆在抓什麼陷阱
```

**用法 (手動 / 自動跑):**

1. 把這份範本貼給 AI, 產生 `tests/agent_nlu/AGENT_NLU_TEST_CASES.md`。
2. 對每一筆 `user_input`, 用 `python tests/agent_nlu/run_nlu_tests.py` 自動跑 (或手動進 `python -m skeleton.ui` 餵進去)。
3. 對照 `expected_tool_calls` 與 agent 真實呼叫的 tool 清單, 不一致就是路由錯。
4. 對照 `expected_answer_must_contain` / `must_not_contain` 過答案文字, 抓回退、誤導、漏資訊。
5. Regression case 失敗時直接到對應的 `databases/` 或 `skeleton/agent.py` 修, 不要改測例放水。

**驗證 (寫完後對自己回答):**

- [ ] 9 大類每類都 ≥ 2 筆, 登入類 ≥ 1?
- [ ] 中英文比例接近 1:1?
- [ ] 每筆 8 欄都齊?
- [ ] expected_tool_calls 只引用 TOOLS_SCHEMA 裡實際存在的 tool name?
- [ ] 至少 3 筆 regression (45min 延遲 / 'null' 字串 / 未登入訂票) 都有?
- [ ] 兩步驟流程的後段 schedule_id 標 "<from_previous_result>", 沒硬寫假值?

### 如何分享有效的提示詞

當你找到一個產生好輸出的提示詞時，將它加到 `AI_SESSION_CONTEXT.md` 的**提示詞日誌**區段。你的隊友可以重用它，而不用花時間寫自己的。

---

## 附錄：工作階段前檢查清單

每次 AI 輔助工作階段前執行這個清單。

```
[ ] git checkout main && git pull origin main
[ ] 檢查 GitHub 上的 Pull Request — 有什麼需要你審查的嗎？
[ ] 確認 Docker 容器正在執行：docker compose ps
    （應顯示 postgres、neo4j、pgadmin 為 "Up"）
[ ] 確認你的虛擬環境已啟動：python -c "import psycopg2; print('ok')"
[ ] 開啟 AI_SESSION_CONTEXT.md 並將其內容貼到你的 AI 聊天中
[ ] 告訴隊友你即將做什麼
```

如果 Docker 未執行：從專案根目錄執行 `docker compose up -d`。

如果你的 venv 遺失：見 README.md 的 [Python 虛擬環境](README.md#python-virtual-environments) 區段。

---

## 快速參考

| 問題 | 去哪裡看 |
|---|---|
| 我需要實作什麼函式？ | `databases/relational/queries.py`、`databases/graph/queries.py` — 閱讀 stub 和 docstring |
| 我有什麼資料可以用？ | `train-mock-data/` — 每個實體的 JSON 檔案 |
| Agent 用什麼參數呼叫我的函式？ | `skeleton/agent.py` — `TOOLS` 清單顯示確切參數 |
| 我在哪裡設計 schema？ | `databases/relational/schema.sql` — 目前為空，你來填寫 |
| 開始時我貼什麼到 AI？ | `AI_SESSION_CONTEXT.md` — 共享上下文檔案 |
| 通用團隊實踐和檢查清單 | `TEAM_PROJECT_GUIDE.md` |
