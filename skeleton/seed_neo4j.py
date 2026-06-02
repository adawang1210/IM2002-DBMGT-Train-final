"""
TransitFlow — Neo4j Seeder
Run once after starting Docker:
    python skeleton/seed_neo4j.py

Loads station and network data from train-mock-data/:
  - metro_stations.json         — city metro stations and adjacencies
  - national_rail_stations.json — national rail stations and adjacencies

Schema (locked in DATA_DICTIONARY_GRAPH_FINAL.md):
  Nodes:
    (:Station {station_id, name, network, lines,
               is_interchange_metro, is_interchange_national_rail})
  Relationships:
    (:Station)-[:CONNECTS_TO {network, line, travel_time_min}]->(:Station)
        - bidirectional (one MERGE per direction)
    (:Station)-[:INTERCHANGE {travel_time_min, transfer_type, transfer_note}]->(:Station)
        - bidirectional, default travel_time_min = 5 (APOC Dijkstra cannot accept NULL)
"""

import json
import os
import sys

sys.path.insert(0, ".")

from neo4j import GraphDatabase
from skeleton.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

_DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "train-mock-data")
)

# Default walking transfer time between metro <-> rail when not provided in JSON.
# Required because APOC Dijkstra treats NULL relationship weights as infinite.
INTERCHANGE_DEFAULT_MIN = 5


def _load(filename):
    with open(os.path.join(_DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def seed():
    metro_stations = _load("metro_stations.json")
    rail_stations  = _load("national_rail_stations.json")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:

        # ── Constraints / Indexes (idempotent, survive DETACH DELETE) ────────
        session.run(
            "CREATE CONSTRAINT station_id_unique IF NOT EXISTS "
            "FOR (s:Station) REQUIRE s.station_id IS UNIQUE"
        )
        session.run(
            "CREATE INDEX station_network IF NOT EXISTS "
            "FOR (s:Station) ON (s.network)"
        )
        print("  Ensured constraints and indexes")

        # ── Wipe existing data so re-runs start fresh ────────────────────────
        session.run("MATCH (n) DETACH DELETE n")
        print("  Cleared existing graph data")

        # ── Create metro Station nodes ───────────────────────────────────────
        for s in metro_stations:
            session.run(
                """
                MERGE (n:Station {station_id: $station_id})
                SET n.name                         = $name,
                    n.network                      = 'metro',
                    n.lines                        = $lines,
                    n.is_interchange_metro         = $is_interchange_metro,
                    n.is_interchange_national_rail = $is_interchange_national_rail
                """,
                station_id=s["station_id"],
                name=s["name"],
                lines=s["lines"],
                is_interchange_metro=bool(s.get("is_interchange_metro", False)),
                is_interchange_national_rail=bool(s.get("is_interchange_national_rail", False)),
            )
        print(f"  Created {len(metro_stations)} metro Station nodes")

        # ── Create national rail Station nodes ───────────────────────────────
        for s in rail_stations:
            session.run(
                """
                MERGE (n:Station {station_id: $station_id})
                SET n.name                         = $name,
                    n.network                      = 'rail',
                    n.lines                        = $lines,
                    n.is_interchange_metro         = $is_interchange_metro,
                    n.is_interchange_national_rail = $is_interchange_national_rail
                """,
                station_id=s["station_id"],
                name=s["name"],
                lines=s["lines"],
                is_interchange_metro=bool(s.get("is_interchange_metro", False)),
                is_interchange_national_rail=bool(s.get("is_interchange_national_rail", False)),
            )
        print(f"  Created {len(rail_stations)} national rail Station nodes")

        # ── Create CONNECTS_TO edges within metro network ────────────────────
        # JSON lists every adjacency from both endpoints, so iterating and
        # MERGE-ing one direction per entry naturally produces both directions.
        # MERGE on (line) keeps multi-line pairs from collapsing.
        metro_edge_count = 0
        for s in metro_stations:
            for adj in s.get("adjacent_stations", []):
                session.run(
                    """
                    MATCH (a:Station {station_id: $a_id})
                    MATCH (b:Station {station_id: $b_id})
                    MERGE (a)-[r:CONNECTS_TO {line: $line}]->(b)
                    SET   r.network         = 'metro',
                          r.travel_time_min = $time
                    """,
                    a_id=s["station_id"],
                    b_id=adj["station_id"],
                    line=adj["line"],
                    time=adj["travel_time_min"],
                )
                metro_edge_count += 1
        print(f"  Created {metro_edge_count} metro CONNECTS_TO edges")

        # ── Create CONNECTS_TO edges within national rail network ────────────
        rail_edge_count = 0
        for s in rail_stations:
            for adj in s.get("adjacent_stations", []):
                session.run(
                    """
                    MATCH (a:Station {station_id: $a_id})
                    MATCH (b:Station {station_id: $b_id})
                    MERGE (a)-[r:CONNECTS_TO {line: $line}]->(b)
                    SET   r.network         = 'rail',
                          r.travel_time_min = $time
                    """,
                    a_id=s["station_id"],
                    b_id=adj["station_id"],
                    line=adj["line"],
                    time=adj["travel_time_min"],
                )
                rail_edge_count += 1
        print(f"  Created {rail_edge_count} national rail CONNECTS_TO edges")

        # ── Create INTERCHANGE edges across networks (bidirectional) ─────────
        # Source of truth: metro_stations.json (each interchange metro station
        # carries interchange_national_rail_station_id pointing to its rail
        # counterpart). Default travel_time_min = 5 so APOC Dijkstra can use
        # the relationship as a real edge weight.
        interchange_count = 0
        for s in metro_stations:
            if not s.get("is_interchange_national_rail"):
                continue
            rail_id = s.get("interchange_national_rail_station_id")
            if not rail_id:
                continue

            note = f"{s['name']} <-> rail"  # debug-friendly label
            session.run(
                """
                MATCH (m:Station {station_id: $m_id})
                MATCH (n:Station {station_id: $n_id})
                MERGE (m)-[r1:INTERCHANGE]->(n)
                SET   r1.travel_time_min = $time,
                      r1.transfer_type   = 'metro_rail',
                      r1.transfer_note   = $note
                MERGE (n)-[r2:INTERCHANGE]->(m)
                SET   r2.travel_time_min = $time,
                      r2.transfer_type   = 'metro_rail',
                      r2.transfer_note   = $note
                """,
                m_id=s["station_id"],
                n_id=rail_id,
                time=INTERCHANGE_DEFAULT_MIN,
                note=note,
            )
            interchange_count += 2  # one MERGE per direction
        print(f"  Created {interchange_count} INTERCHANGE edges (bidirectional)")

        # ── Verification counts ──────────────────────────────────────────────
        totals = session.run(
            """
            MATCH (s:Station) WITH count(s) AS stations
            OPTIONAL MATCH ()-[c:CONNECTS_TO]->() WITH stations, count(c) AS connects
            OPTIONAL MATCH ()-[i:INTERCHANGE]->() WITH stations, connects, count(i) AS interchange
            RETURN stations, connects, interchange
            """
        ).single()
        print(
            "\nGraph totals: "
            f"Station={totals['stations']}, "
            f"CONNECTS_TO={totals['connects']}, "
            f"INTERCHANGE={totals['interchange']}"
        )
        print("Expected:     Station=30, CONNECTS_TO=60, INTERCHANGE=6")

    driver.close()
    print("\nNeo4j graph seeded successfully.")
    print("   Open http://localhost:7475 to explore the graph.")


if __name__ == "__main__":
    print("Connecting to Neo4j...")
    seed()
