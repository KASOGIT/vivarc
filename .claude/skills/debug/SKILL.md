---
name: debug
description: Use when asked to debug, investigate a failing test or error, or find why something breaks: finds the root cause, reproduces it with a failing test, fixes it minimally and verifies.
argument-hint: <symptom, error or failing test>
---

# Debug workflow

You are the manager: keep summaries in this session, send long traces and logs to `debugger-analyst`.

Symptom: $ARGUMENTS

1. **Understand.** Restate the symptom as literals: input, expected result, actual result. Ask when the expected result is not clear.
2. **Search.** Run `debugger-analyst` with the symptom, the failing command and the logs location. It returns the root cause with evidence, a minimal reproduction, a proposed fix and its risk. Open the evidence yourself before believing it.
3. **Diagnose further if needed.** When the cause is not proven, add diagnostics (temporary logging or a probe test), run it, and remove it afterwards.
4. **Escalation check.** If the fix touches an irreversible effect (moving value, sending, deleting, publishing), auth, a migration on existing data or a production admin command (or anything the project `CLAUDE.md` lists), stop here. Report the root cause, the proposed fix and the risk, and ask before acting.
5. **Reproduce.** Run `test-engineer` to write a test that reproduces the bug, red for the right reason, before any fix.
6. **Fix.** Run `implementer` for the minimal fix. Never change the test's expected value to fit the code.
7. **Verify.** Run `test-runner` for the repro test plus the affected tests (pass it the base branch), type-check and lint, then the full suite. If it fails, fix and re-run until a full suite passes after the last change.
8. **Summarize.** Root cause, fix, evidence pasted, follow-ups.

Do not end the session until all four are true: root cause documented, fix implemented, tests pass, no new type errors. Exception: the escalation stop in step 4.

If blocked, write a checkpoint: root cause so far, proposed fix, what blocks, next steps.
