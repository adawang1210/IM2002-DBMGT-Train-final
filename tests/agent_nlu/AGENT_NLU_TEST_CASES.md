# TransitFlow Agent — NLU 測資集 / NLU Test Set

> 由 TEAM_AI_WORKFLOW Template G / 範本 G 產出 (人工校對過 tool 名稱與已知世界資料一致)。
> 用法:把 `user_input` 餵進 `python -m skeleton.ui` 或直接呼叫 agent,逐筆比對 `expected_tool_calls`、
> `expected_answer_must_contain` / `must_not_contain`。Regression case 失敗時改程式,不要改測例。

## 摘要 / Summary

- 測例總數 / Total cases: **27**
- 中文 / 英文比例: **14 zh-TW / 13 en** (約 1:1)
- 類別分布 / Category distribution:
  - Routing: 3 · Availability: 3 · Fare: 3 · Booking flow: 4 · Cancellation: 2
  - User history: 2 · Policy: 4 · Disruption: 3 · Out-of-scope: 3
- 已知 bug regression: **T15** (45 分鐘延遲 / RF005_R1) · **T07** (`'null'` 字串日期) · **T11** (未登入訂票)

---

## 測試矩陣 / Test Matrix

### T01 · Routing · en

- requires_login: false
- user_input:
  > What's the fastest way from MS01 to MS14?
- expected_tool_calls:
  ```json
  [
    {"name": "find_route", "params": {"origin_id": "MS01", "destination_id": "MS14", "optimise_by": "time"}}
  ]
  ```
- expected_answer_must_contain: ["MS01", "MS14", "minutes"]
- expected_answer_must_not_contain: ["log in", "weather"]
- notes: 「fastest / quickest」必須觸發 find_route 而非 get_metro_fare。

### T02 · Routing · zh-TW

- requires_login: false
- user_input:
  > NR01 到 NR05 最便宜的走法是什麼?
- expected_tool_calls:
  ```json
  [
    {"name": "find_route", "params": {"origin_id": "NR01", "destination_id": "NR05", "optimise_by": "cost"}}
  ]
  ```
- expected_answer_must_contain: ["NR01", "NR05"]
- expected_answer_must_not_contain: ["請先登入", "天氣"]
- notes: 「最便宜」應對應 optimise_by=cost,不該誤判成 fare。

### T03 · Routing · en

- requires_login: false
- user_input:
  > How do I get from Central to Ferndale?
- expected_tool_calls:
  ```json
  [
    {"name": "find_route", "params": {"origin_id": "MS01", "destination_id": "MS15"}}
  ]
  ```
- expected_answer_must_contain: ["Central", "Ferndale"]
- expected_answer_must_not_contain: ["no route", "not found"]
- notes: 站名而非 ID 的口語輸入,要能解析成 MS01/MS15 (兩端都是地鐵側 interchange);也接受 NR01/NR07 cross-network 解析。

### T04 · Availability · en

- requires_login: false
- user_input:
  > What national rail trains run from NR01 to NR03 on 2026-06-01?
- expected_tool_calls:
  ```json
  [
    {"name": "check_national_rail_availability", "params": {"origin_id": "NR01", "destination_id": "NR03", "travel_date": "2026-06-01"}}
  ]
  ```
- expected_answer_must_contain: ["NR01", "NR03", "2026-06-01"]
- expected_answer_must_not_contain: ["error", "no schedules"]

### T05 · Availability · zh-TW

- requires_login: false
- user_input:
  > 看一下 MS01 到 MS09 有哪幾班地鐵
- expected_tool_calls:
  ```json
  [
    {"name": "check_metro_availability", "params": {"origin_id": "MS01", "destination_id": "MS09"}}
  ]
  ```
- expected_answer_must_contain: ["MS01", "MS09"]
- expected_answer_must_not_contain: ["登入", "找不到"]
- notes: 中文「看一下…幾班」屬於口語版的 availability,不要誤判成 fare。

### T06 · Availability · zh-TW

- requires_login: false
- user_input:
  > 幫我看 NR01 到 NR05
- expected_tool_calls:
  ```json
  [
    {"name": "check_national_rail_availability", "params": {"origin_id": "NR01", "destination_id": "NR05"}}
  ]
  ```
- expected_answer_must_contain: ["NR01", "NR05"]
- expected_answer_must_not_contain: ["error"]
- notes: 缺少日期、缺少動詞的最小指令; travel_date 應被省略或設成 null,絕對不能塞 "null" 字串。

### T07 · Availability · en — REGRESSION ('null' string defense)

- requires_login: false
- user_input:
  > Show me trains NR01 to NR05, no specific date
- expected_tool_calls:
  ```json
  [
    {"name": "check_national_rail_availability", "params": {"origin_id": "NR01", "destination_id": "NR05"}}
  ]
  ```
- expected_answer_must_contain: ["NR01", "NR05"]
- expected_answer_must_not_contain: ["InvalidDatetimeFormat", "invalid input syntax", "null"]
- notes: 即使 LLM 偷懶把 travel_date 填 "null" 字串,databases/relational/queries.py 的防呆已會把它正規化成 None,SQL 不該炸。

### T08 · Fare · zh-TW

- requires_login: false
- user_input:
  > MS01 到 MS09 票價多少?
- expected_tool_calls:
  ```json
  [
    {"name": "get_metro_fare", "params": {"origin_id": "MS01", "destination_id": "MS09"}}
  ]
  ```
- expected_answer_must_contain: ["MS01", "MS09", "USD"]
- expected_answer_must_not_contain: ["登入", "找不到"]
- notes: 「票價多少」是 fare 而非 routing,絕對不該觸發 find_route。

### T09 · Fare · en

- requires_login: false
- user_input:
  > How much does it cost from MS01 to MS14?
- expected_tool_calls:
  ```json
  [
    {"name": "get_metro_fare", "params": {"origin_id": "MS01", "destination_id": "MS14"}}
  ]
  ```
- expected_answer_must_contain: ["MS01", "MS14", "USD"]
- expected_answer_must_not_contain: ["fastest", "quickest"]

### T10 · Fare · en (two-step)

- requires_login: false
- user_input:
  > What's a first-class ticket from NR01 to NR05?
- expected_tool_calls:
  ```json
  [
    {"name": "check_national_rail_availability", "params": {"origin_id": "NR01", "destination_id": "NR05"}},
    {"name": "get_national_rail_fare", "params": {"schedule_id": "<from_previous_result>", "fare_class": "first", "stops_travelled": "<from_previous_result>"}}
  ]
  ```
- expected_answer_must_contain: ["first", "USD"]
- expected_answer_must_not_contain: ["standard only"]
- notes: 兩步驟 — schedule_id 與 stops_travelled 必須來自第一個 tool 的結果。

### T11 · Booking flow · en — REGRESSION (login required)

- requires_login: true
- user_input:
  > Book me a first-class seat from NR01 to NR05 on 2026-06-01
- expected_tool_calls:
  ```json
  []
  ```
- expected_answer_must_contain: ["log in"]
- expected_answer_must_not_contain: ["booked", "BK-", "confirmed"]
- notes: 沒登入時,agent 應先要求登入,絕對不該呼叫 make_booking。

### T12 · Booking flow · en (logged in)

- requires_login: true
- user_input:
  > Book me a standard ticket from NR01 to NR05 on 2026-06-01
- expected_tool_calls:
  ```json
  [
    {"name": "check_national_rail_availability", "params": {"origin_id": "NR01", "destination_id": "NR05", "travel_date": "2026-06-01"}},
    {"name": "get_available_seats", "params": {"schedule_id": "<from_previous_result>", "travel_date": "2026-06-01", "fare_class": "standard"}},
    {"name": "make_booking", "params": {"schedule_id": "<from_previous_result>", "origin_station_id": "NR01", "destination_station_id": "NR05", "travel_date": "2026-06-01", "fare_class": "standard", "seat_id": "<from_previous_result>"}}
  ]
  ```
- expected_answer_must_contain: ["confirmed", "BK-"]
- expected_answer_must_not_contain: ["log in", "登入"]
- notes: 完整三步驟訂票流程。

### T13 · Booking flow · zh-TW (logged in)

- requires_login: true
- user_input:
  > 幫我訂 2026-06-15 NR01 到 NR05 的頭等艙,座位你選就好
- expected_tool_calls:
  ```json
  [
    {"name": "check_national_rail_availability", "params": {"origin_id": "NR01", "destination_id": "NR05", "travel_date": "2026-06-15"}},
    {"name": "get_available_seats", "params": {"schedule_id": "<from_previous_result>", "travel_date": "2026-06-15", "fare_class": "first"}},
    {"name": "make_booking", "params": {"schedule_id": "<from_previous_result>", "origin_station_id": "NR01", "destination_station_id": "NR05", "travel_date": "2026-06-15", "fare_class": "first", "seat_id": "any"}}
  ]
  ```
- expected_answer_must_contain: ["BK-", "頭等"]
- expected_answer_must_not_contain: ["請先登入"]
- notes: 「座位你選就好」應對應 seat_id="any";頭等艙 → fare_class="first"。

### T14 · Booking flow · zh-TW (seat selection prompt)

- requires_login: true
- user_input:
  > 我想看 2026-06-01 NR01 到 NR05 還有哪些頭等艙座位
- expected_tool_calls:
  ```json
  [
    {"name": "check_national_rail_availability", "params": {"origin_id": "NR01", "destination_id": "NR05", "travel_date": "2026-06-01"}},
    {"name": "get_available_seats", "params": {"schedule_id": "<from_previous_result>", "travel_date": "2026-06-01", "fare_class": "first"}}
  ]
  ```
- expected_answer_must_contain: ["seat", "first"]
- expected_answer_must_not_contain: ["confirmed", "BK-"]
- notes: 只看座位不下訂,絕對不能呼叫 make_booking。

### T15 · Policy · en — REGRESSION (RF005 30–59 min)

- requires_login: false
- user_input:
  > My train was delayed 45 minutes — what compensation am I entitled to?
- expected_tool_calls:
  ```json
  [
    {"name": "search_policy", "params": {"query": "delay compensation 45 minutes"}}
  ]
  ```
- expected_answer_must_contain: ["50%", "RF005", "28 days"]
- expected_answer_must_not_contain: ["no compensation", "not entitled", "0%"]
- notes: 已知 bug — 過去 search_policy 把 content 截到 800 字元會切掉 RF005 後段;
  修正後完整 content 會送進 LLM, 必須回 50% 退款。

### T16 · Policy · zh-TW

- requires_login: false
- user_input:
  > 我想退票,還能退多少?
- expected_tool_calls:
  ```json
  [
    {"name": "search_policy", "params": {"query": "退票 退款 政策"}}
  ]
  ```
- expected_answer_must_contain: ["退款"]
- expected_answer_must_not_contain: ["不能退"]
- notes: 政策問題且未指定 booking_id, 應觸發 search_policy 而非 cancel_booking。

### T17 · Policy · en

- requires_login: false
- user_input:
  > Can I bring a bicycle on the train during peak hours?
- expected_tool_calls:
  ```json
  [
    {"name": "search_policy", "params": {"query": "bicycle peak hours"}}
  ]
  ```
- expected_answer_must_contain: ["bicycle", "peak"]
- expected_answer_must_not_contain: ["no rule"]

### T18 · Policy · zh-TW

- requires_login: false
- user_input:
  > 我可以帶寵物上車嗎?
- expected_tool_calls:
  ```json
  [
    {"name": "search_policy", "params": {"query": "寵物 動物 規定"}}
  ]
  ```
- expected_answer_must_contain: ["寵物"]
- expected_answer_must_not_contain: ["未知"]

### T19 · Cancellation · en (logged in)

- requires_login: true
- user_input:
  > Cancel booking BK-A1B2C3
- expected_tool_calls:
  ```json
  [
    {"name": "cancel_booking", "params": {"booking_id": "BK-A1B2C3"}}
  ]
  ```
- expected_answer_must_contain: ["BK-A1B2C3"]
- expected_answer_must_not_contain: ["log in"]

### T20 · Cancellation · zh-TW (pronoun)

- requires_login: true
- user_input:
  > 把我最近那筆訂位取消
- expected_tool_calls:
  ```json
  [
    {"name": "get_user_bookings", "params": {}},
    {"name": "cancel_booking", "params": {"booking_id": "<from_previous_result>"}}
  ]
  ```
- expected_answer_must_contain: ["取消"]
- expected_answer_must_not_contain: ["請先登入"]
- notes: 代名詞「最近那筆」需先呼 get_user_bookings 才能解析出 booking_id。

### T21 · User history · en

- requires_login: true
- user_input:
  > Show me my bookings
- expected_tool_calls:
  ```json
  [
    {"name": "get_user_bookings", "params": {}}
  ]
  ```
- expected_answer_must_contain: ["booking"]
- expected_answer_must_not_contain: ["log in"]

### T22 · User history · zh-TW

- requires_login: true
- user_input:
  > 我訂過哪些票?
- expected_tool_calls:
  ```json
  [
    {"name": "get_user_bookings", "params": {}}
  ]
  ```
- expected_answer_must_contain: ["訂"]
- expected_answer_must_not_contain: ["請先登入"]

### T23 · Disruption · en

- requires_login: false
- user_input:
  > NR03 is delayed, can I still get from NR01 to NR05?
- expected_tool_calls:
  ```json
  [
    {"name": "find_alternative_routes", "params": {"origin_id": "NR01", "destination_id": "NR05", "avoid_station_id": "NR03"}}
  ]
  ```
- expected_answer_must_contain: ["NR01", "NR05"]
- expected_answer_must_not_contain: ["no alternative"]

### T24 · Disruption · zh-TW

- requires_login: false
- user_input:
  > 如果 NR03 出問題,還有別的路嗎?從 NR01 到 NR05
- expected_tool_calls:
  ```json
  [
    {"name": "find_alternative_routes", "params": {"origin_id": "NR01", "destination_id": "NR05", "avoid_station_id": "NR03"}}
  ]
  ```
- expected_answer_must_contain: ["NR01", "NR05"]
- expected_answer_must_not_contain: ["不行", "找不到"]

### T25 · Disruption · en

- requires_login: false
- user_input:
  > If NR03 has a delay, which stations are affected?
- expected_tool_calls:
  ```json
  [
    {"name": "get_delay_ripple", "params": {"station_id": "NR03"}}
  ]
  ```
- expected_answer_must_contain: ["NR03"]
- expected_answer_must_not_contain: ["only NR03"]

### T26 · Out-of-scope · en

- requires_login: false
- user_input:
  > What's the weather today?
- expected_tool_calls:
  ```json
  []
  ```
- expected_answer_must_contain: []
- expected_answer_must_not_contain: ["BK-", "schedule_id", "USD"]
- notes: 不該呼叫任何 tool;agent 可禮貌地說超出範圍或直接結束。

### T27 · Out-of-scope · zh-TW

- requires_login: false
- user_input:
  > 你好
- expected_tool_calls:
  ```json
  []
  ```
- expected_answer_must_contain: []
- expected_answer_must_not_contain: ["BK-", "schedule_id"]
- notes: 純打招呼,不應觸發任何工具。
