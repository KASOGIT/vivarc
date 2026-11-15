---
name: triage
description: Review Vivarc's open pull requests and issues on GitHub, see what changed since the maintainer last spoke, review new ones, and prepare merges, closes and replies for the maintainer to run. Use for the regular round: triage, "the PR and issue round", check what's new on GitHub. Not for a code review of one PR (use /crew:review).
---

# PR and issue triage

The goal of a round: every open PR and issue ends merged, closed, or with a clear next step owned by someone. The maintainer (`KASOGIT`) decides; you analyse, review, draft and prepare.

## 1. Digest (one call, no diffs yet)

```sh
python3 .claude/skills/triage/digest.py            # everything
python3 .claude/skills/triage/digest.py NEW UPDATED # only what moved
```

States: **NEW** (maintainer never spoke), **UPDATED** (a contributor commented or pushed after the maintainer's last word), **OWNER_LAST** (maintainer spoke last). `idle=Nd` is days since any event. Issues closed by an open PR are folded into that PR.

For each OWNER_LAST item, read the printed "last owner word" and decide whose turn it is:
- **Theirs** (asks for a rebase, screenshots, an answer): nothing to do unless idle is long (see step 3).
- **Mine** ("I'll look at it", a promised follow-up, a question only the maintainer can answer): list it as owner work.
- **Blocker now gone** ("goes after #X", "after #X is merged"): check `gh pr view X --json state,mergedAt`. If X is merged, draft an "unblocked" update.

Also check `git log --oneline -30` for merged PRs that complete an open issue or one of its steps ("Part of #N", "Closes #N"): draft a progress note, or a close when nothing is left.

## 2. Review what is new or updated

Only for NEW and UPDATED PRs, and OWNER_LAST PRs where the contributor's turn is done:
- `gh pr view N --json body,files,commits` and `gh pr diff N`. Compare with the maintainer's earlier asks: is each one done?
- For a deep review, hand the diff to `crew:code-reviewer` (or `/crew:review N`), briefed with the maintainer's earlier comments.
- Check against CONTRIBUTING.md: one thing per PR, Conventional Commit title, Python test for installer or preference changes (machine-touching calls mocked), "how I checked it" for JS, README or CHANGELOG updated when behaviour changes, before and after screenshots (light, dark, Liquid Glass) for look changes.
- Read `docs/HOW-IT-WORKS.md` quirks before judging changes to toolbars, preferences or tiling.
- `CI=NONE` on a first-time fork PR usually means the maintainer must click "Approve and run workflows".

For NEW issues: is it a bug (ask for Vivaldi version, OS, `./vivarc.py status`, new-profile repro if missing), a duplicate (link it), already done in a release (say which), or a feature (fit with the roadmap, size, what a first small PR would be)?

## 3. Recommend, then ask

Present one compact table: item, state, idle, what changed, recommendation (merge / close / reply / nudge / owner work / leave). Then ask the maintainer only the real decisions with `AskUserQuestion` (self-contained questions, 4 at most per call). Typical ones:
- Close or nudge a PR that has been waiting on its author for 7+ days after "can't accept as is". Closing is always the maintainer's call.
- Take over a PR that is one small fix away (push to the contributor's branch, then merge).
- Whether to post an answer whose facts you could not verify.

## 4. Before a merge

1. `gh pr checkout N`, then `python3 -m unittest discover -s tests` (and any `node --test` the PR adds).
2. For JS or CSS changes, check the behaviour in a throwaway Vivaldi profile. `./vivarc.py apply` needs the maintainer's Vivaldi quit, so ask first, quit it with `osascript -e 'quit app "Vivaldi"'`, and reopen it at the end.
   - Profile: `tools/demo/demo.sh setup`. It can fail at the end (consent walls), and the profile is still usable. CDP is on port 9335.
   - Drive the profile with a small Node script in the scratchpad: `import { connect } from "<repo>/tools/demo/cdp.mjs"` to read or set state, e.g. `window.__vm.settings.set(key, value)` or `chrome.tabs.update(id, {active: true})`. Send real keys with `~/.cache/vivarc-demo/input "key 37 cmd; wait 900"` (build it once: `swiftc -O tools/demo/input.swift -o ~/.cache/vivarc-demo/input`). Bring the demo window to the front first. Check state with `document.activeElement` and the DOM, and take `screencapture -x -R100,80,1280,800` shots.
   - Use Node, not zsh loops, for test matrices: zsh does not word-split `$var`.
   - At the end: `tools/demo/demo.sh clean`, `git checkout main`, `./vivarc.py apply`, `open -a Vivaldi`.
3. Squash with a Conventional Commit subject that keeps the PR number: `feat(scope): what (#N)`.
4. Contributor thanks go into `CHANGELOG.md` and the release notes at release time (see the release process). No separate PR for it.
5. After the maintainer runs the merges: `git pull` on `main` and `./vivarc.py apply` so they can try it.

## 5. Hand the GitHub writes to the maintainer

You cannot post, merge or close on GitHub yourself. Write every action into one script in the scratchpad, e.g. `<scratchpad>/triage-YYYY-MM-DD.sh`:

```sh
#!/bin/sh
set -e
gh issue comment 126 --repo KASOGIT/vivarc --body-file <scratchpad>/126.md
gh pr merge 144 --repo KASOGIT/vivarc --squash --subject "feat(command-bar): Cmd+L edits the page's address in the command bar (#144)" --admin
gh pr close 103 --repo KASOGIT/vivarc --comment "..."
```

- `--admin` is required: the `protect-main` ruleset blocks a plain `gh pr merge` even with green CI.
- Put long comments in their own `.md` files and use `--body-file`.
- Show the maintainer every comment's text before handing over the script, then copy `! bash <absolute path>` with `pbcopy` and say it is on the clipboard.
- Force-pushes to a contributor's fork go the same way (a `!` command the maintainer runs).

## Writing comments

Write in the maintainer's voice, as in past comments: start with "Thanks @user." and one line on what is good, then numbered, concrete asks naming files, settings and PR numbers. Kind and direct. Never an em dash or en dash: use a comma, colon, parentheses or a new sentence. When closing, say why in one sentence and what would make a new PR welcome.
