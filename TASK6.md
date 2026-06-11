# TASK 6 — Optional Extension: Service Ratings & Popularity Analytics

This file lists every file added or modified for the Task 6 extension, with the
specific functions, tables, and tools involved. Each modified source file also
carries a `# TASK 6 EXTENSION:` comment near the top (or at the changed lines)
so TAs can locate the extension code unambiguously.

## Summary

The seeded `feedback` table (30 rows: 14 national-rail + 16 metro) was never
read by any core query function or agent tool — riders could not ask about
service quality. This extension adds a **database-layer analytics feature** that
aggregates passenger ratings across **both** networks and exposes them to the
chat assistant through a new tool.

## Files added

| File | What it adds |
|------|--------------|
| `databases/relational/extensions.py` | New analytics query module (read-only). Functions: **`query_line_ratings(network=None)`** and **`query_top_rated_routes(min_reviews=1, limit=5)`**. Shared `_RATINGS_CTE` flattens the polymorphic `feedback` table into uniform rating rows. |
| `DESIGN_DOC_SECTION7.md` | Section 7 of the design document (motivation, schema/query design, example queries, testing evidence). Paste into `Team<Id>_DESIGN_DOC.md`. |
| `TASK6.md` | This manifest. |

## Files modified

| File | Change | Marker |
|------|--------|--------|
| `skeleton/agent.py` | Imports the two new query functions; adds the **`get_service_ratings`** tool definition to `TOOLS`; adds its entry to `TOOLS_SCHEMA`; adds the `get_service_ratings` branch in `_execute_tool` (bundles `query_line_ratings` + `query_top_rated_routes`); adds a routing hint in the Ollama tool-router system prompt. | `# TASK 6 EXTENSION:` on each changed block |

## Database objects used (no schema migration required)

- **Tables read:** `feedback`, `national_rail_bookings`, `national_rail_schedules`,
  `metro_travel_history`, `metro_schedules`, `metro_stations`, `national_rail_stations`.
- **No new table / no new index added by design:** every join rides an existing
  PRIMARY KEY or the existing `idx_feedback_booking_id` index. The `feedback`
  table is polymorphic (`transaction_type` = `'NR'` | `'Metro'`), so each query
  `UNION ALL`s the national-rail and metro join paths before aggregating.

## New query functions

| Function | Signature | Returns |
|----------|-----------|---------|
| `query_line_ratings` | `(network: Optional[str] = None)` | `[{network, line, avg_rating, review_count, min_rating, max_rating}]`, best-rated first |
| `query_top_rated_routes` | `(min_reviews: int = 1, limit: int = 5)` | `[{network, origin_id, origin_name, destination_id, destination_name, avg_rating, review_count}]` |

## New agent tool

`get_service_ratings(network?)` → returns `{ "line_ratings": [...], "top_rated_routes": [...] }`.
Triggered by review / rating / satisfaction / "best-rated line or route" questions
(English and Chinese).

## How to test

```bash
# 1. Direct DB / function test
.venv/bin/python -c "from databases.relational.extensions import query_line_ratings; \
import json; print(json.dumps(query_line_ratings(), indent=2, default=str))"

# 2. Chat UI — ask the assistant:
#    "Which metro line has the best reviews?"
#    "國鐵哪一條路線評價最高?"
#    "What are the top rated routes?"
```

Existing functions (B1–C6) are unchanged and continue to pass — the extension is
read-only and additive, so there are no regressions.
