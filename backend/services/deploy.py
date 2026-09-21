"""GitHub Webhook 的签名校验与部署触发。

刻意不依赖 Flask 请求上下文，便于脱离 HTTP 单独验证签名逻辑。
"""
from __future__ import annotations

import hashlib
import hmac
import os
import subprocess

SIGNATURE_HEADER = "X-Hub-Signature-256"
EVENT_HEADER = "X-GitHub-Event"
PUSH_EVENT = "push"


def sign(secret, payload):
    """计算 GitHub 约定的签名值（带 sha256= 前缀）。"""
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def signature_matches(secret, payload, signature):
    """恒定时间比较签名。

    密钥或签名任一缺失都视为不匹配：未配置密钥时必须拒绝，
    否则任何人都能用空签名触发一次部署。
    """
    if not secret or not signature:
        return False
    return hmac.compare_digest(sign(secret, payload), signature)


def trigger(script_path, log_path):
    """异步执行部署脚本并立即返回，不阻塞 webhook 响应。

    脚本自身会重启本服务，因此必须放进独立会话（start_new_session），
    否则服务被停掉时子进程会一起收到信号，git pull 只做了一半。
    输出重定向到日志文件而不是黑洞，部署失败才有据可查。

    返回 False 表示脚本缺失或 bash 无法启动。
    """
    if not os.path.isfile(script_path):
        return False

    with open(log_path, "ab") as log:
        try:
            subprocess.Popen(
                ["bash", script_path],
                stdout=log,
                stderr=subprocess.STDOUT,
                cwd=os.path.dirname(script_path),
                start_new_session=True,
            )
        except OSError:
            return False
    return True