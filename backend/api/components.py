"""元器件 CRUD。"""
from __future__ import annotations

import sqlite3

import base64

from flask import Blueprint, jsonify, request

from ..db import get_db, to_dicts
from ..security import current_user, login_required, superadmin_required
from ..services import catalog, custody
from ..services.inventory import TX_ADJUST, TX_INIT, log_transaction

bp = Blueprint("components", __name__, url_prefix="/api/components")

MAX_IMAGE_BYTES = 1_400_000


def detect_image_mime(content):
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None

LIST_SQL = """
WITH device_rows AS (
    SELECT c.*,
           (SELECT ROUND(IFNULL(SUM(p.qty), 0), 6)
              FROM custody_positions p
             WHERE p.component_id = c.id AND ROUND(p.qty, 6) > 0) AS borrowed_qty
      FROM components c
)
SELECT *,
       CASE
           WHEN stock > 0 THEN 'available'
           WHEN borrowed_qty > 0 THEN 'borrowed'
           WHEN maintenance_qty > 0 THEN 'maintenance'
           WHEN unavailable_qty > 0 THEN 'unavailable'
           ELSE 'unavailable'
       END AS equipment_status
FROM device_rows
{where}
ORDER BY category, name
"""


def _filters():
    """把查询参数翻译成 WHERE 片段，保持路由函数只做编排。"""
    clauses, args = [], []
    keyword = (request.args.get("q") or "").strip()
    if keyword:
        like = f"%{keyword}%"
        clauses.append(
            "(name LIKE ? OR asset_no LIKE ? OR category LIKE ? OR spec LIKE ? OR location LIKE ? OR owner LIKE ?)"
        )
        args.extend([like] * 6)

    category = (request.args.get("category") or "").strip()
    if category:
        clauses.append("category = ?")
        args.append(category)

    if request.args.get("low") in ("1", "true", "yes"):
        clauses.append("threshold > 0 AND stock <= threshold")

    return ("WHERE " + " AND ".join(clauses) if clauses else ""), args


@bp.route("")
@login_required
def list_components():
    db = get_db()
    where, args = _filters()
    rows = db.execute(LIST_SQL.format(where=where), args).fetchall()
    return jsonify({"ok": True, "data": to_dicts(rows)})


@bp.route("", methods=["POST"])
@superadmin_required
def create_component():
    db = get_db()
    payload = request.get_json(silent=True) or {}
    fields = catalog.normalize(payload)

    error = catalog.validate(fields)
    if error:
        return jsonify({"ok": False, "msg": error}), 400

    manual_status = payload.get("manual_status", "available")
    if manual_status not in {"available", "maintenance", "unavailable"}:
        return jsonify({"ok": False, "msg": "设备状态无效"}), 400

    try:
        cursor = db.execute(
            "INSERT INTO components "
            "(name, asset_no, image_data, category, spec, unit, location, owner, "
            "maintenance, unavailable, maintenance_qty, unavailable_qty, stock, threshold, remark) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
            (
                fields["name"],
                fields["asset_no"],
                fields["image_data"],
                fields["category"],
                fields["spec"],
                fields["unit"],
                fields["location"],
                fields["owner"],
                1 if manual_status == "maintenance" else 0,
                1 if manual_status == "unavailable" else 0,
                1 if manual_status == "maintenance" else 0,
                1 if manual_status == "unavailable" else 0,
                1 if manual_status == "available" else 0,
                fields["remark"],
            ),
        )
        component_id = cursor.lastrowid
        log_transaction(db, component_id, 1, TX_INIT, current_user(), "登记单台设备")

        db.commit()
        return jsonify({"ok": True, "id": component_id})
    except sqlite3.IntegrityError as exc:
        db.rollback()
        message = "固定资产编号已存在" if "asset_no" in str(exc) else "设备信息保存失败"
        return jsonify({"ok": False, "msg": message}), 400


@bp.route("/<int:component_id>", methods=["PUT"])
@superadmin_required
def update_component(component_id):
    db = get_db()
    payload = request.get_json(silent=True) or {}
    changes = catalog.pick_changes(payload)
    current = db.execute(
        "SELECT c.*, EXISTS(SELECT 1 FROM custody_positions p "
        " WHERE p.component_id = c.id AND ROUND(p.qty, 6) > 0) AS borrowed "
        "FROM components c WHERE c.id = ?",
        (component_id,),
    ).fetchone()
    if current is None:
        return jsonify({"ok": False, "msg": "设备不存在"}), 404

    changes.pop("threshold", None)
    if "maintenance" in changes:
        changes["maintenance"] = catalog.to_flag(changes["maintenance"])
    if "unavailable" in changes:
        changes["unavailable"] = catalog.to_flag(changes["unavailable"])
    if changes.get("maintenance") == 1:
        changes["unavailable"] = 0
    elif changes.get("unavailable") == 1:
        changes["maintenance"] = 0
    if "name" in changes:
        changes["name"] = catalog.to_text(changes["name"])
        if not changes["name"]:
            return jsonify({"ok": False, "msg": "器件名称不能为空"}), 400
    for key in ("asset_no", "image_data", "category", "spec", "unit", "location", "owner", "remark"):
        if key in changes:
            changes[key] = catalog.to_text(changes[key])

    error = catalog.validate({"name": changes.get("name", "valid"), **changes})
    if error:
        return jsonify({"ok": False, "msg": error}), 400

    requested_status = payload.get("manual_status")
    if requested_status is not None:
        if requested_status not in {"available", "maintenance", "unavailable"}:
            return jsonify({"ok": False, "msg": "设备状态无效"}), 400
        if current["borrowed"]:
            return jsonify({"ok": False, "msg": "借出中的设备不能手动修改状态"}), 400
        changes.update({
            "stock": 1 if requested_status == "available" else 0,
            "maintenance": 1 if requested_status == "maintenance" else 0,
            "maintenance_qty": 1 if requested_status == "maintenance" else 0,
            "unavailable": 1 if requested_status == "unavailable" else 0,
            "unavailable_qty": 1 if requested_status == "unavailable" else 0,
            "threshold": 0,
        })
    if not changes:
        return jsonify({"ok": True})

    assignments = ", ".join(f"{key} = ?" for key in changes)
    try:
        if changes:
            db.execute(
                f"UPDATE components SET {assignments} WHERE id = ?",
                [*changes.values(), component_id],
            )
        if requested_status is not None:
            log_transaction(db, component_id, 0, TX_ADJUST, current_user(), "设备状态调整")
        db.commit()
    except sqlite3.IntegrityError as exc:
        db.rollback()
        message = "固定资产编号已存在" if "asset_no" in str(exc) else "设备信息保存失败"
        return jsonify({"ok": False, "msg": message}), 400

    return jsonify({"ok": True})


@bp.route("/<int:component_id>/image", methods=["POST"])
@superadmin_required
def upload_component_image(component_id):
    upload = request.files.get("image")
    if upload is None:
        return jsonify({"ok": False, "msg": "请选择设备图片"}), 400

    content = upload.read(MAX_IMAGE_BYTES + 1)
    if not content:
        return jsonify({"ok": False, "msg": "图片文件为空"}), 400
    if len(content) > MAX_IMAGE_BYTES:
        return jsonify({"ok": False, "msg": "图片过大，请选择小于 1.4 MB 的图片"}), 400

    mime = detect_image_mime(content)
    if mime is None:
        return jsonify({"ok": False, "msg": "仅支持 JPG、PNG 或 WebP 图片"}), 400

    db = get_db()
    if db.execute("SELECT id FROM components WHERE id = ?", (component_id,)).fetchone() is None:
        return jsonify({"ok": False, "msg": "设备不存在"}), 404

    image_data = f"data:{mime};base64,{base64.b64encode(content).decode('ascii')}"
    db.execute("UPDATE components SET image_data = ? WHERE id = ?", (image_data, component_id))
    db.commit()
    return jsonify({"ok": True})


@bp.route("/<int:component_id>/image", methods=["DELETE"])
@superadmin_required
def delete_component_image(component_id):
    db = get_db()
    cursor = db.execute("UPDATE components SET image_data = '' WHERE id = ?", (component_id,))
    if cursor.rowcount == 0:
        return jsonify({"ok": False, "msg": "设备不存在"}), 404
    db.commit()
    return jsonify({"ok": True})


@bp.route("/bulk-delete", methods=["POST"])
@superadmin_required
def bulk_delete_components():
    """整批删除无流转历史的设备；任一设备不符合条件时不执行删除。"""
    db = get_db()
    payload = request.get_json(silent=True) or {}
    raw_ids = payload.get("ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        return jsonify({"ok": False, "msg": "请选择要删除的设备"}), 400
    if len(raw_ids) > 500:
        return jsonify({"ok": False, "msg": "单次最多删除 500 台设备"}), 400
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in raw_ids):
        return jsonify({"ok": False, "msg": "设备编号无效"}), 400

    component_ids = list(dict.fromkeys(raw_ids))
    placeholders = ",".join("?" for _ in component_ids)
    existing = db.execute(
        f"SELECT id, name, asset_no FROM components WHERE id IN ({placeholders})",
        component_ids,
    ).fetchall()
    if len(existing) != len(component_ids):
        return jsonify({"ok": False, "msg": "部分设备已不存在，请刷新列表后重试"}), 404

    protected = db.execute(
        f"SELECT c.name, c.asset_no FROM components c "
        f"WHERE c.id IN ({placeholders}) "
        "AND EXISTS (SELECT 1 FROM custody_positions p WHERE p.component_id = c.id) "
        "ORDER BY c.name, c.asset_no",
        component_ids,
    ).fetchall()
    if protected:
        labels = [row["asset_no"] or row["name"] for row in protected[:3]]
        suffix = "等" if len(protected) > 3 else ""
        return jsonify({
            "ok": False,
            "msg": f"{', '.join(labels)}{suffix}存在借还记录，整批设备均未删除",
        }), 400

    try:
        db.execute(f"DELETE FROM transactions WHERE component_id IN ({placeholders})", component_ids)
        cursor = db.execute(f"DELETE FROM components WHERE id IN ({placeholders})", component_ids)
        db.commit()
    except sqlite3.DatabaseError:
        db.rollback()
        raise
    return jsonify({"ok": True, "deleted": cursor.rowcount})


@bp.route("/<int:component_id>", methods=["DELETE"])
@superadmin_required
def delete_component(component_id):
    db = get_db()

    # 有流转历史的器件禁止删除：领用链、转交与归还记录是追踪凭证
    if custody.has_history(db, component_id):
        return jsonify({"ok": False, "msg": "该器件存在流转记录，禁止删除"}), 400

    db.execute("DELETE FROM transactions WHERE component_id = ?", (component_id,))
    db.execute("DELETE FROM components WHERE id = ?", (component_id,))
    db.commit()
    return jsonify({"ok": True})
