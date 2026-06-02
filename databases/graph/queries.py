"""
TransitFlow — Neo4j Graph Database Layer
=========================================
This module handles all queries to Neo4j.
"""

from __future__ import annotations

from typing import Optional
from neo4j import GraphDatabase
from skeleton.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

def _driver():
    """Return a Neo4j driver. Caller is responsible for closing."""
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# ── Example ───────────────────────────────────────────────────────────────────

def example_count_nodes() -> int:
    """Example: count all nodes currently in the graph."""
    with _driver() as driver:
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) AS total")
            return result.single()["total"]


# ── FASTEST ROUTE (Dijkstra by travel_time_min) ───────────────────────────────

def query_shortest_route(origin_id: str, destination_id: str, network: str = "auto") -> dict:
    """Find the fastest path between two stations, minimising total travel time."""
    cypher = """
    MATCH (start:Station {station_id: $origin}), (end:Station {station_id: $destination})
    CALL apoc.algo.dijkstra(start, end, 'CONNECTS_TO>|INTERCHANGE>', 'travel_time_min')
    YIELD path, weight
    RETURN path, weight AS total_time_min
    """
    with _driver() as driver, driver.session() as session:
        res = session.run(cypher, origin=origin_id, destination=destination_id).single()
        
        if not res or not res.get("path"):
            return {"found": False}
        
        # 拆解 Neo4j 的 Path 物件，轉成 AI 易讀的站點清單
        stations = [{"station_id": n["station_id"], "name": n["name"], "network": n["network"]} for n in res["path"].nodes]
        
        return {
            "found": True,
            "origin_id": origin_id,
            "destination_id": destination_id,
            "total_time_min": res["total_time_min"],
            "path": stations
        }


# ── CHEAPEST ROUTE (Dijkstra by fare) ────────────────────────────────────────

def query_cheapest_route(origin_id: str, destination_id: str, network: str = "auto", fare_class: str = "standard") -> dict:
    """
    Find the cheapest path between two stations, minimising total estimated fare.
    (Since fares are stop-based, cheapest = fewest hops / shortestPath)
    """
    # 由於我們的票價是算「站數 (stops)」，所以最便宜的路徑就是「經過最少站」的路徑。
    # 這裡直接用 Neo4j 原生的 shortestPath (以 hop 數為權重) 來找最少站數的路徑。
    cypher = """
    MATCH (start:Station {station_id: $origin}), (end:Station {station_id: $destination})
    MATCH path = shortestPath((start)-[:CONNECTS_TO|INTERCHANGE*..20]->(end))
    RETURN path, length(path) AS stops
    """
    with _driver() as driver, driver.session() as session:
        res = session.run(cypher, origin=origin_id, destination=destination_id).single()
        
        if not res or not res.get("path"):
            return {"found": False}
        
        stations = [{"station_id": n["station_id"], "name": n["name"]} for n in res["path"].nodes]
        stops = res["stops"]
        
        # 簡單估算票價 (提供給 AI 參考，精確票價會由 SQL 負責)
        approx_fare = 2.50 + (stops * 1.50) if start_id.startswith("NR") else 0.80 + (stops * 0.30)

        return {
            "found": True,
            "total_fare_usd_approx": round(approx_fare, 2),
            "stops": stops,
            "stations": stations
        }


# ── ALTERNATIVE ROUTES (avoiding a station) ───────────────────────────────────

def query_alternative_routes(origin_id: str, destination_id: str, avoid_station_id: str, network: str = "auto", max_routes: int = 3) -> list[list[dict]]:
    """Find paths between two stations that avoid a specific intermediate station."""
    cypher = """
    MATCH (start:Station {station_id: $origin}), (end:Station {station_id: $destination}),
          path = (start)-[:CONNECTS_TO|INTERCHANGE*..15]->(end)
    WHERE NONE(n IN nodes(path) WHERE n.station_id = $avoid_id)
    RETURN path, reduce(t = 0, r IN relationships(path) | t + r.travel_time_min) AS total_time
    ORDER BY total_time LIMIT $max_routes
    """
    with _driver() as driver, driver.session() as session:
        results = session.run(cypher, origin=origin_id, destination=destination_id, avoid_id=avoid_station_id, max_routes=max_routes)
        
        routes = []
        for res in results:
            route_nodes = [{"station_id": n["station_id"], "name": n["name"]} for n in res["path"].nodes]
            routes.append(route_nodes)
            
        return routes


# ── CROSS-NETWORK INTERCHANGE PATH ───────────────────────────────────────────

def query_interchange_path(origin_id: str, destination_id: str) -> dict:
    """Find a path between a metro station and a national rail station."""
    cypher = """
    MATCH (start:Station {station_id: $origin}), (end:Station {station_id: $destination})
    WHERE start.network <> end.network
    CALL apoc.algo.dijkstra(start, end, 'CONNECTS_TO>|INTERCHANGE>', 'travel_time_min')
    YIELD path, weight
    RETURN path, weight AS total_time_min,
           [n IN nodes(path) WHERE n.is_interchange_metro = true AND n.is_interchange_national_rail = true | n.station_id] AS interchange_points
    """
    with _driver() as driver, driver.session() as session:
        res = session.run(cypher, origin=origin_id, destination=destination_id).single()
        
        if not res or not res.get("path"):
            return {"found": False}
            
        stations = [{"station_id": n["station_id"], "name": n["name"], "network": n["network"]} for n in res["path"].nodes]
        
        return {
            "found": True,
            "stations": stations,
            "interchange_points": res["interchange_points"],
            "total_time_min": res["total_time_min"]
        }


# ── DELAY RIPPLE ANALYSIS ─────────────────────────────────────────────────────

def query_delay_ripple(delayed_station_id: str, hops: int = 2) -> list[dict]:
    """Find all stations within N hops of a delayed or disrupted station."""
    # 在 Cypher 中，變數長度路徑無法直接用參數帶入 (*1..$hops 會報錯)
    # 所以我們在這裡使用 f-string 安全地動態注入 hops 數字
    cypher = f"""
    MATCH (s:Station {{station_id: $delayed_id}})-[:CONNECTS_TO|INTERCHANGE*1..{hops}]-(affected:Station)
    RETURN DISTINCT affected.station_id AS station_id, affected.name AS name, affected.lines AS lines
    """
    with _driver() as driver, driver.session() as session:
        results = session.run(cypher, delayed_id=delayed_station_id)
        return [record.data() for record in results]


# ── STATION CONNECTIONS ───────────────────────────────────────────────────────

def query_station_connections(station_id: str) -> list[dict]:
    """List all direct connections from a given station."""
    cypher = """
    MATCH (s:Station {station_id: $station_id})-[r:CONNECTS_TO|INTERCHANGE]->(neighbor:Station)
    RETURN neighbor.station_id AS station_id, neighbor.name AS name, type(r) AS rel_type,
           r.line AS line, r.travel_time_min AS travel_time_min
    """
    with _driver() as driver, driver.session() as session:
        results = session.run(cypher, station_id=station_id)
        return [record.data() for record in results]
