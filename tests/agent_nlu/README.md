# Agent NLU Test Suite

驗證 TransitFlow agent 把使用者自然語言輸入路由到正確 tool 的整條鏈路。

## 檔案

- `AGENT_NLU_TEST_CASES.md` — 測例清單(由 `TEAM_AI_WORKFLOW` 範本 G 產出)
- `run_nlu_tests.py` — 解析 markdown、跑 agent、比對結果的 runner
- `__init__.py` — 讓資料夾成為 importable package

## 前置作業

```bash
docker compose up -d              # postgres / neo4j / pgadmin
.venv/bin/python skeleton/seed_postgres.py
.venv/bin/python skeleton/seed_neo4j.py
.venv/bin/python skeleton/seed_vectors.py
```

LLM 設定請看專案根目錄 `.env`(`OLLAMA_*` 或 `GEMINI_*`)。

## 跑全部

```bash
.venv/bin/python tests/agent_nlu/run_nlu_tests.py
```

## 只跑指定測例(常用於 regression 修完後快速確認)

```bash
.venv/bin/python tests/agent_nlu/run_nlu_tests.py --only T07,T15
```

## 跑登入相關的測例

```bash
NLU_TEST_USER_EMAIL=alice@example.com \
  .venv/bin/python tests/agent_nlu/run_nlu_tests.py --only T11,T12,T13
```

`requires_login: true` 的測例會把這個 email 帶進 `run_agent(current_user_email=...)`;
沒設環境變數就會以 guest 身份跑,登入測例可能會失敗(屬預期)。

## 詳細輸出

```bash
.venv/bin/python tests/agent_nlu/run_nlu_tests.py -v
```

`-v` 連同 PASS 的測例也會印出實際 tool calls 與 agent 回覆前 200 字。

## 比對邏輯重點

- **Tool 順序嚴格** — 第一筆呼叫必須是 expected 的第一筆;名稱不一致直接 FAIL。
- **Params 採 subset 比對** — expected 寫的 key 必須在 actual 中相等,actual 多寫的 key 不算錯。
- **兩個通配字串跳過比對:**
  - `"<from_previous_result>"` — 兩步驟流程下游的動態 ID(例如 booking_id 要先查 user_bookings 才知道)
  - `"<any>"` — 純粹不要管這個 key 的值(例如 `search_policy.query` 是自然語言改寫,不該斷言字面相等)
- **must_contain / must_not_contain 採大小寫不敏感** — 所有比對都先 `.lower()`。

## 加新測例

直接在 `AGENT_NLU_TEST_CASES.md` 末尾追加一個 `### Tnn · category · lang` 區塊,
8 欄補齊就會自動被 runner 抓到。格式參考檔頭的範本說明,或現有任一測例。
