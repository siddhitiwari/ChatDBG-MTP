import sys

from chatdbg.assistant.assistant import Assistant, AssistantError
from chatdbg.util.config import chatdbg_config
from chatdbg.util.log import ChatDBGLog
from chatdbg.util.prompts import build_postmortem_prompt, postmortem_instructions

from .context import build_source_context
from .parser import parse_python_traceback


def analyze_crash_log(filename: str) -> None:
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

    crash = parse_python_traceback(text)
    if crash is None:
        print(
            f"chatdbg: no Python traceback found in {filename}", file=sys.stderr
        )
        sys.exit(1)

    source_context = build_source_context(crash, context=chatdbg_config.context)
    prompt = build_postmortem_prompt(crash.raw_traceback, source_context)
    instructions = postmortem_instructions()

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
            functions=[],
            listeners=[printer, log],
        )
        stats = assistant.query(prompt, user_text="")
        print(stats.get("message", ""))
        assistant.close()
    except AssistantError as e:
        for line in str(e).split("\n"):
            print(f"*** {line}", file=sys.stderr)
        sys.exit(1)
