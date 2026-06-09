# ChatDBG MTP Changes

This file tracks all feature additions and modifications made as part of the MTP project.

---

## Feature #2 — Post-mortem Analysis (no live process needed)

**Status:** Implemented

### Problem

ChatDBG originally required a live debugger session: you had to invoke `chatdbg -c continue script.py` and the program had to crash in the active session. This meant:
- Crashes from CI pipelines, production logs, or Sentry exports could not be analyzed.
- You could not paste a copied stack trace and get an explanation.
- No way to analyze a crash that occurred on another machine.

### What was built

A new `--analyze` flag that accepts a crash log file (any text file containing a Python traceback) and runs LLM-based root cause analysis on it **without launching a debugger or running any code**.

```
chatdbg --analyze crash.log
chatdbg --analyze crash.log --model gpt-4o
chatdbg --analyze crash.log --model claude-3-5-sonnet-20241022
```

The tool:
1. Parses the traceback out of the file
2. Reads the relevant source files from disk and builds context around each crashed line
3. Sends the traceback + source context to the LLM with a static-analysis-focused system prompt
4. Prints the root cause explanation and recommended fix

### New files

| File | Purpose |
|---|---|
| `src/chatdbg/postmortem/__init__.py` | Package marker |
| `src/chatdbg/postmortem/parser.py` | Parses Python tracebacks from raw text into `CrashReport` / `FrameInfo` dataclasses. Handles chained exceptions, embedded log files, and exceptions with no message. |
| `src/chatdbg/postmortem/context.py` | Reads source code from disk around each user-code frame. Skips library frames (`site-packages`, stdlib). |
| `src/chatdbg/postmortem/analyze.py` | Orchestrates the full pipeline: parse → read context → build prompt → call LLM → print result. |
| `src/chatdbg/util/instructions/postmortem.txt` | System prompt for post-mortem mode. Differs from the interactive prompt: instructs the LLM to analyze static context only, since no `debug`/`info`/`slice` tool calls are available. |

### Modified files

| File | Change |
|---|---|
| `src/chatdbg/__main__.py` | Added `--analyze <file>` flag handling before the normal ipdb flow. Parses remaining ChatDBG flags (e.g. `--model`) so they still work in analyze mode. |
| `src/chatdbg/util/prompts.py` | Added `build_postmortem_prompt(raw_traceback, source_context)` and `postmortem_instructions()`. |

### Design decisions

- **No tool calls in postmortem mode** — the `Assistant` is created with `functions=[]`. There is no live process to run `debug` / `info` / `slice` against, so the LLM is given all relevant source context upfront instead.
- **Source context is included statically** — `context.py` reads source files directly from disk, using `linecache`. If a file no longer exists (e.g., the log came from a different machine), that frame is silently skipped.
- **Library frames are filtered** — frames from `site-packages`, `dist-packages`, and the stdlib are excluded from source context to keep the prompt focused on user code.
- **The same `Assistant` + `ChatDBGLog` infrastructure is reused** — the session is still logged to `log.yaml`, and all existing `--model`, `--log`, `--format` flags work identically.

### Limitations / known gaps

- Only Python tracebacks are supported. C/C++ core dumps and LLDB crash logs are not yet handled.
- Source context requires the source files to be present on the current machine at the same paths recorded in the traceback.
- No interactive follow-up: post-mortem is a single-shot query. There is no `chat` command after the first analysis.

---

## Planned: Feature #4 — Zero-friction exception hook

**Status:** Not started

### Problem

You must explicitly invoke `chatdbg -c continue script.py` instead of the normal `python script.py`. Most users never do this — the tool stays unused because the invocation friction is too high.

### Plan

Register a `sys.excepthook` so that any unhandled exception in a normal `python script.py` run automatically triggers ChatDBG analysis (post-mortem mode). Installable via:

```python
import chatdbg
chatdbg.install()
```

Or as a `.pth` file in `site-packages` for zero-code-change auto-injection.

**Connection to Feature #2:** The exception hook can reuse the post-mortem pipeline directly — capture the traceback from `sys.excepthook`, write it to a temp file or pass it in-memory, and call `analyze_crash_log`.

---

## Planned: Feature #1 — Pytest plugin

**Status:** Not started

### Problem

When `pytest` tests fail, developers get a traceback but have to manually invoke ChatDBG. The analysis is not integrated into the normal test workflow.

### Plan

A pytest plugin (`chatdbg-pytest`) that hooks into pytest's `pytest_runtest_logreport` event. On a failing test:
1. Captures the exception + traceback from the test report
2. Runs post-mortem analysis (reusing Feature #2's pipeline)
3. Prints the root cause + fix inline with the test failure output

Can optionally post the analysis as a GitHub PR comment via the GitHub Actions integration already present in `.github/workflows/`.
