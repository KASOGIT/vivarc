# Changelog

## Unreleased
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
