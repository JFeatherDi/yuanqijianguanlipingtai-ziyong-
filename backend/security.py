"""登录限流与会话鉴权。

- 同一 IP 连续失败 N 次后锁定一段时间，抵御暴力破解
- login_required 装饰器统一拦截未登录请求，返回 401
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
    return request.remote_addr or "unknown"


def _prune(now, stamps):
    return [stamp for stamp in stamps if now - stamp < Config.LOGIN_LOCK_SECONDS]


def check_login_limit():
    """返回 (是否允许登录, 剩余锁定秒数)。"""
    now = time.time()
    key = _client_key()
    with _lock:
        stamps = _prune(now, _failures[key])
        _failures[key] = stamps
        if len(stamps) >= Config.LOGIN_MAX_FAIL:
            remain = int(Config.LOGIN_LOCK_SECONDS - (now - stamps[0]))
            return False, max(remain, 0)
    return True, 0


def record_login_failure():
    with _lock:
        _failures[_client_key()].append(time.time())


def clear_login_failures():
    with _lock:
        _failures.pop(_client_key(), None)


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return jsonify({"ok": False, "msg": "未登录或会话已过期"}), 401
        return view(*args, **kwargs)

    return wrapper


def current_user():
    return session.get("user")