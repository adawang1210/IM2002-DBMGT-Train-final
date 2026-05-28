# TransitFlow — 智慧鐵路助手

> **課程起始專案** — 你的任務是建構驅動這個 AI 助手的資料庫。
> AI 管線、網頁介面和資料庫連線已經接好並可正常運作。

---

## 目錄

1. [這個專案是什麼？](#這個專案是什麼) — TransitFlow 概述及你要建構的內容
2. [三個資料庫](#三個資料庫及為何需要各一個) — 為何分別使用 PostgreSQL、pgvector 和 Neo4j
3. [它實際上如何運作？](#它實際上如何運作完整管線) — 端到端管線走查與真實範例
4. [先決條件](#先決條件) — Docker、Python 和 LLM 需求
5. [安裝設定](#安裝設定僅需一次) — 一次性安裝與啟動步驟
6. [瀏覽資料庫](#瀏覽資料庫) — 登入 pgAdmin 和 Neo4j Browser 檢視資料
7. [團隊協作](#團隊協作) — 在隊友間保持資料庫狀態同步
8. [試試這些查詢](#試試這些查詢) — 驗證一切正常運作的範例問題
9. [專案結構](#專案結構) — 檔案與資料夾配置一覽
10. [真實世界 vs 教學結構](#本專案結構與真實正式環境的差異) — 本專案與正式程式碼庫的差異及原因
11. [databases/ 資料夾](#databases-資料夾即插即用元件) — 各模組中要編輯什麼及變更如何生效
12. [原始資料](#原始資料設計資料庫前先研究這些) — 設計 schema 前要研究的來源檔案
13. [你的任務](#你的任務) — 需要完成的四個課程任務
14. [進階 — 擴充 Agent 或 UI](#進階擴充-agent-或-ui) — 為 agent 新增工具或修改 UI
15. [切換 Ollama 和 Gemini](#切換-ollama-和-gemini) — 如何更換 LLM 提供者
16. [實用網址](#實用網址docker-運行時) — 本機服務位址快速參考
17. [疑難排解](#疑難排解) — 常見錯誤及修復方法
18. [Python 虛擬環境](#python-虛擬環境) — venv 是什麼、為何使用、如何設定

---

## 這個專案是什麼？

TransitFlow 是一個可運作的 AI 聊天助手，服務於一個虛構的雙網路交通營運商。你可以輸入以下問題：

- *「今天有沒有從中央車站（NR01）到 Ferndale（NR07）的列車？」*
- *「我的列車延誤了 45 分鐘 — 我可以獲得什麼補償？」*
- *「如果 MS05 關閉，從 MS01 到 MS09 最快的地鐵路線是什麼？」*

助手透過**查詢三種不同類型的資料庫**並將結果組合成有用的回覆來回答問題。你的任務是理解這些資料庫、研究原始資料、設計 schema、填充資料庫並擴充它們。

---

## 三個資料庫及為何需要各一個

本專案旨在展示*何時*該使用每種資料庫類型 — 以及*為何*單一類型不夠用。

| 資料庫 | 最擅長什麼 | 在 TransitFlow 中儲存什麼 |
|---|---|---|
| **PostgreSQL**（關聯式） | 具有精確關係的結構化記錄 — 數字、日期、外鍵 | 地鐵和國鐵車站、時刻表、座位配置、票價、使用者、國鐵訂票、地鐵行程、付款 |
| **PostgreSQL + pgvector**（向量） | 依*語意*而非精確字詞尋找文件 | 公司政策文件 — 退款規則、鐵路卡指南、無障礙資訊 |
| **Neo4j**（圖形） | 在網路中尋找路徑和連接 | 實體鐵路網路 — 車站為節點、鐵路連結為邊 |

**為什麼不能只用一個資料庫？** 沒有單一資料庫類型能做好所有事：

- SQL 很適合回答 *「07:00 NR1 班次（NR_SCH01）還有多少座位？」* 但處理 *「從倫敦到 Exeter 最快的路線是什麼，可在任何車站轉乘？」* 就很笨拙
- 圖形資料庫天生擅長路線搜尋 — 這正是它的設計目的 — 但它無法進行智慧文件搜尋所需的數學運算
- 向量資料庫即使使用者以意想不到的方式提問，也能找到正確的退款政策，透過*語意*而非關鍵字匹配。但它無法管理座位訂票

使用三個資料庫不是過度工程。而是為每項工作選擇正確的工具。

---

## 它實際上如何運作？完整管線

以下是從使用者發送訊息到看到回答的完整過程。我們將追蹤一個真實範例。

> **使用者輸入：** *「我搭乘 2026-04-02 從 Central（NR01）到 Stonehaven（NR05）的 07:00 列車，延誤了 45 分鐘。我可以獲得補償嗎？」*

---

### 步驟 1 — 問題到達網頁介面

使用者在 Gradio 聊天介面中輸入（程式碼位於 `skeleton/ui.py`）。訊息被傳遞給 agent。

---

### 步驟 2 — LLM 讀取問題並選擇要查詢哪些資料庫

`skeleton/agent.py` 將問題發送給 **LLM**（大型語言模型 — AI 大腦，可以是 Google Gemini 或本機 Ollama 模型）。LLM 會看到一份可用**工具**清單 — 把工具想像成標記好的按鈕，每個都連接到一個資料庫查詢函式。LLM 決定要按哪些按鈕。

對於這個問題，LLM 選擇：

```
工具 1: get_user_bookings()
工具 2: search_policy(query="compensation for delayed train 45 minutes")
```

這種技術 — 讓 LLM 選擇要呼叫哪些函式 — 稱為**工具使用**或**函式呼叫**。LLM 本身不查詢資料庫；它只是發出指令，然後由 Python 程式碼執行。

> **Ollama vs Gemini 工具路由：** 使用 Ollama 時，agent 使用模型的原生工具呼叫 API（`llm_provider.py` 中的 `ollama_tool_call`），比要求小模型產生 JSON 更可靠。使用 Gemini 時，agent 發送結構化 JSON 路由提示。兩種路徑產生相同的工具呼叫清單。

> **登入感知路由：** 如果使用者已登入，agent 會將其姓名、電子郵件和使用者 ID 注入系統提示。需要驗證的工具（`get_user_bookings`、`make_booking`、`cancel_booking`）自動使用登入身份 — LLM 永遠不需要詢問使用者的電子郵件或 ID。

---

### 步驟 3 — 工具查詢真實資料庫

每個工具對應到 `databases/relational/queries.py` 或 `databases/graph/queries.py` 中的 Python 函式：

**`get_user_bookings`** → 對 PostgreSQL 中的 `national_rail_bookings` 資料表執行 SQL

```sql
SELECT b.booking_id, b.travel_date, b.departure_time::text,
       b.amount_usd, b.status,
       orig.name AS origin_name, dest.name AS destination_name, ...
FROM national_rail_bookings b
JOIN national_rail_stations orig ON orig.station_id = b.origin_station_id
JOIN national_rail_stations dest ON dest.station_id = b.destination_station_id
WHERE b.user_id = 'RU01'
ORDER BY b.travel_date DESC
```

回傳原始 JSON：*`[{"booking_id": "BK001", "travel_date": "2026-04-02", ...}]`*

**`search_policy`** → 將問題轉換為向量，然後對 PostgreSQL（pgvector）中的 `policy_documents` 執行相似度搜尋

```sql
SELECT title, content,
       1 - (embedding <=> '[...query vector...]') AS similarity
FROM policy_documents
ORDER BY similarity DESC
LIMIT 3
```

回傳原始 JSON：*`[{"title": "Delay Compensation Policy", "content": "RF005: 30–59 minutes...", ...}]`*

---

### 步驟 4 — 原始結果被正規化為結構化可讀文字

每個工具的原始 JSON 通過一個 **Python 展平器**（`agent.py` 中的 `_normalise_result`），遞迴地將任何 JSON 結構轉換為縮排的鍵值文字。例如，Alice 的訂票結果變成：

```
[get_user_bookings]
national_rail:
  [1]
    booking_id: BK020
    travel_date: 2026-05-13
    origin_name: Bridgeport
    destination_name: Central Station
    fare_class: standard
    amount_usd: 4.00
    status: confirmed
  [2]
    booking_id: BK001
    ...
metro:
  [1]
    trip_id: MT009
    ...
```

這個正規化步驟就是為什麼**新增工具時不需要撰寫任何格式化程式碼** — 展平器自動處理任何 JSON 結構，無論巢狀深度或欄位名稱。它使用純 Python，不涉及 LLM，因此不存在模型幻覺、損壞或遺漏記錄的風險。

---

### 步驟 5 — LLM 撰寫最終回答

LLM 讀取正規化的資料摘要和原始問題，然後撰寫最終回覆：

> *「我可以看到您的訂票 BK001，2026 年 4 月 2 日 07:00 NR01 → NR05（$8.50）。根據延誤補償政策（RF005），30–59 分鐘的延誤可獲得票價 50% 的退款 — 即 $4.25。您可以在 28 天內透過應用程式的『我的行程 → 申請補償』提交申請，或聯繫客服。」*

---

### 步驟 6 — 顯示回答

回覆被傳回 `skeleton/ui.py` 並顯示在聊天視窗中。

---

### 管線摘要圖

```
使用者輸入問題
        │
        ▼
  skeleton/ui.py  (Gradio 網頁聊天 — 處理登入/註冊狀態)
        │  current_user_email 隨每則訊息傳遞
        ▼
  skeleton/agent.py  ◄──────────────────────── LLM (Gemini 或 Ollama)
        │                                               ▲  ▲  ▲
        │   [1] LLM 讀取問題 +                          │  │  │
        │       登入上下文，選擇工具 ───────────────────┘  │  │
        │   [2] Agent 對真實資料庫                         │  │
        │       執行工具                                   │  │
        │   [3] Python 展平器正規化 ────────────────────────┘  │
        │       原始 JSON 為可讀文字                            │
        │   [4] LLM 使用正規化資料 ─────────────────────────────┘
        │       撰寫最終回答
        │
        ├── databases/relational/queries.py ──► PostgreSQL (port 5433)
        │                                          ├── 關聯式資料表
        │                                          │     metro_stations, national_rail_stations,
        │                                          │     schedules, seat_layouts, users,
        │                                          │     national_rail_bookings, metro_travels
        │                                          └── 向量資料表
        │                                                policy_documents（依語意搜尋）
        │
        └── databases/graph/queries.py ─────► Neo4j (port 7688)
                                                 └── 圖形網路
                                                       MetroStation / NationalRailStation 節點,
                                                       METRO_LINK / RAIL_LINK / INTERCHANGE_TO 邊
                                                       （路線搜尋、延誤擴散）
```

---

### 什麼是 RAG？（政策搜尋如何運作）

政策文件搜尋使用一種稱為 **RAG — 檢索增強生成**的技術：

1. 資料庫匯入時，每份政策文件被轉換為一長串數字，稱為**向量嵌入**。這些數字以數學方式捕捉文字的*語意*。
2. 當使用者提出政策問題時，該問題也被轉換為向量 — 使用相同方法。
3. 資料庫找到向量與問題向量*最接近*（最相似）的政策文件。
4. 這些文件被交給 LLM，LLM 閱讀它們並用來回答問題。

關鍵好處：即使使用者的措辭與文件的措辭完全不同，它也能找到正確的政策，因為它匹配的是語意而非關鍵字。

---

## 先決條件

- **Git** — [git-scm.com/downloads](https://git-scm.com/downloads)
  > 用於複製儲存庫。大多數 macOS 和 Linux 系統已預裝。Windows 使用者需下載並執行 Git 安裝程式。
- **Docker Desktop** — [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)
  > Docker 讓你無需直接安裝 PostgreSQL 或 Neo4j 即可執行資料庫。把它想像成一個乾淨、獨立的容器，裝著資料庫伺服器。
  > **Windows 使用者：** Docker Desktop 需要 WSL2（Windows Subsystem for Linux 2）。如果尚未啟用，請參考 [Docker 的 WSL2 設定指南](https://docs.docker.com/desktop/wsl/)。
- **Python 3.10 或更新版本** — [python.org/downloads](https://www.python.org/downloads/)
  > 在 **Windows** 上，指令是 `python`。在 **macOS 和 Linux** 上，通常是 `python3`。本 README 中請使用適合你機器的版本。
- **LLM — 選擇一個：**
  - **Ollama**（推薦 — 完全在你的筆電上執行，不需要 API 金鑰）：[ollama.com/download](https://ollama.com/download)
  - **Gemini**（替代方案 — 回應更快，但需要免費 API 金鑰）：[aistudio.google.com](https://aistudio.google.com/app/apikey)

---

## 安裝設定（僅需一次）

> **建議：** 在 Python 虛擬環境中執行此專案。它將專案的套件與機器上的其他東西隔離，防止版本衝突。這不是必須的，但是良好實踐，也是大多數專業 Python 開發者使用的方法。請參閱本文件底部的 [Python 虛擬環境](#python-虛擬環境)了解完整說明。

### 1. 複製儲存庫、建立虛擬環境並安裝 Python 套件

```bash
git clone https://github.com/NCUIM-Lab710-Teaching/IM2002-DBMGT-Train-final transitflow
cd transitflow
```

**建議 — 先建立並啟動虛擬環境：**

**macOS / Linux：**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell)：**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

> **Windows PowerShell 注意：** 如果啟動失敗並顯示「running scripts is disabled on this system」，請在 PowerShell 中執行一次以下指令後重試：
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

當環境啟動時，你的終端提示會變為顯示 `(.venv)`。現在將專案套件安裝到其中：

```bash
pip install -r requirements.txt
```

> 如果你選擇不使用虛擬環境，直接執行 `pip install -r requirements.txt`。請注意這會將套件安裝到系統 Python 中，可能與其他專案產生衝突。

### 2. 建立環境檔案

```bash
cp .env.example .env
```

預設提供者是 **Ollama** — 不需要 API 金鑰。如果你想改用 Gemini，打開 `.env` 並設定 `LLM_PROVIDER=gemini`，然後貼上你的 `GEMINI_API_KEY`。

### 3. 啟動資料庫

```bash
docker compose up -d
```

這會在背景下載並啟動三個服務：
- **PostgreSQL** 在 port 5433 — 關聯式 + 向量資料庫
- **Neo4j** 在 port 7688 — 圖形資料庫
- **pgAdmin** 在 port 5051 — 瀏覽和查詢 PostgreSQL 的瀏覽器 UI

關聯式資料庫 schema（資料表和索引）在首次啟動時自動從 `databases/relational/schema.sql` 載入。種子資料在下一步驟中單獨載入。

> **首次執行時**，Docker 還必須下載資料庫映像檔（總計約 500 MB）。根據你的網路連線，這可能需要幾分鐘。後續啟動時，兩個容器在 15–30 秒內就緒。
>
> **較舊的 Docker 安裝：** 如果 `docker compose` 無法識別，試試 `docker-compose`（帶連字號）。建議更新 Docker Desktop 到最新版本。

等待兩個容器就緒：

```bash
docker compose ps
```

兩個容器的 Status 欄應顯示 `healthy`。

### 4. 匯入關聯式資料庫資料

> **你的任務：** 在執行此步驟之前，你需要實作 `skeleton/seed_postgres.py` 中的 seed 函式。連線設定和輔助函式已提供 — 你撰寫每個 `seed_*` 函式的主體。

實作完成後：

```bash
# macOS / Linux:
python3 skeleton/seed_postgres.py

# Windows (PowerShell):
python skeleton/seed_postgres.py
```

這會從 `train-mock-data/` 資料夾讀取所有模擬資料，並按相依順序插入 PostgreSQL：車站 → 時刻表 → 座位配置 → 使用者 → 訂票 → 行程 → 付款 → 回饋。它使用 `ON CONFLICT DO NOTHING`，因此可安全重複執行。

### 5. 拉取 Ollama 模型並載入政策文件嵌入

如果你使用 Ollama（預設），確保 Ollama 正在執行並先拉取所需模型 — 這只需做一次：

```bash
ollama pull llama3.2:1b        # ~1.3 GB  — 聊天模型
ollama pull nomic-embed-text   # ~274 MB  — pgvector 的嵌入模型
```

然後匯入向量資料庫：

```bash
# macOS / Linux:
python3 skeleton/seed_vectors.py

# Windows (PowerShell):
python skeleton/seed_vectors.py
```

這會直接從 `train-mock-data/` 中的 JSON 檔案（`refund_policy.json`、`ticket_types.json`、`booking_rules.json`、`travel_policies.json`）載入政策文件，使用 Ollama（`nomic-embed-text`）將每個條目轉換為向量嵌入，並將結果儲存在 PostgreSQL 中。

> 如果你使用 Gemini 而非 Ollama，在執行前先在 `.env` 中設定 `LLM_PROVIDER=gemini` 並加入你的 `GEMINI_API_KEY`。你不需要拉取 Ollama 模型。

### 6. 載入交通網路圖形

```bash
# macOS / Linux:
python3 skeleton/seed_neo4j.py

# Windows (PowerShell):
python skeleton/seed_neo4j.py
```

這會執行 `databases/graph/seed.cypher` 中的 Cypher 查詢，在 Neo4j 中建立所有車站節點和鐵路連結邊。該檔案中編碼的圖形拓撲源自 `train-mock-data/metro_stations.json` 和 `train-mock-data/national_rail_stations.json` — 如果需要擴充或修正圖形，請研究這些檔案。

### 7. 啟動助手

```bash
# macOS / Linux:
python3 skeleton/ui.py

# Windows (PowerShell):
python skeleton/ui.py
```

在瀏覽器中開啟 **http://localhost:7860**。TransitFlow 聊天介面應該會出現。

---

## 瀏覽資料庫

Docker 容器執行後，你可以直接在瀏覽器中檢視資料 — 對於驗證匯入是否成功以及開發時執行臨時查詢很有用。

### pgAdmin — PostgreSQL 瀏覽器

1. 在瀏覽器中開啟 **http://localhost:5051**。
2. 使用以下帳號登入：
   - **Email：** `admin@admin.com`
   - **密碼：** `admin`
3. 在左側邊欄，右鍵點擊 **Servers → Register → Server…**
4. 填寫兩個分頁：

   **General 分頁**
   - Name：`TransitFlow`（或任何你喜歡的標籤）

   **Connection 分頁**
   - Host：`postgres`
   - Port：`5432`
   - Maintenance database：`transitflow`
   - Username：`transitflow`
   - Password：`transitflow`
   - 勾選 **Save password**

5. 點擊 **Save**。伺服器出現在左側邊欄。
6. 展開 **Servers → TransitFlow → Databases → transitflow → Schemas → public → Tables** 瀏覽所有資料表。
7. 要執行 SQL 查詢，右鍵點擊 `transitflow` 資料庫並選擇 **Query Tool**。

> **為什麼這裡是 port 5432 而不是 5433？** pgAdmin 在 Docker 內部執行，透過內部 Docker 網路與 PostgreSQL 通訊，其中 Postgres 使用原生 port 5432。Port 5433 僅在從 Docker 外部連線時使用（例如從你的終端或本機 Python 腳本）。

---

### Neo4j Browser — 圖形視覺化工具

1. 在瀏覽器中開啟 **http://localhost:7475**。
2. 將連線 URL 設為 `bolt://localhost:7688`（Bolt port 從預設的 7687 重新映射）。
3. 使用以下帳號登入：
   - **Username：** `neo4j`
   - **密碼：** `transitflow`
4. 要視覺化整個鐵路網路，貼上此查詢並按 **Run (Ctrl+Enter)**：

   ```cypher
   MATCH (n)-[r]->(m) RETURN n, r, m
   ```

   點擊圖形中的任何節點或邊來檢視其屬性。

---

## 試試這些查詢

將以下內容貼到聊天中以確認一切正常運作：

```
What national rail trains run from Central (NR01) to Stonehaven (NR05)?
```
→ 測試 PostgreSQL 關聯式（`check_national_rail_availability` 對 `national_rail_schedules`）

```
What is the fastest metro route from MS01 to MS14?
```
→ 測試 Neo4j（透過地鐵圖形以 `travel_time_min` 進行 Dijkstra）

```
How do I get from Central Square (MS01) to Stonehaven (NR05)?
```
→ 測試 Neo4j 跨網路路由（METRO_LINK → INTERCHANGE_TO → RAIL_LINK）

```
If Old Town station (NR03) is closed, what alternative routes exist from NR01 to NR05?
```
→ 測試 Neo4j（替代路由，避開特定節點）

```
My train was delayed 45 minutes — what compensation am I entitled to?
```
→ 測試 pgvector RAG（延誤補償政策 RF005）

```
What is the company policy on travelling with a bicycle on national rail?
```
→ 測試 pgvector RAG（旅行政策文件 — 自行車、行李、寵物）

**需要驗證的查詢 — 先登入（使用右上角的 Register 或 Login 按鈕）：**

```
Show my bookings
```
→ 測試 `get_user_bookings` — 從 PostgreSQL 回傳你的訂票歷史（新註冊使用者為空）

```
Book me a standard ticket from Central Station (NR01) to Stonehaven (NR05) on 2026-06-01
```
→ 測試多步驟訂票流程：`check_national_rail_availability` → `get_available_seats` → `make_booking`

```
Cancel booking BK-XXXXXX
```
→ 測試 `cancel_booking` 及根據適用政策自動計算退款

在 UI 側邊欄啟用 **「Show database debug panel」** 可以看到確切呼叫了哪些工具、資料庫回傳了什麼、以及 LLM 如何正規化原始結果。

---

## 專案結構

```
transitflow/
├── docker-compose.yml                  # 啟動 PostgreSQL + Neo4j + pgAdmin
├── requirements.txt
├── .env.example                        # 複製為 .env 並填入你的 API 金鑰
│
├── train-mock-data/                    #   來源 JSON 檔案 — 設計 schema 前先研究
│   ├── metro_stations.json
│   ├── national_rail_stations.json
│   ├── metro_schedules.json
│   ├── national_rail_schedules.json
│   ├── registered_users.json
│   ├── bookings.json
│   ├── metro_travel_history.json
│   ├── payments.json
│   ├── feedback.json
│   └── ...                             #   （政策 JSON 檔案）
│
├── databases/                          # ← 你的工作區域
│   ├── relational/
│   │   ├── schema.sql                  # ← 編輯此檔：資料表定義（僅 DDL）
│   │   └── queries.py                  # ← 編輯此檔：新增 SQL 查詢函式
│   │
│   ├── graph/
│   │   ├── seed.cypher                 # ← 編輯此檔：圖形節點和關係
│   │   └── queries.py                  # ← 編輯此檔：新增 Cypher 查詢函式
│   │
│   └── vector/
│       └── documents.py                #   （已棄用 — 不再使用）
│
└── skeleton/                           # ← 請勿編輯（除非你知道自己在做什麼）
    ├── agent.py                        #   LLM 編排和工具路由
    ├── ui.py                           #   Gradio 網頁介面
    ├── llm_provider.py                 #   LLM 抽象層（Gemini / Ollama）
    ├── config.py                       #   環境設定（讀取 .env）
    ├── seed_postgres.py                #   將 train-mock-data/ JSON 檔案載入 PostgreSQL
    ├── seed_neo4j.py                   #   執行 databases/graph/seed.cypher
    └── seed_vectors.py                 #   將 train-mock-data/ 政策 JSON 嵌入 pgvector
```

---

## 本專案結構與真實正式環境的差異

本專案的資料夾配置是為了學習而刻意簡化的。理解它與真實程式碼庫的差異 — 以及原因 — 將幫助你理解兩個世界。

### 正式程式碼庫的樣子

在建構於三個資料庫之上的真實系統中，查詢程式碼會放在它所屬的功能旁邊，而非按資料庫類型分組。典型的 Python 服務可能如下：

```
transitflow/
├── api/                          # HTTP 層 — FastAPI 或 Django REST
│   ├── routes/
│   │   ├── bookings.py           # POST /bookings, GET /bookings/{id}
│   │   ├── routes.py             # GET /routes?from=LDN&to=BRS
│   │   └── policies.py          # GET /policies/search?q=...
│   └── middleware/
├── services/                     # 商業邏輯，此處無資料庫知識
│   ├── booking_service.py
│   ├── routing_service.py
│   └── policy_service.py
├── repositories/                 # 每個資料庫關注點一個檔案
│   ├── postgres/
│   │   ├── bookings_repo.py      # 訂票和使用者的 SQL
│   │   └── pricing_repo.py
│   ├── neo4j/
│   │   └── network_repo.py       # 路線搜尋的 Cypher
│   └── vector/
│       └── policy_repo.py        # pgvector 相似度搜尋
├── migrations/                   # 漸進式 schema 變更（Alembic / Flyway）
│   ├── 001_initial_schema.sql
│   ├── 002_add_loyalty_points.sql
│   └── 003_add_operators_table.sql
├── tests/
│   ├── unit/
│   └── integration/              # 測試對真實（測試）資料庫執行
├── infrastructure/               # Docker, Kubernetes, Terraform
└── config/
    ├── settings_dev.py
    ├── settings_staging.py
    └── settings_prod.py          # 密鑰從 Vault / AWS Secrets Manager 載入
```

與本專案的主要差異：

| 面向 | 本專案 | 正式實踐 |
|---|---|---|
| **Schema 變更** | 編輯 `schema.sql`，然後 `docker compose down -v` 清除並重建 | 遷移檔案 — 每次變更一個檔案，漸進式套用不遺失資料 |
| **查詢程式碼位置** | 按資料庫類型分組（`databases/relational/`、`databases/graph/`） | 按商業領域分組（`repositories/bookings/`、`repositories/routing/`） |
| **資料匯入** | 手動執行腳本 | 由 CI 管線或專用 seed/fixture 框架處理 |
| **設定** | 一個 `.env` 檔案 | 每個環境（dev/staging/prod）獨立設定；密鑰由 vault 管理，永不存在檔案中 |
| **網頁介面** | Gradio — 一個 Python 檔案，零前端程式碼 | 專用前端（React、Vue）與 REST 或 GraphQL API 通訊 |
| **Agent** | 單一 `agent.py` | 可能是獨立微服務或託管 AI 平台（如 AWS Bedrock、Google Vertex AI） |
| **LLM 提供者** | 透過環境變數切換 | 抽象在版本化 API 合約之後；模型升級經過分階段推出 |
| **測試** | 手動 — 執行應用程式並輸入查詢 | 自動化單元、整合和端到端測試在每次提交時於 CI 中執行 |

### 為什麼本專案使用較簡單的結構

本專案的目標是教你**何時以及為何**使用每種資料庫類型 — 而非教軟體架構。每個結構決策都是為了保持這個焦點：

- **`databases/` 按資料庫類型分組，而非按功能** — 因此每個資料夾是一個專注、獨立的學習單元。你可以在不觸碰圖形或向量程式碼的情況下處理關聯式資料庫。
- **一個 `schema.sql` 檔案而非遷移** — 遷移在正式環境中是正確的工具，但它們增加了一層間接性。單一檔案讓你一目了然地看到整個資料模型並整體推理。
- **`skeleton/` 包含所有預建程式碼** — 這個邊界是刻意的。它告訴你確切的責任範圍，讓你無需在開始處理資料庫之前理解 LLM 編排或 UI 程式碼。
- **Gradio 而非完整 API + 前端** — 正式 UI 需要數天設定。Gradio 用一個指令就能得到可運作的互動介面，讓焦點保持在資料庫上。
- **手動 seed 腳本而非遷移/fixture 框架** — 自己執行 `python skeleton/seed_vectors.py` 使匯入過程可見且可除錯。在正式環境中這會隱藏在部署管線中，更難從中學習。

當你離開這門課程並建構真實系統時，你自然會超越這些簡化。這裡的結構是教學鷹架 — 正因為它保持事物可見和分離而有用，即使這不是你向使用者交付系統時的組織方式。

我們也提供了三個資料庫的正式實踐附註 — 關聯式、向量和圖形資料庫。[在專案根目錄下找到它們]

- 關聯式資料庫：[SideNote1-RelationalDBPractices.md](https://github.com/NCUIM-Lab710-Teaching/IM2002-DBMGT-Train-v2/blob/master/SideNote1-RelationalDBPractices.md)
- 向量資料庫：[SideNote2-VectorDBPractices.md](https://github.com/NCUIM-Lab710-Teaching/IM2002-DBMGT-Train-v2/blob/master/SideNote2-VectorDBPractices.md)
- 圖形資料庫：[SideNote3-GraphDBPractices.md](https://github.com/NCUIM-Lab710-Teaching/IM2002-DBMGT-Train-v2/blob/master/SideNote3-GraphDBPractices.md)

---

## databases/ 資料夾：即插即用元件

`databases/` 內的每個子資料夾都是一個獨立元件。`skeleton/` 中的 AI 管線自動從它們匯入 — 你只需修改 `databases/` 內的檔案即可擴充助手的功能。

把每個資料庫資料夾想像成一個**即插即用模組**：

| 資料夾 | 你控制什麼 | 變更如何生效 |
|---|---|---|
| `databases/relational/` | SQL schema 和查詢函式 | 編輯 `schema.sql`，然後重置資料庫（見下方）。編輯 `queries.py` 新增 Python 查詢函式。 |
| `databases/graph/` | 圖形拓撲和 Cypher 查詢 | 編輯 `seed.cypher` 新增節點和邊（資料源自 `train-mock-data/` 車站 JSON）。編輯 `queries.py` 新增 Cypher 查詢函式。 |
| `databases/vector/` | 助手知道的政策文件 | 編輯 `train-mock-data/` 中的政策 JSON 檔案以新增或更新文件，然後重新執行 seed 腳本。 |

### 關聯式資料庫（PostgreSQL）

**要編輯的檔案：** `databases/relational/schema.sql`

此檔案定義所有資料表和索引（僅 DDL — 無資料）。先研究 `train-mock-data/` 中的 JSON 檔案以理解資料模型。種子資料由 `skeleton/seed_postgres.py` 單獨載入。

擴充想法：
- 新增 `delay_records` 資料表記錄營運商報告的每班次延誤
- 新增 `season_tickets` 資料表用於週票、月票和年票
- 新增 `platform_assignments` 資料表 — 每班次從哪個月台出發
- 在 `users` 資料表新增 `loyalty_points` 欄位
- 新增 `disruptions` 資料表用於計畫性工程

任何 schema 變更後，重置並重新載入資料庫：
```bash
docker compose down -v && docker compose up -d
```

**要編輯的檔案：** `databases/relational/queries.py`

在此新增 Python 函式，遵循現有模式。任何以 `query_` 為前綴的函式都可以在 agent 中註冊為工具（見下方進階章節）。

---

### 圖形資料庫（Neo4j）

**要編輯的檔案：** `databases/graph/seed.cypher`

此 Cypher 檔案建立所有 `MetroStation` 和 `NationalRailStation` 節點，加上 `METRO_LINK`、`RAIL_LINK` 和 `INTERCHANGE_TO` 邊。研究 `train-mock-data/metro_stations.json` 和 `train-mock-data/national_rail_stations.json` 以理解網路拓撲。

擴充想法：
- 新增 `BUS_LINK` 關係類型連接公車站到地鐵或鐵路車站
- 新增更多地鐵車站並延伸現有路線
- 為節點新增區域屬性（zone 1、2、3）用於區域票價計算
- 新增 `OPERATED_BY` 關係連結車站到營運商
- 為節點新增 `CLOSED` 屬性用於即時中斷模擬

編輯 Cypher seed 檔案後：
```bash
# macOS / Linux:
python3 skeleton/seed_neo4j.py

# Windows (PowerShell):
python skeleton/seed_neo4j.py
```

**要編輯的檔案：** `databases/graph/queries.py`

在此新增 Cypher 查詢函式，遵循現有模式。

---

### 向量資料庫（pgvector / RAG）

**要編輯的檔案：** `train-mock-data/` 中的政策 JSON 檔案（`refund_policy.json`、`ticket_types.json`、`booking_rules.json`、`travel_policies.json`）。

按照每個檔案中的現有結構新增條目。

擴充想法：
- 失物招領政策
- 團體訂票折扣（國鐵 10+ 名乘客）
- 無障礙和協助旅行
- 工程施工和計畫性中斷
- 罰款票價和逃票

新增或變更文件後：
```bash
# macOS / Linux:
python3 skeleton/seed_vectors.py

# Windows (PowerShell):
python skeleton/seed_vectors.py
```

> 如果你在匯入後切換提供者（Ollama ↔ Gemini），必須重新執行 seed 腳本。嵌入模型隨提供者改變 — 儲存的向量將不再與使用新模型的查詢匹配。

---

## 原始資料：設計資料庫前先研究這些

所有來源資料以結構化 JSON 檔案存放在 `train-mock-data/` 資料夾中。在開始 schema 或圖形設計任務前先研究這些檔案。

| 檔案 | 包含什麼 |
|---|---|
| `metro_stations.json` | 20 個地鐵車站（MS01–MS20）、路線、轉乘標記、相鄰車站清單 |
| `national_rail_stations.json` | 10 個國鐵車站（NR01–NR10）、路線、與地鐵的轉乘連結 |
| `metro_schedules.json` | M1–M4 線地鐵時刻表：停靠站、票價、班次頻率、營運日 |
| `national_rail_schedules.json` | NR1–NR2 國鐵時刻表：普通和快車服務、票價等級 |
| `national_rail_seat_layouts.json` | 每個國鐵班次的車廂和座位圖 |
| `registered_users.json` | 20 個虛構使用者，含個人資料和驗證欄位 |
| `bookings.json` | 所有使用者的國鐵訂票歷史 |
| `metro_travel_history.json` | 地鐵行程歷史（單程票和日票） |
| `payments.json` | 國鐵和地鐵交易的付款記錄 |
| `feedback.json` | 乘客評分和評論 |
| `refund_policy.json`、`ticket_types.json`、`booking_rules.json`、`travel_policies.json` | 嵌入 pgvector 用於 RAG 的政策文件。編輯這些檔案以擴充助手的知識，然後重新執行 `seed_vectors.py`。 |

**研究資料時問自己的問題：**

- 哪些欄位在許多記錄中重複？那些是獨立資料表的候選者。
- 什麼唯一識別每筆記錄 — 自然主鍵是什麼？
- 記錄之間如何關聯？那些關係成為外鍵。
- 哪些車站連接最好表示為*網路*而非一行行的資料表？
- 哪些政策內容需要依*語意*而非精確關鍵字搜尋？

---

## 你的任務

**必要 — 你必須編輯這些檔案以完成專案：**

| 檔案 | 要做什麼 |
|---|---|
| `skeleton/seed_postgres.py` | 實作每個 `seed_*` 函式以將 JSON 資料載入你的 PostgreSQL 資料表 |
| `skeleton/seed_neo4j.py` | 實作 `seed()` 函式以在 Neo4j 中建立車站節點和鐵路連結關係 |
| `databases/relational/schema.sql` | 設計並撰寫所有關聯式資料的資料表定義（DDL） |
| `databases/relational/queries.py` | 新增查詢你的 PostgreSQL 資料表的 Python 函式 |
| `databases/graph/seed.cypher` | 定義圖形拓撲 — 車站節點和它們之間的連結 |
| `databases/graph/queries.py` | 新增對 Neo4j 執行 Cypher 查詢的 Python 函式 |
| `train-mock-data/` 中的政策 JSON | 新增或擴充政策條目使助手能回答更多政策問題 |

**選擇性 — 編輯這些以新增擴充功能：**

| 檔案 | 你可以做什麼 |
|---|---|
| `skeleton/agent.py` | 將新的查詢函式註冊為工具使 AI 能呼叫它們 |
| `skeleton/ui.py` | 自訂聊天介面 — 版面、範例查詢、顯示選項 |

---

### 撰寫你的匯入腳本

有兩個匯入腳本留給你實作：

- `skeleton/seed_postgres.py` — 從 `train-mock-data/` 讀取 JSON 檔案並將列插入你的 PostgreSQL 資料表
- `skeleton/seed_neo4j.py` — 讀取車站 JSON 檔案並在 Neo4j 中建立節點和關係

連線設定、輔助函式和整體呼叫順序已就位。**你的工作是實作每個 `seed_*` 函式**，從載入的 JSON 中提取正確的欄位並撰寫插入邏輯。

---

#### PostgreSQL 匯入器（`seed_postgres.py`）

每個 `seed_*` 函式接收一個開啟的 cursor。使用 `insert_many` 輔助函式批量插入列。你傳入的欄位名稱必須與你的 `schema.sql` 資料表定義完全匹配。

**基本範例 — 插入扁平記錄：**

```python
def seed_metro_stations(cur):
    data = load("metro_stations.json")
    rows = [
        (s["station_id"], s["name"], s["zone"])
        for s in data
    ]
    n = insert_many(cur, "metro_stations", ["station_id", "name", "zone"], rows)
    print(f"  metro_stations: {n} rows")
```

**巢狀範例 — 展平每筆記錄中的清單：**

某些 JSON 欄位是巢狀清單（例如包含多個停靠站的時刻表）。同時迴圈外層清單和內層清單，為每個停靠站產生一列：

```python
def seed_metro_schedules(cur):
    data = load("metro_schedules.json")
    rows = []
    for schedule in data:
        for stop in schedule["stops"]:
            rows.append((
                schedule["schedule_id"],
                stop["station_id"],
                stop["arrival_time"],
                stop["stop_order"],
            ))
    n = insert_many(cur, "metro_schedule_stops",
                    ["schedule_id", "station_id", "arrival_time", "stop_order"], rows)
    print(f"  metro_schedule_stops: {n} rows")
```

`insert_many` 產生單一 `INSERT … VALUES %s ON CONFLICT DO NOTHING` — 可安全重複執行任意次數。

---

#### Neo4j 匯入器（`seed_neo4j.py`）

在 `seed()` 函式內，使用 `session.run()` 執行 Cypher。使用 `MERGE` 而非 `CREATE`，這樣重複執行不會產生重複的節點或關係。

**建立節點：**

```python
for s in metro_stations:
    session.run(
        "MERGE (n:MetroStation {station_id: $id}) "
        "SET n.name = $name, n.zone = $zone",
        id=s["station_id"], name=s["name"], zone=s.get("zone"),
    )
print(f"  Created {len(metro_stations)} MetroStation nodes")
```

**建立節點之間的關係：**

每個地鐵車站列出其相鄰車站。迴圈它們以建立有向連結：

```python
for s in metro_stations:
    for adj in s.get("adjacent_stations", []):
        session.run(
            "MATCH (a:MetroStation {station_id: $from_id}) "
            "MATCH (b:MetroStation {station_id: $to_id}) "
            "MERGE (a)-[r:METRO_LINK {line: $line}]->(b) "
            "SET r.travel_time_min = $time",
            from_id=s["station_id"], to_id=adj["station_id"],
            line=adj["line"], time=adj["travel_time_min"],
        )
print("  Created metro links")
```

在撰寫匯入器之前仔細研究 `train-mock-data/` 中的每個 JSON 檔案 — JSON 中的欄位成為你資料表中的欄位（PostgreSQL）或節點和關係上的屬性（Neo4j）。

---

### 任務 1 — 設計並擴充關聯式 Schema（PostgreSQL）

**要編輯的檔案：** `databases/relational/schema.sql`、`databases/relational/queries.py`

研究 `train-mock-data/` 中的 JSON 檔案，然後如上所述擴充 schema 並新增查詢函式。

任何 SQL schema 檔案變更後：
```bash
docker compose down -v && docker compose up -d

# macOS / Linux:
python3 skeleton/seed_postgres.py

# Windows (PowerShell):
python skeleton/seed_postgres.py
```

### 任務 2 — 豐富圖形（Neo4j）

**要編輯的檔案：** `databases/graph/seed.cypher`、`databases/graph/queries.py`

研究 `train-mock-data/metro_stations.json` 和 `train-mock-data/national_rail_stations.json`，然後如上所述擴充圖形並新增 Cypher 查詢函式。

編輯 seed 檔案後：
```bash
# macOS / Linux:
python3 skeleton/seed_neo4j.py

# Windows (PowerShell):
python skeleton/seed_neo4j.py
```

### 任務 3 — 新增政策文件（pgvector / RAG）

**要編輯的檔案：** `train-mock-data/` 中的政策 JSON 檔案 — 按照現有結構新增條目。

新增文件後：
```bash
# macOS / Linux:
python3 skeleton/seed_vectors.py

# Windows (PowerShell):
python skeleton/seed_vectors.py
```

### 任務 4 — 撰寫新的查詢函式

**要編輯的檔案：** `databases/relational/queries.py`、`databases/graph/queries.py`

按照這些檔案中已有的模式新增函式。要讓 agent 使用新函式，請見下方進階章節。

---

## 進階：擴充 Agent 或 UI

> **風險自負。** `skeleton/` 中的檔案是刻意完整且可運作的。編輯它們不是完成課程任務所必需的，且此處的錯誤可能破壞整個系統。在變更任何內容前先備份。

### 為 agent 新增工具

如果你在 `databases/relational/queries.py` 或 `databases/graph/queries.py` 中撰寫了新的查詢函式，並希望 AI 能呼叫它，你需要在 `skeleton/agent.py` 中做四個小變更。你**不需要**撰寫任何格式化或摘要程式碼 — 管線會自動將原始 JSON 結果轉換為純文字。

---

**步驟 1 — 匯入你的函式**，在檔案頂部與現有匯入一起：

```python
from databases.relational.queries import (
    query_national_rail_availability,
    # ... 現有匯入 ...
    your_new_function,          # 新增此行
)
```

---

**步驟 2 — 新增工具定義**到 `TOOLS` 清單。這是 LLM 讀取以決定何時及如何呼叫你的工具的內容。將描述寫成清晰的觸發短語 — 越精確，LLM 就越能在正確時機可靠地呼叫你的工具：

```python
{
    "name": "your_tool_name",
    "description": (
        "一兩句話解釋此工具做什麼。"
        "包含應觸發它的確切問題類型，例如"
        "'當使用者詢問月台號碼或出發看板時使用。'"
    ),
    "parameters": {
        "param_one": {"type": "string", "description": "此參數是什麼，例如車站 ID 如 NR01"},
        "param_two": {"type": "string", "description": "此參數是什麼"},
    },
    "required": ["param_one"],
},
```

---

**步驟 3 — 在 `TOOLS_SCHEMA` 新增一行**（Gemini JSON 路由器使用的精簡文字摘要，在 `TOOLS` 清單下方幾行）：

```python
TOOLS_SCHEMA = """\
...現有工具...
your_tool_name(param_one, param_two?)"""
```

使用 `?` 標記選擇性參數。

---

**步驟 4 — 接線執行**，在 `_execute_tool` 函式內，遵循每個現有工具使用的相同 `elif` 模式：

```python
elif tool_name == "your_tool_name":
    result = your_new_function(**params)
```

就這樣。管線的 Python 展平器（`agent.py` 中的 `_normalise_result`）會自動將你的函式回傳的任何 JSON 轉換為結構化可讀文字 — 不需要格式化程式碼。

---

**選擇性步驟 5 — 為 Ollama 新增路由提示**（僅在使用小型本機模型時 LLM 無法可靠呼叫你的工具時）：

在 `run_agent()` 中，找到 `ollama_tool_call` 系統提示字串並新增一行提示：

```python
system_prompt=(
    "...現有提示..."
    "Platform/departure board questions → your_tool_name. "   # 新增此行
    ...
),
```

你可以在 UI 中啟用 **「Show database debug panel」** 來驗證你的工具是否被呼叫 — 它顯示每輪的工具選擇輸出、原始資料庫結果和 LLM 生成的資料摘要。

---

**完整範例** — 新增一個查詢月台號碼的工具：

```python
# 步驟 1：在 agent.py 頂部的匯入中
from databases.relational.queries import (
    ...,
    query_platform_assignment,
)

# 步驟 2：在 TOOLS 清單中
{
    "name": "get_platform",
    "description": (
        "Look up the platform number for a national rail service at a station. "
        "Use when the user asks which platform to go to, or about departure boards."
    ),
    "parameters": {
        "station_id":   {"type": "string", "description": "Station ID e.g. NR01"},
        "schedule_id":  {"type": "string", "description": "Schedule ID e.g. NR_SCH01"},
    },
    "required": ["station_id", "schedule_id"],
},

# 步驟 3：在 TOOLS_SCHEMA 中
"get_platform(station_id, schedule_id)"

# 步驟 4：在 _execute_tool 中
elif tool_name == "get_platform":
    result = query_platform_assignment(**params)
```

---

### 修改 UI

聊天介面位於 `skeleton/ui.py`，使用 [Gradio](https://www.gradio.app/) 建構。如果你想變更版面、新增範例查詢或新增 UI 控制項，那是你唯一需要編輯的檔案。

你可以安全變更 `skeleton/ui.py` 中的：
- `EXAMPLES` 清單 — 新增或移除側邊欄中顯示的可點擊範例查詢
- `gr.Markdown()` 中的標題和描述文字
- UI 版面（欄寬、列數、色彩主題）

你不應在不理解影響的情況下變更 `skeleton/ui.py` 中的：
- `chat()` 函式 — 它呼叫 `run_agent()` 並管理對話歷史
- `agent_history_state` 狀態變數 — 移除它會破壞多輪對話
- `debug_panel` 和 `debug_toggle` — 它們連接到 agent 的除錯輸出

---

## 切換 Ollama 和 Gemini

**Ollama**（預設 — 本機、無 API 金鑰、不需網路）：
```bash
# 從 https://ollama.com/download 安裝 Ollama，然後拉取所需模型：
ollama pull llama3.2:1b        # ~1.3 GB  — 聊天模型
ollama pull nomic-embed-text   # ~274 MB  — pgvector 的嵌入模型
```
```env
LLM_PROVIDER=ollama
```

**Gemini**（替代方案 — 回應更快，需要免費 API 金鑰）：
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
```

Gemini 的嵌入模型產生 **3072 維**向量。Schema 預設為 **768**（Ollama）。如果你切換到 Gemini，在重置資料庫前還必須更新 `databases/relational/schema.sql`：

```sql
-- 在 policy_documents 資料表定義中變更此行：
embedding   vector(3072),
```

然後重置資料庫並重新匯入：
```bash
docker compose down -v && docker compose up -d

# macOS / Linux:
python3 skeleton/seed_vectors.py

# Windows (PowerShell):
python skeleton/seed_vectors.py
```

> **重要：** 如果你在匯入向量資料庫後切換提供者，必須始終重新執行 seed 腳本。嵌入模型隨提供者改變 — 儲存的向量將不再與使用新模型的查詢匹配。

---

## 實用網址（Docker 運行時）

| 服務 | 網址 | 登入憑證 |
|---|---|---|
| TransitFlow 聊天 UI | http://localhost:7860 | — |
| Neo4j Browser（圖形視覺化） | http://localhost:7475 | neo4j / transitflow |
| pgAdmin（PostgreSQL 瀏覽器 UI） | http://localhost:5051 | admin@admin.com / admin |
| PostgreSQL（直接連線） | localhost:5433 | transitflow / transitflow |

### 將 pgAdmin 連接到 PostgreSQL

1. 開啟 **http://localhost:5051** 並以 `admin@admin.com` / `admin` 登入
2. 在左側邊欄，右鍵點擊 **Servers → Register → Server…**
3. 填寫兩個分頁：

   **General 分頁**
   - Name：`TransitFlow`（或任何你喜歡的標籤）

   **Connection 分頁**
   - Host：`postgres`
   - Port：`5432`
   - Maintenance database：`transitflow`
   - Username：`transitflow`
   - Password：`transitflow`
   - 勾選 **Save password**

4. 點擊 **Save** — 伺服器出現在側邊欄。展開它在 **Databases → transitflow → Schemas → public → Tables** 下瀏覽資料表。

要執行 SQL 查詢，右鍵點擊資料庫並選擇 **Query Tool**。

---

要在 Neo4j Browser 中視覺化整個鐵路網路，貼上此查詢：
```cypher
MATCH (n)-[r]->(m) RETURN n, r, m
```

---

## 疑難排解

**「Cannot connect to Neo4j」** — Neo4j 最多需要 30 秒啟動。等待後重試。

**「GEMINI_API_KEY is not set」** — 你設定了 `LLM_PROVIDER=gemini` 但沒有金鑰。要麼在 `.env` 中加入你的金鑰，要麼切換到 `LLM_PROVIDER=ollama` 以無需金鑰執行。

**「Cannot reach Ollama」** — Ollama 未執行。從應用程式資料夾或系統匣啟動它，然後重試。

**「embedding dimension mismatch」** — 資料庫中儲存的向量維度與活動嵌入模型不匹配。可能是你在匯入後切換了提供者，或 `schema.sql` 仍宣告錯誤的維度。確認 `schema.sql` 中 Ollama 為 `vector(768)` 或 Gemini 為 `vector(3072)`，重置資料庫（`docker compose down -v && docker compose up -d`），然後重新執行 `python skeleton/seed_vectors.py`。

**Docker 容器無法啟動** — 確保 Docker Desktop 已開啟並執行。然後嘗試：`docker compose down -v && docker compose up -d`

**Gradio 啟動時顯示錯誤** — 檢查終端中的 Python traceback。最常見的原因是缺少 `.env` 檔案，或資料庫容器尚未完全就緒。

**`pip install` 成功但 `python skeleton/ui.py` 顯示「ModuleNotFoundError」** — 你的虛擬環境未啟動。執行 `source .venv/bin/activate`（macOS/Linux）或 `.venv\Scripts\Activate.ps1`（Windows PowerShell）後重試。

**Windows PowerShell 顯示「running scripts is disabled」** — 執行一次以下指令，然後重試啟動：
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**macOS 或 Linux 上找不到 `python`** — 改用 `python3`。在這些系統上，`python` 可能指向 Python 2 或可能不存在。本 README 中所有 `python` 指令都可替換為 `python3`。

---

## Python 虛擬環境

### 什麼是虛擬環境？

當你用 `pip install` 安裝 Python 套件時，它們會被放在你機器上的某個地方。沒有虛擬環境時，它們會進入你的**系統 Python** — 一個共享的全域位置，被你的作業系統、其他專案和你可能不知道的工具使用。

**虛擬環境**（venv）為單一專案建立一個私有、隔離的 Python 副本。安裝在其中的套件留在其中。你的系統 Python 不受影響。如果你刪除專案，環境也隨之刪除 — 不需要清理。

```
沒有 venv                            有 venv
────────────────────────────────     ───────────────────────────────────
系統 Python                          系統 Python（未變更）
  └── site-packages/                   └── site-packages/（未變更）
        requests==2.28                        ← 此處未新增任何東西
        gradio==4.0
        neo4j==5.0                   transitflow/.venv/
        psycopg2==2.9                  └── site-packages/
        （所有專案使用）                       requests==2.28
                                             gradio==4.0
                                             neo4j==5.0
                                             psycopg2==2.9
                                             （僅此專案使用）
```

### 為什麼對本專案重要

本專案安裝特定版本的 `gradio`、`neo4j`、`psycopg2`、`google-genai` 和其他幾個套件。如果你在同一台機器上處理其他 Python 專案，那些專案可能需要相同套件的不同版本。沒有隔離，安裝一個專案的需求可能悄悄破壞另一個。

虛擬環境完全防止這種情況。每個專案都有自己的沙盒。

### `apt install` vs `pip install` — 有什麼區別？

你可能見過這兩個指令並想知道何時使用哪個。

**`apt install`**（僅 Debian/Ubuntu Linux）是你**作業系統的**套件管理器。它在系統層級安裝軟體 — 不只是 Python 套件，還有你的 OS 需要的任何程式、函式庫或工具。當你安裝整台機器需要的東西時使用它：

```bash
# 安裝 Python 本身，或系統層級工具
sudo apt install python3
sudo apt install python3-pip
sudo apt install postgresql-client
```

`apt` 套件經過與你的 OS 發行版的相容性測試。它們通常刻意稍微落後最新版本，因為在系統層級穩定性比新穎性更重要。

**`pip install`** 是 **Python 的**套件管理器。它從 [PyPI](https://pypi.org)（Python Package Index）安裝套件到當前活動的 Python 環境中。當你安裝程式碼要使用的 Python 函式庫時使用它：

```bash
# 安裝你的程式碼匯入的 Python 函式庫
pip install gradio
pip install psycopg2-binary
pip install neo4j
```

關鍵區別：`apt` 管理你的機器；`pip` 管理你的 Python 專案。對於應用程式開發，虛擬環境中的 `pip` 是你管理所有 Python 相依性的方式。`apt` 僅在安裝 Python 本身或系統層級先決條件（如資料庫客戶端）時需要。

| | `apt install` | `pip install` |
|---|---|---|
| 安裝什麼 | 系統軟體和 OS 層級函式庫 | 你程式碼用的 Python 套件 |
| 套件去哪裡 | 系統目錄（`/usr/lib` 等） | 活動 Python 環境 |
| 誰維護 | 你的 Linux 發行版 | Python 社群（PyPI） |
| 何時使用 | 安裝 Python、系統工具、驅動程式 | 安裝你的專案匯入的函式庫 |
| 需要 `sudo`？ | 是 | 否（在 venv 中） |

### 為本專案設定虛擬環境

**步驟 1 — 建立環境**（複製後一次）：

**macOS / Linux：**
```bash
cd transitflow
python3 -m venv .venv
```

**Windows (PowerShell)：**
```powershell
cd transitflow
python -m venv .venv
```

這會在專案內建立一個 `.venv/` 資料夾。它包含一個私有 Python 直譯器和一個空的 `site-packages/` 目錄。該資料夾列在 `.gitignore` 中 — 永遠不應被提交。

**步驟 2 — 啟動它**（每次開啟新終端時）：

**macOS / Linux：**
```bash
source .venv/bin/activate
```

**Windows (PowerShell)：**
```powershell
.venv\Scripts\Activate.ps1
```

> **Windows PowerShell 注意：** 如果啟動失敗並顯示「running scripts is disabled」，執行一次以下指令後重試：
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

你的提示會變為顯示 `(.venv)` 作為確認。啟動時，`python` 和 `pip` 指向環境的私有副本，而非系統的。

**步驟 3 — 安裝專案套件：**

```bash
pip install -r requirements.txt
```

所有套件進入 `.venv/site-packages/`。你的系統 Python 不受影響。

**步驟 4 — 完成後停用**（選擇性）：

```bash
deactivate
```

### 快速參考

| 任務 | macOS / Linux | Windows (PowerShell) |
|---|---|---|
| 建立環境 | `python3 -m venv .venv` | `python -m venv .venv` |
| 啟動 | `source .venv/bin/activate` | `.venv\Scripts\Activate.ps1` |
| 安裝專案套件 | `pip install -r requirements.txt` | `pip install -r requirements.txt` |
| 查看已安裝套件 | `pip list` | `pip list` |
| 停用 | `deactivate` | `deactivate` |
| 刪除環境 | `rm -rf .venv` | 刪除 `.venv\` 資料夾 |

### 虛擬環境與 IDE

大多數 IDE 自動偵測並使用虛擬環境：

- **VS Code** — 開啟專案資料夾，按 `Ctrl+Shift+P`，選擇 **Python: Select Interpreter**，並選擇標記為 `.venv` 的那個。VS Code 之後會在所有終端和除錯器中使用它。
- **PyCharm** — 前往 Settings → Project → Python Interpreter → Add Interpreter → Existing → 指向 `.venv/bin/python`（macOS/Linux）或 `.venv\Scripts\python.exe`（Windows PowerShell）。

一旦你的 IDE 設定好，你不需要在整合終端中手動啟動環境 — 它會自動啟動。

---

## 團隊協作

### Git 追蹤什麼 — 以及不追蹤什麼

Docker volumes 不是你 git 儲存庫的一部分。每個隊友的資料庫資料完全存在於他們自己的機器上。**Git 只追蹤定義資料的檔案** — 而非資料本身。

| 什麼 | 被 git 追蹤？ | 備註 |
|---|---|---|
| `databases/relational/schema.sql` | 是 | 資料表、約束和所有種子資料 |
| `databases/graph/seed.cypher` | 是 | 車站節點和鐵路連結邊 |
| `train-mock-data/` 政策 JSON | 是 | 要嵌入的政策文件 |
| `databases/*/queries.py` | 是 | Python 查詢函式 |
| `.env` | **否**（gitignored） | 每個隊友基於 `.env.example` 保留自己的副本 |
| Docker volume 資料 | **否** | 僅由 Docker 儲存在你的本機 |

這意味著：如果隊友變更了 `schema.sql` 並推送到 git，你正在執行的資料庫不受影響，直到你明確重置並重新載入。

---

### 黃金法則

> **如果 seed 檔案在 git 中變更了，重置你的資料庫。**

每次 `git pull` 後，檢查三個 seed 檔案是否有變更，並相應處理：

```bash
# 查看隊友變更了哪些 seed 檔案：
git diff HEAD~1 HEAD -- databases/relational/schema.sql databases/graph/seed.cypher train-mock-data/refund_policy.json train-mock-data/ticket_types.json train-mock-data/booking_rules.json train-mock-data/travel_policies.json
```

| 變更的檔案 | 要執行的指令 |
|---|---|
| `databases/relational/schema.sql` | `docker compose down -v && docker compose up -d`，然後 `python skeleton/seed_postgres.py` |
| `skeleton/seed_postgres.py`（或任何 `train-mock-data/*.json`） | `python skeleton/seed_postgres.py` |
| `databases/graph/seed.cypher` | `python skeleton/seed_neo4j.py` |
| `train-mock-data/` 政策 JSON 檔案 | `python skeleton/seed_vectors.py` |

> **重要：** `docker compose down -v` 會清除**兩個** Docker volumes（PostgreSQL 和 pgvector 一起）。如果你因 schema 變更而重置，之後也必須重新執行 `seed_neo4j.py` 和 `seed_vectors.py` — 即使那些檔案沒有變更。

---

### 匯入前先統一 LLM 提供者

pgvector 中的政策文件以數值向量儲存。這些向量的大小取決於嵌入模型，而嵌入模型隨 LLM 提供者改變：

| 提供者 | `schema.sql` 中的向量大小 | `.env` 設定 |
|---|---|---|
| Ollama（預設） | `vector(768)` | `LLM_PROVIDER=ollama` |
| Gemini | `vector(3072)` | `LLM_PROVIDER=gemini` |

**這兩種格式不相容。** 如果一個隊友用 Ollama 匯入而另一個用 Gemini 查詢（或反之），應用程式會失敗並顯示 `embedding dimension mismatch` 錯誤。

在任何人執行 `seed_vectors.py` 之前，團隊先統一單一提供者。確保：
1. 每個人在自己的 `.env` 中設定相同的 `LLM_PROVIDER` 值
2. `databases/relational/schema.sql` 中的 `vector(...)` 維度與該提供者匹配

如果之後團隊切換提供者，每個人都必須重置資料庫（`docker compose down -v && docker compose up -d`）並重新執行 `seed_vectors.py`。

---

### 完整重新同步流程（如果 seed 檔案變更，每次 `git pull` 後執行）

```bash
# 1. 清除 volumes 並重啟容器（僅在 schema.sql 變更時需要）
docker compose down -v && docker compose up -d

# 2. 等待兩個容器健康
docker compose ps

# 3. 匯入關聯式資料庫
#    macOS / Linux:
python3 skeleton/seed_postgres.py
#    Windows (PowerShell):
python skeleton/seed_postgres.py

# 4. 重新匯入圖形資料庫
#    macOS / Linux:
python3 skeleton/seed_neo4j.py
#    Windows (PowerShell):
python skeleton/seed_neo4j.py

# 5. 重新匯入向量資料庫
#    macOS / Linux:
python3 skeleton/seed_vectors.py
#    Windows (PowerShell):
python skeleton/seed_vectors.py
```

---

### 該提交什麼 — 以及不該提交什麼

**始終提交** `databases/` 內任何檔案的變更 — 那是你的工作區域和共享的真實來源。

**永遠不要提交：**
- `.env` — gitignored 因為它包含憑證。每個隊友複製 `.env.example` 並填入自己的值。
- `.venv/` 資料夾 — gitignored，且很大。每個隊友透過 `python -m venv .venv` 建立自己的。
- 任何本機生成的資料匯出或傾印檔案。

推送前，執行 `git status` 和 `git diff --staged` 確認你只提交了 `databases/` 中的檔案。
