<h1 align="center">Vivarc</h1>

<p align="center">
  <b>Arc's sidebar and command bar, inside Vivaldi.</b><br>
  Favorites, pinned folders and open tabs in one panel. A Cmd+T command bar with quick actions. A theme editor. One command to install, one to remove.
</p>

<p align="center">
  <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-blue"></a>
  <img alt="macOS" src="https://img.shields.io/badge/platform-macOS-lightgrey">
  <img alt="Vivaldi 8" src="https://img.shields.io/badge/Vivaldi-8.x-ef3939">
  <img alt="No dependencies" src="https://img.shields.io/badge/dependencies-none-brightgreen">
</p>

<p align="center">
  <img src="docs/demo.gif" alt="Vivarc demo: split view, the command bar and a YouTube search shortcut in Vivaldi" width="860">
</p>

> **Arc is being discontinued on December 22, 2026**, according to the announcement email The Browser Company sent. If you want to keep the sidebar and command bar workflow somewhere else, Vivarc gives you most of it in Vivaldi, free and open source.

## Install

No developer experience needed. It takes about two minutes.

1. Open **Terminal** (press Cmd+Space, type `Terminal`, press Enter).
2. Paste this line and press Enter:

   ```sh
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KASOGIT/vivarc/main/install.sh)"
   ```

3. Follow what it says. It offers to close Vivaldi for you, and if macOS asks for a permission (**App Management**) it opens the right settings page and waits while you switch it on for Terminal.
4. Open Vivaldi.

Every profile gets the sidebar, and profiles you create later set themselves up the first time they open (the sidebar needs no restart, but Vivaldi reads keyboard shortcuts at launch, so the space and profile shortcuts work after the profile's next restart). Each profile starts with a few example favorites and pins so you can see how it works, and a new profile opens a short guide page.

Requires macOS and Vivaldi 8.x. If your Mac has never had developer tools, macOS shows an "Install" window the first time (it is Apple's free command line tools, which include Python); click Install, wait, then paste the line again.

**Updating, and after a Vivaldi update:** Vivaldi updates replace the app and remove Vivarc. Open **Update Vivarc**. It is an app in the `Applications` folder inside your home folder: in Finder press Cmd+Shift+H, then open `Applications` (not the one in the sidebar), and drag it to your Dock to keep it close. It quits Vivaldi, fetches the latest Vivarc, puts it back into Vivaldi and reopens it. It runs in Terminal, so Terminal needs the App Management permission (the same one as at install). The same thing from Terminal: `python3 ~/.vivarc/app/vivarc.py update`, or paste the install line again. If macOS asks for the App Management permission again, allow it the same way as at install. The installer also offers an optional reminder: when a Vivaldi update removes Vivarc, a small dialog asks whether to bring it back. Switch it on or off with `python3 ~/.vivarc/app/vivarc.py reminder on` (or `off`).

**Uninstall:** `python3 ~/.vivarc/app/vivarc.py uninstall` restores your settings. Your bookmarks are never deleted.

### Troubleshooting

- **"Operation not permitted" or "macOS blocked writing into Vivaldi.app":** switch on Terminal under System Settings > Privacy & Security > App Management, then paste the line again. **Do not use `sudo`**: it does not help and can leave files only root can change.
- **Already used `sudo`?** Run `sudo chown -R "$(whoami)" ~/.vivarc` once, then paste the install line again (without `sudo`).
- **"Vivaldi not found":** Vivarc looks in `/Applications/Vivaldi.app`. If yours is elsewhere, use the developer install below with `--app`.

### For developers

```sh
git clone https://github.com/KASOGIT/vivarc.git && cd vivarc
./vivarc.py install       # also: apply, status, uninstall, import-arc
```

## What you get

**One sidebar.** A favorites grid on top, your pinned folders below, a divider with *Clear*, then your open tabs. Drag and drop between all of them, nest folders, rename in place, right-click for everything. Removed items go to Vivaldi's bookmark trash. Like Arc, a pinned tab stays on its pin when you navigate inside it: the row shows a `/` and the title of the page you are on, and on hover you can jump back to the pinned page or separate the page you are on into its own tab.

<p align="center">
  <img src="docs/screenshots/sidebar.png" alt="Vivarc sidebar: favorites grid, pinned folders, open tabs" width="760">
</p>

**A command bar on Cmd+T.** It opens over the page you are on. Type to jump to an open tab, a bookmark or a history entry, paste a URL, or search.

<p align="center">
  <img src="docs/screenshots/command-bar.png" alt="Command bar in YouTube search mode" width="760">
</p>

- **Search shortcuts.** Type `yt` then Tab to search YouTube. 18 are built in (`g`, `gm` Gmail, `gd` Drive, `gc` Calendar, `gh`, `so`, `npm`, `mdn`, `li`, `x`, `w`, `r`, `m`, `az`, `tr`, `d`, `b`). The search engine keywords you already set in Vivaldi work too.
- **Quick actions.** Type `history`, `downloads`, `pin`, `theme`, `private`, `guide`... and run it: View History, View Downloads, Pin This Tab, Add to Favorites, Collapse / Expand All Folders, Copy Current URL, **Split View** (side by side or top and bottom, like Arc), Duplicate, Mute, New Private Window and more.

**A theme editor.** Hover the space name and click the palette: pick a colour, intensity and grain. Saved per profile, so each one gets its own look.

<p align="center">
  <img src="docs/screenshots/theme.png" alt="Theme editor with colour pad, swatches, intensity and grain" width="760">
</p>

**Shortcuts**

| Keys | Does |
|---|---|
| Cmd+T | Command bar |
| Cmd+S | Show or hide the sidebar |
| Cmd+Shift+C | Copy the page URL (with a toast) |
| Cmd+L | Edit the address |
| Cmd+E | Vivaldi's own Quick Commands |

**Also:** an optional link preview (Peek, by [PaRr0tBoY](https://github.com/PaRr0tBoY/Awesome-Vivaldi), downloaded from upstream and verified at install), and an importer for your Arc spaces and site icons.

## Coming from Arc or Chrome

**From Chrome (or Safari, Firefox, Edge):** use Vivaldi's own importer, **File > Import Bookmarks and Settings…**, and most Chrome extensions install from the Chrome Web Store. The guide page that opens in a new profile covers this too. Imported bookmarks stay in Vivaldi's bookmarks; pin a site into the sidebar with the `pin` or `favorites` quick action.

**From Arc:**

```sh
./vivarc.py import-arc     # reads Arc's data (read only), writes ~/.vivarc/import/arc-<space>.html and your site icons
```

In each Vivaldi profile: **File > Import Bookmarks and Settings… > HTML file**, pick the matching file. Quit Vivaldi and run `./vivarc.py apply` once to include the icons. Each Arc profile goes to a Vivaldi profile; its spaces become `Arc - <space>` folders, which a Vivaldi workspace with the same name picks up as that space's pinned links.

### Where Vivaldi differs from Arc

- **Spaces and profiles are two layers.** A **space** is a Vivaldi workspace: a group of tabs and pinned links inside one window. Once a profile has workspaces, a row of emoji tiles under the sidebar switches between them (click one, or **Cmd+Option+Left/Right** for the previous/next; **Ctrl+Cmd+N** makes one). Each space lists only its own tabs and has its own Pinned folder, named after the workspace; favorites are shared. Spaces **share the profile's logins**, which Vivaldi does not separate. A **profile** is the real boundary: its own window, bookmarks, logins and extensions. Switch with the **round avatars in the bottom bar** (click one, **Cmd+Ctrl+1..9** for the nth, **Cmd+Ctrl+Left/Right** for the previous/next); the **+** creates a profile and right-clicking your own avatar opens Vivaldi's profile manager. Vivaldi's own use of Cmd+Option+arrows for switching tabs is given up for the spaces, and Ctrl+Tab still cycles tabs.
- **Links do not pick a space.** Arc can send a link to a given space; Vivaldi opens links from other apps in whichever profile was used last. The workaround is [Finicky](https://github.com/johnste/finicky), a tiny app that becomes your default browser and routes each link to a profile by domain:
  1. `brew install --cask finicky`, then set Finicky as the default browser in System Settings.
  2. Copy [templates/finicky.js](templates/finicky.js) to `~/.finicky.js` and edit it: one `handlers` entry per space, with the domains you want in it and the profile name as shown in Vivaldi's profile menu.
- **Not built yet:** Boosts, automatic archiving of old tabs, and Arc's share links.

## Keeping it working

After a Vivaldi update, double-click **Update Vivarc** (see [Install](#install)); it also updates Vivarc itself. To check what is installed: `python3 ~/.vivarc/app/vivarc.py status`. To remove everything: `python3 ~/.vivarc/app/vivarc.py uninstall` restores your preferences and `window.html`. Your bookmarks, including the `Vivarc` folder, are left alone.

## Safety

Every file Vivarc edits is backed up in `~/.vivarc/backup/`, existing shortcuts are kept, and `uninstall` restores the original values. The styles ship inside the script, so a Vivaldi update can never leave you with half a UI. No Vivaldi flags are changed. See [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md) for exactly what changes and how it works.

The command bar sends what you type to DuckDuckGo's autocomplete for suggestions; set `"suggestions": "off"` in `~/.vivarc/config.json` to turn that off.

## Contributing

**Contributions are very welcome, and they make this project better.** Bug reports, ideas, testing on other setups, docs fixes and pull requests all help, and you do not need to be an expert. See [CONTRIBUTING.md](CONTRIBUTING.md) to get started, and open an issue if you want to talk something through first. The notes in [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md) cover the Vivaldi quirks worth knowing. If Vivarc saves you time, a star on the repo helps others find it.

## Credits and licence

MIT, see [LICENSE](LICENSE). Peek is [VividPeek by PaRr0tBoY and contributors](https://github.com/PaRr0tBoY/Awesome-Vivaldi) (GPL-3.0); it is not part of this repository.

Not affiliated with The Browser Company or Vivaldi Technologies. "Arc" and "Vivaldi" are their owners' trademarks; the names are used only to describe compatibility. A separate project, [VivalArc](https://github.com/tovifun/VivalArc), restyles Vivaldi's tabs with CSS and a theme; Vivarc adds the behaviour (command bar, favorites, importer, installer).
