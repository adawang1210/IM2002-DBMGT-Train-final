# 📖 資料字典 — train-mock-data/

本文件說明 `train-mock-data/` 中每個 JSON 檔案的欄位定義與用途。

---

## 🚇 metro_stations.json

> 地鐵車站主檔，共 20 筆（MS01–MS20）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `station_id` | string | 車站唯一識別碼，如 `"MS01"` |
| `name` | string | 車站名稱，如 `"Central Square"` |
| `lines` | string[] | 所屬地鐵路線，如 `["M1", "M2"]` |
| `is_interchange_metro` | boolean | 是否為地鐵轉乘站（多條線交會） |
| `interchange_metro_lines` | string[] | 可轉乘的地鐵路線清單 |
| `is_interchange_national_rail` | boolean | 是否可轉乘國鐵 |
| `interchange_national_rail_station_id` | string \| null | 對應的國鐵車站 ID，無則為 `null` |
| `adjacent_stations` | object[] | 相鄰車站清單（⚠️ 此欄位用於 Neo4j 圖形，不存入 PostgreSQL） |

**`adjacent_stations` 子欄位：**

| 欄位 | 型別 | 說明 |
|------|------|------|
| `station_id` | string | 相鄰車站 ID |
| `line` | string | 連接的路線 |
| `travel_time_min` | integer | 兩站間行車時間（分鐘） |

---

## 🚄 national_rail_stations.json

> 國鐵車站主檔，共 10 筆（NR01–NR10）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `station_id` | string | 車站唯一識別碼，如 `"NR01"` |
| `name` | string | 車站名稱，如 `"Central Station"` |
| `lines` | string[] | 所屬國鐵路線，如 `["NR1", "NR2"]` |
| `is_interchange_national_rail` | boolean | 是否為國鐵轉乘站（多條國鐵線交會） |
| `interchange_national_rail_lines` | string[] | 可轉乘的國鐵路線清單 |
| `is_interchange_metro` | boolean | 是否可轉乘地鐵 |
| `interchange_metro_station_id` | string \| null | 對應的地鐵車站 ID，無則為 `null` |
| `adjacent_stations` | object[] | 相鄰車站清單（⚠️ 用於 Neo4j，不存入 PostgreSQL） |

**轉乘點：** NR01↔MS01、NR03↔MS07、NR07↔MS15

---

## 🚇 metro_schedules.json

> 地鐵時刻表，共 8 筆（M1–M4 各雙向）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `schedule_id` | string | 時刻表 ID，如 `"MS_SCH01"` |
| `line` | string | 路線：`"M1"` / `"M2"` / `"M3"` / `"M4"` |
| `direction` | string | 方向：`northbound` / `southbound` / `eastbound` / `westbound` |
| `origin_station_id` | string | 起點站 ID |
| `destination_station_id` | string | 終點站 ID |
| `stops_in_order` | string[] | 停靠站有序陣列（含起訖站） |
| `first_train_time` | string | 首班車時間，格式 `"HH:MM"` |
| `last_train_time` | string | 末班車時間 |
| `travel_time_from_origin_min` | object | 從起點到各站的累計行車時間（分鐘），key=站ID |
| `base_fare_usd` | number | 基本票價（美元），統一 `0.80` |
| `per_stop_rate_usd` | number | 每站加收，統一 `0.30` |
| `frequency_min` | integer | 發車間隔（分鐘）：M1=5, M2=6, M3=8, M4=7 |
| `operates_on` | string[] | 營運日，如 `["mon","tue",...,"sun"]` |

> 💰 **票價公式：** `total = base_fare_usd + per_stop_rate_usd × stops_travelled`

---

## 🚄 national_rail_schedules.json

> 國鐵時刻表，共 8 筆（普通車 4 筆 + 快車 4 筆）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `schedule_id` | string | 時刻表 ID，如 `"NR_SCH01"` |
| `line` | string | 路線：`"NR1"` 或 `"NR2"` |
| `service_type` | string | 服務類型：`"normal"`（普通車）或 `"express"`（快車） |
| `direction` | string | 方向：`northbound` / `southbound` / `eastbound` / `westbound` |
| `origin_station_id` | string | 起點站 ID |
| `destination_station_id` | string | 終點站 ID |
| `stops_in_order` | string[] | 實際停靠站有序陣列（快車跳站） |
| `passed_through_stations` | string[] | 快車經過但不停的站（僅 express 有） |
| `first_train_time` | string | 首班車時間 |
| `last_train_time` | string | 末班車時間 |
| `travel_time_from_origin_min` | object | 從起點到各停靠站的累計行車時間 |
| `fare_classes` | object | 票價結構（見下方子表） |
| `frequency_min` | integer | 發車間隔：普通車 30/45 分鐘，快車 60/90 分鐘 |
| `operates_on` | string[] | 營運日（快車僅平日 mon–fri） |

**`fare_classes` 子結構：**

| 等級 | `base_fare_usd` | `per_stop_rate_usd` | 說明 |
|------|-----------------|---------------------|------|
| `standard`（普通車） | 2.50 | 1.50 | 標準艙 |
| `first`（普通車） | 4.00 | 2.50 | 頭等艙 |
| `standard`（快車） | 6.60 | 1.80 | 快車標準艙（較貴） |
| `first`（快車） | 10.80 | 3.00 | 快車頭等艙 |

> 💰 **票價公式：** `total = base_fare_usd + per_stop_rate_usd × stops_travelled`

---

## 💺 national_rail_seat_layouts.json

> 國鐵座位配置，共 4 筆（僅普通車 NR_SCH01–04）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `layout_id` | string | 配置 ID，如 `"SL01"` |
| `schedule_id` | string | 對應的時刻表 ID |
| `coaches` | object[] | 車廂陣列 |

**`coaches` 子欄位：**

| 欄位 | 型別 | 說明 |
|------|------|------|
| `coach` | string | 車廂代號：`"A"`（頭等）或 `"B"`（標準） |
| `fare_class` | string | 票價等級：`"first"` 或 `"standard"` |
| `seats` | object[] | 座位陣列 |

**`seats` 子欄位：**

| 欄位 | 型別 | 說明 |
|------|------|------|
| `seat_id` | string | 座位 ID，如 `"A01"`、`"B05"` |
| `row` | integer | 排數 |
| `column` | string | 欄位：`"A"` / `"B"` / `"C"` |

> 📐 **座位數量：** A 車廂 = 6 席（3排×2欄），B 車廂 = 12 席（4排×3欄），每班次共 18 席

---

## 👤 registered_users.json

> 註冊使用者，共 20 筆（RU01–RU20）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `user_id` | string | 使用者 ID，如 `"RU01"` |
| `full_name` | string | 全名，如 `"Alice Tan"` |
| `email` | string | 電子郵件（登入帳號） |
| `password` | string | 密碼（⚠️ 教學用明文，正式環境應用 argon2/bcrypt 雜湊） |
| `phone` | string | 電話號碼 |
| `date_of_birth` | string | 出生日期，格式 `"YYYY-MM-DD"` |
| `secret_question` | string | 密碼重設用安全問題 |
| `secret_answer` | string | 安全問題答案 |
| `registered_at` | string | 註冊時間，ISO 8601 |
| `is_active` | boolean | 帳號是否啟用（RU05、RU12 為 `false`） |

---

## 🎫 bookings.json

> 國鐵訂票記錄，共 20 筆（BK001–BK020）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `booking_id` | string | 訂票 ID，如 `"BK001"` |
| `user_id` | string | 訂票使用者 ID |
| `schedule_id` | string | 對應時刻表 ID |
| `origin_station_id` | string | 出發站 ID |
| `destination_station_id` | string | 到達站 ID |
| `travel_date` | string | 旅行日期，`"YYYY-MM-DD"` |
| `departure_time` | string | 出發時間，`"HH:MM"` |
| `ticket_type` | string | 票種：`"single"`（單程）/ `"return"`（來回） |
| `fare_class` | string | 等級：`"standard"` / `"first"` |
| `coach` | string | 車廂：`"A"` / `"B"` |
| `seat_id` | string | 座位 ID，如 `"B05"` |
| `stops_travelled` | integer | 經過站數（用於票價計算） |
| `amount_usd` | number | 實付金額（美元） |
| `status` | string | 狀態：`"confirmed"` / `"completed"` / `"cancelled"` |
| `booked_at` | string | 訂票時間，ISO 8601 |
| `travelled_at` | string \| null | 實際搭乘時間，未搭乘為 `null` |

> 📌 **狀態說明：** `confirmed`=已訂未搭、`completed`=已完成旅程、`cancelled`=已取消

---

## 🚇 metro_travel_history.json

> 地鐵行程記錄，共 24 筆（MT001–MT024）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `trip_id` | string | 行程 ID，如 `"MT001"` |
| `user_id` | string | 使用者 ID |
| `schedule_id` | string | 對應地鐵時刻表 ID |
| `origin_station_id` | string | 出發站 ID |
| `destination_station_id` | string | 到達站 ID |
| `travel_date` | string | 旅行日期 |
| `ticket_type` | string | 票種：`"single"`（單程）/ `"day_pass"`（日票） |
| `day_pass_ref` | string \| null | 日票參考（見下方說明） |
| `stops_travelled` | integer \| null | 經過站數（日票為 `null`） |
| `amount_usd` | number | 支付金額（使用已購日票為 `0.00`） |
| `status` | string | 狀態：`"completed"` / `"cancelled"` |
| `purchased_at` | string \| null | 購票時間（使用已購日票為 `null`） |
| `travelled_at` | string \| null | 搭乘時間（取消為 `null`） |

> 🎫 **日票邏輯：**
> - 首次購買：`day_pass_ref = null`，`amount_usd = 5.00`
> - 同日後續使用：`day_pass_ref = "MT002"`（指向首次購買），`amount_usd = 0.00`，`purchased_at = null`

---

## 💳 payments.json

> 付款記錄，共 40 筆（PM001–PM040），涵蓋國鐵和地鐵

| 欄位 | 型別 | 說明 |
|------|------|------|
| `payment_id` | string | 付款 ID，如 `"PM001"` |
| `booking_id` | string | 對應的交易 ID（`"BK"`=國鐵訂票，`"MT"`=地鐵行程） |
| `amount_usd` | number | 付款金額（美元） |
| `method` | string | 付款方式：`"credit_card"` / `"debit_card"` / `"ewallet"` |
| `status` | string | 狀態：`"paid"`（已付）/ `"refunded"`（已退款） |
| `paid_at` | string | 付款時間，ISO 8601 |

> 📌 **觀察：** `refunded` 對應被取消的訂票/行程（如 BK003→PM005、MT006→PM012）

---

## ⭐ feedback.json

> 旅程回饋，共 30 筆（FB001–FB030）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `feedback_id` | string | 回饋 ID，如 `"FB001"` |
| `booking_id` | string | 對應的交易 ID（`"BK"` 或 `"MT"` 開頭） |
| `user_id` | string | 提交者 ID |
| `rating` | integer | 評分：1–5 |
| `comment` | string \| null | 文字評論，可為空 |
| `submitted_at` | string | 提交時間，ISO 8601 |

---

## 📋 政策文件（用於 pgvector RAG，共 4 個檔案）

以下四個檔案結構相同，被嵌入向量資料庫供語意搜尋：

### ticket_types.json — 票種定義

### refund_policy.json — 退款政策

### booking_rules.json — 訂票規則

### travel_policies.json — 旅行政策

| 欄位 | 型別 | 說明 |
|------|------|------|
| `policy_id` | string | 政策 ID，如 `"TT001"`、`"RF001"`、`"BR001"`、`"TP001"` |
| `title` | string | 政策標題 |
| `category` | string | 分類：`"ticket_type"` / `"refund"` / `"booking_rule"` / `"travel_policy"` |
| `content` | string | 完整政策內容（長文字，被轉為向量嵌入） |

---

## 🔗 資料關聯圖

```
┌─────────────────────┐
│  registered_users   │
│  (RU01–RU20)        │
└──────┬──────────────┘
       │ user_id
       ├────────────────────────┬──────────────────────┐
       ▼                        ▼                      ▼
┌──────────────┐    ┌────────────────────┐    ┌──────────────┐
│   bookings   │    │ metro_travel_hist. │    │   feedback   │
│ (BK001–020)  │    │   (MT001–024)      │    │ (FB001–030)  │
└──────┬───────┘    └──────┬─────────────┘    └──────────────┘
       │                   │
       │ booking_id        │ trip_id
       ▼                   ▼
┌──────────────────────────────────┐
│           payments               │
│          (PM001–040)             │
└──────────────────────────────────┘

┌────────────────────────┐         ┌─────────────────────┐
│ national_rail_schedules│◄────────│ national_rail_seat_  │
│    (NR_SCH01–08)       │ sched.  │    layouts (SL01–04) │
└────────────┬───────────┘         └─────────────────────┘
             │ schedule_id
             ▼
      bookings.schedule_id

┌────────────────────┐
│  metro_schedules   │◄──── metro_travel_history.schedule_id
│  (MS_SCH01–08)     │
└────────────────────┘

┌────────────────────┐    ┌──────────────────────────┐
│  metro_stations    │    │  national_rail_stations   │
│  (MS01–MS20)       │    │  (NR01–NR10)             │
└────────────────────┘    └──────────────────────────┘
  ▲ 被 schedules、bookings、travel_history 引用為起訖站
```
