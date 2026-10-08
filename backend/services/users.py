"""普通用户账号管理。

管理员账号来自环境变量（APP_USERNAME / APP_PASSWORD），不入库；
普通用户存放在 users 表，密码用 Werkzeug 哈希保存。

会话失效机制：users.pw_version 是账号的「口令版本号」，
重置密码时 +1；登录会话里记录登录时的版本号，
login_required 每次校验版本一致，重置或删除后旧会话立即失效。
"""
from __future__ import annotations

from werkzeug.security import check_password_hash, generate_password_hash

from .inventory import now_str

USERNAME_MAX = 40
PASSWORD_MIN = 6
PASSWORD_MAX = 128


class UserError(Exception):
    """可预期错误，消息可直接返回给前端。"""


def _validate_username(username: str) -> str:
    username = (username or "").strip()
    if not username:
        raise UserError("用户名不能为空")
    if len(username) > USERNAME_MAX:
        raise UserError(f"用户名不能超过 {USERNAME_MAX} 个字符")
    return username


def _validate_password(password) -> str:
    password = str(password or "")
    if len(password) < PASSWORD_MIN:
        raise UserError(f"密码至少 {PASSWORD_MIN} 位")
    if len(password) > PASSWORD_MAX:
        raise UserError(f"密码不能超过 {PASSWORD_MAX} 位")
    return password


def list_users(db):
    return db.execute(
        "SELECT id, username, pw_version, created_at FROM users ORDER BY id"
    ).fetchall()


def get_user(db, user_id):
    return db.execute(
        "SELECT id, username, pw_version, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


def get_by_name(db, username: str):
    return db.execute(
        "SELECT * FROM users WHERE username = ?", ((username or "").strip(),)
    ).fetchone()


def create_user(db, username, password, reserved_names=("reserved",)):
    """创建普通用户。reserved_names 用于挡住与环境变量管理员重名的注册。"""
    username = _validate_username(username)
    password = _validate_password(password)
    if username in reserved_names:
        raise UserError("该用户名为管理员保留，请换一个")
    if get_by_name(db, username) is not None:
        raise UserError("该用户名已存在")
    cursor = db.execute(
        "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
        (username, generate_password_hash(password), now_str()),
    )
    return cursor.lastrowid


def verify_user(db, username, password):
    """校验普通用户登录，成功返回用户行，失败返回 None。"""
    row = get_by_name(db, username)
    if row is None:
        return None
    if not check_password_hash(row["password_hash"], str(password or "")):
        return None
    return row


def set_password(db, user_id, password):
    """重置密码并使旧会话失效。返回 (用户名, 新口令版本)。"""
    row = get_user(db, user_id)
    if row is None:
        raise UserError("用户不存在或已删除")
    password = _validate_password(password)
    db.execute(
        "UPDATE users SET password_hash = ?, pw_version = pw_version + 1 WHERE id = ?",
        (generate_password_hash(password), user_id),
    )
    return row["username"], row["pw_version"] + 1


def delete_user(db, user_id):
    row = get_user(db, user_id)
    if row is None:
        raise UserError("用户不存在或已删除")
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return row["username"]
