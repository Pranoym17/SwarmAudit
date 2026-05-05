from pathlib import Path

from app.config import Settings
from app.schemas import SourceFile
from app.services.chunker import Chunker


def test_chunker_preserves_line_ranges(tmp_path: Path):
    source = tmp_path / "demo.py"
    source.write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
    source_file = SourceFile(
        path="demo.py",
        absolute_path=str(source),
        size_bytes=source.stat().st_size,
        language="Python",
    )

    chunks = Chunker(Settings(max_chars_per_chunk=8)).chunk_file(source_file)

    assert len(chunks) > 1
    assert chunks[0].line_start == 1
    assert chunks[-1].line_end == 3
