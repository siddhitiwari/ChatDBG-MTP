import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class FrameInfo:
    filename: str
    lineno: int
    function: str
    source_line: str


@dataclass
class CrashReport:
    frames: list[FrameInfo]
    exception_type: str
    exception_message: str
    raw_traceback: str


_FRAME_RE = re.compile(r'  File "(.+?)", line (\d+), in (.+)')
_EXC_RE = re.compile(r'^([A-Za-z][A-Za-z0-9_.]*)(?:: (.*))?$')
_SKIP_PREFIXES = (
    "Traceback (most recent call last):",
    "During handling of the above exception",
    "The above exception was the direct cause",
)


def parse_python_traceback(text: str) -> Optional[CrashReport]:
    """Parse a Python traceback string into a CrashReport.

    Handles single tracebacks, chained exceptions, and tracebacks embedded
    in larger log files. Collects all frames; records the final exception type.
    """
    lines = text.splitlines()
    frames: list[FrameInfo] = []
    exc_type = ""
    exc_message = ""

    i = 0
    while i < len(lines):
        line = lines[i]

        frame_m = _FRAME_RE.match(line)
        if frame_m:
            filename = frame_m.group(1)
            lineno = int(frame_m.group(2))
            function = frame_m.group(3)
            source_line = ""
            if i + 1 < len(lines) and lines[i + 1].startswith("    "):
                source_line = lines[i + 1].strip()
                i += 1
            frames.append(FrameInfo(filename, lineno, function, source_line))
        elif line and not line[0].isspace() and not any(
            line.startswith(p) for p in _SKIP_PREFIXES
        ):
            exc_m = _EXC_RE.match(line)
            if exc_m:
                exc_type = exc_m.group(1)
                exc_message = exc_m.group(2) or ""

        i += 1

    if not frames and not exc_type:
        return None

    return CrashReport(
        frames=frames,
        exception_type=exc_type,
        exception_message=exc_message,
        raw_traceback=text,
    )
