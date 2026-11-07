"""把 Excel / CSV 学生名册导入 SQLite 学生库。

示例：
    python scripts/import_students.py \
        --file registry/imports/students_2025_cs.xlsx \
        --cohort 2025 --college 计算机科学与技术学院

其他学院/届只需换 ``--file``、``--cohort``、``--college``；
表头支持中英文别名，重复导入按 (届, 学院, 学号) 更新。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402
from app.student_registry import (  # noqa: E402
    StudentRegistry,
    normalize_student_id,
)

HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "student_id": ("学号", "学生学号", "studentid", "student_id", "id"),
    "name": ("姓名", "name", "学生姓名"),
    "major": ("专业", "major"),
    "class_name": ("班级名称", "班级", "classname", "class_name", "class"),
    "phone": ("手机号码", "手机号", "电话", "phone", "mobile"),
    "gender": ("性别", "gender", "sex"),
    "dorm_building": ("楼宇", "宿舍楼", "building", "dorm_building"),
    "dorm_room": ("房间", "宿舍房间", "room", "dorm_room"),
    "campus": ("校区", "campus"),
    "college": ("学院", "college", "院系"),
    "cohort": ("届", "年级", "cohort", "grade"),
}

REQUIRED = ("student_id", "name", "class_name")


def normalize_header(value: Any) -> str:
    """表头归一化：去空格、下划线、括号，转小写。"""
    text = str(value or "").strip().lower()
    return re.sub(r"[\s_（）()【】\[\]：:]+", "", text)


def build_header_map(headers: Iterable[Any]) -> dict[str, int]:
    """把原始表头映射到规范字段。"""
    normalized = [normalize_header(header) for header in headers]
    mapping: dict[str, int] = {}
    for canonical, aliases in HEADER_ALIASES.items():
        alias_set = {normalize_header(alias) for alias in aliases}
        for index, header in enumerate(normalized):
            if header in alias_set:
                mapping[canonical] = index
                break
    return mapping


def read_table(path: Path, sheet: str | None = None) -> tuple[list[Any], list[list[Any]]]:
    """返回 (表头, 数据行)；支持 xlsx/xlsm/csv。"""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            rows = [list(row) for row in reader]
        if not rows:
            raise ValueError("CSV 为空")
        return rows[0], rows[1:]

    workbook = load_workbook(path, read_only=True, data_only=True)
    worksheet = workbook[sheet] if sheet else workbook.active
    iterator = worksheet.iter_rows(values_only=True)
    try:
        headers = list(next(iterator))
    except StopIteration as error:
        raise ValueError("工作表为空") from error
    rows = [list(row) for row in iterator]
    return headers, rows


def cell(row: list[Any], index: int | None) -> Any:
    """安全取值。"""
    if index is None or index >= len(row):
        return None
    return row[index]


def derive_status(
    student_id: str | None,
    phone_text: str,
    building: str,
) -> tuple[str, str]:
    """依据原始字段推断状态与备注。"""
    notes: list[str] = []
    if not student_id:
        notes.append("原始表学号为空或不是 10 位")
    if phone_text and not re.fullmatch(r"\d{11}", phone_text):
        notes.append(f"原始手机号字段：{phone_text}")
    if "保留入学资格" in building:
        return "retained", "；".join(notes + ["保留入学资格"])
    if "复读" in phone_text:
        return "retaking", "；".join(notes + ["复读"])
    if "港澳台" in phone_text or "不来" in phone_text:
        return "not_arrived", "；".join(notes + ["港澳台/未报到"])
    if not student_id:
        return "missing_id", "；".join(notes)
    return "active", "；".join(notes)


def transform(
    rows: Iterable[list[Any]],
    header_map: dict[str, int],
    *,
    college: str,
    cohort: str,
) -> list[dict[str, Any]]:
    """把原始行转成 registry 需要的结构。"""
    missing = [field for field in REQUIRED if field not in header_map and field != "student_id"]
    if missing:
        labels = {"name": "姓名", "class_name": "班级名称"}
        raise ValueError("缺少必需列：" + "、".join(labels.get(item, item) for item in missing))

    students: list[dict[str, Any]] = []
    for offset, row in enumerate(rows, start=2):
        if all(value is None or str(value).strip() == "" for value in row):
            continue
        raw_id = cell(row, header_map.get("student_id"))
        student_id = normalize_student_id(raw_id)
        name = str(cell(row, header_map.get("name")) or "").strip()
        class_name = str(cell(row, header_map.get("class_name")) or "").strip()
        if not name and not class_name:
            continue
        phone_text = str(cell(row, header_map.get("phone")) or "").strip()
        phone_match = re.search(r"\d{11}", phone_text)
        building = str(cell(row, header_map.get("dorm_building")) or "").strip()
        status, notes = derive_status(student_id, phone_text, building)
        students.append(
            {
                "student_id": student_id,
                "name": name,
                "major": str(cell(row, header_map.get("major")) or "").strip(),
                "class_name": class_name,
                "phone": phone_match.group(0) if phone_match else None,
                "gender": str(cell(row, header_map.get("gender")) or "").strip() or None,
                "dorm_building": building or None,
                "dorm_room": str(cell(row, header_map.get("dorm_room")) or "").strip() or None,
                "campus": str(cell(row, header_map.get("campus")) or "").strip() or None,
                "status": status,
                "notes": notes or None,
                "source_row": offset,
            }
        )
    return students


def file_sha256(path: Path) -> str:
    """文件指纹，用于追责与去重参考。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def archive_source(path: Path, imports_dir: Path) -> Path:
    """把原始文件复制到 registry/imports，使用英文安全文件名。"""
    imports_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^0-9A-Za-z._-]+", "_", path.name)
    target = imports_dir / safe_name
    if target.resolve() != path.resolve():
        shutil.copy2(path, target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="导入学生名册到 SQLite 学生库")
    parser.add_argument("--file", required=True, help="xlsx/xlsm/csv 文件路径")
    parser.add_argument("--cohort", required=True, help="届别，例如 2025")
    parser.add_argument("--college", required=True, help="学院，例如 计算机科学与技术学院")
    parser.add_argument("--sheet", default=None, help="工作表名，默认活动工作表")
    parser.add_argument("--db", default=None, help="覆盖学生库路径")
    parser.add_argument("--replace", action="store_true", help="先清空该学院该届再导入")
    parser.add_argument("--dry-run", action="store_true", help="只解析和统计，不写库")
    parser.add_argument("--no-archive", action="store_true", help="不复制原始文件到 registry/imports")
    args = parser.parse_args()

    source = Path(args.file).expanduser()
    if not source.exists():
        raise SystemExit(f"文件不存在：{source}")

    headers, rows = read_table(source, args.sheet)
    header_map = build_header_map(headers)
    students = transform(rows, header_map, college=args.college, cohort=args.cohort)
    settings = get_settings()
    db_path = Path(args.db) if args.db else settings.student_db_path

    summary = {
        "file": str(source),
        "college": args.college,
        "cohort": args.cohort,
        "rows": len(students),
        "with_id": sum(1 for item in students if item["student_id"] and normalize_student_id(item["student_id"])),
        "missing_id": sum(1 for item in students if not normalize_student_id(item["student_id"])),
        "status": {},
    }
    for item in students:
        summary["status"][item["status"]] = summary["status"].get(item["status"], 0) + 1

    if args.dry_run:
        print("[dry-run] 解析完成，未写库")
        print(summary)
        return

    registry = StudentRegistry(db_path)
    if args.replace:
        deleted = registry.clear_scope(args.college, args.cohort)
        print(f"已清空 {args.college} / {args.cohort}：{deleted} 条")
    archived = source if args.no_archive else archive_source(source, settings.student_imports_dir)
    result = registry.upsert_batch(
        students,
        source_file=archived.name,
        source_sha256=file_sha256(source),
        college=args.college,
        cohort=args.cohort,
    )
    print("导入完成")
    print(f"  批次：{result['batch_id']}")
    print(f"  新增：{result['inserted']}  更新：{result['updated']}  跳过：{result['skipped']}")
    print(f"  需关注：{result['issues']}")
    print(f"  学生库：{db_path}")
    print(f"  原始文件：{archived}")
    stats = registry.stats()
    print(f"  当前总人数：{stats['total']}  学院：{stats['colleges']}  届：{stats['cohorts']}")


if __name__ == "__main__":
    main()
