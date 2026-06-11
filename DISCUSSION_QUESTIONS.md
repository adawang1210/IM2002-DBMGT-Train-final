# 📚 TransitFlow 期末專案討論區 Q&A 總整理

這份文件彙整了課程討論區中，老師與助教對於專案實作細節、評分標準與系統架構的關鍵回覆。
最後一欄「本專案現狀」為對照記錄，由 Kiro 根據實際 codebase 審查填入。

---

## 🗄️ 一、 資料庫設計與架構 (Database Design)

### 1. 座位可用性：即時計算 vs. Occupancy Table
* **問題**：`available_seats` 應該每次 Query 時動態計算，還是建立 Occupancy Table 預先維護？
* **助教建議**：推薦採用 **動態計算 (Dynamic Calculation)** 搭配索引。
  * **原因**：目前資料規模與併發量不大，首要目標是「保持資料正確性與架構簡單性」。一開始就做反正規化 (Denormalization) 維護 occupancy table 成本太高，容易引發資料不一致的 Bug。未來若有效能瓶頸，再來考慮 Redis 暫存。
* **本專案現狀** ✅：`query_available_seats` 使用動態 SQL（`NOT IN` 子查詢即時計算已佔用座位），符合建議。

### 2. 資料刪除策略：軟刪除 vs. 去識別化 vs. 硬刪除
* **問題**：使用者刪除資料時該採取哪種策略？
* **助教建議**：只要 `delete propagation` 有做好，且商業邏輯一致即可。
  * **折衷方案**：交易/訂單紀錄建議採用「去識別化 (設為 null)」，會員帳號採用「軟刪除 (Soft delete)」。
* **本專案現狀** ✅：
  * `users.is_active BOOLEAN`：帳號軟刪除，停用不物理刪除。
  * `national_rail_bookings.status = 'cancelled'`：訂單狀態欄位取代硬刪除，保留稽核軌跡。
  * `schema.sql` 已加設計理由說明。

### 3. Primary Key 型態限制
* **問題**：PK 可以用 `VARCHAR` 嗎？還是只能限定 `UUID` 或 `SERIAL`？
* **助教建議**：強烈建議使用 **`UUID`** 或 **`SERIAL`**。
  * **原因**：VARCHAR PK 需全表掃描檢查唯一性，有效能副作用。
* **本專案現狀** ⚠️ 已文件化說明：
  * 業務實體 PK 均採 VARCHAR（e.g. "RU01", "NR_SCH01"），因為 mock data 本身即使用此格式，改用 UUID/SERIAL 需額外建立映射表，成本大於收益。
  * `schema.sql` 頂部已加「Primary Key 設計說明」欄位解釋此選擇及其取捨。
  * 唯一例外：`policy_documents` 使用 SERIAL（系統內部管理，無業務 ID 對應）。

### 4. Schema 限制與資料初始化 (Seeding)
* **問題**：`schema.sql` 標註了 "do not modify"，但文件要求 seeding 不能有重複資料，這樣不衝突嗎？
* **助教建議**：不衝突。「不重複」的邏輯應寫在 Seeding 的 Python 腳本裡，不是去改動 Vector Create Table 語法。
* **本專案現狀** ✅：`skeleton/seed_postgres.py` 的 `insert_many()` helper 全面使用 `INSERT ... ON CONFLICT DO NOTHING`，重複執行腳本不會產生重複資料。

---

## ⚙️ 二、 系統邏輯與 API 實作 (Implementation Details)

### 1. 訂單歷史紀錄 (Show my bookings) 的範圍
* **問題**：查詢歷史紀錄時，要包含捷運搭乘紀錄嗎？
* **助教建議**：**兩者都要**。`query_user_bookings` 必須回傳含 `"national_rail"` 與 `"metro"` 兩個 key 的 dict。
* **本專案現狀** ✅：`query_user_bookings` 固定回傳 `{"national_rail": [...], "metro": [...]}` 兩個 key，即使其中一個為空 list 也不會遺漏。

### 2. 訂票時缺乏 `departure_time` 參數
* **問題**：`make_booking` 沒有發車時間怎麼訂特定班次？
* **助教建議**：如果系統有完整時刻表，可以修改 `agent.py` 加入該參數，但需在文件中說明。
* **本專案現狀** ✅：`execute_booking` 在交易內部直接從 `national_rail_schedules.first_train_time` 取得 `departure_time`，不需使用者另外傳入，設計合理且簡潔。

### 3. 生日欄位 (年份 vs. 完整日期)
* **問題**：UI 只能存西元年，應該要改成存完整年月日嗎？
* **助教建議**：只存年是為了「減少收集敏感資料」，除非有新功能需求否則不建議費心去改。
* **本專案現狀** ✅：UI 只收西元年，存入時轉為 `YYYY-01-01` 格式，符合最小資料收集原則。

### 4. 轉乘時間設定
* **問題**：轉站需要設定固定轉乘時間嗎？
* **助教建議**：自行設定一個合理的轉站時間即可。
* **本專案現狀** ✅：`skeleton/seed_neo4j.py` 中 `INTERCHANGE_DEFAULT_MIN = 5`（5 分鐘），雙向建立 `[:INTERCHANGE]` 邊，APOC Dijkstra 可正常使用此邊權重。

---

## 🤖 三、 LLM Agent 與測試 (Agent & Testing)

### 1. 語意陷阱與 Tool Calling 錯誤
* **問題**："Old Town station (NR03)" 常被 LLM 誤解為 "Old Town (MS07)"。
* **助教建議**：不推薦過度優化 Prompt 來迎合範例題。應專注讓系統有合理的防呆與容錯，這類修改不納入計分。
* **本專案現狀** ✅：`_inject_station_ids()` 會把站名替換為 `"名稱 (ID)"` 格式，讓 LLM 直接讀到站號；同時有 deterministic fallback 規則在 LLM 選錯工具時自動糾正，不依賴 prompt 硬解。

### 2. 模型不穩定與評分方式
* **問題**：小模型不穩定，老師如何評分？
* **助教建議**：老師還會用後端腳本直接測試 `queries.py` 函式，底層 SQL 與邏輯寫對就不影響後端給分。
* **本專案現狀** ✅：所有 `query_*` / `execute_*` 函式均實作完整，可獨立測試，不依賴 LLM routing 正確與否。

---

## 🛠️ 四、 環境設置與團隊協作 (Environment)

### 1. Docker Neo4j Port 衝突 (Windows)
* **問題**：Windows 系統 7475、7688 ports 被保護無法使用。
* **助教建議**：建立 `.env` 檔案修改 Port，`.env` 已在 `.gitignore` 不會影響隊友。
* **本專案現狀** ✅：`.env` 已寫入 `.gitignore`，環境差異透過 `.env` 隔離，不會 push 到遠端。

---

## 🌟 五、 加分項評分標準 (Bonus Scoring)

### 1. Task 6 Bonus 的 "End-to-End" 定義
* **問題**：只有底層 API 沒有串 LLM，還能拿 Bonus 嗎？
* **助教建議**：完整 End-to-End (`UI → Agent → Tool Calling → DB → Agent & LLM → UI`) 才能完整計分，只有底層 API 依然有加分但分數打折。
* **本專案現狀** ✅：完整的 End-to-End 已實作，包含 Gradio UI、agent.py LLM routing、完整的 tool calling → DB 查詢 → LLM reply 鏈路。

---

## 📋 改善紀錄 (Kiro 審查後實施)

| 項目 | 狀態 | 說明 |
|---|---|---|
| `schema.sql` 頂部加 VARCHAR PK 設計說明 | ✅ 已完成 | 解釋為何使用 VARCHAR 而非 UUID/SERIAL |
| `password` 欄位從 VARCHAR(100) 改 VARCHAR(60) | ✅ 已完成 | bcrypt hash 固定 60 字元；加了設計理由說明 |
| `is_active` 旁加刪除策略說明 | ✅ 已完成 | 說明軟刪除 + 狀態欄取代硬刪除的設計理由 |
