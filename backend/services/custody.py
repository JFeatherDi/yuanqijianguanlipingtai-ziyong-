"""器件流转：领用链、部分转交、分支路径与归还。

数据模型：
- 每笔新出库在 custody_positions 建一个根节点（parent_id 为空），
  申请人是初始持有人，root_id 指向链的根节点 id；
- 转交在原节点下挂子节点并扣减原节点持有量，支持部分转交；
  同一节点多次部分转交会形成分支，各分支沿 parent_id 保留完整路径；
- 归还写入 custody_returns，同时增加仓库库存并写一条 return 类型流水。

所有数量的加减与比较都走 SQLite ROUND(..., 6)，配合
services/quantity.py 的入口校验，避免二进制浮点残量（0.3-0.1 问题）。
"""
from __future__ import annotations

from .inventory import TX_RETURN, apply_change, now_str
from .quantity import positive_quantity


class CustodyError(Exception):
    """可预期错误，message 可直接返回给前端，status 为 HTTP 状态码。"""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


HOLDER_MAX = 120


def _check_holder(holder) -> str:
    holder = (holder or "").strip()
    if not holder:
        raise CustodyError("持有人不能为空")
    if len(holder) > HOLDER_MAX:
        raise CustodyError(f"持有人不能超过 {HOLDER_MAX} 个字符")
    return holder


def normalize_due_date(value):
    """校验并规范化预计归还日期；空值返回 None。

    只接受 YYYY-MM-DD 且不得早于今天——约定归还日期没有写过去的道理
    （已经逾期是继承来的状态，不是新约定的内容）。非法输入抛 CustodyError。
    """
    from datetime import date

    raw = (value or "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        raise CustodyError("预计归还日期格式应为 YYYY-MM-DD")
    if parsed < date.today():
        raise CustodyError("预计归还日期不能早于今天")
    return parsed.isoformat()


def overdue_days(due_date, today=None):
    """已逾期天数：日期早于今天返回正整数，否则返回 None。"""
    if not due_date:
        return None
    from datetime import date

    try:
        delta = (date.today() - date.fromisoformat(str(due_date)[:10])).days
    except ValueError:
        return None
    return delta if delta > 0 else None


def create_chain(db, component_id, holder, qty, operator, remark="", due_date=None):
    """新出库形成独立领用链。qty 已由出库入口校验，这里直接落库。"""
    cursor = db.execute(
        "INSERT INTO custody_positions "
        "(component_id, root_id, parent_id, holder, qty, operator, remark, due_date, created_at) "
        "VALUES (?, 0, NULL, ?, ?, ?, ?, ?, ?)",
        (component_id, holder, qty, operator, remark or "", due_date, now_str()),
    )
    position_id = cursor.lastrowid
    db.execute(
        "UPDATE custody_positions SET root_id = ? WHERE id = ?", (position_id, position_id)
    )
    return position_id


def get_position(db, position_id):
    return db.execute(
        "SELECT * FROM custody_positions WHERE id = ?", (position_id,)
    ).fetchone()


def transfer(db, position_id, holder, qty, operator, remark="", due_date=None):
    """从某个持有节点转交给新持有人。数量非法或超量时抛 CustodyError。

    due_date 缺省时继承原持有点的约定日期（器件在谁手里，约定跟到谁）；
    显式传入新日期则覆盖。原节点已全部转出仍保留在链上作为路径记录。
    原子性：持有量扣减的 WHERE 带上 ROUND 比较，并发下不会扣成负数。
    """
    holder = _check_holder(holder)
    qty = positive_quantity(qty, "转交数量")

    position = get_position(db, position_id)
    if position is None:
        raise CustodyError("持有记录不存在", 404)
    effective_due = normalize_due_date(due_date) if due_date else position["due_date"]

    cursor = db.execute(
        "UPDATE custody_positions SET qty = ROUND(qty - ?, 6) "
        "WHERE id = ? AND ROUND(qty, 6) >= ROUND(?, 6)",
        (qty, position_id, qty),
    )
    if cursor.rowcount != 1:
        remaining = db.execute(
            "SELECT ROUND(qty, 6) AS qty FROM custody_positions WHERE id = ?",
            (position_id,),
        ).fetchone()
        raise CustodyError(
            f"转交数量超过当前持有量 {remaining['qty'] if remaining else 0}"
        )

    cursor = db.execute(
        "INSERT INTO custody_positions "
        "(component_id, root_id, parent_id, holder, qty, operator, remark, due_date, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            position["component_id"],
            position["root_id"],
            position_id,
            holder,
            qty,
            operator,
            remark or "",
            effective_due,
            now_str(),
        ),
    )
    return {"position_id": cursor.lastrowid, "root_id": position["root_id"], "qty": qty}


def give_back(db, position_id, qty, operator, remark=""):
    """从某个持有节点归还到仓库。返回更新后的库存。"""
    qty = positive_quantity(qty, "归还数量")

    position = get_position(db, position_id)
    if position is None:
        raise CustodyError("持有记录不存在", 404)

    cursor = db.execute(
        "UPDATE custody_positions SET qty = ROUND(qty - ?, 6) "
        "WHERE id = ? AND ROUND(qty, 6) >= ROUND(?, 6)",
        (qty, position_id, qty),
    )
    if cursor.rowcount != 1:
        remaining = db.execute(
            "SELECT ROUND(qty, 6) AS qty FROM custody_positions WHERE id = ?",
            (position_id,),
        ).fetchone()
        raise CustodyError(
            f"归还数量超过当前持有量 {remaining['qty'] if remaining else 0}"
        )

    db.execute(
        "INSERT INTO custody_returns "
        "(position_id, root_id, component_id, qty, operator, remark, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            position_id,
            position["root_id"],
            position["component_id"],
            qty,
            operator,
            remark or "",
            now_str(),
        ),
    )
    # 归还增加仓库库存，并写一条 return 类型流水，账实同步
    return apply_change(db, position["component_id"], qty, TX_RETURN, operator, remark or "流转归还")


def open_positions(db, component_id=None, keyword=""):
    """列出仍在外的持有节点（持有量 > 0），供转交 / 归还表单选择。"""
    clauses, args = ["ROUND(cp.qty, 6) > 0"]
    if component_id:
        clauses.append("cp.component_id = ?")
        args.append(component_id)
    keyword = (keyword or "").strip()
    if keyword:
        like = f"%{keyword}%"
        clauses.append("(c.name LIKE ? OR c.spec LIKE ? OR cp.holder LIKE ?)")
        args.extend([like] * 3)
    args.insert(0, " AND ".join(clauses))
    return db.execute(
        "SELECT cp.id, cp.component_id, cp.root_id, cp.holder, ROUND(cp.qty, 6) AS qty, "
        "       cp.due_date, cp.created_at, c.name, c.spec, c.unit "
        "FROM custody_positions cp "
        "LEFT JOIN components c ON c.id = cp.component_id "
        f"WHERE {args[0]} "
        "ORDER BY c.name, cp.id LIMIT 100",
        args[1:],
    ).fetchall()


def chain_events(db, root_id):
    """一条链的完整时间线：初始领用 + 历次转交 + 历次归还。"""
    positions = db.execute(
        "SELECT id, parent_id, holder, qty, operator, remark, due_date, created_at "
        "FROM custody_positions WHERE root_id = ? ORDER BY id",
        (root_id,),
    ).fetchall()
    if not positions:
        return None

    returns = db.execute(
        "SELECT cr.id, cr.position_id, cr.qty, cr.operator, cr.remark, cr.created_at, "
        "       cp.holder "
        "FROM custody_returns cr "
        "JOIN custody_positions cp ON cp.id = cr.position_id "
        "WHERE cr.root_id = ? ORDER BY cr.id",
        (root_id,),
    ).fetchall()

    events = []
    for row in positions:
        kind = "out" if row["parent_id"] is None else "transfer"
        events.append(
            {
                "id": row["id"],
                "kind": kind,
                "holder": row["holder"],
                "qty": row["qty"],
                "operator": row["operator"],
                "remark": row["remark"],
                "due_date": row["due_date"],
                "created_at": row["created_at"],
            }
        )
    for row in returns:
        events.append(
            {
                "id": f"r{row['id']}",
                "kind": "return",
                "holder": row["holder"],
                "qty": row["qty"],
                "operator": row["operator"],
                "remark": row["remark"],
                "created_at": row["created_at"],
            }
        )
    events.sort(key=lambda item: (item["created_at"], str(item["id"])))
    return {"positions": [dict(row) for row in positions], "events": events}


def has_history(db, component_id):
    """器件是否存在流转记录（含已全部归还的），用于删除保护。"""
    row = db.execute(
        "SELECT 1 FROM custody_positions WHERE component_id = ? LIMIT 1",
        (component_id,),
    ).fetchone()
    return row is not None
