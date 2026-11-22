---
name: review
description: Reviews the current branch or a pull request in a clean context and disproves each finding before reporting, so use it when asked to review, critique or check a diff or PR.
argument-hint: [base branch, PR number or branch]
---

# Review workflow

Target: $ARGUMENTS (default: the current branch against the base branch named in the project `CLAUDE.md`).

Call crew agents without a `model`: each carries its own. One exception: an agent that failed twice on the same task is re-run once with `model` one tier up (sonnet to opus, opus to fable), never a third time at the same tier. Every agent brief carries a tool-call budget N at or below the called agent's own `Budget:` line, 35 for `code-reviewer` ("at most N tool calls, hand back what you have").

The review is only independent if it happens in a context that has not seen this conversation, so you do not read the diff or judge it yourself: you scope it, hand it to the reviewer, and check what comes back.

1. **Scope.** Get the file list and size only: `git diff --stat <base>...<branch>`, or `gh pr diff <number> --name-only` for a PR. For a PR, run `git fetch origin pull/<number>/head` first, so `git show FETCH_HEAD:path` can read its files. Uncommitted work counts when the target is the current branch: run `git status --porcelain`, add `git diff HEAD --stat` for tracked changes and `git ls-files --others --exclude-standard` for untracked files to the scope. Never check out another branch in the working directory.
2. **Review.** Call the Agent tool with `code-reviewer`, giving it the diff command to run (plus `git diff HEAD` and `git ls-files --others --exclude-standard` for uncommitted work), the base branch and the invariants from the project `CLAUDE.md`. For a large diff, split by area and launch several reviewers in parallel in one message.
3. **Disprove.** With zero findings, skip this step. Otherwise run one disprove call per review area: a second `code-reviewer` call in disprove mode, given that area's findings, the diff command (with the `git diff HEAD` and `git ls-files --others --exclude-standard` commands for uncommitted work) and the base branch, whose only job is to disprove each one: look for the guard the finding says is missing, try to build the failing scenario. Keep what survives, keep a PARTLY verdict with its corrected claim, and check what was dropped and why.
4. **Consolidate.** Report a table: severity, `file:line`, the failure scenario, the suggested fix, and what was dropped as disproved with one line of reason.
5. **Ask before posting.** Never post to a PR, comment on GitHub or message anyone without the user's explicit OK.
6. **Offer fixes.** Offer to fix the confirmed findings. Fixes follow the test-first flow: a failing test when behavior changes (`/feature` or `/debug`).
