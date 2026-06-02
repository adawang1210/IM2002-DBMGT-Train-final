# Xan
## 🚆 Train Ticket Booking System — Relational Schema Design

本報告基於系統需求與原始 JSON 資料，設計出對應的關聯式資料庫結構 (Relational Schema)。

系統涵蓋兩種不同的交通業務邏輯：「國家鐵路 (National Rail)」著重於提前劃位與對號座設計；「城市地鐵 (City Metro)」則著重於進出站刷卡與一日票的綁定機制。

---

## 📂 第一部分：資料表定義與關聯設計 (Schema Definition)

### 👤 1. 使用者與金流模組 (Users & Payments)

#### Users（使用者資料表）

| 欄位名稱 | 型別 | 說明 |
|---|---|---|
| `user_id` | PK, VARCHAR | 唯一帳號 ID |
| `full_name` | VARCHAR | 姓名 |
| `email` | VARCHAR | 電子郵件 |
| `password` | VARCHAR | 密碼 |
| `phone` | VARCHAR | 聯絡電話 |
| `date_of_birth` | DATE | 出生年月日 |

#### Payments（付款紀錄表）

| 欄位名稱 | 型別 | 說明 |
|---|---|---|
| `payment_id` | PK, VARCHAR | 付款編號 |
| `reference_id` | FK, VARCHAR | 對應到 Booking ID 或 Trip ID（多型關聯） |
| `transaction_type` | ENUM | 用來區分是國鐵 (`NR`) 還是地鐵 (`Metro`) |
| `amount_usd` | DECIMAL | 交易金額 |
| `method` | VARCHAR | 支付方式（credit_card, ewallet 等） |
| `status` | VARCHAR | 交易狀態（paid, refunded） |
| `paid_at` | TIMESTAMP | 付款時間 |

---

### 🚆 2. 國家鐵路系統 (National Rail - 需劃位、有班次)

#### NR_Stations（國鐵車站）

| 欄位名稱 | 型別 | 說明 |
|---|---|---|
| `station_id` | PK, VARCHAR | 國鐵車站 ID |
| `name` | VARCHAR | 站名 |
| `is_interchange_national_rail` | BOOLEAN | 是否為國鐵轉乘站 |
| `is_interchange_metro` | BOOLEAN | 是否為地鐵轉乘站 |
| `interchange_metro_station_id` | FK, VARCHAR | 對應 `Metro_Stations.station_id` |

#### NR_Schedules（國鐵時刻表）

| 欄位名稱 | 型別 | 說明 |
|---|---|---|
| `schedule_id` | PK, VARCHAR | 班次 ID |
| `line` | VARCHAR | 路線（如 NR1, NR2） |
| `service_type` | VARCHAR | 服務類型（normal, express） |
| `direction` | VARCHAR | 行駛方向 |
| `origin_station_id` | FK, VARCHAR | 起點站 ID |
| `destination_station_id` | FK, VARCHAR | 終點站 ID |
| `first_train_time` | TIME | 首班車時間 |
| `last_train_time` | TIME | 末班車時間 |

#### NR_Schedule_Stops（國鐵停靠站明細 - 將 Array 正規化）

| 欄位名稱 | 型別 | 說明 |
|---|---|---|
| `schedule_id` | PK/FK, VARCHAR | 班次 ID |
| `stop_order` | PK, INT | 停靠順序 |
| `station_id` | FK, VARCHAR | 車站 ID |
| `travel_time_from_origin_min` | INT | 距離起點站所需時間 |

#### NR_Seats（國鐵座位配置）

| 欄位名稱 | 型別 | 說明 |
|---|---|---|
| `schedule_id` | PK/FK, VARCHAR | 班次 ID |
| `coach` | PK, VARCHAR | 車廂號碼 |
| `seat_id` | PK, VARCHAR | 座位號碼 |
| `fare_class` | VARCHAR | 艙等（standard, first） |

#### NR_Bookings（國鐵訂票紀錄）

| 欄位名稱 | 型別 | 說明 |
|---|---|---|
| `booking_id` | PK, VARCHAR | 訂單編號 |
| `user_id` | FK, VARCHAR | 訂票使用者 ID |
| `schedule_id` | FK, VARCHAR | 班次 ID |
| `origin_station_id` | FK, VARCHAR | 出發站 ID |
| `destination_station_id` | FK, VARCHAR | 抵達站 ID |
| `travel_date` | DATE | 乘車日期 |
| `ticket_type` | VARCHAR | 票種（single, return） |
| `fare_class` | VARCHAR | 艙等 |
| `coach` | VARCHAR | 劃位車廂 |
| `seat_id` | VARCHAR | 劃位座位 |
| `amount_usd` | DECIMAL | 訂單金額 |
| `status` | VARCHAR | 訂單狀態（completed, cancelled, confirmed） |

---

### 🚇 3. 城市地鐵系統 (City Metro - 刷卡進出、無對號)

#### Metro_Stations（地鐵車站）

| 欄位名稱 | 型別 | 說明 |
|---|---|---|
| `station_id` | PK, VARCHAR | 地鐵車站 ID |
| `name` | VARCHAR | 站名 |
| `is_interchange_metro` | BOOLEAN | 是否為地鐵轉乘站 |
| `is_interchange_national_rail` | BOOLEAN | 是否為國鐵轉乘站 |
| `interchange_national_rail_station_id` | FK, VARCHAR | 對應 `NR_Stations.station_id` |

#### Metro_Schedules（地鐵路線與費率）

| 欄位名稱 | 型別 | 說明 |
|---|---|---|
| `schedule_id` | PK, VARCHAR | 路線 ID |
| `line` | VARCHAR | 路線（如 M1, M2） |
| `direction` | VARCHAR | 行駛方向 |
| `base_fare_usd` | DECIMAL | 基本票價 |
| `per_stop_rate_usd` | DECIMAL | 每站加價金額 |

#### Metro_Trips（地鐵搭乘紀錄）

| 欄位名稱 | 型別 | 說明 |
|---|---|---|
| `trip_id` | PK, VARCHAR | 旅程紀錄 ID |
| `user_id` | FK, VARCHAR | 搭乘使用者 ID |
| `schedule_id` | FK, VARCHAR | 路線 ID |
| `origin_station_id` | FK, VARCHAR | 進站車站 ID |
| `destination_station_id` | FK, VARCHAR | 出站車站 ID |
| `day_pass_ref` | FK, VARCHAR | 自我參照（Self-referencing），指向綁定的一日票 `trip_id` |
| `ticket_type` | VARCHAR | 票種（single, day_pass） |
| `stops_travelled` | INT | 經過站數 |
| `amount_usd` | DECIMAL | 扣款金額 |
| `status` | VARCHAR | 狀態（completed, cancelled） |

---

### 📝 4. 附屬資訊 (Feedback & General Rules)

#### Feedback（乘客意見回饋）

| 欄位名稱 | 型別 | 說明 |
|---|---|---|
| `feedback_id` | PK, VARCHAR | 回饋編號 |
| `user_id` | FK, VARCHAR | 使用者 ID |
| `reference_id` | FK, VARCHAR | 對應 Booking ID 或 Trip ID |
| `rating` | INT | 評分（1–5） |
| `comment` | TEXT | 文字評論 |
| `submitted_at` | TIMESTAMP | 提交時間 |

> **備註：** `Ticket_Types`、`Refund_Policies`、`Travel_Policies` 等業務規則，實務上常以靜態 JSON 存入 `System_Configs` 資料表，或拆分為獨立的 Lookup Tables，依系統變更頻率而定。

---

## 📊 第二部分：ER Diagram（實體關聯圖）

```mermaid
erDiagram
    USERS {
        varchar user_id PK
        varchar full_name
        varchar email
    }
    PAYMENTS {
        varchar payment_id PK
        varchar reference_id FK "BK001 or MT001"
        decimal amount_usd
        varchar status
    }
    NR_STATIONS {
        varchar station_id PK
        varchar name
        varchar interchange_metro_id FK
    }
    METRO_STATIONS {
        varchar station_id PK
        varchar name
        varchar interchange_nr_id FK
    }
    NR_SCHEDULES {
        varchar schedule_id PK
        varchar line
        varchar service_type
    }
    NR_SEATS {
        varchar schedule_id PK FK
        varchar coach PK
        varchar seat_id PK
        varchar fare_class
    }
    NR_BOOKINGS {
        varchar booking_id PK
        varchar user_id FK
        varchar schedule_id FK
        varchar origin_station_id FK
        varchar seat_id
        varchar status
    }
    METRO_TRIPS {
        varchar trip_id PK
        varchar user_id FK
        varchar schedule_id FK
        varchar origin_station_id FK
        varchar day_pass_ref FK "Self-referencing"
        varchar ticket_type
    }
    FEEDBACK {
        varchar feedback_id PK
        varchar user_id FK
        varchar reference_id FK
        int rating
    }

    USERS ||--o{ NR_BOOKINGS : "makes"
    USERS ||--o{ METRO_TRIPS : "makes"
    USERS ||--o{ FEEDBACK : "writes"

    NR_BOOKINGS ||--o| PAYMENTS : "paid by"
    METRO_TRIPS ||--o| PAYMENTS : "paid by"

    NR_SCHEDULES ||--o{ NR_BOOKINGS : "has"
    NR_SCHEDULES ||--o{ NR_SEATS : "configures"

    NR_STATIONS ||--o{ NR_BOOKINGS : "origin / destination"
    METRO_STATIONS ||--o{ METRO_TRIPS : "origin / destination"

    METRO_TRIPS |o--o{ METRO_TRIPS : "uses day_pass_ref"
```