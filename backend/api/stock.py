"""入库 / 出库。"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..db import get_db
from ..security import current_user, login_required
from ..services.catalog import to_number, to_text
from ..services.inventory import consume, log_transaction, replenish

bp = Blueprint("stock", __name__, url_prefix="/api/stock")


def _read_request():
    """把请求体整形成 (器件 id, 数量, 备注)；数量非法时返回错误。"""
    payload = request.get_json(silent=True) or {}
    qty = to_number(payload.get("qty"), 0.0)
    if qty <= 0:
        return None, None, None, "数量必须大于 0"
    return payload.get("id"), qty, to_text(payload.get("remark")), None


def _exists(db, component_id):
    return db.execute("SELECT id FROM components WHERE id = ?", (component_id,)).fetchone() is not None


@bp.route("/in", methods=["POST"])
@login_required
def stock_in():
    db = get_db()
    component_id, qty, remark, error = _read_request()
    if error:
        return jsonify({"ok": False, "msg": error}), 400
    if not _exists(db, component_id):
        return jsonify({"ok": False, "msg": "器件不存在"}), 404

    stock = replenish(db, component_id, qty, current_user(), remark)
    db.commit()
    return jsonify({"ok": True, "stock": stock})


@bp.route("/out", methods=["POST"])
@login_required
def stock_out():
    db = get_db()
    component_id, qty, remark, error = _read_request()
    if error:
        return jsonify({"ok": False, "msg": error}), 400

    succeeded, message = consume(db, component_id, qty)
    if not succeeded:
        status = 404 if message == "器件不存在" else 400
        return jsonify({"ok": False, "msg": message}), status

    # 库存已在 consume 中原子扣减，这里只补流水
    log_transaction(db, component_id, -qty, "out", current_user(), remark)
    db.commit()

    row = db.execute("SELECT stock FROM components WHERE id = ?", (component_id,)).fetchone()
    return jsonify({"ok": True, "stock": row["stock"]})