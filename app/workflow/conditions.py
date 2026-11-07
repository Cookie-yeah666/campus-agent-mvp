"""工作流分支条件。

条件函数以名称注册，流程定义中只引用名称，实现“流程不写死在代码里”。
"""

from __future__ import annotations

from collections.abc import Callable

from app.models.domain import WorkflowContext

ConditionFn = Callable[[WorkflowContext], bool]
_CONDITIONS: dict[str, ConditionFn] = {}


def condition(name: str) -> Callable[[ConditionFn], ConditionFn]:
    """注册条件函数的装饰器。"""

    def decorator(func: ConditionFn) -> ConditionFn:
        if name in _CONDITIONS:
            raise ValueError(f"条件名称重复: {name}")
        _CONDITIONS[name] = func
        return func

    return decorator


def evaluate(name: str, context: WorkflowContext) -> bool:
    """执行命名条件。

    Raises:
        KeyError: 条件未注册。
    """
    if name not in _CONDITIONS:
        raise KeyError(f"未注册的条件: {name}")
    return bool(_CONDITIONS[name](context))


def available_conditions() -> list[str]:
    """返回全部已注册条件名称。"""
    return sorted(_CONDITIONS)


@condition("student_valid")
def _student_valid(context: WorkflowContext) -> bool:
    """学号查询成功且在籍。"""
    profile = context.get_variable("student_profile") or {}
    return bool(profile.get("valid"))


@condition("student_invalid")
def _student_invalid(context: WorkflowContext) -> bool:
    """学号不存在。"""
    return not _student_valid(context)


@condition("card_lost")
def _card_lost(context: WorkflowContext) -> bool:
    """校园卡已挂失。"""
    status = context.get_variable("loss_status") or {}
    return bool(status.get("lost"))


@condition("card_not_lost")
def _card_not_lost(context: WorkflowContext) -> bool:
    """校园卡未挂失。"""
    return not _card_lost(context)


@condition("has_arrears")
def _has_arrears(context: WorkflowContext) -> bool:
    """存在欠费。"""
    balance = context.get_variable("balance") or {}
    return bool(balance.get("has_arrears"))


@condition("no_arrears")
def _no_arrears(context: WorkflowContext) -> bool:
    """无欠费。"""
    return not _has_arrears(context)


@condition("confirmed")
def _confirmed(context: WorkflowContext) -> bool:
    """用户已确认提交。"""
    return context.confirmed is True


@condition("cancelled")
def _cancelled(context: WorkflowContext) -> bool:
    """用户取消办理。"""
    return context.confirmed is False


@condition("always")
def _always(context: WorkflowContext) -> bool:
    """恒真，用于显式默认分支。"""
    return True


@condition("leave_long")
def _leave_long(context: WorkflowContext) -> bool:
    """请假超过 3 天，需要学院二级审批。"""
    try:
        return int(context.get_variable("leave_days", 0)) > 3
    except (TypeError, ValueError):
        return False
