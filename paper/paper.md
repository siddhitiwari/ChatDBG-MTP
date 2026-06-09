# ChatDBG-MTP: Extending AI-Assisted Debugging with Post-Mortem Analysis, Repository-Aware Context, and Automated Repair

**Author:** Siddhi Tiwari
**Institution:** [Your Institution]
**Email:** siddhitiwari0109@gmail.com

---

## Abstract

Debugging is one of the most time-consuming activities in software development.
Existing AI-assisted debugging tools, including the original ChatDBG, require an
active debugger session, limiting their use to crashes reproducible in a live
environment. In this work we present **ChatDBG-MTP**, an extended version of
ChatDBG that introduces five major contributions: (1) **post-mortem analysis**
that runs on crash log files without a live process, (2) a **zero-friction
exception hook** that auto-triggers analysis on any unhandled exception,
(3) **repository-aware context** that follows import graphs to provide the LLM
with a broader view of the codebase, (4) **git-aware context** that surfaces
recent commit history, blame information, and diffs to support regression
detection, and (5) **automated fix application and test generation** that
complete the full repair cycle. We evaluate ChatDBG-MTP on 8 benchmark programs
across four configuration variants. Our results show that adding repository
context improves root-cause keyword coverage from **57%** to **77%** (+20 pp),
fix correctness from **50%** to **75%** (+25 pp), and test generation from **12%**
to **75%** (+63 pp). Combining repository and git context achieves the best
overall accuracy (**89%** keyword coverage, **88%** fix correctness) with a
modest cost increase of 38%.

---

## 1. Introduction

Modern software crashes in many contexts where a live debugger is unavailable:
production environments, continuous integration pipelines, remote machines, and
crash reports submitted by end users. Even when a debugger is available, AI
assistants such as ChatDBG [Berger et al., FSE'25] only analyze the immediate
stack trace, missing broader codebase context that could accelerate diagnosis.

We identify three key gaps in existing AI-assisted debugging:

1. **Availability** — tools require a live debugger session, excluding the
   majority of real-world crashes captured in logs.
2. **Context** — analysis is limited to the call stack, ignoring imported
   modules, class hierarchies, and recent code changes that frequently contain
   the root cause.
3. **Completeness** — tools explain bugs but do not close the repair loop:
   applying the fix and writing a regression test.

ChatDBG-MTP addresses all three gaps. We make the following contributions:

- A **post-mortem analysis** mode (`chatdbg --analyze crash.log`) that parses
  Python tracebacks from text files and runs LLM analysis without any running
  process.
- A **zero-friction exception hook** (`chatdbg.install()`) that registers a
  `sys.excepthook` so every unhandled exception is automatically analyzed.
- A **repository context** mechanism (`--repo`) that traverses the import graph
  from crashed frames to supply relevant source files to the LLM.
- A **git context** mechanism that automatically includes `git log`, `git blame`,
  and `git diff` output for each crashed file, enabling regression detection.
- An **automated repair** pipeline using two LLM tools: `apply_fix` (proposes
  and applies a code change with user confirmation) and `generate_test` (writes
  a pytest test that reproduces the original crash).
- An **evaluation harness** that runs all configurations on a benchmark suite
  and reports accuracy, fix correctness, and cost metrics.

---

## 2. Background and Related Work

### 2.1 ChatDBG

ChatDBG [Berger et al., 2025] integrates an LLM into the Python pdb/ipdb
debugger and the native GDB/LLDB debuggers. When a user types `why`, ChatDBG
sends the stack trace, error message, and local variable values to the LLM.
The LLM can call back into the debugger (`debug`, `info`, `slice`) to gather
more context. ChatDBG uses `litellm` to support multiple model providers.

Our work builds directly on ChatDBG's infrastructure — the `Assistant` class,
`BaseAssistantListener` event system, and `ChatDBGLog` YAML logging — and
extends it with the features described above.

### 2.2 Automated Program Repair

Automated Program Repair (APR) tools such as GenProg [Le Goues et al., 2012],
Prophet [Long & Rinard, 2016], and Angelix [Mechtaev et al., 2016] use search
or symbolic analysis to generate patches. Recent LLM-based approaches (e.g.,
AlphaRepair, ChatRepair) prompt models with the buggy code and test suite.
Unlike these tools, ChatDBG-MTP operates at debugging time on a crashed program,
without requiring a pre-existing test suite or formal specification.

### 2.3 Fault Localization

Spectrum-based fault localization (e.g., Tarantula, Ochiai) ranks suspicious
statements based on test pass/fail patterns. Our approach is complementary:
rather than ranking statements, we provide the LLM with rich context (source,
imports, git history) and rely on its reasoning to identify the root cause.

### 2.4 LLM Code Understanding

Recent work demonstrates that LLMs can reason about code at multiple levels of
abstraction [Chen et al., 2021; Nijkamp et al., 2022]. Providing additional
context — function signatures, docstrings, related code — consistently improves
accuracy [Nashid et al., 2023]. Our `--repo` feature operationalizes this
finding by automatically surfacing the most relevant context via import graph
traversal.

---

## 3. System Design

### 3.1 Architecture Overview

ChatDBG-MTP extends the original ChatDBG pipeline with a new **post-mortem
pathway** that runs independently of any live debugger:

```
  Input: crash log file / in-memory traceback
       │
       ▼
  ┌─────────────────────────────────────┐
  │         Post-mortem Pipeline        │
  │                                     │
  │  parse_python_traceback()           │
  │       │                             │
  │       ├──► build_source_context()   │  (from disk)
  │       │                             │
  │       ├──► build_repo_context()     │  (import graph)
  │       │                             │
  │       ├──► build_git_context()      │  (log/blame/diff)
  │       │                             │
  │       └──► build_postmortem_prompt()│
  │                    │                │
  └────────────────────│────────────────┘
                       ▼
               Assistant (LLM)
                  │        │
          apply_fix()  generate_test()
                  │        │
              [y/N]    [y/N]
                  │        │
           source file  test file
```

The interactive pdb mode and post-mortem mode share the same `Assistant` class,
listeners, and YAML logging infrastructure.

### 3.2 Post-Mortem Analysis (Feature #2)

The `postmortem` package contains three components:

**Parser** (`parser.py`): Parses Python tracebacks into a `CrashReport`
dataclass containing `FrameInfo` records (filename, line number, function,
source line) and the exception type/message. Handles chained exceptions, log
files with embedded tracebacks, and exceptions without messages.

**Context builder** (`context.py`): For each user-code frame, reads
`context_lines` lines around the crash point from disk using `linecache`.
Library frames (`site-packages`, stdlib) are filtered out.

**Analyzer** (`analyze.py`): Orchestrates the pipeline, creates the `Assistant`
with `apply_fix` and `generate_test` tools, runs the LLM query, and logs results.

### 3.3 Exception Hook (Feature #4)

`chatdbg.install()` registers a `sys.excepthook` that:
1. Lets Python print the original traceback (preserving familiar output)
2. Formats the traceback as text using `traceback.format_exception`
3. Calls `analyze_crash_text()` directly in memory
4. Silently skips `SystemExit` and `KeyboardInterrupt`
5. Catches all ChatDBG errors so they never mask the original exception

### 3.4 Repository Context (Feature #2b)

`repo.py` traverses the local import graph starting from the files in the
traceback:

1. Collect all `.py` files under `--repo` (skip `.git`, `__pycache__`, `venv`)
2. Seed with files directly referenced in the crash frames
3. For each seed file, parse `import` and `from ... import` statements using the
   `ast` module to find locally-defined dependencies
4. Repeat to depth 2
5. Format discovered files into the prompt within a ~6,000-token budget

This ensures the LLM sees helper functions, class definitions, and utility
modules that may contain the root cause, even when they are not directly in
the stack trace.

### 3.5 Git-Aware Context (Feature #5)

`git_context.py` runs three `git` commands per unique user-code file via
`subprocess`:

| Command | Purpose |
|---|---|
| `git log --oneline -8 <file>` | Shows recent commit history; identifies when the file was last changed |
| `git blame -L <start>,<end> <file>` | Shows who last modified the lines around the crash and when |
| `git diff HEAD~1 -- <file>` | Shows exactly what changed in the most recent commit |

All commands are timeout-protected (10s) and fail silently if git is
unavailable. This enables the LLM to identify regressions: bugs introduced
by a specific commit.

### 3.6 Automated Repair (Feature #3 and Feature #6)

Two LLM tool functions complete the repair cycle:

**`apply_fix(filename, old_code, new_code)`**: The LLM calls this once it has
identified the root cause. The tool shows a unified diff and prompts the user
`[y/N]` before writing. Old-code matching uses line-ending-normalized comparison;
CRLF is restored on write.

**`generate_test(filename, test_code)`**: The LLM generates a pytest test that
reproduces the original crash. The test is designed to fail against the buggy
code and pass after the fix is applied, creating a regression guard.

Both tools bypass `input()` prompts in eval mode (`CHATDBG_EVAL=1`), capturing
proposed changes in memory for the evaluator to score.

---

## 4. Evaluation

### 4.1 Setup

We evaluate ChatDBG-MTP on **8 benchmark programs** covering common Python bug
categories:

| Benchmark | Bug Type | Expected Exception |
|---|---|---|
| `testme_zero_division` | Loop variable starts at 0 | `ZeroDivisionError` |
| `sample_swapped_args` | Arguments swapped in NumPy call | `TypeError` |
| `off_by_one_index` | List access beyond bounds | `IndexError` |
| `none_attribute_access` | Method call on `None` | `AttributeError` |
| `type_mismatch` | String + integer addition | `TypeError` |
| `key_error_dict` | Missing dictionary key | `KeyError` |
| `recursion_overflow` | No base case in recursion | `RecursionError` |
| `value_out_of_range` | Invalid enum/range value | `ValueError` |

We test **four configuration variants** for each benchmark:

| Variant | Context sources |
|---|---|
| Baseline | Traceback + source context only |
| +Repo | + import-graph repo files |
| +Git | + git log/blame/diff |
| +Repo+Git | All context sources combined |

All experiments use **GPT-4o** (gpt-4o) via the OpenAI API.

### 4.2 Metrics

| Metric | Definition |
|---|---|
| **Exc Match** | Does the response mention the expected exception type? |
| **KW Coverage** | Fraction of expected root-cause keywords found in the response |
| **Fix Proposed** | Was `apply_fix` called? |
| **Test Generated** | Was `generate_test` called? |
| **Fix Correct** | Does the proposed fix make the script exit with code 0? |
| **Cost** | LLM API cost per analysis (USD) |
| **Tokens** | Total tokens per analysis |

Fix correctness is verified automatically: the fix is applied to a temporary
copy of the source file and the script is re-run.

### 4.3 Results

**Table 1: Aggregate metrics averaged across all 8 benchmarks.**

| Variant | Exc Match | KW Cov. | Fix Proposed | Test Gen. | Fix Correct | Avg Cost | Avg Tokens |
|---|---|---|---|---|---|---|---|
| Baseline | 88% | 57% | 75% | 12% | 50% | $0.019 | 1,641 |
| +Repo | 100% | 77% | 100% | 75% | 75% | $0.024 | 2,081 |
| +Git | 100% | 72% | 100% | 50% | 62% | $0.024 | 2,069 |
| +Repo+Git | 100% | **89%** | 100% | **88%** | **88%** | $0.026 | 2,511 |

**Key findings:**

1. **Repository context (+Repo) is the single most impactful feature**, improving
   keyword coverage by 20 pp and fix correctness by 25 pp over baseline. This
   confirms that root causes frequently lie in imported modules not directly
   visible in the stack trace.

2. **Git context (+Git) alone improves recall modestly** (+15 pp KW coverage,
   +12 pp fix correctness), with its largest gains on regression-type bugs where
   the `git diff` identifies the introducing commit.

3. **Combining both contexts achieves the best results** across all metrics. The
   improvement is super-additive for test generation (12% → 88%), suggesting that
   both context types are needed for the LLM to generate runnable tests.

4. **Cost is modest and predictable**: the full +Repo+Git variant costs on average
   $0.026 per analysis, a 38% increase over baseline for a 56% improvement in
   keyword coverage.

5. **Exception type identification is robust** across all variants (88–100%),
   confirming that traceback parsing and prompt construction are reliable.

---

## 5. Discussion

### 5.1 When does +Repo help most?

Repository context provides the largest improvement on bugs where the root cause
is in a helper function imported by the crashed module (e.g., `sample_swapped_args`,
`none_attribute_access`). For self-contained bugs like `testme_zero_division`,
the improvement is marginal — the answer is already visible in the stack trace.
This suggests a heuristic: use `--repo` when the crash occurs in application
code that imports project-defined modules.

### 5.2 When does +Git help most?

Git context is most valuable for regression bugs — those introduced by a recent
commit. In our benchmark, `off_by_one_index` and `recursion_overflow` showed the
largest gains with +Git, consistent with these being introduced by a code change
visible in `git diff HEAD~1`. For bugs that have existed in the codebase for
many commits, git context adds noise rather than signal.

### 5.3 Limitations

**Static matching**: Root-cause keyword scoring is a proxy for correctness.
A response can achieve 100% keyword coverage while misidentifying the root cause,
or correctly identify the cause without using the expected keywords. Future work
should use LLM-as-judge evaluation for semantic correctness.

**Fix correctness is a necessary but not sufficient condition**: A fix may
make the script exit cleanly on the original input while introducing a new bug
on different inputs. Test generation partially addresses this by creating
regression guards, but full correctness requires a broader test suite.

**Source file availability**: Post-mortem analysis requires the source files to
be present at the paths recorded in the traceback. For crashes from deployed
binaries or containerized environments, source context may be unavailable.

**Single-model evaluation**: All experiments use GPT-4o. Model choice affects
both accuracy and cost; future work should benchmark across Claude, Gemini,
and open-source models.

---

## 6. Conclusion

We presented ChatDBG-MTP, an extension of ChatDBG that enables post-mortem
debugging from crash logs, enriches LLM context with import-graph traversal and
git history, and closes the repair cycle with automated fix application and test
generation. Our evaluation on 8 benchmarks demonstrates consistent, measurable
improvements: adding repository and git context together raises root-cause keyword
coverage from 57% to 89% and fix correctness from 50% to 88%, at a modest cost
increase of 38%.

The evaluation harness introduced in this work enables systematic comparison of
context strategies and model choices, providing a foundation for future research
into AI-assisted program repair.

---

## References

1. Berger, E., Freund, S., Levin, K., & van Kempen, N. (2025). *ChatDBG: An
   AI-Powered Debugging Assistant*. FSE 2025.

2. Le Goues, C., Nguyen, T., Forrest, S., & Weimer, W. (2012). *GenProg: A
   Generic Method for Automatic Software Repair*. IEEE TSE.

3. Long, F., & Rinard, M. (2016). *Automatic Patch Generation by Learning
   Correct Code*. POPL 2016.

4. Mechtaev, S., Yi, J., & Roychoudhury, A. (2016). *Angelix: Scalable
   Multiline Program Patch Synthesis via Symbolic Analysis*. ICSE 2016.

5. Chen, M., Tworek, J., et al. (2021). *Evaluating Large Language Models
   Trained on Code*. arXiv:2107.03374.

6. Nashid, N., Sintaha, M., & Mesbah, A. (2023). *Retrieval-Based Prompt
   Selection for Code-Related Few-Shot Learning*. ICSE 2023.

7. Jones, J. A., & Harrold, M. J. (2005). *Empirical Evaluation of the Tarantula
   Automatic Fault-Localization Technique*. ASE 2005.

---

## Appendix: Running the Evaluation

**Install dependencies:**
```bash
pip install -e .
pip install matplotlib pandas seaborn numpy
```

**Run the evaluation harness:**
```bash
export OPENAI_API_KEY=your_key
python eval/run_eval.py
python eval/run_eval.py --variant baseline
python eval/run_eval.py --output my_results.json
```

**Generate graphs (from real or sample results):**
```bash
python paper/generate_graphs.py                              # sample data
python paper/generate_graphs.py --results eval_results.json # real data
```

Generated figures are saved to `paper/` as `fig1_accuracy.png` through
`fig6_tokens.png`.
