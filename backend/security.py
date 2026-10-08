"""登录限流与会话鉴权。

- 登录限流采用 IP 与账号双维度滑动窗口：同一 IP 失败过多（防爆破 sprayed
  弱口令）或同一账号失败过多（防换 IP 定向爆破单个账号）都会锁定一段时间。
- 登录成功只清账号维度的计数，不清 IP 计数：否则攻击者拿一个可用账号
  登录一次就能替同 IP 的爆破进度清零。
- login_required 装饰器统一拦截未登录请求，返回 401
- 普通用户会话记录口令版本号：管理员重置密码或删除账号后旧会话立即失效
- admin_required 在登录基础上再校验管理员角色，普通用户返回 403
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from functools import wraps

from flask import jsonify, request, session

from .config import Config

_failures: "defaultdict[str, list[float]]" = defaultdict(list)
_lock = threading.Lock()


def _client_key():
    return f"ip:{request.remote_addr or 'unknown'}"


def _account_key(username):
    return f"user:{username or 'unknown'}"


def _prune(now, stamps):
    return [stamp for stamp in stamps if now - stamp < Config.LOGIN_LOCK_SECONDS]


def check_login_limit(username=None):
    """返回 (是否允许登录, 剩余锁定秒数)。

    IP 与账号两个维度分别检查，任一超限即拒绝；对外不区分是哪个维度，
    避免向攻击者泄露「账号存在且已被盯上」这类信息。
    """
    now = time.time()
    keys = [_client_key()]
    if username:
        keys.append(_account_key(username))
    with _lock:
        for key in keys:
            stamps = _prune(now, _failures[key])
            _failures[key] = stamps
            limit = (
                Config.LOGIN_MAX_FAIL_PER_USER
                if key.startswith("user:")
                else Config.LOGIN_MAX_FAIL
            )
            if len(stamps) >= limit:
                remain = int(Config.LOGIN_LOCK_SECONDS - (now - stamps[0]))
                return False, max(remain, 0)
    return True, 0


def record_login_failure(username=None):
    """记录一次登录失败：同时计入 IP 与账号两个维度。"""
    now = time.time()
    with _lock:
        _failures[_client_key()].append(now)
        if username:
            _failures[_account_key(username)].append(now)


def clear_login_failures(username=None):
    """登录成功后清掉该账号的失败计数（IP 计数保留，见模块说明）。"""
    with _lock:
        if username:
            _failures.pop(_account_key(username), None)
        else:
            _failures.pop(_client_key(), None)


def reset_rate_limits():
    """清空全部限流状态。仅供测试使用，生产代码不要调用。"""
    with _lock:
        _failures.clear()


def _member_session_valid():
    """校验普通用户会话：账号仍存在，且口令版本与登录时一致。"""
    from .db import get_db
    from .services import users as user_service

    uid = session.get("uid")
    if uid is None:
        return False
    row = user_service.get_user(get_db(), uid)
    if row is None:
        return False
    return row["pw_version"] == session.get("ver")


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return jsonify({"ok": False, "msg": "未登录或会话已过期"}), 401
        if session.get("role") != "admin" and not _member_session_valid():
            session.clear()
            return jsonify({"ok": False, "msg": "会话已失效，请重新登录"}), 401
        return view(*args, **kwargs)

    return wrapper


def admin_required(view):
    """管理员专用接口：先过登录校验，再校验角色。"""

    @login_required
    @wraps(view)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            return jsonify({"ok": False, "msg": "该操作需要管理员权限"}), 403
        return view(*args, **kwargs)

    return wrapper


def current_user():
    return session.get("user")
