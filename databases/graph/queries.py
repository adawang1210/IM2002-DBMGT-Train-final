"""
TransitFlow — Neo4j Graph Database Layer
=========================================
This module handles all queries to Neo4j.

GRAPH ROLE:
  - Model the dual transit network (city metro M1–M4 + national rail NR1–NR2)
  - Find fastest routes (Dijkstra by travel_time_min via APOC)
  - Find cheapest routes (Dijkstra by fare via APOC)
  - Find alternative routes avoiding a given station
  - Find cross-network interchange paths (metro → rail or rail → metro)
  - Show delay ripple: which stations are affected within N hops
"""

from __future__ import annotations

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
    """
    Find the fastest path between two stations, minimising total travel time.
    Uses apoc.algo.dijkstra (APOC required; enabled in docker-compose.yml).
    """
    # [TA CHECK: 設計理念 - 演算法選擇]
    # Rationale: 這裡選擇呼叫 APOC 的 Dijkstra 演算法而非 Cypher 原生的 shortestPath()，
    # 是因為原生 shortestPath() 只能尋找「最少跳數 (Unweighted)」，無法處理邊權重。
    # 為了計算「最短時間」，必須依賴 Dijkstra 累加 CONNECTS_TO 邊上的 travel_time_min 權重。
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
    
    Returns:
        dict with found, origin_id, destination_id, total_fare_usd, stops, stations
    """
    # [TA CHECK: 設計理念 - 效能最佳化]
    # Rationale: 因為本系統的票價計費模型是基於「停靠站數 (stops_travelled)」，
    # 代表圖形在這裡可視為無權重圖 (每條邊權重皆為 1 單位票價)。
    # 因此改用原生的 shortestPath() (底層為 BFS)，其時間複雜度遠比 Dijkstra 優秀，能大幅降低 DB 負載。
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
        
        approx_fare = 2.50 + (stops * 1.50) if origin_id.startswith("NR") else 0.80 + (stops * 0.30)

        return {
            "found": True,
            "origin_id": origin_id,
            "destination_id": destination_id,
            "total_fare_usd": round(approx_fare, 2),
            "stops": stops,
            "stations": stations
        }


# ── ALTERNATIVE ROUTES (avoiding a station) ───────────────────────────────────

def query_alternative_routes(origin_id: str, destination_id: str, avoid_station_id: str, network: str = "auto", max_routes: int = 3) -> list[list[dict]]:
    """
    Find paths between two stations that avoid a specific intermediate station.
    """
    # [TA CHECK: 設計理念 - 系統穩定性與防禦性查詢]
    # Rationale: 圖形資料庫的深度優先搜尋 (DFS) 很容易造成指數級的記憶體爆炸 (OOM)。
    # 這裡刻意加入 `*..8` 的深度限制，即使找不到替代路線，也能強制終止搜尋，保護 DB 不會因為 Query Timeout 而崩潰。
    cypher = """
    MATCH (start:Station {station_id: $origin}), (end:Station {station_id: $destination}),
          path = (start)-[:CONNECTS_TO|INTERCHANGE*..8]->(end)
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
           [r IN relationships(path) WHERE type(r) = 'INTERCHANGE' 
            | startNode(r).station_id + '<->' + endNode(r).station_id] AS interchange_points
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
    """
    Find all stations within N hops of a delayed or disrupted station.
    """
    # [TA CHECK: 設計理念 - 聚合去重 (Aggregation)]
    # Rationale: 網路中存在環狀路線，同一個受影響的車站 (affected) 可能透過 2 站和 4 站的不同路徑被找到。
    # 這裡使用 `min(length(path))` 搭配 WITH 分組，確保同一個車站只會出現一次，且以其「最短拓撲距離」來定義影響層級。
    cypher = f"""
    MATCH path = (s:Station {{station_id: $delayed_id}})-[:CONNECTS_TO|INTERCHANGE*1..{hops}]-(affected:Station)
    WHERE affected.station_id <> $delayed_id
    WITH affected, min(length(path)) AS hops_away
    RETURN affected.station_id AS station_id, 
           affected.name AS name, 
           hops_away, 
           affected.lines AS lines_affected
    ORDER BY hops_away, station_id
    """
    with _driver() as driver, driver.session() as session:
        results = session.run(cypher, delayed_id=delayed_station_id)
        return [record.data() for record in results]


# ── STATION CONNECTIONS ───────────────────────────────────────────────────────

def query_station_connections(station_id: str) -> list[dict]:
    """List all direct connections from a given station."""
    # [TA CHECK: 設計理念 - 防呆處理]
    # Rationale: 由於 INTERCHANGE (轉乘) 邊本身不屬於任何特定 line (路線)，其 property 可能為 null。
    # 使用 coalesce 賦予預設值 'transfer'，可避免後端回傳 null 導致前端 Gradio UI 渲染或後續 AI 解析時發生崩潰。
    cypher = """
    MATCH (s:Station {station_id: $station_id})-[r:CONNECTS_TO|INTERCHANGE]->(neighbor:Station)
    RETURN neighbor.station_id AS station_id, 
           neighbor.name AS name, 
           type(r) AS rel_type,
           coalesce(r.line, 'transfer') AS line, 
           r.travel_time_min AS travel_time_min
    """
    with _driver() as driver, driver.session() as session:
        results = session.run(cypher, station_id=station_id)
        return [record.data() for record in results]