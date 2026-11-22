---
name: crew-update
description: Updates the vendored crew workflow in this repo from the public redgreen marketplace and proposes the change as a pull request, so use it when asked to update, refresh or upgrade the crew agents, skills or hooks.
---

# Update the vendored crew workflow

1. **Preview.** Run `.claude/hooks/crew/crew-update.sh --dry-run` and show the user the plan it prints. A result of `up-to-date` ends the task.
2. **Ask.** Get the user's OK before anything is created or pushed.
3. **Apply.** On the OK, run `.claude/hooks/crew/crew-update.sh` without flags: it pushes a `chore/crew-update-<rev>` branch and opens a pull request. When the user wants no push, run it with `--local`: it only commits on a local branch.
4. **Blocked.** When the result is `blocked (edited: ...)`, list the edited files and ask the user, per file, to keep or take. Take: delete the local edit, so the update installs the plugin version. Keep: first move the local change to a differently named file with a different frontmatter `name:` (the same name under another file is a CLASH), then delete the vendored file so the update restores it. The script plans on `origin/<base>`, so merge the deletion to the base branch before running the script again.
5. **Never** push to the protected branch, never force-push, and never edit the vendored files by hand to get past a block.

Report the one-line `crew-update <result>` the script prints, and the pull request URL when there is one.
