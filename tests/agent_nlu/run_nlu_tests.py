"""
TransitFlow Agent — NLU Test Runner
====================================

跑 tests/agent_nlu/AGENT_NLU_TEST_CASES.md 裡的全部測例, 對每一筆:
  1. 解析出 user_input / expected_tool_calls / must_contain / must_not_contain
  2. 用 run_agent(..., debug=True) 真的呼叫一次, 從 debug_info 抽出實際 tool calls
  3. 比對 tool 名稱順序、必含 / 不該出現的關鍵字
  4. Print 一行通過 / 失敗摘要, 結束時印總計

設計原則:
  - 不依賴 pytest, 用純 stdlib 解析 markdown, 直接 import skeleton.agent
  - tool name 比對採嚴格順序; params 比對採 "subset match" — 只要 expected
    裡寫死的 key 在 actual 中相等即可
  - 兩個通配字串會跳過比對:
      "<from_previous_result>" — 兩步驟流程下游動態 ID
      "<any>"                  — 允許任意值 (e.g. free-form policy query)
  - 每筆測例彼此獨立, 用全新 history=[]
  - 預設不登入; requires_login=true 的測例會用環境變數 NLU_TEST_USER_EMAIL 傳入登入 email
    (沒設就以 guest 身份跑, 這時登入相關的測例可能失敗 — 屬預期)

用法:
    .venv/bin/python tests/agent_nlu/run_nlu_tests.py
    .venv/bin/python tests/agent_nlu/run_nlu_tests.py --only T07,T15
    NLU_TEST_USER_EMAIL=alice@example.com .venv/bin/python tests/agent_nlu/run_nlu_tests.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# 確保專案根目錄在 sys.path 上, 才能 import skeleton.agent
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from skeleton.agent import run_agent  # noqa: E402


_TEST_FILE = Path(__file__).parent / "AGENT_NLU_TEST_CASES.md"


# ── Markdown 解析 ────────────────────────────────────────────────────────────

@dataclass
class TestCase:
    id: str
    category: str
    language: str
    requires_login: bool
    user_input: str
    expected_tool_calls: list[dict]
    must_contain: list[str]
    must_not_contain: list[str]
    notes: str = ""
    raw_section: str = field(repr=False, default="")


_HEADER_RE = re.compile(r"^###\s+(T\d+)\s*·\s*([^·]+?)\s*·\s*([\w-]+)", re.MULTILINE)
_FIELD_RE = re.compile(r"^-\s*([a-z_]+):\s*(.*)$", re.MULTILINE)


def _parse_section(section: str) -> TestCase | None:
    """Parse one '### Tnn · category · lang' block."""
    header_m = _HEADER_RE.match(section)
    if not header_m:
        return None
    tid, category, language = header_m.group(1), header_m.group(2).strip(), header_m.group(3).strip()

    # requires_login
    rl_m = re.search(r"^-\s*requires_login:\s*(true|false)\s*$", section, re.MULTILINE)
    requires_login = bool(rl_m and rl_m.group(1) == "true")

    # user_input — blockquote line(s) after "user_input:"
    ui_m = re.search(r"^-\s*user_input:\s*\n\s*>\s*(.+?)$", section, re.MULTILINE)
    user_input = ui_m.group(1).strip() if ui_m else ""

    # expected_tool_calls — JSON code fence right after the field
    etc_m = re.search(
        r"-\s*expected_tool_calls:\s*\n\s*```json\s*\n(.*?)\n\s*```",
        section,
        re.DOTALL,
    )
    if etc_m:
        try:
            expected_tool_calls = json.loads(etc_m.group(1))
        except json.JSONDecodeError as e:
            print(f"[parse-error] {tid}: bad JSON in expected_tool_calls: {e}")
            expected_tool_calls = []
    else:
        expected_tool_calls = []

    # must_contain / must_not_contain — single-line list literal
    def _parse_list(field_name: str) -> list[str]:
        m = re.search(rf"^-\s*{field_name}:\s*(\[.*\])\s*$", section, re.MULTILINE)
        if not m:
            return []
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return []

    must_contain = _parse_list("expected_answer_must_contain")
    must_not_contain = _parse_list("expected_answer_must_not_contain")

    notes_m = re.search(r"^-\s*notes(?:\s*\([^)]+\))?:\s*(.+?)$", section, re.MULTILINE | re.DOTALL)
    notes = notes_m.group(1).strip().split("\n")[0] if notes_m else ""

    return TestCase(
        id=tid,
        category=category,
        language=language,
        requires_login=requires_login,
        user_input=user_input,
        expected_tool_calls=expected_tool_calls,
        must_contain=must_contain,
        must_not_contain=must_not_contain,
        notes=notes,
        raw_section=section,
    )


def load_test_cases(path: Path = _TEST_FILE) -> list[TestCase]:
    text = path.read_text(encoding="utf-8")
    # Split by '### Tnn' headers; keep each block including its header
    chunks = re.split(r"(?=^###\s+T\d+\s*·)", text, flags=re.MULTILINE)
    cases: list[TestCase] = []
    for chunk in chunks:
        if not chunk.lstrip().startswith("### T"):
            continue
        case = _parse_section(chunk)
        if case:
            cases.append(case)
    return cases


# ── Agent 結果擷取 ────────────────────────────────────────────────────────────

# debug_info 內每個 "**Calling:** `name(params)`" 對應一次真實 tool 呼叫
_CALL_RE = re.compile(r"\*\*Calling:\*\*\s*`([a-z_]+)\((.*?)\)`", re.DOTALL)


def extract_actual_calls(debug_info: list[str]) -> list[dict]:
    """Pull the actual tool name + params dict from agent debug info.

    Note: skeleton.agent.run_agent in streaming mode yields debug_info as
    individual character chunks (one element per char). We therefore join the
    whole list into one string before scanning, instead of per-element regex.
    """
    blob = "".join(debug_info) if debug_info else ""
    actual: list[dict] = []
    import ast
    for m in _CALL_RE.finditer(blob):
        name = m.group(1)
        params_repr = m.group(2).strip()
        try:
            params = ast.literal_eval(params_repr) if params_repr else {}
        except (ValueError, SyntaxError):
            params = {}
        if not isinstance(params, dict):
            params = {}
        actual.append({"name": name, "params": params})
    return actual


# ── 比對 ────────────────────────────────────────────────────────────────────

PLACEHOLDER = "<from_previous_result>"
WILDCARD = "<any>"
_WILDCARDS = {PLACEHOLDER, WILDCARD}


def compare_calls(expected: list[dict], actual: list[dict]) -> tuple[bool, str]:
    """Return (ok, reason). Order-strict on tool names; params: subset match,
    wildcard values are skipped:
      - "<from_previous_result>" : value comes from a prior tool call (dynamic)
      - "<any>"                  : value not asserted (e.g. free-form policy query)
    """
    if len(expected) != len(actual):
        return False, f"call count differs: expected {len(expected)}, got {len(actual)}"

    for i, (exp, act) in enumerate(zip(expected, actual)):
        if exp["name"] != act["name"]:
            return False, f"call #{i+1}: expected `{exp['name']}`, got `{act['name']}`"
        exp_params = exp.get("params", {}) or {}
        act_params = act.get("params", {}) or {}
        for k, v in exp_params.items():
            if v in _WILDCARDS:
                continue
            if act_params.get(k) != v:
                return False, (
                    f"call #{i+1} ({exp['name']}): param `{k}` "
                    f"expected {v!r}, got {act_params.get(k)!r}"
                )
    return True, "ok"


def check_keywords(reply: str, must_contain: list[str], must_not_contain: list[str]) -> tuple[bool, str]:
    lower = reply.lower()
    for kw in must_contain:
        if kw.lower() not in lower:
            return False, f"missing required keyword: {kw!r}"
    for kw in must_not_contain:
        if kw.lower() in lower:
            return False, f"forbidden keyword present: {kw!r}"
    return True, "ok"


# ── Runner ───────────────────────────────────────────────────────────────────

def run_one(case: TestCase, login_email: str | None) -> dict:
    user_email = login_email if case.requires_login else None
    try:
        reply, _history, debug_info = run_agent(
            user_message=case.user_input,
            history=[],
            debug=True,
            current_user_email=user_email,
        )
    except Exception as e:
        return {
            "id": case.id, "ok": False, "stage": "agent-exception",
            "detail": f"{type(e).__name__}: {e}", "reply": "", "actual_calls": [],
        }

    actual_calls = extract_actual_calls(debug_info)
    calls_ok, calls_reason = compare_calls(case.expected_tool_calls, actual_calls)
    kw_ok, kw_reason = check_keywords(reply, case.must_contain, case.must_not_contain)

    if not calls_ok:
        return {"id": case.id, "ok": False, "stage": "tool-calls",
                "detail": calls_reason, "reply": reply, "actual_calls": actual_calls}
    if not kw_ok:
        return {"id": case.id, "ok": False, "stage": "answer",
                "detail": kw_reason, "reply": reply, "actual_calls": actual_calls}

    return {"id": case.id, "ok": True, "stage": "all",
            "detail": "ok", "reply": reply, "actual_calls": actual_calls}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the TransitFlow agent NLU test set.")
    parser.add_argument(
        "--only",
        help="Comma-separated case IDs to run (e.g. T01,T07,T15). Default: all.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print agent reply and actual tool calls for every case (not just failures).",
    )
    args = parser.parse_args()

    cases = load_test_cases()
    if args.only:
        wanted = {x.strip().upper() for x in args.only.split(",") if x.strip()}
        cases = [c for c in cases if c.id.upper() in wanted]

    if not cases:
        print("[!] no test cases parsed — check AGENT_NLU_TEST_CASES.md format")
        return 2

    login_email = os.environ.get("NLU_TEST_USER_EMAIL")
    if any(c.requires_login for c in cases) and not login_email:
        print("[hint] some cases require login; set NLU_TEST_USER_EMAIL=<email> for them to pass")

    print(f"Running {len(cases)} test case(s) (login_email={login_email or 'guest'})\n")

    results = []
    for c in cases:
        print(f"  {c.id} · {c.category} · {c.language} ... ", end="", flush=True)
        r = run_one(c, login_email)
        results.append(r)
        status = "PASS" if r["ok"] else f"FAIL [{r['stage']}]"
        print(status)
        if not r["ok"] or args.verbose:
            print(f"    detail: {r['detail']}")
            print(f"    actual_calls: {r['actual_calls']}")
            preview = r["reply"][:200].replace("\n", " ")
            print(f"    reply: {preview!r}{'…' if len(r['reply']) > 200 else ''}")

    passed = sum(1 for r in results if r["ok"])
    failed = len(results) - passed
    print(f"\n=== {passed} passed · {failed} failed · {len(results)} total ===")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
