---
name: research
description: Use when asked to research, investigate options for or plan something unclear before building it, to research with the crew and iterate on a plan file that then goes to the feature workflow.
argument-hint: <subject or plan path>
---

# Research workflow

You are the manager: delegate the reading to the crew, keep summaries in this session, and write the plan file yourself (the agents are read-only).

The manager does not do the reading itself: it always runs `domain-researcher` (then `architecture-planner` for options), and a small or tiny subject or repo is no exception.

Subject: $ARGUMENTS

Call crew agents without a `model`: each carries its own. One exception: an agent that failed twice on the same task is re-run once with `model` one tier up (sonnet to opus, opus to fable), never a third time at the same tier. Every agent brief carries a tool-call budget N at or below the called agent's own `Budget:` line, `domain-researcher` 17, `architecture-planner` 35 ("at most N tool calls, hand back what you have").

1. **Subject.** If it is a path to an existing plan file, resume it: read it and continue from its open questions.
2. **Frame.** Restate the question as literals: inputs, expected outcome, constraints. Ask about whatever is ambiguous.
3. **Research.** Run `domain-researcher` for the constraints (repo docs, decision records, code; the web when the subject needs outside facts), then `architecture-planner` for options with a recommendation. Launch independent agents in parallel, in one message. Spot-check the key evidence yourself.
4. **Write the plan file.** Folder from the project `CLAUDE.md`, default `docs/plans/<slug>.md`. Sections: Question, Constraints, Options, Recommendation, Decision, Spec (literals), Test plan, Open questions.
5. **Iterate.** Each round ends with the plan path, a short summary and the open questions, then wait for the user. On feedback, revise the same file. Delegate new reading again rather than reading many files yourself.
6. **Hand off.** When the Decision is filled and no open questions remain, offer `/feature <plan path>`.

Rules:
- Edit no code, only the plan file.
- Never commit on a protected branch: create a branch with `git checkout -b <branch>` before committing the plan file.
- The escalation list in the project `CLAUDE.md` applies: stop and ask before anything on it.
