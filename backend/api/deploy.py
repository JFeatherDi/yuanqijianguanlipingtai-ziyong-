"""GitHub Webhook 接口：校验签名后触发服务器自动部署。

路径刻意保持 /webhook 而不是 /api/webhook —— 仓库里的 Payload URL 已经按
这个地址配置，改路径会同时让 GitHub 侧失效。

不加 login_required：GitHub 不会携带会话 Cookie，鉴权完全依赖 HMAC 签名。
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..config import Config
from ..services import deploy

bp = Blueprint("deploy", __name__)


@bp.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_data()
    signature = request.headers.get(deploy.SIGNATURE_HEADER, "")

    if not Config.WEBHOOK_SECRET:
        # 与「签名错误」区分开：部署日志里能直接看出是没配密钥还是被伪造
        return jsonify({"ok": False, "msg": "webhook secret not configured"}), 503

    if not deploy.signature_matches(Config.WEBHOOK_SECRET, payload, signature):
        return jsonify({"ok": False, "msg": "invalid signature"}), 403

    event = request.headers.get(deploy.EVENT_HEADER, "")
    if event != deploy.PUSH_EVENT:
        return jsonify({"ok": True, "msg": f"ignored event: {event}"})

    if not deploy.trigger(Config.DEPLOY_SCRIPT, Config.DEPLOY_LOG):
        return jsonify({"ok": False, "msg": "deploy script not runnable"}), 500

    return jsonify({"ok": True, "msg": "deploy triggered"})