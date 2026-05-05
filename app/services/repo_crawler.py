import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from git import Repo

from app.config import Settings
from app.schemas import RepoScanResult, SourceFile


IGNORED_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    ".venv",
    "__pycache__",
    "vendor",
    "target",
    ".next",
}

SUPPORTED_EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript React",
    ".jsx": "JavaScript React",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".cpp": "C++",
    ".c": "C",
    ".cs": "C#",
    ".php": "PHP",
    ".rb": "Ruby",
}


def validate_github_url(repo_url: str) -> str:
    parsed = urlparse(repo_url)
    if parsed.scheme not in {"https", "http"}:
        raise ValueError("Only HTTP(S) GitHub URLs are supported.")
    if parsed.netloc.lower() != "github.com":
        raise ValueError("Only public github.com repository URLs are supported.")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise ValueError("GitHub URL must include owner and repo name.")

    owner, repo = parts[0], parts[1].removesuffix(".git")
    return f"https://github.com/{owner}/{repo}.git"


class RepoCrawler:
    def __init__(self, settings: Settings):
        self.settings = settings

    def clone_and_scan(self, repo_url: str) -> RepoScanResult:
        clone_url = validate_github_url(repo_url)
        temp_root = Path(tempfile.mkdtemp(prefix="swarm_audit_"))
        repo_path = temp_root / "repo"

        try:
            Repo.clone_from(
                clone_url,
                repo_path,
                depth=1,
                single_branch=True,
                kill_after_timeout=self.settings.clone_timeout_seconds,
                env={"GIT_TERMINAL_PROMPT": "0"},
                multi_options=["--filter=blob:none"],
            )
            return self.scan_local_repo(repo_url=repo_url, repo_path=repo_path)
        except Exception:
            shutil.rmtree(temp_root, ignore_errors=True)
            raise

    def scan_local_repo(self, repo_url: str, repo_path: Path) -> RepoScanResult:
        files: list[SourceFile] = []
        skipped = 0
        warnings: list[str] = []
        max_bytes = self.settings.max_file_size_kb * 1024

        for path in repo_path.rglob("*"):
            if not path.is_file():
                continue
            rel_path = path.relative_to(repo_path)
            if any(part in IGNORED_DIRS for part in rel_path.parts):
                skipped += 1
                continue
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                skipped += 1
                continue
            size = path.stat().st_size
            if size > max_bytes:
                skipped += 1
                warnings.append(f"Skipped large file: {rel_path}")
                continue
            if len(files) >= self.settings.max_files:
                skipped += 1
                continue

            files.append(
                SourceFile(
                    path=str(rel_path).replace("\\", "/"),
                    absolute_path=str(path),
                    size_bytes=size,
                    language=SUPPORTED_EXTENSIONS[path.suffix.lower()],
                )
            )

        if len(files) >= self.settings.max_files:
            warnings.append(f"Repo hit MAX_FILES={self.settings.max_files}; remaining files were skipped.")

        return RepoScanResult(
            repo_url=repo_url,
            local_path=str(repo_path),
            files=files,
            skipped_files=skipped,
            warnings=warnings,
        )

    def cleanup(self, scan_result: RepoScanResult | None) -> None:
        if scan_result is None:
            return

        repo_path = Path(scan_result.local_path)
        temp_root = repo_path.parent
        temp_dir = Path(tempfile.gettempdir()).resolve()

        try:
            resolved_temp_root = temp_root.resolve()
        except FileNotFoundError:
            return

        if temp_dir in resolved_temp_root.parents and temp_root.name.startswith("swarm_audit_"):
            shutil.rmtree(temp_root, ignore_errors=True)
