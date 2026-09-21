"""仪表盘统计：概览指标、出入库趋势、分类库存分布。"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request

from ..db import get_db
from ..security import login_required
from ..services.inventory import now_str

bp = Blueprint("stats", __name__, url_prefix="/api/stats")

OVERVIEW_SQL = """
SELECT
    (SELECT COUNT(*) FROM components)                                  AS kinds,
    (SELECT COUNT(*) FROM components WHERE IFNULL(category, '') = '')  AS uncategorized,
    (SELECT COUNT(DISTINCT category) FROM components
      WHERE IFNULL(category, '') <> '')                                AS categories,
    (SELECT IFNULL(SUM(stock), 0) FROM components)                     AS total_stock,
    (SELECT COUNT(*) FROM components
      WHERE threshold > 0 AND stock <= threshold)                      AS low_count,
    (SELECT COUNT(*) FROM components
      WHERE threshold > 0 AND stock > threshold)                       AS healthy_count,
    (SELECT COUNT(*) FROM components WHERE threshold > 0)              AS guarded_count,
    (SELECT IFNULL(SUM(delta), 0) FROM transactions WHERE delta > 0)   AS inbound_total,
    (SELECT IFNULL(SUM(-delta), 0) FROM transactions WHERE delta < 0)  AS outbound_total,
    (SELECT COUNT(*) FROM transactions)                                AS total_ops,
    (SELECT COUNT(*) FROM transactions WHERE created_at >= :since)     AS recent_ops,
    (SELECT COUNT(*) FROM transactions WHERE created_at >= :today)     AS today_ops
"""

# 注意：components 表本身就有 name 列，所以 GROUP BY 必须写完整表达式。
# 若写成 GROUP BY name，SQLite 会把它解析成输入列 components.name（按器件名分组），
# 而不是这里的输出别名，导致同一分类被拆成多行、分类名重复出现。
CATEGORY_EXPR = "IFNULL(NULLIF(category, ''), '未分类')"

CATEGORY_SQL = f"""
SELECT
    {CATEGORY_EXPR} AS name,
    COUNT(*)        AS kinds,
    IFNULL(SUM(stock), 0) AS stock,
    SUM(CASE WHEN threshold > 0 AND stock <= threshold THEN 1 ELSE 0 END) AS low_count
FROM components
GROUP BY {CATEGORY_EXPR}
ORDER BY stock DESC
"""

FLOW_SQL = """
SELECT
    date(created_at)                                    AS day,
    IFNULL(SUM(CASE WHEN delta > 0 THEN delta END), 0)  AS inbound,
    IFNULL(SUM(CASE WHEN delta < 0 THEN -delta END), 0) AS outbound
FROM transactions
WHERE date(created_at) >= ?
GROUP BY date(created_at)
"""


def _percent(part, whole):
    return round(part / whole * 100, 1) if whole else 0.0


@bp.route("/overview")
@login_required
def overview():
    db = get_db()
    yesterday = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    row = db.execute(
        OVERVIEW_SQL,
        {"since": yesterday, "today": date.today().isoformat()},
    ).fetchone()

    data = dict(row)
    data["guarded_rate"] = _percent(data["healthy_count"], data["guarded_count"])
    data["low_rate"] = _percent(data["low_count"], data["kinds"])
    data["updated_at"] = now_str()
    return jsonify({"ok": True, "data": data})


@bp.route("/categories")
@login_required
def categories():
    db = get_db()
    rows = db.execute(CATEGORY_SQL).fetchall()
    data = [dict(row) for row in rows]
    total = sum(item["stock"] for item in data)
    for item in data:
        item["share"] = _percent(item["stock"], total)
    return jsonify({"ok": True, "data": data, "total_stock": total})


@bp.route("/flow")
@login_required
def flow():
    """最近 N 天的出入库趋势，缺失的日期补 0，保证图表 X 轴连续。"""
    days = min(max(request.args.get("days", 7, type=int) or 7, 1), 90)
    start = date.today() - timedelta(days=days - 1)

    db = get_db()
    rows = db.execute(FLOW_SQL, (start.isoformat(),)).fetchall()
    by_day = {row["day"]: row for row in rows}

    series = []
    for offset in range(days):
        day = (start + timedelta(days=offset)).isoformat()
        row = by_day.get(day)
        series.append(
            {
                "date": day,
                "inbound": float(row["inbound"]) if row else 0.0,
                "outbound": float(row["outbound"]) if row else 0.0,
            }
        )

    return jsonify({"ok": True, "data": series, "days": days})