---
name: demo
description: Record or remake the Vivarc demo GIF / video (docs/demo.gif) in a throwaway Vivaldi profile, change its storyboard, or re-encode it. Use when asked to make, redo or tweak the demo, the README GIF, or a promo video of Vivarc.
---

# Recording the Vivarc demo

Everything lives in `tools/demo/`. It runs a second Vivaldi with its own `--user-data-dir` (`~/.cache/vivarc-demo/profile`,
DevTools on port 9335), so the user's profiles are never touched. macOS only.

```sh
./vivarc.py apply              # the demo films whatever Vivarc is applied to /Applications/Vivaldi.app
tools/demo/demo.sh setup       # once: fresh profile, Vivarc shortcuts, English UI, spaces/pins/tabs, consent walls dismissed
tools/demo/demo.sh rehearse    # play the storyboard without filming
tools/demo/demo.sh record 52   # film N seconds (the take is ~50 s)
DEMO_LENGTH=50 tools/demo/demo.sh encode   # -> ~/.cache/vivarc-demo/demo.gif (1280 px, 15 fps) + demo.mp4 (2560 px)
cp ~/.cache/vivarc-demo/demo.gif docs/demo.gif
tools/demo/demo.sh clean       # quit the demo Vivaldi and delete its profile
```

Steps:
1. Tell the user, in one line, that `rehearse` and `record` move the real mouse and type for about a minute: hands off,
   and no other window over the demo window (input goes to whatever is frontmost; `demo.sh` raises the demo Vivaldi first).
2. Edit the storyboard in `tools/demo/take.mjs` (the STORY section), and the start state in `tools/demo/reset.js` (every
   favorite, pin, setting or tab the story adds must be undone there).
3. `rehearse`, then `record`. Check the take before encoding: a contact sheet is
   `ffmpeg -i ~/.cache/vivarc-demo/take.mov -vf "fps=1/2,scale=480:-1,tile=5x6" -frames:v 1 sheet.png`, then read it.
4. Encode, show the user the GIF (`open -R`), and only replace `docs/demo.gif` (on a branch, with a PR) once they approve.

## What was learned (Vivaldi 8.3, 2026-11)

- Spaces: workspaces written into Preferences, or a `workspaceId` in a tab's `vivExtData`, are ignored, and
  `vivaldi.tabsPrivate.move` to such an id does nothing. `seed.js` creates spaces with Vivaldi's own workspace manager
  (webpack module exposing `addWorkspace`) and opens tabs while the space is active.
- New tabs report their URL in `pendingUrl` until they load; match `pendingUrl || url`.
- Synthetic CDP input shows no cursor, so `input.swift` posts real CGEvents with an eased pointer. Vivaldi drops key events
  that only carry a unicode string, so `type` uses real key codes (US layout; add keys to `codes` when a word needs them). Set `flags` to none on every typed key, or a Cmd held by the
  previous shortcut leaks into the letters and they vanish.
- The first click into a background window only focuses it: a right-click sent then just selects the tab. `play()` clicks
  an empty part of the sidebar first.
- A fresh profile has tab bar auto-hide on (the sidebar slides away when the pointer leaves); setup turns it off.
- Positions shift as the story runs (a new favorites row, the URL bar). `take.mjs` reads each element's rect right before
  clicking it; never hard-code coordinates for Vivarc UI.
- Cmd+S (hide the sidebar) only takes effect visually once the sidebar's URL field loses focus; blur it through CDP,
  not Escape, which turns on tile ordering mode in a split view.
- Turn off the update pill (`updateCheck`) or "Update Vivarc" shows in the sidebar.
- GIF: one palette for the clip with `diff_mode=rectangle` gives ~14 MB at 1280 px; per-frame palettes weigh ~230 MB.
- Cmd+Shift+C in the story overwrites the user's clipboard: say so.
