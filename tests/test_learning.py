"""学习空间 API 的最小闭环测试。"""

from __future__ import annotations

import base64
import os
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from app.learning.service import LearningService


def test_learning_plan_and_tasks(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    parsed = client.post(
        "/api/v1/learning/tasks/parse",
        json={"text": "今天学高数2小时，重点看极限\n明天写英语作业40分钟，紧急"},
    )
    assert parsed.status_code == 200
    items = parsed.json()["items"]
    assert len(items) == 2
    assert items[0]["duration_min"] == 120
    assert items[1]["priority"] == "high"

    comma_parsed = client.post(
        "/api/v1/learning/tasks/parse",
        json={"text": "今天复习高数2小时，重点看极限，背英语单词30分钟，明天交物理作业"},
    ).json()["items"]
    assert len(comma_parsed) == 3
    assert comma_parsed[0]["duration_min"] == 120
    assert "重点看极限" in comma_parsed[0]["detail"]
    assert comma_parsed[1]["duration_min"] == 30
    assert "明天" in comma_parsed[2]["detail"]

    connector_parsed = client.post(
        "/api/v1/learning/tasks/parse",
        json={
            "text": (
                "我明天要交高数作业然后背英语单词接着写物理报告再做线代习题"
                "然后准备社团海报最后看Python项目"
            )
        },
    ).json()["items"]
    assert len(connector_parsed) == 6
    assert connector_parsed[-1]["title"] == "看Python项目"

    no_punct = client.post(
        "/api/v1/learning/tasks/parse",
        json={"text": "这周要处理高数作业英语作文物理实验报告线代习题社团海报和Python项目"},
    ).json()["items"]
    assert len(no_punct) == 6

    filler_parsed = client.post(
        "/api/v1/learning/tasks/parse",
        json={"text": "嗯，那个，我明天要交高数作业，然后那个背单词"},
    ).json()["items"]
    assert len(filler_parsed) == 2
    assert all("嗯" not in item["title"] and "那个" not in item["title"] for item in filler_parsed)

    fragment_parsed = client.post(
        "/api/v1/learning/tasks/parse",
        json={"text": "学习一下线性代数还有一个加二"},
    ).json()["items"]
    assert len(fragment_parsed) == 1
    assert fragment_parsed[0]["title"] == "学习一下线性代数"

    missing_model = client.post(
        "/api/v1/learning/tasks/parse",
        json={"text": "明天交高数作业", "use_model": True},
    )
    assert missing_model.status_code == 400

    monkeypatch.setattr(
        LearningService,
        "credentials",
        lambda self, owner_id: {"api_key": "test", "base_url": "http://model", "model": "test"},
    )
    monkeypatch.setattr(
        LearningService,
        "_chat",
        lambda self, credentials, *, messages, max_tokens=1000: (
            '[{"title":"交高数作业","detail":"明天交","duration_min":45,'
            '"priority":"medium","start_date":"2026-11-07","due_date":"2026-11-08"}]'
        ),
    )
    model_parsed = client.post(
        "/api/v1/learning/tasks/parse",
        json={"text": "嗯那个明天交高数作业", "use_model": True},
    ).json()
    assert model_parsed["mode"] == "model"
    assert model_parsed["items"][0]["title"] == "交高数作业"

    created = client.post("/api/v1/learning/tasks", json={"tasks": items})
    assert created.status_code == 200
    assert len(created.json()["items"]) == 2
    tasks = client.get("/api/v1/learning/tasks").json()["items"]
    assert len(tasks) == 2

    exam = client.post(
        "/api/v1/learning/exams",
        json={
            "course_name": "高等数学",
            "exam_date": (date.today() + timedelta(days=2)).isoformat(),
            "start_time": "09:00-11:30",
            "location": "A101",
        },
    )
    assert exam.status_code == 200
    exam_id = exam.json()["id"]
    plan = client.post(f"/api/v1/learning/exams/{exam_id}/plan")
    assert plan.status_code == 200
    assert plan.json()["generated_days"] >= 1
    room = client.get("/api/v1/learning/exam-room").json()
    assert room["next_exam"]["course_name"] == "高等数学"
    assert room["today_tasks"]
    report = client.get("/api/v1/learning/report?days=7").json()
    assert report["tasks"]["pending"] >= 1
    assert report["days"] == 7

    semester = client.put(
        "/api/v1/learning/calendar/settings",
        json={"start_date": "2026-09-07"},
    )
    assert semester.status_code == 200
    assert semester.json()["semester_start"] == "2026-09-07"

    course = client.post(
        "/api/v1/learning/courses",
        json={
            "name": "高等数学",
            "weekday": 1,
            "start_time": "08:00",
            "end_time": "09:40",
            "weeks": "5,10-17",
            "week_parity": "odd",
        },
    ).json()
    assert course["weeks"] == "5,10-17"
    assert course["week_parity"] == "odd"
    material = client.post(
        f"/api/v1/learning/courses/{course['id']}/materials",
        json={"title": "第二章 导数", "content": "导数表示瞬时变化率；可导必连续。"},
    )
    assert material.status_code == 200
    search = client.get(
        f"/api/v1/learning/courses/{course['id']}/materials/search?q=导数"
    ).json()
    assert search["items"]
    assert "导数" in search["items"][0]["snippet"]

    from io import BytesIO

    from docx import Document

    document = Document()
    document.add_paragraph("第三章 积分：定积分表示面积。")
    buffer = BytesIO()
    document.save(buffer)
    uploaded = client.post(
        f"/api/v1/learning/courses/{course['id']}/materials/upload",
        json={
            "filename": "第三章.docx",
            "content_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
        },
    )
    assert uploaded.status_code == 200
    assert client.get(
        f"/api/v1/learning/courses/{course['id']}/materials"
    ).json()["items"][0]["content"].startswith("第三章")

    week = client.get(
        f"/api/v1/learning/calendar/week?start={date.today().isoformat()}"
    )
    assert week.status_code == 200
    assert len(week.json()["days"]) == 7

    deleted = client.delete(f"/api/v1/learning/tasks/{tasks[0]['id']}")
    assert deleted.status_code == 200
    remaining = client.get("/api/v1/learning/tasks").json()["items"]
    assert tasks[0]["id"] not in {item["id"] for item in remaining}


def test_learning_mistake_requires_key_and_is_sanitized(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library = client.post(
        "/api/v1/learning/libraries",
        json={"name": "高等数学上错题本", "subject": "高数"},
    )
    assert library.status_code == 200
    library_id = library.json()["id"]

    # 没有自己的 Key，必须拒绝识别，不能返回 mock 题。
    rejected = client.post(
        "/api/v1/learning/questions",
        json={"library_id": library_id, "text": "求函数 f(x)=x^2-4x+3 的零点。"},
    )
    assert rejected.status_code == 400
    assert "模型设置" in rejected.json()["detail"]["message"] or "测试连接" in rejected.json()["detail"]["message"]

    if os.name != "nt":
        pytest.skip("DPAPI 仅在 Windows 测试环境验证")
    saved = client.post(
        "/api/v1/learning/settings/vision",
        json={
            "api_key": "sk-test-12345678",
            "base_url": "https://example.com/v1",
            "model": "qwen-vl-max",
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["configured"] is True
    assert body["ready"] is False
    assert "sk-test-12345678" not in str(body)
    assert body["key_masked"].endswith("5678")
    assert body["key_fingerprint"]
    # 已保存后不能覆盖，必须删除后重新录入。
    overwrite = client.post(
        "/api/v1/learning/settings/vision",
        json={
            "api_key": "sk-new-99999999",
            "base_url": "https://example.com/v1",
            "model": "deepseek-flash",
        },
    )
    assert overwrite.status_code == 400
    assert "删除" in overwrite.json()["detail"]["message"]

    monkeypatch.setattr(
        LearningService,
        "_http_text_extraction",
        lambda self, text, credentials: {
            "question_text": text,
            "options": [],
            "reference_answer": "零点为 1 和 3。",
            "analysis": "因式分解得到 (x-1)(x-3)=0。",
            "knowledge_points": "二次函数",
            "difficulty": "中等",
        },
    )
    monkeypatch.setattr(
        LearningService,
        "_chat",
        lambda self, credentials, *, messages, max_tokens=1000: (
            '{"correctness":"correct","score":1,'
            '"feedback":"结论正确。","steps":[{"step":"因式分解","status":"done","comment":"正确"}]}'
        ),
    )
    profiles = client.get("/api/v1/learning/model-profiles").json()["items"]
    assert len(profiles) == 1
    profile_id = profiles[0]["id"]
    tested = client.post(f"/api/v1/learning/model-profiles/{profile_id}/test")
    assert tested.status_code == 200
    assert tested.json()["profile"]["status"] == "ok"
    activated = client.post(f"/api/v1/learning/model-profiles/{profile_id}/activate")
    assert activated.status_code == 200
    assert activated.json()["is_active"] is True

    created = client.post(
        "/api/v1/learning/questions",
        json={"library_id": library_id, "text": "求函数 f(x)=x^2-4x+3 的零点。"},
    )
    assert created.status_code == 200
    question_id = created.json()["id"]
    assert "reference_answer" not in created.json()

    practice = client.get(f"/api/v1/learning/questions/{question_id}")
    assert practice.status_code == 200
    assert "reference_answer" not in practice.json()
    assert "analysis" not in practice.json()
    solution = client.get(f"/api/v1/learning/questions/{question_id}/solution")
    assert solution.status_code == 200
    assert "reference_answer" in solution.json()
    assert "analysis" in solution.json()

    attempt = client.post(
        f"/api/v1/learning/questions/{question_id}/attempts",
        json={"answer": "零点为 1 和 3"},
    )
    assert attempt.status_code == 200
    assert attempt.json()["feedback"]["correctness"] == "correct"
    assert "reference_answer" in attempt.json()["feedback"]
    assert attempt.json()["review"]["interval_days"] == 3
    review = client.get("/api/v1/learning/review").json()
    assert review["summary"]["total"] == 1
    assert review["summary"]["reviewed"] == 1
    report = client.get("/api/v1/learning/report?days=7").json()
    assert report["question_count"] == 1
    teachback = client.post(
        f"/api/v1/learning/questions/{question_id}/teachback",
        json={"explanation": "先因式分解，再令每个因子为 0。"},
    )
    assert teachback.status_code == 200
    assert "feedback" in teachback.json()

    deleted = client.delete(f"/api/v1/learning/questions/{question_id}")
    assert deleted.status_code == 200
    active = client.get(f"/api/v1/learning/questions?library_id={library_id}").json()["items"]
    assert question_id not in {item["id"] for item in active}
    trash = client.get("/api/v1/learning/questions/trash").json()["items"]
    assert question_id in {item["id"] for item in trash}
    restored = client.post(f"/api/v1/learning/questions/{question_id}/restore")
    assert restored.status_code == 200
    assert "reference_answer" not in restored.json()["item"]
    active = client.get(f"/api/v1/learning/questions?library_id={library_id}").json()["items"]
    assert question_id in {item["id"] for item in active}
    client.delete(f"/api/v1/learning/questions/{question_id}")
    assert client.delete(f"/api/v1/learning/questions/{question_id}/permanent").status_code == 200

    assert client.delete(f"/api/v1/learning/libraries/{library_id}").status_code == 200
    library_list = client.get("/api/v1/learning/libraries").json()["items"]
    assert library_id not in {item["id"] for item in library_list}
    library_trash = client.get("/api/v1/learning/libraries/trash").json()["items"]
    assert library_id in {item["id"] for item in library_trash}
    assert client.post(f"/api/v1/learning/libraries/{library_id}/restore").status_code == 200
    assert library_id in {
        item["id"] for item in client.get("/api/v1/learning/libraries").json()["items"]
    }
    client.delete(f"/api/v1/learning/libraries/{library_id}")
    assert client.delete(f"/api/v1/learning/libraries/{library_id}/permanent").status_code == 200

    monkeypatch.setattr(
        LearningService,
        "_chat",
        lambda self, credentials, *, messages, max_tokens=1000: (
            '[{"title":"习题 1-5","course":"高等数学",'
            '"due_date":"2026-11-20","detail":"P45 第 1-5 题"}]'
        ),
    )
    extracted = client.post(
        "/api/v1/learning/assignments/extract",
        json={"text": "高数 P45 第 1-5 题，11月20日交"},
    )
    assert extracted.status_code == 200
    assert extracted.json()["items"][0]["title"] == "习题 1-5"

    deleted = client.delete("/api/v1/learning/settings/vision")
    assert deleted.status_code == 200
    assert client.get("/api/v1/learning/settings/vision").json()["configured"] is False


def test_learning_focus_start_stop(client: TestClient) -> None:
    started = client.post(
        "/api/v1/learning/focus/start",
        json={"planned_min": 25},
    )
    assert started.status_code == 200
    focus_id = started.json()["item"]["id"]

    stopped = client.post(
        f"/api/v1/learning/focus/{focus_id}/stop",
        json={"completed": True, "elapsed_seconds": 90},
    )
    assert stopped.status_code == 200
    assert stopped.json()["item"]["ended_at"]
    assert stopped.json()["item"]["actual_min"] == 2
    assert "encouragement" in stopped.json()
