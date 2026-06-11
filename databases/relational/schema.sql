-- ============================================================
--  TransitFlow PostgreSQL Schema
--  Seed data is loaded separately by: python skeleton/seed_postgres.py
--
--  TWO ROLES:
--    1. Relational  → dual-network transit data (designed below)
--    2. Vector      → policy documents for RAG (provided — do not modify)
--
--  Schema 整合三份資料字典後的最終決議
--  (詳見 train-mock-data/DATA_DICTIONARY_RELATIONAL/SCHEMA_COMPARISON_RELATIONAL.md)
--
--  原則：
--    1. 欄位完整度為先 → 兩家都不完整時直接從原始 JSON 取
--    2. 採用 Xan 的架構亮點 → polymorphic transaction_type、子表化 stops、self-reference
--    3. 加上業界最佳實踐 → CHECK 約束、複合索引、避開 SQL 保留字
--    4. station_adjacent 留給 Neo4j，不在這裡建表
--
--  Primary Key 設計說明：
--    本 schema 所有業務實體 PK (users, stations, schedules, bookings, seats, payments)
--    均採用 VARCHAR 而非 UUID 或 SERIAL。
--    原因：mock data JSON 已使用 human-readable ID (e.g. "RU01", "NR_SCH01", "BK-A1B2C3")，
--    直接採用相同型態可避免額外的 ID 映射表，並讓 seeder、agent、測試腳本得以使用
--    可讀的業務識別碼。唯一例外是 policy_documents 使用 SERIAL (為系統內部自動管理，
--    與業務 ID 無關)。
--    正式生產系統建議改用 UUID + 隨機生成，以防 ID 可預測性安全疑慮。
-- ============================================================


-- ============================================================
--  1. USERS
-- ============================================================

CREATE TABLE users (
    user_id          VARCHAR(10) PRIMARY KEY,
    full_name        VARCHAR(100) NOT NULL,
    email            VARCHAR(100) UNIQUE NOT NULL,
    -- bcrypt hash 固定 60 字元；使用 CHAR(60) 更精確但 VARCHAR(60) 也可接受。
    -- 原始設計為明文 (VARCHAR(100))，此欄已在 register_user / update_password
    -- 改用 bcrypt.hashpw() 存雜湊，login_user 改用 bcrypt.checkpw() 驗證。
    password         VARCHAR(60) NOT NULL,
    phone            VARCHAR(20),
    date_of_birth    DATE,
    secret_question  TEXT,
    secret_answer    TEXT,
    registered_at    TIMESTAMPTZ DEFAULT NOW(),
    -- 軟刪除 (Soft Delete)：停用帳號不硬刪除 user row，以保留歷史訂單關聯。
    -- 訂單/交易紀錄採「狀態欄位 (status = cancelled)」取代物理刪除，符合稅務與審計保留要求。
    is_active        BOOLEAN DEFAULT TRUE
);


-- ============================================================
--  2. STATIONS  (兩個 stations 表互相參照,不設嚴格 FK)
-- ============================================================

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


-- ============================================================
--  3. SCHEDULES + STOPS
-- ============================================================

-- 國鐵時刻表 ----------------------------------------------------
CREATE TABLE national_rail_schedules (
    schedule_id                  VARCHAR(20) PRIMARY KEY,
    line                         VARCHAR(10) NOT NULL,
    service_type                 VARCHAR(20) NOT NULL CHECK (service_type IN ('normal', 'express')),
    direction                    VARCHAR(20),
    origin_station_id            VARCHAR(10) REFERENCES national_rail_stations(station_id),
    destination_station_id       VARCHAR(10) REFERENCES national_rail_stations(station_id),
    first_train_time             TIME,
    last_train_time              TIME,
    -- 票價攤平成 4 欄 (參考 fare_classes JSON)
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
    is_passed_through             BOOLEAN DEFAULT FALSE,  -- 快車經過但不停的站
    PRIMARY KEY (schedule_id, stop_order)
);

CREATE INDEX idx_nr_schedule_stops_station ON national_rail_schedule_stops(station_id);

-- 地鐵時刻表 ----------------------------------------------------
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

CREATE INDEX idx_metro_schedule_stops_station ON metro_schedule_stops(station_id);


-- ============================================================
--  4. NATIONAL RAIL SEATS
--  注意：row 是 SQL 保留字 → row_number；column 改 column_letter
-- ============================================================

CREATE TABLE national_rail_seats (
    schedule_id    VARCHAR(20) NOT NULL REFERENCES national_rail_schedules(schedule_id),
    seat_id        VARCHAR(10) NOT NULL,
    coach          CHAR(1)     NOT NULL CHECK (coach IN ('A', 'B')),
    fare_class     VARCHAR(10) NOT NULL CHECK (fare_class IN ('standard', 'first')),
    row_number     INTEGER     NOT NULL,
    column_letter  CHAR(1)     NOT NULL,
    PRIMARY KEY (schedule_id, seat_id)
);


-- ============================================================
--  5. BOOKINGS / TRAVEL HISTORY
-- ============================================================

-- 國鐵訂票 -----------------------------------------------------
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

-- 加速座位可用性查詢 (query_available_seats 高頻使用)
CREATE INDEX idx_nr_bookings_schedule_date_status
    ON national_rail_bookings(schedule_id, travel_date, status);
CREATE INDEX idx_nr_bookings_user ON national_rail_bookings(user_id);

-- 地鐵搭乘紀錄 -------------------------------------------------
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

CREATE INDEX idx_metro_history_user ON metro_travel_history(user_id);
CREATE INDEX idx_metro_history_user_date ON metro_travel_history(user_id, travel_date);


-- ============================================================
--  6. PAYMENTS  (polymorphic：booking_id 同時指向 NR 或 Metro)
-- ============================================================

CREATE TABLE payments (
    payment_id        VARCHAR(20) PRIMARY KEY,
    booking_id        VARCHAR(20) NOT NULL,
    transaction_type  VARCHAR(10) NOT NULL CHECK (transaction_type IN ('NR', 'Metro')),
    amount_usd        NUMERIC(10,2) NOT NULL,
    method            VARCHAR(30) CHECK (method IN ('credit_card', 'debit_card', 'ewallet')),
    status            VARCHAR(30) CHECK (status IN ('paid', 'refunded')),
    paid_at           TIMESTAMPTZ,
    -- 確保 booking_id 前綴與 transaction_type 一致
    CONSTRAINT chk_payment_booking_prefix CHECK (
        (transaction_type = 'NR'    AND booking_id LIKE 'BK%') OR
        (transaction_type = 'Metro' AND booking_id LIKE 'MT%')
    )
);

CREATE INDEX idx_payments_booking_id ON payments(booking_id);


-- ============================================================
--  7. FEEDBACK  (polymorphic 同 payments)
-- ============================================================

CREATE TABLE feedback (
    feedback_id       VARCHAR(20) PRIMARY KEY,
    booking_id        VARCHAR(20) NOT NULL,
    transaction_type  VARCHAR(10) NOT NULL CHECK (transaction_type IN ('NR', 'Metro')),
    user_id           VARCHAR(10) REFERENCES users(user_id),
    rating            INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment           TEXT,
    submitted_at      TIMESTAMPTZ,
    CONSTRAINT chk_feedback_booking_prefix CHECK (
        (transaction_type = 'NR'    AND booking_id LIKE 'BK%') OR
        (transaction_type = 'Metro' AND booking_id LIKE 'MT%')
    )
);

CREATE INDEX idx_feedback_booking_id ON feedback(booking_id);
CREATE INDEX idx_feedback_user ON feedback(user_id);


-- ============================================================
--  VECTOR SCHEMA  (RAG / Help Desk) — do not modify
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS policy_documents (
    id          SERIAL       PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    category    VARCHAR(50)  NOT NULL,  -- 'refund', 'booking', 'conduct'
    content     TEXT         NOT NULL,
    -- 768-dim  → Ollama nomic-embed-text (default)
    -- 3072-dim → Gemini gemini-embedding-001
    -- If you switch LLM_PROVIDER to gemini, change to vector(3072) and reset the database.
    embedding   vector(768),
    source_file VARCHAR(200),
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- Index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS idx_policy_documents_embedding
    ON policy_documents USING hnsw (embedding vector_cosine_ops);
