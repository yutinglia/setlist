"""Reject oversized hand-written production files before they become monoliths."""

from __future__ import annotations

import subprocess
from pathlib import Path

MAX_SOURCE_LINES = 1_000
SOURCE_SUFFIXES = frozenset(
    {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".sql", ".ps1", ".sh"}
)
GENERATED_PATHS = frozenset(
    {
        "backend/db/models.py",
        "frontend/src/routeTree.gen.ts",
    }
)
GENERATED_PREFIXES = ("frontend/src/paraglide/",)
TEST_DIRECTORY_NAMES = frozenset({"test", "tests", "__tests__"})
TEST_FILENAME_MARKERS = (".test.", ".spec.")


def _project_paths(root: Path) -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
    )
    return [root / raw.decode("utf-8") for raw in output.split(b"\0") if raw]


def _is_handwritten_source(path: Path, root: Path) -> bool:
    relative = path.relative_to(root).as_posix()
    parts = relative.split("/")
    filename = parts[-1]
    is_test = (
        any(part in TEST_DIRECTORY_NAMES for part in parts[:-1])
        or filename.startswith("test_")
        or filename.endswith("_test.py")
        or any(marker in filename for marker in TEST_FILENAME_MARKERS)
    )
    return (
        path.suffix.lower() in SOURCE_SUFFIXES
        and not is_test
        and relative not in GENERATED_PATHS
        and not relative.startswith(GENERATED_PREFIXES)
    )


def _line_count(path: Path) -> int:
    content = path.read_bytes()
    if not content:
        return 0
    return content.count(b"\n") + int(not content.endswith(b"\n"))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    source_files = [
        path
        for path in _project_paths(root)
        if path.is_file() and _is_handwritten_source(path, root)
    ]
    source_sizes = [
        (_line_count(path), path.relative_to(root).as_posix()) for path in source_files
    ]
    oversized = sorted(
        (item for item in source_sizes if item[0] > MAX_SOURCE_LINES),
        reverse=True,
    )
    if oversized:
        print(f"Source files must not exceed {MAX_SOURCE_LINES} lines:")
        for lines, path in oversized:
            print(f"  {lines:>5}  {path}")
        return 1

    print(
        f"Code quality check passed: {len(source_files)} hand-written production "
        f"files are at most {MAX_SOURCE_LINES} lines."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
