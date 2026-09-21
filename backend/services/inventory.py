"""库存变更的唯一入口。

约束：任何库存变化都必须「改库存」与「写流水」同时发生，避免账实不符。
"""
from __future__ import annotations

from datetime import datetime

TX_INIT = "init"
TX_IN = "in"
TX_OUT = "out"
TX_IMPORT = "import"

# 流水类型的中文名，前端与导出共用同一份事实来源
TX_LABELS = {
    TX_INIT: "初始化",
    TX_IN: "入库",
    TX_OUT: "出库",
    TX_IMPORT: "导入",
}


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_transaction(db, component_id, delta, kind, operator, remark=""):
    """只写流水，不改库存。供已原子扣减的出库场景使用。"""
    db.execute(
        "INSERT INTO transactions (component_id, delta, type, operator, remark, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (component_id, delta, kind, operator, remark or "", now_str()),
    )


def apply_change(db, component_id, delta, kind, operator, remark=""):
    """累加库存 + 写流水。delta 为负表示减少。"""
    db.execute(
        "UPDATE components SET stock = stock + ? WHERE id = ?",
        (delta, component_id),
    )
    log_transaction(db, component_id, delta, kind, operator, remark)


def consume(db, component_id, qty):
    """原子出库：WHERE stock >= ? 保证并发下也不会扣成负数。

    返回 (是否成功, 错误信息)。
    """
    cursor = db.execute(
        "UPDATE components SET stock = stock - ? WHERE id = ? AND stock >= ?",
        (qty, component_id, qty),
    )
    if cursor.rowcount == 1:
        return True, None

    db.rollback()
    row = db.execute("SELECT stock FROM components WHERE id = ?", (component_id,)).fetchone()
    if row is None:
        return False, "器件不存在"
    return False, f"库存不足，当前可用 {row['stock']}"


def replenish(db, component_id, qty, operator, remark=""):
    """入库：库存累加 + 写流水。返回更新后的库存。"""
    apply_change(db, component_id, qty, TX_IN, operator, remark)
    row = db.execute("SELECT stock FROM components WHERE id = ?", (component_id,)).fetchone()
    return row["stock"] if row else None