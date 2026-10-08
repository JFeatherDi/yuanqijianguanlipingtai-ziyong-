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
    applicant    TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL,
    FOREIGN KEY(component_id) REFERENCES components(id)
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    pw_version    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS custody_positions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id INTEGER NOT NULL,
    root_id      INTEGER NOT NULL,
    parent_id    INTEGER,
    holder       TEXT NOT NULL,
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
    """建表 + 建索引 + 旧库补列，幂等。

    旧数据库（早于申请人字段）通过 PRAGMA 检测后自动 ALTER TABLE，
    历史流水的申请人保持为空字符串，前端显示为「—」。
    """
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(transactions)")}
        if "applicant" not in columns:
            conn.execute(
                "ALTER TABLE transactions ADD COLUMN applicant TEXT NOT NULL DEFAULT ''"
            )
        pos_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(custody_positions)")
        }
        if "due_date" not in pos_columns:
            # 旧库补「预计归还日期」：历史持有点为空 = 未约定，不影响既有数据
            conn.execute("ALTER TABLE custody_positions ADD COLUMN due_date TEXT")
        conn.commit()
    finally:
        conn.close()


def to_dict(row):
    return {key: row[key] for key in row.keys()} if row else None


def to_dicts(rows):
    return [to_dict(row) for row in rows]