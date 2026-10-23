# How Vivarc works

Vivaldi's UI is a web page (`window.html`). Vivarc adds one script and one stylesheet to it.

| Piece | Where it lives | What it does |
|---|---|---|
| CSS | Embedded in `vivarc.js` and added to the UI as a `<style>` element (source: `src/css/vivarc.css`) | Styles. Every rule is scoped to `#browser.vm-on`, a class the JS adds. No CSS-mods folder or browser flag is needed, and it never conflicts with your own CSS mods. |
| JS | `<Vivaldi.app>/.../vivaldi/vivarc.js`, referenced from `window.html` by one marked block | The sidebar, command bar, toast and theme editor. Rebuilt from `src/js/` by `vivarc.py apply`. |
| Data | A bookmarks folder with `Favorites` and `Pinned` subfolders (created on first run) | Your favorites and pinned folders. Plain bookmarks: they sync, export and back up like any others. |
| Settings | `~/.vivarc/config.json` | See below. |
| State | `~/.vivarc/state.json`, `~/.vivarc/backup/` | What the installer changed and the original values, used by `uninstall`. |

## Why a Vivaldi update removes the JS

An update replaces `Vivaldi.app`, including `window.html`. Run `./vivarc.py update` after updating: it pulls (git checkout) or downloads the latest release when there is one, then re-runs `install`. The installer leaves `~/Applications/Update Vivarc.app`, which opens `~/.vivarc/Update Vivarc.command` in Terminal; that script runs `update` (it quits Vivaldi) and reopens Vivaldi. Both are generated locally (the app by `osacompile`, ad-hoc signed), so macOS does not quarantine them, the app can sit in the Dock, and `uninstall` removes them. The optional reminder (`vivarc.py reminder on`) is a LaunchAgent, `~/Library/LaunchAgents/com.vivarc.reminder.plist`, that runs `vivarc.py remind` at login, every hour and when Vivaldi's `Info.plist` changes. `remind` only reads: if `window.html` has lost the Vivarc block (or `vivarc.js` is missing) it shows one dialog, at most every 12 hours, and on yes opens the update script in Terminal. A background job cannot do the update itself: macOS only lets a terminal you have granted App Management edit `Vivaldi.app`.
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
- `autoConfigureProfiles`: let Vivarc set up profiles created after install (see below).
- `compactBottomBar`: shrink the bottom toolbar (profile button) to Arc's proportions.
- `suggestions`: `"ddg"` sends what you type in the command bar to DuckDuckGo's autocomplete endpoint; `"off"` sends nothing.
- `spaceFolderTitle`: name of the folder created on first run.

## What the installer changes

Per Vivaldi profile (`Preferences`): the tab bar goes left; `Cmd+T` is freed from "New Tab" and "Quick Commands" (the command bar listens for it itself);
`Cmd+Shift+C` copies the page URL; `Cmd+S` toggles the sidebar instead of saving the page; the `Spacer` and Workspaces items are removed from the tab bar toolbar and the VPN button becomes the Downloads button; the address bar and back/forward/reload move into the sidebar toolbar (the top bar is hidden); the panel icon bar moves to the right and auto-hides (Vivaldi's auto-hide switch is on so Cmd+S can hide the sidebar, which starts visible); the bottom status bar only overlays on hover; the sidebar width starts at 323 unless you set one.
Existing shortcuts are kept. Nothing else in Vivaldi's settings, flags or `Local State` is touched. `uninstall` restores the original values.

## Profiles created later

`install` configures the profiles that exist. For a profile created afterwards, the JS (through `vivaldi.prefs`) applies the same
settings the first time it opens; they take effect immediately, no restart. It also opens the guide page in place of Vivaldi's welcome tab.
`uninstall` finds profiles that carry Vivarc's settings but have no snapshot and resets those keys to Vivaldi's defaults.
Set `"autoConfigureProfiles": false` to skip this and configure profiles only with `install`.

## Files in `~/.vivarc/`

`start/` (guide page), `peek/` (downloaded Peek), `icons.js` (Arc site icons), `import/`, `backup/`, `config.json`, `state.json`.
`apply` refreshes `start/` and rebuilds the bundle (stylesheet included).

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
- Enum prefs set through `vivaldi.prefs.set` only take effect live when set by name (`"left"`, `"right"`, `"overlay"`). A number is stored but the UI ignores it until restart. The installer writes numbers because it edits the file while Vivaldi is closed.
- `auto_hide.enabled` is a master switch: when it is on, every bar defaults to hidden unless its own `auto_hide.*` key is explicitly `false`.
- A new profile's welcome tab is `chrome-extension://mpognobbkildjkofajifpdfhcoklimli/components/welcome/welcome.html`, and it can open after the mod has run. "Welcome to Vivaldi" is the start page's title, not the welcome tab's.
- Vivaldi does not write a pref that equals its default, so a key missing from `Preferences` does not mean the set failed.
- Profile switching uses Vivaldi's own UI API, which mods can call: `vivaldi.runtimePrivate.getUserProfiles(cb)` (entries have `name`, `path`, `active`, `guest`, `image`, `customAvatar`), `onProfilesUpdated`, `openNamedProfile(path, cb)` (takes the profile **path**, not the name) and `createProfile(name, imageIndex, createShortcut, cb)`. The chips live in Vivaldi's bottom toolbar (`.toolbar-tabbar-after`), a wrapping flex row that grows to fill the sidebar; its flexible spacers have a minimum width of about the whole sidebar, so the layout rule in `vivarc.css` turns wrapping off and removes that minimum for any toolbar that contains the chips (`:has(> .vm-spaces)`, no class on `#browser`, because Vivaldi rewrites that element's classes). The account button is removed from `vivaldi.toolbars.tabbar_after` while there are two or more profiles, and the Downloads button is added to every profile.
- A tab belongs to a pin or favorite through two keys Vivarc adds to the tab's `vivExtData` (merged with Vivaldi's own keys, which share the field): `vivarcPin` is the bookmark id and `vivarcHome` is where the pin landed after the site's redirects, so a site that redirects off its root is not shown as away. Vivaldi saves them with the session, so the link survives a restart. Tabs that match a pin by URL when first seen are bound automatically; a key whose bookmark is gone is cleared. The logic is `src/js/08-pins.js`, covered by `tests/test_pins.py` (needs node).
- Split view is Vivaldi's tab tiling, stored in each tab's `vivExtData` JSON as `tiling: {id, layout, type, index}`. A mod can write it with `chrome.tabs.update(id, {vivExtData})`. Measured on the rendered panes: `row` is side by side, `column` is one above the other. Write all tiles at once, and start a fresh `id` for each split: Vivaldi restores tile groups with the session, and reusing an old group keeps its old layout.
