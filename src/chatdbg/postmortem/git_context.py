import os
import subprocess

from .parser import CrashReport


def _run_git(args: list[str], cwd: str) -> str:
    """Run a git command and return stdout, or empty string on any failure."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _git_root(filepath: str) -> str | None:
    """Return the git root for a file path, or None if not in a git repo."""
    directory = os.path.dirname(os.path.abspath(filepath))
    root = _run_git(["rev-parse", "--show-toplevel"], cwd=directory)
    return root or None


def _file_log(filepath: str, git_root: str, n: int = 8) -> str:
    rel = os.path.relpath(filepath, git_root)
    return _run_git(["log", "--oneline", f"-{n}", "--", rel], cwd=git_root)


def _blame(filepath: str, git_root: str, lineno: int, context: int = 3) -> str:
    rel = os.path.relpath(filepath, git_root)
    start = max(1, lineno - context)
    end = lineno + context
    return _run_git(
        ["blame", f"-L{start},{end}", "--date=short", rel], cwd=git_root
    )


def _recent_diff(filepath: str, git_root: str) -> str:
    rel = os.path.relpath(filepath, git_root)
    return _run_git(["diff", "HEAD~1", "--", rel], cwd=git_root)


def build_git_context(crash_report: CrashReport) -> str:
    """Return git log/blame/diff context for each user-code file in the crash."""
    sections: list[str] = []
    seen: set[str] = set()

    for frame in crash_report.frames:
        filepath = os.path.abspath(frame.filename)
        if filepath in seen or not os.path.exists(filepath):
            continue
        seen.add(filepath)

        root = _git_root(filepath)
        if not root:
            continue

        parts: list[str] = []

        log = _file_log(filepath, root)
        if log:
            parts.append(f"Recent commits on this file:\n```\n{log}\n```")

        blame = _blame(filepath, root, frame.lineno)
        if blame:
            parts.append(
                f"git blame around line {frame.lineno}:\n```\n{blame}\n```"
            )

        diff = _recent_diff(filepath, root)
        if diff:
            parts.append(f"Changes introduced in the last commit:\n```diff\n{diff}\n```")

        if parts:
            sections.append(
                f"Git history for `{filepath}`:\n\n" + "\n\n".join(parts)
            )

    if not sections:
        return ""
    return "Git context:\n\n" + "\n\n---\n\n".join(sections)
