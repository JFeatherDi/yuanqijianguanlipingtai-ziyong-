"""普通用户账号管理。

管理员账号来自环境变量（APP_USERNAME / APP_PASSWORD），不入库；
普通用户存放在 users 表，密码用 Werkzeug 哈希保存。

会话失效机制：users.pw_version 是账号的「口令版本号」，
重置密码时 +1；登录会话里记录登录时的版本号，
login_required 每次校验版本一致，重置或删除后旧会话立即失效。
"""
from __future__ import annotations

import re

from werkzeug.security import check_password_hash, generate_password_hash

from .inventory import now_str

USERNAME_MAX = 40
PASSWORD_MIN = 6
PASSWORD_MAX = 128
ROLES = ("manager", "member")
USER_TYPES = ("teacher", "student")
FULL_NAME_MAX = 80
MENTOR_MAX = 120
PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")
STUDENT_ID_PATTERN = re.compile(r"^\d{4,20}$")


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


def _validate_user_type(user_type) -> str:
    user_type = (user_type or "").strip().lower()
    if user_type not in USER_TYPES:
        raise UserError("请选择老师或学生")
    return user_type


def _validate_full_name(full_name) -> str:
    full_name = str(full_name or "").strip()
    if not full_name:
        raise UserError("姓名不能为空")
    if len(full_name) > FULL_NAME_MAX:
        raise UserError(f"姓名不能超过 {FULL_NAME_MAX} 个字符")
    return full_name


def _validate_account(username, user_type) -> str:
    username = _validate_username(username)
    if user_type == "teacher" and not PHONE_PATTERN.fullmatch(username):
        raise UserError("老师账号必须是 11 位手机号")
    if user_type == "student" and not STUDENT_ID_PATTERN.fullmatch(username):
        raise UserError("学生账号必须是 4-20 位数字学号")
    return username


def _validate_phone(phone, user_type, username) -> str:
    """老师账号即手机号；学生必须单独填写手机号。"""
    if user_type == "teacher":
        return username
    phone = str(phone or "").strip()
    if not phone:
        raise UserError("学生必须填写手机号")
    if not PHONE_PATTERN.fullmatch(phone):
        raise UserError("学生手机号必须是正确的 11 位手机号")
    return phone


def default_password(username) -> str:
    """按实验室规则生成初始密码：swust + 账号后四位。"""
    username = (username or "").strip()
    if len(username) < 4:
        raise UserError("账号至少需要 4 位")
    return f"swust{username[-4:]}"


def _validate_mentor(mentor, user_type) -> str:
    mentor = str(mentor or "").strip()
    if user_type == "student" and not mentor:
        raise UserError("学生必须填写所属导师")
    if len(mentor) > MENTOR_MAX:
        raise UserError(f"所属导师不能超过 {MENTOR_MAX} 个字符")
    return mentor if user_type == "student" else ""


def list_users(db):
    return db.execute(
        "SELECT id, username, full_name, phone, user_type, mentor, role, pw_version, created_at "
        "FROM users ORDER BY id"
    ).fetchall()


def get_user(db, user_id):
    return db.execute(
        "SELECT id, username, full_name, phone, user_type, mentor, role, pw_version, created_at "
        "FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


def get_by_name(db, username: str):
    return db.execute(
        "SELECT * FROM users WHERE username = ?", ((username or "").strip(),)
    ).fetchone()


def _validate_role(role):
    role = (role or "member").strip()
    if role not in ROLES:
        raise UserError("用户角色无效")
    return role


def create_user(
    db,
    username,
    role="member",
    user_type=None,
    mentor="",
    full_name="",
    phone="",
    reserved_names=("reserved",),
):
    """创建数据库用户。reserved_names 用于挡住与总管理员重名的注册。"""
    user_type = _validate_user_type(user_type)
    username = _validate_account(username, user_type)
    full_name = _validate_full_name(full_name)
    phone = _validate_phone(phone, user_type, username)
    mentor = _validate_mentor(mentor, user_type)
    password = default_password(username)
    role = _validate_role(role)
    if username in reserved_names:
        raise UserError("该用户名为管理员保留，请换一个")
    if get_by_name(db, username) is not None:
        raise UserError("该用户名已存在")
    cursor = db.execute(
        "INSERT INTO users (username, full_name, phone, password_hash, user_type, mentor, role, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            username,
            full_name,
            phone,
            generate_password_hash(password),
            user_type,
            mentor,
            role,
            now_str(),
        ),
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


def set_role(db, user_id, role):
    """修改角色并递增版本，使旧会话立即失效。"""
    row = get_user(db, user_id)
    if row is None:
        raise UserError("用户不存在或已删除")
    role = _validate_role(role)
    db.execute(
        "UPDATE users SET role = ?, pw_version = pw_version + 1 WHERE id = ?",
        (role, user_id),
    )
    return row["username"], role


def set_mentor(db, user_id, mentor):
    """补充或修改学生所属导师。老师账号不允许设置该字段。"""
    row = get_user(db, user_id)
    if row is None:
        raise UserError("用户不存在或已删除")
    if row["user_type"] != "student":
        raise UserError("只有学生用户需要设置所属导师")
    mentor = _validate_mentor(mentor, "student")
    db.execute("UPDATE users SET mentor = ? WHERE id = ?", (mentor, user_id))
    return row["username"], mentor


def set_full_name(db, user_id, full_name):
    """补充或修改用户姓名。"""
    row = get_user(db, user_id)
    if row is None:
        raise UserError("用户不存在或已删除")
    full_name = _validate_full_name(full_name)
    db.execute("UPDATE users SET full_name = ? WHERE id = ?", (full_name, user_id))
    return row["username"], full_name


def set_phone(db, user_id, phone):
    """修改学生手机号；老师手机号由登录账号确定。"""
    row = get_user(db, user_id)
    if row is None:
        raise UserError("用户不存在或已删除")
    if row["user_type"] != "student":
        raise UserError("老师手机号即登录账号，无需单独修改")
    phone = _validate_phone(phone, "student", row["username"])
    db.execute("UPDATE users SET phone = ? WHERE id = ?", (phone, user_id))
    return row["username"], phone


def delete_user(db, user_id):
    row = get_user(db, user_id)
    if row is None:
        raise UserError("用户不存在或已删除")
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return row["username"]
