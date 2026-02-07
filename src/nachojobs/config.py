from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScheduleConfig(BaseModel):
    interval_hours: int = 12
    run_on_startup: bool = True


class OllamaConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    model: str = "llama3.1:8b"
    timeout_seconds: int = 120
    top_k_matches: int = 3


class TargetRoles(BaseModel):
    titles: list[str] = []
    locations: list[str] = []
    employment_types: list[str] = []


class AshbyCompany(BaseModel):
    slug: str
    name: str


class GreenhouseCompany(BaseModel):
    token: str
    name: str


class Companies(BaseModel):
    ashby: list[AshbyCompany] = []
    greenhouse: list[GreenhouseCompany] = []


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NACHOJOBS_",
        env_nested_delimiter="__",
    )

    resume_path: str = "resume/Resume - EM - Chris Bush.pdf"
    output_dir: str = "output"
    freshness_days: int = 14

    schedule: ScheduleConfig = ScheduleConfig()
    ollama: OllamaConfig = OllamaConfig()
    target_roles: TargetRoles = TargetRoles()
    companies: Companies = Companies()


def load_settings(config_path: str | Path = "config.yaml") -> Settings:
    path = Path(config_path)
    if path.exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return Settings(**data)
    return Settings()
