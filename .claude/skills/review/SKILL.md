---
name: review
description: Reviews the current branch or a pull request in a clean context and disproves each finding before reporting, so use it when asked to review, critique or check a diff or PR.
argument-hint: [base branch, PR number or branch]
---

# Review workflow

Target: $ARGUMENTS (default: the current branch against the base branch named in the project `CLAUDE.md`).

The review is only independent if it happens in a context that has not seen this conversation, so you do not read the diff or judge it yourself: you scope it, hand it to the reviewer, and check what comes back.

1. **Scope.** Get the file list and size only: `git diff --stat <base>...<branch>`, or `gh pr diff <number> --name-only` for a PR. Never check out another branch in the working directory.
2. **Review.** Call the Agent tool with `code-reviewer`, giving it the diff command to run, the base branch and the invariants from the project `CLAUDE.md`. For a large diff, split by area and launch several reviewers in parallel in one message.
3. **Disprove.** For each finding, run a second pass whose only job is to disprove it: read the code around it, look for the guard the finding says is missing, try to build the failing scenario. Keep only what survives.
4. **Consolidate.** Report a table: severity, `file:line`, the failure scenario, the suggested fix, and what was dropped as disproved with one line of reason.
5. **Ask before posting.** Never post to a PR, comment on GitHub or message anyone without the user's explicit OK.
6. **Offer fixes.** Offer to fix the confirmed findings. Fixes follow the test-first flow: a failing test when behavior changes (`/feature` or `/debug`).
