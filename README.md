# Vivarc

**An Arc-style sidebar, command bar and theme editor for Vivaldi.**
Favorites grid, pinned folders and open tabs in one panel. Cmd+T command bar with quick actions and search shortcuts. Drag and drop. Per-profile colour themes. One command to install, one to remove.

> Not affiliated with The Browser Company or Vivaldi Technologies. "Arc" and "Vivaldi" are their owners' trademarks; the name is used only to describe compatibility.

<!-- screenshots: docs/screenshots/sidebar.png, command-bar.png, theme.png -->

## Features

- **One scrollable sidebar**: a favorites grid on top, your pinned folders below, a divider with *Clear*, then your open tabs (newest first).
- **Drag and drop** between favorites, pinned folders and open tabs. Drag a pin onto the divider to unpin it.
- **Command bar (Cmd+T)** over the page you are on: switch to open tabs, search bookmarks and history, open URLs, search suggestions.
- **Quick actions** in the command bar: type `history`, `downloads`, `pin`, `theme`, `guide`... and run it (View History/Downloads/Bookmarks, Pin This Tab, Copy Current URL, New Private Window and more).
- **Search shortcuts**: type `yt`, `gm` (Gmail), `gh`, `so`, `npm`, `li`... then Tab to search that site. 18 built in; your own Vivaldi search-engine keywords are added and win on a clash.
- **Cmd+S** shows or hides the sidebar; the Downloads button replaces the VPN button; the Workspaces button is hidden.
- **Guide page**: a new profile opens a short Vivarc tour instead of Vivaldi's welcome tab. Reopen it with `guide` in the command bar.
- **Right-click everything**: pin, add to favorites, rename and nest folders, copy links, close others. Removed items go to Vivaldi's bookmark trash.
- **Theme editor**: tint the sidebar with a colour, shade and grain. Saved per profile.
- **Cmd+Shift+C** copies the page URL and shows a *Copied Current URL* toast.
- **Peek** (optional): Alt+click a link for a floating preview, by [PaRr0tBoY](https://github.com/PaRr0tBoY/Awesome-Vivaldi). Downloaded from upstream and verified at install time.
- **Arc import**: converts your Arc spaces and site icons so your pins come with you.

## Requirements

macOS, Vivaldi 8.x, Python 3 (preinstalled with the Xcode command line tools). Windows and Linux are not supported yet.

## Install

```sh
git clone https://github.com/KASOGIT/vivarc.git && cd vivarc
# quit Vivaldi (Cmd+Q) first
./vivarc.py install
```

Then open Vivaldi. Profiles you create later are set up automatically the first time they open (restart Vivaldi once when it says so). The first time, Vivarc creates a `Vivarc` bookmarks folder with `Favorites` and `Pinned` in each profile; pin things with right-click, or drag tabs onto the sidebar.

macOS may ask you to allow your terminal under **System Settings > Privacy & Security > App Management**, because the script edits `Vivaldi.app`.

### Bring your Arc pins

```sh
./vivarc.py import-arc        # reads Arc's data (read only), writes ~/.vivarc/import/arc-<space>.html and your site icons
```

In each Vivaldi profile: **Cmd+Shift+B > Import Bookmarks and Settings > HTML file**, pick the matching file. Quit Vivaldi and run `./vivarc.py apply` once to include the icons.
Arc spaces map to Vivaldi profiles (each its own window; switch with Cmd+`).

### After a Vivaldi update

An update replaces `Vivaldi.app` and removes the script. Quit Vivaldi, then (this also refreshes the stylesheet and guide page):

```sh
./vivarc.py apply
./vivarc.py status     # shows what is installed
```

### Uninstall

```sh
./vivarc.py uninstall  # restores your preferences, flags and window.html; your bookmarks are left alone
```

## Safety

Every file Vivarc edits is backed up in `~/.vivarc/backup/`, existing shortcuts and flags are kept, and `uninstall` restores the original values. The CSS only applies when the script is running, so a Vivaldi update can never leave you with half a UI. See [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md) for exactly what changes.

The command bar sends what you type to DuckDuckGo's autocomplete for suggestions; set `"suggestions": "off"` in `~/.vivarc/config.json` to turn that off.

## Credits and licence

MIT, see [LICENSE](LICENSE). Peek is [VividPeek by PaRr0tBoY and contributors](https://github.com/PaRr0tBoY/Awesome-Vivaldi) (GPL-3.0); it is not part of this repository.

## Support

If Vivarc saves you time, you can [sponsor the project](https://github.com/sponsors/KASOGIT). Issues and pull requests are welcome.
