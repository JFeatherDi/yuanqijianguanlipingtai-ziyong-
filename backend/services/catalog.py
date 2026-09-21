"""元器件字段的规范化与校验。

纯函数：输入原始 JSON 字典，输出干净的字段字典，不触碰数据库。
"""
from __future__ import annotations

# 可写字段的唯一定义处 —— 新增字段只需在这里登记
EDITABLE_FIELDS = (
    "name",
    "category",
    "spec",
    "unit",
    "location",
    "threshold",
    "remark",
)

DEFAULT_UNIT = "个"


def to_text(value):
    return "" if value is None else str(value).strip()


def to_number(value, default=0.0):
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize(payload):
    """把任意输入整形成规范的器件字段字典（不含库存）。"""
    payload = payload or {}
    return {
        "name": to_text(payload.get("name")),
        "category": to_text(payload.get("category")),
        "spec": to_text(payload.get("spec")),
        "unit": to_text(payload.get("unit")) or DEFAULT_UNIT,
        "location": to_text(payload.get("location")),
        "threshold": max(to_number(payload.get("threshold")), 0.0),
        "remark": to_text(payload.get("remark")),
    }


def initial_stock(payload):
    """新建器件时的初始库存，允许为负外的任意数值。"""
    return to_number((payload or {}).get("stock"))


def validate(fields):
    """返回错误信息；通过校验时返回 None。"""
    if not fields.get("name"):
        return "器件名称不能为空"
    if len(fields["name"]) > 120:
        return "器件名称过长"
    if fields.get("threshold", 0) < 0:
        return "预警值不能为负数"
    return None


def pick_changes(payload):
    """只挑出请求里真正出现的可写字段，用于局部更新。"""
    payload = payload or {}
    return {key: payload[key] for key in EDITABLE_FIELDS if key in payload}