# Changelog

## Unreleased
- Spaces: Vivaldi workspaces become Arc-style spaces. A row of emoji tiles under the sidebar switches between them; each space lists only its own tabs (Clear and Close Other Tabs stay inside it) and has its own Pinned folder, named after the workspace (an imported `Arc - Work` folder goes with a workspace called Work, and a new workspace gets an empty one). Favorites are shared by every space. A space only groups tabs: logins are shared, profiles remain the way to separate them.
- Cmd+Option+Left/Right now switches to the previous/next space (Vivaldi's own workspace commands). The profile switcher's previous/next moves to Cmd+Ctrl+Left/Right; Cmd+Ctrl+1..9 is unchanged.

## 0.1.11 - 2026-10-24
- Right-click a favorite or a pinned tab and pick Rename… to change its name. A favorite's name is edited in a field under its row (the tile only shows the icon); Enter saves, Escape cancels.
- Fix: some favorites (Gmail for example) showed a letter instead of their icon after restarting Vivaldi, until they were opened again. Large favicons are now shrunk to 64px before being cached, instead of not being cached at all.
- Profile switcher: the bottom bar shows your Vivaldi profiles as round avatars in place of the account button. Click one to open or focus that profile, or press Cmd+Ctrl+1..9. A **+** creates a new profile and right-clicking your own avatar opens Vivaldi's profile manager.
- Cmd+Option+Left/Right switches to the previous/next profile, like Arc's spaces (it replaces Vivaldi's own use of that combo for switching tabs; Ctrl+Tab still cycles tabs).
- Every profile now gets the Downloads button in the bottom bar (profiles without Vivaldi's VPN button never had it).

## 0.1.10 - 2026-10-24
- Fix: with a theme on, the hidden sidebar (Cmd+S) still could not be clicked when it slid back in on hover.

## 0.1.9 - 2026-10-24
- Fix: with the sidebar hidden (Cmd+S), nothing in it could be clicked when it slid back in on hover.

## 0.1.8 - 2026-10-24
- The favorites grid shrinks its tiles (down to 72px) before dropping a column, instead of jumping straight from 3 to 2 columns.
- The sidebar can no longer be resized below 220px.

## 0.1.7 - 2026-10-23
- Like Arc, a pinned tab stays on its pin when you navigate inside it, instead of turning into a separate open tab and leaving the pin looking closed. The row shows a `/` and the current page's title (the pin's name is in the tooltip); hover it for "Back to pinned page" and "Separate From Pinned Tab" (also in the right-click menu, and for favorites). The link is stored in the tab's session data, so it survives a restart.
- Behaviour change: only the tab bound to a pin is hidden from the open tabs list. A second tab on the same site now shows up as a regular tab.

## 0.1.6 - 2026-10-23
- Update Vivarc is now a real app (`~/Applications/Update Vivarc.app`) that you can drag to the Dock; it opens the update script in Terminal. The plain script moved to `~/.vivarc/` and the old one in `~/Applications` is removed on the next install.

## 0.1.5 - 2026-10-23
- Fix: the installer's questions ("Quit Vivaldi now?", the App Management "press Enter" step) never reached the terminal and always fell through to "nothing was changed". They now work.
- `update` (and so Update Vivarc and the reminder) closes Vivaldi by itself, and the Update Vivarc script reopens it afterwards, also when the update fails.

## 0.1.4 - 2026-10-23
- Optional update reminder: `install` asks once; when a Vivaldi update has removed Vivarc, a dialog offers to bring it back (opens Update Vivarc). Turn it on or off with `reminder on|off`; `uninstall` removes it.

## 0.1.3 - 2026-10-23
- `update` command: fetches the latest release (or pulls a git checkout) and re-applies it. The installer leaves a double-clickable "Update Vivarc" in your Applications folder that runs it after a Vivaldi update and reopens Vivaldi. `uninstall` removes it. If you are on 0.1.2, paste the install line once to get it.

## 0.1.2 - 2026-10-23
- One-line installer for everyone (also updates and repairs): downloads the latest release and runs it, no git needed.
- The installer checks that macOS allows editing Vivaldi before changing anything, opens the App Management settings page and waits, offers to quit Vivaldi, refuses to run as root, and detects files left owned by root after an earlier sudo run.
- `apply` works while Vivaldi is open; the bundle is written atomically.

## 0.1.1 - 2026-10-23
- Fix: the sidebar could stay empty after a restart when tab events cancelled the first bookmark load.
- Added a contributing guide, issue templates and a demo GIF in the README.
- Quick actions Split View: Side by Side, Split View: Top and Bottom and Close Split View, built on Vivaldi's tab tiling. A split tab shows a ◫ mark in the sidebar.

## 0.1.0 - 2026-10-23
- Sidebar: favorites grid, pinned folders, divider with Clear, open tabs in one scrollable panel.
- Drag and drop between favorites, pinned folders and open tabs; context menus; inline folder rename.
- Command bar on Cmd+T: tabs, bookmarks, history, URLs, search suggestions, `yt` + Tab engine mode.
- Cmd+Shift+C "Copied Current URL" toast.
- Theme editor: sidebar colour, shade and grain, saved per profile.
- Layout applied to every profile: address bar and back/forward/reload inside the sidebar toolbar, profile and Downloads buttons at the bottom, panel bar on the right with auto-hide, status bar in overlay mode, sidebar width 323.
- First run of a profile: starter favorites (Gmail, Calendar, Drive, YouTube, GitHub, Maps) and example pins (a link, a folder, a nested folder); the guide page replaces Vivaldi's welcome tab.
- Quick actions in the command bar, 18 built-in search shortcuts, Cmd+S sidebar toggle, Downloads button, guide page.
- Profiles created after install are set up automatically, live (no restart). The stylesheet is embedded in the injected script: no CSS-mods folder or Vivaldi flags.
- Installer with backups, per-profile snapshots, uninstall; Arc importer (spaces to bookmarks, site icons).
- Optional Peek link preview, downloaded from upstream at a pinned commit.
