"""审计日志哈希链：正常链、篡改检测。"""

from __future__ import annotations

import json
from pathlib import Path

from app.audit.logger import AuditLogger
from app.config import Settings


def test_audit_hash_chain_detects_tampering(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    logger = AuditLogger(settings)
    logger.record("message", "session-1", None, {"text": "第一"})
    logger.record("message", "session-1", None, {"text": "第二"})

    result = logger.verify_chain()
    assert result["valid"] is True
    assert result["checked"] == 2

    path = next((tmp_path / "audit").glob("audit-*.jsonl"))
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    lines[0]["payload"]["text"] = "被篡改"
    path.write_text(
        "\n".join(json.dumps(line, ensure_ascii=False) for line in lines) + "\n",
        encoding="utf-8",
    )

    broken = logger.verify_chain()
    assert broken["valid"] is False
    assert broken["reason"] == "hash_mismatch"
