---
name: debug
description: "Use when asked to debug, investigate a failing test or error, or find why something breaks: finds the root cause, reproduces it with a failing test, fixes it minimally and verifies."
argument-hint: <symptom, error or failing test>
---

# Debug workflow

You are the manager: keep summaries in this session, send long traces and logs to `debugger-analyst`.

The manager decides and delegates, and never writes or edits source or test files: every code change goes to `implementer`, and small or one-line fixes are no exception, once the step 4 escalation check clears, to the `debugger-analyst`, `test-engineer` and `implementer` steps.

Symptom: $ARGUMENTS

Call crew agents without a `model`: each carries its own. One exception: an agent that failed twice on the same task is re-run once with `model` one tier up (sonnet to opus, opus to fable), never a third time at the same tier. Every agent brief carries a tool-call budget N at or below the called agent's own `Budget:` line, `test-runner` 13, every other agent 35 ("at most N tool calls, hand back what you have").

1. **Understand.** Restate the symptom as literals: input, expected result, actual result. Ask when the expected result is not clear.
2. **Search.** Run `debugger-analyst` with the symptom, the failing command and the logs location. It returns the root cause with evidence, a minimal reproduction, a proposed fix and its risk. Open the evidence yourself before believing it.
3. **Diagnose further if needed.** When the cause is not proven, add diagnostics (temporary logging or a probe test), run them and remove them afterwards, all through `implementer`. Logging-only changes are exempt work: when the spec-first hook runs in enforce mode (`specFirst.mode` in `.claude/crew.json`), an edit of an existing source file the hook gates (docs, JSON and new files are not gated) still gets a characterization test first from `test-engineer` (brief it with the word "characterization"), or you ask the owner to switch the mode in that config.
4. **Escalation check.** Default escalation list: architecture choices, new dependencies, pattern deviations, irreversible effects (moving value, sending, deleting, publishing), auth, migrations on existing data, production commands. The project `CLAUDE.md` escalation list adds to this default. If the fix touches anything on the list, stop here. Report the root cause, the proposed fix and the risk, and ask before acting.
5. **Reproduce.** Run `test-engineer` to write a test that reproduces the bug, red for the right reason, before any fix. A check that already fails still goes to `test-engineer`, which reuses it as the reproduction when it fails for the root cause, or writes one that does.
6. **Fix.** Run `implementer` for the minimal fix. Never change the test's expected value to fit the code.
7. **Verify.** Run `test-runner` for the repro test plus the affected tests (pass it the base branch), type-check and lint, then the full suite. If it fails, fix and re-run by sending the failure back to `implementer`, until a full suite passes after the last change.
8. **Summarize.** Root cause, fix, evidence pasted, follow-ups.

Do not end the session until all four are true: root cause documented, fix implemented, tests pass, no new type errors. Exception: the escalation stop in step 4.

If blocked, write a checkpoint: root cause so far, proposed fix, what blocks, next steps.
