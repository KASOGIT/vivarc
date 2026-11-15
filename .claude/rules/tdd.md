---
paths:
  - "src/js/**/*.js"
  - "vivarc.py"
  - "tools/**/*.py"
---

# Spec first (Vivarc)

Applies to feature and fix work that changes behavior. Exempt: pure refactors, logging-only changes, generated files, docs, dependency bumps, and CSS (no test harness; describe how it was checked in a real Vivaldi window). The protocol itself (right-reason red, independent oracle, tautology list) is built into the `test-engineer` agent. This file holds what is specific to this repo.

## Commands

- One test file: `python3 -m unittest discover -s tests -p test_<area>.py`
- One test: add `-k <name>` to the line above
- All tests: `python3 -m unittest discover -s tests`
- Type-check, lint: none

Run from the repo root with `discover -s tests`: there is no `tests/__init__.py` and the suites import `jsrun` and `platforms` as top-level modules. The JS suites skip without `node`, so check it is on PATH before trusting a green run.

## Where tests live

- `tests/test_<area>.py`, one file per feature area (`test_pins.py` for `src/js/08-pins.js`, `test_install_flow.py` for the installer).
- JS: load the module with `run_js("<file>.js", expr, **data)` from `tests/jsrun.py` and test the pure logic it exposes on `window.__vm` (for example `pins.plan`). Reference: `tests/test_pins.py`.
- Installer and CLI: reference `tests/test_install_flow.py` (temporary home, `mock.patch.object(vivarc, ...)`).
- Copy the structure from the references, never their expected values.

## Commits

- RED: `test(<scope>): <behavior>`, only the test, fixtures and scaffolding.
- GREEN: `feat(<scope>): ...` or `fix(<scope>): ...`.

## Repo specifics

- Always mock `open_settings`, `launchctl`, `ask` and `vivaldi_running`, and point every path constant (`HOME_DIR`, `REMINDER_PLIST`, app and command paths) into a temporary directory. Never touch the real Vivaldi profile, `~/.vivarc`, LaunchAgents or scheduled tasks.
- Behavior that only exists in Vivaldi's UI (DOM, drag and drop, toolbars) cannot be unit tested: extract the decision into a pure function on `window.__vm` and test that, then check the rest in a throwaway Vivaldi profile after `./vivarc.py apply`.
- Tests must pass on macOS and Windows: gate OS-specific tests with `mac_only`, `windows_only` or `posix_only` from `tests/platforms.py`.
- A hook blocking exempt work is not a reason to touch an unrelated test. Ask the user.
