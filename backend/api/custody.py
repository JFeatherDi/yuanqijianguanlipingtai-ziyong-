"""器件流转接口：链条列表（服务端筛选 + 分页）、明细、转交、归还、持有点选择。

跨页搜索：q 在数据库层过滤后再分页（器件名、规格、链上所有历任持有人），
总数查询使用相同条件 —— 目标记录哪怕在未筛选列表的后续页，搜索也能直达。
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..db import get_db
from ..security import current_user, manager_required, superadmin_required
from ..services import custody
from ..services.custody import CustodyError
from ..services.inventory import now_str

bp = Blueprint("custody", __name__, url_prefix="/api/custody")

PAGE_SIZE = 10

# 链条摘要：root 是每条链的根节点（首次出库），子查询聚合全链数据。
# 已全部归还的链也保留，记录页因此展示完整借还历史。
_CHAIN_SELECT = """
SELECT root.id, root.component_id, root.holder AS applicant, root.contact,
       root.qty AS initial_qty, root.operator, root.remark, root.created_at,
       c.name, c.asset_no, c.spec, c.unit,
       (SELECT IFNULL(ROUND(SUM(cp.qty), 6), 0) FROM custody_positions cp
         WHERE cp.root_id = root.id)                            AS holding_total,
       (SELECT IFNULL(ROUND(SUM(cr.qty), 6), 0) FROM custody_returns cr
         WHERE cr.root_id = root.id)                            AS returned_total,
       (SELECT MAX(cr.created_at) FROM custody_returns cr
         WHERE cr.root_id = root.id)                            AS last_return_at,
       (SELECT COUNT(*) FROM custody_positions cp
         WHERE cp.root_id = root.id AND cp.parent_id IS NOT NULL) AS transfer_count,
       (SELECT GROUP_CONCAT(DISTINCT cp.holder) FROM custody_positions cp
         WHERE cp.root_id = root.id)                            AS holders,
       (SELECT MAX(t.act) FROM (
            SELECT cp.created_at AS act FROM custody_positions cp WHERE cp.root_id = root.id
            UNION ALL
            SELECT cr.created_at AS act FROM custody_returns cr WHERE cr.root_id = root.id
       ) t)                                                    AS last_activity,
       (SELECT MIN(cp.due_date) FROM custody_positions cp
         WHERE cp.root_id = root.id AND cp.due_date IS NOT NULL
           AND ROUND(cp.qty, 6) > 0)                           AS due_date
FROM custody_positions root
LEFT JOIN components c ON c.id = root.component_id
WHERE root.parent_id IS NULL
"""

_CHAIN_ORDER = "ORDER BY last_activity DESC, root.id DESC"

# q 命中：器件名 / 规格 / 链上任一节点（含根）的持有人
_SEARCH_CLAUSE = """AND (c.name LIKE ? OR c.asset_no LIKE ? OR c.spec LIKE ? OR root.contact LIKE ?
       OR EXISTS (SELECT 1 FROM custody_positions cp2
                   WHERE cp2.root_id = root.id
                     AND (cp2.holder LIKE ? OR cp2.contact LIKE ?)))
"""

_COUNT_SQL = """
SELECT COUNT(*) AS total
FROM custody_positions root
LEFT JOIN components c ON c.id = root.component_id
WHERE root.parent_id IS NULL
"""

_RECORD_TYPE_CLAUSES = {
    "borrow": "AND NOT EXISTS (SELECT 1 FROM custody_returns cr WHERE cr.root_id = root.id)\n",
    "return": "AND EXISTS (SELECT 1 FROM custody_returns cr WHERE cr.root_id = root.id)\n",
}

_HOLDINGS_SQL = """
SELECT root_id, holder, ROUND(SUM(qty), 6) AS qty
FROM custody_positions
WHERE root_id IN (%s)
GROUP BY root_id, holder
HAVING ROUND(SUM(qty), 6) > 0
ORDER BY root_id, MIN(id)
"""


def _search_args(keyword):
    like = f"%{keyword}%"
    return [like, like, like, like, like, like]


@bp.errorhandler(CustodyError)
def on_custody_error(exc):
    return jsonify({"ok": False, "msg": str(exc)}), exc.status


def _decorate_chains(db, rows, include_events=False):
    """给一页链条附加当前持有人、逾期状态以及可选的完整事件明细。"""
    chains = [dict(row) for row in rows]
    ids = [chain["id"] for chain in chains]
    if ids:
        placeholders = ",".join("?" for _ in ids)
        holders = db.execute(_HOLDINGS_SQL % placeholders, ids).fetchall()
        by_chain = {}
        for row in holders:
            by_chain.setdefault(row["root_id"], []).append(
                {"holder": row["holder"], "qty": row["qty"]}
            )
        for chain in chains:
            chain["holdings"] = by_chain.get(chain["id"], [])
    else:
        for chain in chains:
            chain["holdings"] = []
    for chain in chains:
        # 链上最早的在外约定日期即最紧迫的那份承诺；逾期天数在后端算好
        chain["overdue_days"] = custody.overdue_days(chain.get("due_date"))
        if include_events:
            detail = custody.chain_events(db, chain["id"])
            chain["events"] = detail["events"] if detail else []
    return chains


@bp.route("", methods=["GET"])
@manager_required
def list_chains():
    keyword = (request.args.get("q") or "").strip()
    record_type = (request.args.get("record_type") or "").strip()
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    where = _RECORD_TYPE_CLAUSES.get(record_type, "")
    if keyword:
        where += _SEARCH_CLAUSE
    args = _search_args(keyword) if keyword else []

    db = get_db()
    total = db.execute(_COUNT_SQL + where, args).fetchone()["total"]
    pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    page = min(page, pages)

    rows = db.execute(
        _CHAIN_SELECT + where + _CHAIN_ORDER + " LIMIT ? OFFSET ?",
        [*args, PAGE_SIZE, (page - 1) * PAGE_SIZE],
    ).fetchall()

    return jsonify(
        {
            "ok": True,
            "data": _decorate_chains(db, rows, include_events=True),
            "total": total,
            "page": page,
            "pages": pages,
            "page_size": PAGE_SIZE,
        }
    )


@bp.route("/<int:root_id>/records", methods=["GET"])
@manager_required
def chain_records(root_id):
    db = get_db()
    root = db.execute(
        "SELECT 1 FROM custody_positions WHERE id = ? AND parent_id IS NULL", (root_id,)
    ).fetchone()
    if root is None:
        return jsonify({"ok": False, "msg": "流转记录不存在"}), 404

    summary = db.execute(_CHAIN_SELECT + "AND root.id = ?", [root_id]).fetchone()
    detail = custody.chain_events(db, root_id)
    return jsonify(
        {
            "ok": True,
            "summary": _decorate_chains(db, [summary])[0] if summary else None,
            **detail,
        }
    )


@bp.route("/bulk-delete", methods=["POST"])
@superadmin_required
def bulk_delete_chains():
    """删除已全部归还的借用链；未归还记录会阻止整批操作。"""
    payload = request.get_json(silent=True) or {}
    raw_ids = payload.get("ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        return jsonify({"ok": False, "msg": "请选择要删除的借还记录"}), 400
    if len(raw_ids) > 100:
        return jsonify({"ok": False, "msg": "单次最多删除 100 条借还记录"}), 400
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in raw_ids):
        return jsonify({"ok": False, "msg": "借还记录编号无效"}), 400

    root_ids = list(dict.fromkeys(raw_ids))
    placeholders = ",".join("?" for _ in root_ids)
    db = get_db()
    roots = db.execute(
        f"SELECT root.id, root.holder, c.name, c.asset_no "
        f"FROM custody_positions root "
        f"LEFT JOIN components c ON c.id = root.component_id "
        f"WHERE root.id IN ({placeholders}) AND root.parent_id IS NULL",
        root_ids,
    ).fetchall()
    if len(roots) != len(root_ids):
        return jsonify({"ok": False, "msg": "部分借还记录已不存在，请刷新后重试"}), 404

    active = db.execute(
        f"SELECT root.id, root.holder, c.name, c.asset_no "
        f"FROM custody_positions root "
        f"LEFT JOIN components c ON c.id = root.component_id "
        f"WHERE root.id IN ({placeholders}) AND root.parent_id IS NULL "
        "AND EXISTS (SELECT 1 FROM custody_positions cp "
        "            WHERE cp.root_id = root.id AND ROUND(cp.qty, 6) > 0) "
        "ORDER BY root.id",
        root_ids,
    ).fetchall()
    if active:
        labels = [row["asset_no"] or row["name"] or f"记录 #{row['id']}" for row in active[:3]]
        suffix = "等" if len(active) > 3 else ""
        return jsonify({
            "ok": False,
            "msg": f"{', '.join(labels)}{suffix}尚未全部归还，整批记录均未删除",
        }), 400

    try:
        db.execute(f"DELETE FROM custody_returns WHERE root_id IN ({placeholders})", root_ids)
        cursor = db.execute(f"DELETE FROM custody_positions WHERE root_id IN ({placeholders})", root_ids)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return jsonify({"ok": True, "deleted": len(root_ids), "deleted_rows": cursor.rowcount})


@bp.route("/positions", methods=["GET"])
@manager_required
def open_positions():
    """可操作的持有点（当前持有量 > 0），供转借 / 归还表单选择。"""
    component_id = request.args.get("component_id", type=int)
    keyword = (request.args.get("q") or "").strip()

    clauses, args = ["ROUND(cp.qty, 6) > 0"], []
    if component_id:
        clauses.append("cp.component_id = ?")
        args.append(component_id)
    if keyword:
        like = f"%{keyword}%"
        clauses.append("(c.name LIKE ? OR c.asset_no LIKE ? OR c.spec LIKE ? OR cp.holder LIKE ?)")
        args.extend([like, like, like, like])

    rows = get_db().execute(
        """
        SELECT cp.id, cp.component_id, cp.root_id, cp.parent_id, cp.holder, cp.contact,
               ROUND(cp.qty, 6) AS qty, cp.created_at, parent.holder AS handler,
               c.name, c.asset_no, c.spec, c.unit
        FROM custody_positions cp
        LEFT JOIN components c ON c.id = cp.component_id
        LEFT JOIN custody_positions parent ON parent.id = cp.parent_id
        WHERE """
        + " AND ".join(clauses)
        + """
        ORDER BY cp.id DESC
        """,
        args,
    ).fetchall()
    return jsonify({"ok": True, "data": [dict(row) for row in rows]})


@bp.route("/transfer", methods=["POST"])
@manager_required
def transfer():
    payload = request.get_json(silent=True) or {}
    qty = 1

    db = get_db()
    custody.transfer(
        db,
        payload.get("position_id"),
        payload.get("holder"),
        payload.get("contact"),
        qty,
        current_user(),
        payload.get("remark") or "",
        payload.get("due_date"),
    )
    db.commit()
    return jsonify({"ok": True, "msg": "转借已登记"})


@bp.route("/return", methods=["POST"])
@manager_required
def give_back():
    payload = request.get_json(silent=True) or {}
    qty = 1

    db = get_db()
    returned_at = now_str()
    stock = custody.give_back(
        db,
        payload.get("position_id"),
        qty,
        current_user(),
        payload.get("remark") or "",
        returned_at,
    )
    db.commit()
    return jsonify({
        "ok": True,
        "msg": "归还已登记",
        "stock": stock,
        "returned_at": returned_at,
    })
