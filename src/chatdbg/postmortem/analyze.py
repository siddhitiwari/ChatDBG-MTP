import sys
from typing import Optional

from chatdbg.assistant.assistant import Assistant, AssistantError
from chatdbg.util.config import chatdbg_config
from chatdbg.util.log import ChatDBGLog
from chatdbg.util.fix import apply_fix
from chatdbg.util.prompts import build_postmortem_prompt, postmortem_instructions

from .context import build_source_context
from .git_context import build_git_context
from .parser import parse_python_traceback
from .repo import build_repo_context, find_relevant_files


def _run_analysis(text: str, repo_path: Optional[str] = None) -> None:
    crash = parse_python_traceback(text)
    if crash is None:
        print("chatdbg: no Python traceback found in input", file=sys.stderr)
        return

    source_context = build_source_context(crash, context=chatdbg_config.context)

    repo_context = ""
    if repo_path:
        relevant = find_relevant_files(crash, repo_path)
        repo_context = build_repo_context(relevant)

    git_context = build_git_context(crash)

    functions = [apply_fix]
    prompt = build_postmortem_prompt(
        crash.raw_traceback, source_context, repo_context, git_context
    )
    instructions = postmortem_instructions(functions)

    log = ChatDBGLog(
        log_filename=chatdbg_config.log,
        config=chatdbg_config.to_json(),
        capture_streams=False,
    )
    printer = chatdbg_config.make_printer(sys.stdout, "(ChatDBG) ", "   ", 120)

    try:
        assistant = Assistant(
            instructions,
            model=chatdbg_config.model,
            functions=functions,
            listeners=[printer, log],
        )
        stats = assistant.query(prompt, user_text="")
        print(stats.get("message", ""))
        assistant.close()
    except AssistantError as e:
        for line in str(e).split("\n"):
            print(f"*** {line}", file=sys.stderr)


def analyze_crash_log(filename: str, repo_path: Optional[str] = None) -> None:
    """Parse a crash log file and run LLM-based post-mortem analysis on it."""
    try:
        with open(filename, "r") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"chatdbg: file not found: {filename}", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"chatdbg: error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    _run_analysis(text, repo_path=repo_path)


def analyze_crash_text(text: str, repo_path: Optional[str] = None) -> None:
    """Run post-mortem analysis on an in-memory traceback string."""
    _run_analysis(text, repo_path=repo_path)
