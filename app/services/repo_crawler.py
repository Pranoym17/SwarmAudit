import os
import shutil
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlparse

from git import GitCommandError, Repo

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

README_FILENAMES = {"readme", "readme.md", "readme.rst", "readme.txt"}


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
        temp_root = self._create_clone_root()
        repo_path = temp_root / "repo"

        try:
            self._clone_repo(clone_url, repo_path)
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
            readme_language = self._readme_language(rel_path)
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS and readme_language is None:
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

            language = readme_language or SUPPORTED_EXTENSIONS[path.suffix.lower()]
            files.append(
                SourceFile(
                    path=str(rel_path).replace("\\", "/"),
                    absolute_path=str(path),
                    size_bytes=size,
                    language=language,
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

    def _readme_language(self, rel_path: Path) -> str | None:
        if rel_path.name.lower() not in README_FILENAMES:
            return None
        return "Markdown" if rel_path.suffix.lower() == ".md" else "Documentation"

    def cleanup(self, scan_result: RepoScanResult | None) -> None:
        if scan_result is None:
            return

        repo_path = Path(scan_result.local_path)
        temp_root = repo_path.parent

        try:
            resolved_temp_root = temp_root.resolve()
            resolved_base_dir = Path(self.settings.clone_base_dir).resolve()
        except FileNotFoundError:
            return

        if resolved_base_dir in resolved_temp_root.parents and temp_root.name.startswith("swarm_audit_"):
            shutil.rmtree(temp_root, ignore_errors=True)

    def _create_clone_root(self) -> Path:
        base_dir = Path(self.settings.clone_base_dir)
        base_dir.mkdir(parents=True, exist_ok=True)
        clone_root = base_dir / f"swarm_audit_{uuid.uuid4().hex}"
        clone_root.mkdir(parents=False, exist_ok=False)
        return clone_root

    def _clone_repo(self, clone_url: str, repo_path: Path) -> None:
        clone_kwargs = {
            "depth": 1,
            "single_branch": True,
            "env": self._git_env(),
            "multi_options": ["--filter=blob:none"],
        }
        if os.name != "nt":
            clone_kwargs["kill_after_timeout"] = self.settings.clone_timeout_seconds

        try:
            Repo.clone_from(clone_url, repo_path, **clone_kwargs)
        except GitCommandError as exc:
            if not self._should_retry_with_openssl(exc):
                raise
            shutil.rmtree(repo_path, ignore_errors=True)
            self._clone_repo_with_openssl(clone_url, repo_path)

    def _should_retry_with_openssl(self, exc: GitCommandError) -> bool:
        if os.name != "nt":
            return False
        return "schannel" in str(exc).lower()

    def _clone_repo_with_openssl(self, clone_url: str, repo_path: Path) -> None:
        command = [
            "git",
            "-c",
            "http.sslBackend=openssl",
            "clone",
            "-v",
            "--depth=1",
            "--single-branch",
            "--filter=blob:none",
            "--",
            clone_url,
            str(repo_path),
        ]
        result = subprocess.run(
            command,
            cwd=Path.cwd(),
            env={**os.environ, **self._git_env()},
            text=True,
            capture_output=True,
            timeout=self.settings.clone_timeout_seconds,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Git clone failed with OpenSSL fallback: {result.stderr.strip()}")

    def _git_env(self) -> dict[str, str]:
        return {
            "GIT_TERMINAL_PROMPT": "0",
            "HTTP_PROXY": "",
            "HTTPS_PROXY": "",
            "ALL_PROXY": "",
            "http_proxy": "",
            "https_proxy": "",
            "all_proxy": "",
        }
