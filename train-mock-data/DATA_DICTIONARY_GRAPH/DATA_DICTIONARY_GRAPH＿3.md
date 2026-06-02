# 張恩家
---

# TransitFlow Graph Database Schema

## 一、Nodes

## 1. Station

代表所有車站，包含 Metro 與 National Rail。

| Property                     | 說明      | 範例             |
| ---------------------------- | ------- | -------------- |
| station_id                   | 車站編號    | MS01、NR01      |
| name                         | 車站名稱    | Central Square |
| network                      | 所屬系統    | metro、rail     |
| lines                        | 所屬路線    | M1、M2          |
| is_interchange_metro         | 是否可轉乘捷運 | true           |
| is_interchange_national_rail | 是否可轉乘國鐵 | true           |

---

## 2. Line

代表交通路線。

| Property | 說明   | 範例           |
| -------- | ---- | ------------ |
| line_id  | 路線編號 | M1、NR1       |
| name     | 路線名稱 | Metro Line 1 |
| network  | 所屬系統 | metro、rail   |

---

## 3. Network

代表交通系統。

| Property | 說明   | 範例                  |
| -------- | ---- | ------------------- |
| name     | 系統名稱 | Metro、National Rail |
| type     | 系統類型 | metro、rail          |

---

# 二、Relationships

## 1. CONNECTS_TO

代表兩個相鄰車站之間的連接。

| Relationship | 起點      | 終點      | 說明        |
| ------------ | ------- | ------- | --------- |
| CONNECTS_TO  | Station | Station | 車站與相鄰車站相連 |

### Properties

| Property        | 說明   | 範例         |
| --------------- | ---- | ---------- |
| line            | 所屬路線 | M1、NR1     |
| travel_time_min | 行駛時間 | 3          |
| network         | 所屬系統 | metro、rail |

---

## 2. SERVES

代表某條路線服務某個車站。

| Relationship | 起點   | 終點      | 說明     |
| ------------ | ---- | ------- | ------ |
| SERVES       | Line | Station | 路線經過車站 |

---

## 3. PART_OF

代表路線屬於某交通系統。

| Relationship | 起點   | 終點      | 說明       |
| ------------ | ---- | ------- | -------- |
| PART_OF      | Line | Network | 路線屬於交通系統 |

---

## 4. INTERCHANGES_WITH

代表 Metro 與 National Rail 可轉乘。

| Relationship      | 起點      | 終點      | 說明      |
| ----------------- | ------- | ------- | ------- |
| INTERCHANGES_WITH | Station | Station | 捷運與國鐵轉乘 |

### Properties

| Property      | 說明   | 範例               |
| ------------- | ---- | ---------------- |
| transfer_type | 轉乘類型 | metro_rail       |
| transfer_note | 轉乘說明 | Central transfer |

---

# 三、Cypher 實作架構雛形參考

## 1. 建立 Network Nodes

```cypher
CREATE (:Network {
  name: "Metro",
  type: "metro"
});

CREATE (:Network {
  name: "National Rail",
  type: "rail"
});
```

---

## 2. 建立 Line Nodes

```cypher
CREATE (:Line {
  line_id: "M1",
  name: "Metro Line 1",
  network: "metro"
});

CREATE (:Line {
  line_id: "M2",
  name: "Metro Line 2",
  network: "metro"
});

CREATE (:Line {
  line_id: "M3",
  name: "Metro Line 3",
  network: "metro"
});

CREATE (:Line {
  line_id: "M4",
  name: "Metro Line 4",
  network: "metro"
});

CREATE (:Line {
  line_id: "NR1",
  name: "National Rail Line 1",
  network: "rail"
});

CREATE (:Line {
  line_id: "NR2",
  name: "National Rail Line 2",
  network: "rail"
});
```

---

## 3. 建立 Station Nodes 範例

```cypher
CREATE (:Station {
  station_id: "MS01",
  name: "Central Square",
  network: "metro",
  lines: ["M1", "M2"],
  is_interchange_metro: true,
  is_interchange_national_rail: true
});

CREATE (:Station {
  station_id: "NR01",
  name: "Central Station",
  network: "rail",
  lines: ["NR1", "NR2"],
  is_interchange_metro: true,
  is_interchange_national_rail: true
});
```

---

## 4. 建立 PART_OF Relationships

```cypher
MATCH (l:Line {line_id: "M1"}), (n:Network {type: "metro"})
CREATE (l)-[:PART_OF]->(n);

MATCH (l:Line {line_id: "NR1"}), (n:Network {type: "rail"})
CREATE (l)-[:PART_OF]->(n);
```

---

## 5. 建立 SERVES Relationships

```cypher
MATCH (l:Line {line_id: "M1"}), (s:Station {station_id: "MS01"})
CREATE (l)-[:SERVES]->(s);

MATCH (l:Line {line_id: "M1"}), (s:Station {station_id: "MS02"})
CREATE (l)-[:SERVES]->(s);

MATCH (l:Line {line_id: "NR1"}), (s:Station {station_id: "NR01"})
CREATE (l)-[:SERVES]->(s);

MATCH (l:Line {line_id: "NR1"}), (s:Station {station_id: "NR02"})
CREATE (l)-[:SERVES]->(s);
```

---

## 6. 建立 CONNECTS_TO Relationships

```cypher
MATCH (a:Station {station_id: "MS01"}), (b:Station {station_id: "MS02"})
CREATE (a)-[:CONNECTS_TO {
  line: "M1",
  travel_time_min: 3,
  network: "metro"
}]->(b);

MATCH (a:Station {station_id: "MS02"}), (b:Station {station_id: "MS03"})
CREATE (a)-[:CONNECTS_TO {
  line: "M1",
  travel_time_min: 2,
  network: "metro"
}]->(b);

MATCH (a:Station {station_id: "NR01"}), (b:Station {station_id: "NR02"})
CREATE (a)-[:CONNECTS_TO {
  line: "NR1",
  travel_time_min: 12,
  network: "rail"
}]->(b);

MATCH (a:Station {station_id: "NR01"}), (b:Station {station_id: "NR06"})
CREATE (a)-[:CONNECTS_TO {
  line: "NR2",
  travel_time_min: 14,
  network: "rail"
}]->(b);
```

---

## 7. 建立 INTERCHANGES_WITH Relationships

```cypher
MATCH (m:Station {station_id: "MS01"}), (r:Station {station_id: "NR01"})
CREATE (m)-[:INTERCHANGES_WITH {
  transfer_type: "metro_rail",
  transfer_note: "Central transfer"
}]->(r);

MATCH (m:Station {station_id: "MS07"}), (r:Station {station_id: "NR03"})
CREATE (m)-[:INTERCHANGES_WITH {
  transfer_type: "metro_rail",
  transfer_note: "Old Town transfer"
}]->(r);

MATCH (m:Station {station_id: "MS15"}), (r:Station {station_id: "NR07"})
CREATE (m)-[:INTERCHANGES_WITH {
  transfer_type: "metro_rail",
  transfer_note: "Ferndale transfer"
}]->(r);
```

---

# 四、最終架構總表

| 類型           | 名稱                |
| ------------ | ----------------- |
| Node         | Station           |
| Node         | Line              |
| Node         | Network           |
| Relationship | CONNECTS_TO       |
| Relationship | SERVES            |
| Relationship | PART_OF           |
| Relationship | INTERCHANGES_WITH |
