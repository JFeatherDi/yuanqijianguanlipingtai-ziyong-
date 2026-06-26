"""实验室元器件管理平台 - 后端"""
import os
import io
import csv
import time
import sqlite3
import threading
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict

from flask import (
    Flask, request, session, jsonify, send_from_directory,
    Response, g
)
from openpyxl import load_workbook

# ---------- 配置 ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data.db")
STATIC_DIR = os.path.join(BASE_DIR, "static")

USERNAME = "IOTAT"
PASSWORD = "swust350351"
SECRET_KEY = "swust-lab-components-2026"

# 并发与安全参数
DB_BUSY_TIMEOUT_MS = 10000        # SQLite 写锁等待 10 秒
SESSION_LIFETIME_HOURS = 12       # session 12 小时过期
LOGIN_MAX_FAIL = 5                # 登录失败 5 次
LOGIN_LOCK_SECONDS = 300          # 锁定 5 分钟
MAX_WORKER_THREADS = 8            # 最大并发请求线程数

app = Flask(__name__, static_folder=None)
app.secret_key = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8MB 上传上限
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=SESSION_LIFETIME_HOURS)
app.config["SESSION_REFRESH_EACH_REQUEST"] = True    # 每次请求续期


# ---------- 登录限流 ----------
_login_fails = defaultdict(list)   # key -> [timestamp, ...]
_login_lock = threading.Lock()


def _login_key():
    return (request.remote_addr or "unknown")


def check_login_limit():
    """返回 (是否允许, 剩余锁定秒数)。"""
    now = time.time()
    key = _login_key()
    with _login_lock:
        fails = _login_fails[key]
        # 清理过期记录（超过锁定窗口）
        _login_fails[key] = [t for t in fails if now - t < LOGIN_LOCK_SECONDS]
        if len(_login_fails[key]) >= LOGIN_MAX_FAIL:
            oldest = _login_fails[key][0]
            remain = int(LOGIN_LOCK_SECONDS - (now - oldest))
            return False, max(remain, 0)
        return True, 0


def record_login_fail():
    with _login_lock:
        _login_fails[_login_key()].append(time.time())


def clear_login_fails():
    with _login_lock:
        _login_fails.pop(_login_key(), None)


# ---------- 数据库 ----------
def get_db():
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH, timeout=DB_BUSY_TIMEOUT_MS / 1000)
        conn.row_factory = sqlite3.Row
        # 开启 WAL：读不阻塞写，写不阻塞读，大幅提升并发
        conn.execute(f"PRAGMA busy_timeout = {DB_BUSY_TIMEOUT_MS}")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")  # WAL 下安全且更快
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.executescript("""
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
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        component_id INTEGER NOT NULL,
        delta       REAL NOT NULL,
        type        TEXT NOT NULL,
        operator    TEXT,
        remark      TEXT,
        created_at  TEXT NOT NULL,
        FOREIGN KEY(component_id) REFERENCES components(id)
    );
    CREATE INDEX IF NOT EXISTS idx_comp_name ON components(name);
    CREATE INDEX IF NOT EXISTS idx_txn_comp ON transactions(component_id);
    """)
    conn.commit()
    conn.close()


# ---------- 鉴权 ----------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return jsonify({"ok": False, "msg": "未登录或会话过期"}), 401
        return f(*args, **kwargs)
    return wrapper


# ---------- 工具 ----------
def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def row_to_dict(row):
    return {k: row[k] for k in row.keys()} if row else None


def apply_change(db, comp_id, delta, ttype, operator, remark=""):
    """累加库存 + 写流水。delta 负数=出库。用于入库/导入/初始。"""
    db.execute(
        "UPDATE components SET stock = stock + ? WHERE id = ?",
        (delta, comp_id),
    )
    log_transaction(db, comp_id, delta, ttype, operator, remark)


def log_transaction(db, comp_id, delta, ttype, operator, remark=""):
    """仅写流水，不动库存。用于已原子扣减的出库场景。"""
    db.execute(
        "INSERT INTO transactions (component_id, delta, type, operator, remark, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (comp_id, delta, ttype, operator, remark, now_str()),
    )


# ---------- 页面 ----------
@app.route("/")
def index():
    if not session.get("user"):
        return send_from_directory(STATIC_DIR, "login.html")
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/login", methods=["POST"])
def login():
    allowed, remain = check_login_limit()
    if not allowed:
        return jsonify({"ok": False, "msg": f"登录失败次数过多，请 {remain} 秒后再试"}), 429
    data = request.get_json(silent=True) or {}
    u = (data.get("username") or "").strip()
    p = (data.get("password") or "").strip()
    if u == USERNAME and p == PASSWORD:
        clear_login_fails()
        session.permanent = True
        session["user"] = u
        session["login_at"] = time.time()
        return jsonify({"ok": True, "user": u})
    record_login_fail()
    return jsonify({"ok": False, "msg": "账号或密码错误"}), 401


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/me")
@login_required
def me():
    return jsonify({"ok": True, "user": session.get("user")})


# ---------- 元器件 CRUD ----------
@app.route("/api/components")
@login_required
def list_components():
    db = get_db()
    keyword = (request.args.get("q") or "").strip()
    sql = "SELECT * FROM components"
    args = []
    if keyword:
        sql += " WHERE name LIKE ? OR category LIKE ? OR spec LIKE ? OR location LIKE ?"
        like = f"%{keyword}%"
        args = [like, like, like, like]
    sql += " ORDER BY category, name"
    rows = db.execute(sql, args).fetchall()
    return jsonify({"ok": True, "data": [row_to_dict(r) for r in rows]})


@app.route("/api/components", methods=["POST"])
@login_required
def add_component():
    db = get_db()
    d = request.get_json(silent=True) or {}
    init_stock = float(d.get("stock") or 0)
    try:
        cur = db.execute(
            "INSERT INTO components (name, category, spec, unit, location, stock, threshold, remark) "
            "VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
            (
                d.get("name", "").strip(),
                d.get("category", "").strip(),
                d.get("spec", "").strip(),
                d.get("unit", "").strip() or "个",
                d.get("location", "").strip(),
                float(d.get("threshold") or 0),
                d.get("remark", "").strip(),
            ),
        )
        comp_id = cur.lastrowid
        if init_stock != 0:
            apply_change(db, comp_id, init_stock, "init",
                         session.get("user"), "新建初始库存")
        db.commit()
        return jsonify({"ok": True, "id": comp_id})
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "msg": "器件名称+规格已存在"}), 400
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 400


@app.route("/api/components/<int:cid>", methods=["PUT"])
@login_required
def update_component(cid):
    db = get_db()
    d = request.get_json(silent=True) or {}
    fields = ("name", "category", "spec", "unit", "location", "threshold", "remark")
    sets = []
    args = []
    for f in fields:
        if f in d:
            sets.append(f"{f} = ?")
            args.append(d[f])
    if sets:
        args.append(cid)
        db.execute(f"UPDATE components SET {', '.join(sets)} WHERE id = ?", args)
        db.commit()
    return jsonify({"ok": True})


@app.route("/api/components/<int:cid>", methods=["DELETE"])
@login_required
def delete_component(cid):
    db = get_db()
    db.execute("DELETE FROM transactions WHERE component_id = ?", (cid,))
    db.execute("DELETE FROM components WHERE id = ?", (cid,))
    db.commit()
    return jsonify({"ok": True})


# ---------- 入库 / 出库 ----------
@app.route("/api/stock/in", methods=["POST"])
@login_required
def stock_in():
    db = get_db()
    d = request.get_json(silent=True) or {}
    cid = d.get("id")
    try:
        qty = float(d.get("qty") or 0)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "msg": "数量格式错误"}), 400
    if qty <= 0:
        return jsonify({"ok": False, "msg": "数量必须大于 0"}), 400
    comp = db.execute("SELECT stock FROM components WHERE id = ?", (cid,)).fetchone()
    if not comp:
        return jsonify({"ok": False, "msg": "器件不存在"}), 404
    apply_change(db, cid, qty, "in", session.get("user"), d.get("remark", ""))
    db.commit()
    return jsonify({"ok": True, "stock": comp["stock"] + qty})


@app.route("/api/stock/out", methods=["POST"])
@login_required
def stock_out():
    db = get_db()
    d = request.get_json(silent=True) or {}
    cid = d.get("id")
    try:
        qty = float(d.get("qty") or 0)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "msg": "数量格式错误"}), 400
    if qty <= 0:
        return jsonify({"ok": False, "msg": "数量必须大于 0"}), 400

    # 原子扣减：WHERE stock >= ? 保证不会扣成负数
    # rowcount=1 成功，=0 表示库存不足或器件不存在
    cur = db.execute(
        "UPDATE components SET stock = stock - ? WHERE id = ? AND stock >= ?",
        (qty, cid, qty),
    )
    if cur.rowcount == 0:
        db.rollback()
        comp = db.execute("SELECT stock FROM components WHERE id = ?", (cid,)).fetchone()
        if not comp:
            return jsonify({"ok": False, "msg": "器件不存在"}), 404
        return jsonify({"ok": False, "msg": f"库存不足，当前 {comp['stock']}"}), 400
    # 原子 UPDATE 已扣减库存，这里只写流水
    log_transaction(db, cid, -qty, "out", session.get("user"), d.get("remark", ""))
    db.commit()
    new_stock = db.execute("SELECT stock FROM components WHERE id = ?", (cid,)).fetchone()["stock"]
    return jsonify({"ok": True, "stock": new_stock})


# ---------- 导入 ----------
@app.route("/api/import", methods=["POST"])
@login_required
def import_file():
    if "file" not in request.files:
        return jsonify({"ok": False, "msg": "未上传文件"}), 400
    f = request.files["file"]
    filename = (f.filename or "").lower()

    try:
        # ---- 阶段 1：解析文件，不持数据库连接 ----
        raw = f.read()
        if filename.endswith(".csv"):
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("gbk", errors="replace")
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
        elif filename.endswith((".xlsx", ".xlsm")):
            wb = load_workbook(filename=io.BytesIO(raw), read_only=True, data_only=True)
            ws = wb.active
            rows = [[c.value for c in r] for r in ws.iter_rows()]
            wb.close()
        else:
            return jsonify({"ok": False, "msg": "仅支持 .csv / .xlsx"}), 400

        if not rows:
            return jsonify({"ok": False, "msg": "文件为空"}), 400

        # 识别表头；找不到则默认第一列为 name
        header = [str(x).strip().lower() if x is not None else "" for x in rows[0]]
        col_map = {}
        for idx, h in enumerate(header):
            if h in ("name", "名称", "器件", "器件名称"):
                col_map["name"] = idx
            elif h in ("category", "分类", "类别"):
                col_map["category"] = idx
            elif h in ("spec", "规格", "型号"):
                col_map["spec"] = idx
            elif h in ("unit", "单位"):
                col_map["unit"] = idx
            elif h in ("location", "位置", "存放位置"):
                col_map["location"] = idx
            elif h in ("stock", "数量", "库存", "当前数量"):
                col_map["stock"] = idx
            elif h in ("threshold", "阈值", "预警值"):
                col_map["threshold"] = idx
            elif h in ("remark", "备注"):
                col_map["remark"] = idx

        if "name" not in col_map:
            col_map["name"] = 0

        data_rows = rows[1:] if any(col_map.values()) else rows

        # 预处理成内存中的待写入列表
        to_write = []
        skip = 0
        for r in data_rows:
            if not r or all((v is None or str(v).strip() == "") for v in r):
                continue
            def pick(key, default=""):
                idx = col_map.get(key)
                if idx is None or idx >= len(r):
                    return default
                v = r[idx]
                return "" if v is None else str(v).strip()

            name = pick("name")
            if not name:
                skip += 1
                continue
            spec = pick("spec")
            stock_raw = pick("stock", "0")
            try:
                stock = float(stock_raw) if stock_raw else 0.0
            except ValueError:
                stock = 0.0
            try:
                threshold = float(pick("threshold", "0")) or 0.0
            except ValueError:
                threshold = 0.0
            to_write.append({
                "name": name, "category": pick("category"), "spec": spec,
                "unit": pick("unit", "个"), "location": pick("location"),
                "stock": stock, "threshold": threshold, "remark": pick("remark"),
            })

        # ---- 阶段 2：开短事务批量写入 ----
        db = get_db()
        operator = session.get("user")
        ok = 0
        try:
            for item in to_write:
                existing = db.execute(
                    "SELECT id FROM components WHERE name = ? AND IFNULL(spec,'') = IFNULL(?, '')",
                    (item["name"], item["spec"]),
                ).fetchone()
                if existing:
                    if item["stock"]:
                        apply_change(db, existing["id"], item["stock"],
                                     "import", operator, "导入累加")
                    ok += 1
                else:
                    cur = db.execute(
                        "INSERT INTO components (name, category, spec, unit, location, stock, threshold, remark) "
                        "VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
                        (item["name"], item["category"], item["spec"], item["unit"],
                         item["location"], item["threshold"], item["remark"]),
                    )
                    if item["stock"]:
                        apply_change(db, cur.lastrowid, item["stock"],
                                     "init", operator, "导入初始")
                    ok += 1
            db.commit()
        except Exception:
            db.rollback()
            raise
        return jsonify({"ok": True, "imported": ok, "skipped": skip})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"解析失败: {e}"}), 500


# ---------- 流水 ----------
@app.route("/api/transactions")
@login_required
def list_transactions():
    db = get_db()
    cid = request.args.get("cid")
    limit = min(int(request.args.get("limit", 100)), 500)
    if cid:
        rows = db.execute(
            "SELECT t.*, c.name, c.spec FROM transactions t "
            "JOIN components c ON c.id = t.component_id "
            "WHERE t.component_id = ? ORDER BY t.id DESC LIMIT ?",
            (cid, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT t.*, c.name, c.spec FROM transactions t "
            "JOIN components c ON c.id = t.component_id "
            "ORDER BY t.id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return jsonify({"ok": True, "data": [row_to_dict(r) for r in rows]})


# ---------- 导出 ----------
@app.route("/api/export")
@login_required
def export_csv():
    db = get_db()
    rows = db.execute(
        "SELECT name, category, spec, unit, location, stock, threshold, remark "
        "FROM components ORDER BY category, name"
    ).fetchall()
    out = io.StringIO()
    out.write("\ufeff")  # BOM for Excel
    w = csv.writer(out)
    w.writerow(["名称", "分类", "规格", "单位", "位置", "库存", "预警值", "备注"])
    for r in rows:
        w.writerow([r["name"], r["category"], r["spec"], r["unit"],
                    r["location"], r["stock"], r["threshold"], r["remark"]])
    return Response(
        out.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=components.csv"},
    )


# ---------- 模板下载 ----------
@app.route("/api/template")
@login_required
def template():
    csv_text = "名称,分类,规格,单位,位置,库存,预警值,备注\n电阻10K,电阻,10K 0805,个,柜A-1,100,20,示例\n"
    return Response(
        "\ufeff" + csv_text,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=template.csv"},
    )


def run_server():
    """启动生产级 WSGI 服务器（waitress），限制并发线程防止小服务器进程堆积。"""
    try:
        from waitress import serve
        serve(
            app,
            host="0.0.0.0",
            port=5000,
            threads=MAX_WORKER_THREADS,     # 最大并发线程数
            connection_limit=20,            # 最大连接数（含排队）
            channel_timeout=30,             # 单请求超时 30 秒
            recv_bytes=8 * 1024 * 1024,     # 8MB 上传上限
        )
    except ImportError:
        # 回退到 Flask dev server（仅开发/调试用）
        print("[WARN] 未安装 waitress，回退到 Flask dev server（不推荐生产使用）")
        print("[WARN] 请运行: pip install waitress")
        app.run(host="0.0.0.0", port=5000, threaded=True)


if __name__ == "__main__":
    init_db()
    run_server()