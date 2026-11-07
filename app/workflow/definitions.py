"""声明式工作流注册。

流程定义在 ``workflows/*.json``，本模块只负责加载。
新增流程 = 新增一个 JSON + 可选的新工具/条件，不改引擎。
"""

from __future__ import annotations

from pathlib import Path

from app.models.domain import WorkflowDefinition
from app.workflow.dsl import load_workflows

WORKFLOW_DIR = Path(__file__).resolve().parents[2] / "workflows"
WORKFLOWS: dict[str, WorkflowDefinition] = load_workflows(WORKFLOW_DIR)

CARD_REISSUE_WORKFLOW = WORKFLOWS["card_reissue"]
NETWORK_REPAIR_WORKFLOW = WORKFLOWS["network_repair"]


def get_workflow(workflow_type: str) -> WorkflowDefinition | None:
    """按类型获取工作流定义。"""
    return WORKFLOWS.get(workflow_type)
