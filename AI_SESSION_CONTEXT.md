# AI Session Context — TransitFlow

**How to use this file:**
At the start of every AI coding session, paste the full contents of this file as your first message to your AI assistant. This gives the AI the context it needs to produce code that fits your codebase and is consistent with your teammates' work.

**Who maintains this file:**
Whoever makes a schema change or architectural decision updates this file in the same commit. Treat it like a team contract.

---

## Project Overview

TransitFlow is a Python-based AI chat assistant for a fictional transit operator. It queries three databases — PostgreSQL (relational + vector), Neo4j (graph) — and uses an LLM to answer user questions. Our task as students is to design the database schema and implement the query functions in `databases/relational/queries.py` and `databases/graph/queries.py`.

## Tech Stack

- Language: Python 3.11+
- Relational DB: PostgreSQL via `psycopg2` with `RealDictCursor`
- Graph DB: Neo4j via the `neo4j` Python driver
- Vector search: `pgvector` extension (already implemented — do not modify)
- Web UI: Gradio
- LLM: Google Gemini or local Ollama (configured via `.env`)

## Coding Conventions

- **Naming:** `snake_case` for all Python names and SQL identifiers
- **Docstrings:** All functions must have a docstring with `Args:` and `Returns:` sections
- **Return types:** Use type hints. Read-only functions return `list[dict]` or `Optional[dict]`
- **Empty results:** Return `[]` or `None` (as documented), never raise an exception for "not found"
- **SQL:** Use `%s` placeholders for all user inputs — never string-format into SQL
- **Relational pattern:** Use `_connect()` helper + `psycopg2.extras.RealDictCursor`:
  ```python
  with _connect() as conn:
      with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
          cur.execute("SELECT ...", (param,))
          return [dict(row) for row in cur.fetchall()]
  ```
- **Graph pattern:** Use `_driver()` helper + session:
  ```python
  with _driver() as driver:
      with driver.session() as session:
          result = session.run("MATCH ...", station_id=station_id)
          return [dict(record) for record in result]
  ```

## Agreed Relational Schema

整合三份資料字典的最終決議。三項原則：(1) 欄位完整度為先,兩家都不完整時直接從原始 JSON 取；(2) 採用 Xan 的架構亮點 — polymorphic `transaction_type`、子表化 stops、`day_pass_ref` 自參照；(3) 加上 CHECK 約束、複合索引、避開 SQL 保留字。`station_adjacent` 留給 Neo4j。

詳細比較見 `train-mock-data/DATA_DICTIONARY_RELATIONAL/SCHEMA_COMPARISON_RELATIONAL.md`,實際 DDL 在 `databases/relational/schema.sql`。

```sql
-- USERS
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

-- STATIONS  (兩表互相參照,故不設嚴格 FK)
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

-- SCHEDULES + STOPS  (子表化便於做順序查詢)
CREATE TABLE national_rail_schedules (
    schedule_id                  VARCHAR(20) PRIMARY KEY,
    line                         VARCHAR(10) NOT NULL,
    service_type                 VARCHAR(20) NOT NULL CHECK (service_type IN ('normal','express')),
    direction                    VARCHAR(20),
    origin_station_id            VARCHAR(10) REFERENCES national_rail_stations(station_id),
    destination_station_id       VARCHAR(10) REFERENCES national_rail_stations(station_id),
    first_train_time             TIME,
    last_train_time              TIME,
    fare_standard_base_usd       NUMERIC(5,2) NOT NULL,
    fare_standard_per_stop_usd   NUMERIC(5,2) NOT NULL,
    fare_first_base_usd          NUMERIC(5,2) NOT NULL,
    fare_first_per_stop_usd      NUMERIC(5,2) NOT NULL,
    frequency_min                INTEGER,
    operates_on                  TEXT[]
);

CREATE TABLE national_rail_schedule_stops (
    schedule_id                   VARCHAR(20) NOT NULL REFERENCES national_rail_schedules(schedule_id),
    stop_order                    INTEGER NOT NULL,
    station_id                    VARCHAR(10) NOT NULL REFERENCES national_rail_stations(station_id),
    travel_time_from_origin_min   INTEGER NOT NULL,
    is_passed_through             BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (schedule_id, stop_order)
);

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
    schedule_id                   VARCHAR(20) NOT NULL REFERENCES metro_schedules(schedule_id),
    stop_order                    INTEGER NOT NULL,
    station_id                    VARCHAR(10) NOT NULL REFERENCES metro_stations(station_id),
    travel_time_from_origin_min   INTEGER NOT NULL,
    PRIMARY KEY (schedule_id, stop_order)
);

-- NATIONAL RAIL SEATS (避開 SQL 保留字 row/column)
CREATE TABLE national_rail_seats (
    schedule_id    VARCHAR(20) NOT NULL REFERENCES national_rail_schedules(schedule_id),
    seat_id        VARCHAR(10) NOT NULL,
    coach          CHAR(1)     NOT NULL CHECK (coach IN ('A','B')),
    fare_class     VARCHAR(10) NOT NULL CHECK (fare_class IN ('standard','first')),
    row_number     INTEGER     NOT NULL,
    column_letter  CHAR(1)     NOT NULL,
    PRIMARY KEY (schedule_id, seat_id)
);

-- BOOKINGS / TRIPS
CREATE TABLE national_rail_bookings (
    booking_id               VARCHAR(20) PRIMARY KEY,
    user_id                  VARCHAR(10) REFERENCES users(user_id),
    schedule_id              VARCHAR(20) REFERENCES national_rail_schedules(schedule_id),
    origin_station_id        VARCHAR(10) REFERENCES national_rail_stations(station_id),
    destination_station_id   VARCHAR(10) REFERENCES national_rail_stations(station_id),
    travel_date              DATE NOT NULL,
    departure_time           TIME,
    ticket_type              VARCHAR(20) CHECK (ticket_type IN ('single','return')),
    fare_class               VARCHAR(10) CHECK (fare_class IN ('standard','first')),
    coach                    CHAR(1),
    seat_id                  VARCHAR(10),
    stops_travelled          INTEGER,
    amount_usd               NUMERIC(10,2),
    status                   VARCHAR(20) CHECK (status IN ('confirmed','completed','cancelled')),
    booked_at                TIMESTAMPTZ,
    travelled_at             TIMESTAMPTZ
);

CREATE TABLE metro_travel_history (
    trip_id                  VARCHAR(20) PRIMARY KEY,
    user_id                  VARCHAR(10) REFERENCES users(user_id),
    schedule_id              VARCHAR(20) REFERENCES metro_schedules(schedule_id),
    origin_station_id        VARCHAR(10) REFERENCES metro_stations(station_id),
    destination_station_id   VARCHAR(10) REFERENCES metro_stations(station_id),
    travel_date              DATE NOT NULL,
    ticket_type              VARCHAR(20) CHECK (ticket_type IN ('single','day_pass')),
    day_pass_ref             VARCHAR(20) REFERENCES metro_travel_history(trip_id),
    stops_travelled          INTEGER,
    amount_usd               NUMERIC(10,2),
    status                   VARCHAR(20) CHECK (status IN ('completed','cancelled')),
    purchased_at             TIMESTAMPTZ,
    travelled_at             TIMESTAMPTZ
);

-- PAYMENTS / FEEDBACK  (polymorphic 用 transaction_type + CHECK 約束防錯)
CREATE TABLE payments (
    payment_id        VARCHAR(20) PRIMARY KEY,
    booking_id        VARCHAR(20) NOT NULL,
    transaction_type  VARCHAR(10) NOT NULL CHECK (transaction_type IN ('NR','Metro')),
    amount_usd        NUMERIC(10,2) NOT NULL,
    method            VARCHAR(30) CHECK (method IN ('credit_card','debit_card','ewallet')),
    status            VARCHAR(30) CHECK (status IN ('paid','refunded')),
    paid_at           TIMESTAMPTZ,
    CONSTRAINT chk_payment_booking_prefix CHECK (
        (transaction_type = 'NR'    AND booking_id LIKE 'BK%') OR
        (transaction_type = 'Metro' AND booking_id LIKE 'MT%')
    )
);

CREATE TABLE feedback (
    feedback_id       VARCHAR(20) PRIMARY KEY,
    booking_id        VARCHAR(20) NOT NULL,
    transaction_type  VARCHAR(10) NOT NULL CHECK (transaction_type IN ('NR','Metro')),
    user_id           VARCHAR(10) REFERENCES users(user_id),
    rating            INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment           TEXT,
    submitted_at      TIMESTAMPTZ,
    CONSTRAINT chk_feedback_booking_prefix CHECK (
        (transaction_type = 'NR'    AND booking_id LIKE 'BK%') OR
        (transaction_type = 'Metro' AND booking_id LIKE 'MT%')
    )
);
```

## Agreed Graph Schema

<!-- ============================================================
  FILL THIS IN after your team agrees on Neo4j node labels and
  relationship types.
  ============================================================ -->

```
Node labels:
- TODO

Relationship types:
- TODO

Key properties:
- TODO
```

## Function Signatures We Are Implementing

These are fixed contracts. AI-generated code must match these signatures exactly.

### Relational (`databases/relational/queries.py`)

```python
# Read-only
def query_national_rail_availability(origin_id: str, destination_id: str, travel_date: Optional[str] = None) -> list[dict]: ...
def query_national_rail_fare(schedule_id: str, fare_class: str, stops_travelled: int) -> Optional[dict]: ...
def query_metro_schedules(origin_id: str, destination_id: str) -> list[dict]: ...
def query_metro_fare(schedule_id: str, stops_travelled: int) -> Optional[dict]: ...
def query_available_seats(schedule_id: str, travel_date: str, fare_class: str) -> list[dict]: ...
def query_user_profile(user_email: str) -> Optional[dict]: ...
def query_user_bookings(user_email: str) -> dict: ...  # returns {"national_rail": [...], "metro": [...]}
def query_payment_info(booking_id: str) -> Optional[dict]: ...

# Write operations
def execute_booking(user_id, schedule_id, origin_station_id, destination_station_id, travel_date, fare_class, seat_id, ticket_type="single") -> tuple[bool, dict | str]: ...
def execute_cancellation(booking_id: str, user_id: str) -> tuple[bool, dict | str]: ...

# Auth
def register_user(email, first_name, surname, year_of_birth, password, secret_question, secret_answer) -> tuple[bool, str]: ...
def login_user(email: str, password: str) -> Optional[dict]: ...
def get_user_secret_question(email: str) -> Optional[str]: ...
def verify_secret_answer(email: str, answer: str) -> bool: ...
def update_password(email: str, new_password: str) -> bool: ...
```

### Graph (`databases/graph/queries.py`)

```python
def query_shortest_route(origin_id: str, destination_id: str, network: str = "auto") -> dict: ...
def query_cheapest_route(origin_id: str, destination_id: str, network: str = "auto", fare_class: str = "standard") -> dict: ...
def query_alternative_routes(origin_id, destination_id, avoid_station_id, network="auto", max_routes=3) -> list[list[dict]]: ...
def query_interchange_path(origin_id: str, destination_id: str) -> dict: ...
def query_delay_ripple(delayed_station_id: str, hops: int = 2) -> list[dict]: ...
def query_station_connections(station_id: str) -> list[dict]: ...
```

## Team Decisions Log

<!-- Add entries as you make decisions. Format: "Decision: X. Why: Y." -->

### Schema 整合決議 (2026-06-01)

- **Decision:** `users` 採張恩家版本(完整 10 欄)。**Why:** Xan 漏掉 `secret_question`/`secret_answer`/`registered_at`/`is_active`,會讓 `register_user()`、`get_user_secret_question()`、`verify_secret_answer()` 無法實作。
- **Decision:** `payments` / `feedback` 用 polymorphic `transaction_type` 欄位 + CHECK 約束保證 `booking_id` 前綴 (BK / MT) 與類型一致。**Why:** 採 Xan 的多型概念但保留原始 `booking_id` 命名,seed 不需做欄位映射,還能用 CHECK 防止髒資料。
- **Decision:** stations 的 `lines` / `interchange_*_lines` 用 `TEXT[]` 直接存陣列,不拆 `station_lines` 子表。**Why:** 30 個車站、6 條線的規模拆子表是過度設計,PostgreSQL 原生陣列查詢同樣方便。
- **Decision:** **不**建立 `station_adjacent` 表。**Why:** 相鄰站關係是 Neo4j 的職責,DATA_DICTIONARY_RELATIONAL_3.md 明確標注此欄位不入 PostgreSQL,張恩家方案在這裡是設計錯誤。
- **Decision:** 兩個 stations 表互為外鍵不設嚴格 FK 約束。**Why:** 互相參照會出現雞生蛋問題,seed 時無論先載哪邊都會違反約束。
- **Decision:** 國鐵票價攤平成 4 個欄位 (`fare_standard_base_usd` 等),不另開 `fare_classes` 子表。**Why:** 只有 standard / first 兩種等級且固定,攤平比子表簡潔且 query 不需 JOIN。
- **Decision:** `national_rail_schedule_stops` / `metro_schedule_stops` 拆子表 + `is_passed_through` BOOLEAN 標記快車經過不停的站。**Why:** 採 Xan 的子表設計,順序查詢比 JSONB 容易;同時把 `passed_through_stations` 整合進來,不需另開第三張子表。
- **Decision:** `national_rail_seats` 把 `row` / `column` 改名為 `row_number` / `column_letter`。**Why:** `row` 是 SQL 保留字,`column` 與 SQL 語意衝突,改名最安全。
- **Decision:** seats 表直接掛 `schedule_id`,不經 `layout_id` 中介層。**Why:** schedule 與 layout 是 1:1,中介層可省略。
- **Decision:** `metro_travel_history.day_pass_ref` 自參照同表的 `trip_id`。**Why:** 採 Xan 的 self-reference 設計,日票邏輯 (首購 vs 同日續用) 直接用 FK 表達。
- **Decision:** `national_rail_bookings` 保留 `stops_travelled` 與 `travelled_at` 兩個欄位 (兩家都漏)。**Why:** `stops_travelled` 是退款計算 (RF005) 的核心,`travelled_at` 用來判斷是否已搭乘,不能省。
- **Decision:** 加複合索引 `idx_nr_bookings_schedule_date_status` (schedule_id, travel_date, status)。**Why:** `query_available_seats()` 高頻使用,組合條件需要複合索引。
- [ ] Graph schema: TODO — add your node label and relationship type decisions here

## Prompts That Worked

<!-- Share prompts that produced good output so teammates can reuse them. -->

### Schema design prompt that worked:
```
TODO — add a prompt here after your schema design workshop
```

### Query implementation prompt that worked:
```
TODO — add after implementing your first function
```
