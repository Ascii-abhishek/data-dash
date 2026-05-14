from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    app_name: str = "Data Dash"
    project_dir: Path = Path(".")
    connections_dir: Path = Path("connections")
    credentials_dir: Path = Path("credentials")
    ui_dir: Path = Path("ui")

    model_config = SettingsConfigDict(env_file=".env", env_prefix="TTD_")

    @model_validator(mode="after")
    def resolve_runtime_paths(self) -> "AppSettings":
        project_dir = _resolve_project_dir(self.project_dir)
        object.__setattr__(self, "project_dir", project_dir)
        object.__setattr__(self, "connections_dir", _resolve_child_path(self.connections_dir, project_dir))
        object.__setattr__(self, "credentials_dir", _resolve_child_path(self.credentials_dir, project_dir))
        object.__setattr__(self, "ui_dir", _resolve_child_path(self.ui_dir, project_dir))
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
