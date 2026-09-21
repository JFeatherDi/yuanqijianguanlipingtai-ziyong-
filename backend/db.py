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
    category    TEXT,
    spec        TEXT,
    unit        TEXT,
    location    TEXT,
    stock       REAL NOT NULL DEFAULT 0,
    threshold   REAL DEFAULT 0,
    remark      TEXT,
    UNIQUE(name, spec)
);

CREATE TABLE IF NOT EXISTS transactions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id INTEGER NOT NULL,
    delta        REAL NOT NULL,
    type         TEXT NOT NULL,
    operator     TEXT,
    remark       TEXT,
    created_at   TEXT NOT NULL,
    FOREIGN KEY(component_id) REFERENCES components(id)
);

CREATE INDEX IF NOT EXISTS idx_comp_name     ON components(name);
CREATE INDEX IF NOT EXISTS idx_comp_category ON components(category);
CREATE INDEX IF NOT EXISTS idx_txn_comp      ON transactions(component_id);
CREATE INDEX IF NOT EXISTS idx_txn_created   ON transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_txn_type      ON transactions(type);
"""


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
    """建表 + 建索引，幂等。"""
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def to_dict(row):
    return {key: row[key] for key in row.keys()} if row else None


def to_dicts(rows):
    return [to_dict(row) for row in rows]