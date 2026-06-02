"""
TransitFlow — PostgreSQL / Relational Database Layer
=====================================================
This module handles all queries to PostgreSQL.

TWO ROLES ARE SERVED HERE:
  1. Relational  → dual-network transit (metro + national rail),
                   availability, fares, bookings, seat selection
  2. Vector      → policy document similarity search (pgvector)

STUDENT TASK
------------
Design your schema in databases/relational/schema.sql, seed it with
skeleton/seed_postgres.py, then implement the query functions below.

Functions prefixed with `query_`  are read-only lookups called by the agent.
Functions prefixed with `execute_` are write operations (booking/cancellation).

The vector functions (query_policy_vector_search, store_policy_document)
are already implemented — do not modify them.
"""

from __future__ import annotations

import json
import random
import string
from datetime import datetime, timezone
from typing import Optional

import psycopg2
import psycopg2.extras

from skeleton.config import PG_DSN, VECTOR_TOP_K, VECTOR_SIMILARITY_THRESHOLD


def _connect():
    """Return a new psycopg2 connection with autocommit enabled."""
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = True
    return conn


def _gen_booking_id() -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"BK-{suffix}"


def _gen_payment_id() -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"PM-{suffix}"


# ── Example ───────────────────────────────────────────────────────────────────
# The block below shows the query pattern: open a cursor, run SQL, return rows.
# Use _connect() for read-only queries; for write operations use a manual
# connection with conn.commit() / conn.rollback() (see execute_booking below).

def example_query() -> dict:
    """Example: returns the name of the connected database."""
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT current_database() AS db;")
            return dict(cur.fetchone())

# TODO: Implement the query_ and execute_ functions below.
# ─────────────────────────────────────────────────────────────────────────────


# ── NATIONAL RAIL AVAILABILITY ────────────────────────────────────────────────

def query_national_rail_availability(
    origin_id: str,
    destination_id: str,
    travel_date: Optional[str] = None,
) -> list[dict]:
    """
    Return national rail schedules that serve both origin and destination stations
    in the correct order, along with seat occupancy for the requested travel date.

    Args:
        origin_id:       e.g. "NR01"
        destination_id:  e.g. "NR05"
        travel_date:     e.g. "2025-06-01" — used to count bookings; omit for general info
    """
    # Defensive: LLM sometimes passes the string 'null' / 'None' / '' instead of None.
    # 在進 SQL 前統一正規化, 避免 psycopg2 把字串 'null' 當成日期值送進 DB 噴 InvalidDatetimeFormat。
    if isinstance(travel_date, str) and travel_date.strip().lower() in ("", "null", "none"):
        travel_date = None

    # 為什麼用這個 SQL: 用 stops 子表自 join (alias o, d) 同時抓 origin / destination 兩站,
    # 用 o.stop_order < d.stop_order 確保方向正確; 兩站都要 is_passed_through=false 才算有效停靠;
    # 每張 schedule 的當日訂位數用 LEFT JOIN + 子查詢預先彙總 (避免 GROUP BY 複雜化);
    # travel_date 為 None 時 seats_taken 直接設 0。
    if travel_date is None:
        sql = """
            SELECT
                s.schedule_id,
                s.line,
                s.service_type,
                s.direction,
                s.first_train_time AS departure_time,
                (d.stop_order - o.stop_order) AS total_stops_travelled,
                0 AS seats_taken
            FROM national_rail_schedules s
            JOIN national_rail_schedule_stops o
              ON o.schedule_id = s.schedule_id
             AND o.station_id  = %s
             AND o.is_passed_through = FALSE
            JOIN national_rail_schedule_stops d
              ON d.schedule_id = s.schedule_id
             AND d.station_id  = %s
             AND d.is_passed_through = FALSE
             AND d.stop_order > o.stop_order
            ORDER BY s.first_train_time;
        """
        params = (origin_id, destination_id)
    else:
        sql = """
            SELECT
                s.schedule_id,
                s.line,
                s.service_type,
                s.direction,
                s.first_train_time AS departure_time,
                (d.stop_order - o.stop_order) AS total_stops_travelled,
                COALESCE(b.seats_taken, 0) AS seats_taken
            FROM national_rail_schedules s
            JOIN national_rail_schedule_stops o
              ON o.schedule_id = s.schedule_id
             AND o.station_id  = %s
             AND o.is_passed_through = FALSE
            JOIN national_rail_schedule_stops d
              ON d.schedule_id = s.schedule_id
             AND d.station_id  = %s
             AND d.is_passed_through = FALSE
             AND d.stop_order > o.stop_order
            LEFT JOIN (
                SELECT schedule_id, COUNT(*) AS seats_taken
                FROM national_rail_bookings
                WHERE travel_date = %s AND status = 'confirmed'
                GROUP BY schedule_id
            ) b ON b.schedule_id = s.schedule_id
            ORDER BY s.first_train_time;
        """
        params = (origin_id, destination_id, travel_date)

    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def query_national_rail_fare(
    schedule_id: str,
    fare_class: str,
    stops_travelled: int,
) -> Optional[dict]:
    """
    Calculate the fare for a national rail journey.

    Args:
        schedule_id:     e.g. "NR_SCH01"
        fare_class:      "standard" or "first"
        stops_travelled: number of stops between origin and destination (inclusive)

    Returns:
        dict with fare_class, base_fare_usd, per_stop_rate_usd, total_fare_usd
    """
    # 為什麼用這個 SQL: 票價拆成 4 個攤平欄, 用 CASE 依 fare_class 選對應的 base/per_stop,
    # 同時讓 SQL 自己算 total = base + per_stop * stops, 不可能跑兩種等級時各取錯欄。
    # fare_class 限制成 standard / first 兩種, 其他直接回 None。
    if fare_class not in ("standard", "first"):
        return None

    sql = """
        SELECT
            CASE WHEN %s = 'first' THEN fare_first_base_usd     ELSE fare_standard_base_usd     END AS base_fare_usd,
            CASE WHEN %s = 'first' THEN fare_first_per_stop_usd ELSE fare_standard_per_stop_usd END AS per_stop_rate_usd
        FROM national_rail_schedules
        WHERE schedule_id = %s;
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (fare_class, fare_class, schedule_id))
            row = cur.fetchone()
            if not row:
                return None
            base = float(row["base_fare_usd"])
            per_stop = float(row["per_stop_rate_usd"])
            total = round(base + per_stop * int(stops_travelled), 2)
            return {
                "fare_class": fare_class,
                "base_fare_usd": base,
                "per_stop_rate_usd": per_stop,
                "total_fare_usd": total,
            }


# ── METRO SCHEDULES & FARE ────────────────────────────────────────────────────

def query_metro_schedules(origin_id: str, destination_id: str) -> list[dict]:
    """
    Return metro schedules that serve both origin and destination in the correct order.

    Args:
        origin_id:       e.g. "MS01"
        destination_id:  e.g. "MS09"
    """
    # 為什麼用這個 SQL: 同 NR 邏輯, 用 metro_schedule_stops 自 join 找同時包含兩站且順序正確的班表;
    # metro 子表沒有 is_passed_through 欄 (地鐵每站都停), 所以不需過濾; 也沒有 service_type / fare_class。
    sql = """
        SELECT
            s.schedule_id,
            s.line,
            s.direction,
            s.first_train_time AS departure_time,
            (d.stop_order - o.stop_order) AS total_stops_travelled
        FROM metro_schedules s
        JOIN metro_schedule_stops o
          ON o.schedule_id = s.schedule_id
         AND o.station_id  = %s
        JOIN metro_schedule_stops d
          ON d.schedule_id = s.schedule_id
         AND d.station_id  = %s
         AND d.stop_order > o.stop_order
        ORDER BY s.first_train_time;
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (origin_id, destination_id))
            return [dict(row) for row in cur.fetchall()]


def query_metro_fare(schedule_id: str, stops_travelled: int) -> Optional[dict]:
    """
    Calculate the metro fare for a single-ticket journey.

    Args:
        schedule_id:     e.g. "MS_SCH01"
        stops_travelled: number of stops between origin and destination

    Returns:
        dict with base_fare_usd, per_stop_rate_usd, total_fare_usd
    """
    # 為什麼用這個 SQL: metro_schedules 表已直接帶 base_fare_usd / per_stop_rate_usd 兩欄,
    # 不像國鐵需依 fare_class 分流, 直接 SELECT 兩欄回來再算 total 即可; 找不到 schedule 回 None。
    sql = """
        SELECT base_fare_usd, per_stop_rate_usd
        FROM metro_schedules
        WHERE schedule_id = %s;
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (schedule_id,))
            row = cur.fetchone()
            if not row:
                return None
            base = float(row["base_fare_usd"])
            per_stop = float(row["per_stop_rate_usd"])
            total = round(base + per_stop * int(stops_travelled), 2)
            return {
                "base_fare_usd": base,
                "per_stop_rate_usd": per_stop,
                "total_fare_usd": total,
            }


# ── SEAT SELECTION ────────────────────────────────────────────────────────────

def query_available_seats(
    schedule_id: str,
    travel_date: str,
    fare_class: str,
) -> list[dict]:
    """
    Return available seats for a national rail journey on a given date.

    Args:
        schedule_id:  e.g. "NR_SCH01"
        travel_date:  e.g. "2025-06-01"
        fare_class:   "standard" or "first"

    Returns:
        List of dicts: {seat_id, coach, row, column}
    """
    # 為什麼用這個 SQL: schema 欄位實際叫 row_number / column_letter (避開 SQL 保留字),
    # 但 docstring 規定回傳 key 是 row / column, 所以用 AS 別名做欄位重命名;
    # 已被佔用的座位用 NOT IN 子查詢排除 (限 status='confirmed' + 同 schedule + 同日)。
    sql = """
        SELECT
            seat_id,
            coach,
            row_number   AS row,
            column_letter AS column
        FROM national_rail_seats
        WHERE schedule_id = %s
          AND fare_class  = %s
          AND seat_id NOT IN (
              SELECT seat_id
              FROM national_rail_bookings
              WHERE schedule_id = %s
                AND travel_date = %s
                AND status = 'confirmed'
                AND seat_id IS NOT NULL
          )
        ORDER BY coach, row_number, column_letter;
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (schedule_id, fare_class, schedule_id, travel_date))
            return [dict(row) for row in cur.fetchall()]


def auto_select_adjacent_seats(available_seats: list[dict], count: int) -> list[str]:
    """
    Select `count` seats that are as close together as possible (same row preferred,
    then adjacent rows). Returns a list of seat_ids.

    Args:
        available_seats: output of query_available_seats()
        count:           number of seats needed
    """
    if not available_seats or count <= 0:
        return []
    if count >= len(available_seats):
        return [s["seat_id"] for s in available_seats[:count]]

    from collections import defaultdict
    rows: dict[int, list[dict]] = defaultdict(list)
    for seat in available_seats:
        rows[seat["row"]].append(seat)

    for row_seats in sorted(rows.values(), key=lambda s: s[0]["row"]):
        if len(row_seats) >= count:
            return [s["seat_id"] for s in row_seats[:count]]

    sorted_seats = sorted(available_seats, key=lambda s: (s["row"], s["column"]))
    return [s["seat_id"] for s in sorted_seats[:count]]


# ── USER & BOOKING QUERIES ────────────────────────────────────────────────────

def query_user_profile(user_email: str) -> Optional[dict]:
    """Return a user's profile by email."""
    # 為什麼用這個 SQL: 直接整 row 取出 (RealDictCursor 自動轉 dict),
    # 找不到回 None 以符合 Optional[dict] 契約; SELECT * 在這裡 OK 因為 schema 受我們控管。
    sql = "SELECT * FROM users WHERE email = %s;"
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (user_email,))
            row = cur.fetchone()
            return dict(row) if row else None


def query_user_bookings(user_email: str) -> dict:
    """
    Return a user's combined booking history (national rail + metro).

    Returns:
        dict with keys 'national_rail' (list) and 'metro' (list)
    """
    # 為什麼用這個 SQL: 用 email 透過子查詢拿到 user_id 再查兩張歷史表,
    # 不在 Python 端先做一次 round trip; 兩邊都 join users 拿 user_id 也行,
    # 但子查詢更簡潔。即使空也保證兩個 key 都在 (符合 docstring)。
    # NR 排序: travel_date desc, departure_time desc; Metro 排序: travel_date desc。
    sql_nr = """
        SELECT *
        FROM national_rail_bookings
        WHERE user_id = (SELECT user_id FROM users WHERE email = %s)
        ORDER BY travel_date DESC, departure_time DESC;
    """
    sql_metro = """
        SELECT *
        FROM metro_travel_history
        WHERE user_id = (SELECT user_id FROM users WHERE email = %s)
        ORDER BY travel_date DESC;
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql_nr, (user_email,))
            national_rail = [dict(row) for row in cur.fetchall()]
            cur.execute(sql_metro, (user_email,))
            metro = [dict(row) for row in cur.fetchall()]
    return {"national_rail": national_rail, "metro": metro}


def query_payment_info(booking_id: str) -> Optional[dict]:
    """Return payment record for a booking or metro trip."""
    # 為什麼用這個 SQL: payments 表已有 transaction_type 欄區分 NR / Metro,
    # 直接以 booking_id 為 key 取單筆即可, 不需在 Python 端加 prefix 判斷。
    sql = "SELECT * FROM payments WHERE booking_id = %s;"
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (booking_id,))
            row = cur.fetchone()
            return dict(row) if row else None


# ── TRANSACTIONAL OPERATIONS ──────────────────────────────────────────────────

def execute_booking(
    user_id: str,
    schedule_id: str,
    origin_station_id: str,
    destination_station_id: str,
    travel_date: str,
    fare_class: str,
    seat_id: str,
    ticket_type: str = "single",
) -> tuple[bool, dict | str]:
    """
    Create a national rail booking for a logged-in user.

    Args:
        user_id:                e.g. "RU01" — must match the logged-in user
        schedule_id:            e.g. "NR_SCH01"
        origin_station_id:      e.g. "NR01"
        destination_station_id: e.g. "NR05"
        travel_date:            e.g. "2025-06-01"
        fare_class:             "standard" or "first"
        seat_id:                e.g. "B05" (or "any" to auto-assign)
        ticket_type:            "single" (default) or "return"

    Returns:
        (True, booking_dict)   on success
        (False, error_message) on failure
    """
    # 為什麼用這個 SQL: 整段必須是原子交易, 任何驗證失敗或 INSERT 失敗都 rollback。
    # 驗證走 5 道:
    #   (a) user 存在且 is_active
    #   (b) schedule 存在 (順便取 first_train_time 當 departure_time)
    #   (c) origin/destination 都在 stops 子表, is_passed_through=false, 順序正確
    #   (d) seat_id 屬於該 schedule + fare_class (seat_id="any" 時走自動挑座)
    #   (e) 該座位當日未被其他 confirmed booking 佔用
    # 用 query_national_rail_fare 算金額; 兩筆 INSERT (booking + payment) 在同交易內。
    if fare_class not in ("standard", "first"):
        return (False, "fare_class must be 'standard' or 'first'")
    if ticket_type not in ("single", "return"):
        return (False, "ticket_type must be 'single' or 'return'")

    conn = _connect()
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # (a) user 存在且 is_active
            cur.execute(
                "SELECT user_id, is_active FROM users WHERE user_id = %s;",
                (user_id,),
            )
            user_row = cur.fetchone()
            if not user_row:
                conn.rollback()
                return (False, f"user '{user_id}' not found")
            if not user_row["is_active"]:
                conn.rollback()
                return (False, f"user '{user_id}' is inactive")

            # (b) schedule 存在
            cur.execute(
                "SELECT schedule_id, first_train_time FROM national_rail_schedules WHERE schedule_id = %s;",
                (schedule_id,),
            )
            sch_row = cur.fetchone()
            if not sch_row:
                conn.rollback()
                return (False, f"schedule '{schedule_id}' not found")
            departure_time = sch_row["first_train_time"]

            # (c) origin/destination 都在停靠站, 順序正確, 非快車經過站
            cur.execute(
                """
                SELECT
                    o.stop_order AS o_order,
                    d.stop_order AS d_order
                FROM national_rail_schedule_stops o
                JOIN national_rail_schedule_stops d
                  ON d.schedule_id = o.schedule_id
                WHERE o.schedule_id = %s
                  AND o.station_id  = %s AND o.is_passed_through = FALSE
                  AND d.station_id  = %s AND d.is_passed_through = FALSE;
                """,
                (schedule_id, origin_station_id, destination_station_id),
            )
            stop_row = cur.fetchone()
            if not stop_row:
                conn.rollback()
                return (False, "origin or destination is not a valid stop on this schedule")
            if stop_row["o_order"] >= stop_row["d_order"]:
                conn.rollback()
                return (False, "origin must come before destination on this schedule")
            stops_travelled = stop_row["d_order"] - stop_row["o_order"]

            # (d) seat 處理: "any" 走自動挑座, 否則驗證歸屬 schedule+fare_class
            if seat_id == "any":
                # 在交易內讀(autocommit=False), 用同一個 cur 直接撈避免再開連線
                cur.execute(
                    """
                    SELECT seat_id, coach,
                           row_number   AS row,
                           column_letter AS column
                    FROM national_rail_seats
                    WHERE schedule_id = %s
                      AND fare_class  = %s
                      AND seat_id NOT IN (
                          SELECT seat_id FROM national_rail_bookings
                          WHERE schedule_id = %s
                            AND travel_date = %s
                            AND status = 'confirmed'
                            AND seat_id IS NOT NULL
                      )
                    ORDER BY coach, row_number, column_letter;
                    """,
                    (schedule_id, fare_class, schedule_id, travel_date),
                )
                avail = [dict(r) for r in cur.fetchall()]
                picked = auto_select_adjacent_seats(avail, 1)
                if not picked:
                    conn.rollback()
                    return (False, "no available seats for the requested fare class")
                seat_id = picked[0]

            # 驗證 seat 屬於該 schedule + fare_class, 順便取 coach 寫入 booking
            cur.execute(
                """
                SELECT coach
                FROM national_rail_seats
                WHERE schedule_id = %s AND seat_id = %s AND fare_class = %s;
                """,
                (schedule_id, seat_id, fare_class),
            )
            seat_row = cur.fetchone()
            if not seat_row:
                conn.rollback()
                return (False, f"seat '{seat_id}' not found in {fare_class} class on this schedule")
            coach = seat_row["coach"]

            # (e) 該座位當日未被其他 confirmed booking 佔用
            cur.execute(
                """
                SELECT 1
                FROM national_rail_bookings
                WHERE schedule_id = %s
                  AND seat_id     = %s
                  AND travel_date = %s
                  AND status = 'confirmed';
                """,
                (schedule_id, seat_id, travel_date),
            )
            if cur.fetchone() is not None:
                conn.rollback()
                return (False, f"seat '{seat_id}' is already booked on {travel_date}")

            # 計算金額 (從 schema 票價欄直接算, 不用再開連線)
            cur.execute(
                """
                SELECT
                    CASE WHEN %s = 'first' THEN fare_first_base_usd     ELSE fare_standard_base_usd     END AS base,
                    CASE WHEN %s = 'first' THEN fare_first_per_stop_usd ELSE fare_standard_per_stop_usd END AS per_stop
                FROM national_rail_schedules
                WHERE schedule_id = %s;
                """,
                (fare_class, fare_class, schedule_id),
            )
            fare_row = cur.fetchone()
            base = float(fare_row["base"])
            per_stop = float(fare_row["per_stop"])
            amount_usd = round(base + per_stop * stops_travelled, 2)

            booking_id = _gen_booking_id()
            payment_id = _gen_payment_id()
            now_utc = datetime.now(timezone.utc)

            # INSERT booking
            cur.execute(
                """
                INSERT INTO national_rail_bookings (
                    booking_id, user_id, schedule_id,
                    origin_station_id, destination_station_id,
                    travel_date, departure_time, ticket_type,
                    fare_class, coach, seat_id,
                    stops_travelled, amount_usd, status, booked_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, 'confirmed', %s
                );
                """,
                (
                    booking_id, user_id, schedule_id,
                    origin_station_id, destination_station_id,
                    travel_date, departure_time, ticket_type,
                    fare_class, coach, seat_id,
                    stops_travelled, amount_usd, now_utc,
                ),
            )

            # INSERT payment
            cur.execute(
                """
                INSERT INTO payments (
                    payment_id, booking_id, transaction_type,
                    amount_usd, method, status, paid_at
                ) VALUES (
                    %s, %s, 'NR', %s, 'credit_card', 'paid', %s
                );
                """,
                (payment_id, booking_id, amount_usd, now_utc),
            )

        conn.commit()
        return (True, {
            "booking_id": booking_id,
            "user_id": user_id,
            "schedule_id": schedule_id,
            "origin_station_id": origin_station_id,
            "destination_station_id": destination_station_id,
            "travel_date": travel_date,
            "fare_class": fare_class,
            "ticket_type": ticket_type,
            "coach": coach,
            "seat_id": seat_id,
            "stops_travelled": stops_travelled,
            "total_fare_usd": amount_usd,
            "payment_id": payment_id,
            "status": "confirmed",
        })
    except Exception as e:
        conn.rollback()
        return (False, str(e))
    finally:
        conn.close()


def execute_cancellation(booking_id: str, user_id: str) -> tuple[bool, dict | str]:
    """
    Cancel a national rail booking owned by the given user.

    Calculates the refund amount according to the booking's service type:
      - Normal service: RF001 windows (100% / 75% / 50% / 0%)
      - Express service: RF002 windows (100% / 50% / 0%)

    Args:
        booking_id: e.g. "BK001"
        user_id:    must match the booking's user_id

    Returns:
        (True, result_dict)  with refund_amount_usd and policy note
        (False, error_msg)
    """
    # 為什麼用這個 SQL: 用 LEFT JOIN schedules 同時取 booking 與 service_type, 一次 round trip;
    # 在 Python 端依 service_type 套退款窗口 (RF001 normal / RF002 express),
    # 距離出發小時數用 datetime.now(timezone.utc) - (travel_date + departure_time) 算;
    # UPDATE booking 改 cancelled, 若 refund > 0 再 UPDATE payment 改 refunded, 全包成原子交易。
    conn = _connect()
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    b.booking_id, b.user_id, b.status, b.amount_usd,
                    b.travel_date, b.departure_time, b.schedule_id,
                    s.service_type
                FROM national_rail_bookings b
                LEFT JOIN national_rail_schedules s
                       ON s.schedule_id = b.schedule_id
                WHERE b.booking_id = %s;
                """,
                (booking_id,),
            )
            booking = cur.fetchone()
            if not booking:
                conn.rollback()
                return (False, f"booking '{booking_id}' not found")
            if booking["user_id"] != user_id:
                conn.rollback()
                return (False, "booking does not belong to this user")
            if booking["status"] == "cancelled":
                conn.rollback()
                return (False, "booking is already cancelled")
            if booking["status"] != "confirmed":
                conn.rollback()
                return (False, f"cannot cancel booking with status '{booking['status']}'")

            # 距離出發的小時數 (travel_date + departure_time, 視為 UTC)
            depart_dt = datetime.combine(
                booking["travel_date"], booking["departure_time"],
                tzinfo=timezone.utc,
            )
            hours_before = (depart_dt - datetime.now(timezone.utc)).total_seconds() / 3600.0

            # 退款窗口
            service_type = booking["service_type"]
            if service_type == "normal":
                policy_id = "RF001"
                if hours_before >= 48:
                    refund_pct, admin_fee, window = 100, 0.0, ">=48hr"
                elif hours_before >= 24:
                    refund_pct, admin_fee, window = 75, 0.5, "24-48hr"
                elif hours_before >= 2:
                    refund_pct, admin_fee, window = 50, 0.5, "2-24hr"
                else:
                    refund_pct, admin_fee, window = 0, 0.0, "<2hr"
            elif service_type == "express":
                policy_id = "RF002"
                if hours_before >= 48:
                    refund_pct, admin_fee, window = 100, 1.0, ">=48hr"
                elif hours_before >= 24:
                    refund_pct, admin_fee, window = 50, 1.0, "24-48hr"
                else:
                    refund_pct, admin_fee, window = 0, 0.0, "<24hr"
            else:
                conn.rollback()
                return (False, f"unknown service_type for booking '{booking_id}'")

            amount_usd = float(booking["amount_usd"] or 0)
            refund_amount = round(amount_usd * (refund_pct / 100.0) - admin_fee, 2)
            if refund_amount < 0:
                refund_amount = 0.0

            # UPDATE booking → cancelled
            cur.execute(
                "UPDATE national_rail_bookings SET status = 'cancelled' WHERE booking_id = %s;",
                (booking_id,),
            )

            # 退款 > 0 才更新 payment
            if refund_amount > 0:
                cur.execute(
                    """
                    UPDATE payments
                    SET status = 'refunded'
                    WHERE booking_id = %s AND transaction_type = 'NR';
                    """,
                    (booking_id,),
                )

        conn.commit()
        return (True, {
            "booking_id": booking_id,
            "refund_amount_usd": refund_amount,
            "refund_percent": refund_pct,
            "admin_fee_usd": admin_fee,
            "policy_window": f"{policy_id} {window}",
            "hours_before_departure": round(hours_before, 2),
        })
    except Exception as e:
        conn.rollback()
        return (False, str(e))
    finally:
        conn.close()


# ── AUTHENTICATION QUERIES ────────────────────────────────────────────────────

def register_user(
    email: str,
    first_name: str,
    surname: str,
    year_of_birth: int,
    password: str,
    secret_question: str,
    secret_answer: str,
) -> tuple[bool, str]:
    """
    Register a new user.
    Returns (True, user_id) on success or (False, error_message) on failure.

    NOTE: passwords are stored as plain text here intentionally for teaching
    purposes. In production, replace with a salted hash (e.g. bcrypt).
    """
    # 為什麼用這個 SQL: 先在交易內檢查 email 唯一性 (避免和 UNIQUE constraint 衝突),
    # 再用 SUBSTRING + CAST 把現有 RU## 的尾碼取出取最大 +1 產生新 user_id,
    # 最後 INSERT 整筆 user。寫入操作所以手動 commit/rollback 包成原子交易。
    full_name = f"{first_name} {surname}".strip()
    date_of_birth = f"{year_of_birth}-01-01"

    conn = _connect()
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 1. email 唯一性檢查
            cur.execute("SELECT 1 FROM users WHERE email = %s;", (email,))
            if cur.fetchone() is not None:
                conn.rollback()
                return (False, "email already registered")

            # 2. 取現有 RU## 最大序號 + 1, 沒有人時從 1 開始
            cur.execute(
                """
                SELECT COALESCE(
                    MAX(CAST(SUBSTRING(user_id FROM 3) AS INTEGER)),
                    0
                ) AS max_num
                FROM users
                WHERE user_id LIKE 'RU%' AND SUBSTRING(user_id FROM 3) ~ '^[0-9]+$';
                """
            )
            next_num = (cur.fetchone() or {}).get("max_num", 0) + 1
            new_user_id = f"RU{str(next_num).zfill(2)}"

            # 3. INSERT
            cur.execute(
                """
                INSERT INTO users (
                    user_id, full_name, email, password,
                    date_of_birth, secret_question, secret_answer, is_active
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE);
                """,
                (
                    new_user_id, full_name, email, password,
                    date_of_birth, secret_question, secret_answer,
                ),
            )
        conn.commit()
        return (True, new_user_id)
    except Exception as e:
        conn.rollback()
        return (False, str(e))
    finally:
        conn.close()


def login_user(email: str, password: str) -> Optional[dict]:
    """
    Verify credentials. Returns a user dict on success or None on failure.
    Dict keys: user_id, email, full_name, first_name, surname, phone, date_of_birth, is_active.
    """
    # 為什麼用這個 SQL: 用 split_part 把 full_name 拆成 first_name/surname 直接在 DB 端處理,
    # 比 Python 端拆字串更省一次序列化。WHERE 同時比對 email + password (plain text),
    # 失敗 (找不到列) 一律回 None, 不讓呼叫端區分是 email 不存在還是密碼錯誤。
    sql = """
        SELECT
            user_id,
            email,
            full_name,
            split_part(full_name, ' ', 1) AS first_name,
            split_part(full_name, ' ', 2) AS surname,
            phone,
            date_of_birth,
            is_active
        FROM users
        WHERE email = %s AND password = %s;
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (email, password))
            row = cur.fetchone()
            return dict(row) if row else None


def get_user_secret_question(email: str) -> Optional[str]:
    """Return the secret question for a registered email, or None if not found."""
    # 為什麼用這個 SQL: 只要回單欄 (secret_question), 用 RealDictCursor 取出後直接讀欄位;
    # 若 email 無對應 user 則回 None, 與 docstring 的 Optional[str] 契約一致。
    sql = "SELECT secret_question FROM users WHERE email = %s;"
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (email,))
            row = cur.fetchone()
            return row["secret_question"] if row else None


def verify_secret_answer(email: str, answer: str) -> bool:
    """Return True if the provided answer matches the stored secret answer (case-insensitive)."""
    # 為什麼用這個 SQL: 答案比對需大小寫不敏感, 直接在 DB 端用 LOWER() 兩邊各做一次比較,
    # 比把整列拉回 Python 再 .lower() 來得安全 (避免 NULL/編碼意外); 找不到回 False。
    sql = """
        SELECT 1
        FROM users
        WHERE email = %s
          AND LOWER(secret_answer) = LOWER(%s);
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (email, answer))
            return cur.fetchone() is not None


def update_password(email: str, new_password: str) -> bool:
    """Update the password for a user. Returns True if the row was updated."""
    # 為什麼用這個 SQL: 寫入操作必須包在交易內 (autocommit=False),
    # UPDATE 後用 cur.rowcount 判斷是否真的有更新到任何 row,
    # 找不到 email 時 rowcount=0 → 回 False; 任何例外 rollback 並回 False。
    conn = _connect()
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password = %s WHERE email = %s;",
                (new_password, email),
            )
            updated = cur.rowcount
        conn.commit()
        return updated > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


# ── VECTOR / RAG QUERIES — do not modify ─────────────────────────────────────

def query_policy_vector_search(embedding: list[float], top_k: int = VECTOR_TOP_K) -> list[dict]:
    """
    Find the most relevant policy documents for a given query embedding.

    Args:
        embedding: Query vector from llm.embed(user_question)
        top_k:     Number of results to return

    Returns:
        List of dicts with title, category, content, and similarity score
    """
    sql = """
        SELECT
            title,
            category,
            content,
            1 - (embedding <=> %s::vector) AS similarity
        FROM policy_documents
        WHERE 1 - (embedding <=> %s::vector) > %s
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (vec_str, vec_str, VECTOR_SIMILARITY_THRESHOLD, vec_str, top_k))
            return [dict(row) for row in cur.fetchall()]


def store_policy_document(
    title: str,
    category: str,
    content: str,
    embedding: list[float],
    source_file: str = "",
) -> int:
    """
    Insert a policy document with its embedding into the database.
    Used by skeleton/seed_vectors.py — students don't need to call this directly.

    Returns:
        The new document's id
    """
    sql = """
        INSERT INTO policy_documents (title, category, content, embedding, source_file)
        VALUES (%s, %s, %s, %s::vector, %s)
        RETURNING id
    """
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (title, category, content, vec_str, source_file))
            return cur.fetchone()[0]
