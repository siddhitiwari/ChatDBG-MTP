import difflib
import os

_eval_captures: list[dict] = []


def clear_eval_captures() -> None:
    _eval_captures.clear()


def get_eval_captures() -> list[dict]:
    return list(_eval_captures)


def apply_fix(filename: str, old_code: str, new_code: str) -> tuple[str, str]:
    """
    {
        "name": "apply_fix",
        "description": "Apply a code fix directly to a source file. Call this once you have identified the root cause and know the exact change needed. Provide the file path, the exact existing lines to replace (matching indentation precisely), and the corrected replacement. The user will be shown a diff and asked to confirm before any change is written.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Path to the source file to modify."
                },
                "old_code": {
                    "type": "string",
                    "description": "The exact lines of existing code to replace, including all indentation and whitespace."
                },
                "new_code": {
                    "type": "string",
                    "description": "The corrected replacement code."
                }
            },
            "required": ["filename", "old_code", "new_code"]
        }
    }
    """
    call = f"apply_fix({filename!r})"

    if not os.path.exists(filename):
        return call, f"Error: file not found: {filename}"

    try:
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
    except IOError as e:
        return call, f"Error reading file: {e}"

    normalized = content.replace("\r\n", "\n")
    old_normalized = old_code.replace("\r\n", "\n")
    new_normalized = new_code.replace("\r\n", "\n")

    if old_normalized not in normalized:
        return call, (
            f"Error: the specified old_code was not found verbatim in {filename}. "
            "Ensure indentation and whitespace match exactly."
        )

    diff = "".join(
        difflib.unified_diff(
            old_normalized.splitlines(keepends=True),
            new_normalized.splitlines(keepends=True),
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
        )
    )

    # Eval mode: capture without prompting or writing
    if os.environ.get("CHATDBG_EVAL"):
        _eval_captures.append(
            {"filename": filename, "old_code": old_normalized, "new_code": new_normalized}
        )
        return call, f"Fix captured for evaluation (not written): {filename}"

    print(f"\n[ChatDBG] Proposed fix for {filename}:\n")
    print(diff or "(no changes — old and new code are identical)")

    try:
        answer = input("\n[ChatDBG] Apply this fix? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return call, "Fix not applied (no input available)."

    if answer != "y":
        return call, "Fix not applied (user declined)."

    new_content = normalized.replace(old_normalized, new_normalized, 1)
    if "\r\n" in content:
        new_content = new_content.replace("\n", "\r\n")

    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(new_content)
        return call, f"Fix applied to {filename}."
    except IOError as e:
        return call, f"Error writing file: {e}"
