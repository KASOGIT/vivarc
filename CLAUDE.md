# Vivarc

Vivarc brings Arc's sidebar and command bar to Vivaldi on macOS and Windows: an installer (`vivarc.py`) patches the user's Vivaldi install and profile `Preferences`, and a plain JS and CSS mod runs inside Vivaldi's UI. A mistake can break a user's browser profile or leave Vivaldi half patched on a machine we never see, so the installer, uninstall and preference patching must stay reversible.

## Repo map

- `vivarc.py`: the CLI (`install`, `apply`, `update`, `uninstall`, `status`, `reminder`, `import-arc`), preference patching, the update reminder.
- `src/js/*.js`: the mod, concatenated in file-name order by `apply`. `src/css/vivarc.css`: its styles. `src/start/`: the start page. `src/optional/`: optional pieces.
- `tests/`: `unittest` suites. `tests/jsrun.py` loads one `src/js` file in node with a fake `window`; `tests/platforms.py` holds per-OS helpers.
- `tools/arc_import.py`: import from Arc. `tools/demo/`: scripts behind the README demo (see the `demo` skill).
- `templates/`: files offered to users (Finicky config).
- `docs/HOW-IT-WORKS.md`: architecture and Vivaldi quirks. Read its "Notes for contributors" before touching toolbars, preferences, tiling or Peek.
- `install.sh`, `install.ps1`: one-line installers from the README.

## Commands

Run from the repo root. No dependencies, no build step. Use `python` instead of `python3` on Windows.

| Task | Command |
|---|---|
| Install | nothing to install; node is needed for the JS tests |
| Run | quit Vivaldi, then `./vivarc.py apply` (rebuilds the mod and puts it into Vivaldi) |
| All tests | `python3 -m unittest discover -s tests` |
| One test file | `python3 -m unittest discover -s tests -p test_pins.py` |
| One test | `python3 -m unittest discover -s tests -p test_pins.py -k <name>` |
| Type-check | none |
| Lint | none |
| Format | none, match the surrounding code |

The JS suites are skipped when `node` is not on PATH, so a green run without node has not tested the JS.

Before committing: all tests. After a change to the mod, run `./vivarc.py apply` so the maintainer can try it in Vivaldi, preferably in a throwaway profile.

## Git and PRs

- Base branch: `main`. Protected: `main` (GitHub ruleset `protect-main`). Never commit or push to `main` without explicit confirmation; branch with a plain `git checkout -b <branch>`.
- Commits and PR titles: Conventional Commits (`feat(scope):`, `fix(scope):`, `docs:`, `chore:`), scope is the feature area (`sidebar`, `spaces`, `command-bar`, `peek`, `update`...). PRs are squash merged, one thing per PR.
- Update `README.md` or `CHANGELOG.md` when behavior changes. Releases (`chore: release x.y.z`) credit contributors in the changelog and release notes.
- Never post to GitHub (comments, merges, closes) without asking; the `triage` skill prepares those for the maintainer.

## Escalate, do not act

Stop with root cause, options and a recommendation, and wait, for: preference patching (`patch_preferences` and anything that writes Vivaldi's profile files), install, uninstall, self-update and the update reminder (launchd, scheduled task), releases (version bumps, tags, GitHub releases), Arc import and anything that reads or writes user data (bookmarks, pins, profiles), new dependencies, architecture choices and deviations from existing patterns.

## Invariants

- `uninstall` puts everything back: every install-time change has a matching restore.
- Tests never reach the real machine: mock `open_settings`, `launchctl`, `ask` and `vivaldi_running` (an unmocked `open_settings` opens System Settings on every run). Copy the patches in `tests/test_install_flow.py`.
- Python code stays compatible with the version pinned in `.github/workflows/test.yml` (macOS's system Python) and runs on both macOS and Windows; CI runs both.
- No runtime dependencies: standard library Python, plain JS and CSS with no build step.
- The mod uses only what Vivaldi exposes to mods (`chrome.*`, `vivaldi.*`); it cannot call Vivaldi's own commands.
- Vivaldi profile files are edited only while Vivaldi is closed; live changes go through `vivaldi.prefs.set` by name.

## Rules and agents

- Spec-first protocol and this repo's test commands: `.claude/rules/tdd.md`.
- Workflow: `/feature`, `/debug`, `/review`. Repo skills: `demo` (README demo), `triage` (PR and issue round).
- Keep the main conversation small: hand work whose output you only need summarized to the agents in `.claude/agents/`. Test runs go to `test-runner`, reading an unfamiliar area to `domain-researcher`, long logs and traces to `debugger-analyst`, a diff to `code-reviewer`. Decisions and anything about the user's intent stay in the main conversation.
