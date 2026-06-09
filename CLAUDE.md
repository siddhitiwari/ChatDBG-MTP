# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ChatDBG is an AI-assisted debugging tool that integrates LLM-powered root cause analysis into Python (`pdb`/`ipdb`), GDB, and LLDB debuggers. Published at FSE'25.

## Commands

### Install for development
```bash
pip install -e .
```

### Run linting and type checks (mirrors CI)
```bash
python -m black --check src          # formatting check (run on Python 3.11)
python -m compileall src             # syntax check across all Python versions
python -m mypy src                   # type checking
```

### Auto-format
```bash
python -m black src
```

### Run ChatDBG on a Python script
```bash
chatdbg -c continue samples/python/marbles.py
```

### Print a saved debug log
```bash
print_chatdbg_log <logfile.yaml>
```

## Architecture

### Request flow

1. **Entry** — `__main__.py` patches `ipdb` to use the `ChatDBG` class, parses config flags, then delegates to `ipdb.__main__.main()`.
2. **Debugger layer** — `ChatDBG` (`chatdbg_pdb.py`) extends `ipdb.TerminalPdb`. When the user types `why` or `chat`, it builds a prompt from the current debugger state and calls `Assistant.query()`.
3. **Assistant** (`assistant/assistant.py`) — wraps `litellm.completion()` with streaming and tool calling. The LLM can call back into the debugger via registered functions (`debug`, `info`, `slice`). Responses are emitted to all registered `Listener` objects via broadcast.
4. **Listeners** (`assistant/listeners.py`) — receive events (`on_stream_delta`, `on_function_call`, `on_end_query`, etc.) and handle printing, YAML logging, and Jupyter output.

### Debugger backends

| File | Backend |
|---|---|
| `chatdbg_pdb.py` | Python (`ipdb`/`pdb`) |
| `chatdbg_gdb.py` | GDB (loaded via `~/.gdbinit`) |
| `chatdbg_lldb.py` | LLDB (loaded as an extension) |

GDB and LLDB share `native_util/dbg_dialog.py` (`DBGDialog`) as the base for the interactive question/answer loop.

### Prompt construction

`util/prompts.py` builds the initial LLM prompt from: stack trace + error message + source snippets + captured stdin/stdout + command history. Follow-up prompts include only history + stack + user text. System instructions are loaded from `util/instructions/default.txt` (or a model-specific file like `gpt-4o.txt`).

`util/trim.py` implements a *sandwich trimming* algorithm: when the conversation exceeds the model's context limit, it trims the middle of long messages while preserving the beginning and end.

### Safety

- **Python**: `pdb_util/sandbox.py` evaluates expressions via AST analysis with a module whitelist, blocking dangerous operations.
- **Native**: `native_util/safety.py` validates GDB/LLDB commands against an allowlist before the LLM can execute them.

### Configuration

`util/config.py` uses `traitlets` to define all settings (`ChatDBGConfig`). Flags are parsed from CLI args before `ipdb` sees them. Key env vars / settings:

- `OPENAI_API_KEY` — required for the default model
- `CHATDBG_MODEL` — LLM model to use (default: `gpt-4o`; must support function calling)
- `CHATDBG_MAX_CALL_RESPONSE_TOKENS` — caps function call results fed back to the LLM

### Function tools (LLM callbacks)

Functions registered with `Assistant` must have a JSON schema as their docstring (`_add_function` parses `function.__doc__` as JSON). The LLM can call:
- `debug(command)` — run a debugger command and return output
- `info(symbol)` — look up documentation/source for a symbol  
- `slice(variable)` — backward slice to find what produced a variable (Jupyter only, via `ipyflow`)

### Rust support

`rust-support/chatdbg/` is a separate Cargo workspace. It provides a panic hook (`lib.rs`) that writes a log file, and a `#[chatdbg::main]` proc macro (`chatdbg_macros/`) that wraps `main()` to invoke the hook on panic.

### Logging

All sessions are written to YAML logs via `util/log.py`. The `print_chatdbg_log` CLI entry point (`util/plog.py`) pretty-prints these logs.
