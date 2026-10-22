# How Vivarc works

Vivaldi's UI is a web page (`window.html`). Vivarc adds one script and one stylesheet to it.

| Piece | Where it lives | What it does |
|---|---|---|
| CSS | `~/.vivarc/css/vivarc.css`, loaded by Vivaldi's own "CSS modifications" setting | Styles. Every rule is scoped to `#browser.vm-on`, a class the JS adds, so the CSS does nothing if the JS is missing. |
| JS | `<Vivaldi.app>/.../vivaldi/vivarc.js`, referenced from `window.html` by one marked block | The sidebar, command bar, toast and theme editor. Rebuilt from `src/js/` by `vivarc.py apply`. |
| Data | A bookmarks folder with `Favorites` and `Pinned` subfolders (created on first run) | Your favorites and pinned folders. Plain bookmarks: they sync, export and back up like any others. |
| Settings | `~/.vivarc/config.json` | See below. |
| State | `~/.vivarc/state.json`, `~/.vivarc/backup/` | What the installer changed and the original values, used by `uninstall`. |

## Why a Vivaldi update removes the JS

An update replaces `Vivaldi.app`, including `window.html`. Run `./vivarc.py apply` after updating (with Vivaldi closed).
`./vivarc.py status` tells you whether the JS is in place. Until you re-apply, Vivaldi simply looks like normal Vivaldi.

## Configuration

`~/.vivarc/config.json`, then run `./vivarc.py apply`:

```json
{
  "hideWorkspaceButton": true,
  "autoConfigureProfiles": true,
  "compactBottomBar": true,
  "suggestions": "ddg",
  "spaceFolderTitle": "Vivarc"
}
```

- `hideWorkspaceButton`: hide Vivaldi's Workspaces button at the top of the sidebar (on by default).
- `autoConfigureProfiles`: let Vivarc set up profiles created after install (see below). Set to `false` to configure profiles only with `install`.
- `compactBottomBar`: shrink the bottom toolbar (profile button) to Arc's proportions.
- `suggestions`: `"ddg"` sends what you type in the command bar to DuckDuckGo's autocomplete endpoint; `"off"` sends nothing.
- `spaceFolderTitle`: name of the folder created on first run.

## What the installer changes

Per Vivaldi profile (`Preferences`): the tab bar goes left; the "CSS modifications" folder points at `~/.vivarc/css`;
`Cmd+T` is freed from "New Tab" and "Quick Commands" (the command bar listens for it itself); `Cmd+Shift+C` copies the page URL;
`Cmd+S` toggles the sidebar instead of saving the page; the `Spacer` and Workspaces items are removed from the tab bar toolbar and the VPN button becomes the Downloads button. In `Local State`: two flags are enabled (`vivaldi-css-mods`,
`vivaldi-horizontal-pinned-tabs`). Existing shortcuts and flags are kept. `uninstall` restores the original values.

## Profiles created later

`install` configures the profiles that exist. For a profile created afterwards, the JS (through `vivaldi.prefs`) applies the same
settings the first time it opens, then asks for one restart because Vivaldi reads the CSS folder at start-up. It opens the guide page in
place of Vivaldi's welcome tab. A profile that already uses a different CSS mods folder is never touched. `uninstall` resets these
profiles to Vivaldi's defaults, since they have no snapshot.

## Files in `~/.vivarc/`

`css/` (stylesheet, Peek's), `start/` (guide page), `peek/` (downloaded Peek), `icons.js` (Arc site icons), `import/`, `backup/`, `config.json`, `state.json`.
`apply` refreshes `css/`, `start/` and the bundle.

## Limits

- Vivaldi profiles are the equivalent of Arc spaces; each is its own window (switch with Cmd+`).
- Vivaldi's own UI code cannot be called from a mod, so Cmd+T opens Vivarc's command bar, not Vivaldi's Quick Commands (Cmd+E and F2 still do).
- macOS only for now.

## Notes for contributors

Things that cost time to find out:

- Vivaldi toolbar buttons are found with `[data-name="<PanelId>"]` (for example `PanelDownloads`), not a `name` attribute.
- They ignore a bare `.click()`. Send `pointerdown`, `mousedown`, `pointerup`, `mouseup`, `click` in that order.
- Changing the layout inside a `dragstart` handler makes Chromium cancel the drag. Defer it with `requestAnimationFrame`.
- Re-rendering the sidebar while a drag is running detaches the dragged node. Renders are held back until `dragend`.
- A mod cannot call Vivaldi's own commands or reach its webpack modules; only `chrome.*`, `vivaldi.prefs`, `vivaldi.searchEngines` and `vivaldi.tabsPrivate` are available.
