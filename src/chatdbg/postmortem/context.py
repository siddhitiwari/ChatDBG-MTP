import linecache
import os
import sys

from .parser import CrashReport


_LIBRARY_ROOTS = tuple(
    filter(
        None,
        [
            os.path.dirname(os.__file__),
            next((p for p in sys.path if "site-packages" in p), None),
            next((p for p in sys.path if "dist-packages" in p), None),
        ],
    )
)


def _is_user_file(filename: str) -> bool:
    if not os.path.isabs(filename):
        return True
    return not any(
        "site-packages" in filename
        or "dist-packages" in filename
        or filename.startswith(root)
        for root in _LIBRARY_ROOTS
    )


def _read_context(filename: str, lineno: int, context: int) -> str:
    if not os.path.exists(filename):
        return ""
    start = max(1, lineno - context)
    end = lineno + context
    result = []
    for i in range(start, end + 1):
        line = linecache.getline(filename, i)
        if not line:
            break
        marker = ">" if i == lineno else " "
        result.append(f"{marker}{i:5d}  {line}")
    return "".join(result)


def build_source_context(crash_report: CrashReport, context: int = 10) -> str:
    """Return formatted source context for all user-code frames in the report."""
    sections = []
    for frame in crash_report.frames:
        if not _is_user_file(frame.filename):
            continue
        source = _read_context(frame.filename, frame.lineno, context)
        if not source:
            continue
        header = (
            f"File `{frame.filename}`, line {frame.lineno} in `{frame.function}`:"
        )
        sections.append(f"{header}\n```python\n{source}```")

    if not sections:
        return ""
    return "Source code context:\n\n" + "\n\n".join(sections)
