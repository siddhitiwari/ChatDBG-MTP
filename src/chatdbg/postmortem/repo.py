import ast
import os

from .parser import CrashReport


_SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "env",
    "node_modules", "dist", "build", ".eggs", ".tox",
}


def _collect_py_files(repo_path: str) -> set[str]:
    result = set()
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for f in files:
            if f.endswith(".py"):
                result.add(os.path.abspath(os.path.join(root, f)))
    return result


def _local_imports(filepath: str, repo_root: str, all_files: set[str]) -> list[str]:
    """Return absolute paths of repo files imported by filepath."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
        tree = ast.parse(source, filename=filepath)
    except (SyntaxError, IOError):
        return []

    repo_root = os.path.abspath(repo_root)
    file_dir = os.path.dirname(os.path.abspath(filepath))
    rel_dir = os.path.relpath(file_dir, repo_root)
    pkg_parts = [] if rel_dir == "." else rel_dir.replace(os.sep, "/").split("/")

    found = []

    def _resolve(module_parts: list[str]) -> None:
        as_file = os.path.join(repo_root, *module_parts) + ".py"
        as_pkg = os.path.join(repo_root, *module_parts, "__init__.py")
        for candidate in (as_file, as_pkg):
            if candidate in all_files:
                found.append(candidate)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _resolve(alias.name.split("."))

        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            if node.level > 0:
                base = pkg_parts[: len(pkg_parts) - (node.level - 1)]
                parts = base + node.module.split(".")
            else:
                parts = node.module.split(".")
            _resolve(parts)

    return list(set(found))


def find_relevant_files(
    crash_report: CrashReport, repo_path: str, max_depth: int = 2
) -> list[str]:
    """Return repo files relevant to the crash by following imports from crash frames."""
    repo_abs = os.path.abspath(repo_path)
    all_files = _collect_py_files(repo_abs)

    # Seed: files from the traceback that exist in the repo
    seed: list[str] = []
    for frame in crash_report.frames:
        abs_frame = os.path.abspath(frame.filename)
        if abs_frame in all_files:
            seed.append(abs_frame)
        else:
            # Fall back to matching by basename
            for rf in all_files:
                if os.path.basename(frame.filename) == os.path.basename(rf):
                    seed.append(rf)

    relevant: list[str] = list(dict.fromkeys(seed))  # ordered, deduplicated
    seen: set[str] = set(relevant)
    frontier = list(relevant)

    for _ in range(max_depth):
        next_frontier: list[str] = []
        for f in frontier:
            for imp in _local_imports(f, repo_abs, all_files):
                if imp not in seen:
                    seen.add(imp)
                    relevant.append(imp)
                    next_frontier.append(imp)
        frontier = next_frontier
        if not frontier:
            break

    return relevant


def build_repo_context(files: list[str], token_budget: int = 6000) -> str:
    """Format relevant repo files as LLM context, within an approximate token budget."""
    if not files:
        return ""

    char_budget = token_budget * 4  # rough: 1 token ≈ 4 chars
    sections: list[str] = []
    used = 0

    for filepath in files:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except IOError:
            continue
        if not content.strip():
            continue
        section = f"File `{filepath}`:\n```python\n{content}\n```"
        if used + len(section) > char_budget and sections:
            break
        sections.append(section)
        used += len(section)

    if not sections:
        return ""
    return "Additional repository context:\n\n" + "\n\n".join(sections)
