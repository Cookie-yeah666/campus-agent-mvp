"""日志配置。

使用 loguru 统一日志格式：控制台输出保留颜色，文件输出 JSON 友好的
纯文本行；日志同时写入 ``data/app.log``，按天轮转。
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

_CONSOLE_FORMAT = (
    "<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
)
_FILE_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"


def configure_logging(log_file: Path, level: str = "INFO") -> None:
    """重新初始化 loguru 的日志输出。

    Args:
        log_file: 日志文件路径，父目录会自动创建。
        level: 控制台与文件的最低日志级别。
    """
    logger.remove()
    logger.add(sys.stderr, level=level, format=_CONSOLE_FORMAT, colorize=True, enqueue=False)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_file),
        level=level,
        format=_FILE_FORMAT,
        rotation="10 MB",
        retention="14 days",
        encoding="utf-8",
        enqueue=False,
    )


def get_logger(name: str = "campus"):
    """返回带模块标签的 logger。"""
    return logger.bind(module=name)
