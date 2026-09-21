"""出入库流水：查询、导出、模板下载、批量导入。"""
from __future__ import annotations

import csv
import io

from flask import Blueprint, Response, jsonify, request

from ..db import get_db, to_dicts
from ..security import current_user, login_required
from ..services import importer
from ..services.importer import ImportError_
from ..services.inventory import TX_IMPORT, TX_INIT, apply_change

bp = Blueprint("records", __name__, url_prefix="/api/records")

RECORD_SQL = """
SELECT t.id, t.component_id, t.delta, t.type, t.operator, t.remark, t.created_at,
       c.name, c.spec, c.unit
FROM transactions t
JOIN components c ON c.id = t.component_id
{where}
ORDER BY t.id DESC
LIMIT ? OFFSET ?
"""

COUNT_SQL = """
SELECT COUNT(*) AS total FROM transactions t
JOIN components c ON c.id = t.component_id
{where}
"""

EXPORT_HEADER = ["名称", "分类", "规格", "单位", "位置", "库存", "预警值", "备注"]
TEMPLATE_ROWS = [
    ["电阻10K", "电阻", "10K 0805", "个", "柜A-1", "100", "20", "示例行"],
    ["电容100uF", "电容", "100uF 16V", "个", "柜A-2", "50", "10", "示例行"],
]


def _conditions():
    clauses, args = [], []
    component_id = request.args.get("cid")
    if component_id:
        clauses.append("t.component_id = ?")
        args.append(component_id)

    kind = (request.args.get("type") or "").strip()
    if kind:
        clauses.append("t.type = ?")
        args.append(kind)

    keyword = (request.args.get("q") or "").strip()
    if keyword:
        clauses.append("(c.name LIKE ? OR c.spec LIKE ?)")
        args.extend([f"%{keyword}%"] * 2)

    return ("WHERE " + " AND ".join(clauses) if clauses else ""), args


@bp.route("")
@login_required
def list_records():
    db = get_db()
    where, args = _conditions()
    limit = min(max(request.args.get("limit", 50, type=int) or 50, 1), 500)
    offset = max(request.args.get("offset", 0, type=int) or 0, 0)

    rows = db.execute(RECORD_SQL.format(where=where), [*args, limit, offset]).fetchall()
    total = db.execute(COUNT_SQL.format(where=where), args).fetchone()["total"]
    return jsonify({"ok": True, "data": to_dicts(rows), "total": total})


def _csv_response(text, filename):
    return Response(
        "\ufeff" + text,  # BOM，保证 Excel 正确识别中文
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _to_csv(rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerows(rows)
    return buffer.getvalue()


@bp.route("/export")
@login_required
def export_components():
    db = get_db()
    rows = db.execute(
        "SELECT name, category, spec, unit, location, stock, threshold, remark "
        "FROM components ORDER BY category, name"
    ).fetchall()
    body = _to_csv([EXPORT_HEADER, *([row[key] for key in row.keys()] for row in rows)])
    return _csv_response(body, "components.csv")


@bp.route("/template")
@login_required
def download_template():
    return _csv_response(_to_csv([EXPORT_HEADER, *TEMPLATE_ROWS]), "template.csv")


@bp.route("/import", methods=["POST"])
@login_required
def import_file():
    upload = request.files.get("file")
    if upload is None:
        return jsonify({"ok": False, "msg": "未收到上传文件"}), 400

    try:
        items, skipped = importer.parse(upload.read(), upload.filename or "")
    except ImportError_ as exc:
        return jsonify({"ok": False, "msg": str(exc)}), 400
    except Exception as exc:  # 解析库抛出的底层异常
        return jsonify({"ok": False, "msg": f"解析失败: {exc}"}), 400

    if not items:
        return jsonify({"ok": False, "msg": "没有可导入的有效数据行"}), 400

    db = get_db()
    operator = current_user()
    imported = 0
    try:
        for item in items:
            existing = db.execute(
                "SELECT id FROM components WHERE name = ? AND IFNULL(spec, '') = IFNULL(?, '')",
                (item["name"], item["spec"]),
            ).fetchone()

            if existing:
                # 已存在：库存累加到原记录
                if item["stock"]:
                    apply_change(db, existing["id"], item["stock"], TX_IMPORT, operator, "导入累加")
            else:
                cursor = db.execute(
                    "INSERT INTO components (name, category, spec, unit, location, stock, threshold, remark) "
                    "VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
                    (
                        item["name"],
                        item["category"],
                        item["spec"],
                        item["unit"],
                        item["location"],
                        item["threshold"],
                        item["remark"],
                    ),
                )
                if item["stock"]:
                    apply_change(db, cursor.lastrowid, item["stock"], TX_INIT, operator, "导入初始库存")
            imported += 1
        db.commit()
    except Exception as exc:
        db.rollback()
        return jsonify({"ok": False, "msg": f"写入失败: {exc}"}), 500

    return jsonify({"ok": True, "imported": imported, "skipped": skipped})