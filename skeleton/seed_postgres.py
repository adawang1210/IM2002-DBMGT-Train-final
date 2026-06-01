"""
Seed PostgreSQL with all TransitFlow mock data from train-mock-data/.

Usage:
    python skeleton/seed_postgres.py

Run AFTER docker-compose up -d.
You must first design and create your tables in databases/relational/schema.sql.
Safe to re-run: implement your inserts with ON CONFLICT DO NOTHING.
"""

import json
import os
import sys

import psycopg2
from psycopg2.extras import execute_values

# ── resolve paths ────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR    = os.path.join(PROJECT_DIR, "train-mock-data")

sys.path.insert(0, PROJECT_DIR)
from skeleton import config as cfg


def load(filename):
    with open(os.path.join(DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def connect():
    return psycopg2.connect(
        host=cfg.PG_HOST,
        port=cfg.PG_PORT,
        dbname=cfg.PG_DB,
        user=cfg.PG_USER,
        password=cfg.PG_PASSWORD,
    )


def insert_many(cur, table, columns, rows):
    """Bulk insert with ON CONFLICT DO NOTHING. Returns row count inserted."""
    if not rows:
        return 0
    sql = (
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s "
        f"ON CONFLICT DO NOTHING"
    )
    execute_values(cur, sql, rows)
    return cur.rowcount


# ── seeders ──────────────────────────────────────────────────────────────────

def seed_users(cur):
    data = load("registered_users.json")
    rows = []
    for u in data:
        rows.append((
            u["user_id"],
            u["full_name"],
            u["email"],
            u["password"],
            u.get("phone"),
            u.get("date_of_birth"),
            u.get("secret_question"),
            u.get("secret_answer"),
            u["registered_at"],
            u["is_active"]
        ))
    
    columns = ["user_id", "full_name", "email", "password", "phone", "date_of_birth", "secret_question", "secret_answer", "registered_at", "is_active"]
    n = insert_many(cur, "users", columns, rows)
    print(f"  users: {n} rows")


def seed_metro_stations(cur):
    data = load("metro_stations.json")
    rows = []
    for s in data:
        rows.append((
            s["station_id"],
            s["name"],
            s["lines"],
            s.get("is_interchange_metro", False),
            s.get("interchange_metro_lines"),
            s.get("is_interchange_national_rail", False),
            s.get("interchange_national_rail_station_id")
        ))
    
    columns = ["station_id", "name", "lines", "is_interchange_metro", "interchange_metro_lines", "is_interchange_national_rail", "interchange_national_rail_station_id"]
    n = insert_many(cur, "metro_stations", columns, rows)
    print(f"  metro_stations: {n} rows")


def seed_national_rail_stations(cur):
    data = load("national_rail_stations.json")
    rows = []
    for s in data:
        rows.append((
            s["station_id"],
            s["name"],
            s["lines"],
            s.get("is_interchange_national_rail", False),
            s.get("interchange_national_rail_lines"),
            s.get("is_interchange_metro", False),
            s.get("interchange_metro_station_id")
        ))
    
    columns = ["station_id", "name", "lines", "is_interchange_national_rail", "interchange_national_rail_lines", "is_interchange_metro", "interchange_metro_station_id"]
    n = insert_many(cur, "national_rail_stations", columns, rows)
    print(f"  national_rail_stations: {n} rows")


def seed_metro_schedules(cur):
    data = load("metro_schedules.json")
    schedules_rows = []
    stops_rows = []
    
    for sch in data:
        schedules_rows.append((
            sch["schedule_id"],
            sch["line"],
            sch["direction"],
            sch["origin_station_id"],
            sch["destination_station_id"],
            sch.get("first_train_time"),
            sch.get("last_train_time"),
            sch.get("base_fare_usd", 0.80),
            sch.get("per_stop_rate_usd", 0.30),
            sch.get("frequency_min"),
            sch.get("operates_on")
        ))
        
        stop_order = 1
        for station_id in sch.get("stops_in_order", []):
            travel_time = sch.get("travel_time_from_origin_min", {}).get(station_id, 0)
            stops_rows.append((sch["schedule_id"], stop_order, station_id, travel_time))
            stop_order += 1

    cols_sch = ["schedule_id", "line", "direction", "origin_station_id", "destination_station_id", "first_train_time", "last_train_time", "base_fare_usd", "per_stop_rate_usd", "frequency_min", "operates_on"]
    n_sch = insert_many(cur, "metro_schedules", cols_sch, schedules_rows)
    
    cols_stops = ["schedule_id", "stop_order", "station_id", "travel_time_from_origin_min"]
    n_stops = insert_many(cur, "metro_schedule_stops", cols_stops, stops_rows)
    print(f"  metro_schedules: {n_sch} rows, stops: {n_stops} rows")


def seed_national_rail_schedules(cur):
    data = load("national_rail_schedules.json")
    schedules_rows = []
    stops_rows = []
    
    for sch in data:
        schedules_rows.append((
            sch["schedule_id"],
            sch["line"],
            sch["service_type"],
            sch["direction"],
            sch["origin_station_id"],
            sch["destination_station_id"],
            sch.get("first_train_time"),
            sch.get("last_train_time"),
            sch["fare_classes"]["standard"]["base_fare_usd"],
            sch["fare_classes"]["standard"]["per_stop_rate_usd"],
            sch["fare_classes"]["first"]["base_fare_usd"],
            sch["fare_classes"]["first"]["per_stop_rate_usd"],
            sch.get("frequency_min"),
            sch.get("operates_on")
        ))
        
        stop_order = 1
        for station_id in sch.get("stops_in_order", []):
            travel_time = sch.get("travel_time_from_origin_min", {}).get(station_id, 0)
            stops_rows.append((sch["schedule_id"], stop_order, station_id, travel_time, False))
            stop_order += 1
            
        for station_id in sch.get("passed_through_stations", []):
            stops_rows.append((sch["schedule_id"], stop_order, station_id, 0, True))
            stop_order += 1

    cols_sch = ["schedule_id", "line", "service_type", "direction", "origin_station_id", "destination_station_id", "first_train_time", "last_train_time", "fare_standard_base_usd", "fare_standard_per_stop_usd", "fare_first_base_usd", "fare_first_per_stop_usd", "frequency_min", "operates_on"]
    n_sch = insert_many(cur, "national_rail_schedules", cols_sch, schedules_rows)
    
    cols_stops = ["schedule_id", "stop_order", "station_id", "travel_time_from_origin_min", "is_passed_through"]
    n_stops = insert_many(cur, "national_rail_schedule_stops", cols_stops, stops_rows)
    print(f"  national_rail_schedules: {n_sch} rows, stops: {n_stops} rows")


def seed_seat_layouts(cur):
    data = load("national_rail_seat_layouts.json")
    rows = []
    for layout in data:
        schedule_id = layout["schedule_id"]
        for coach in layout.get("coaches", []):
            coach_letter, fare_class = coach["coach"], coach["fare_class"]
            for seat in coach.get("seats", []):
                rows.append((schedule_id, seat["seat_id"], coach_letter, fare_class, seat["row"], seat["column"]))
                
    cols = ["schedule_id", "seat_id", "coach", "fare_class", "row_number", "column_letter"]
    n = insert_many(cur, "national_rail_seats", cols, rows)
    print(f"  national_rail_seats: {n} rows")


def seed_national_rail_bookings(cur):
    data = load("bookings.json")
    rows = []
    for b in data:
        rows.append((
            b["booking_id"], b["user_id"], b["schedule_id"], b["origin_station_id"],
            b["destination_station_id"], b["travel_date"], b.get("departure_time"),
            b["ticket_type"], b["fare_class"], b.get("coach"), b.get("seat_id"),
            b.get("stops_travelled"), b["amount_usd"], b["status"], b.get("booked_at"), b.get("travelled_at")
        ))
        
    cols = ["booking_id", "user_id", "schedule_id", "origin_station_id", "destination_station_id", "travel_date", "departure_time", "ticket_type", "fare_class", "coach", "seat_id", "stops_travelled", "amount_usd", "status", "booked_at", "travelled_at"]
    n = insert_many(cur, "national_rail_bookings", cols, rows)
    print(f"  national_rail_bookings: {n} rows")


def seed_metro_travels(cur):
    data = load("metro_travel_history.json")
    rows = []
    for t in data:
        rows.append((
            t["trip_id"], t["user_id"], t["schedule_id"], t["origin_station_id"],
            t["destination_station_id"], t["travel_date"], t["ticket_type"],
            t.get("day_pass_ref"), t.get("stops_travelled"), t["amount_usd"],
            t["status"], t.get("purchased_at"), t.get("travelled_at")
        ))
        
    cols = ["trip_id", "user_id", "schedule_id", "origin_station_id", "destination_station_id", "travel_date", "ticket_type", "day_pass_ref", "stops_travelled", "amount_usd", "status", "purchased_at", "travelled_at"]
    n = insert_many(cur, "metro_travel_history", cols, rows)
    print(f"  metro_travel_history: {n} rows")


def seed_payments(cur):
    data = load("payments.json")
    rows = []
    for p in data:
        transaction_type = 'NR' if p["booking_id"].startswith('BK') else 'Metro'
        rows.append((p["payment_id"], p["booking_id"], transaction_type, p["amount_usd"], p.get("method"), p["status"], p.get("paid_at")))
        
    cols = ["payment_id", "booking_id", "transaction_type", "amount_usd", "method", "status", "paid_at"]
    n = insert_many(cur, "payments", cols, rows)
    print(f"  payments: {n} rows")


def seed_feedback(cur):
    data = load("feedback.json")
    rows = []
    for f in data:
        transaction_type = 'NR' if f["booking_id"].startswith('BK') else 'Metro'
        rows.append((f["feedback_id"], f["booking_id"], transaction_type, f["user_id"], f["rating"], f.get("comment"), f.get("submitted_at")))
        
    cols = ["feedback_id", "booking_id", "transaction_type", "user_id", "rating", "comment", "submitted_at"]
    n = insert_many(cur, "feedback", cols, rows)
    print(f"  feedback: {n} rows")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print("Connecting to PostgreSQL...")
    conn = connect()
    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("Seeding tables (dependency order):")
        seed_metro_stations(cur)
        seed_national_rail_stations(cur)
        seed_metro_schedules(cur)
        seed_national_rail_schedules(cur)
        seed_seat_layouts(cur)
        seed_users(cur)
        seed_national_rail_bookings(cur)
        seed_metro_travels(cur)
        seed_payments(cur)
        seed_feedback(cur)
        conn.commit()
        print("\nAll done. Database seeded successfully.")
    except Exception as e:
        conn.rollback()
        print(f"\nError: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
