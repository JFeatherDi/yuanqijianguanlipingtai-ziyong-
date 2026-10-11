"""单台设备数据模型回归测试。"""
import os
import sys
import tempfile
import io

from openpyxl import Workbook, load_workbook

DB_PATH = os.path.join(tempfile.gettempdir(), "individual_devices_test.db")
for suffix in ("", "-wal", "-shm"):
    try:
        os.remove(DB_PATH + suffix)
    except FileNotFoundError:
        pass

os.environ["APP_DB_PATH"] = DB_PATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app import create_app  # noqa: E402
from backend.config import Config  # noqa: E402


app = create_app()
client = app.test_client()

with client.session_transaction() as session:
    session["user"] = Config.USERNAME
    session["role"] = "superadmin"


def create(asset_no):
    response = client.post(
        "/api/components",
        json={
            "name": "同型号示波器",
            "asset_no": asset_no,
            "spec": "OSC-1",
            "manual_status": "available",
        },
    )
    assert response.status_code == 200, response.get_json()
    return response.get_json()["id"]


first = create("UNIT-001")
second = create("UNIT-002")
rows = client.get("/api/components").get_json()["data"]
assert len(rows) == 2
assert all(row["stock"] == 1 for row in rows)

borrow = client.post(
    "/api/stock/out",
    json={"id": first, "applicant": "张三", "contact": "13800000000"},
)
assert borrow.status_code == 200, borrow.get_json()
rows = client.get("/api/components").get_json()["data"]
assert next(row for row in rows if row["id"] == first)["equipment_status"] == "borrowed"
assert next(row for row in rows if row["id"] == second)["equipment_status"] == "available"

position = client.get(
    "/api/custody/positions", query_string={"component_id": first}
).get_json()["data"][0]
transfer = client.post(
    "/api/custody/transfer",
    json={"position_id": position["id"], "holder": "李四", "contact": "13900000000"},
)
assert transfer.status_code == 200, transfer.get_json()
position = client.get(
    "/api/custody/positions", query_string={"component_id": first}
).get_json()["data"][0]
transferred_chain = next(
    row for row in client.get("/api/custody").get_json()["data"]
    if row["component_id"] == first
)
assert float(transferred_chain["holding_total"]) == 1
assert [event["kind"] for event in transferred_chain["events"]] == ["out", "transfer"]
assert transferred_chain["events"][1]["handler"] == "张三"
returned = client.post("/api/custody/return", json={"position_id": position["id"]})
assert returned.status_code == 200, returned.get_json()

# 记录页直接返回独立的借用、转借、归还行；转借经手人为上一位借用人。
record_chain = next(
    row for row in client.get("/api/custody").get_json()["data"]
    if row["component_id"] == first
)
assert float(record_chain["holding_total"]) == 0
assert [event["kind"] for event in record_chain["events"]] == ["out", "transfer", "return"]
transfer_event = next(event for event in record_chain["events"] if event["kind"] == "transfer")
assert transfer_event["holder"] == "李四"
assert transfer_event["handler"] == "张三"
return_event = next(event for event in record_chain["events"] if event["kind"] == "return")
assert return_event["contact"] == "13900000000"

template = client.get("/api/records/template")
assert template.status_code == 200
workbook = load_workbook(filename=__import__("io").BytesIO(template.data), read_only=True)
headers = [cell.value for cell in next(workbook.active.iter_rows())]
workbook.close()
assert headers == [
    "设备名称", "设备固定资产编号", "分类", "设备型号", "单位",
    "位置", "设备负责人", "设备状态", "备注",
]

upload_book = Workbook()
upload_sheet = upload_book.active
upload_sheet.append(headers)
upload_sheet.append(["同型号相机", "CAM-001", "视觉设备", "CAM-X", "台", "A区", "王老师", "可借用", ""])
upload_sheet.append(["同型号相机", "CAM-002", "视觉设备", "CAM-X", "台", "A区", "王老师", "维护中", ""])
upload_data = io.BytesIO()
upload_book.save(upload_data)
upload_data.seek(0)
imported = client.post(
    "/api/records/import",
    data={"file": (upload_data, "devices.xlsx")},
    content_type="multipart/form-data",
)
assert imported.status_code == 200, imported.get_json()
rows = client.get("/api/components").get_json()["data"]
assert len(rows) == 4
assert len([row for row in rows if row["name"] == "同型号相机"]) == 2
overview = client.get("/api/stats/overview").get_json()["data"]
assert overview["total_count"] == 4

# 无借还历史的设备可以整批删除。
bulk_first = create("BULK-001")
bulk_second = create("BULK-002")
deleted = client.post(
    "/api/components/bulk-delete",
    json={"ids": [bulk_first, bulk_second]},
)
assert deleted.status_code == 200, deleted.get_json()
assert deleted.get_json()["deleted"] == 2
remaining_ids = {row["id"] for row in client.get("/api/components").get_json()["data"]}
assert bulk_first not in remaining_ids
assert bulk_second not in remaining_ids

# 任一设备存在借还历史时整批拒绝，其他无历史设备也必须保留。
clean = create("BULK-KEEP")
protected_delete = client.post(
    "/api/components/bulk-delete",
    json={"ids": [first, clean]},
)
assert protected_delete.status_code == 400, protected_delete.get_json()
remaining_ids = {row["id"] for row in client.get("/api/components").get_json()["data"]}
assert first in remaining_ids
assert clean in remaining_ids

# 总管理员可批量删除已全部归还的借还链。
returned_chain = next(
    row for row in client.get("/api/custody").get_json()["data"] if row["component_id"] == first
)
deleted_records = client.post(
    "/api/custody/bulk-delete",
    json={"ids": [returned_chain["id"]]},
)
assert deleted_records.status_code == 200, deleted_records.get_json()
assert deleted_records.get_json()["deleted"] == 1
assert all(
    row["id"] != returned_chain["id"]
    for row in client.get("/api/custody").get_json()["data"]
)

# 尚未归还的记录必须保留。
active_borrow = client.post(
    "/api/stock/out",
    json={"id": second, "applicant": "未归还测试", "contact": "13800000001"},
)
assert active_borrow.status_code == 200, active_borrow.get_json()
active_chain = next(
    row for row in client.get("/api/custody").get_json()["data"] if row["component_id"] == second
)
active_delete = client.post(
    "/api/custody/bulk-delete",
    json={"ids": [active_chain["id"]]},
)
assert active_delete.status_code == 400, active_delete.get_json()
assert any(
    row["id"] == active_chain["id"]
    for row in client.get("/api/custody").get_json()["data"]
)

# 管理员会话返回姓名，供借用表单自动填写借用人。
student_missing_phone = client.post(
    "/api/users",
    json={
        "username": "20269991",
        "full_name": "缺少手机号学生",
        "user_type": "student",
        "mentor": "测试导师",
    },
)
assert student_missing_phone.status_code == 400, student_missing_phone.get_json()
student_created = client.post(
    "/api/users",
    json={
        "username": "20269992",
        "full_name": "手机号学生",
        "phone": "13900009992",
        "user_type": "student",
        "mentor": "测试导师",
    },
)
assert student_created.status_code == 201, student_created.get_json()
student_id = student_created.get_json()["id"]
student_row = next(row for row in client.get("/api/users").get_json()["data"] if row["id"] == student_id)
assert student_row["phone"] == "13900009992"
student_phone_updated = client.put(
    f"/api/users/{student_id}/phone",
    json={"phone": "13700009992"},
)
assert student_phone_updated.status_code == 200, student_phone_updated.get_json()

user_template = client.get("/api/users/template")
assert user_template.status_code == 200
user_template_book = load_workbook(io.BytesIO(user_template.data), read_only=True)
user_headers = [cell.value for cell in next(user_template_book.active.iter_rows())]
user_template_book.close()
assert user_headers == ["用户类型", "姓名", "账号", "手机号", "所属导师", "权限角色"]

user_import_book = Workbook()
user_import_sheet = user_import_book.active
user_import_sheet.append(user_headers)
user_import_sheet.append(["学生", "导入手机号学生", "20269993", "13600009993", "测试导师", "普通用户"])
user_import_data = io.BytesIO()
user_import_book.save(user_import_data)
user_import_data.seek(0)
user_imported = client.post(
    "/api/users/import",
    data={"file": (user_import_data, "users.xlsx")},
    content_type="multipart/form-data",
)
assert user_imported.status_code == 200, user_imported.get_json()
imported_student = next(
    row for row in client.get("/api/users").get_json()["data"] if row["username"] == "20269993"
)
assert imported_student["phone"] == "13600009993"

# 总管理员账号固定为 SWUST，姓名与手机号可以在用户管理页持久化维护。
assert Config.USERNAME == "SWUST"
admin_profile_response = client.get("/api/users/superadmin")
assert admin_profile_response.status_code == 200, admin_profile_response.get_json()
assert admin_profile_response.get_json()["data"]["username"] == "SWUST"
invalid_admin_profile = client.put(
    "/api/users/superadmin",
    json={"full_name": "系统负责人", "phone": "123"},
)
assert invalid_admin_profile.status_code == 400, invalid_admin_profile.get_json()
saved_admin_profile = client.put(
    "/api/users/superadmin",
    json={"full_name": "系统负责人", "phone": "13500000000"},
)
assert saved_admin_profile.status_code == 200, saved_admin_profile.get_json()
admin_session = client.get("/api/auth/me").get_json()
assert admin_session["user"] == "SWUST"
assert admin_session["full_name"] == "系统负责人"
assert admin_session["phone"] == "13500000000"
admin_directory = client.get("/api/users/directory").get_json()["data"]
assert admin_directory[0] == {
    "username": "SWUST",
    "full_name": "系统负责人",
    "phone": "13500000000",
}

manager_created = client.post(
    "/api/users",
    json={
        "username": "13800009999",
        "full_name": "自动填写管理员",
        "user_type": "teacher",
        "role": "manager",
    },
)
assert manager_created.status_code == 201, manager_created.get_json()
manager_id = manager_created.get_json()["id"]
with client.session_transaction() as session:
    session["user"] = "13800009999"
    session["role"] = "manager"
    session["uid"] = manager_id
    session["ver"] = 0
manager_session = client.get("/api/auth/me")
assert manager_session.status_code == 200, manager_session.get_json()
assert manager_session.get_json()["full_name"] == "自动填写管理员"
assert manager_session.get_json()["phone"] == "13800009999"
directory = client.get("/api/users/directory")
assert directory.status_code == 200, directory.get_json()
directory_manager = next(
    row for row in directory.get_json()["data"] if row["username"] == "13800009999"
)
assert directory_manager["full_name"] == "自动填写管理员"
assert directory_manager["phone"] == "13800009999"

# 当前账号先验证原密码，再修改自己的密码；修改后当前会话继续有效。
wrong_password = client.post(
    "/api/auth/password/verify", json={"current_password": "wrong-password"}
)
assert wrong_password.status_code == 400, wrong_password.get_json()
verified_password = client.post(
    "/api/auth/password/verify", json={"current_password": "swust9999"}
)
assert verified_password.status_code == 200, verified_password.get_json()
mismatched_password = client.put(
    "/api/auth/password",
    json={"new_password": "manager-new-password", "confirm_password": "different"},
)
assert mismatched_password.status_code == 400, mismatched_password.get_json()
changed_password = client.put(
    "/api/auth/password",
    json={
        "new_password": "manager-new-password",
        "confirm_password": "manager-new-password",
    },
)
assert changed_password.status_code == 200, changed_password.get_json()
assert client.get("/api/auth/me").status_code == 200
assert client.post(
    "/api/auth/password/verify", json={"current_password": "swust9999"}
).status_code == 400
assert client.post(
    "/api/auth/password/verify", json={"current_password": "manager-new-password"}
).status_code == 200

# 总管理员首次使用环境变量密码，修改后使用数据库中的安全哈希。
with client.session_transaction() as session:
    session.clear()
    session["user"] = Config.USERNAME
    session["role"] = "superadmin"
assert client.post(
    "/api/auth/password/verify", json={"current_password": Config.PASSWORD}
).status_code == 200
superadmin_changed = client.put(
    "/api/auth/password",
    json={
        "new_password": "superadmin-new-password",
        "confirm_password": "superadmin-new-password",
    },
)
assert superadmin_changed.status_code == 200, superadmin_changed.get_json()
assert client.post(
    "/api/auth/password/verify", json={"current_password": Config.PASSWORD}
).status_code == 400
assert client.post(
    "/api/auth/password/verify", json={"current_password": "superadmin-new-password"}
).status_code == 200

print("单台设备模型测试通过")
