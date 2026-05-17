from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    APP_NAME: str = Field("Data Dash", validation_alias=AliasChoices("TTD_APP_NAME", "APP_NAME"))
    PROJECT_DIR: Path = Field(Path("."), validation_alias=AliasChoices("TTD_PROJECT_DIR", "PROJECT_DIR"))
    CONNECTIONS_DIR: Path = Field(Path("connections"), validation_alias=AliasChoices("TTD_CONNECTIONS_DIR", "CONNECTIONS_DIR"))
    CREDENTIALS_DIR: Path = Field(Path("credentials"), validation_alias=AliasChoices("TTD_CREDENTIALS_DIR", "CREDENTIALS_DIR"))
    UI_DIR: Path = Field(Path("ui"), validation_alias=AliasChoices("TTD_UI_DIR", "UI_DIR"))
    MEMORY_DIR: Path = Field(Path("memory"), validation_alias=AliasChoices("TTD_MEMORY_DIR", "MEMORY_DIR"))
    LOGS_DIR: Path = Field(Path("logs"), validation_alias=AliasChoices("TTD_LOGS_DIR", "LOGS_DIR"))
    LLM_PROVIDER: str = Field("groq", validation_alias=AliasChoices("TTD_LLM_PROVIDER", "LLM_PROVIDER"))
    GROQ_API_KEY: str | None = Field(None, validation_alias=AliasChoices("TTD_GROQ_API_KEY", "GROQ_API_KEY"))
    GROQ_MODEL: str = Field(
        "llama-3.3-70b-versatile",
        validation_alias=AliasChoices("TTD_GROQ_MODEL", "GROQ_MODEL"),
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def resolve_runtime_paths(self) -> "AppSettings":
        project_dir = _resolve_project_dir(self.PROJECT_DIR)
        object.__setattr__(self, "PROJECT_DIR", project_dir)
        object.__setattr__(self, "CONNECTIONS_DIR", _resolve_child_path(self.CONNECTIONS_DIR, project_dir))
        object.__setattr__(self, "CREDENTIALS_DIR", _resolve_child_path(self.CREDENTIALS_DIR, project_dir))
        object.__setattr__(self, "UI_DIR", _resolve_child_path(self.UI_DIR, project_dir))
        object.__setattr__(self, "MEMORY_DIR", _resolve_child_path(self.MEMORY_DIR, project_dir))
        object.__setattr__(self, "LOGS_DIR", _resolve_child_path(self.LOGS_DIR, project_dir))
        return self


def _resolve_project_dir(path: Path) -> Path:
    if path.is_absolute():
        return path.expanduser().resolve()
    if path != Path("."):
        return (Path.cwd() / path).expanduser().resolve()
    return _discover_project_dir()


def _resolve_child_path(path: Path, project_dir: Path) -> Path:
    if path.is_absolute():
        return path.expanduser().resolve()
    return (project_dir / path).expanduser().resolve()


def _discover_project_dir() -> Path:
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "src" / "tick_ticker_dash").exists():
            return candidate
    return current


settings = AppSettings()
