# Changelog

## 0.1.32 - 2026-11-12
- Fix: **pinned links and new tabs open in the space on screen.** After switching spaces with the space tiles, Vivaldi kept opening them in the space you came from. Vivarc now tells Vivaldi about every switch, including the ones made through a favorite or the tab switcher.
- A space tile shows the icon picked in Vivaldi's workspace editor when the space has no emoji, instead of the first letter of its name. The README mentions **Move to Space** (right-click a tab) for moving a tab to another space. Thanks u/blondedco on Reddit for the report (#169).

## 0.1.31 - 2026-11-11
- Fix: with the **URL bar** setting on, the address bar no longer spills past a narrow sidebar when you click into it, and the buttons on its right (feed, translate, install, bookmark) are hidden to leave the room to the address, which now runs to the end of the field instead of fading out before it. A site asking for the camera or microphone still shows its button there (#155, #156).

## 0.1.30 - 2026-11-11
- Fix: **Copy Link** in the sidebar menu (pinned tabs, favorites, tabs) and **Copy Current URL** in the command bar copy the link again. They silently did nothing while the page had focus (#153).

## 0.1.29 - 2026-11-11
- **Peek, the link preview, behaves like Arc's and can be turned off.** A plain click on Google results now opens the page normally; a plain click opens a preview only for a link to another site from a pinned tab, as in Arc. **Vivarc Settings** has a **Link preview (Peek)** switch (off, every link opens in its tab, at once, even on pages already open), plus **Preview links from pinned tabs**, the **Preview shortcut** (Option+click, Shift+click or none; Cmd+click always opens a new tab) and **Dim the page behind**. The tabs Peek opens behind a preview no longer show up in the sidebar, a space, the tab switcher or tab search, and the preview keeps Arc's controls only: close, open in a tab, split view, copy link. The first preview says what it is and where to turn it off. Thanks u/yapesochek on Reddit for the report (#150).

## 0.1.28 - 2026-11-10
- Fix: the update reminder works when you installed from a checkout in Documents, Desktop or Downloads. macOS hides those folders from background jobs, so the reminder never ran and no popup appeared after a Vivaldi update. It now runs the copy in `~/.vivarc/app`. Run `./vivarc.py reminder on` once to switch an existing reminder over.

## 0.1.27 - 2026-11-09
- Fix: dragging a favorite to a new place in the grid is reliable. A drop in the gap between tiles lands next to the closest tile instead of at the end of the grid, the drop marker shows on the glass theme, and tiles no longer grow under the pointer while you drag.
- Fix: a hovered favorite in the top row is no longer cut off at the top of the sidebar on the glass theme.
- The palette icon that opens the theme editor, next to the space name, is always shown and a little brighter, instead of appearing only on hover.

## 0.1.26 - 2026-11-09
- **A quiet Update Vivarc button replaces the update dialog.** When a new release is out, a small button appears above the space bar in the sidebar, like Vivaldi's own update button. Click it to update, as the dialog's Update button did; right-click it for **Copy Update Command**, **What's New** or **Later**. macOS shows a Notification Center banner instead of the blocking dialog (Windows no longer asks). Vivarc checks GitHub at most every 12 hours; **Check for updates** in Vivarc Settings turns it off. Thanks @groenroos (#100).
- A tab's right-click menu in the sidebar has more of Vivaldi's: **Reload Tab**, **Split View** (side by side or top and bottom, **Close Split View** when the tab is in one), **Move to New Window**, **Move to Window** (one entry per other window) and **Move to Space** (one per other space, without switching to it). Thanks @groenroos (#128).
- Fix: the space bar stays at the bottom of the sidebar, above the bottom bar, however few tabs the space has; before, it sat right under the last tab. Thanks @groenroos (#101).
- Fix: updating Vivarc no longer resets the Auto-Hide choices you made in Vivaldi (for example Tab Bar, which Cmd+S toggles). The first install still starts with the sidebar visible. Thanks @groenroos (#99).

## 0.1.25 - 2026-11-08
- **A favorite has one tab for every space, like Arc.** Clicking a favorite whose tab is in another space brings that tab to the space you are in instead of opening a second one, and clicking it back in the first space moves it back. A favorite in a split view stays where it is. Pinned links still belong to their space. Thanks @gulin-desigenr (#120).
- Closing the active tab keeps you in its space, on the space's most recent tab, instead of jumping to another space. Closing the last page of a space leaves you in it with the command bar open. Vivaldi still switches space for a moment first, so you may see a brief flash. Thanks @gulin-desigenr (#118, #75).
- Fix: closing the command bar in an empty space by clicking outside it no longer closes the space's only tab (which sent you to another space), and the click still reaches the space, tab or favorite you clicked. Thanks @gulin-desigenr (#119).
- Fix: a click on the page now closes the sidebar's right-click menus and the theme editor; before, only Escape did. Thanks @gulin-desigenr (#116).
- Fix: removing a pin or favorite now removes its link from the tab, so the tab can be archived and bound to a new pin again, and **Close Split View** works. Vivaldi keeps a key that is only left out of a tab's data; Vivarc now writes `null`, which removes it. Thanks @gulin-desigenr (#115).
- Fix: a space folder in Vivaldi's bookmark trash is no longer a space, so a deleted space, or a new one with the same name, does not bring back the old pins. Thanks @gulin-desigenr (#117).
- Fix: a suggestion that is a full web address (`https://...`) opens that page instead of searching for it. Thanks @groenroos (#111, reported in #108).

## 0.1.24 - 2026-11-08
- Sidebar: *Clear* next to the divider is always visible, dimmed, instead of only on hover, like Arc. A new Cmd+T quick action **Clear All Tabs** does the same from the keyboard (type `clear` or `close`): it closes the open tabs below the divider, exactly like the button, and leaves favorites, pinned tabs and other spaces alone.
- Docs: profiles on the same Vivaldi account share bookmarks, and so Vivarc's favorites and pinned folders. The README, the guide page and the technical notes now say to sign each profile into its own Vivaldi account to keep profiles apart and still sync each one.

## 0.1.23 - 2026-11-07
- Clicking a pinned folder twice quickly only opens and closes it. Before, the double-click reached Vivaldi's tab bar, which opened a new tab and the command bar. Thanks @gulin-desigenr (#83), after the guard @saurL first wrote in #58.
- A click on a space tile or a sidebar row no longer gets lost while pages load: the sidebar redraws only for its own window's tabs, and waits while a mouse button is held. Thanks @gulin-desigenr (#84).
- Fix: a tab could vanish from the sidebar when Favorites held a folder with a link to the same site. Links inside such folders are not drawn, but they claimed the tab; now only the favorites and pinned links the sidebar shows do. Thanks @gulin-desigenr (#88).
- Switching spaces has a short transition: the sidebar fades and slides in over 220 ms and the page fades in. The switch itself is not delayed, and Reduce Motion turns the transition off. Thanks @gulin-desigenr (#85).
- Fix: switching to an empty space works again, and opens the command bar there for an address. Before, the command bar opened over the old space; on Vivaldi 8.3 the space did not change at all, because Vivaldi ignores a workspace written into a new tab. Thanks @gulin-desigenr (#89), with the native workspace switch @saurL first tried in #58.
- **Mute a single tab, like Arc.** A tab that is playing sound shows a speaker in the sidebar, on its row, its pinned row or its favorite tile; click it to mute the tab, and click the crossed-out speaker to unmute it. Right-click a tab, or a pin or favorite with an open tab, for *Mute Tab* / *Unmute Tab*. Thanks @KevinJulien34 (#95).
- **URL bar at the top of the sidebar, like Arc**: a new switch in Vivarc Settings (off by default). On, the address bar is always shown under the back, reload and forward buttons; off, it stays hidden until you press Cmd+L (Ctrl+L on Windows), as before. Thanks @KevinJulien34 (#96).

## 0.1.22 - 2026-11-06
- **Archive inactive tabs, like Arc** (off by default; turn it on in Vivarc Settings). A tab you have not opened for the chosen time, 12 hours by default and from 1 hour to 7 days, is closed. Tabs bound to a pinned link or favorite, Vivaldi-pinned tabs, split views, tabs playing sound and the tab you are on are never closed. Bring one back with Reopen Closed Tab. It only runs while a Vivaldi window is open, and each window looks after its own tabs.

## 0.1.21 - 2026-11-05
- **Ctrl+Tab switcher, like Arc's.** Hold Ctrl and press Tab to open a row of your five latest tabs with thumbnails; Tab or Shift+Tab (or the arrow keys) move through it, and holding Tab keeps moving faster and faster. Let go of Ctrl to switch. A quick Ctrl+Tab goes straight to the previous tab. A tab you open or focus takes the first place and the oldest drops out. Ctrl+Tab and Ctrl+Shift+Tab are taken from Vivaldi's own tab cycling; Vivaldi reads shortcuts at launch, so a profile needs one restart after it is updated.

## 0.1.20 - 2026-11-05
- The Cmd+T command bar is more compact, closer to Arc's: smaller text, rows and icons. Its top edge no longer moves as results come and go; it sits where a full list would be centred in the window, and only the bottom grows or shrinks.

## 0.1.19 - 2026-11-05
- Fix: the Cmd+T command bar always searched DuckDuckGo, whatever search engine you picked in Vivaldi's settings. Searches and suggestions now use your default engine (the private one in a private window), and change as soon as you pick another. An engine without a suggestions service gets no suggestions instead of DuckDuckGo's. Thanks @groenroos (#65).
- Pinned folders slide open and shut instead of appearing at once. With Reduce Motion on, they still open instantly. Thanks @dknz7 (#59).

## 0.1.18 - 2026-11-05
- **Windows support.** Install with `irm https://raw.githubusercontent.com/KASOGIT/vivarc/main/install.ps1 | iex` (needs Python 3). Ctrl stands in for Cmd: Ctrl+T command bar, Ctrl+S sidebar, Ctrl+Shift+C copy URL, Ctrl+Alt+Left/Right spaces, Ctrl+Alt+N new space, Ctrl+Alt+Shift+Left/Right and 1..9 profiles. **Update Vivarc** and **Uninstall Vivarc** are in the Start Menu, and a scheduled task re-applies Vivarc by itself after each Vivaldi update. macOS is unchanged.
- Site icons show up straight away for pins, favorites and tabs restored after a restart: when no open tab has provided one yet, Vivarc takes it from Vivaldi's own favicon database (filled by browsing and Sync). Before, these showed a letter until the site had been opened once.
- Files Vivarc writes now always use Unix line endings, and the repository has a `.gitattributes`, so a checkout made on Windows keeps `install.sh` working.
- Tests run on macOS and Windows in GitHub Actions.
- Windows: a Vivaldi in a custom place keeps working after an update, because the Update and Uninstall launchers pass along the `--app` and `--data-dir` it was installed with. `--app` also accepts `vivaldi.exe`, and a portable copy without version folders is found. Thanks @saurL (#58), whose Windows work inspired these.

## 0.1.17 - 2026-11-05
- Fix: after updating to Vivaldi 8.3, the profile chips floated at the top right of the empty space under the tabs. They are back at the bottom-left of the sidebar with the Downloads button at the bottom-right.

## 0.1.16 - 2026-10-28
- **Uninstall Vivarc**: the installer now also leaves `~/Applications/Uninstall Vivarc.app` next to Update Vivarc. It quits Vivaldi, restores your settings, removes Vivarc and reopens Vivaldi, so removing or reinstalling no longer needs Terminal.
- Docs: the README and the guide page now say that a sidebar hidden with Cmd+S slides back in when you move the pointer to the left edge of the window.

## 0.1.15 - 2026-10-27
- Right-click a space tile and pick **Delete Space…** to remove it; a second step asks first and says how many tabs will close. The space's Pinned folder stays in your bookmarks and comes back if you create a space with the same name. The default space cannot be deleted.

## 0.1.14 - 2026-10-27
- The update reminder also tells you when a new Vivarc release is out: one dialog per release, and on yes it runs Update Vivarc. It needs the reminder to be on (`reminder on`).

## 0.1.13 - 2026-10-27
- Fix: sites could not ask for the camera or microphone (Google Meet's "Allow" did nothing). Vivaldi shows these requests under the address bar, which Vivarc keeps collapsed, so they were invisible. The address bar now floats over the sidebar, as with Cmd+L, while such a popup is open, and is no longer cut off by the page when a theme is on.
- **Liquid glass** (off by default; turn it on in Vivarc Settings): a translucent, blurred sidebar, menus, command bar and dialogs, following Apple's Liquid Glass guidance (glass only for navigation and controls, never stacked, legible text) and falling back to solid surfaces when macOS has Reduce Transparency or Increase Contrast on. A **Glass opacity** slider in the settings goes from clear to frosted.
- **Vivarc Settings**: Cmd+T, type `settings`, or right-click the sidebar and pick Vivarc Settings… to switch features on and off live: the space bar, the compact bottom bar and search suggestions. Saved per profile and applied in all of the profile's windows; `~/.vivarc/config.json` still sets the starting values.
- Cmd+T quick actions **Collapse All Folders** and **Expand All Folders** fold or unfold every pinned folder in the sidebar at once (type `collapse`, `expand` or `folders`).

## 0.1.12 - 2026-10-26
- Spaces: Vivaldi workspaces become Arc-style spaces. A row of emoji tiles under the sidebar switches between them; each space lists only its own tabs (Clear and Close Other Tabs stay inside it) and has its own Pinned folder, named after the workspace (an imported `Arc - Work` folder goes with a workspace called Work, and a new workspace gets an empty one). Favorites are shared by every space, and a tab you open (command bar, link, sidebar) stays in the active space. A space only groups tabs: logins are shared, profiles remain the way to separate them.
- Cmd+Option+Left/Right now switches to the previous/next space (Vivaldi's own workspace commands). The profile switcher's previous/next moves to Cmd+Ctrl+Left/Right; Cmd+Ctrl+1..9 is unchanged.
- **Ctrl+Cmd+N** opens Vivaldi's Create Workspace dialog (name, icon or emoji). The **+** tile under the sidebar and **Create New Space** in the Cmd+T bar remind you of it: a mod cannot press a shortcut for you.

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
