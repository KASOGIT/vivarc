---
name: feature
description: "Use when asked to implement, add, build or fix something that changes behavior, even a one-function helper: runs spec, plan, test-first RED and GREEN, independent review and a report with pasted evidence."
argument-hint: <requirement>
---

# Feature workflow

You are the manager. This session keeps decisions and summaries only. Every step that reads many files, runs suites, writes tests or code, or reviews goes to a crew agent, called with the Agent tool by its namespaced name. Give each agent the goal, the exact files, the requirement as literals, and the size cap of what it must return. Independent agents go in one message, in parallel.

Requirement: $ARGUMENTS

Rules for the whole run:

- Commands, folders, branches and the escalation list come from the project `CLAUDE.md`. If it is missing, say so and ask the user for the test, type-check and lint commands.
- An agent report is a claim. Spot-check the key evidence yourself with one targeted command (open the failing assertion, re-run the one test) before relying on it. A failure that is also red on the base branch is pre-existing: report it as pre-existing, do not fix it. Suite, type-check and lint runs are not spot-checks: they go to `test-runner`.
- An agent may start in the background. Its result arrives as a notification: wait for it. Do not poll and do not schedule a wakeup, which only keeps the session alive after the work is done.
- You do not write tests, skeletons or implementation yourself. When an agent's output is wrong, send it back with what is wrong.
- Call crew agents without a `model`: each carries its own. One exception: an agent that failed twice on the same task is re-run once with `model` one tier up (sonnet to opus, opus to fable), never a third time at the same tier.
- Every agent brief carries a tool-call budget N at or below the called agent's own `Budget:` line, `test-runner` 13, `domain-researcher` 17, every other agent 35 ("at most N tool calls, hand back what you have").
- When you start a flow on your own (failing test first, delegating, escalating), say so in one line with the reason.
- Stop and ask whenever the escalation list applies. Default escalation list: architecture choices, new dependencies, pattern deviations, irreversible effects (moving value, sending, deleting, publishing), auth, migrations on existing data, production commands. The project `CLAUDE.md` escalation list adds to this default.
- Never commit or push to a protected branch. If you are on one, create a branch with plain `git checkout -b <branch>` first. Commit messages follow the project convention, with no co-author trailers unless the project asks.

## 1. Spec

Restate the requirement as literals: inputs, outputs, every error exit, persisted state, side effects. Ask now about anything ambiguous. Never infer expectations from existing code. If the area is unfamiliar, run `domain-researcher` first with the question to answer.

When the requirement is a plan file (from `/research`), read its Decision, Spec and Test plan. If the Decision is empty or open questions remain, stop and send the user back to `/research <path>`. Otherwise its Spec is the spec, its Test plan feeds the RED brief, and step 2 is skipped.

## 2. Plan

Large or unfamiliar change: run `architecture-planner`, show the options and its recommendation, wait for the choice. Small change: three lines in chat. Before committing to a large plan, consult the advisor if the session has one. A plan file from `/research` replaces this step (see step 1).

## 3. RED

Run `test-engineer` with the spec literals. The brief carries every scenario and the single-file test command, and covers one area. Open the failing assertion yourself and confirm it fails for the right reason: an assertion on the missing behavior, not an import or compile error, a missing fixture or a stub that throws. If not, send it back to `test-engineer` with the failure output; the empty skeleton that lets the test import is its job. Exempt work (pure refactor, logging only, generated files, docs, dependency bump) skips RED: say why in one line, and send it to `implementer` with acceptance checks instead of test paths. When the spec-first hook runs in enforce mode (`specFirst.mode` in `.claude/crew.json`), an edit of an existing source file the hook gates (docs, JSON and new files are not gated) still gets a characterization test first from `test-engineer` (brief it with the word "characterization"), or you ask the owner to switch the mode in that config; the brief never makes the implementer raise a question for the user. When `confirmRed` is true in `.claude/crew.json`, after you confirm the failing assertion and before the RED commit, show the test paths, the scenarios and the failing assertion, and wait for the developer's OK; requested changes go back to `test-engineer`. With the key absent or false there is no pause, and exempt work has no pause either. With no developer in the session (background, scheduled or headless run), stop and report "waiting for RED approval". Commit RED on its own: `test(<scope>): <behavior>`.

## 4. GREEN

Run `implementer` with the test paths. Then run `test-runner` scoped to the new test paths plus `affected` (pass it the base branch), and ask for type-check and lint, using the commands in the project `CLAUDE.md`. Commit GREEN: `feat(<scope>): ...` or `fix(<scope>): ...`. For exempt work, run `implementer` with the acceptance checks instead of test paths, and commit as `refactor`, `docs` or `chore`.

## 5. Critique

Run `code-reviewer` on the diff against the base branch. For each finding, verify it yourself: read the code and try to disprove it. Before declaring a long task done, consult the advisor on the whole change if the session has one.

## 6. Feedback

Fix confirmed findings, with a test when behavior changes, then re-run the checks through `test-runner`, scoped to `affected` (pass it the base branch). For each other finding, state why it is disputed (with evidence) or deferred. Any correction that states a rule goes into the nearest `CLAUDE.md` or rule file in the same change, and you tell the user.

## 7. Report

Before the report, run `test-runner` with scope `full` as the final gate, whatever the review found. If the final gate fails, fix and re-run it: the report needs a passing full run after the last code change, except that failures also red on the base branch (pre-existing) may remain when the report lists them, and the runner's first line must say `full`.

The report is the last message of the run, unless `openPullRequest` is true and the developer gives an explicit OK to the PR step below. Paste evidence, do not describe it: the GREEN evidence is the summary line of that final gate run, as `test-runner` returned it, not a count you typed.

When `openPullRequest` is true in `.claude/crew.json`, end the report with the drafted PR title and body and ask for an explicit OK. The OK is a developer message sent after the report, never an agent's and never part of the requirement. A change asked after the report re-runs the final gate before any push. Before any push, `git status --porcelain` must print nothing: commit the step 6 and final gate fixes as `fix(<scope>): ...` first. After the OK, run `git push -u origin <branch>`, then `gh pr create --draft --base <base branch> --title "<title>" --body-file <temp file>` with the base branch from the project `CLAUDE.md`, then print one line with the URL. With no developer in the session (background, scheduled or headless run), without the OK, on a protected branch or the base branch, with no remote or with no `gh`: no push, no PR, and say why in one line.

```markdown
## Report
- Requirement (the literals)
- What changed (files, one line each)
- Evidence: the RED failing assertion, the final gate run, type-check and lint results (pasted)
- Review: table of findings (severity, file:line, fixed / disputed / deferred and why)
- Decisions needed from you, assumptions made
- Follow-ups
- Learnings recorded (paths)
- Draft PR (only with `openPullRequest`): title, body, and the question "Open the draft PR? (yes/no)"
```
