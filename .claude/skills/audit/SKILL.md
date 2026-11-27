---
name: audit
description: Audits the repo through one lens (perf, bugs, debt or security) with parallel reviewers and writes a ranked findings file, and it edits no code.
argument-hint: <perf|bugs|debt|security> [paths]
---

# Audit workflow

You are the manager: send the reading to `code-reviewer`, keep only the findings in this session.

Target: $ARGUMENTS

Call crew agents without a `model`: each carries its own. One exception: an agent that failed twice on the same task is re-run once with `model` one tier up (sonnet to opus, opus to fable), never a third time at the same tier.

1. **Target.** The first word is the lens; if it is not one of the four lenses, ask. Paths default to the whole repo minus generated and vendored folders.
2. **Scope.** Count files and size only (`git ls-files -- <paths>`), then split the paths into at most 4 areas. Above about 400 files, ask the user to narrow the paths or agree to a sample.
3. **Find.** Run `code-reviewer` once per area, in parallel, in one message, in lens mode: give it the paths, the lens, the lens checklist below and the invariants from the project `CLAUDE.md`. Each brief carries a budget at or below the reviewer's own `Budget:` line ("at most 30 tool calls, hand back what you have"), asks for an effort estimate (S/M/L) per finding, and asks the reviewer to list what it did not read. Pass `effort: "medium"` on these calls: an offline replay measured recall within its preset bar at about 0.7x the cost, while disprove passes measured weaker at medium.
   - perf: N+1 queries, work in hot loops, blocking I/O on request paths, unbounded memory or result sets, missing indexes or caching.
   - bugs: wrong edge cases, swallowed errors, races, partial failure, type-safety escapes.
   - debt: duplication, dead code, layering violations against the repo's patterns, missing or weak tests, outdated or unused dependencies.
   - security: authorization before action, injection, secrets, personal data in logs, risky dependencies.
4. **Disprove.** With zero findings, skip this step. Otherwise run one disprove pass per area: a second `code-reviewer` call in disprove mode, given that area's findings, whose only job is to disprove each one (look for the guard or the measurement that refutes it). Keep what survives, and keep a PARTLY verdict with its corrected claim.
5. **Write.** A ranked table in a file: folder from the project `CLAUDE.md`, default `docs/audits/<lens>-<YYYY-MM-DD>.md`. Columns: rank, severity, `file:line`, failure scenario or cost, suggested fix, effort (S/M/L). Add what was dropped and why, and a coverage line listing what was not read.
6. **Hand off.** The user picks findings. Offer `/feature` for changes and `/debug` for confirmed bugs.

Rules:
- Edit no code, only the findings file.
- Never copy a secret or personal data value into the findings file: cite `file:line` only.
- For the security lens, ask before committing or pushing the findings file.
- Never commit on a protected branch: create a branch with `git checkout -b <branch>` before committing the file.
