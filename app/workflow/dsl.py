"""声明式工作流 DSL。

流程不再写死在 Python 里，而是从 JSON 文件加载为
:class:`WorkflowDefinition`。第一版只支持现有引擎已有节点类型：
start / parameter_extract / tool_call / condition / confirmation /
result / human_handoff / end。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models.domain import WorkflowDefinition
from app.workflow import conditions


class DSLValidationError(ValueError):
    """DSL 定义不合法。"""


def validate_definition(data: dict[str, Any]) -> None:
    """校验节点/边引用，避免到运行时才报错。"""
    for key in ("id", "name", "start_node", "nodes"):
        if not data.get(key):
            raise DSLValidationError(f"缺少字段: {key}")
    node_ids = [node.get("id") for node in data["nodes"]]
    if len(node_ids) != len(set(node_ids)):
        raise DSLValidationError("节点 id 重复")
    if data["start_node"] not in node_ids:
        raise DSLValidationError("start_node 不在 nodes 中")
    known_conditions = set(conditions.available_conditions())
    for edge in data.get("edges", []):
        source = edge.get("source")
        target = edge.get("target")
        if source not in node_ids:
            raise DSLValidationError(f"边 source 不存在: {source}")
        if target not in node_ids:
            raise DSLValidationError(f"边 target 不存在: {target}")
        condition = edge.get("condition")
        if condition and condition not in known_conditions:
            raise DSLValidationError(f"未注册的条件: {condition}")


def load_definition(path: Path) -> WorkflowDefinition:
    """从 JSON 文件加载并校验流程定义。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_definition(data)
    return WorkflowDefinition.model_validate(data)


def load_workflows(directory: Path) -> dict[str, WorkflowDefinition]:
    """加载目录下全部 ``*.json`` 流程定义。"""
    definitions: dict[str, WorkflowDefinition] = {}
    for path in sorted(directory.glob("*.json")):
        definition = load_definition(path)
        if definition.id in definitions:
            raise DSLValidationError(f"流程 id 重复: {definition.id}")
        definitions[definition.id] = definition
    return definitions
