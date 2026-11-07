"""校园业务系统模拟。

内存数据库 + JSON 落盘，模拟网络延迟与超时故障。
学号、余额、挂失状态均为确定性数据，保证演示与测试可复现。
"""

from __future__ import annotations

import asyncio
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.config import Settings
from app.core.exceptions import ToolTimeoutError
from app.student_registry import StudentRegistry

CAMPUS_LOCATIONS: dict[str, str] = {
    "天赐庄": "天赐庄校区敬文书院一楼卡务中心",
    "独墅湖": "独墅湖校区炳麟图书馆北楼卡务中心",
    "阳澄湖": "阳澄湖校区行政楼 A 座 108",
}

WEEKDAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

# (学号, 姓名, 学院, 校区, 是否挂失, 余额)
SEED_STUDENTS: tuple[tuple[str, str, str, str, bool, float], ...] = (
    ("2025001001", "张子墨", "计算机科学与技术学院", "天赐庄", False, 120.50),
    ("2025001002", "李沐晴", "商学院", "独墅湖", True, 0.00),
    ("2025001003", "王予安", "光电科学与工程学院", "阳澄湖", True, -35.50),
    ("2025001004", "陈嘉禾", "文学院", "天赐庄", False, 58.00),
    ("2025001005", "刘思远", "数学科学学院", "天赐庄", True, -12.00),
    ("2025001006", "赵清和", "电子信息学院", "独墅湖", False, 0.00),
    ("2025001007", "孙可欣", "外国语学院", "天赐庄", False, 245.00),
    ("2025001008", "周予宁", "材料与化学化工学部", "独墅湖", True, 0.00),
    ("2025001009", "吴之恒", "体育学院", "天赐庄", False, 32.00),
    ("2025001010", "郑雨桐", "社会学院", "独墅湖", False, -8.50),
    ("2025001011", "冯亦辰", "王健法学院", "天赐庄", True, 66.00),
    ("2025001012", "蒋书瑶", "教育学院", "独墅湖", False, 15.00),
    ("2025001013", "沈砚白", "建筑学院", "独墅湖", False, 0.00),
    ("2025001014", "韩清越", "医学院", "独墅湖", True, 88.00),
    ("2025001015", "杨知微", "音乐学院", "天赐庄", False, -20.00),
    ("2025001016", "许星野", "传媒学院", "独墅湖", False, 42.00),
    ("2025001017", "何雨眠", "历史学院", "天赐庄", False, 0.00),
    ("2025001018", "罗嘉树", "能源学院", "阳澄湖", True, 130.00),
    ("2025001019", "唐予棠", "纺织与服装工程学院", "独墅湖", False, 6.00),
    ("2025001020", "顾行舟", "机电工程学院", "阳澄湖", False, -3.00),
)


class MockCampusService:
    """模拟校园业务后端。"""

    def __init__(self, settings: Settings, registry: StudentRegistry | None = None) -> None:
        self._settings = settings
        self._registry = registry
        self._state_path: Path = settings.data_dir / "mock_services.json"
        self._students: dict[str, dict[str, Any]] = {}
        self._orders: dict[str, dict[str, Any]] = {}
        self._receipt_seq: dict[str, int] = {}
        self._repairs: dict[str, dict[str, Any]] = {}
        self._repair_idempotency: dict[str, str] = {}
        self._repair_seq = 0
        self._leaves: dict[str, dict[str, Any]] = {}
        self._leave_idempotency: dict[str, str] = {}
        self._leave_seq = 0
        self._seed()
        self._load_state()

    # ------------------------------------------------------------------ 数据
    def _seed(self) -> None:
        """从种子数据初始化学生与校园卡状态。"""
        for student_id, name, college, campus, lost, balance in SEED_STUDENTS:
            self._students[student_id] = {
                "student_id": student_id,
                "name": name,
                "college": college,
                "campus": campus,
                "grade": "2025级",
                "enrolled": True,
                "card_lost": lost,
                "reported_at": "2026-10-28T09:30:00" if lost else None,
                "balance": round(balance, 2),
            }

    def _load_state(self) -> None:
        """加载上次运行落盘的状态（挂失、余额、工单）。"""
        if not self._state_path.exists():
            return
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for student_id, saved in payload.get("students", {}).items():
            if student_id in self._students:
                self._students[student_id].update(saved)
        self._orders = payload.get("orders", {})
        self._receipt_seq = payload.get("receipt_seq", {})
        self._repairs = payload.get("repairs", {})
        self._repair_idempotency = payload.get("repair_idempotency", {})
        self._repair_seq = int(payload.get("repair_seq", 0))
        self._leaves = payload.get("leaves", {})
        self._leave_idempotency = payload.get("leave_idempotency", {})
        self._leave_seq = int(payload.get("leave_seq", 0))

    def _save_state(self) -> None:
        """原子写入状态文件。"""
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "students": {
                student_id: {
                    "card_lost": record["card_lost"],
                    "reported_at": record["reported_at"],
                    "balance": record["balance"],
                }
                for student_id, record in self._students.items()
            },
            "orders": self._orders,
            "receipt_seq": self._receipt_seq,
            "repairs": self._repairs,
            "repair_idempotency": self._repair_idempotency,
            "repair_seq": self._repair_seq,
            "leaves": self._leaves,
            "leave_idempotency": self._leave_idempotency,
            "leave_seq": self._leave_seq,
        }
        temporary = self._state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self._state_path)

    async def _delay(self) -> None:
        """模拟网络延迟。"""
        if not self._settings.tool_simulate_delay:
            return
        await asyncio.sleep(
            random.uniform(
                self._settings.tool_min_delay_ms / 1000,
                self._settings.tool_max_delay_ms / 1000,
            )
        )

    def _guard_fault(self, student_id: str | None) -> None:
        """故障注入：指定学号的所有业务调用都超时。"""
        if student_id and student_id in self._settings.fault_student_ids:
            raise ToolTimeoutError(
                f"业务系统在查询学号 {student_id} 时响应超时（模拟故障注入）"
            )

    def _student(self, student_id: str) -> dict[str, Any] | None:
        return self._students.get(student_id)

    def _roster_student(self, student_id: str) -> dict[str, Any] | None:
        """从持久化名册读取学生；名册不存在时返回 None。"""
        if self._registry is None:
            return None
        return self._registry.lookup(student_id)

    def _ensure_roster_card(self, student_id: str) -> dict[str, Any] | None:
        """为名册学生创建一份模拟校园卡状态（只用于演示）。"""
        roster = self._roster_student(student_id)
        if roster is None:
            return None
        record = {
            "student_id": student_id,
            "name": roster["name"],
            "college": roster["college"],
            "campus": roster.get("campus") or "天赐庄",
            "grade": f"{roster.get('cohort', '')}级",
            "enrolled": roster.get("status") == "active",
            "card_lost": False,
            "reported_at": None,
            "balance": 0.0,
            "source": "roster",
            "simulated_card_state": True,
        }
        self._students[student_id] = record
        return record

    # ------------------------------------------------------------------ 工具实现
    async def query_profile(self, student_id: str) -> dict[str, Any]:
        """查询学籍信息。"""
        await self._delay()
        self._guard_fault(student_id)
        record = self._student(student_id)
        if not record:
            roster = self._roster_student(student_id)
            if roster is None:
                return {"valid": False, "student_id": student_id, "exists": False}
            return {
                "valid": True,
                "exists": True,
                "student_id": roster["student_id"],
                "name": roster["name"],
                "college": roster["college"],
                "campus": roster.get("campus"),
                "grade": f"{roster.get('cohort', '')}级",
                "enrolled": roster.get("status") == "active",
                "major": roster.get("major"),
                "class_name": roster.get("class_name"),
                "cohort": roster.get("cohort"),
                "status": roster.get("status"),
                "source": "roster",
                "simulated_card_state": True,
            }
        return {
            "valid": True,
            "exists": True,
            "student_id": record["student_id"],
            "name": record["name"],
            "college": record["college"],
            "campus": record["campus"],
            "grade": record["grade"],
            "enrolled": record["enrolled"],
            "major": record.get("major", ""),
            "class_name": record.get("class_name", ""),
            "cohort": record.get("cohort", ""),
            "source": record.get("source", "mock"),
            "simulated_card_state": record.get("simulated_card_state", False),
        }

    async def query_loss_status(self, student_id: str) -> dict[str, Any]:
        """查询校园卡挂失状态。"""
        await self._delay()
        self._guard_fault(student_id)
        record = self._student(student_id)
        if not record:
            roster = self._roster_student(student_id)
            if roster is None:
                return {"student_id": student_id, "exists": False, "lost": False}
            return {
                "student_id": student_id,
                "exists": True,
                "lost": False,
                "reported_at": None,
                "source": "roster",
                "simulated": True,
            }
        return {
            "student_id": student_id,
            "exists": True,
            "lost": bool(record["card_lost"]),
            "reported_at": record["reported_at"],
            "source": record.get("source", "mock"),
            "simulated": record.get("simulated_card_state", False),
        }

    async def report_loss(self, student_id: str) -> dict[str, Any]:
        """提交挂失，重复调用保持幂等。"""
        await self._delay()
        self._guard_fault(student_id)
        record = self._student(student_id) or self._ensure_roster_card(student_id)
        if not record:
            raise ValueError(f"学号 {student_id} 不存在")
        already_lost = bool(record["card_lost"])
        if not already_lost:
            record["card_lost"] = True
            record["reported_at"] = datetime.now().isoformat(timespec="seconds")
            self._save_state()
        return {
            "student_id": student_id,
            "lost": True,
            "reported_at": record["reported_at"],
            "already_lost": already_lost,
        }

    async def query_balance(self, student_id: str) -> dict[str, Any]:
        """查询校园卡余额与欠费。"""
        await self._delay()
        self._guard_fault(student_id)
        record = self._student(student_id)
        if not record:
            roster = self._roster_student(student_id)
            if roster is None:
                return {"student_id": student_id, "exists": False, "balance": 0.0, "arrears": 0.0}
            return {
                "student_id": student_id,
                "exists": True,
                "balance": 0.0,
                "arrears": 0.0,
                "has_arrears": False,
                "source": "roster",
                "simulated": True,
            }
        balance = round(float(record["balance"]), 2)
        arrears = round(-balance, 2) if balance < 0 else 0.0
        return {
            "student_id": student_id,
            "exists": True,
            "balance": balance,
            "arrears": arrears,
            "has_arrears": arrears > 0,
            "source": record.get("source", "mock"),
            "simulated": record.get("simulated_card_state", False),
        }

    async def query_available_slots(self, campus: str) -> dict[str, Any]:
        """返回未来 3 天的 6 个可预约时段。"""
        await self._delay()
        location = CAMPUS_LOCATIONS.get(campus, CAMPUS_LOCATIONS["天赐庄"])
        slots: list[dict[str, Any]] = []
        today = date.today()
        for offset in range(1, 4):
            day = today + timedelta(days=offset)
            for period, time_range in (("AM", "09:00-11:30"), ("PM", "13:30-16:30")):
                slots.append(
                    {
                        "slot_id": f"{day.isoformat()}-{period}",
                        "date": day.isoformat(),
                        "weekday": WEEKDAYS[day.weekday()],
                        "time": time_range,
                        "location": location,
                        "remaining": 6 if period == "AM" else 4,
                    }
                )
        return {
            "campus": campus,
            "location": location,
            "slots": slots,
            "recommended": slots[0],
        }

    async def submit_reissue_order(
        self,
        student_id: str,
        campus: str,
        slot_id: str,
        idempotency_key: str,
        fee: float = 20.0,
    ) -> dict[str, Any]:
        """提交制卡工单，按幂等键去重。"""
        await self._delay()
        self._guard_fault(student_id)
        if idempotency_key in self._orders:
            existing = dict(self._orders[idempotency_key])
            existing["duplicate"] = True
            return existing

        record = self._student(student_id) or self._ensure_roster_card(student_id)
        if not record:
            raise ValueError(f"学号 {student_id} 不存在")

        day_key = date.today().strftime("%Y%m%d")
        sequence = self._receipt_seq.get(day_key, 0) + 1
        self._receipt_seq[day_key] = sequence
        receipt = f"CARD{day_key}{sequence:03d}"
        order = {
            "order_id": f"WO-{receipt}",
            "receipt_number": receipt,
            "student_id": student_id,
            "student_name": record["name"],
            "campus": campus,
            "slot_id": slot_id,
            "fee": fee,
            "status": "submitted",
            "location": CAMPUS_LOCATIONS.get(campus, CAMPUS_LOCATIONS["天赐庄"]),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "expected_days": 3,
            "idempotency_key": idempotency_key,
            "duplicate": False,
        }
        self._orders[idempotency_key] = order
        self._save_state()
        return dict(order)

    def get_order(self, receipt_number: str) -> dict[str, Any] | None:
        """按回执号查询模拟系统中的工单。"""
        for order in self._orders.values():
            if order["receipt_number"] == receipt_number:
                return dict(order)
        return None

    async def create_repair_ticket(
        self,
        student_id: str,
        campus: str,
        category: str,
        description: str,
    ) -> dict[str, Any]:
        """生成待确认的网络报修单。"""
        await self._delay()
        self._guard_fault(student_id)
        record = self._student(student_id) or self._ensure_roster_card(student_id)
        if not record:
            raise ValueError(f"学号 {student_id} 不存在")
        self._repair_seq += 1
        ticket_id = f"REP{date.today().strftime('%Y%m%d')}{self._repair_seq:04d}"
        ticket = {
            "ticket_id": ticket_id,
            "student_id": student_id,
            "student_name": record["name"],
            "campus": campus,
            "category": category or "网络",
            "description": description,
            "status": "draft",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._repairs[ticket_id] = ticket
        self._save_state()
        return dict(ticket)

    async def submit_repair_ticket(
        self,
        ticket_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """提交报修单；幂等键重复时返回原回执。"""
        await self._delay()
        if idempotency_key in self._repair_idempotency:
            existing_id = self._repair_idempotency[idempotency_key]
            existing = dict(self._repairs.get(existing_id, {}))
            existing["duplicate"] = True
            return existing
        ticket = self._repairs.get(ticket_id)
        if ticket is None:
            raise ValueError("报修单不存在")
        receipt = ticket_id.replace("REP", "RPR", 1)
        ticket.update(
            {
                "status": "submitted",
                "receipt_number": receipt,
                "submitted_at": datetime.now().isoformat(timespec="seconds"),
                "assigned_to": f"{ticket['campus']}网络维护组",
            }
        )
        self._repair_idempotency[idempotency_key] = ticket_id
        self._save_state()
        return dict(ticket)

    async def create_leave_request(
        self,
        student_id: str,
        campus: str,
        days: int,
        reason: str,
    ) -> dict[str, Any]:
        """生成请假申请草稿。"""
        await self._delay()
        self._guard_fault(student_id)
        record = self._student(student_id) or self._ensure_roster_card(student_id)
        if not record:
            raise ValueError(f"学号 {student_id} 不存在")
        self._leave_seq += 1
        leave_id = f"LEAVE{date.today().strftime('%Y%m%d')}{self._leave_seq:04d}"
        request = {
            "leave_id": leave_id,
            "student_id": student_id,
            "student_name": record["name"],
            "campus": campus,
            "days": max(1, int(days)),
            "reason": reason,
            "status": "draft",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._leaves[leave_id] = request
        self._save_state()
        return dict(request)

    async def submit_leave_request(
        self,
        leave_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """提交已审批的请假申请。"""
        await self._delay()
        if idempotency_key in self._leave_idempotency:
            existing_id = self._leave_idempotency[idempotency_key]
            existing = dict(self._leaves.get(existing_id, {}))
            existing["duplicate"] = True
            return existing
        request = self._leaves.get(leave_id)
        if request is None:
            raise ValueError("请假申请不存在")
        receipt = leave_id.replace("LEAVE", "LVE", 1)
        request.update(
            {
                "status": "approved",
                "receipt_number": receipt,
                "submitted_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        self._leave_idempotency[idempotency_key] = leave_id
        self._save_state()
        return dict(request)

    async def return_leave(self, leave_id: str) -> dict[str, Any]:
        """返校销假：只允许已批准的请假单。"""
        await self._delay()
        request = self._leaves.get(leave_id)
        if request is None:
            raise ValueError("请假申请不存在")
        if request.get("status") not in {"approved", "returned"}:
            raise ValueError("请假申请尚未通过，不能销假")
        request["status"] = "returned"
        request["returned_at"] = datetime.now().isoformat(timespec="seconds")
        self._save_state()
        return dict(request)

    def list_students(self) -> list[dict[str, Any]]:
        """返回脱敏后的学生样例，用于前端系统页展示。"""
        return [
            {
                "student_id": record["student_id"],
                "name": record["name"],
                "college": record["college"],
                "campus": record["campus"],
                "card_lost": record["card_lost"],
                "balance": record["balance"],
            }
            for record in self._students.values()
        ]
