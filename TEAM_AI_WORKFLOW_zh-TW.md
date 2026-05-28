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
