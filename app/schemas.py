from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class Severity(str, Enum):
    critical = "CRITICAL"
    high = "HIGH"
    medium = "MEDIUM"
    low = "LOW"


class AuditRequest(BaseModel):
    repo_url: HttpUrl


class SourceFile(BaseModel):
    path: str
    absolute_path: str
    size_bytes: int
    language: str | None = None


class CodeChunk(BaseModel):
    file_path: str
    language: str | None = None
    line_start: int
    line_end: int
    content: str


class Finding(BaseModel):
    title: str
    severity: Severity
    file_path: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    description: str
    why_it_matters: str
    suggested_fix: str
    agent_source: str


class AgentOutput(BaseModel):
    agent_name: str
    findings: list[Finding] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RepoScanResult(BaseModel):
    repo_url: str
    local_path: str
    files: list[SourceFile]
    skipped_files: int = 0
    warnings: list[str] = Field(default_factory=list)


class AuditReport(BaseModel):
    repo_url: str
    scanned_file_count: int
    skipped_file_count: int
    findings: list[Finding]
    severity_summary: dict[Severity, int]
    total_findings_count: int = 0
    displayed_findings_count: int = 0
    hidden_findings_count: int = 0
    agent_finding_counts: dict[str, int] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agents_run: list[str]
    warnings: list[str] = Field(default_factory=list)


class AuditProgress(BaseModel):
    message: str
    stage: str
