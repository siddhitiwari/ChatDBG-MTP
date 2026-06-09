"""Score ChatDBG analysis results against benchmark expectations."""
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Optional


def score_result(benchmark: dict, result: dict) -> dict:
    """Score a ChatDBG analysis result against a benchmark definition."""
    response = result.get("response", "").lower()
    fix_captures = result.get("fix_captures", [])
    test_captures = result.get("test_captures", [])
    meta = result.get("log", {}).get("meta", {})

    # Did the response mention the expected exception type?
    expected_exc = benchmark.get("expected_exception", "").lower()
    exception_match = (expected_exc in response) if expected_exc else None

    # How many root cause keywords appear in the response?
    keywords = benchmark.get("root_cause_keywords", [])
    if keywords:
        hits = sum(1 for kw in keywords if kw.lower() in response)
        keyword_score = hits / len(keywords)
    else:
        keyword_score = None

    # Was a fix proposed?
    fix_proposed = len(fix_captures) > 0

    # Was a test generated?
    test_generated = len(test_captures) > 0

    # Does the proposed fix actually make the script stop crashing?
    fix_correct: Optional[bool] = None
    if fix_captures and benchmark.get("script"):
        fix_correct = _verify_fix(benchmark["script"], fix_captures[0])

    return {
        "exception_match": exception_match,
        "keyword_score": round(keyword_score, 2) if keyword_score is not None else None,
        "fix_proposed": fix_proposed,
        "test_generated": test_generated,
        "fix_correct": fix_correct,
        "cost": meta.get("total_cost", 0.0),
        "time": round(meta.get("total_time", 0.0), 1),
        "tokens": meta.get("total_tokens", 0),
    }


def _verify_fix(script_path: str, fix: dict) -> bool:
    """Apply the proposed fix to a temp copy and check the script no longer crashes."""
    target = fix.get("filename", "")
    if not target or not os.path.exists(target):
        return False

    try:
        with open(target, "r", encoding="utf-8") as f:
            original = f.read()
    except IOError:
        return False

    old = fix.get("old_code", "")
    new = fix.get("new_code", "")
    fixed = original.replace("\r\n", "\n").replace(old, new, 1)

    if fixed == original.replace("\r\n", "\n"):
        return False  # fix changed nothing

    tmp_dir = tempfile.mkdtemp()
    try:
        tmp_script = os.path.join(tmp_dir, os.path.basename(target))
        with open(tmp_script, "w", encoding="utf-8") as f:
            f.write(fixed)

        result = subprocess.run(
            [sys.executable, tmp_script],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=os.path.dirname(os.path.abspath(script_path)),
        )
        return result.returncode == 0
    except Exception:
        return False
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
