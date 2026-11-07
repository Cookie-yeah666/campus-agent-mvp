"""全局配置。

所有可调参数集中在本模块，业务代码不得出现魔法数字。
配置支持通过 ``CAMPUS_`` 前缀的环境变量或 ``.env`` 文件覆盖，
例如 ``CAMPUS_PORT=9000``、``CAMPUS_DATA_DIR=/tmp/campus``。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """应用配置模型（Pydantic Settings）。"""

    model_config = SettingsConfigDict(
        env_prefix="CAMPUS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- 基础信息 ----------
    app_name: str = "知行 · 校园智能服务助手"
    app_version: str = "V26.1108.1"
    app_description: str = "有依据地回答，有回执地办事：双 Agent 校园服务助手"
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8000

    # ---------- 认证与权限 ----------
    auth_enabled: bool = True
    auth_secret: str = "dev-only-change-me-in-production"
    auth_token_ttl_seconds: int = 8 * 60 * 60

    # ---------- 路径 ----------
    data_dir: Path = Field(default=BASE_DIR / "data")
    static_dir: Path = Field(default=BASE_DIR / "static")
    student_registry_dir: Path = Field(default=BASE_DIR / "registry")
    student_registry_db: str = "students.db"
    log_level: str = "INFO"

    # ---------- 会话与记忆 ----------
    session_context_rounds: int = 10
    session_title_length: int = 20
    max_workflow_steps: int = 40

    # ---------- 检索参数 ----------
    chunk_min_chars: int = 500
    chunk_max_chars: int = 800
    chunk_overlap_chars: int = 50
    vector_top_k: int = 20
    keyword_top_k: int = 20
    final_top_k: int = 5
    rrf_k: int = 60
    high_confidence: float = 0.70
    low_confidence: float = 0.45
    rewrite_candidate_count: int = 2

    # ---------- 模型参数 ----------
    llm_model_name: str = "DeepSeek-V3 · Mock"
    llm_temperature: float = 0.30
    llm_max_tokens: int = 800
    llm_simulate_delay: bool = True
    llm_min_delay_ms: int = 220
    llm_max_delay_ms: int = 760

    # ---------- 真实校园接口 ----------
    integration_mode: str = "mock"  # mock | http
    integration_base_url: str = ""
    integration_api_key: str = ""
    integration_timeout_seconds: float = 8.0

    # ---------- 学习空间 ----------
    learning_dir: Path | None = None
    learning_db: str = "learning.db"
    learning_images_dir: str = "learning/images"
    learning_vision_mode: str = "per_user"  # 每个学生自己的 Key
    learning_vision_base_url: str = "https://api.deepseek.com"
    learning_vision_api_key: str = ""
    learning_vision_model: str = "deepseek-flash"
    learning_vision_timeout_seconds: float = 30.0

    # ---------- 工具与工作流 ----------
    tool_timeout_seconds: int = 5
    tool_max_retries: int = 1
    card_reissue_fee: float = 20.0
    tool_simulate_delay: bool = True
    tool_min_delay_ms: int = 120
    tool_max_delay_ms: int = 520
    fault_student_ids: list[str] = Field(default_factory=lambda: ["2025000999"])

    # ---------- 审计与幂等 ----------
    audit_max_memory_records: int = 2000
    idempotency_file: str = "idempotency.json"

    # ---------- 服务 ----------
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    @property
    def sessions_dir(self) -> Path:
        """会话 JSON 存放目录。"""
        return self.data_dir / "sessions"

    @property
    def workorders_dir(self) -> Path:
        """工单 JSON 存放目录。"""
        return self.data_dir / "workorders"

    @property
    def audit_dir(self) -> Path:
        """审计 JSONL 存放目录。"""
        return self.data_dir / "audit"

    @property
    def student_db_path(self) -> Path:
        """学生库 SQLite 文件（独立于可重置的演示数据目录）。"""
        return self.student_registry_dir / self.student_registry_db

    @property
    def student_imports_dir(self) -> Path:
        """原始导入文件留档目录。"""
        return self.student_registry_dir / "imports"

    @property
    def learning_root(self) -> Path:
        """学习数据目录；默认与 data 同级，避免演示重置时被删。"""
        return self.learning_dir or (self.data_dir.parent / "learning_data")

    @property
    def learning_db_path(self) -> Path:
        """学习空间 SQLite 文件。"""
        return self.learning_root / self.learning_db

    @property
    def learning_images_path(self) -> Path:
        """错题图片目录。"""
        return self.learning_root / self.learning_images_dir

    @property
    def log_file(self) -> Path:
        """应用日志文件。"""
        return self.data_dir / "app.log"

    @property
    def idempotency_path(self) -> Path:
        """幂等键映射文件。"""
        return self.data_dir / self.idempotency_file

    def ensure_directories(self) -> None:
        """创建全部运行时目录（幂等）。"""
        for directory in (
            self.data_dir,
            self.sessions_dir,
            self.workorders_dir,
            self.audit_dir,
            self.student_registry_dir,
            self.student_imports_dir,
            self.learning_root,
            self.learning_images_path,
        ):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """返回进程级单例配置。"""
    return Settings()


def reset_settings_cache() -> None:
    """清空配置缓存（测试或热重载时使用）。"""
    get_settings.cache_clear()
