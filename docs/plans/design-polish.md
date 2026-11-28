# Design polish: modern look, fluid motion, personal vibe, polished details

Status: scope decided. PR 1 is ready for `/feature`; the other PRs need the spec work listed under Decision first.

## Question

What design changes and features would make Vivarc look modern, move fluidly, feel personal per space and show polished details, within what a Vivaldi mod can do?

- Inputs: `src/css/vivarc.css` (~840 lines), `src/js/40-theme.js` (per-space theme), `src/js/01-settings.js` (settings schema), `src/js/10-sidebar.js`, `src/js/20-command-bar.js`, `src/start/index.html`.
- Expected outcome: a menu of ideas grouped by pillar, a structure for the work, and a roadmap of single-purpose PRs that `/feature` can take one at a time.
- Constraints: below.

## Constraints

### Platform

- Mods use only `chrome.*`, `vivaldi.prefs`, `vivaldi.searchEngines`, `vivaldi.tabsPrivate` (`docs/HOW-IT-WORKS.md:74`). No build step, no dependency.
- Installed Vivaldi 8.3 ships Chromium 156 (read from the framework binary). Every CSS feature below is available there: `linear()` easing (113), `@starting-style` (117), relative colour `oklch(from ...)` (119), `interpolate-size` (129), `@property` (85), same-document view transitions (111). `vivarc.py` enforces no minimum Vivaldi version; the README says 8.x. Vivaldi 8.0 ships Chromium 148, 8.1 ships 150, 8.2 ships 152 (see References), so every feature here works on all of 8.x with no `@supports` fallback.
- Vivaldi rewrites the classes on `#browser`; Vivarc's `vm-*` classes survive, layout rules use `:has()` (`HOW-IT-WORKS.md:82`).
- Never re-render the sidebar during a drag; defer layout changes out of `dragstart` (`HOW-IT-WORKS.md:72-73`).
- The themed sidebar uses `isolation: isolate` and needs a `z-index` lift while the address bar popups are open; `app-region` is inherited, so decorative overlays need `app-region: none` (`vivarc.css:503-523`).
- The bottom toolbar is a forced single-row flex since 8.3 (`HOW-IT-WORKS.md:82`). Redesigning it means redoing that workaround.
- Peek is third-party; styling it is limited.

### Current design (verified)

- Colour: three root tokens `--vm-surface`, `--vm-text`, `--vm-sel` mixed in sRGB from Vivaldi's `--colorBg`, `--colorFg`, `--colorHighlightBg` (`vivarc.css:3-6`). Hardcoded fallbacks throughout.
- Radii: 13 distinct values (8px x8, 14px x6, 6px x5, 12px x4, 9px x3, then 5, 7, 10, 11, 16, 18, 1, 999). No scale.
- Motion: 7 durations (90 to 260ms), mostly default `ease`. One spring curve, only under `.vm-glass` (`vivarc.css:770`). No `@keyframes`, no `@starting-style`. Menus (`:277`) and the command bar (`:296-314`) have no transition: they appear and vanish instantly.
- Reduced motion: `:202` (stack chevron) and `:208` (folder body) set `transition: none`; `:823-827`, only under `.vm-glass`, sets `transition: none !important` on the panel, command bar, menus, theme pop-up, settings card and toast, and cancels the hover `transform` on favourites and the space pill. Reduced transparency and contrast handled only under `.vm-glass` (`:814-822`).
- Space switch already animates in JS: `animateSpaceChange` (`10-sidebar.js:20-35`) runs Web Animations on the panel (opacity 0.72 to 1, `translateY(4px)`, 220ms, `cubic-bezier(0.22, 1, 0.36, 1)`) and the page (opacity 0.9 to 1, 180ms), cancels on a new switch and skips under Reduce Motion. The tint itself switches instantly. CSS tokens do not reach these JS literals.
- Per-space theme: HSL record `{on, hue, sat, light, grain}` saved in IndexedDB as `theme:space:<id>`, 9 hardcoded presets, flat `--vm-tint` background on `#tabs-tabbar-container`, foreground flips hard at lightness 58, grain via an `feTurbulence` data URI (`40-theme.js:4-32`). No gradient.
- Liquid glass: opt-in, covers menus, command box, switcher, theme pop-up, settings card, toast (`vivarc.css:757-827`). Sidebar glass is faked with gradients.
- Settings: Appearance has two entries, Liquid glass and Glass opacity (`01-settings.js:10-13`). SCHEMA entries take `key`, `section`, `label`, `hint` (string or `{mac, win}`), `default`, `onClass`/`offClass`, `cssVar`, `needs`, `requires`, `fromConfig`; types `range` and `choice` (with `options`) exist. `vivarc.py` reads `~/.vivarc/config.json` but only settings with `fromConfig` use it, so new settings stay out of the installer.
- No test asserts CSS text; tests only check the stylesheet is bundled (`tests/test_install_flow.py:112`, `tests/test_vivarc.py:280`).
- Start page: its own purple palette with inline styles, ignores Vivaldi's theme and the space tint. It is a `file://` copy made by the installer (`vivarc.py:566`) and its URL lives in a user bookmark, so it cannot read the mod's store.

### Code shape that gates motion work (verified unless marked)

- The sidebar rebuilds every row on each refresh: `render()` builds a fresh `.vm-scroll` body with a new `tabRow` per tab, then `panel.replaceChildren(...)` (`10-sidebar.js:1027-1079`, 80ms debounce). Entry animations on rows would replay on every tab event; a sliding active pill and close-collapse need stable, keyed nodes first.
- The command bar list is rebuilt the same way (`20-command-bar.js:267`).
- Overlays close with a synchronous `.remove()` (`20-command-bar.js:209`, `40-theme.js:51`, `10-sidebar.js:239`, `45-settings.js:17`). Exit animations need deferred removal. Unchecked: the command bar harness stubs `setTimeout` and `remove`.
- Saved themes need no migration if new fields are additive: loading spreads the record over `DEFAULT` (`40-theme.js:144`). `tests/test_space_themes.py:37,42` pins `--vm-tint` to `hsl(250 28% 20%)`.
- A token built from `var(--colorFg)` resolves where it is declared; the themed sidebar overrides `--colorFg` on `#tabs-tabbar-container` (`vivarc.css:505`), so fill tokens must be declared there too.

### Repo rules

- No CSS test harness (`.claude/rules/tdd.md`): CSS changes are checked visually in a throwaway profile after `./vivarc.py apply`. JS logic is tested in node.
- Escalate: anything that stores new user data (new theme fields, new settings), architecture changes (keyed sidebar render), anything writing profile files or the installer copy.

## Options

### Idea menu

Effort: S (under a day, CSS only), M (JS + tests), L (refactor). Esc: needs a go from the maintainer before work (new stored data, architecture, installer). Outside references with URLs are in the References section.

**Modern look**

| # | Idea | Effort | Esc | Notes |
|---|---|---|---|---|
| L1 | Design tokens: radius, motion, fill scales | S | | Foundation for everything else. Radii snap by 1 to 2px. |
| L2 | Space gradient derived from the tint (2 stops, hue shift) | S | | CSS only via `oklch(from var(--vm-tint) ...)`. Visible change for every themed space. |
| L3 | Accent derived from the tint (selection, focus ring, switch, drop markers) | S | | Same mechanism. Fixed lightness looks off on near-gray or very light presets (preset 1 is 90% light), needs a clamp. |
| L4 | Real sidebar glass instead of faked gradients | M | | Nothing behind the sidebar to blur; would need the page to extend under it. Likely not feasible. |
| L5 | Start page restyle with shared tokens | S | | Restyle only. Following the tint needs the installer copy or bookmark URL to change (Esc). |

**Fluid motion**

| # | Idea | Effort | Esc | Notes |
|---|---|---|---|---|
| M1 | Entry transitions on menus, command bar, theme pop-up, settings | S | | `@starting-style`, no JS. Exit stays instant. |
| M2 | Exit transitions on the same overlays | M | | Deferred `.remove()` in four places, harness changes. |
| M3 | Spring easing via `linear()` | S | | Replaces the cubic-bezier overshoot; tuning in a window. |
| M4 | Tint cross-fade on space switch | S | | The panel already fades on switch (`animateSpaceChange`); the tint still jumps. `@property --vm-tint`, enabled only during a switch so the theme pad drag stays instant. Risk: recalculates the whole UI subtree per frame. Spike first. |
| M5 | Folder and stack expand to `height: auto` | S | | `interpolate-size: allow-keywords`. Folders already ease; stacks check. |
| M6 | Keyed sidebar render | L | Esc | `10-sidebar.js` is 1427 lines. Unlocks M7 to M9. |
| M7 | Tab close collapse (row shrinks before removal) | M | after M6 | |
| M8 | Sliding active-tab pill | M | after M6 | Indicator element or view transition. |
| M9 | Sliding selection in the command bar | M | | Needs a keyed list in `20-command-bar.js`, smaller than M6. |
| M10 | View transitions for space switch | M | Esc | Unverified on Vivaldi's UI document. Spike only. |

**Personalisation**

| # | Idea | Effort | Esc | Notes |
|---|---|---|---|---|
| P1 | Gradient per space with user-picked stops (Arc-style multi-colour pad) | M | Esc | New stored field on the theme record (additive, no migration). |
| P2 | More presets, curated in OKLCH so all hues feel equally bright | S | | Presets are code, not user data. |
| P3 | Appearance controls: density (row height), corner style, motion (full / reduced / off) | M | Esc | New settings entries. Density interacts with the 8.3 toolbar quirk. |
| P4 | Tinted space icon and switcher chip from the space tint | S | | CSS only. |
| P5 | Auto light/dark per space (follow system) | M | Esc | New stored field. |
| P6 | Boosts: per-site CSS by hostname | L | Esc | Page injection plus new user data. Out of the current mod model. Arc dropped Boosts in Dia. |
| P7 | Compact sidebar with hover reveal | M | Esc | Overlaps Vivaldi's own auto-hide, which 8.1 reworked. |

**Polished details**

| # | Idea | Effort | Esc | Notes |
|---|---|---|---|---|
| D1 | Accent `:focus-visible` rings, `::selection`, thin scrollbars | S | | CSS only. |
| D2 | Command bar: highlight matched characters | M | | Node-testable. |
| D3 | Command bar: key hint footer and empty state | M | | Labels per platform through `window.__vm.keyLabel`. |
| D4 | Reduced motion and reduced transparency for all of Vivarc, not only glass | S | | Folds into L1. |
| D5 | Hover-reveal close button on tab rows with a fade | S | | Check against the current row layout. |
| D6 | Tabular numbers for counters, `text-wrap: balance` for titles | S | | |

### Structure

- **A. Tokens first, then features (recommended).** One small CSS PR, then slices that consume the tokens. Low risk; existing users see radii snap by 1 to 2px and durations move by up to 40ms; no data change.
- **B. Vertical slices without tokens.** Fastest first demo; each slice adds one-off values and a later sweep touches everything again.
- **C. Theme engine rewrite (OKLCH state, stored gradient stops).** Large; needs a stored-record migration and a rewritten test; HSL hue differs from OKLCH hue, so converted themes shift colour. Deriving in CSS from the existing `--vm-tint` gets most of the look with no migration.

## Recommendation

Written before the maintainer's answers; the Decision section below supersedes it.

Option A. Ship the S items that need no escalation first, in this order:

1. `refactor(css): radius, motion and fill tokens` (L1, D4). `vivarc.css`. Visual check.
2. `feat(motion): entry transitions for menus, command bar, theme pop-up and settings` (M1, M3). CSS only.
3. `feat(theme): accent focus rings, selection colour and thin scrollbars` (D1).
4. `feat(theme): accent and gradient derived from the space tint` (L2, L3, P4). `vivarc.css`, `40-theme.js` only if a pure helper is needed, `tests/test_space_themes.py`.
5. `feat(command-bar): highlight the matched text` (D2). `20-command-bar.js`, CSS, `tests/command_bar_*.test.cjs`.
6. `feat(command-bar): key hint footer and empty state` (D3).
7. `feat(start): restyle the guide page with the shared tokens` (L5, restyle only).

Then, on a go per item: M6 keyed sidebar render (unlocks M7, M8), M2 exits, P1 user gradients, P3 Appearance controls, M4 cross-fade after a spike. P6 Boosts and P7 compact sidebar stay out unless the maintainer wants them.

## Decision

Round 1 answers from the maintainer (2026-11-28):

- Structure: option A, tokens first.
- In scope beyond the first seven PRs: P1 user-picked gradients, P3 Appearance controls, M2 overlay exit motion, M4 space cross-fade (after a perf spike), M6 keyed sidebar render with M7 close-collapse and M8 sliding active pill.
- Derived gradient (L2) ships behind a new Appearance switch. Stored themes stay unchanged.
- Round 3: P2 OKLCH presets, M5 smooth stack expand, D5 hover-reveal close, P5 auto light/dark per space added.
- Out of scope: P6 Boosts, P7 compact sidebar, M9 sliding command bar selection, M10 view transitions, L4 real sidebar glass.

Roadmap, one PR each, in order. Items marked Esc were approved in scope here but still get their spec reviewed before `/feature` starts, since they add stored data or change architecture.

| # | PR | Ideas | Files | Tests |
|---|---|---|---|---|
| 1 | `refactor(css): radius, motion and fill tokens` | L1, D4 | `vivarc.css` | visual |
| 2 | `feat(motion): entry transitions for menus, command bar, theme pop-up and settings` | M1, M3 | `vivarc.css` | visual |
| 3 | `feat(theme): accent focus rings, selection colour and thin scrollbars` | D1, D6 | `vivarc.css` | visual |
| 4 | `feat(theme): accent and gradient derived from the space tint` | L2, L3, P4 | `vivarc.css`, `01-settings.js`, `40-theme.js`, `tests/test_space_themes.py` | node (setting, neutral class), visual |
| 5 | `feat(command-bar): highlight the matched text` | D2 | `20-command-bar.js`, CSS, `tests/command_bar_*.test.cjs` | node |
| 6 | `feat(command-bar): key hint footer and empty state` | D3 | same | node |
| 7 | `feat(start): restyle the guide page with the shared tokens` | L5 | `src/start/index.html` | visual |
| 8 | `feat(motion): exit transitions for overlays` | M2 | `20-command-bar.js`, `40-theme.js`, `10-sidebar.js`, `45-settings.js`, CSS, harness | node (removal deferred, then done) |
| 9 | `feat(settings): density, corner style and motion controls` (Esc) | P3 | `01-settings.js`, CSS | node (schema), visual |
| 10 | `feat(theme): user-picked gradient per space` (Esc) | P1 | `40-theme.js`, CSS, `tests/test_space_themes.py` | node |
| 11 | spike, then `feat(theme): cross-fade the tint on space switch` | M4 | CSS, maybe `40-theme.js` | visual, perf check |
| 12 | `refactor(sidebar): keyed render` (Esc) | M6 | `10-sidebar.js` | node, drag check |
| 13 | `feat(sidebar): collapse a closing tab row` | M7 | `10-sidebar.js`, CSS | visual |
| 14 | `feat(sidebar): sliding active-tab indicator` | M8 | `10-sidebar.js`, CSS | visual |
| 15 | `feat(sidebar): smooth stack expand` | M5 | `vivarc.css` | visual |
| 16 | `feat(sidebar): fade in the tab close button on hover` | D5 | `vivarc.css` | visual |
| 17 | `feat(theme): presets curated in OKLCH` | P2 | `40-theme.js`, `tests/test_space_themes.py` (pop-up child positions) | node |
| 18 | `feat(theme): follow the system appearance per space` (Esc) | P5 | `40-theme.js`, CSS, `tests/test_space_themes.py` | node |

PRs 15 and 16 are CSS only and can land any time after PR 1. PR 17 lands after PR 4 so presets are tuned against the derived accent and gradient. PR 18 lands after PR 10 so both stored-field changes share one review of the theme record.

PR 12 gets its own `/research` round (architecture-planner) before `/feature`: it touches drag, stacks and favourites.

Spec status before `/feature`:

- Ready: PR 1.
- Literal spec here, tuned in a window during the PR: PR 2, PR 4.
- Draft, finish the spec first: PR 9, PR 10, PR 18 (new optional field, e.g. `mode: "dark" | "light" | "auto"`, absent means today's behaviour).
- Spike first: PR 11.
- Own research round: PR 12.
- No spec yet, write one at the start of the PR (small, scoped by the idea row): PR 3, 5, 6, 7, 8, 13, 14, 15, 16, 17.

Defaults chosen by the planner, not the maintainer, open to override: the accent (L3) is not behind the gradient switch; under glass, the glass layers stack above the gradient.

## Spec (literals)

### PR 1, tokens

Declared on `#browser.vm-on` and again on `#browser.vm-on #tabs-tabbar-container` (fill tokens resolve `--colorFg` where declared). `--vm-css: 1` stays.

- Radii: `--vm-r-1: 6px` (absorbs 5, 6, 7), `--vm-r-2: 8px` (8, 9), `--vm-r-3: 12px` (10, 11, 12), `--vm-r-4: 14px` (14, 16), `--vm-r-5: 18px`, `--vm-r-full: 999px` (also the 11px switch). The 1px guide line stays literal.
- Durations: `--vm-dur-1: 120ms` (90, 120), `--vm-dur-2: 180ms` (150, 160, 180), `--vm-dur-3: 240ms` (220, 260).
- Easing: `--vm-ease-out: cubic-bezier(0.22, 1, 0.36, 1)` (already at `vivarc.css:177` and in JS at `10-sidebar.js:30`), `--vm-ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1)` (moved from `:770` to the root). A `linear()` spring replaces it in PR 2 once tuned.
- JS motion literals in `animateSpaceChange` (`10-sidebar.js:28-34`) stay as they are; they already match the scale (220ms is between dur-2 and dur-3, keep it). No JS change in PR 1.
- Fills: `--vm-fill-1: color-mix(in srgb, var(--colorFg) 8%, transparent)`, `--vm-fill-2` 14%, `--vm-fill-3` 24%.
- Reduced motion, one policy for all of Vivarc, stated once here and reused by PR 2, 8, 9 and 11: no movement (no transform transitions, no hover scale, no translate or scale on entry or exit), opacity changes stay but at `--vm-dur-1`.
  - One `@media (prefers-reduced-motion: reduce)` block on `#browser.vm-on`: `--vm-dur-2` and `--vm-dur-3` set to `var(--vm-dur-1)`; `transition-property` limited to `opacity, background-color, color, box-shadow` on the overlay and row selectors; the hover `transform: none` from `:826` generalised beyond `.vm-glass`.
  - It replaces `:202`, `:208` and `:823-827`. The folder body (`:208`) animates height: it gets `transition: none` explicitly, since height is movement.
- One `prefers-reduced-transparency` / `prefers-contrast: more` block covers all of Vivarc, keeping today's glass fallbacks (`:814-822`).

### PR 2, overlay entry

- Selectors: `.vm-menu`, `#vm-cmd .vm-cmd-box`, `.vm-theme-pop`, `.vm-set-card`.
- `transition: opacity var(--vm-dur-2) var(--vm-ease-out), transform var(--vm-dur-2) var(--vm-ease-spring)`.
- `--vm-ease-spring` becomes a `linear(...)` curve pasted from the Linear Easing Generator (a light spring, no visible bounce), tuned in a window.
- `@starting-style { opacity: 0; transform: translateY(-4px) scale(0.98); }`.
- Under reduced motion: the PR 1 policy (fade only).
- No JS change; exit stays instant.

### PR 4, derived palette

- JS keeps writing `--vm-tint` as `hsl(H S% L%)`; stored records unchanged.
- `--vm-accent: oklch(from var(--vm-tint) clamp(0.45, l, 0.75) max(c, 0.12) h)` under `.vm-themed`, used by `.vm-selected`, drop markers, the checked switch, focus rings and `--vm-sel`. Starting values, tuned in a window against all 9 presets.
- Near-gray tints have no usable hue (an achromatic colour in `oklch(from ...)` gets hue 0, so the forced chroma lands on red). `40-theme.js` `apply()` adds `vm-tint-neutral` on `#browser` when `sat < 10`; under it, `--vm-accent` falls back to `var(--colorHighlightBg)` and the gradient keeps hue (`h` unchanged, no `+ 30`). Node test: `sat: 5` sets the class, `sat: 28` does not, `on: false` removes it.
- `#browser.vm-themed #tabs-tabbar-container { background-image: linear-gradient(160deg, var(--vm-tint), oklch(from var(--vm-tint) calc(l * 0.86) c calc(h + 30))); }`.
- Under `.vm-glass.vm-themed`, the glass rule also sets `background-image` on that element (`vivarc.css:783`). Default: the glass layers stack above the gradient in one comma-separated `background-image`, gradient last. Confirm visually.
- The gradient applies only under a class from a new Appearance setting, placed after `glassOpacity`: `{ key: "spaceGradient", section: "Appearance", label: "Space gradient", hint: "Blend each space's colour into a soft gradient.", default: true, onClass: "vm-gradient" }` in `01-settings.js` SCHEMA. No `fromConfig`, so the installer is untouched. On by default, so themed spaces change look after the update: note it in `CHANGELOG.md`. The accent (L3) is not behind the switch.

### PR 9, Appearance controls (draft)

- `density`: compact / default / comfortable, sets `--vm-row-h` to 28 / 32 / 36px (values to confirm against the current row height).
- `corners`: sharp / default / round, multiplies the radius scale by 0.5 / 1 / 1.4 through one `--vm-r-k` factor.
- `motion`: full / reduced / off. Reduced applies the PR 1 reduced-motion policy through a class; off also sets `--vm-dur-1` to `0ms`. System Reduce Motion always wins over full.
- All three use `type: "choice"`. Open: whether a choice setting can drive `cssVar` or a class per option today, or `01-settings.js` needs a small extension. Read it when finishing this spec.

### PR 10, user-picked gradient (draft)

- Additive optional field on the theme record: `stops: [{hue, sat, light}, ...]`, 2 or 3 entries. Absent means the derived gradient (PR 4). No migration; `{...DEFAULT, ...saved}` still loads old records.
- JS writes `--vm-grad` as a `linear-gradient(160deg, ...)` string when `stops` exists; CSS prefers `--vm-grad` over the derived one.
- Editor: a second and third handle on the existing hue/lightness pad.

## Test plan

- Theme (node, `tests/test_space_themes.py`): `{on:true, hue:250, sat:28, light:20, grain:30}` still yields `--vm-tint: hsl(250 28% 20%)`; a legacy `theme` record still applies to a space with none; `on:false` removes every theme property, including any new one.
- Command bar highlight (node): query `git` on `GitHub` marks characters 0 to 3; no match marks nothing; matching ignores case; the label is never injected as HTML.
- Settings, if any is added: default value, class or cssVar output, one section, a hint for macOS and Windows.
- CSS PRs (visual, throwaway profile after `./vivarc.py apply`): glass on and off, themed and unthemed, all 9 presets plus Intensity 0 (gray tint), macOS Reduce Motion and Reduce Transparency on, a favourite drag, address bar popups over the themed sidebar.

## Open questions

None. Round 2 answers (2026-11-28): space gradient switch on by default; rows and cards at 12px; start page restyle only; new scopes `motion` and `start` approved.

## References

Facts from search results; pages marked (snippet) were not opened in full.

- Vivaldi versions: 8.0 on Chromium 148 ([8.0 RC4](https://vivaldi.com/blog/desktop/8-0-rc-4/)), 8.1 on 150 ([snapshot](https://vivaldi.com/blog/desktop/vivaldi-8-1-bumped-to-chromium-150-vivaldi-browser-snapshot-4085-3/)), 8.2 on 152 ([changelog](https://vivaldi.com/changelog-vivaldi-browser-8-2)). 8.1 reworked auto-hide ([AlternativeTo](https://alternativeto.net/news/2026/7/vivaldi-8-1-introduces-tab-behavior-improvements-and-a-more-polished-auto-hide-feature/)).
- CSS landings: [linear()](https://developer.chrome.com/docs/css-ui/css-linear-easing-function) (113, with the Linear Easing Generator), [@starting-style](https://developer.chrome.com/blog/entry-exit-animations) (117), [view transitions](https://developer.chrome.com/docs/web-platform/view-transitions/same-document) (111), [interpolate-size](https://developer.chrome.com/blog/new-in-chrome-129) (129). Relative colour (119) from memory.
- Arc: per-space themes from the Space title ([release notes](https://start.arc.net/release-notes)); Boosts, Little Arc and Peek are not carried into Dia ([sunset FAQ](https://resources.arc.net/hc/en-us/articles/44413577819159-Arc-Sunset-Frequently-Asked-Questions)). Official wording on the gradient pad and grain slider: unsourced.
- Dia: built for familiarity and simplicity ([Browser Company](https://browsercompany.substack.com/p/the-strategy-behind-dias-design), snippet); bringing back sidebar mode ([TechCrunch](https://techcrunch.com/2025/11/03/dias-ai-browser-starts-adding-arcs-greatest-hits-to-its-feature-set)). No official theming found.
- Zen: per-workspace icon and name ([workspaces](https://docs.zen-browser.app/user-manual/workspaces)), sidebar gradient and accent colour ([flags](https://docs.zen-browser.app/guides/about-config-flags)), compact mode ([docs](https://docs.zen-browser.app/user-manual/compact-mode)).
- Linear: theme generator rebuilt in LCH from base colour, accent and contrast, lightness stepped by elevation ([redesign write-up](https://linear.app/now/how-we-redesigned-the-linear-ui), [custom themes](https://linear.app/docs/custom-themes)). Supports deriving every tone from `--vm-tint` (L2, L3).
- Raycast: primary action on Enter with its hint shown, Compact and Expanded window modes, separate light and dark themes ([action panel](https://manual.raycast.com/action-panel), [themes](https://manual.raycast.com/themes)). Supports D3.
- Apple HIG [Materials](https://developer.apple.com/design/human-interface-guidelines/materials): the regular (more opaque) material for text-heavy surfaces such as sidebars; custom surfaces must honour Reduce Transparency and Increase Contrast. Supports keeping the sidebar opaque (L4 dropped) and D4.
