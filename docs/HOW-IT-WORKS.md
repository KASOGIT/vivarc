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

An update replaces `Vivaldi.app`, including `window.html`. Run `./vivarc.py update` after updating: it pulls (git checkout) or downloads the latest release when there is one, then re-runs `install`. The installer leaves `~/Applications/Update Vivarc.app`, which opens `~/.vivarc/Update Vivarc.command` in Terminal; that script runs `update` (it quits Vivaldi) and reopens Vivaldi. Both are generated locally (the app by `osacompile`, ad-hoc signed), so macOS does not quarantine them, the app can sit in the Dock, and `uninstall` removes them. The optional reminder (`vivarc.py reminder on`) is a LaunchAgent, `~/Library/LaunchAgents/com.vivarc.reminder.plist`, that runs `vivarc.py remind` at login, every hour and when Vivaldi's `Info.plist` changes. `remind` only reads: if `window.html` has lost the Vivarc block (or `vivarc.js` is missing) it shows one dialog, at most every 12 hours, and on yes opens the update script in Terminal. When Vivarc is in place it also asks GitHub for the latest release tag (a redirect, nothing is downloaded) and, if that is newer than the installed version, shows one dialog per release (remembered in `~/.vivarc/offered`) with the same yes path. A background job cannot do the update itself: macOS only lets a terminal you have granted App Management edit `Vivaldi.app`.
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

`compactBottomBar` and `suggestions` are only the starting values: **Vivarc Settings** (Cmd+T, `settings`) overrides them per profile, live. `01-settings.js` holds the schema (one entry per switch, with the marker class it toggles on `#browser`) and the precedence (saved, then config, then default); `45-settings.js` is the overlay. The `glass` switch only adds the class `vm-glass`, and the `glassOpacity` slider (a `range` entry in the schema, 15 to 95, clamped when read) sets `--vm-glass-opacity` on `#browser`, which every glass fill mixes with; the rules at the end of `vivarc.css` do the rest (the regular variant of Apple's material: blurred, saturated backdrop, translucent fill, specular rim; floating surfaces and the sidebar only, never rows inside them). Vivarc's surfaces sit in Vivaldi's UI layer, where `backdrop-filter` also blurs the page behind floating ones; the sidebar blurs the window background, so it shows real glass over a theme with a background image. `prefers-reduced-transparency` and `prefers-contrast` are supported by Vivaldi's Chromium and switch the surfaces back to solid. Windows of a profile stay in step through a `BroadcastChannel`. Only switches that apply live belong there: anything that writes Vivaldi's Preferences (shortcuts, toolbars) is read at launch, so it stays out.

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
- Profile switching uses Vivaldi's own UI API, which mods can call: `vivaldi.runtimePrivate.getUserProfiles(cb)` (entries have `name`, `path`, `active`, `guest`, `image`, `customAvatar`), `onProfilesUpdated`, `openNamedProfile(path, cb)` (takes the profile **path**, not the name) and `createProfile(name, imageIndex, createShortcut, cb)`. The chips live in Vivaldi's bottom toolbar (`.toolbar-tabbar-after`), a wrapping flex row that grows to fill the sidebar; its flexible spacers have a minimum width of about the whole sidebar, so the layout rule in `vivarc.css` turns wrapping off and removes that minimum for any toolbar that contains the chips (`:has(> .vm-spaces)`, no class on `#browser`, because Vivaldi rewrites that element's classes). Cmd+Ctrl+Left/Right (previous/next profile, wrapping, by name) and Cmd+Ctrl+1..9 are handled by `06-spaces.js`; `patch_preferences` and the runtime setup in `05-bootstrap.js` free those keys from any Vivaldi command. The account button is removed from `vivaldi.toolbars.tabbar_after` while there are two or more profiles, and the Downloads button is added to every profile.
- A tab belongs to a pin or favorite through two keys Vivarc adds to the tab's `vivExtData` (merged with Vivaldi's own keys, which share the field): `vivarcPin` is the bookmark id and `vivarcHome` is where the pin landed after the site's redirects, so a site that redirects off its root is not shown as away. Vivaldi saves them with the session, so the link survives a restart. Tabs that match a pin by URL when first seen are bound automatically; a key whose bookmark is gone is cleared. The logic is `src/js/08-pins.js`, covered by `tests/test_pins.py` (needs node).
- Split view is Vivaldi's tab tiling, stored in each tab's `vivExtData` JSON as `tiling: {id, layout, type, index}`. A mod can write it with `chrome.tabs.update(id, {vivExtData})`. Measured on the rendered panes: `row` is side by side, `column` is one above the other. Write all tiles at once, and start a fresh `id` for each split: Vivaldi restores tile groups with the session, and reusing an old group keeps its old layout.

## Spaces (Vivaldi workspaces)

- A workspace is `{id, name, emoji, icon}` in the pref `vivaldi.workspaces.list`. Vivaldi reads it once at start-up and writes it back from its own store, so Vivarc only reads it (every 3 s and on tab events) and never writes it; creating one is Vivaldi's own command, bound to `ctrl+meta+n` at install. Events a mod dispatches with `tabsPrivate.onKeyboardShortcut.dispatch` reach other mod listeners but never Vivaldi's shortcut handler (tested with a command that works by hand), so the **+** tile and the *Create New Space* action only show the shortcut. A tab opened while a space is active is stamped with that space (`workspaces.stamp`), because Vivaldi only does it for tabs its own UI opens.
- A tab's workspace is `workspaceId` in its `vivExtData` JSON (no key means the default space, id 0). `07-workspaces.js` holds the pure logic (tested): which space a tab is in, the list for the space bar, the most recently used tab to switch to, and which Pinned folder belongs to which space. The sidebar lists only the active space's tabs, so Clear and Close Other Tabs cannot touch another space.
- Switching activates the space's most recent tab (`lastAccessed`); Vivaldi switches the workspace itself. An empty space gets a new tab created with `vivExtData: {workspaceId}`. Vivarc never writes `workspaceId` into an existing tab.
- Cmd+Option+Left/Right are bound by `patch_preferences` and `05-bootstrap.js` to Vivaldi's `COMMAND_WORKSPACE_SWITCH_BACK_ORDER`/`_FORWARD_ORDER`, which skip workspaces open in another window and include the default space.
- Pinned folders: bookmark folders that contain a `Pinned` folder are spaces. A workspace takes the folder with its name (case-insensitive, an `Arc - ` prefix ignored); the default space is the first folder no workspace claims. A workspace with no folder gets an empty one when first shown. Favorites always come from the default space's folder. `plan()` in `08-pins.js` receives the pin ids of every space so a tab bound to a pin of another space is never cleared.
- Learned the hard way: Vivaldi normalises a shortcut to the order `ctrl+alt+shift+meta+key` and reads shortcut bindings at launch, so a binding the bootstrap writes live works from the next launch (an install that patches Preferences while Vivaldi is closed works at once). `window.vivaldiWindowId` is not Chrome's window id (`chrome.windows`, `tab.windowId`); every window runs its own copy of the mod, so per-window work (stamping new tabs) compares `tab.windowId` with `chrome.windows.getCurrent().id`.
- Deleting a space (right-click its tile) calls Vivaldi's own `removeWorkspace`, which also closes the space's tabs. A mod has no API for it, and the webpack chunk array (`webpackChunkgapp_browser_react`) is not on the window the mod runs in: it is on the background page, `chrome.extension.getBackgroundPage()`. `findRemover` pushes a runtime callback onto that array to get webpack's module list, finds the module whose source mentions `removeWorkspace(` and takes the manager from its exports. If a Vivaldi update changes that, the sidebar shows a toast and deletes nothing. Learned by running a second Vivaldi with `--user-data-dir` and `--remote-debugging-port` and calling it from the Chrome DevTools Protocol.
- Workspaces share cookies, IndexedDB and service workers with the rest of the profile. Only a Vivaldi profile isolates logins.
