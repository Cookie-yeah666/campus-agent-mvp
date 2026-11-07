"""学习空间业务逻辑：计划解析、图片预处理、错题提取、批改与专注反馈。"""

from __future__ import annotations

import base64
import calendar
import hashlib
import io
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageOps

from app.config import Settings
from app.learning.secrets import protect, unprotect
from app.learning.store import LearningStore
from app.models.domain import KnowledgeChunk
from app.retrieval.vector_search import TfidfVectorIndex


PRIORITY_LABELS = {
    "high": "高优先级",
    "medium": "中优先级",
    "low": "低优先级",
    "none": "无优先级",
}

DURATION_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(小时|h|分钟|min|分)", re.IGNORECASE)
MONTH_DAY_RE = re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日")
WEEKDAY_RE = re.compile(r"(?:周|星期)([一二三四五六日天])")
PRIORITY_WORDS = {
    "high": ("高优先级", "重要", "紧急", "必须", "考试"),
    "medium": ("中优先级", "一般"),
    "low": ("低优先级", "有空", "可选"),
}

WEEKDAY_MAP = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}

# 「智能拆解」的本地分段规则：
# - 强分隔：换行、分号、句号；
# - 逗号前后根据“时间词 / 新任务动词”判断是否是新任务；
# - “重点看…”“明天交…”等补充说明留在原任务里。
PLAN_LINE_SPLIT_RE = re.compile(r"[\n;；。!?！？]+")
PLAN_CLAUSE_SPLIT_RE = re.compile(r"[,，、]+")
PLAN_CONNECTOR_SPLIT_RE = re.compile(
    r"(?:，|,)?\s*(?:然后|接着|之后|随后|再|另外|还有|以及|同时|最后|最终)(?=\S)"
)
PLAN_TASK_CUE_RE = re.compile(
    r"(学|复习|预习|看|读|背|写|做|刷|练|听|整理|完成|准备|提交|交|"
    r"改|总结|记|查|翻译|计算|推导|画|编程|实验|论文|报告|作业|"
    r"单词|题|卷|PPT|ppt|项目|网课|作文|习题|试卷|错题|海报|方案|"
    r"展示|汇报|笔记|听力|口语|代码|课程|章节|知识点|实验报告)"
)
PLAN_CONTINUATION_RE = re.compile(
    r"^(重点|主要|尤其|特别是|比如|例如|包括|其中|要求|注意|具体|"
    r"先|最好|尽量|至少|再|然后|接着|顺便)"
)
PLAN_TIME_START_RE = re.compile(
    r"^(今天|明天|后天|今晚|明早|上午|下午|晚上|中午|下周|这周|本周|"
    r"周[一二三四五六日天]|星期[一二三四五六日天]|\d{1,2}月\d{1,2}日)"
)
PLAN_DEADLINE_ONLY_RE = re.compile(
    r"^(?:(?:今天|明天|后天|下周[一二三四五六日天]?|周[一二三四五六日天])?"
    r"(?:交|提交|截止|考试|考))$"
)
# 无标点长列表的兜底边界；不把“实验”单列，避免把“实验报告”切坏。
PLAN_TASK_NOUN_RE = re.compile(
    r"(作业|作文|报告|习题|试卷|错题|海报|方案|论文|项目|单词|笔记|"
    r"课程|章节|知识点|网课|ppt|PPT)"
)
# “还有一个二 / 加二”这类不是任务，是连接词后面的序号残片。
PLAN_NUMERIC_FRAGMENT_RE = re.compile(
    r"^(?:还?有?|一?个?)?(?:加)?[一二三四五六七八九十百0-9]+(?:个|条|项)?$"
)
# 只在“分句开头/结尾”清口水词，保留正文里的“那个作业”等实义表达。
PLAN_FILLER_PREFIX_RE = re.compile(
    r"^(?:(?:嗯+|啊+|呃+|额+|唔+|诶+|哎+|那个|就是说|怎么说呢|"
    r"你知道吧|对吧|然后就是|就是|然后|接着|再|最后)+[，,\s]*)+"
)
PLAN_FILLER_SUFFIX_RE = re.compile(
    r"(?:[，,\s]*(?:嗯+|啊+|呃+|额+|对吧|你知道吗|你知道吧|怎么说呢))+$"
)
PLAN_INLINE_INTERJECTION_RE = re.compile(
    r"(?<=[\u4e00-\u9fff])(?:嗯+|啊+|呃+|额+|唔+|诶+|哎+)(?=[\u4e00-\u9fff])"
)


def clean_plan_transcript(text: str) -> str:
    """转写清洗：处理语气词、重复连接词和口水式停顿，不删除正文实词。"""
    text = re.sub(r"([，,。；;！？!?])\1+", r"\1", text)
    # 只压缩行内空白，保留换行作为任务边界。
    text = re.sub(r"[ \t]+", " ", text)
    # 词中间的单个语气词（如“我嗯明天”）不属于任务内容。
    text = PLAN_INLINE_INTERJECTION_RE.sub("", text)
    clauses = []
    for clause in re.split(r"[，,。；;！？!?]+", text):
        cleaned = PLAN_FILLER_PREFIX_RE.sub("", clause.strip())
        cleaned = PLAN_FILLER_SUFFIX_RE.sub("", cleaned).strip()
        if cleaned:
            clauses.append(cleaned)
    return "，".join(clauses).strip()

HOLIDAYS_2026 = {
    "2026-01-01": "元旦",
    "2026-02-16": "春节假期",
    "2026-02-17": "春节",
    "2026-02-18": "春节假期",
    "2026-02-19": "春节假期",
    "2026-02-20": "春节假期",
    "2026-02-21": "春节假期",
    "2026-02-22": "春节假期",
    "2026-04-05": "清明节",
    "2026-05-01": "劳动节",
    "2026-06-19": "端午节",
    "2026-09-25": "中秋节",
    "2026-10-01": "国庆节",
    "2026-10-02": "国庆假期",
    "2026-10-03": "国庆假期",
    "2026-10-04": "国庆假期",
    "2026-10-05": "国庆假期",
    "2026-10-06": "国庆假期",
    "2026-10-07": "国庆假期",
}


def _clean_title(text: str) -> str:
    title = DURATION_RE.sub("", text)
    title = MONTH_DAY_RE.sub("", title)
    title = WEEKDAY_RE.sub("", title)
    title = re.sub(
        r"(今天|明天|后天|今晚|明早|上午|下午|晚上|中午|下周|这周|本周|"
        r"周[一二三四五六日天]|星期[一二三四五六日天]|高优先级|中优先级|"
        r"低优先级|重要|紧急|必须)",
        "",
        title,
    )
    # 标题只取第一个任务短语；逗号后的“重点/要求”留在 detail。
    title = re.split(r"[,，]", title, maxsplit=1)[0]
    title = re.sub(r"^(然后|接着|之后|随后|再|另外|还有|以及|同时|最后|最终)", "", title)
    title = re.sub(r"^[\s,，。；;、\-—:：]+|[\s,，。；;、\-—:：]+$", "", title)
    return title.strip()[:60] or "学习任务"


def _split_plan_segments(text: str) -> list[str]:
    """把一段中文计划拆成任务段，而不是只按换行/分号切。"""
    segments: list[str] = []
    for raw_line in PLAN_LINE_SPLIT_RE.split(text):
        for line in PLAN_CONNECTOR_SPLIT_RE.split(raw_line):
            line = line.strip(" -•\t")
            if not line:
                continue
            clauses = [item.strip() for item in PLAN_CLAUSE_SPLIT_RE.split(line) if item.strip()]
            current = ""
            for clause in clauses:
                if not current:
                    current = clause
                    continue
                continuation = bool(PLAN_CONTINUATION_RE.search(clause))
                deadline_only = bool(PLAN_DEADLINE_ONLY_RE.match(clause))
                starts_new = bool(PLAN_TIME_START_RE.search(clause)) or bool(
                    PLAN_TASK_CUE_RE.search(clause)
                )
                if continuation or deadline_only:
                    current += "，" + clause
                elif starts_new:
                    segments.append(current)
                    current = clause
                else:
                    current += "，" + clause
            if current:
                segments.append(current)
    # 完全没有标点/连接词的长列表兜底：
    # “高数作业英语作文物理报告线代习题社团海报Python项目”按任务名词边界切开。
    # 过滤连接词后的纯序号残片，例如“还有一个二”里的“二”。
    if len(segments) > 1:
        filtered = [
            segment
            for segment in segments
            if not PLAN_NUMERIC_FRAGMENT_RE.fullmatch(segment.strip(" ，,、"))
        ]
        if filtered:
            segments = filtered
    if len(segments) == 1 and len(segments[0]) >= 20:
        text_value = segments[0]
        matches = list(PLAN_TASK_NOUN_RE.finditer(text_value))
        if len(matches) >= 3:
            pieces: list[str] = []
            start = 0
            for match in matches:
                end = match.end()
                piece = text_value[start:end].strip(" ，,、和与及")
                if piece:
                    pieces.append(piece)
                start = end
            tail = text_value[start:].strip(" ，,、和与及")
            if tail:
                pieces.append(tail)
            if len(pieces) >= 3:
                segments = pieces
    return segments


def _parse_date(text: str) -> date:
    today = date.today()
    if "后天" in text:
        return today + timedelta(days=2)
    if "明天" in text:
        return today + timedelta(days=1)
    if "今天" in text:
        return today
    match = MONTH_DAY_RE.search(text)
    if match:
        month, day = int(match.group(1)), int(match.group(2))
        year = today.year
        candidate = date(year, month, day)
        return candidate if candidate >= today else date(year + 1, month, day)
    match = WEEKDAY_RE.search(text)
    if match:
        target = WEEKDAY_MAP[match.group(1)]
        delta = (target - today.weekday()) % 7
        return today + timedelta(days=delta or 7)
    return today


def _parse_minutes(text: str) -> int:
    match = DURATION_RE.search(text)
    if not match:
        return 60
    value = float(match.group(1))
    unit = match.group(2).lower()
    if unit in {"小时", "h"}:
        return max(5, int(round(value * 60)))
    return max(5, int(round(value)))


def _parse_priority(text: str) -> str:
    for priority, words in PRIORITY_WORDS.items():
        if any(word in text for word in words):
            return priority
    return "none"


class LearningService:
    """学习空间服务。"""

    def __init__(self, settings: Settings, store: LearningStore) -> None:
        self.settings = settings
        self.store = store

    def active_profile(self, owner_id: str) -> dict[str, Any] | None:
        return self.store.active_vision_profile(owner_id)

    def credentials(self, owner_id: str) -> dict[str, str] | None:
        """解密当前启用配置的 Key；只在请求内存中使用。"""
        row = self.store.active_vision_profile(owner_id)
        if not row:
            return None
        if row["status"] != "ok":
            return None
        try:
            api_key = unprotect(row["key_cipher"])
        except Exception:  # noqa: BLE001
            return None
        return {
            "api_key": api_key,
            "base_url": row["base_url"],
            "model": row["model"],
        }

    def vision_mode(self, owner_id: str) -> str:
        profile = self.store.active_vision_profile(owner_id)
        if profile is None:
            return "unconfigured"
        if profile["status"] != "ok":
            return "untested"
        return "http" if self.credentials(owner_id) else "unconfigured"

    def vision_model(self, owner_id: str) -> str:
        credentials = self.credentials(owner_id)
        return credentials["model"] if credentials else self.settings.learning_vision_model

    def public_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": profile["id"],
            "name": profile["name"],
            "provider": profile["provider"],
            "model": profile["model"],
            "base_url": profile["base_url"],
            "official_url": profile["official_url"],
            "note": profile["note"],
            "key_masked": profile["key_mask"],
            "key_fingerprint": profile["key_fingerprint"],
            "status": profile["status"],
            "last_tested_at": profile["last_tested_at"],
            "last_test_message": profile["last_test_message"],
            "is_active": bool(profile["is_active"]),
            "created_at": profile["created_at"],
            "one_way": True,
        }

    def list_profiles(self, owner_id: str) -> list[dict[str, Any]]:
        return [
            self.public_profile(profile)
            for profile in self.store.list_vision_profiles(owner_id)
        ]

    def create_profile(
        self,
        owner_id: str,
        *,
        name: str,
        provider: str,
        model: str,
        base_url: str,
        official_url: str,
        note: str,
        api_key: str,
    ) -> dict[str, Any]:
        key = api_key.strip()
        if not key:
            raise ValueError("必须填写 API Key")
        if not base_url.strip():
            raise ValueError("必须填写 Base URL")
        if not model.strip():
            raise ValueError("必须填写模型名称")
        cipher = protect(key)
        mask = f"{key[:3]}****{key[-4:]}" if len(key) >= 8 else "****"
        profile = self.store.create_vision_profile(
            owner_id,
            {
                "name": name or provider or "模型配置",
                "provider": provider or "custom",
                "model": model,
                "base_url": base_url,
                "official_url": official_url,
                "note": note,
                "key_cipher": cipher,
                "key_mask": mask,
                "key_fingerprint": hashlib.sha256(key.encode("utf-8")).hexdigest()[:16],
            },
        )
        return self.public_profile(profile)

    def update_profile(
        self,
        owner_id: str,
        profile_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        profile = self.store.get_vision_profile(profile_id, owner_id)
        if profile is None:
            raise LookupError("配置不存在")
        allowed = {"name", "provider", "model", "base_url", "official_url", "note"}
        clean = {key: value for key, value in updates.items() if key in allowed}
        if "model" in clean and clean["model"] != profile["model"]:
            clean["status"] = "unknown"
        if "base_url" in clean and clean["base_url"] != profile["base_url"]:
            clean["status"] = "unknown"
        updated = self.store.update_vision_profile(profile_id, owner_id, clean)
        return self.public_profile(updated or profile)

    def delete_profile(self, owner_id: str, profile_id: str) -> dict[str, Any]:
        profile = self.store.get_vision_profile(profile_id, owner_id)
        if profile is None:
            raise LookupError("配置不存在")
        was_active = bool(profile["is_active"])
        self.store.delete_vision_profile(profile_id, owner_id)
        new_active = None
        if was_active:
            remaining = self.store.list_vision_profiles(owner_id)
            tested = [item for item in remaining if item["status"] == "ok"]
            if tested:
                self.store.activate_vision_profile(tested[0]["id"], owner_id)
                new_active = self.public_profile(self.store.get_vision_profile(tested[0]["id"], owner_id))
        return {"deleted": True, "active": new_active}

    def activate_profile(self, owner_id: str, profile_id: str) -> dict[str, Any]:
        profile = self.store.get_vision_profile(profile_id, owner_id)
        if profile is None:
            raise LookupError("配置不存在")
        if profile["status"] != "ok":
            raise ValueError("请先测试连接，成功后才能设为当前配置")
        self.store.activate_vision_profile(profile_id, owner_id)
        return self.public_profile(profile)

    def test_profile(self, owner_id: str, profile_id: str) -> dict[str, Any]:
        profile = self.store.get_vision_profile(profile_id, owner_id)
        if profile is None:
            raise LookupError("配置不存在")
        try:
            api_key = unprotect(profile["key_cipher"])
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Key 无法解密，请删除后重新录入") from exc
        started = datetime.now()
        try:
            content = self._chat(
                {
                    "api_key": api_key,
                    "base_url": profile["base_url"],
                    "model": profile["model"],
                },
                messages=[{"role": "user", "content": "只回复两个字：正常"}],
                max_tokens=256,
            )
            latency = round((datetime.now() - started).total_seconds() * 1000)
            updated = self.store.update_vision_profile_test(
                profile_id,
                owner_id,
                status="ok",
                message=f"连接正常 · {latency}ms · {content[:30]}",
            )
            return {
                "ok": True,
                "model": profile["model"],
                "reply": content[:50],
                "latency_ms": latency,
                "profile": self.public_profile(updated or profile),
            }
        except Exception as exc:  # noqa: BLE001
            self.store.update_vision_profile_test(
                profile_id,
                owner_id,
                status="error",
                message=str(exc),
            )
            raise ValueError(f"连接失败：{exc}") from exc

    def test_vision(self, owner_id: str) -> dict[str, Any]:
        profile = self.store.active_vision_profile(owner_id)
        if profile is None:
            raise ValueError("请先新增并测试一个模型配置")
        return self.test_profile(owner_id, profile["id"])

    def save_vision_settings(
        self,
        owner_id: str,
        *,
        api_key: str,
        base_url: str,
        model: str,
    ) -> dict[str, Any]:
        """兼容旧接口：创建第一个配置；已有配置时拒绝覆盖。"""
        existing = self.store.list_vision_profiles(owner_id)
        if existing:
            raise ValueError("已保存配置。为保护 Key，不能覆盖；请删除旧配置后重新录入。")
        return self.create_profile(
            owner_id,
            name="默认配置",
            provider="custom",
            model=model,
            base_url=base_url,
            official_url="",
            note="",
            api_key=api_key,
        )

    def delete_vision_settings(self, owner_id: str) -> bool:
        profile = self.store.active_vision_profile(owner_id)
        if profile is None:
            return False
        self.store.delete_vision_profile(profile["id"], owner_id)
        return True

    def vision_settings_public(self, owner_id: str) -> dict[str, Any]:
        profile = self.store.active_vision_profile(owner_id)
        credentials = self.credentials(owner_id)
        if profile is None:
            return {
                "configured": False,
                "mode": "unconfigured",
                "model": self.settings.learning_vision_model,
                "base_url": self.settings.learning_vision_base_url,
                "key_masked": "",
                "key_fingerprint": "",
                "one_way": True,
                "profile": None,
            }
        return {
            "configured": True,
            "ready": credentials is not None,
            "mode": "http" if credentials else "untested",
            "model": profile["model"],
            "base_url": profile["base_url"],
            "key_masked": profile["key_mask"],
            "key_fingerprint": profile["key_fingerprint"],
            "one_way": True,
            "profile": self.public_profile(profile),
        }

    # ------------------------------------------------------------------
    # 任务计划
    # ------------------------------------------------------------------
    def parse_plan(self, text: str) -> list[dict[str, Any]]:
        """把自然语言计划拆成任务草稿（本地规则；可替换为 LLM）。"""
        lines = _split_plan_segments(clean_plan_transcript(text))
        tasks: list[dict[str, Any]] = []
        for line in lines:
            due = _parse_date(line)
            tasks.append(
                {
                    "title": _clean_title(line),
                    "detail": line,
                    "duration_min": _parse_minutes(line),
                    "priority": _parse_priority(line),
                    "start_date": date.today().isoformat(),
                    "due_date": due.isoformat(),
                    "remind_at": None,
                }
            )
        return tasks

    def parse_plan_with_model(self, owner_id: str, text: str) -> list[dict[str, Any]]:
        """用学生自己的模型做语义拆解；未配置/未测试时明确报错。"""
        credentials = self.credentials(owner_id)
        if credentials is None:
            raise ValueError("请先在「模型设置」中配置并测试模型，或关闭“用模型提炼”")
        cleaned = clean_plan_transcript(text)
        prompt = (
            "你是学习计划拆解器。把用户的一段口语计划拆成可执行任务。"
            "先忽略语气词、口头禅、重复和自我纠正；不要把“嗯、那个、就是说、然后”当作任务内容。"
            f"今天是 {date.today().isoformat()}。"
            "严格返回 JSON 数组，不要 Markdown："
            '[{"title":"简短任务名","detail":"具体要求/重点","duration_min":60,'
            '"priority":"high|medium|low|none","start_date":"YYYY-MM-DD",'
            '"due_date":"YYYY-MM-DD"}]。'
            "每个独立任务一条；同一任务的补充说明不要拆开。\n\n"
            f"用户原话：{cleaned}"
        )
        content = self._chat(
            credentials,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1600,
        )
        value = content.strip()
        if value.startswith("```"):
            value = value.split("```", 2)[1]
            if value.startswith("json"):
                value = value[4:]
        data = json.loads(value.strip())
        if isinstance(data, dict):
            data = data.get("items") or data.get("tasks") or []
        today = date.today().isoformat()
        results: list[dict[str, Any]] = []
        for item in data if isinstance(data, list) else []:
            if not isinstance(item, dict):
                continue
            detail = str(item.get("detail") or "").strip()[:1000]
            title = str(item.get("title") or "").strip()[:80]
            if not title:
                title = _clean_title(detail)
            try:
                duration = max(5, min(600, int(item.get("duration_min") or 60)))
            except (TypeError, ValueError):
                duration = 60
            priority = str(item.get("priority") or "none")
            if priority not in PRIORITY_LABELS:
                priority = "none"
            start = str(item.get("start_date") or today)
            due = str(item.get("due_date") or "")
            try:
                date.fromisoformat(start)
            except ValueError:
                start = today
            try:
                date.fromisoformat(due)
            except ValueError:
                due = _parse_date(detail or title).isoformat()
            results.append(
                {
                    "title": title,
                    "detail": detail or title,
                    "duration_min": duration,
                    "priority": priority,
                    "start_date": start,
                    "due_date": due,
                    "remind_at": None,
                }
            )
        if not results:
            raise ValueError("模型没有提取到任务，请换个说法或关闭模型开关")
        return results

    def public_task(self, task: dict[str, Any]) -> dict[str, Any]:
        item = dict(task)
        item["priority_label"] = PRIORITY_LABELS.get(item.get("priority"), "无优先级")
        if (
            item.get("status") == "pending"
            and item.get("due_date")
            and item["due_date"] <= date.today().isoformat()
        ):
            item["priority"] = "high"
            item["priority_label"] = (
                "高优先级（已逾期）"
                if item["due_date"] < date.today().isoformat()
                else "高优先级（今日截止）"
            )
        return item

    # ------------------------------------------------------------------
    # 图片预处理（混合模式：只保存去元数据后的校内图片）
    # ------------------------------------------------------------------
    def preprocess_image(self, image_base64: str, owner_id: str) -> tuple[Path, bytes]:
        payload = image_base64.split(",", 1)[-1]
        try:
            raw = base64.b64decode(payload, validate=True)
        except Exception as exc:  # noqa: BLE001
            raise ValueError("图片编码不正确") from exc
        if len(raw) > 12 * 1024 * 1024:
            raise ValueError("图片不能超过 12MB")
        try:
            image = Image.open(io.BytesIO(raw))
            image = ImageOps.exif_transpose(image).convert("RGB")
        except Exception as exc:  # noqa: BLE001
            raise ValueError("无法读取图片，请换一张 JPG/PNG") from exc
        image.thumbnail((1600, 1600))
        owner_dir = self.settings.learning_images_path / owner_id
        owner_dir.mkdir(parents=True, exist_ok=True)
        target = owner_dir / f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{id(image)}.jpg"
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=88, optimize=True)
        data = buffer.getvalue()
        target.write_bytes(data)
        return target, data

    def _image_data_url(self, path: str | None) -> str | None:
        if not path:
            return None
        file = Path(path)
        if not file.exists():
            return None
        encoded = base64.b64encode(file.read_bytes()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    # ------------------------------------------------------------------
    # 视觉提取
    # ------------------------------------------------------------------
    def _chat(
        self,
        credentials: dict[str, str],
        *,
        messages: list[dict[str, Any]],
        max_tokens: int = 1200,
    ) -> str:
        base = credentials["base_url"].rstrip("/")
        with httpx.Client(timeout=self.settings.learning_vision_timeout_seconds) as client:
            response = client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {credentials['api_key']}"},
                json={
                    "model": credentials["model"],
                    "messages": messages,
                    "temperature": 0.1,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            data = response.json()
            choice = data["choices"][0]
            content = str(choice["message"].get("content") or "")
            if not content.strip():
                finish = choice.get("finish_reason") or "unknown"
                reasoning = len(choice["message"].get("reasoning_content") or "")
                raise ValueError(
                    f"模型未返回正文（finish_reason={finish}，reasoning_chars={reasoning}）；"
                    "可能是推理 token 用尽或当前模型不支持图片输入"
                )
            return content

    def _http_extraction(
        self,
        image_data: bytes,
        text: str | None,
        credentials: dict[str, str],
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        encoded = base64.b64encode(image_data).decode("ascii")
        prompt = (
            "你是校园错题本助手。识别图片中的一道题目，返回严格 JSON："
            '{"question_text":"题干","options":["A...","B..."],'
            '"question_bbox":[x1,y1,x2,y2],'
            '"reference_answer":"答案","analysis":"逐步解析",'
            '"knowledge_points":"知识点","difficulty":"简单/中等/困难"}。'
            "解析要分步骤、换行清晰；数学公式用 $...$ LaTeX，"
            "化学式用 \\ce{...}（例如 \\ce{H2SO4}），不要输出乱码。"
            "question_bbox 是题目区域在原图中的归一化坐标（0-1），没有则为 null。"
            "只返回 JSON，不要 Markdown。图片可能包含多题，只取最清晰的一题。"
        )
        if text:
            prompt += f"\n学生补充文字：{text}"
        content = self._chat(
            credentials,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                        },
                    ],
                }
            ],
            # DeepSeek 推理型模型会先消耗 reasoning token；1400 会被推理吃光，
            # 正文变空。默认给足额度，前端可按图片调整。
            max_tokens=max(512, min(32768, int(max_tokens or 4096))),
        )
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```", 2)[1]
            if content.startswith("json"):
                content = content[4:]
        data = json.loads(content.strip())
        return {
            "question_text": str(data.get("question_text") or "未识别出题干"),
            "options": list(data.get("options") or []),
            "question_bbox": data.get("question_bbox"),
            "reference_answer": str(data.get("reference_answer") or ""),
            "analysis": str(data.get("analysis") or ""),
            "knowledge_points": str(data.get("knowledge_points") or ""),
            "difficulty": str(data.get("difficulty") or "中等"),
        }

    def _http_text_extraction(self, text: str, credentials: dict[str, str]) -> dict[str, Any]:
        prompt = (
            "你是校园错题本助手。把下面的题目整理成严格 JSON："
            '{"question_text":"题干","options":["A...","B..."],'
            '"reference_answer":"答案","analysis":"逐步解析",'
            '"knowledge_points":"知识点","difficulty":"简单/中等/困难"}。'
            "解析要分步骤、换行清晰；数学公式用 $...$ LaTeX，"
            "化学式用 \\ce{...}（例如 \\ce{H2SO4}），不要输出乱码。"
            "只返回 JSON，不要 Markdown。\n\n题目："
            f"{text}"
        )
        content = self._chat(
            credentials,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2500,
        )
        return self._parse_extraction(content)

    def _parse_extraction(self, content: str) -> dict[str, Any]:
        value = content.strip()
        if value.startswith("```"):
            value = value.split("```", 2)[1]
            if value.startswith("json"):
                value = value[4:]
        data = json.loads(value.strip())
        return {
            "question_text": str(data.get("question_text") or "未识别出题干"),
            "options": list(data.get("options") or []),
            "question_bbox": data.get("question_bbox"),
            "reference_answer": str(data.get("reference_answer") or ""),
            "analysis": str(data.get("analysis") or ""),
            "knowledge_points": str(data.get("knowledge_points") or ""),
            "difficulty": str(data.get("difficulty") or "中等"),
        }

    def _crop_question(self, image_path: Path, bbox: Any) -> Path | None:
        """按模型返回的归一化 bbox 裁出题图；失败则保留原图。"""
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            return None
        try:
            x1, y1, x2, y2 = (float(value) for value in bbox)
        except (TypeError, ValueError):
            return None
        try:
            image = Image.open(image_path).convert("RGB")
        except Exception:  # noqa: BLE001
            return None
        width, height = image.size
        left, right = sorted((max(0, x1), min(1, x2)))
        top, bottom = sorted((max(0, y1), min(1, y2)))
        if right - left < 0.05 or bottom - top < 0.05:
            return None
        crop = image.crop(
            (
                int(left * width),
                int(top * height),
                int(right * width),
                int(bottom * height),
            )
        )
        target = image_path.with_name(f"{image_path.stem}-question.jpg")
        crop.save(target, format="JPEG", quality=90, optimize=True)
        return target

    def create_question(
        self,
        owner_id: str,
        *,
        library_id: str,
        text: str | None = None,
        image_base64: str | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        library = self.store.get_library(library_id, owner_id)
        if library is None:
            raise LookupError("错题本不存在")
        credentials = self.credentials(owner_id)
        if credentials is None:
            raise ValueError("请先在「模型设置」中新增配置并测试连接，测试通过后才能识别")
        image_path: Path | None = None
        image_data: bytes | None = None
        if image_base64:
            image_path, image_data = self.preprocess_image(image_base64, owner_id)
        try:
            if image_data:
                extracted = self._http_extraction(
                    image_data, text, credentials, max_tokens=max_tokens
                )
            else:
                extracted = self._http_text_extraction(text or "", credentials)
        except Exception as exc:  # noqa: BLE001
            detail = str(exc).strip()[:240]
            raise ValueError(
                f"视觉模型调用失败：{detail or '请检查 Key、Base URL 与模型名'}"
            ) from exc
        if image_path and extracted.get("question_bbox"):
            cropped = self._crop_question(image_path, extracted["question_bbox"])
            if cropped is not None:
                image_path = cropped
        question = self.store.create_question(
            library_id=library_id,
            owner_id=owner_id,
            question_text=extracted["question_text"],
            image_path=str(image_path) if image_path else None,
            options=extracted["options"],
            reference_answer=extracted["reference_answer"],
            analysis=extracted["analysis"],
            knowledge_points=extracted["knowledge_points"],
            difficulty=extracted["difficulty"],
        )
        return self.public_question(question)

    def public_question(self, question: dict[str, Any], *, include_answer: bool = False) -> dict[str, Any]:
        item = {
            "id": question["id"],
            "library_id": question["library_id"],
            "question_text": question["question_text"],
            "options": json.loads(question.get("options_json") or "[]"),
            "knowledge_points": question.get("knowledge_points") or "",
            "difficulty": question.get("difficulty") or "中等",
            "image_url": self._image_data_url(question.get("image_path")),
            "created_at": question.get("created_at"),
            "review_due": question.get("review_due") or "",
            "review_streak": int(question.get("review_streak") or 0),
            "last_reviewed_at": question.get("last_reviewed_at"),
            "deleted_at": question.get("deleted_at"),
            "purge_at": question.get("purge_at"),
            "vision_mode": self.vision_mode(question["owner_id"]),
        }
        if include_answer:
            item.update(
                {
                    "reference_answer": question.get("reference_answer") or "",
                    "analysis": question.get("analysis") or "",
                    "vision_mode": self.vision_mode(question["owner_id"]),
                }
            )
        return item

    def grade(
        self,
        question: dict[str, Any],
        answer_text: str,
        owner_id: str,
    ) -> dict[str, Any]:
        credentials = self.credentials(owner_id)
        if credentials is None:
            raise ValueError("请先在「模型设置」中新增配置并测试连接，测试通过后才能批改")
        if not answer_text.strip():
            raise ValueError("还没有写解答，先写下你的思路")
        prompt = (
            "你是严谨的校园错题批改老师。根据题目、参考答案和解析，批改学生作答。"
            "必须返回严格 JSON："
            '{"correctness":"correct|partial|incorrect","score":0到1,'
            '"feedback":"总体反馈","steps":[{"step":"步骤","status":"done|needs_work",'
            '"comment":"具体点评"}]}。只返回 JSON。\n\n'
            f"题目：{question.get('question_text')}\n"
            f"参考答案：{question.get('reference_answer')}\n"
            f"参考解析：{question.get('analysis')}\n"
            f"学生作答：{answer_text}"
        )
        try:
            content = self._chat(
                credentials,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
            )
        except Exception as exc:  # noqa: BLE001
            raise ValueError("批改模型调用失败，请检查 Key、Base URL 与模型名") from exc
        value = content.strip()
        if value.startswith("```"):
            value = value.split("```", 2)[1]
            if value.startswith("json"):
                value = value[4:]
        data = json.loads(value.strip())
        correctness = str(data.get("correctness") or "partial")
        if correctness not in {"correct", "partial", "incorrect"}:
            correctness = "partial"
        score = max(0.0, min(1.0, float(data.get("score") or 0)))
        return {
            "correctness": correctness,
            "score": score,
            "feedback": str(data.get("feedback") or ""),
            "steps": list(data.get("steps") or []),
            "reference_answer": question.get("reference_answer") or "",
            "analysis": question.get("analysis") or "",
            "mode": "http",
        }

    # ------------------------------------------------------------------
    # 专注
    # ------------------------------------------------------------------
    def encouragement(self, actual_min: int, planned_min: int) -> str:
        now = datetime.now()
        if now.hour >= 23 or now.hour < 4:
            return "已经这么晚了，今天的专注先到这里，去睡觉吧。"
        if 4 <= now.hour < 6:
            return "这么早就开始学了，今天的状态会很不一样。"
        if actual_min < planned_min:
            return f"比计划提前 {planned_min - actual_min} 分钟完成，保持这个节奏。"
        if actual_min > planned_min:
            return f"比计划多用了 {actual_min - planned_min} 分钟，记下来，下次估时更准。"
        return "刚好按计划完成，节奏很稳。"

    def parse_courses(self, text: str) -> list[dict[str, Any]]:
        """从简单课表文本解析课程，例如：周一 08:00-09:40 高等数学 A101。"""
        pattern = re.compile(
            r"(?:周|星期)([一二三四五六日天])\s*"
            r"(\d{1,2}:\d{2})\s*[-~至]\s*(\d{1,2}:\d{2})\s+(.+)"
        )
        courses: list[dict[str, Any]] = []
        for line in re.split(r"[\n;；]+", text):
            match = pattern.search(line.strip())
            if not match:
                continue
            weekday = WEEKDAY_MAP[match.group(1)] + 1
            rest = match.group(4).strip()
            week_match = re.search(
                r"(?:第)?(\d{1,2})\s*[-~到]\s*(\d{1,2})\s*周", rest
            ) or re.search(r"(?:第)?(\d{1,2})\s*周", rest)
            weeks = ""
            if week_match:
                weeks = (
                    f"{week_match.group(1)}-{week_match.group(2)}"
                    if week_match.lastindex and week_match.lastindex >= 2
                    else week_match.group(1)
                )
            parity = "odd" if "单周" in rest else "even" if "双周" in rest else "all"
            rest = re.sub(
                r"(?:第)?\d{1,2}\s*(?:[-~到]\s*\d{1,2})?\s*周|单周|双周",
                "",
                rest,
            ).strip()
            parts = re.split(r"\s+", rest, maxsplit=1)
            courses.append(
                {
                    "name": parts[0][:60],
                    "teacher": "",
                    "weekday": weekday,
                    "start_time": match.group(2),
                    "end_time": match.group(3),
                    "location": parts[1][:60] if len(parts) > 1 else "",
                    "weeks": weeks,
                    "week_parity": parity,
                    "assignment": "",
                }
            )
        return courses

    def teachback(
        self,
        question: dict[str, Any],
        explanation: str,
        owner_id: str,
    ) -> dict[str, Any]:
        """让学生用自己的话复述，检查概念而不是只对答案。"""
        credentials = self.credentials(owner_id)
        if credentials is None:
            raise ValueError("请先在「模型设置」中配置并测试模型")
        if not explanation.strip():
            raise ValueError("先写下你的复述")
        prompt = (
            "你是校园学习教练。学生正在用自己的话复述一道错题的概念/解法。"
            "不要只对最终答案，重点检查概念是否讲对、步骤是否完整。"
            "严格返回 JSON："
            '{"score":0到1,"verdict":"understood|partial|not_yet",'
            '"feedback":"总体评价","good":["讲对的点"],'
            '"missing":["漏掉的点"],"misconceptions":["讲错的概念"]}。'
            "只返回 JSON。\n\n"
            f"题目：{question.get('question_text')}\n"
            f"参考解析：{question.get('analysis')}\n"
            f"学生复述：{explanation}"
        )
        content = self._chat(
            credentials,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=900,
        )
        value = content.strip()
        if value.startswith("```"):
            value = value.split("```", 2)[1]
            if value.startswith("json"):
                value = value[4:]
        data = json.loads(value.strip())
        return {
            "score": max(0.0, min(1.0, float(data.get("score") or 0))),
            "verdict": str(data.get("verdict") or "partial"),
            "feedback": str(data.get("feedback") or ""),
            "good": list(data.get("good") or []),
            "missing": list(data.get("missing") or []),
            "misconceptions": list(data.get("misconceptions") or []),
        }

    # ------------------------------------------------------------------
    # 作业提取
    # ------------------------------------------------------------------
    def extract_assignments(
        self,
        owner_id: str,
        *,
        text: str | None = None,
        image_base64: str | None = None,
    ) -> list[dict[str, Any]]:
        credentials = self.credentials(owner_id)
        if credentials is None:
            raise ValueError("请先在「模型设置」中配置并测试模型")
        if not text and not image_base64:
            raise ValueError("请粘贴作业文字或上传作业图片")
        prompt = (
            "从下面的作业通知中提取每一项作业，严格返回 JSON 数组："
            '[{"title":"作业标题","course":"课程","due_date":"YYYY-MM-DD",'
            '"detail":"要求/页码/提交方式"}]。'
            "没有明确日期时 due_date 用空字符串。只返回 JSON，不要 Markdown。"
        )
        if image_base64:
            _path, image_data = self.preprocess_image(image_base64, owner_id)
            encoded = base64.b64encode(image_data).decode("ascii")
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                        },
                    ],
                }
            ]
        else:
            messages = [
                {
                    "role": "user",
                    "content": f"{prompt}\n\n作业通知：\n{text}",
                }
            ]
        content = self._chat(credentials, messages=messages, max_tokens=1200)
        value = content.strip()
        if value.startswith("```"):
            value = value.split("```", 2)[1]
            if value.startswith("json"):
                value = value[4:]
        data = json.loads(value.strip())
        if isinstance(data, dict):
            data = data.get("items") or data.get("assignments") or []
        results: list[dict[str, Any]] = []
        default_due = (date.today() + timedelta(days=7)).isoformat()
        for item in data if isinstance(data, list) else []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "作业").strip()[:80]
            due = str(item.get("due_date") or "").strip()
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due):
                due = default_due
            results.append(
                {
                    "title": title,
                    "course": str(item.get("course") or "").strip()[:60],
                    "due_date": due,
                    "detail": str(item.get("detail") or "").strip()[:500],
                }
            )
        if not results:
            raise ValueError("没有从内容中提取到作业")
        return results

    # ------------------------------------------------------------------
    # 间隔重复
    # ------------------------------------------------------------------
    def review_due(self, owner_id: str) -> dict[str, Any]:
        today = date.today().isoformat()
        questions = self.store.list_due_questions(owner_id, today)
        return {
            "items": [self.public_question(question) for question in questions],
            "summary": self.store.review_summary(owner_id, today),
        }

    def schedule_review(
        self,
        owner_id: str,
        question: dict[str, Any],
        correctness: str,
    ) -> dict[str, Any]:
        streak = int(question.get("review_streak") or 0)
        if correctness == "correct":
            streak += 1
            interval = {1: 3, 2: 7, 3: 14}.get(streak, 30)
        elif correctness == "partial":
            streak = max(0, streak)
            interval = 1
        else:
            streak = 0
            interval = 1
        due = (date.today() + timedelta(days=interval)).isoformat()
        self.store.update_question_review(
            question["id"],
            owner_id,
            due=due,
            streak=streak,
            reviewed_at=date.today().isoformat(),
        )
        return {"due": due, "streak": streak, "interval_days": interval}

    # ------------------------------------------------------------------
    # 课程资料
    # ------------------------------------------------------------------
    def list_materials(self, owner_id: str, course_id: str) -> list[dict[str, Any]]:
        if self.store.get_course(course_id, owner_id) is None:
            raise LookupError("课程不存在")
        return [
            {
                "id": item["id"],
                "title": item["title"],
                "content": item["content"],
                "created_at": item["created_at"],
            }
            for item in self.store.list_course_materials(owner_id, course_id)
        ]

    def add_material(
        self,
        owner_id: str,
        course_id: str,
        *,
        title: str,
        content: str,
    ) -> dict[str, Any]:
        if self.store.get_course(course_id, owner_id) is None:
            raise LookupError("课程不存在")
        if not content.strip():
            raise ValueError("资料内容不能为空")
        item = self.store.add_course_material(owner_id, course_id, title, content)
        return {"id": item["id"], "title": item["title"], "created_at": item["created_at"]}

    def add_material_file(
        self,
        owner_id: str,
        course_id: str,
        *,
        filename: str,
        data: bytes,
    ) -> dict[str, Any]:
        if self.store.get_course(course_id, owner_id) is None:
            raise LookupError("课程不存在")
        if len(data) > 10 * 1024 * 1024:
            raise ValueError("文件不能超过 10MB")
        suffix = Path(filename).suffix.lower()
        if suffix == ".docx":
            from docx import Document  # type: ignore[import-not-found]
            from io import BytesIO

            document = Document(BytesIO(data))
            content = "\n".join(
                paragraph.text.strip()
                for paragraph in document.paragraphs
                if paragraph.text.strip()
            )
        elif suffix == ".pdf":
            from io import BytesIO

            from pypdf import PdfReader  # type: ignore[import-not-found]

            reader = PdfReader(BytesIO(data))
            content = "\n".join((page.extract_text() or "") for page in reader.pages)
        elif suffix in {".txt", ".md"}:
            content = data.decode("utf-8", errors="replace")
        else:
            raise ValueError("只支持 .docx / .pdf / .txt / .md")
        content = content.strip()
        if not content:
            raise ValueError("没有从文件中提取到文本")
        if len(content) > 50000:
            content = content[:50000]
        return self.add_material(
            owner_id,
            course_id,
            title=Path(filename).stem[:120] or "课程资料",
            content=content,
        )

    def search_materials(
        self,
        owner_id: str,
        course_id: str,
        query: str,
    ) -> list[dict[str, Any]]:
        materials = self.store.list_course_materials(owner_id, course_id)
        if not materials:
            return []
        chunks = [
            KnowledgeChunk(
                chunk_id=item["id"],
                doc_id=item["id"],
                doc_title=item["title"],
                chapter="课程资料",
                category="课程资料",
                chunk_index=0,
                content=item["content"],
            )
            for item in materials
        ]
        index = TfidfVectorIndex(chunks)
        hits = index.search(query, top_k=5) if query.strip() else []
        by_id = {item["id"]: item for item in materials}
        results = []
        for hit in hits:
            item = by_id[hit.doc_id]
            results.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "snippet": item["content"][:240],
                    "score": hit.score,
                }
            )
        return results

    # ------------------------------------------------------------------
    # 学习报告
    # ------------------------------------------------------------------
    def learning_report(self, owner_id: str, days: int = 7) -> dict[str, Any]:
        days = max(1, min(30, int(days)))
        today = date.today()
        start = today - timedelta(days=days - 1)
        sessions = self.store.focus_between(owner_id, start.isoformat(), today.isoformat())
        focus_minutes = sum(int(item.get("actual_min") or 0) for item in sessions)
        focus_days = len({str(item.get("started_at", ""))[:10] for item in sessions})
        tasks = self.store.task_summary(owner_id)
        review = self.store.review_summary(owner_id, today.isoformat())
        questions = self.store.list_all_questions(owner_id)
        points: dict[str, int] = {}
        for question in questions:
            for point in (question.get("knowledge_points") or "").replace("、", ",").split(","):
                point = point.strip()
                if point:
                    points[point] = points.get(point, 0) + 1
        top_points = [
            {"name": name, "count": count}
            for name, count in sorted(points.items(), key=lambda item: item[1], reverse=True)[:8]
        ]
        return {
            "days": days,
            "start": start.isoformat(),
            "end": today.isoformat(),
            "focus_minutes": focus_minutes,
            "focus_sessions": len(sessions),
            "focus_days": focus_days,
            "tasks": tasks,
            "review": review,
            "question_count": len(questions),
            "top_knowledge_points": top_points,
        }

    # ------------------------------------------------------------------
    # 考试周作战室
    # ------------------------------------------------------------------
    def public_exam(self, exam: dict[str, Any]) -> dict[str, Any]:
        try:
            exam_day = date.fromisoformat(exam["exam_date"])
        except (KeyError, ValueError):
            exam_day = date.today()
        days_left = (exam_day - date.today()).days
        urgency = "critical" if days_left <= 2 else "soon" if days_left <= 7 else "normal"
        return {
            "id": exam["id"],
            "course_name": exam["course_name"],
            "exam_date": exam["exam_date"],
            "start_time": exam["start_time"],
            "location": exam["location"],
            "note": exam["note"],
            "days_left": days_left,
            "urgency": urgency,
        }

    def create_exam(self, owner_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return self.public_exam(self.store.create_exam(owner_id, data))

    def exam_room(self, owner_id: str) -> dict[str, Any]:
        exams = [self.public_exam(exam) for exam in self.store.list_exams(owner_id)]
        questions = self.store.list_all_questions(owner_id)
        tasks = [
            self.public_task(task)
            for task in self.store.list_tasks(owner_id)
            if task.get("source_exam_id")
        ]
        upcoming = [exam for exam in exams if exam["days_left"] >= 0]
        points = sorted(
            {
                point.strip()
                for question in questions
                for point in (question.get("knowledge_points") or "").replace("、", ",").split(",")
                if point.strip()
            }
        )[:20]
        return {
            "exams": exams,
            "next_exam": min(upcoming, key=lambda item: item["exam_date"]) if upcoming else None,
            "tasks": tasks,
            "today_tasks": [
                task for task in tasks if task["due_date"] == date.today().isoformat()
            ],
            "wrong_question_count": len(questions),
            "knowledge_points": points,
        }

    def generate_exam_plan(self, owner_id: str, exam_id: str) -> dict[str, Any]:
        exam = self.store.get_exam(exam_id, owner_id)
        if exam is None:
            raise LookupError("考试不存在")
        public = self.public_exam(exam)
        if public["days_left"] < 0:
            raise ValueError("这场考试已经结束，不能生成计划")
        self.store.delete_pending_exam_tasks(owner_id, exam_id)
        questions = self.store.list_all_questions(owner_id)
        points = [
            point.strip()
            for question in questions
            for point in (question.get("knowledge_points") or "").replace("、", ",").split(",")
            if point.strip()
        ]
        start = date.today()
        exam_day = date.fromisoformat(exam["exam_date"])
        end = exam_day - timedelta(days=1)
        if end < start:
            end = start
        total_days = max(1, (end - start).days + 1)
        plan_days = min(total_days, 14)
        tasks: list[dict[str, Any]] = []
        for index in range(plan_days):
            day = start + timedelta(days=index)
            left = (exam_day - day).days
            per_day = max(1, (len(questions) + plan_days - 1) // plan_days) if questions else 1
            title = (
                f"复习 {exam['course_name']}：错题重做 {per_day} 道"
                if questions
                else f"复习 {exam['course_name']}：重点与公式"
            )
            detail = "；".join(points[:5]) if points else "过一遍课程重点，整理仍然模糊的公式/概念"
            tasks.append(
                {
                    "title": title,
                    "detail": detail,
                    "duration_min": 45 if questions else 60,
                    "priority": "high" if left <= 2 else "medium" if left <= 7 else "low",
                    "start_date": day.isoformat(),
                    "due_date": day.isoformat(),
                    "source_exam_id": exam_id,
                }
            )
        created = self.store.create_tasks(owner_id, tasks)
        return {
            "exam": public,
            "items": [self.public_task(task) for task in created],
            "generated_days": plan_days,
            "wrong_question_count": len(questions),
        }

    # ------------------------------------------------------------------
    # 日历
    # ------------------------------------------------------------------
    def calendar_week(self, owner_id: str, start: date) -> dict[str, Any]:
        """返回从 start 起 7 天的课程/任务，供周视图使用。"""
        tasks = self.store.list_tasks(owner_id)
        by_date: dict[str, list[dict[str, Any]]] = {}
        for task in tasks:
            by_date.setdefault(task["due_date"], []).append(self.public_task(task))
        days_data = []
        for offset in range(7):
            current = start + timedelta(days=offset)
            key = current.isoformat()
            days_data.append(
                {
                    "date": key,
                    "day": current.day,
                    "month": current.month,
                    "weekday": current.weekday() + 1,
                    "is_weekend": current.weekday() >= 5,
                    "holiday": HOLIDAYS_2026.get(key),
                    "tasks": by_date.get(key, []),
                }
            )
        return {
            "start": start.isoformat(),
            "end": (start + timedelta(days=6)).isoformat(),
            "days": days_data,
            "courses": self.store.list_courses(owner_id),
            "semester_start": self.store.semester_start(owner_id),
        }

    def calendar_month(self, owner_id: str, year: int, month: int) -> dict[str, Any]:
        first_weekday, days = calendar.monthrange(year, month)
        tasks = self.store.list_tasks(owner_id)
        by_date: dict[str, list[dict[str, Any]]] = {}
        for task in tasks:
            key = task["due_date"]
            by_date.setdefault(key, []).append(self.public_task(task))
        days_data = []
        for day in range(1, days + 1):
            current = date(year, month, day)
            key = current.isoformat()
            days_data.append(
                {
                    "date": key,
                    "day": day,
                    "weekday": current.weekday() + 1,
                    "is_weekend": current.weekday() >= 5,
                    "holiday": HOLIDAYS_2026.get(key),
                    "tasks": by_date.get(key, []),
                }
            )
        return {
            "year": year,
            "month": month,
            "first_weekday": first_weekday,
            "days": days_data,
            "courses": self.store.list_courses(owner_id),
            "semester_start": self.store.semester_start(owner_id),
            "holiday_note": "节假日为 2026 示例数据，正式版接校历。",
        }
