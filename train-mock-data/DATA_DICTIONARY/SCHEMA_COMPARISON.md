# 三份資料字典的比較分析

本文比較三組來源的關聯式 schema 設計：

- **Xan**（DATA_DICTIONARY_1.md）
- **張恩家**（DATA_DICTIONARY_2.md）
- **陳楷**（DATA_DICTIONARY_3）

> **原則：** 不是一定要從兩位組員的設計裡二擇一。原始 JSON 結構本身已經很乾淨，三位都不夠完整時，直接給出新設計才是負責任的整合。

---

## 表格逐項比較與最終決議

### 1. Users（使用者）

| 比較項 | Xan | 張恩家 | 原始 JSON |
|--------|-----|--------|----------|
| 基本欄位 | ✓ | ✓ | ✓ |
| `secret_question` / `secret_answer` | ❌ 缺 | ✓ | ✓ |
| `registered_at` | ❌ 缺 | ✓ | ✓ |
| `is_active` | ❌ 缺 | ✓ | ✓ |

**✅ 最終決議：採用張恩家的設計（與原始 JSON 完全一致）**

理由：張恩家完整對應 JSON 結構，沒有遺漏。Xan 漏掉的認證欄位會讓 `register_user()`、`get_user_secret_question()`、`verify_secret_answer()` 等函式無法實作。

```sql
CREATE TABLE users (
    user_id          VARCHAR(10) PRIMARY KEY,
    full_name        VARCHAR(100) NOT NULL,
    email            VARCHAR(100) UNIQUE NOT NULL,
    password         VARCHAR(100) NOT NULL,
    phone            VARCHAR(20),
    date_of_birth    DATE,
    secret_question  TEXT,
    secret_answer    TEXT,
    registered_at    TIMESTAMPTZ DEFAULT NOW(),
    is_active        BOOLEAN DEFAULT TRUE
);
```

---

### 2. Payments（付款）

| 比較項 | Xan | 張恩家 | 原始 JSON |
|--------|-----|--------|----------|
| 多型 FK 處理 | ✓ `transaction_type` ENUM | ❌ 模糊處理 | ❌ 同張恩家 |
| 欄位命名 | `reference_id`（改名） | `booking_id`（保留） | `booking_id` |

**✅ 最終決議：新設計 — 保留原始命名 + 採用 Xan 的多型概念 + 加 CHECK 約束**

理由：Xan 用 `transaction_type` 區分 NR/Metro 是好設計，但改名 `reference_id` 會讓 mock data seed 時要做欄位映射。最佳解是**保留原命名 `booking_id`，但加上 CHECK 約束**確保前綴正確：

```sql
CREATE TABLE payments (
    payment_id        VARCHAR(20) PRIMARY KEY,
    booking_id        VARCHAR(20) NOT NULL,
    transaction_type  VARCHAR(10) NOT NULL CHECK (transaction_type IN ('NR', 'Metro')),
    amount_usd        NUMERIC(10,2) NOT NULL,
    method            VARCHAR(30) CHECK (method IN ('credit_card', 'debit_card', 'ewallet')),
    status            VARCHAR(30) CHECK (status IN ('paid', 'refunded')),
    paid_at           TIMESTAMPTZ,
    -- 確保 booking_id 前綴與 transaction_type 一致
    CONSTRAINT chk_booking_prefix CHECK (
        (transaction_type = 'NR' AND booking_id LIKE 'BK%') OR
        (transaction_type = 'Metro' AND booking_id LIKE 'MT%')
    )
);

CREATE INDEX idx_payments_booking_id ON payments(booking_id);
```

這比兩位組員的設計都更嚴謹——不只區分類型，還用 CHECK 防止類型與 ID 不對應的髒資料。

---

### 3. National Rail Stations / Metro Stations（車站）

| 比較項 | Xan | 張恩家 | 原始 JSON |
|--------|-----|--------|----------|
| `lines` 陣列 | ❌ 缺 | ✓ 拆 `station_lines` 子表 | ✓ inline 陣列 |
| 轉乘旗標 | ✓ | ✓ | ✓ |
| `station_adjacent` 子表 | ❌ | ⚠️ **錯誤** | — |

**✅ 最終決議：新設計 — 直接用 PostgreSQL 的 TEXT[] 存陣列**

理由：張恩家拆 `station_lines` 子表是「教科書式正規化」，但對這個資料規模（20 + 10 = 30 個車站，總共 6 條線）**過度設計**。PostgreSQL 原生支援陣列型別，查詢同樣方便。

而張恩家的 `station_adjacent` 子表是**設計錯誤**——`adjacent_stations` 屬於 Neo4j 圖形資料庫的職責，原始資料字典明確標注「⚠️ 用於 Neo4j，不存入 PostgreSQL」。

```sql
CREATE TABLE metro_stations (
    station_id                            VARCHAR(10) PRIMARY KEY,
    name                                  VARCHAR(100) NOT NULL,
    lines                                 TEXT[] NOT NULL,
    is_interchange_metro                  BOOLEAN DEFAULT FALSE,
    interchange_metro_lines               TEXT[],
    is_interchange_national_rail          BOOLEAN DEFAULT FALSE,
    interchange_national_rail_station_id  VARCHAR(10)
);

CREATE TABLE national_rail_stations (
    station_id                            VARCHAR(10) PRIMARY KEY,
    name                                  VARCHAR(100) NOT NULL,
    lines                                 TEXT[] NOT NULL,
    is_interchange_national_rail          BOOLEAN DEFAULT FALSE,
    interchange_national_rail_lines       TEXT[],
    is_interchange_metro                  BOOLEAN DEFAULT FALSE,
    interchange_metro_station_id          VARCHAR(10)
);
```

> 註：兩個 stations 表互相參照（互為 FK），所以建議不設嚴格 FK 約束，避免雞生蛋蛋生雞的問題。或者用 `DEFERRABLE` FK。

---

### 4. National Rail Schedules（國鐵時刻表）

| 比較項 | Xan | 張恩家 | 原始 JSON |
|--------|-----|--------|----------|
| 基本欄位 | ✓ | ✓ | ✓ |
| `frequency_min` | ❌ | ✓ | ✓ |
| `operates_on` | ❌ | ❌ | ✓ |
| `fare_classes` | ❌ | ❌ | ✓ **三家都漏或都不完整** |
| `passed_through_stations`（快車跳站）| ❌ | ❌ | ✓ |
| `stops_in_order` 處理 | ✓ 拆 `Schedule_Stops` 子表 | ❌ | ✓ inline |

**✅ 最終決議：新設計 — 結合 Xan 的子表 + 票價攤平 + 補齊兩家都漏的欄位**

理由：兩位組員都漏了 `fare_classes`（票價計算的核心）和 `operates_on`（營運日，快車週末不開），這些不能省。Xan 拆 `Schedule_Stops` 子表的設計很好，比 JSONB 更容易做順序查詢。

```sql
CREATE TABLE national_rail_schedules (
    schedule_id                  VARCHAR(20) PRIMARY KEY,
    line                         VARCHAR(10) NOT NULL,
    service_type                 VARCHAR(20) NOT NULL CHECK (service_type IN ('normal', 'express')),
    direction                    VARCHAR(20),
    origin_station_id            VARCHAR(10) REFERENCES national_rail_stations(station_id),
    destination_station_id       VARCHAR(10) REFERENCES national_rail_stations(station_id),
    first_train_time             TIME,
    last_train_time              TIME,
    -- 票價攤平成 4 欄位（取 Xan 思路 + 原始 JSON 資料）
    fare_standard_base_usd       NUMERIC(5,2) NOT NULL,
    fare_standard_per_stop_usd   NUMERIC(5,2) NOT NULL,
    fare_first_base_usd          NUMERIC(5,2) NOT NULL,
    fare_first_per_stop_usd      NUMERIC(5,2) NOT NULL,
    frequency_min                INTEGER,
    operates_on                  TEXT[]   -- ["mon","tue",...,"sun"]
);

-- 採用 Xan 的子表設計（比 JSONB 更易於順序查詢）
CREATE TABLE national_rail_schedule_stops (
    schedule_id                   VARCHAR(20) REFERENCES national_rail_schedules(schedule_id),
    stop_order                    INTEGER NOT NULL,
    station_id                    VARCHAR(10) REFERENCES national_rail_stations(station_id),
    travel_time_from_origin_min   INTEGER NOT NULL,
    is_passed_through             BOOLEAN DEFAULT FALSE,  -- 快車經過但不停的站
    PRIMARY KEY (schedule_id, stop_order)
);
```

`is_passed_through` 是新加的欄位，把 `passed_through_stations` 也整合進子表，避免再開一張子表。

---

### 5. Metro Schedules（地鐵時刻表）

| 比較項 | Xan | 張恩家 | 原始 JSON |
|--------|-----|--------|----------|
| 起訖站、時間、頻率 | ❌ 太簡化 | ✓ | ✓ |
| `stops_in_order` | ❌ | ❌ | ✓ |
| `travel_time_from_origin_min` | ❌ | ❌ | ✓ |
| `operates_on` | ❌ | ❌ | ✓ |
| 票價欄位 | ✓ | ✓ | ✓ |

**✅ 最終決議：新設計 — 比照國鐵的子表結構**

理由：兩家都漏了 `stops_in_order` 和 `travel_time_from_origin_min`，這是計算地鐵站數和旅行時間的關鍵。應該比照 NR 採用子表設計，保持一致性：

```sql
CREATE TABLE metro_schedules (
    schedule_id              VARCHAR(20) PRIMARY KEY,
    line                     VARCHAR(10) NOT NULL,
    direction                VARCHAR(20),
    origin_station_id        VARCHAR(10) REFERENCES metro_stations(station_id),
    destination_station_id   VARCHAR(10) REFERENCES metro_stations(station_id),
    first_train_time         TIME,
    last_train_time          TIME,
    base_fare_usd            NUMERIC(5,2) NOT NULL DEFAULT 0.80,
    per_stop_rate_usd        NUMERIC(5,2) NOT NULL DEFAULT 0.30,
    frequency_min            INTEGER,
    operates_on              TEXT[]
);

CREATE TABLE metro_schedule_stops (
    schedule_id                   VARCHAR(20) REFERENCES metro_schedules(schedule_id),
    stop_order                    INTEGER NOT NULL,
    station_id                    VARCHAR(10) REFERENCES metro_stations(station_id),
    travel_time_from_origin_min   INTEGER NOT NULL,
    PRIMARY KEY (schedule_id, stop_order)
);
```

---

### 6. National Rail Seats（座位）

| 比較項 | Xan | 張恩家 | 原始 JSON |
|--------|-----|--------|----------|
| `schedule_id` | ✓ | ❌ 缺 | ✓（透過 layout） |
| `coach` / `seat_id` | ✓ | ✓ | ✓ |
| `fare_class` | ✓ | ❌ 缺 | ✓ |
| `row` / `column` | ❌ | ✓ | ✓ |
| `layout_id` | ❌ | ✓ | ✓ |

**✅ 最終決議：新設計 — 兩家各取所需 + 省略 layout 中介**

理由：原始資料用 `layout_id` 作為中間層（layout → coach → seats），但因為 schedule 與 layout 是 1:1 對應，這層中介可省略。直接把 schedule_id 放在 seats 表上更簡單。

```sql
CREATE TABLE national_rail_seats (
    schedule_id    VARCHAR(20) REFERENCES national_rail_schedules(schedule_id),
    seat_id        VARCHAR(10) NOT NULL,        -- "A01"、"B05"
    coach          CHAR(1) NOT NULL CHECK (coach IN ('A', 'B')),
    fare_class     VARCHAR(10) NOT NULL CHECK (fare_class IN ('standard', 'first')),
    row_number     INTEGER NOT NULL,            -- "row" 是 SQL 保留字，改名
    column_letter  CHAR(1) NOT NULL,
    PRIMARY KEY (schedule_id, seat_id)
);
```

> 注意：`row` 是 SQL 保留字，最好改名 `row_number` 或加引號。`column` 雖然在 PostgreSQL 不是嚴格保留字，但跟 SQL 語意衝突，改名 `column_letter` 比較安全。

---

### 7. Metro Trips（地鐵搭乘）

| 比較項 | Xan | 張恩家 | 原始 JSON |
|--------|-----|--------|----------|
| `day_pass_ref` 自參照 | ✓ **關鍵** | ❌ | ✓ |
| `stops_travelled` | ✓ | ❌ | ✓ |
| `travel_date` | ❌ | ✓ | ✓ |
| `travelled_at` | ❌ | ✓ | ✓ |
| `purchased_at` | ❌ | ❌ | ✓ |

**✅ 最終決議：直接採用原始 JSON 結構（兩家都不完整）**

理由：兩位組員各漏一半欄位，原始 JSON 反而是最完整的。直接以原始為準：

```sql
CREATE TABLE metro_travel_history (
    trip_id                  VARCHAR(20) PRIMARY KEY,
    user_id                  VARCHAR(10) REFERENCES users(user_id),
    schedule_id              VARCHAR(20) REFERENCES metro_schedules(schedule_id),
    origin_station_id        VARCHAR(10) REFERENCES metro_stations(station_id),
    destination_station_id   VARCHAR(10) REFERENCES metro_stations(station_id),
    travel_date              DATE NOT NULL,
    ticket_type              VARCHAR(20) CHECK (ticket_type IN ('single', 'day_pass')),
    day_pass_ref             VARCHAR(20) REFERENCES metro_travel_history(trip_id),  -- 自參照
    stops_travelled          INTEGER,
    amount_usd               NUMERIC(10,2),
    status                   VARCHAR(20) CHECK (status IN ('completed', 'cancelled')),
    purchased_at             TIMESTAMPTZ,
    travelled_at             TIMESTAMPTZ
);
```

---

### 8. National Rail Bookings（國鐵訂票）

| 比較項 | Xan | 張恩家 | 原始 JSON |
|--------|-----|--------|----------|
| 基本欄位 | ✓ | ✓ | ✓ |
| `departure_time` | ❌ | ✓ | ✓ |
| `booked_at` | ❌ | ✓ | ✓ |
| `travelled_at` | ❌ | ❌ | ✓ |
| `stops_travelled` | ❌ | ❌ | ✓ |

**✅ 最終決議：直接採用原始 JSON 結構（兩家都漏 `travelled_at` 和 `stops_travelled`）**

理由：`stops_travelled` 是退款計算的核心（依 RF005 政策），`travelled_at` 用來判斷是否已搭乘。兩家都漏了，必須補。

```sql
CREATE TABLE national_rail_bookings (
    booking_id               VARCHAR(20) PRIMARY KEY,
    user_id                  VARCHAR(10) REFERENCES users(user_id),
    schedule_id              VARCHAR(20) REFERENCES national_rail_schedules(schedule_id),
    origin_station_id        VARCHAR(10) REFERENCES national_rail_stations(station_id),
    destination_station_id   VARCHAR(10) REFERENCES national_rail_stations(station_id),
    travel_date              DATE NOT NULL,
    departure_time           TIME,
    ticket_type              VARCHAR(20) CHECK (ticket_type IN ('single', 'return')),
    fare_class               VARCHAR(10) CHECK (fare_class IN ('standard', 'first')),
    coach                    CHAR(1),
    seat_id                  VARCHAR(10),
    stops_travelled          INTEGER,
    amount_usd               NUMERIC(10,2),
    status                   VARCHAR(20) CHECK (status IN ('confirmed', 'completed', 'cancelled')),
    booked_at                TIMESTAMPTZ,
    travelled_at             TIMESTAMPTZ
);

-- 加速座位可用性查詢（query_available_seats 高頻使用）
CREATE INDEX idx_bookings_schedule_date_status 
    ON national_rail_bookings(schedule_id, travel_date, status);
```

---

### 9. Feedback（回饋）

| 比較項 | Xan | 張恩家 | 原始 JSON |
|--------|-----|--------|----------|
| 命名 | `reference_id` | `booking_id` | `booking_id` |
| 多型處理 | ✓（隱含） | ❌ | ❌ |
| `rating` 範圍約束 | ❌ | ❌ | ❌（隱含 1-5） |

**✅ 最終決議：採用原始命名 + 加 CHECK 約束 + 加多型欄位**

```sql
CREATE TABLE feedback (
    feedback_id       VARCHAR(20) PRIMARY KEY,
    booking_id        VARCHAR(20) NOT NULL,
    transaction_type  VARCHAR(10) NOT NULL CHECK (transaction_type IN ('NR', 'Metro')),
    user_id           VARCHAR(10) REFERENCES users(user_id),
    rating            INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment           TEXT,
    submitted_at      TIMESTAMPTZ
);
```

---

## 整體決議摘要

| 表 | 主要採用 | 來源 |
|----|---------|------|
| **users** | 張恩家的設計 | 完全對應 JSON |
| **payments** | 新設計 | Xan 的 `transaction_type` + 原始命名 + CHECK 約束 |
| **metro_stations** / **national_rail_stations** | 新設計 | 用 TEXT[] 存陣列，移除 station_adjacent |
| **national_rail_schedules** | 新設計 | Xan 的子表 + 票價攤平 + 補 operates_on |
| **metro_schedules** | 新設計 | 比照 NR 的子表結構 |
| **national_rail_seats** | 新設計 | 兩家各取所需 + 避開 SQL 保留字 |
| **metro_travel_history** | 原始 JSON 結構 | 兩家都不完整 |
| **national_rail_bookings** | 原始 JSON 結構 | 兩家都漏關鍵欄位 |
| **feedback** | 新設計 | 原始命名 + 加 CHECK + 加 transaction_type |

---

## 給三位的回饋

### 給 Xan
**強項：** 架構思維清晰——polymorphic 用 ENUM 區分、stops 拆子表、day_pass 自參照都是很乾淨的設計選擇。

**待改進：** 欄位完整度是最大問題。許多業務必要的欄位被漏掉（登入認證、票價結構、時間戳記），實作 `register_user()`、`query_national_rail_fare()`、`execute_cancellation()` 時會卡住。

**建議：** 設計 schema 時先把所有 JSON 欄位逐一列出，確認沒有遺漏，再思考要怎麼正規化或攤平。**結構之前先求完整**。

---

### 給張恩家
**強項：** 欄位完整度最高，幾乎涵蓋所有原始 JSON 內容。對基本資料表的設計很扎實。

**待改進：**
1. `metro_station_adjacent` 子表是設計錯誤——那是 Neo4j 圖形資料庫的職責
2. 缺乏進階設計考量：polymorphic 關聯、自參照 FK、座位的艙等分類等都沒處理
3. 漏了 `fare_classes`（國鐵票價）、`day_pass_ref`（日票邏輯）、`stops_travelled`（退款計算）等業務關鍵欄位

**建議：** 完成基本欄位後，下一步是思考「**這張表的資料會被怎麼查詢？**」例如「取消訂票時要算退款，需要哪些欄位？」這會幫你發現自己漏掉的設計。

---

### 給陳楷（整合者）
你的最終 schema 不需要強迫採用任何一方的設計。原則應該是：

1. **欄位完整度為先：** 兩家都不完整時直接從原始 JSON 取（users、metro_trips、bookings）
2. **採用好的架構選擇：** Xan 的 `transaction_type` 多型、子表化 stops、self-reference 都值得保留
3. **加上兩家都沒做的工程實踐：** CHECK 約束、複合索引、避開 SQL 保留字
4. **修正錯誤：** `station_adjacent` 不該進 PostgreSQL，要說明清楚

最終 schema 應該是「以原始 JSON 為基準確保完整性 + 借用 Xan 的架構亮點 + 補上業界最佳實踐」的混合體。
