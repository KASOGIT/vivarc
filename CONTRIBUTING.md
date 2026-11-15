# Contributing to Vivarc

Contributions are very welcome, and it means a lot that you are here. Vivarc is a small project and every bug report, idea, test on a different setup or pull request genuinely helps. You do not need to be an expert: if something confused you, that is already useful feedback.

## Ways to help

- **Try it and tell us what happened.** Especially on other Vivaldi 8.x versions and other macOS or Windows versions. Say what worked and what did not.
- **Report a bug** with the details below.
- **Suggest or build a feature.** Ideas we would love help with: Linux support, automatic archiving of old tabs, "Move to" for pinned items, renaming pins, Boosts-style per-site tweaks, translations of the guide page.
- **Improve the docs**: clearer install steps, better screenshots, typos.
- **Review code.** Reading a pull request and saying "this was unclear to me" is a real contribution.

If you plan something big, open an issue first so we can agree on the approach before you spend time on it. Small fixes can go straight to a pull request.

## Reporting a bug

Please include:
- macOS or Windows version and Vivaldi version (Vivaldi menu > About Vivaldi)
- the output of `./vivarc.py status`
- what you did, what you expected and what happened (a screenshot helps)
- whether it happens in a brand-new profile

## Development setup

```sh
git clone https://github.com/KASOGIT/vivarc.git && cd vivarc
python3 -m unittest discover -s tests     # Python tests, no dependencies (Windows: python -m unittest discover -s tests)
```

The mod itself is plain JavaScript and CSS in `src/` (no build step). To try a change, quit Vivaldi (Cmd+Q) and run `./vivarc.py apply`; it rebuilds the script and puts it into Vivaldi. Use a throwaway Vivaldi profile for testing. `./vivarc.py uninstall` puts everything back.

[docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md) explains the pieces and has a list of Vivaldi quirks that took a while to find. Please read the notes at the end before touching toolbars, preferences or tiling.

## Pull requests

- Branch from `main`, and keep each pull request about one thing.
- Use [Conventional Commits](https://www.conventionalcommits.org/) for messages (`feat:`, `fix:`, `docs:`...).
- Add or update a Python test when you change the installer or the preference patching. Tests must mock anything that reaches the real machine (`open_settings`, `launchctl`, `ask`, `vivaldi_running`): an unmocked `open_settings` pops System Settings > App Management on every run. For the JavaScript, describe how you checked it in a real Vivaldi window.
- Match the style of the surrounding code, and keep comments for things that are not obvious.
- Update the README or `CHANGELOG.md` when behaviour changes.

## Working with an AI coding agent

Using Claude Code, Cursor, Codex or another agent is fine. You still own the pull request: read the whole diff, run the tests, try the change in a throwaway Vivaldi profile, and say in the description how you checked it.

The repository ships a setup for [Claude Code](https://claude.com/claude-code). Open the repo and it is active, with nothing to install:

| File | What it gives the agent |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | What Vivarc is, the repo map, the commands, git rules, invariants, and what to stop and ask about instead of doing (preference patching, install and uninstall, releases, Arc import) |
| [`.claude/rules/tdd.md`](.claude/rules/tdd.md) | Test first for `src/js`, `vivarc.py` and `tools`: which test file to use, how to load the JavaScript in node, what must be mocked |
| `.claude/skills/` | `/feature <what you want>` (spec, failing test, code, review), `/debug <symptom>` (root cause, failing test, fix) and `/review` (independent review of your branch or a PR). `demo` and `triage` are for the maintainer |
| `.claude/agents/` | Helpers the skills hand work to: writing the test, implementing, running the suite, reviewing |
| `.claude/hooks/crew/` | A reminder when a `src/js` file is edited before any test was touched, and a guard against force-pushing or deleting `main`. They need `bash`, `git` and `jq` (Git Bash on Windows) and do nothing without `jq` |

A good start is `/feature` with the issue you are working on. For another agent, point it at `CLAUDE.md` and `.claude/rules/tdd.md`: they are plain Markdown.

The agents, the `feature`, `debug` and `review` skills and the hooks are copied from the crew plugin and recorded in `.claude/crew.lock.json`, so do not edit them in a pull request; open an issue instead. Fixes to `CLAUDE.md` and `.claude/rules/tdd.md` are welcome. Keep your own `.claude/settings.local.json` out of commits.

Be kind in issues and reviews. Everyone here is volunteering their time.
