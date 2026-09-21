"""后端接口冒烟测试：登录 -> 建器件 -> 出入库 -> 统计 -> 导入/导出。

用法：python backend/tests/smoke.py  （跑完会删除临时数据库）
"""
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

TMP_DB = os.path.join(tempfile.gettempdir(), "components_smoke.db")
for suffix in ("", "-wal", "-shm"):
    if os.path.exists(TMP_DB + suffix):
        os.remove(TMP_DB + suffix)

os.environ["APP_DB_PATH"] = TMP_DB

from backend.app import create_app  # noqa: E402

app = create_app()
app.config["TESTING"] = True
client = app.test_client()

failures = []


def check(label, condition, detail=""):
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {label} {detail}")
    if not condition:
        failures.append(label)


# --- 未登录访问应被拦截 ---
check("未登录访问被拦截", client.get("/api/components").status_code == 401)

# --- 登录 ---
check("错误密码被拒绝", client.post("/api/auth/login", json={"username": "x", "password": "y"}).status_code == 401)
login = client.post("/api/auth/login", json={"username": "IOTAT", "password": "swust350351"})
check("登录成功", login.status_code == 200 and login.get_json()["ok"])
check("获取当前用户", client.get("/api/auth/me").get_json()["user"] == "IOTAT")

# --- 新建器件 ---
created = client.post(
    "/api/components",
    json={
        "name": "电阻10K", "category": "电阻", "spec": "0805",
        "unit": "个", "location": "柜A-1", "stock": 100,
        "threshold": 20, "remark": "测试",
    },
)
check("新建器件", created.status_code == 200, created.get_json())
component_id = created.get_json()["id"]

check("重名校验", client.post("/api/components", json={"name": "电阻10K", "spec": "0805"}).status_code == 400)
check("空名称校验", client.post("/api/components", json={"name": "  "}).status_code == 400)

# --- 入库 / 出库 ---
check("入库", client.post("/api/stock/in", json={"id": component_id, "qty": 50}).get_json()["stock"] == 150)

out = client.post("/api/stock/out", json={"id": component_id, "qty": 30})
check("出库", out.status_code == 200 and out.get_json()["stock"] == 120, out.get_json())

over = client.post("/api/stock/out", json={"id": component_id, "qty": 99999})
check("超额出库被拒绝", over.status_code == 400, over.get_json().get("msg"))

check("数量为 0 被拒绝", client.post("/api/stock/in", json={"id": component_id, "qty": 0}).status_code == 400)
check("未知器件出库 404", client.post("/api/stock/out", json={"id": 99999, "qty": 1}).status_code == 404)

# --- 列表 / 过滤 / 选项 ---
rows = client.get("/api/components").get_json()["data"]
check("列表返回", len(rows) == 1, rows)
check("关键字搜索", len(client.get("/api/components?q=0805").get_json()["data"]) == 1)
check("搜索无结果", len(client.get("/api/components?q=不存在").get_json()["data"]) == 0)
check("分类筛选", len(client.get("/api/components?category=电阻").get_json()["data"]) == 1)

# --- 更新 ---
check("更新器件", client.put(f"/api/components/{component_id}", json={"name": "电阻10K", "threshold": 500}).status_code == 200)
check("低库存筛选生效", len(client.get("/api/components?low=1").get_json()["data"]) == 1)

# --- 统计 ---
overview = client.get("/api/stats/overview").get_json()["data"]
check("概览指标", overview["kinds"] == 1 and overview["low_count"] == 1, overview)

categories = client.get("/api/stats/categories").get_json()
check("分类分布", categories["data"][0]["stock"] == 120, categories["data"])

series = client.get("/api/stats/flow?days=7").get_json()["data"]
check("趋势为 7 天", len(series) == 7, f"len={len(series)}")
check("趋势有出入库数据", series[-1]["inbound"] == 150 and series[-1]["outbound"] == 30, series[-1])

# --- 流水 ---
records = client.get("/api/records").get_json()
check("流水条数", records["total"] == 3, f"total={records['total']}")
check("流水类型过滤", client.get("/api/records?type=out").get_json()["total"] == 1)

# --- 导入 ---
csv_body = "名称,分类,规格,单位,位置,库存,预警值,备注\n电容100uF,电容,16V,个,柜B-2,50,10,导入\n,,,,\n"
upload = client.post(
    "/api/records/import",
    data={"file": (io.BytesIO(csv_body.encode("utf-8-sig")), "batch.csv")},
    content_type="multipart/form-data",
)
check("CSV 导入", upload.get_json().get("imported") == 1, upload.get_json())
check("导入后器件数", len(client.get("/api/components").get_json()["data"]) == 2)

again = client.post(
    "/api/records/import",
    data={"file": (io.BytesIO(csv_body.encode("utf-8-sig")), "batch.csv")},
    content_type="multipart/form-data",
)
check("重复导入累加库存", again.get_json().get("imported") == 1, again.get_json())
stock_of_cap = [r for r in client.get("/api/components").get_json()["data"] if r["name"] == "电容100uF"][0]["stock"]
check("同名同规格累加", stock_of_cap == 100, f"stock={stock_of_cap}")

# --- 回归：分类必须合并成一行 ---
# 曾经写成 GROUP BY name，被 SQLite 解析成 components.name（器件名），
# 导致同一分类按器件拆成多行、分类名重复出现。
grouped = client.get("/api/stats/categories").get_json()["data"]
names = [row["name"] for row in grouped]
check("分类名不重复", len(names) == len(set(names)), names)
check("分类数与器件分类一致", len(grouped) == 2, grouped)
check("分类 kinds 计数正确", sorted(row["kinds"] for row in grouped) == [1, 1], grouped)

check("不支持的后缀报错", client.post(
    "/api/records/import",
    data={"file": (io.BytesIO(b"x"), "bad.txt")},
    content_type="multipart/form-data",
).status_code == 400)

# --- 导出 / 模板 ---
export = client.get("/api/records/export")
check("导出 CSV", export.status_code == 200 and b"\xef\xbb\xbf" in export.data[:3])
check("模板下载", client.get("/api/records/template").status_code == 200)

# --- 删除 ---
check("删除器件", client.delete(f"/api/components/{component_id}").status_code == 200)
check("删除后流水联动清理", client.get("/api/records").get_json()["total"] == 2)

# --- 登出 ---
check("登出", client.post("/api/auth/logout").status_code == 200)
check("登出后受限", client.get("/api/components").status_code == 401)

# --- 缓存策略与 SPA 回退 ---
check("接口响应不被缓存", client.get("/api/health").headers.get("Cache-Control") == "no-store")
check("未知接口返回 404 JSON", client.get("/api/nope").status_code == 404)

from backend.config import Config  # noqa: E402

if os.path.isfile(os.path.join(Config.STATIC_DIST, "index.html")):
    index = client.get("/")
    check("index.html 回源校验", "no-cache" in (index.headers.get("Cache-Control") or ""))
    # 发版后旧入口文件引用的是已被删除的哈希资源，必须每次都重新校验
    check("首页返回 HTML", "text/html" in (index.headers.get("Content-Type") or ""))

    deep = client.get("/some/deep/route")
    check("SPA 深层路由回退 index.html", deep.status_code == 200 and b"<div id=\"app\">" in deep.data)

    asset = next(
        (name for name in os.listdir(os.path.join(Config.STATIC_DIST, "assets")) if name.endswith(".js")),
        None,
    ) if os.path.isdir(os.path.join(Config.STATIC_DIST, "assets")) else None
    if asset:
        cached = client.get(f"/assets/{asset}")
        check("哈希资源长期强缓存", "immutable" in (cached.headers.get("Cache-Control") or ""))

    check("缺失静态资源 404", client.get("/assets/does-not-exist.js").status_code == 404)

for suffix in ("", "-wal", "-shm"):
    if os.path.exists(TMP_DB + suffix):
        os.remove(TMP_DB + suffix)

print()
if failures:
    print(f"失败 {len(failures)} 项: {failures}")
    sys.exit(1)
print("全部通过")