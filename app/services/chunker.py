from pathlib import Path

from app.config import Settings
from app.schemas import CodeChunk, SourceFile


class Chunker:
    def __init__(self, settings: Settings):
        self.settings = settings

    def chunk_files(self, files: list[SourceFile]) -> list[CodeChunk]:
        chunks: list[CodeChunk] = []
        for source_file in files:
            chunks.extend(self.chunk_file(source_file))
        return chunks

    def chunk_file(self, source_file: SourceFile) -> list[CodeChunk]:
        text = Path(source_file.absolute_path).read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        if not lines:
            return []

        chunks: list[CodeChunk] = []
        current_lines: list[str] = []
        current_start = 1
        current_chars = 0

        for index, line in enumerate(lines, start=1):
            line_chars = len(line) + 1
            if current_lines and current_chars + line_chars > self.settings.max_chars_per_chunk:
                chunks.append(
                    CodeChunk(
                        file_path=source_file.path,
                        language=source_file.language,
                        line_start=current_start,
                        line_end=index - 1,
                        content="\n".join(current_lines),
                    )
                )
                current_lines = []
                current_start = index
                current_chars = 0

            current_lines.append(line)
            current_chars += line_chars

        if current_lines:
            chunks.append(
                CodeChunk(
                    file_path=source_file.path,
                    language=source_file.language,
                    line_start=current_start,
                    line_end=len(lines),
                    content="\n".join(current_lines),
                )
            )

        return chunks
