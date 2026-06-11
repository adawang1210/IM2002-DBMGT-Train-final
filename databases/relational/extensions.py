# TASK 6 EXTENSION: Service Ratings & Popularity Analytics
# ============================================================================
#  TransitFlow — Task 6 Extension: Service Ratings & Popularity Analytics
#  --------------------------------------------------------------------------
#  WHY THIS EXTENSION EXISTS
#    The `feedback` table (30 rows) is seeded by skeleton/seed_postgres.py but
#    is NEVER read by any core query function or agent tool. Riders therefore
#    cannot ask "how well-rated is the NR1 line?" or "which routes do people
#    like most?" — the chat assistant has no way to surface satisfaction data.
#
#    This module closes that gap with two read-only analytics queries that
#    aggregate ratings ACROSS BOTH NETWORKS (national rail + metro). The
#    feedback table is polymorphic (transaction_type = 'NR' | 'Metro', with
#    booking_id pointing at either national_rail_bookings.booking_id or
#    metro_travel_history.trip_id), so each query UNIONs the two join paths
#    before aggregating.
#
#  WHY NO NEW TABLE / NO NEW INDEX
#    All joins ride on existing keys: feedback.booking_id is already indexed
#    (idx_feedback_booking_id), and every booking/trip/schedule lookup hits a
#    PRIMARY KEY. Adding another table would denormalise data that is already
#    correctly normalised, so the extension lives entirely in the query layer.
#
#  All functions here are READ-ONLY; no transactions are required.
# ============================================================================

from __future__ import annotations

from typing import Optional

import psycopg2
import psycopg2.extras

from skeleton.config import PG_DSN


def _connect():
    """Return a new autocommit psycopg2 connection (read-only analytics)."""
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = True
    return conn


# ── Reusable rating sub-query ────────────────────────────────────────────────
# A single CTE body that flattens the polymorphic feedback table into uniform
# (network, line, origin_id, destination_id, rating) rows. Defined once as a
# string so both public functions share the exact same join logic and can
# never drift apart.
#   * NR path:    feedback → national_rail_bookings → national_rail_schedules
#   * Metro path: feedback → metro_travel_history   → metro_schedules
# UNION ALL (not UNION) because we want every individual rating row preserved
# for the downstream AVG()/COUNT(); de-duplication would corrupt the averages.
_RATINGS_CTE = """
    WITH ratings AS (
        SELECT
            'rail'                   AS network,
            s.line                   AS line,
            b.origin_station_id      AS origin_id,
            b.destination_station_id AS destination_id,
            f.rating                 AS rating
        FROM feedback f
        JOIN national_rail_bookings  b ON b.booking_id  = f.booking_id
        JOIN national_rail_schedules s ON s.schedule_id = b.schedule_id
        WHERE f.transaction_type = 'NR'

        UNION ALL

        SELECT
            'metro'                  AS network,
            s.line                   AS line,
            t.origin_station_id      AS origin_id,
            t.destination_station_id AS destination_id,
            f.rating                 AS rating
        FROM feedback f
        JOIN metro_travel_history t ON t.trip_id    = f.booking_id
        JOIN metro_schedules      s ON s.schedule_id = t.schedule_id
        WHERE f.transaction_type = 'Metro'
    )
"""


def query_line_ratings(network: Optional[str] = None) -> list[dict]:
    """
    Aggregate rider satisfaction per transit line, across both networks.

    Args:
        network: 'rail', 'metro', or None for both (default).

    Returns:
        List of dicts sorted best-rated first:
        {network, line, avg_rating, review_count, min_rating, max_rating}
    """
    # ROUND(AVG(...),2) keeps the average as a NUMERIC (not a float string);
    # COUNT(*) is the number of reviews backing that average, so the LLM/UI can
    # warn when a "5.0" is based on a single review. Optional network filter is
    # parameterised (never string-formatted) to stay injection-safe.
    sql = _RATINGS_CTE + """
        SELECT
            network,
            line,
            ROUND(AVG(rating), 2) AS avg_rating,
            COUNT(*)              AS review_count,
            MIN(rating)           AS min_rating,
            MAX(rating)           AS max_rating
        FROM ratings
        WHERE (%(network)s IS NULL OR network = %(network)s)
        GROUP BY network, line
        ORDER BY avg_rating DESC, review_count DESC;
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, {"network": network})
            # Cast NUMERIC avg_rating to float so the JSON the agent serialises
            # carries a real number, not a Decimal/string the LLM might mis-read.
            rows = []
            for r in cur.fetchall():
                d = dict(r)
                d["avg_rating"] = float(d["avg_rating"]) if d["avg_rating"] is not None else None
                rows.append(d)
            return rows


def query_top_rated_routes(min_reviews: int = 1, limit: int = 5) -> list[dict]:
    """
    Rank origin→destination routes by average rating, across both networks.

    Args:
        min_reviews: only include routes with at least this many reviews
                     (HAVING filter — avoids a single 5-star review topping the
                     chart over a heavily-reviewed 4.5-star route).
        limit:       maximum number of routes to return.

    Returns:
        List of dicts sorted best-rated first:
        {network, origin_id, origin_name, destination_id,
         destination_name, avg_rating, review_count}
    """
    # Station IDs may belong to either the metro or rail station table, so each
    # endpoint is resolved with a LEFT JOIN to BOTH tables and COALESCE picks
    # whichever matched. HAVING COUNT(*) >= min_reviews filters low-evidence
    # routes AFTER grouping. min_reviews/limit are bound as parameters.
    sql = _RATINGS_CTE + """
        SELECT
            r.network,
            r.origin_id,
            COALESCE(mso.name, nro.name) AS origin_name,
            r.destination_id,
            COALESCE(msd.name, nrd.name) AS destination_name,
            ROUND(AVG(r.rating), 2)      AS avg_rating,
            COUNT(*)                     AS review_count
        FROM ratings r
        LEFT JOIN metro_stations          mso ON mso.station_id = r.origin_id
        LEFT JOIN national_rail_stations  nro ON nro.station_id = r.origin_id
        LEFT JOIN metro_stations          msd ON msd.station_id = r.destination_id
        LEFT JOIN national_rail_stations  nrd ON nrd.station_id = r.destination_id
        GROUP BY r.network, r.origin_id, r.destination_id, origin_name, destination_name
        HAVING COUNT(*) >= %(min_reviews)s
        ORDER BY avg_rating DESC, review_count DESC
        LIMIT %(limit)s;
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, {"min_reviews": int(min_reviews), "limit": int(limit)})
            rows = []
            for r in cur.fetchall():
                d = dict(r)
                d["avg_rating"] = float(d["avg_rating"]) if d["avg_rating"] is not None else None
                rows.append(d)
            return rows
