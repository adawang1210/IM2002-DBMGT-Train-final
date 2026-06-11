# Section 7 — Optional Extension (Task 6): Service Ratings & Popularity Analytics

> Paste this section into `Team<Id>_DESIGN_DOC.md`. It documents the Task 6
> database extension required for the +15 bonus across the Code, Live, and Doc
> components.

## 7.1 Motivation

TransitFlow already collects passenger `feedback` (a 1–5 star `rating` plus an
optional comment per completed booking/trip), and the seed loads **30 real
reviews** — 14 for national rail and 16 for the metro. Yet **no query function
or agent tool ever reads that table**. A rider cannot ask "which metro line has
the best reviews?" or "what are the highest-rated routes?", even though the data
to answer is already in the database.

This extension turns that dormant table into a feature: a **service-quality
analytics layer** that aggregates ratings across *both* networks and lets the
chat assistant answer satisfaction questions. It improves the assistant because
it surfaces decision-useful information (which line/route riders actually rate
highly) that the existing schedule/fare/route tools cannot express, and it does
so without duplicating or denormalising any data.

## 7.2 Database changes

No schema migration is required — the extension is a pure query-layer addition.
The design decision *not* to add a table is deliberate: every value needed is
already reachable through existing primary keys and the existing
`idx_feedback_booking_id` index.

The `feedback` table is **polymorphic**: `transaction_type` is `'NR'` or
`'Metro'`, and `booking_id` references either `national_rail_bookings.booking_id`
or `metro_travel_history.trip_id`. The shared CTE flattens both join paths into
uniform rating rows before aggregating:

```sql
WITH ratings AS (
    SELECT 'rail' AS network, s.line, b.origin_station_id AS origin_id,
           b.destination_station_id AS destination_id, f.rating
    FROM feedback f
    JOIN national_rail_bookings  b ON b.booking_id  = f.booking_id
    JOIN national_rail_schedules s ON s.schedule_id = b.schedule_id
    WHERE f.transaction_type = 'NR'
    UNION ALL
    SELECT 'metro', s.line, t.origin_station_id,
           t.destination_station_id, f.rating
    FROM feedback f
    JOIN metro_travel_history t ON t.trip_id     = f.booking_id
    JOIN metro_schedules      s ON s.schedule_id = t.schedule_id
    WHERE f.transaction_type = 'Metro'
)
```

Two read-only functions in `databases/relational/extensions.py` build on it:

- `query_line_ratings(network=None)` — average rating, review count, and min/max
  rating per line. `UNION ALL` (not `UNION`) preserves every individual rating
  so `AVG()` is not corrupted by de-duplication.
- `query_top_rated_routes(min_reviews=1, limit=5)` — best origin→destination
  routes, with a `HAVING COUNT(*) >= min_reviews` guard so a single 5-star
  review cannot outrank a heavily-reviewed route. Endpoint station names are
  resolved with `LEFT JOIN`s to both station tables + `COALESCE`, because an ID
  may belong to either network.

One new agent tool, `get_service_ratings(network?)`, calls both and returns
`{ "line_ratings": [...], "top_rated_routes": [...] }`.

## 7.3 Example queries

**Per-line ratings (both networks):**

```sql
WITH ratings AS ( /* …CTE above… */ )
SELECT network, line, ROUND(AVG(rating),2) AS avg_rating, COUNT(*) AS review_count,
       MIN(rating) AS min_rating, MAX(rating) AS max_rating
FROM ratings
GROUP BY network, line
ORDER BY avg_rating DESC, review_count DESC;
```

Expected output (from the seeded data):

| network | line | avg_rating | review_count | min | max |
|---------|------|-----------:|-------------:|----:|----:|
| rail    | NR1  | 4.43 | 7 | 3 | 5 |
| rail    | NR2  | 4.29 | 7 | 3 | 5 |
| metro   | M1   | 4.20 | 5 | 3 | 5 |
| metro   | M3   | 4.00 | 4 | 2 | 5 |
| metro   | M4   | 4.00 | 3 | 4 | 4 |
| metro   | M2   | 3.75 | 4 | 3 | 5 |

(Row counts sum to 14 rail + 16 metro = 30 = every seeded review.)

## 7.4 Testing evidence

**Direct function test**

```text
$ .venv/bin/python -c "from databases.relational.extensions import query_line_ratings; \
  [print(r) for r in query_line_ratings('rail')]"
{'network': 'rail', 'line': 'NR1', 'avg_rating': 4.43, 'review_count': 7, 'min_rating': 3, 'max_rating': 5}
{'network': 'rail', 'line': 'NR2', 'avg_rating': 4.29, 'review_count': 7, 'min_rating': 3, 'max_rating': 5}
```

**Chat-UI demo** (Gradio, qwen3:14b)

- *"Which metro line has the best reviews?"* → assistant reports **M1 at 4.2★
  (5 reviews)** as the top metro line.
- *"國鐵哪一條路線評價最高?"* → assistant answers in Chinese that **NR1 (4.43★)**
  is the highest-rated national-rail line.

**Regression** — the extension is read-only and additive; all B1–C6 functions
were re-run after it was added and continue to return correct results, so there
are no regressions.

> Insert your own pgAdmin / Neo4j-Browser / Gradio screenshots here before
> submitting (the rubric awards the testing-evidence marks for visible output).
