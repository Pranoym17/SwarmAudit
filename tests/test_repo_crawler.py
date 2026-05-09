from pathlib import Path
from unittest.mock import patch

import pytest
from git import GitCommandError

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


def test_scan_local_repo_includes_dependency_manifests(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("requests==2.28.0\n", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"dependencies": {"express": "4.18.2"}}', encoding="utf-8")

    crawler = RepoCrawler(Settings(max_files=10, max_file_size_kb=10))
    result = crawler.scan_local_repo("https://github.com/example/project", tmp_path)

    assert {source_file.path for source_file in result.files} == {"requirements.txt", "package.json"}
    assert {source_file.language for source_file in result.files} == {"Python Requirements", "Node Package"}


def test_clone_and_scan_omits_gitpython_timeout_on_windows(tmp_path: Path):
    crawler = RepoCrawler(Settings(max_files=10, max_file_size_kb=1, clone_base_dir=str(tmp_path / "clones")))

    with patch("app.services.repo_crawler.os.name", "nt"), patch(
        "app.services.repo_crawler.Repo.clone_from"
    ) as clone_from, patch.object(
        crawler,
        "scan_local_repo",
        return_value=crawler.scan_local_repo("https://github.com/example/project", tmp_path),
    ):
        crawler.clone_and_scan("https://github.com/example/project")

    assert "kill_after_timeout" not in clone_from.call_args.kwargs
    assert clone_from.call_args.kwargs["env"]["HTTPS_PROXY"] == ""
    assert clone_from.call_args.kwargs["env"]["ALL_PROXY"] == ""


def test_clone_and_scan_retries_schannel_failure_with_openssl(tmp_path: Path):
    crawler = RepoCrawler(Settings(max_files=10, max_file_size_kb=1, clone_base_dir=str(tmp_path / "clones")))
    schannel_error = GitCommandError("git clone", 128, stderr="schannel: AcquireCredentialsHandle failed")

    with patch("app.services.repo_crawler.os.name", "nt"), patch(
        "app.services.repo_crawler.Repo.clone_from",
        side_effect=schannel_error,
    ), patch.object(crawler, "_clone_repo_with_openssl") as clone_with_openssl, patch.object(
        crawler,
        "scan_local_repo",
        return_value=crawler.scan_local_repo("https://github.com/example/project", tmp_path),
    ):
        crawler.clone_and_scan("https://github.com/example/project")

    clone_with_openssl.assert_called_once()
