# 張恩嘉
## 🚆 Train Ticket Booking System — Relational Schema Design

---

## 📂 資料表定義 (Schema Definition)

### 👤 1. Users（使用者資料表）

| 欄位名稱 | 資料型態 | 說明 |
|---|---|---|
| `user_id` | VARCHAR(10) | 使用者編號（PK） |
| `full_name` | VARCHAR(100) | 使用者姓名 |
| `email` | VARCHAR(100) | 電子郵件 |
| `password` | VARCHAR(100) | 密碼 |
| `phone` | VARCHAR(20) | 電話 |
| `date_of_birth` | DATE | 出生日期 |
| `secret_question` | TEXT | 安全問題 |
| `secret_answer` | TEXT | 安全答案 |
| `registered_at` | TIMESTAMP | 註冊時間 |
| `is_active` | BOOLEAN | 帳號是否啟用 |

---

### 🚇 2. Metro_Stations（地鐵車站）

| 欄位名稱 | 資料型態 | 說明 |
|---|---|---|
| `station_id` | VARCHAR(10) | 車站編號（PK） |
| `name` | VARCHAR(100) | 車站名稱 |
| `is_interchange_metro` | BOOLEAN | 是否為地鐵轉乘站 |
| `is_interchange_national_rail` | BOOLEAN | 是否可轉乘國鐵 |
| `interchange_national_rail_station_id` | VARCHAR(10) | 對應國鐵車站 |

---

### 🚇 3. Metro_Station_Lines（地鐵車站路線對應）

| 欄位名稱 | 資料型態 | 說明 |
|---|---|---|
| `station_id` | VARCHAR(10) | 車站編號（PK, FK） |
| `line` | VARCHAR(10) | 路線名稱（PK） |

---

### 🚇 4. Metro_Station_Adjacency（地鐵相鄰站距）

| 欄位名稱 | 資料型態 | 說明 |
|---|---|---|
| `station_id` | VARCHAR(10) | 車站編號（PK） |
| `adjacent_station_id` | VARCHAR(10) | 相鄰車站（PK） |
| `line` | VARCHAR(10) | 路線 |
| `travel_time_min` | INT | 行駛時間（分鐘） |

---

### 🚆 5. NR_Stations（國鐵車站）

| 欄位名稱 | 資料型態 | 說明 |
|---|---|---|
| `station_id` | VARCHAR(10) | 車站編號（PK） |
| `name` | VARCHAR(100) | 車站名稱 |
| `is_interchange_national_rail` | BOOLEAN | 是否為國鐵轉乘站 |
| `interchange_metro_station_id` | VARCHAR(10) | 對應地鐵車站 |

---

### 🚇 6. Metro_Schedules（地鐵班次與費率）

| 欄位名稱 | 資料型態 | 說明 |
|---|---|---|
| `schedule_id` | VARCHAR(20) | 班次編號（PK） |
| `line` | VARCHAR(10) | 路線 |
| `direction` | VARCHAR(20) | 行駛方向 |
| `origin_station_id` | VARCHAR(10) | 起點站 |
| `destination_station_id` | VARCHAR(10) | 終點站 |
| `first_train_time` | TIME | 首班車時間 |
| `last_train_time` | TIME | 末班車時間 |
| `base_fare_usd` | DECIMAL(5,2) | 基本票價 |
| `per_stop_rate_usd` | DECIMAL(5,2) | 每站票價 |
| `frequency_min` | INT | 發車間隔（分鐘） |

---

### 🚆 7. NR_Schedules（國鐵班次時刻表）

| 欄位名稱 | 資料型態 | 說明 |
|---|---|---|
| `schedule_id` | VARCHAR(20) | 班次編號（PK） |
| `line` | VARCHAR(10) | 路線 |
| `service_type` | VARCHAR(20) | 服務類型 |
| `direction` | VARCHAR(20) | 行駛方向 |
| `origin_station_id` | VARCHAR(10) | 起點站 |
| `destination_station_id` | VARCHAR(10) | 終點站 |
| `first_train_time` | TIME | 首班車時間 |
| `last_train_time` | TIME | 末班車時間 |
| `frequency_min` | INT | 發車間隔 |

---

### 🚆 8. NR_Seats（國鐵座位配置）

| 欄位名稱 | 資料型態 | 說明 |
|---|---|---|
| `seat_id` | VARCHAR(10) | 座位編號（PK） |
| `layout_id` | VARCHAR(20) | 座位配置編號 |
| `coach` | VARCHAR(10) | 車廂 |
| `row_number` | INT | 排數 |
| `column_letter` | VARCHAR(5) | 座位欄位 |

---

### 🎫 9. Ticket_Types（票種定義）

| 欄位名稱 | 資料型態 | 說明 |
|---|---|---|
| `ticket_type` | VARCHAR(20) | 票種編號（PK） |
| `display_name` | VARCHAR(100) | 票種名稱 |
| `description` | TEXT | 票種說明 |

---

### 🚆 10. NR_Bookings（國鐵訂票紀錄）

| 欄位名稱 | 資料型態 | 說明 |
|---|---|---|
| `booking_id` | VARCHAR(20) | 訂票編號（PK） |
| `user_id` | VARCHAR(10) | 使用者編號（FK） |
| `schedule_id` | VARCHAR(20) | 班次編號（FK） |
| `origin_station_id` | VARCHAR(10) | 起點站 |
| `destination_station_id` | VARCHAR(10) | 終點站 |
| `travel_date` | DATE | 搭乘日期 |
| `ticket_type` | VARCHAR(20) | 票種 |
| `fare_class` | VARCHAR(20) | 票價等級 |
| `coach` | VARCHAR(10) | 車廂 |
| `seat_id` | VARCHAR(10) | 座位 |
| `amount_usd` | DECIMAL(10,2) | 金額 |
| `status` | VARCHAR(20) | 訂票狀態 |
| `booked_at` | TIMESTAMP | 訂票時間 |

---

### 🚇 11. Metro_Trips（地鐵搭乘紀錄）

| 欄位名稱 | 資料型態 | 說明 |
|---|---|---|
| `trip_id` | VARCHAR(20) | 搭乘編號（PK） |
| `user_id` | VARCHAR(10) | 使用者編號（FK） |
| `schedule_id` | VARCHAR(20) | 班次編號（FK） |
| `origin_station_id` | VARCHAR(10) | 起點站 |
| `destination_station_id` | VARCHAR(10) | 終點站 |
| `travel_date` | DATE | 搭乘日期 |
| `ticket_type` | VARCHAR(20) | 票種 |
| `amount_usd` | DECIMAL(10,2) | 金額 |
| `status` | VARCHAR(20) | 狀態 |
| `travelled_at` | TIMESTAMP | 搭乘時間 |

---

### 💳 12. Payments（付款紀錄）

| 欄位名稱 | 資料型態 | 說明 |
|---|---|---|
| `payment_id` | VARCHAR(20) | 付款編號（PK） |
| `booking_id` | VARCHAR(20) | 訂票編號 |
| `amount_usd` | DECIMAL(10,2) | 金額 |
| `method` | VARCHAR(30) | 付款方式 |
| `status` | VARCHAR(30) | 付款狀態 |
| `paid_at` | TIMESTAMP | 付款時間 |

---

### 📋 13. Travel_Policies（旅行規則）

| 欄位名稱 | 資料型態 | 說明 |
|---|---|---|
| `policy_id` | VARCHAR(20) | 規則編號（PK） |
| `label` | VARCHAR(255) | 規則名稱 |
| `network_type` | VARCHAR(50) | 系統類型 |
| `service_type` | VARCHAR(50) | 服務類型 |
| `notes` | TEXT | 備註 |
| `exclusions` | TEXT | 不適用情況 |

---

### 💬 14. Feedback（乘客意見回饋）

| 欄位名稱 | 資料型態 | 說明 |
|---|---|---|
| `feedback_id` | VARCHAR(20) | 回饋編號（PK） |
| `booking_id` | VARCHAR(20) | 訂票編號 |
| `user_id` | VARCHAR(10) | 使用者編號（FK） |
| `rating` | INT | 評分 |
| `comment` | TEXT | 評論 |
| `submitted_at` | TIMESTAMP | 提交時間 |