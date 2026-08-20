from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "SiteGit"
    app_env: Literal["development", "production", "test"] = "development"
    api_prefix: str = "/api/v1"
    public_url: str = "http://localhost:8000"
    public_hostname: str = "localhost"
    server_host: str = "127.0.0.1"
    server_port: int = 8000

    sitegit_data_root: Path = REPO_ROOT / "runtime"
    database_url: str | None = None
    seed_state_path: Path = REPO_ROOT / "seed" / "sasang_state.json"
    default_project_id: str = "SASANG-001"

    isaac_adapter_enabled: bool = False
    isaac_adapter_url: str = "http://localhost:8100"

    # 자연어 Work Package Compiler. Ollama는 이 PC에서만 실행하며 외부 API 키가 없습니다.
    llm_provider: Literal["ollama"] = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:8b"
    ollama_timeout_seconds: float = Field(default=90.0, gt=0, le=300)

    jwt_secret: str = Field(default="CHANGE-ME-BEFORE-PUBLIC-ACCESS-1234567890", min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    auth_cookie_name: str = "sitegit_access_token"
    cookie_secure: bool = False

    initial_admin_username: str = "admin"
    initial_admin_password: str = "sitegit-demo-2026"
    initial_admin_name: str = "SiteGit 관리자"
    seed_demo_users: bool = True
    initial_manager_username: str = "manager"
    initial_manager_password: str = "sitegit-manager-2026"
    initial_manager_name: str = "김현장"
    initial_viewer_username: str = "viewer"
    initial_viewer_password: str = "sitegit-viewer-2026"
    initial_viewer_name: str = "현장 조회자"

    state_save_debounce_ms: int = 800

    @field_validator("sitegit_data_root", "seed_state_path", mode="after")
    @classmethod
    def _anchor_to_repo_root(cls, value: Path) -> Path:
        """Anchor relative paths at the repository root instead of the CWD.

        외장 SSD를 들고 다니면 드라이브 문자가 PC마다 달라지므로 `.env`에는
        `../SiteGitData` 같은 상대경로를 넣습니다. 이때 실행 위치에 따라 다른
        폴더를 가리키면 빈 DB가 조용히 새로 생기므로 항상 저장소 기준으로
        고정합니다. `isaac_adapter/map_publisher.py`도 같은 규칙을 씁니다.
        """
        return (value if value.is_absolute() else REPO_ROOT / value).resolve()

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        db_path = (self.sitegit_data_root / "database" / "sitegit.db").resolve()
        return f"sqlite:///{db_path.as_posix()}"

    @property
    def frontend_dir(self) -> Path:
        return REPO_ROOT / "frontend"

    @property
    def policy_dir(self) -> Path:
        return REPO_ROOT / "policies"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    for name in ("database", "evidence", "isaac", "site_plans", "logs", "backups"):
        (settings.sitegit_data_root / name).mkdir(parents=True, exist_ok=True)
    return settings
