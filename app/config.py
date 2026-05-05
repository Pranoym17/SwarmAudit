from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SwarmAudit"
    llm_provider: str = "mock"
    llm_base_url: str = "http://localhost:8000/v1"
    llm_api_key: str = "not-needed-for-mock"
    llm_model: str = "Qwen/Qwen2.5-Coder-32B-Instruct"
    max_files: int = 200
    max_file_size_kb: int = 250
    max_chars_per_chunk: int = 12000
    clone_timeout_seconds: int = 60
    clone_base_dir: str = ".swarm_audit_tmp"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
