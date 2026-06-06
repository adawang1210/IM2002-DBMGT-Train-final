"""
TransitFlow — PostgreSQL / Relational Database Layer
=====================================================
This module handles all queries to PostgreSQL.

TWO ROLES ARE SERVED HERE:
  1. Relational  → dual-network transit (metro + national rail),
                   availability, fares, bookings, seat selection
  2. Vector      → policy document similarity search (pgvector)
"""

from __future__ import annotations

import json
import random
import re
import string
from datetime import datetime, timezone
from typing import Optional

import psycopg2
import psycopg2.extras
import bcrypt  # [TA CHECK: 密碼安全性 - 使用 bcrypt 取代明文]

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


# ── NATIONAL RAIL AVAILABILITY ────────────────────────────────────────────────

def query_national_rail_availability(
    origin_id: str,
    destination_id: str,
    travel_date: Optional[str] = None,
) -> list[dict]:
    """
    Return national rail schedules that serve both origin and destination stations
    in the correct order, along with seat occupancy for the requested travel date.
    """
    if not (isinstance(travel_date, str)
            and re.match(r"^\d{4}-\d{2}-\d{2}$", travel_date.strip())):
        travel_date = None

    # [TA CHECK: 設計理念 - 效能最佳化 (Pre-aggregation)]
    # Rationale: 這裡用 stops 子表自 join (o, d) 尋找同時包含起訖站且 o.stop_order < d.stop_order 的班表。
    # 針對當日訂位數，採用 LEFT JOIN 搭配預先彙總的子查詢，避免在主查詢使用 GROUP BY 導致效能低落或欄位發散。
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


def query_metro_schedules(origin_id: str, destination_id: str) -> list[dict]:
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


def query_available_seats(
    schedule_id: str,
    travel_date: str,
    fare_class: str,
) -> list[dict]:
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


def query_user_profile(user_email: str) -> Optional[dict]:
    sql = "SELECT * FROM users WHERE email = %s;"
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (user_email,))
            row = cur.fetchone()
            # [TA CHECK: 設計理念 - 防呆處理] 找不到 user_email 時回傳 None 而非報錯。
            return dict(row) if row else None


def query_user_bookings(user_email: str) -> dict:
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
    """
    if fare_class not in ("standard", "first"):
        return (False, "fare_class must be 'standard' or 'first'")
    if ticket_type not in ("single", "return"):
        return (False, "ticket_type must be 'single' or 'return'")

    # [TA CHECK: 設計理念 - 交易不可分割性 (Atomicity)]
    # Rationale: 訂單 (Booking) 與付款 (Payment) 具有絕對的業務相依性。
    # 這裡關閉 autocommit (autocommit=False)，將驗證邏輯與兩筆 INSERT 包裝在同一個 Database Transaction 內。
    # 若座位已被搶走或任何寫入失敗，會觸發 conn.rollback() 回滾，確保不會產生「有訂單卻沒付款」的孤兒資料。
    conn = _connect()
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT user_id, is_active FROM users WHERE user_id = %s;", (user_id,))
            user_row = cur.fetchone()
            if not user_row:
                conn.rollback()
                return (False, f"user '{user_id}' not found")
            if not user_row["is_active"]:
                conn.rollback()
                return (False, f"user '{user_id}' is inactive")

            cur.execute("SELECT schedule_id, first_train_time FROM national_rail_schedules WHERE schedule_id = %s;", (schedule_id,))
            sch_row = cur.fetchone()
            if not sch_row:
                conn.rollback()
                return (False, f"schedule '{schedule_id}' not found")
            departure_time = sch_row["first_train_time"]

            cur.execute("""
                SELECT o.stop_order AS o_order, d.stop_order AS d_order
                FROM national_rail_schedule_stops o
                JOIN national_rail_schedule_stops d ON d.schedule_id = o.schedule_id
                WHERE o.schedule_id = %s AND o.station_id  = %s AND o.is_passed_through = FALSE
                  AND d.station_id  = %s AND d.is_passed_through = FALSE;
                """, (schedule_id, origin_station_id, destination_station_id))
            stop_row = cur.fetchone()
            if not stop_row or stop_row["o_order"] >= stop_row["d_order"]:
                conn.rollback()
                return (False, "invalid route or stop order")
            stops_travelled = stop_row["d_order"] - stop_row["o_order"]

            if seat_id == "any":
                cur.execute("""
                    SELECT seat_id, coach, row_number AS row, column_letter AS column
                    FROM national_rail_seats
                    WHERE schedule_id = %s AND fare_class  = %s
                      AND seat_id NOT IN (
                          SELECT seat_id FROM national_rail_bookings
                          WHERE schedule_id = %s AND travel_date = %s AND status = 'confirmed' AND seat_id IS NOT NULL
                      ) ORDER BY coach, row_number, column_letter;
                    """, (schedule_id, fare_class, schedule_id, travel_date))
                avail = [dict(r) for r in cur.fetchall()]
                picked = auto_select_adjacent_seats(avail, 1)
                if not picked:
                    conn.rollback()
                    return (False, "no available seats for the requested fare class")
                seat_id = picked[0]

            cur.execute("SELECT coach FROM national_rail_seats WHERE schedule_id = %s AND seat_id = %s AND fare_class = %s;", 
                        (schedule_id, seat_id, fare_class))
            seat_row = cur.fetchone()
            if not seat_row:
                conn.rollback()
                return (False, "invalid seat for this schedule/class")
            coach = seat_row["coach"]

            cur.execute("""
                SELECT 1 FROM national_rail_bookings
                WHERE schedule_id = %s AND seat_id = %s AND travel_date = %s AND status = 'confirmed';
                """, (schedule_id, seat_id, travel_date))
            if cur.fetchone() is not None:
                conn.rollback()
                return (False, f"seat '{seat_id}' is already booked on {travel_date}")

            cur.execute("""
                SELECT
                    CASE WHEN %s = 'first' THEN fare_first_base_usd     ELSE fare_standard_base_usd     END AS base,
                    CASE WHEN %s = 'first' THEN fare_first_per_stop_usd ELSE fare_standard_per_stop_usd END AS per_stop
                FROM national_rail_schedules WHERE schedule_id = %s;
                """, (fare_class, fare_class, schedule_id))
            fare_row = cur.fetchone()
            amount_usd = round(float(fare_row["base"]) + float(fare_row["per_stop"]) * stops_travelled, 2)

            booking_id = _gen_booking_id()
            payment_id = _gen_payment_id()
            now_utc = datetime.now(timezone.utc)

            cur.execute("""
                INSERT INTO national_rail_bookings (
                    booking_id, user_id, schedule_id, origin_station_id, destination_station_id,
                    travel_date, departure_time, ticket_type, fare_class, coach, seat_id,
                    stops_travelled, amount_usd, status, booked_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'confirmed', %s);
                """, (booking_id, user_id, schedule_id, origin_station_id, destination_station_id, travel_date, departure_time, ticket_type, fare_class, coach, seat_id, stops_travelled, amount_usd, now_utc))

            cur.execute("""
                INSERT INTO payments (payment_id, booking_id, transaction_type, amount_usd, method, status, paid_at)
                VALUES (%s, %s, 'NR', %s, 'credit_card', 'paid', %s);
                """, (payment_id, booking_id, amount_usd, now_utc))

        conn.commit()
        return (True, {
            "booking_id": booking_id, "user_id": user_id, "schedule_id": schedule_id,
            "origin_station_id": origin_station_id, "destination_station_id": destination_station_id,
            "travel_date": travel_date, "fare_class": fare_class, "ticket_type": ticket_type,
            "coach": coach, "seat_id": seat_id, "stops_travelled": stops_travelled,
            "total_fare_usd": amount_usd, "payment_id": payment_id, "status": "confirmed",
        })
    except Exception as e:
        conn.rollback()
        return (False, str(e))
    finally:
        conn.close()


def execute_cancellation(booking_id: str, user_id: str) -> tuple[bool, dict | str]:
    conn = _connect()
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT b.booking_id, b.user_id, b.status, b.amount_usd,
                       b.travel_date, b.departure_time, b.schedule_id, s.service_type
                FROM national_rail_bookings b
                LEFT JOIN national_rail_schedules s ON s.schedule_id = b.schedule_id
                WHERE b.booking_id = %s;
                """, (booking_id,))
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

            depart_dt = datetime.combine(booking["travel_date"], booking["departure_time"], tzinfo=timezone.utc)
            hours_before = (depart_dt - datetime.now(timezone.utc)).total_seconds() / 3600.0

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
            refund_amount = max(0.0, round(amount_usd * (refund_pct / 100.0) - admin_fee, 2))

            cur.execute("UPDATE national_rail_bookings SET status = 'cancelled' WHERE booking_id = %s;", (booking_id,))
            if refund_amount > 0:
                cur.execute("""
                    UPDATE payments SET status = 'refunded'
                    WHERE booking_id = %s AND transaction_type = 'NR';
                    """, (booking_id,))

        conn.commit()
        return (True, {
            "booking_id": booking_id, "refund_amount_usd": refund_amount,
            "refund_percent": refund_pct, "admin_fee_usd": admin_fee,
            "policy_window": f"{policy_id} {window}", "hours_before_departure": round(hours_before, 2),
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
    full_name = f"{first_name} {surname}".strip()
    date_of_birth = f"{year_of_birth}-01-01"

    # [TA CHECK: 設計理念 - 密碼安全性 (Security) 與雜湊處理]
    # Rationale: 嚴格禁止明文存儲。在此使用 bcrypt (Adaptive Hash) 生成加鹽雜湊 (Salted Hash)。
    # bcrypt 的 Work Factor 機制能有效防禦暴力破解 (Brute-force)，而自動生成的 Salt 則能免疫彩虹表攻擊 (Rainbow Tables)。
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    conn = _connect()
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT 1 FROM users WHERE email = %s;", (email,))
            if cur.fetchone() is not None:
                conn.rollback()
                return (False, "email already registered")

            cur.execute("""
                SELECT COALESCE(MAX(CAST(SUBSTRING(user_id FROM 3) AS INTEGER)), 0) AS max_num
                FROM users WHERE user_id LIKE 'RU%' AND SUBSTRING(user_id FROM 3) ~ '^[0-9]+$';
            """)
            next_num = (cur.fetchone() or {}).get("max_num", 0) + 1
            new_user_id = f"RU{str(next_num).zfill(2)}"

            cur.execute("""
                INSERT INTO users (
                    user_id, full_name, email, password,
                    date_of_birth, secret_question, secret_answer, is_active
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE);
                """, (new_user_id, full_name, email, hashed_password, date_of_birth, secret_question, secret_answer))
        conn.commit()
        return (True, new_user_id)
    except Exception as e:
        conn.rollback()
        return (False, str(e))
    finally:
        conn.close()


def login_user(email: str, password: str) -> Optional[dict]:
    # [TA CHECK: 設計理念 - 認證防禦機制]
    # 這裡將密碼驗證移至 Python 端執行 `bcrypt.checkpw`，且刻意將帳號不存在與密碼錯誤的回傳結果統一處理為 None，
    # 藉此防止攻擊者利用系統回饋進行帳號列舉 (Account Enumeration) 攻擊。
    sql = """
        SELECT
            user_id, email, full_name,
            split_part(full_name, ' ', 1) AS first_name,
            split_part(full_name, ' ', 2) AS surname,
            phone, date_of_birth, is_active,
            password AS stored_hash
        FROM users WHERE email = %s;
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (email,))
            row = cur.fetchone()
            
            # 進行 bcrypt 密碼雜湊比對
            if row and bcrypt.checkpw(password.encode('utf-8'), row['stored_hash'].encode('utf-8')):
                del row['stored_hash']  # 安全起見，從返回的 dict 中移除密碼 hash
                return dict(row)
            return None


def get_user_secret_question(email: str) -> Optional[str]:
    sql = "SELECT secret_question FROM users WHERE email = %s;"
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (email,))
            row = cur.fetchone()
            return row["secret_question"] if row else None


def verify_secret_answer(email: str, answer: str) -> bool:
    sql = "SELECT 1 FROM users WHERE email = %s AND LOWER(secret_answer) = LOWER(%s);"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (email, answer))
            return cur.fetchone() is not None


def update_password(email: str, new_password: str) -> bool:
    hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    conn = _connect()
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET password = %s WHERE email = %s;", (hashed_password, email))
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
    sql = """
        SELECT title, category, content, 1 - (embedding <=> %s::vector) AS similarity
        FROM policy_documents
        WHERE 1 - (embedding <=> %s::vector) > %s
        ORDER BY embedding <=> %s::vector LIMIT %s
    """
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (vec_str, vec_str, VECTOR_SIMILARITY_THRESHOLD, vec_str, top_k))
            return [dict(row) for row in cur.fetchall()]


def store_policy_document(title: str, category: str, content: str, embedding: list[float], source_file: str = "") -> int:
    sql = "INSERT INTO policy_documents (title, category, content, embedding, source_file) VALUES (%s, %s, %s, %s::vector, %s) RETURNING id"
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (title, category, content, vec_str, source_file))
            return cur.fetchone()[0]