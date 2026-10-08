"""入库 / 出库。

出库规则：
- 申请人必填（最多 120 字），写入流水 transactions.applicant；
- 每笔新出库同时创建一条独立流转链，申请人为初始持有人。
数量校验统一走 services/quantity.py：正数、最多六位小数、上限十亿。
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..db import get_db
from ..security import current_user, login_required
from ..services import custody
from ..services.catalog import to_text
from ..services.custody import CustodyError
from ..services.inventory import consume, log_transaction, replenish
from ..services.quantity import positive_quantity

bp = Blueprint("stock", __name__, url_prefix="/api/stock")

APPLICANT_MAX = 120


def _read_quantity(payload):
    """校验数量，非法时抛 ValueError（消息可直接展示）。"""
    return positive_quantity(payload.get("qty"))


def _read_applicant(payload):
    """出库申请人：必填、去空格、限长。"""
    applicant = to_text(payload.get("applicant"))
    if not applicant:
        return None, "请填写申请人"
    if len(applicant) > APPLICANT_MAX:
        return None, f"申请人不能超过 {APPLICANT_MAX} 个字符"
    return applicant, None


@bp.route("/in", methods=["POST"])
@login_required
def stock_in():
    db = get_db()
    payload = request.get_json(silent=True) or {}
    try:
        qty = _read_quantity(payload)
    except ValueError as exc:
        return jsonify({"ok": False, "msg": str(exc)}), 400

    component_id = payload.get("id")
    if not _exists(db, component_id):
        return jsonify({"ok": False, "msg": "器件不存在"}), 404

    stock = replenish(db, component_id, qty, current_user(), to_text(payload.get("remark")))
    db.commit()
    return jsonify({"ok": True, "stock": stock})


@bp.route("/out", methods=["POST"])
@login_required
def stock_out():
    db = get_db()
    payload = request.get_json(silent=True) or {}
    try:
        qty = _read_quantity(payload)
    except ValueError as exc:
        return jsonify({"ok": False, "msg": str(exc)}), 400

    applicant, error = _read_applicant(payload)
    if error:
        return jsonify({"ok": False, "msg": error}), 400

    try:
        # 预计归还日期可选；非法日期直接拒绝，避免无效约定混进流转链
        due_date = custody.normalize_due_date(payload.get("due_date"))
    except CustodyError as exc:
        return jsonify({"ok": False, "msg": str(exc)}), 400

    component_id = payload.get("id")
    if not _exists(db, component_id):
        return jsonify({"ok": False, "msg": "器件不存在"}), 404

    succeeded, message = consume(db, component_id, qty)
    if not succeeded:
        status = 404 if message == "器件不存在" else 400
        return jsonify({"ok": False, "msg": message}), status

    # 库存已在 consume 中原子扣减；流水与流转链随同一事务提交
    remark = to_text(payload.get("remark"))
    log_transaction(db, component_id, -qty, "out", current_user(), remark, applicant)
    try:
        custody.create_chain(db, component_id, applicant, qty, current_user(), remark, due_date)
    except CustodyError:
        db.rollback()
        raise
    db.commit()

    row = db.execute(
        "SELECT ROUND(stock, 6) AS stock FROM components WHERE id = ?", (component_id,)
    ).fetchone()
    return jsonify({"ok": True, "stock": row["stock"]})


def _exists(db, component_id):
    return (
        db.execute("SELECT id FROM components WHERE id = ?", (component_id,)).fetchone()
        is not None
    )
