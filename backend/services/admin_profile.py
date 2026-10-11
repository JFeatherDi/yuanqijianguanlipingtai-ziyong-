"""总管理员资料：固定账号由配置提供，姓名与手机号持久化到 system_meta。"""
from __future__ import annotations

import re

from ..config import Config

FULL_NAME_KEY = "superadmin_full_name"
PHONE_KEY = "superadmin_phone"
FULL_NAME_MAX = 80
PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")


class AdminProfileError(Exception):
    """总管理员资料校验错误。"""


def _meta_value(db, key, fallback=""):
    row = db.execute("SELECT value FROM system_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row is not None else fallback


def get_profile(db):
    return {
        "username": Config.USERNAME,
        "full_name": _meta_value(db, FULL_NAME_KEY, Config.ADMIN_FULL_NAME),
        "phone": _meta_value(db, PHONE_KEY, Config.ADMIN_PHONE),
        "role": "superadmin",
    }


def update_profile(db, full_name, phone):
    full_name = str(full_name or "").strip()
    phone = str(phone or "").strip()
    if not full_name:
        raise AdminProfileError("总管理员姓名不能为空")
    if len(full_name) > FULL_NAME_MAX:
        raise AdminProfileError(f"总管理员姓名不能超过 {FULL_NAME_MAX} 个字符")
    if not PHONE_PATTERN.fullmatch(phone):
        raise AdminProfileError("请输入正确的 11 位手机号")

    db.executemany(
        "INSERT INTO system_meta(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        ((FULL_NAME_KEY, full_name), (PHONE_KEY, phone)),
    )
    return {
        "username": Config.USERNAME,
        "full_name": full_name,
        "phone": phone,
        "role": "superadmin",
    }
