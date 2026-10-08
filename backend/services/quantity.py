"""数量精度服务：所有出入库 / 流转数量的唯一校验与归整入口。

背景：SQLite REAL 是二进制浮点，0.3 - 0.1 会得到 0.19999999999999998，
再转交 0.2 就会被「库存不足」拒绝。处理方案（六位归整）：

- 入口统一用 Decimal 校验：必须是正数、最多 6 位小数、不超过十亿；
- 落库前把数量归整到 6 位小数；
- 库存与持有量的加减、比较全部用 SQLite ROUND(..., 6)，
  保证「0.3 分两次转交 0.1、0.2」这类操作不再被浮点残量卡住。

注意：数据库列仍是 REAL，不是定点整数方案；6 位是全局约定的精度上限。
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

# 单个数量的上限：十亿。实验室场景远用不到，主要防手滑输入 1e18 之类的值
MAX_QUANTITY = Decimal("1000000000")

# 全局允许的最大小数位数
MAX_DECIMALS = 6

_QUANT = Decimal(1).scaleb(-MAX_DECIMALS)  # 0.000001


def round6(value) -> float:
    """把任意数值归整到 6 位小数（四舍五入），供落库与 SQL 参数统一使用。"""
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return float(value)
    if not dec.is_finite():
        return float(value)
    return float(dec.quantize(_QUANT, rounding=ROUND_HALF_UP))


def positive_quantity(value, label: str = "数量") -> float:
    """校验并归整一个「必须为正」的数量，非法时抛 ValueError（消息可直接展示）。

    规则：
    - 接受 int / float / 数字字符串；
    - 必须有限、大于 0、不超过 MAX_QUANTITY；
    - 小数位最多 6 位（多输入一位都拒绝，避免用户以为精度被默默截断）。
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError(f"{label}不能为空")

    try:
        dec = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{label}必须是数字") from None

    if not dec.is_finite():
        raise ValueError(f"{label}必须是有限数字")
    if dec <= 0:
        raise ValueError(f"{label}必须大于 0")
    if dec > MAX_QUANTITY:
        raise ValueError(f"{label}不能超过 {MAX_QUANTITY}")
    if dec != dec.quantize(_QUANT, rounding=ROUND_HALF_UP):
        raise ValueError(f"{label}最多支持 {MAX_DECIMALS} 位小数")

    return float(dec.quantize(_QUANT, rounding=ROUND_HALF_UP))


def nonnegative_quantity(value, label: str = "数量", default: str = "0") -> float:
    """校验并归整一个「允许为 0」的数量（初始库存、导入库存、预警值）。

    与 positive_quantity 的差别：0 合法；精度规则相同（超 6 位拒绝，
    而不是静默截断——与入库/出库入口保持一致的行为）。
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return 0.0

    try:
        dec = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{label}必须是数字") from None

    if not dec.is_finite():
        raise ValueError(f"{label}必须是有限数字")
    if dec < 0:
        raise ValueError(f"{label}不能为负数")
    if dec > MAX_QUANTITY:
        raise ValueError(f"{label}不能超过 {MAX_QUANTITY}")
    if dec != dec.quantize(_QUANT, rounding=ROUND_HALF_UP):
        raise ValueError(f"{label}最多支持 {MAX_DECIMALS} 位小数")

    return float(dec.quantize(_QUANT, rounding=ROUND_HALF_UP))
