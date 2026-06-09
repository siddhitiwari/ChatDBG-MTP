"""Run ChatDBG post-mortem analysis in non-interactive eval mode."""
import io
import os
import subprocess
import sys
import tempfile
from typing import Optional

import yaml


def generate_crash_log(script_path: str, cwd: Optional[str] = None, timeout: int = 30) -> Optional[str]:
    """Run a Python script and return its crash output, or None if it doesn't crash."""
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or os.path.dirname(os.path.abspath(script_path)),
        )
    except subprocess.TimeoutExpired:
        return None

    if result.returncode == 0:
        return None

    output = result.stderr or result.stdout
    return output if "Traceback" in output else None


def run_analysis(crash_text: str, repo_path: Optional[str] = None) -> dict:
    """
    Run ChatDBG analysis in eval mode (no prompts, no file writes).
    Returns a dict with: response, fix_captures, test_captures, log, log_file.
    """
    os.environ["CHATDBG_EVAL"] = "1"

    tmp = tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w")
    tmp.close()
    log_file = tmp.name

    from chatdbg.util.config import chatdbg_config
    from chatdbg.util.fix import clear_eval_captures, get_eval_captures
    from chatdbg.util.test_gen import (
        clear_eval_captures as clear_test,
        get_eval_captures as get_test,
    )

    original_log = chatdbg_config.log
    chatdbg_config.log = log_file

    clear_eval_captures()
    clear_test()

    captured = io.StringIO()
    orig_stdout = sys.stdout
    sys.stdout = captured

    try:
        from chatdbg.postmortem.analyze import analyze_crash_text
        analyze_crash_text(crash_text, repo_path=repo_path)
    finally:
        sys.stdout = orig_stdout
        chatdbg_config.log = original_log
        os.environ.pop("CHATDBG_EVAL", None)

    return {
        "response": captured.getvalue(),
        "fix_captures": get_eval_captures(),
        "test_captures": get_test(),
        "log": _parse_log(log_file),
        "log_file": log_file,
    }


def _parse_log(log_file: str) -> dict:
    try:
        with open(log_file, "r") as f:
            entries = yaml.safe_load(f.read())
        if isinstance(entries, list) and entries:
            return entries[0]
    except Exception:
        pass
    return {}
