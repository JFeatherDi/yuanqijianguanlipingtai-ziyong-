"""SQLite 访问层。

设计要点：
- WAL 模式：读不阻塞写、写不阻塞读，显著提升多人并发体验
- busy_timeout：写锁自动排队，避免直接抛 "database is locked"
- 连接按请求复用（存于 flask.g），请求结束自动归还
"""
from __future__ import annotations

import sqlite3

from flask import g

from .config import Config

SCHEMA = """
CREATE TABLE IF NOT EXISTS components (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    asset_no    TEXT NOT NULL DEFAULT '',
    image_data  TEXT NOT NULL DEFAULT '',
    category    TEXT,
    spec        TEXT,
    unit        TEXT,
    location    TEXT,
    owner       TEXT,
    maintenance INTEGER NOT NULL DEFAULT 0,
    unavailable INTEGER NOT NULL DEFAULT 0,
    maintenance_qty REAL NOT NULL DEFAULT 0,
    unavailable_qty REAL NOT NULL DEFAULT 0,
    stock       REAL NOT NULL DEFAULT 0,
    threshold   REAL DEFAULT 0,
    remark      TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id INTEGER NOT NULL,
    delta        REAL NOT NULL,
    type         TEXT NOT NULL,
    operator     TEXT,
    remark       TEXT,
    applicant    TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL,
    FOREIGN KEY(component_id) REFERENCES components(id)
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    full_name     TEXT NOT NULL DEFAULT '',
    phone         TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    user_type     TEXT NOT NULL DEFAULT 'student',
    mentor        TEXT NOT NULL DEFAULT '',
    role          TEXT NOT NULL DEFAULT 'member',
    pw_version    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS custody_positions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id INTEGER NOT NULL,
    root_id      INTEGER NOT NULL,
    parent_id    INTEGER,
    holder       TEXT NOT NULL,
    contact      TEXT NOT NULL DEFAULT '',
    qty          REAL NOT NULL,
    operator     TEXT NOT NULL DEFAULT '',
    remark       TEXT,
    due_date     TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS custody_returns (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id  INTEGER NOT NULL,
    root_id      INTEGER NOT NULL,
    component_id INTEGER NOT NULL,
    qty          REAL NOT NULL,
    operator     TEXT NOT NULL DEFAULT '',
    remark       TEXT,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_comp_name     ON components(name);
CREATE INDEX IF NOT EXISTS idx_comp_category ON components(category);
CREATE INDEX IF NOT EXISTS idx_txn_comp      ON transactions(component_id);
CREATE INDEX IF NOT EXISTS idx_txn_created   ON transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_txn_type      ON transactions(type);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_custody_pos_root ON custody_positions(root_id);
CREATE INDEX IF NOT EXISTS idx_custody_pos_component ON custody_positions(component_id);
CREATE INDEX IF NOT EXISTS idx_custody_ret_root ON custody_returns(root_id);
CREATE TABLE IF NOT EXISTS system_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _remove_grouped_component_constraint(conn):
    """旧表以「名称 + 型号」聚合库存；独立设备允许同名同型号重复。"""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'components'"
    ).fetchone()
    table_sql = (row["sql"] or "").replace(" ", "").lower() if row else ""
    if "unique(name,spec)" not in table_sql:
        return

    conn.execute("PRAGMA legacy_alter_table = ON")
    conn.execute("ALTER TABLE components RENAME TO components_grouped")
    conn.execute(
        """CREATE TABLE components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            asset_no TEXT NOT NULL DEFAULT '',
            image_data TEXT NOT NULL DEFAULT '',
            category TEXT,
            spec TEXT,
            unit TEXT,
            location TEXT,
            owner TEXT,
            maintenance INTEGER NOT NULL DEFAULT 0,
            unavailable INTEGER NOT NULL DEFAULT 0,
            maintenance_qty REAL NOT NULL DEFAULT 0,
            unavailable_qty REAL NOT NULL DEFAULT 0,
            stock REAL NOT NULL DEFAULT 0,
            threshold REAL DEFAULT 0,
            remark TEXT
        )"""
    )
    conn.execute(
        """INSERT INTO components
           (id, name, asset_no, image_data, category, spec, unit, location, owner,
            maintenance, unavailable, maintenance_qty, unavailable_qty, stock, threshold, remark)
           SELECT id, name, asset_no, image_data, category, spec, unit, location, owner,
                  maintenance, unavailable, maintenance_qty, unavailable_qty, stock, threshold, remark
             FROM components_grouped"""
    )
    conn.execute("DROP TABLE components_grouped")
    conn.execute("PRAGMA legacy_alter_table = OFF")


def _clone_asset_no(conn, base, sequence):
    if not base:
        return ""
    suffix = sequence
    while True:
        candidate = f"{base}-{suffix:02d}"
        exists = conn.execute(
            "SELECT 1 FROM components WHERE asset_no = ?", (candidate,)
        ).fetchone()
        if not exists:
            return candidate
        suffix += 1


def _individualize_components(conn):
    """把旧版数量池拆成一台一行，并保留当前借用人。"""
    marker = conn.execute(
        "SELECT value FROM system_meta WHERE key = 'individual_devices_v1'"
    ).fetchone()
    if marker:
        return

    rows = conn.execute(
        """SELECT c.*,
          (SELECT IFNULL(SUM(p.qty), 0) FROM custody_positions p
            WHERE p.component_id = c.id AND ROUND(p.qty, 6) > 0) AS borrowed_qty
          FROM components c ORDER BY c.id"""
    ).fetchall()
    columns = (
        "name", "image_data", "category", "spec", "unit", "location", "owner",
        "threshold", "remark",
    )

    for source in rows:
        available = max(int(round(float(source["stock"] or 0))), 0)
        maintenance = max(int(round(float(source["maintenance_qty"] or 0))), 0)
        unavailable = max(int(round(float(source["unavailable_qty"] or 0))), 0)
        positions = conn.execute(
            "SELECT * FROM custody_positions WHERE component_id = ? AND ROUND(qty, 6) > 0 ORDER BY id",
            (source["id"],),
        ).fetchall()
        borrowed = []
        for position in positions:
            borrowed.extend([position] * max(int(round(float(position["qty"] or 0))), 1))

        states = [("borrowed", position) for position in borrowed]
        states += [("available", None)] * available
        states += [("maintenance", None)] * maintenance
        states += [("unavailable", None)] * unavailable
        if not states:
            states = [("unavailable", None)]

        unit_ids = [source["id"]]
        for sequence in range(2, len(states) + 1):
            asset_no = _clone_asset_no(conn, source["asset_no"], sequence)
            values = [source[key] for key in columns]
            cursor = conn.execute(
                """INSERT INTO components
                   (name, asset_no, image_data, category, spec, unit, location, owner,
                    maintenance, unavailable, maintenance_qty, unavailable_qty, stock, threshold, remark)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, ?, ?)""",
                (values[0], asset_no, *values[1:]),
            )
            unit_ids.append(cursor.lastrowid)

        position_uses = {}
        for unit_id, (state, position) in zip(unit_ids, states):
            stock = 1 if state == "available" else 0
            maintenance_flag = 1 if state == "maintenance" else 0
            unavailable_flag = 1 if state == "unavailable" else 0
            conn.execute(
                """UPDATE components SET stock = ?, maintenance = ?, unavailable = ?,
                   maintenance_qty = ?, unavailable_qty = ?, threshold = 0 WHERE id = ?""",
                (stock, maintenance_flag, unavailable_flag, maintenance_flag, unavailable_flag, unit_id),
            )
            if state != "borrowed":
                continue
            used = position_uses.get(position["id"], 0)
            position_uses[position["id"]] = used + 1
            if used == 0:
                conn.execute(
                    "UPDATE custody_positions SET component_id = ?, qty = 1 WHERE id = ?",
                    (unit_id, position["id"]),
                )
            else:
                cursor = conn.execute(
                    """INSERT INTO custody_positions
                       (component_id, root_id, parent_id, holder, contact, qty, operator, remark, due_date, created_at)
                       VALUES (?, 0, NULL, ?, ?, 1, ?, ?, ?, ?)""",
                    (
                        unit_id, position["holder"], position["contact"], position["operator"],
                        position["remark"], position["due_date"], position["created_at"],
                    ),
                )
                conn.execute(
                    "UPDATE custody_positions SET root_id = ? WHERE id = ?",
                    (cursor.lastrowid, cursor.lastrowid),
                )

    conn.execute(
        "INSERT INTO system_meta(key, value) VALUES ('individual_devices_v1', '1')"
    )


def connect(path=None):
    """建立一条已配置好 PRAGMA 的连接。"""
    conn = sqlite3.connect(
        path or Config.DB_PATH,
        timeout=Config.DB_BUSY_TIMEOUT_MS / 1000,
    )
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {Config.DB_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def get_db():
    """取当前请求的数据库连接。"""
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    """建表 + 建索引 + 旧库补列，幂等。

    旧数据库（早于申请人字段）通过 PRAGMA 检测后自动 ALTER TABLE，
    历史流水的申请人保持为空字符串，前端显示为「—」。
    """
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        _remove_grouped_component_constraint(conn)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(transactions)")}
        if "applicant" not in columns:
            conn.execute(
                "ALTER TABLE transactions ADD COLUMN applicant TEXT NOT NULL DEFAULT ''"
            )
        component_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(components)")
        }
        if "owner" not in component_columns:
            conn.execute("ALTER TABLE components ADD COLUMN owner TEXT")
        if "maintenance" not in component_columns:
            conn.execute(
                "ALTER TABLE components ADD COLUMN maintenance INTEGER NOT NULL DEFAULT 0"
            )
        if "asset_no" not in component_columns:
            conn.execute("ALTER TABLE components ADD COLUMN asset_no TEXT NOT NULL DEFAULT ''")
        if "image_data" not in component_columns:
            conn.execute("ALTER TABLE components ADD COLUMN image_data TEXT NOT NULL DEFAULT ''")
        if "unavailable" not in component_columns:
            conn.execute(
                "ALTER TABLE components ADD COLUMN unavailable INTEGER NOT NULL DEFAULT 0"
            )
        # 旧版把维护/不可借保存为整条设备记录的布尔状态。首次补数量列时，
        # 将当时的可用库存整体迁入对应状态数量，保证总数不变。
        added_maintenance_qty = "maintenance_qty" not in component_columns
        added_unavailable_qty = "unavailable_qty" not in component_columns
        if added_maintenance_qty:
            conn.execute(
                "ALTER TABLE components ADD COLUMN maintenance_qty REAL NOT NULL DEFAULT 0"
            )
        if added_unavailable_qty:
            conn.execute(
                "ALTER TABLE components ADD COLUMN unavailable_qty REAL NOT NULL DEFAULT 0"
            )
        if added_maintenance_qty:
            conn.execute(
                "UPDATE components SET maintenance_qty = stock, stock = 0 "
                "WHERE maintenance = 1 AND stock > 0"
            )
        if added_unavailable_qty:
            conn.execute(
                "UPDATE components SET unavailable_qty = stock, stock = 0 "
                "WHERE unavailable = 1 AND stock > 0"
            )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_components_asset_no "
            "ON components(asset_no) WHERE asset_no <> ''"
        )
        user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "full_name" not in user_columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN full_name TEXT NOT NULL DEFAULT ''"
            )
        if "phone" not in user_columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN phone TEXT NOT NULL DEFAULT ''"
            )
        if "role" not in user_columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'member'"
            )
        if "user_type" not in user_columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN user_type TEXT NOT NULL DEFAULT 'student'"
            )
        if "mentor" not in user_columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN mentor TEXT NOT NULL DEFAULT ''"
            )
        conn.execute(
            "UPDATE users SET phone = username "
            "WHERE user_type = 'teacher' AND phone = ''"
        )
        pos_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(custody_positions)")
        }
        if "due_date" not in pos_columns:
            # 旧库补「预计归还日期」：历史持有点为空 = 未约定，不影响既有数据
            conn.execute("ALTER TABLE custody_positions ADD COLUMN due_date TEXT")
        if "contact" not in pos_columns:
            conn.execute(
                "ALTER TABLE custody_positions ADD COLUMN contact TEXT NOT NULL DEFAULT ''"
            )
        conn.executescript(
            """CREATE INDEX IF NOT EXISTS idx_comp_name ON components(name);
               CREATE INDEX IF NOT EXISTS idx_comp_category ON components(category);
               CREATE UNIQUE INDEX IF NOT EXISTS idx_components_asset_no
                 ON components(asset_no) WHERE asset_no <> '';"""
        )
        _individualize_components(conn)
        conn.commit()
    finally:
        conn.close()


def to_dict(row):
    return {key: row[key] for key in row.keys()} if row else None


def to_dicts(rows):
    return [to_dict(row) for row in rows]
