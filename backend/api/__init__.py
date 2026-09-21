"""API 蓝图注册表。

新增一组接口 = 在这里登记一个模块，无需改动 app.py。
"""
from __future__ import annotations

from . import auth, components, deploy, records, stats, stock

BLUEPRINTS = (
    auth.bp,
    components.bp,
    stock.bp,
    records.bp,
    stats.bp,
    deploy.bp,
)


def register(app):
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)
    return app