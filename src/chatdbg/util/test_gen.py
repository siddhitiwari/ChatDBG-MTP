import os


def generate_test(filename: str, test_code: str) -> tuple[str, str]:
    """
    {
        "name": "generate_test",
        "description": "Write a pytest test that reproduces the crash. Call this after identifying the root cause. The test should fail with the buggy code and pass after the fix is applied. Use standard pytest naming conventions (test_<name>.py, functions starting with test_). If the target file already exists, the test is appended to it.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Path to write the test file, e.g. tests/test_marbles.py or test_foo.py. Parent directories are created automatically."
                },
                "test_code": {
                    "type": "string",
                    "description": "Complete pytest test code including all necessary imports and one or more test functions that reproduce the crash."
                }
            },
            "required": ["filename", "test_code"]
        }
    }
    """
    call = f"generate_test({filename!r})"

    print(f"\n[ChatDBG] Proposed test → {filename}:\n")
    print(test_code)

    try:
        answer = input("\n[ChatDBG] Write this test? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return call, "Test not written (no input available)."

    if answer != "y":
        return call, "Test not written (user declined)."

    parent = os.path.dirname(filename)
    if parent:
        os.makedirs(parent, exist_ok=True)

    exists = os.path.exists(filename)
    try:
        with open(filename, "a", encoding="utf-8") as f:
            if exists:
                f.write("\n\n")
            f.write(test_code.rstrip() + "\n")
        action = "appended to" if exists else "written to"
        return call, f"Test {action} {filename}."
    except IOError as e:
        return call, f"Error writing file: {e}"
