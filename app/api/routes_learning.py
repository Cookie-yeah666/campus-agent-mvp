"""学习空间 API：专注、任务清单、错题本、日历与课程表。"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.auth.models import AuthUser
from app.deps import get_container

router = APIRouter(prefix="/learning", tags=["学习空间"])


def _owner(user: AuthUser) -> str:
    if user.role not in {"student", "admin"}:
        raise HTTPException(
            status_code=403,
            detail={"code": "learning_forbidden", "message": "学习空间仅学生/管理员可用"},
        )
    return user.student_id or user.username


class LibraryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    subject: str = Field(default="", max_length=30)


class TaskDraft(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    detail: str = ""
    duration_min: int = Field(default=60, ge=5, le=600)
    priority: Literal["high", "medium", "low", "none"] = "none"
    start_date: str | None = None
    due_date: str | None = None
    remind_at: str | None = None


class TaskBatch(BaseModel):
    tasks: list[TaskDraft]


class TaskPatch(BaseModel):
    title: str | None = None
    detail: str | None = None
    duration_min: int | None = Field(default=None, ge=5, le=600)
    priority: Literal["high", "medium", "low", "none"] | None = None
    start_date: str | None = None
    due_date: str | None = None
    remind_at: str | None = None
    status: Literal["pending", "completed"] | None = None
    actual_min: int | None = Field(default=None, ge=0)


class PlanRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    use_model: bool = False


class FocusStart(BaseModel):
    task_id: str | None = None
    planned_min: int = Field(default=25, ge=1, le=180)


class FocusStop(BaseModel):
    completed: bool = True
    elapsed_seconds: int | None = Field(default=None, ge=0, le=86400)


class QuestionCreate(BaseModel):
    library_id: str
    text: str | None = None
    image_base64: str | None = None
    max_tokens: int | None = Field(default=None, ge=512, le=32768)


class AttemptCreate(BaseModel):
    answer: str = Field(min_length=0, max_length=8000)


class CourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    teacher: str = ""
    weekday: int = Field(default=1, ge=1, le=7)
    start_time: str = "08:00"
    end_time: str = "09:40"
    location: str = ""
    weeks: str = ""
    week_parity: str = "all"
    assignment: str = ""


class ModelProfileCreate(BaseModel):
    name: str = Field(default="", max_length=60)
    provider: str = Field(default="custom", max_length=30)
    model: str = Field(min_length=1, max_length=80)
    base_url: str = Field(min_length=1, max_length=300)
    official_url: str = Field(default="", max_length=300)
    note: str = Field(default="", max_length=300)
    api_key: str = Field(min_length=1, max_length=300)


class ModelProfileUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=60)
    provider: str | None = Field(default=None, max_length=30)
    model: str | None = Field(default=None, max_length=80)
    base_url: str | None = Field(default=None, max_length=300)
    official_url: str | None = Field(default=None, max_length=300)
    note: str | None = Field(default=None, max_length=300)


class CourseImport(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


class MaterialCreate(BaseModel):
    title: str = Field(default="课程资料", max_length=120)
    content: str = Field(min_length=1, max_length=20000)


class MaterialUpload(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    content_base64: str = Field(min_length=1)


class ExamCreate(BaseModel):
    course_name: str = Field(min_length=1, max_length=60)
    exam_date: str
    start_time: str = ""
    location: str = ""
    note: str = ""


class VisionSettings(BaseModel):
    api_key: str = ""
    base_url: str | None = None
    model: str | None = None


@router.get("/overview", summary="学习空间概览")
def overview(user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    container = get_container()
    active = container.learning_store.active_focus(owner)
    tasks = container.learning_store.list_tasks(owner)
    libraries = container.learning_store.list_libraries(owner)
    hour = __import__("datetime").datetime.now().hour
    greeting = "早上好，今天先做一件最重要的事。" if 4 <= hour < 11 else "今天想先推进哪一项？"
    if hour >= 23 or hour < 4:
        greeting = "已经很晚了，完成这一小段就去休息吧。"
    return {
        "greeting": greeting,
        "vision_mode": container.learning.vision_mode(owner),
        "vision_configured": container.learning.active_profile(owner) is not None,
        "vision_ready": container.learning.credentials(owner) is not None,
        "vision_model": container.learning.vision_model(owner),
        "today_focus_min": container.learning_store.focus_today_minutes(owner),
        "pending_tasks": sum(1 for task in tasks if task["status"] == "pending"),
        "libraries": len(libraries),
        "active_focus": active,
        "tasks": [container.learning.public_task(task) for task in tasks],
        "recent_focus": container.learning_store.recent_focus(owner, 6),
    }


@router.get("/tasks", summary="任务清单")
def list_tasks(
    on_date: str | None = None,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    container = get_container()
    tasks = container.learning_store.list_tasks(owner, on_date)
    return {"items": [container.learning.public_task(task) for task in tasks]}


@router.post("/tasks/parse", summary="自然语言解析任务")
def parse_tasks(payload: PlanRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    container = get_container()
    if payload.use_model:
        try:
            tasks = container.learning.parse_plan_with_model(owner, payload.text)
            return {"items": tasks, "mode": "model"}
        except ValueError as exc:
            raise HTTPException(
                400,
                detail={"code": "plan_model_failed", "message": str(exc)},
            ) from exc
    tasks = container.learning.parse_plan(payload.text)
    return {"items": tasks, "mode": "rule"}


@router.post("/tasks", summary="导入任务清单")
def create_tasks(payload: TaskBatch, user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    container = get_container()
    tasks = container.learning_store.create_tasks(
        owner, [task.model_dump() for task in payload.tasks]
    )
    return {"items": [container.learning.public_task(task) for task in tasks]}


@router.patch("/tasks/{task_id}", summary="更新任务")
def update_task(
    task_id: str,
    payload: TaskPatch,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    container = get_container()
    task = container.learning_store.update_task(
        task_id, owner, payload.model_dump(exclude_none=True)
    )
    if task is None:
        raise HTTPException(404, detail={"code": "task_not_found", "message": "任务不存在"})
    return container.learning.public_task(task)


@router.delete("/tasks/{task_id}", summary="删除任务")
def delete_task(task_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    if not get_container().learning_store.delete_task(task_id, owner):
        raise HTTPException(404, detail={"code": "task_not_found", "message": "任务不存在"})
    return {"deleted": True}


@router.get("/focus/active", summary="当前专注")
def active_focus(user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    return {"item": get_container().learning_store.active_focus(owner)}


@router.post("/focus/start", summary="开始专注")
def start_focus(payload: FocusStart, user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    container = get_container()
    current = container.learning_store.active_focus(owner)
    if current:
        return {"item": current, "reused": True}
    if payload.task_id and container.learning_store.get_task(payload.task_id, owner) is None:
        raise HTTPException(404, detail={"code": "task_not_found", "message": "任务不存在"})
    item = container.learning_store.start_focus(owner, payload.task_id, payload.planned_min)
    return {"item": item, "reused": False}


@router.post("/focus/{focus_id}/stop", summary="结束专注")
def stop_focus(
    focus_id: str,
    payload: FocusStop,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    container = get_container()
    item = container.learning_store.stop_focus(
        focus_id,
        owner,
        payload.completed,
        elapsed_seconds=payload.elapsed_seconds,
    )
    if item is None:
        raise HTTPException(404, detail={"code": "focus_not_found", "message": "专注记录不存在"})
    encouragement = container.learning.encouragement(
        int(item.get("actual_min") or 0), int(item.get("planned_min") or 0)
    )
    return {"item": item, "encouragement": encouragement}


@router.get("/focus/stats", summary="专注统计")
def focus_stats(user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    container = get_container()
    return {
        "today_min": container.learning_store.focus_today_minutes(owner),
        "recent": container.learning_store.recent_focus(owner, 10),
    }


@router.get("/libraries", summary="错题本列表")
def list_libraries(user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    return {"items": get_container().learning_store.list_libraries(owner)}


@router.post("/libraries", summary="新建错题本")
def create_library(payload: LibraryCreate, user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    return get_container().learning_store.create_library(owner, payload.name, payload.subject)


@router.get("/libraries/trash", summary="错题本回收站")
def list_library_trash(user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    return {
        "items": get_container().learning_store.list_trash_libraries(owner),
        "retention_days": 7,
    }


@router.delete("/libraries/{library_id}", summary="删除错题本（移入回收站）")
def delete_library(library_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    library = get_container().learning_store.soft_delete_library(library_id, owner)
    if library is None:
        raise HTTPException(404, detail={"code": "library_not_found", "message": "错题本不存在"})
    return {"deleted": True, "purge_at": library.get("purge_at")}


@router.post("/libraries/{library_id}/restore", summary="恢复错题本")
def restore_library(library_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    library = get_container().learning_store.restore_library(library_id, owner)
    if library is None:
        raise HTTPException(404, detail={"code": "library_not_found", "message": "回收站中没有这个错题本"})
    return {"restored": True, "item": library}


@router.delete("/libraries/{library_id}/permanent", summary="彻底删除错题本")
def purge_library(library_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    if not get_container().learning_store.purge_library(library_id, owner):
        raise HTTPException(404, detail={"code": "library_not_found", "message": "回收站中没有这个错题本"})
    return {"purged": True}


@router.get("/questions", summary="错题列表")
def list_questions(
    library_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    container = get_container()
    if container.learning_store.get_library(library_id, owner) is None:
        raise HTTPException(404, detail={"code": "library_not_found", "message": "错题本不存在"})
    return {
        "items": [
            container.learning.public_question(question)
            for question in container.learning_store.list_questions(owner, library_id)
        ]
    }


@router.post("/questions", summary="上传错题")
def create_question(
    payload: QuestionCreate,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    if not payload.text and not payload.image_base64:
        raise HTTPException(400, detail={"code": "empty_question", "message": "请上传图片或输入题目"})
    try:
        return get_container().learning.create_question(
            owner,
            library_id=payload.library_id,
            text=payload.text,
            image_base64=payload.image_base64,
            max_tokens=payload.max_tokens,
        )
    except LookupError as exc:
        raise HTTPException(404, detail={"code": "library_not_found", "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "invalid_image", "message": str(exc)}) from exc


@router.get("/questions/trash", summary="错题回收站")
def list_question_trash(user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    container = get_container()
    return {
        "items": [
            container.learning.public_question(question)
            for question in container.learning_store.list_trash_questions(owner)
        ],
        "retention_days": 7,
    }


@router.delete("/questions/{question_id}", summary="删除错题（移入回收站）")
def delete_question(question_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    question = get_container().learning_store.soft_delete_question(question_id, owner)
    if question is None:
        raise HTTPException(404, detail={"code": "question_not_found", "message": "题目不存在"})
    return {"deleted": True, "purge_at": question.get("purge_at")}


@router.post("/questions/{question_id}/restore", summary="从回收站恢复错题")
def restore_question(question_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    container = get_container()
    question = container.learning_store.restore_question(question_id, owner)
    if question is None:
        raise HTTPException(404, detail={"code": "question_not_found", "message": "回收站中没有这道题"})
    return {"restored": True, "item": container.learning.public_question(question)}


@router.delete("/questions/{question_id}/permanent", summary="彻底删除错题")
def purge_question(question_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    if not get_container().learning_store.purge_question(question_id, owner):
        raise HTTPException(404, detail={"code": "question_not_found", "message": "回收站中没有这道题"})
    return {"purged": True}


@router.get("/questions/{question_id}/solution", summary="查看参考答案与解析")
def question_solution(
    question_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    container = get_container()
    question = container.learning_store.get_question(question_id, owner)
    if question is None:
        raise HTTPException(404, detail={"code": "question_not_found", "message": "题目不存在"})
    return container.learning.public_question(question, include_answer=True)


@router.get("/questions/{question_id}", summary="练习题目（不含答案）")
def get_question(question_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    container = get_container()
    question = container.learning_store.get_question(question_id, owner)
    if question is None:
        raise HTTPException(404, detail={"code": "question_not_found", "message": "题目不存在"})
    return container.learning.public_question(question)


@router.post("/questions/{question_id}/attempts", summary="提交作答")
def submit_attempt(
    question_id: str,
    payload: AttemptCreate,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    container = get_container()
    question = container.learning_store.get_question(question_id, owner)
    if question is None:
        raise HTTPException(404, detail={"code": "question_not_found", "message": "题目不存在"})
    try:
        feedback = container.learning.grade(question, payload.answer, owner)
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "grading_failed", "message": str(exc)}) from exc
    attempt = container.learning_store.create_attempt(
        question_id=question_id,
        owner_id=owner,
        answer_text=payload.answer,
        correctness=feedback["correctness"],
        score=float(feedback["score"]),
        feedback=feedback,
    )
    review = container.learning.schedule_review(owner, question, feedback["correctness"])
    return {"attempt": attempt, "feedback": feedback, "review": review}


class AssignmentExtractRequest(BaseModel):
    text: str | None = None
    image_base64: str | None = None


class TeachbackRequest(BaseModel):
    explanation: str = Field(min_length=1, max_length=8000)


@router.post("/questions/{question_id}/teachback", summary="错题复述检查")
def teachback(
    question_id: str,
    payload: TeachbackRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    container = get_container()
    question = container.learning_store.get_question(question_id, owner)
    if question is None:
        raise HTTPException(404, detail={"code": "question_not_found", "message": "题目不存在"})
    try:
        return container.learning.teachback(question, payload.explanation, owner)
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "teachback_failed", "message": str(exc)}) from exc


@router.post("/assignments/extract", summary="从文字/图片提取作业")
def extract_assignments(
    payload: AssignmentExtractRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    try:
        items = get_container().learning.extract_assignments(
            owner,
            text=payload.text,
            image_base64=payload.image_base64,
        )
        return {"items": items}
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "assignment_extract_failed", "message": str(exc)}) from exc


@router.get("/review", summary="今日错题复习")
def review_queue(user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    return get_container().learning.review_due(owner)


@router.get("/report", summary="学习报告")
def learning_report(
    days: int = Query(default=7, ge=1, le=30),
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    return get_container().learning.learning_report(owner, days)


@router.get("/courses/{course_id}/materials", summary="课程资料列表")
def course_materials(
    course_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    try:
        return {"items": get_container().learning.list_materials(owner, course_id)}
    except LookupError as exc:
        raise HTTPException(404, detail={"code": "course_not_found", "message": str(exc)}) from exc


@router.post("/courses/{course_id}/materials", summary="新增课程资料")
def add_course_material(
    course_id: str,
    payload: MaterialCreate,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    try:
        return get_container().learning.add_material(
            owner, course_id, title=payload.title, content=payload.content
        )
    except LookupError as exc:
        raise HTTPException(404, detail={"code": "course_not_found", "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "material_invalid", "message": str(exc)}) from exc


@router.post("/courses/{course_id}/materials/upload", summary="上传课程资料文件")
def upload_course_material(
    course_id: str,
    payload: MaterialUpload,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    try:
        import base64

        data = base64.b64decode(payload.content_base64, validate=True)
        return get_container().learning.add_material_file(
            owner, course_id, filename=payload.filename, data=data
        )
    except (ValueError, LookupError) as exc:
        raise HTTPException(400, detail={"code": "material_upload_failed", "message": str(exc)}) from exc


@router.get("/courses/{course_id}/materials/search", summary="课程资料检索")
def search_course_materials(
    course_id: str,
    q: str = Query(default="", max_length=300),
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    return {"items": get_container().learning.search_materials(owner, course_id, q)}


@router.get("/exam-room", summary="考试周作战室")
def exam_room(user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    return get_container().learning.exam_room(owner)


@router.post("/exams", summary="新增考试")
def create_exam(payload: ExamCreate, user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    try:
        return get_container().learning.create_exam(owner, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "invalid_exam", "message": str(exc)}) from exc


@router.delete("/exams/{exam_id}", summary="删除考试")
def delete_exam(exam_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    if not get_container().learning_store.delete_exam(exam_id, owner):
        raise HTTPException(404, detail={"code": "exam_not_found", "message": "考试不存在"})
    return {"deleted": True}


@router.post("/exams/{exam_id}/plan", summary="生成/重排考试复习计划")
def plan_exam(exam_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    try:
        return get_container().learning.generate_exam_plan(owner, exam_id)
    except LookupError as exc:
        raise HTTPException(404, detail={"code": "exam_not_found", "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "exam_plan_invalid", "message": str(exc)}) from exc


class SemesterStart(BaseModel):
    start_date: str = ""


@router.get("/calendar/settings", summary="日历设置")
def calendar_settings(user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    return {"semester_start": get_container().learning_store.semester_start(owner)}


@router.put("/calendar/settings", summary="保存学期开始日期")
def save_calendar_settings(
    payload: SemesterStart,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    value = payload.start_date.strip()
    if value:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise HTTPException(
                400, detail={"code": "invalid_semester_start", "message": "开始日期必须是 YYYY-MM-DD"}
            ) from exc
    return {"semester_start": get_container().learning_store.set_semester_start(owner, value)}


@router.get("/calendar/week", summary="学习周视图")
def calendar_week(
    start: str | None = None,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    try:
        start_date = date.fromisoformat(start) if start else date.today()
    except ValueError as exc:
        raise HTTPException(
            400, detail={"code": "invalid_week_start", "message": "start 必须是 YYYY-MM-DD"}
        ) from exc
    return get_container().learning.calendar_week(owner, start_date)


@router.get("/calendar", summary="学习日历")
def calendar_view(
    year: int | None = None,
    month: int | None = None,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    today = date.today()
    return get_container().learning.calendar_month(owner, year or today.year, month or today.month)


@router.get("/courses", summary="课程表")
def list_courses(user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    return {"items": get_container().learning_store.list_courses(owner)}


@router.post("/courses", summary="新增课程")
def create_course(payload: CourseCreate, user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    return get_container().learning_store.create_course(owner, payload.model_dump())


@router.post("/courses/import", summary="粘贴导入课程表")
def import_courses(payload: CourseImport, user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    container = get_container()
    parsed = container.learning.parse_courses(payload.text)
    if not parsed:
        raise HTTPException(
            400,
            detail={"code": "no_courses_parsed", "message": "没有解析出课程，请用“周一 08:00-09:40 课程名 地点”格式"},
        )
    items = [container.learning_store.create_course(owner, item) for item in parsed]
    return {"items": items, "count": len(items)}


@router.get("/model-profiles", summary="我的模型配置列表")
def list_model_profiles(user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    return {"items": get_container().learning.list_profiles(owner)}


@router.post("/model-profiles", summary="新增模型配置")
def create_model_profile(
    payload: ModelProfileCreate,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    try:
        return get_container().learning.create_profile(
            owner,
            name=payload.name,
            provider=payload.provider,
            model=payload.model,
            base_url=payload.base_url,
            official_url=payload.official_url,
            note=payload.note,
            api_key=payload.api_key,
        )
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "profile_invalid", "message": str(exc)}) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, detail={"code": "profile_encrypt_failed", "message": str(exc)}) from exc


@router.patch("/model-profiles/{profile_id}", summary="修改模型配置元数据")
def update_model_profile(
    profile_id: str,
    payload: ModelProfileUpdate,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    try:
        return get_container().learning.update_profile(
            owner, profile_id, payload.model_dump(exclude_none=True)
        )
    except LookupError as exc:
        raise HTTPException(404, detail={"code": "profile_not_found", "message": str(exc)}) from exc


@router.delete("/model-profiles/{profile_id}", summary="删除模型配置")
def delete_model_profile(
    profile_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    try:
        return get_container().learning.delete_profile(owner, profile_id)
    except LookupError as exc:
        raise HTTPException(404, detail={"code": "profile_not_found", "message": str(exc)}) from exc


@router.post("/model-profiles/{profile_id}/test", summary="测试模型配置")
def test_model_profile(
    profile_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    try:
        return get_container().learning.test_profile(owner, profile_id)
    except LookupError as exc:
        raise HTTPException(404, detail={"code": "profile_not_found", "message": str(exc)}) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, detail={"code": "profile_test_failed", "message": str(exc)}) from exc


@router.post("/model-profiles/{profile_id}/activate", summary="启用模型配置")
def activate_model_profile(
    profile_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    try:
        return get_container().learning.activate_profile(owner, profile_id)
    except LookupError as exc:
        raise HTTPException(404, detail={"code": "profile_not_found", "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "profile_not_ready", "message": str(exc)}) from exc


@router.get("/settings/vision", summary="我的当前视觉模型配置")
def vision_settings(user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    return get_container().learning.vision_settings_public(owner)


@router.post("/settings/vision", summary="保存我的视觉模型 API Key")
def set_vision_settings(
    payload: VisionSettings,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    container = get_container()
    public = container.learning.vision_settings_public(owner)
    base_url = (payload.base_url or "").strip() or public.get("base_url") or ""
    model = (payload.model or "").strip() or public.get("model") or container.settings.learning_vision_model
    try:
        container.learning.save_vision_settings(
            owner,
            api_key=payload.api_key or "",
            base_url=base_url,
            model=model,
        )
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "invalid_vision_settings", "message": str(exc)}) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            500,
            detail={"code": "encryption_failed", "message": f"API Key 加密保存失败：{exc}"},
        ) from exc
    return container.learning.vision_settings_public(owner)


@router.delete("/settings/vision", summary="删除我的视觉模型 Key")
def delete_vision_settings(user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    deleted = get_container().learning.delete_vision_settings(owner)
    if not deleted:
        raise HTTPException(404, detail={"code": "vision_not_configured", "message": "还没有配置 Key"})
    return {"deleted": True}


@router.post("/settings/vision/test", summary="测试我的视觉模型配置")
def test_vision(user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    owner = _owner(user)
    try:
        return get_container().learning.test_vision(owner)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, detail={"code": "vision_test_failed", "message": str(exc)}) from exc
