# Contributing to Vivarc

Contributions are very welcome, and it means a lot that you are here. Vivarc is a small project and every bug report, idea, test on a different setup or pull request genuinely helps. You do not need to be an expert: if something confused you, that is already useful feedback.

## Ways to help

- **Try it and tell us what happened.** Especially on other Vivaldi 8.x versions and other macOS versions. Say what worked and what did not.
- **Report a bug** with the details below.
- **Suggest or build a feature.** Ideas we would love help with: Windows and Linux support, automatic archiving of old tabs, "Move to" for pinned items, renaming pins, Boosts-style per-site tweaks, translations of the guide page.
- **Improve the docs**: clearer install steps, better screenshots, typos.
- **Review code.** Reading a pull request and saying "this was unclear to me" is a real contribution.

If you plan something big, open an issue first so we can agree on the approach before you spend time on it. Small fixes can go straight to a pull request.

## Reporting a bug

Please include:
- macOS version and Vivaldi version (Vivaldi menu > About Vivaldi)
- the output of `./vivarc.py status`
- what you did, what you expected and what happened (a screenshot helps)
- whether it happens in a brand-new profile

## Development setup

```sh
git clone https://github.com/KASOGIT/vivarc.git && cd vivarc
python3 -m unittest discover -s tests     # Python tests, no dependencies
```

The mod itself is plain JavaScript and CSS in `src/` (no build step). To try a change, quit Vivaldi (Cmd+Q) and run `./vivarc.py apply`; it rebuilds the script and puts it into Vivaldi. Use a throwaway Vivaldi profile for testing. `./vivarc.py uninstall` puts everything back.

[docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md) explains the pieces and has a list of Vivaldi quirks that took a while to find. Please read the notes at the end before touching toolbars, preferences or tiling.

## Pull requests

- Branch from `main`, and keep each pull request about one thing.
- Use [Conventional Commits](https://www.conventionalcommits.org/) for messages (`feat:`, `fix:`, `docs:`...).
- Add or update a Python test when you change the installer or the preference patching. For the JavaScript, describe how you checked it in a real Vivaldi window.
- Match the style of the surrounding code, and keep comments for things that are not obvious.
- Update the README or `CHANGELOG.md` when behaviour changes.

Be kind in issues and reviews. Everyone here is volunteering their time.
