from pathlib import Path

import pytest

from app.config import Settings
from app.services.repo_crawler import RepoCrawler, validate_github_url


def test_validate_github_url_normalizes_clone_url():
    assert validate_github_url("https://github.com/example/project") == "https://github.com/example/project.git"


def test_validate_github_url_rejects_non_github():
    with pytest.raises(ValueError):
        validate_github_url("https://gitlab.com/example/project")


def test_scan_local_repo_filters_supported_files(tmp_path: Path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.js").write_text("x", encoding="utf-8")
    (tmp_path / "app.py").write_text("API_KEY = '1234567890'\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")

    crawler = RepoCrawler(Settings(max_files=10, max_file_size_kb=1))
    result = crawler.scan_local_repo("https://github.com/example/project", tmp_path)

    assert [file.path for file in result.files] == ["app.py"]
    assert result.skipped_files == 2


def test_scan_local_repo_includes_readme_for_docs_agent(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    crawler = RepoCrawler(Settings(max_files=10, max_file_size_kb=1))
    result = crawler.scan_local_repo("https://github.com/example/project", tmp_path)

    assert result.files[0].path == "README.md"
    assert result.files[0].language == "Markdown"
