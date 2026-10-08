"""器件流转接口：链条列表（服务端筛选 + 分页）、明细、转交、归还、持有点选择。

跨页搜索：q 在数据库层过滤后再分页（器件名、规格、链上所有历任持有人），
总数查询使用相同条件 —— 目标记录哪怕在未筛选列表的后续页，搜索也能直达。
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..db import get_db
from ..security import current_user, login_required
from ..services import custody
from ..services.custody import CustodyError
from ..services.quantity import positive_quantity

bp = Blueprint("custody", __name__, url_prefix="/api/custody")

PAGE_SIZE = 10

# 链条摘要：root 是每条链的根节点（首次出库），子查询聚合全链数据
_CHAIN_SELECT = """
SELECT root.id, root.component_id, root.holder AS applicant,
       root.qty AS initial_qty, root.operator, root.remark, root.created_at,
       c.name, c.spec, c.unit,
       (SELECT IFNULL(ROUND(SUM(cp.qty), 6), 0) FROM custody_positions cp
         WHERE cp.root_id = root.id)                            AS holding_total,
       (SELECT IFNULL(ROUND(SUM(cr.qty), 6), 0) FROM custody_returns cr
         WHERE cr.root_id = root.id)                            AS returned_total,
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
_SEARCH_CLAUSE = """AND (c.name LIKE ? OR c.spec LIKE ?
       OR EXISTS (SELECT 1 FROM custody_positions cp2
                   WHERE cp2.root_id = root.id AND cp2.holder LIKE ?))
"""

# overdue=1：只看还有在外持有量且约定日期已过的链（快到期的不算逾期）
_OVERDUE_CLAUSE = """AND EXISTS (SELECT 1 FROM custody_positions cp4
                   WHERE cp4.root_id = root.id AND cp4.due_date IS NOT NULL
                     AND cp4.due_date < ? AND ROUND(cp4.qty, 6) > 0)
"""

_COUNT_SQL = """
SELECT COUNT(*) AS total
FROM custody_positions root
LEFT JOIN components c ON c.id = root.component_id
WHERE root.parent_id IS NULL
"""

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
    return [like, like, like]


@bp.errorhandler(CustodyError)
def on_custody_error(exc):
    return jsonify({"ok": False, "msg": str(exc)}), exc.status


def _decorate_chains(db, rows):
    """给一页链条附加「当前各人持有数量」与「逾期天数」。"""
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
    return chains


@bp.route("", methods=["GET"])
@login_required
def list_chains():
    keyword = (request.args.get("q") or "").strip()
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    only_overdue = request.args.get("overdue") in ("1", "true")

    where = _SEARCH_CLAUSE if keyword else ""
    args = _search_args(keyword) if keyword else []
    if only_overdue:
        from datetime import date

        where += _OVERDUE_CLAUSE
        args.append(date.today().isoformat())

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
            "data": _decorate_chains(db, rows),
            "total": total,
            "page": page,
            "pages": pages,
            "page_size": PAGE_SIZE,
        }
    )


@bp.route("/<int:root_id>/records", methods=["GET"])
@login_required
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


@bp.route("/positions", methods=["GET"])
@login_required
def open_positions():
    """可操作的持有点（当前持有量 > 0），供转交 / 归还表单选择。"""
    component_id = request.args.get("component_id", type=int)
    keyword = (request.args.get("q") or "").strip()

    clauses, args = ["ROUND(cp.qty, 6) > 0"], []
    if component_id:
        clauses.append("cp.component_id = ?")
        args.append(component_id)
    if keyword:
        like = f"%{keyword}%"
        clauses.append("(c.name LIKE ? OR c.spec LIKE ? OR cp.holder LIKE ?)")
        args.extend([like, like, like])

    rows = get_db().execute(
        """
        SELECT cp.id, cp.component_id, cp.root_id, cp.holder, ROUND(cp.qty, 6) AS qty,
               c.name, c.spec, c.unit
        FROM custody_positions cp
        LEFT JOIN components c ON c.id = cp.component_id
        WHERE """
        + " AND ".join(clauses)
        + """
        ORDER BY c.name, cp.id
        LIMIT 100
        """,
        args,
    ).fetchall()
    return jsonify({"ok": True, "data": [dict(row) for row in rows]})


@bp.route("/transfer", methods=["POST"])
@login_required
def transfer():
    payload = request.get_json(silent=True) or {}
    try:
        qty = positive_quantity(payload.get("qty"), "转交数量")
    except ValueError as exc:
        return jsonify({"ok": False, "msg": str(exc)}), 400

    db = get_db()
    custody.transfer(
        db,
        payload.get("position_id"),
        payload.get("holder"),
        qty,
        current_user(),
        payload.get("remark") or "",
        payload.get("due_date"),
    )
    db.commit()
    return jsonify({"ok": True, "msg": "转交已登记"})


@bp.route("/return", methods=["POST"])
@login_required
def give_back():
    payload = request.get_json(silent=True) or {}
    try:
        qty = positive_quantity(payload.get("qty"), "归还数量")
    except ValueError as exc:
        return jsonify({"ok": False, "msg": str(exc)}), 400

    db = get_db()
    stock = custody.give_back(
        db,
        payload.get("position_id"),
        qty,
        current_user(),
        payload.get("remark") or "",
    )
    db.commit()
    return jsonify({"ok": True, "msg": "归还已登记", "stock": stock})
