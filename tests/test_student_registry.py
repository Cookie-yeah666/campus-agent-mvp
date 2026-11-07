"""学生名册与真实学号接入的测试。"""

from __future__ import annotations

from pathlib import Path

from app.student_registry import StudentRegistry, mask_phone, normalize_student_id


def make_registry(tmp_path: Path) -> StudentRegistry:
    """创建一个带一条计科院学生记录的临时名册。"""
    registry = StudentRegistry(tmp_path / "registry" / "students.db")
    registry.upsert_batch(
        [
            {
                "student_id": "2527405999",
                "name": "测试学生",
                "major": "计算机科学与技术",
                "class_name": "计25测试班",
                "phone": "13800138000",
                "gender": "女",
                "dorm_building": "本9",
                "dorm_room": "103",
                "campus": None,
                "status": "active",
                "notes": None,
                "source_row": 2,
            }
        ],
        source_file="students_2025_cs.xlsx",
        source_sha256="abc",
        college="计算机科学与技术学院",
        cohort="2025",
    )
    return registry


def test_normalize_and_mask_phone() -> None:
    assert normalize_student_id("2527405999") == "2527405999"
    assert normalize_student_id(2527405999.0) == "2527405999"
    assert normalize_student_id("2527405999.0") == "2527405999"
    assert normalize_student_id("252740500") is None
    assert mask_phone("13800138000") == "138****8000"
    assert mask_phone("复读") is None


def test_registry_stats_and_public_student(tmp_path: Path) -> None:
    registry = make_registry(tmp_path)
    stats = registry.stats()
    assert stats["total"] == 1
    assert stats["colleges"] == 1
    assert stats["cohorts"] == 1
    assert stats["classes"] == 1
    assert stats["latest_batch"]["inserted"] == 1

    row = registry.lookup("2527405999")
    assert row is not None
    public = registry.public_student(row)
    assert public["name"] == "测试学生"
    assert public["phone_masked"] == "138****8000"
    assert "phone" not in public
    assert public["dorm"] == "本9-103"


def test_registry_search_filters(tmp_path: Path) -> None:
    registry = make_registry(tmp_path)
    items, total = registry.search(major="计算机科学与技术", query="测试")
    assert total == 1
    assert items[0]["student_id"] == "2527405999"

    items, total = registry.search(college="商学院")
    assert total == 0
    assert items == []


def test_duplicate_import_updates_not_duplicates(tmp_path: Path) -> None:
    registry = make_registry(tmp_path)
    registry.upsert_batch(
        [
            {
                "student_id": "2527405999",
                "name": "测试学生",
                "major": "计算机科学与技术",
                "class_name": "计25测试班",
                "phone": "13800138000",
                "gender": "女",
                "dorm_building": "本9",
                "dorm_room": "103",
                "campus": None,
                "status": "active",
                "notes": "更新",
                "source_row": 2,
            }
        ],
        source_file="students_2025_cs.xlsx",
        source_sha256="abc",
        college="计算机科学与技术学院",
        cohort="2025",
    )
    stats = registry.stats()
    assert stats["total"] == 1
    assert stats["latest_batch"]["updated"] == 1


def test_student_api_endpoints(client) -> None:
    """学生库统计/列表/404 与系统总览。"""
    stats = client.get("/api/v1/students/stats")
    assert stats.status_code == 200
    assert stats.json()["total"] == 0

    listing = client.get("/api/v1/students", params={"limit": 10})
    assert listing.status_code == 200
    assert listing.json()["items"] == []

    missing = client.get("/api/v1/students/2527405999")
    assert missing.status_code == 404

    overview = client.get("/api/v1/system/overview")
    assert overview.status_code == 200
    assert "student_registry" in overview.json()


def test_real_roster_student_enters_card_flow(container, send) -> None:
    """名册里的真实学号也能走通补办，且确认卡带上姓名/班级。"""
    container.student_registry.upsert_batch(
        [
            {
                "student_id": "2527405999",
                "name": "测试学生",
                "major": "计算机科学与技术",
                "class_name": "计25测试班",
                "phone": "13800138000",
                "gender": "女",
                "dorm_building": "本9",
                "dorm_room": "103",
                "campus": None,
                "status": "active",
                "notes": None,
                "source_row": 2,
            }
        ],
        source_file="students_2025_cs.xlsx",
        source_sha256="abc",
        college="计算机科学与技术学院",
        cohort="2025",
    )

    first = send("我要补办校园卡")
    assert first.workorder is not None
    second = send("2527405999，天赐庄", session_id=first.session_id)
    assert second.workorder is not None
    assert second.workorder.status.value == "awaiting_confirm"
    profile = second.workorder.user_inputs.get("student_profile") or {}
    assert profile.get("name") == "测试学生"
    assert profile.get("class_name") == "计25测试班"
    assert profile.get("source") == "roster"
