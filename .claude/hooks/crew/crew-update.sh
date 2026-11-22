#!/usr/bin/env bash
# crew-update.sh [--dry-run] [--local]
# Proposes the crew update to the adopted repo this script sits in, as a pull request. Run it from anywhere inside
# the repo. It clones the plugin source (CREW_SOURCE, default the public redgreen repo), takes the live default
# branch of origin, builds the update in a throwaway worktree of origin/<base> with the repo's own vendored
# .claude/hooks/crew/crew-vendor pointed at the clone (CREW_PLUGIN_DIR): nothing from the clone is ever executed.
# Plan, stop on EDITED or CLASH, apply, check, stage only the plan's paths plus the lock and settings, commit on
# chore/crew-update-<12 hex of the source revision>, push and open a PR with gh (a pushed branch without a PR only
# gets the PR). A source that is not ahead of the locked revision is skipped. --local keeps the commit on a local
# branch (no push, no gh); --dry-run prints the plan only. The caller's checkout and branch are never modified.
# Prints one line "crew-update <result>"; exit 1 when blocked or failed. Needs git and jq, and gh for the PR step.
set -u
LOCK=".claude/crew.lock.json"
SOURCE="${CREW_SOURCE:-https://github.com/KASOGIT/redgreen.git}"

LOCAL=0; DRY=0
for a in "$@"; do
  case "$a" in
    --local) LOCAL=1 ;;
    --dry-run) DRY=1 ;;
    *) echo "usage: crew-update.sh [--dry-run] [--local]" >&2; exit 2 ;;
  esac
done

command -v git >/dev/null 2>&1 || { echo "crew-update: git is required" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "crew-update: jq is required" >&2; exit 1; }
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -n "$ROOT" ] && [ -f "$ROOT/$LOCK" ] || { echo "crew-update: not an adopted repo" >&2; exit 1; }

TMP=""; WT=""
cleanup() {
  [ -n "$WT" ] && git -C "$ROOT" worktree remove --force "$WT" >/dev/null 2>&1
  git -C "$ROOT" worktree prune >/dev/null 2>&1
  [ -n "$TMP" ] && command rm -r -f "$TMP"
  WT=""; TMP=""
}
trap cleanup EXIT

RESULT=""; BRANCH=""; EXISTS=0

# lastline <text>: the last non-empty line
lastline() { printf '%s\n' "$1" | grep -v '^[[:space:]]*$' | tail -n 1; }
# scrub <text>: drops user:password@ from URLs
scrub() { printf '%s' "$1" | sed -E 's#(://)[^/@[:space:]]*@#\1#g'; }

# create_pr <base> <title> <body>: opens the PR for the pushed $BRANCH.
create_pr() {
  local url
  url="$(cd "$ROOT" && gh pr create --base "$1" --head "$BRANCH" --title "$2" --body "$3" 2>&1)" \
    || {
      if printf '%s' "$url" | grep -qi 'already exists'; then RESULT="skipped (already proposed: $BRANCH)"; return 0; fi
      RESULT="error (pushed $BRANCH, gh pr create failed: $(lastline "$url"))"; return 1
    }
  RESULT="proposed $(lastline "$url")"
}

# rv <args>: the repo's own crew-vendor on the cloned plugin, without the CI tokens
rv() { env -u GH_TOKEN -u GITHUB_TOKEN CREW_PLUGIN_DIR="$src/crew" "$vendor" "$@"; }

update() {
  local out rc base rev prs vendor oldrev newrev scope subj files body blk clash edited lockrev allowed p src same
  out="$(git -C "$ROOT" fetch -q origin 2>&1)" || { RESULT="error (git fetch origin failed: $(printf '%s' "$out" | head -n 1))"; return 1; }
  base="$(git -C "$ROOT" ls-remote --symref origin HEAD 2>/dev/null | awk '/^ref: refs\/heads\// { sub(/^ref: refs\/heads\//, ""); sub(/[ \t]+HEAD$/, ""); print; exit }')"
  if [ -z "$base" ] || ! git -C "$ROOT" rev-parse --verify -q "refs/remotes/origin/$base" >/dev/null; then
    RESULT="error (cannot resolve default branch)"; return 1
  fi
  git -C "$ROOT" cat-file -e "origin/$base:$LOCK" 2>/dev/null || { RESULT="skipped (not adopted on $base)"; return 0; }

  TMP="$(mktemp -d)" || { RESULT="error (no temp folder)"; return 1; }
  src="$TMP/src"
  out="$(git clone -q -- "$SOURCE" "$src" 2>&1)" || { RESULT="$(scrub "error (cannot clone $SOURCE: $(lastline "$out"))")"; return 1; }
  rev="$(git -C "$src" rev-parse HEAD 2>/dev/null | cut -c1-12)"
  [ -n "$rev" ] || { RESULT="error (cannot read the source revision)"; return 1; }
  [ -d "$src/crew" ] || { RESULT="$(scrub "error (no crew folder in $SOURCE)")"; return 1; }
  BRANCH="chore/crew-update-$rev"

  lockrev="$(git -C "$ROOT" show "origin/$base:$LOCK" 2>/dev/null | jq -r '.revision // empty' 2>/dev/null)"
  if [ -n "$lockrev" ] && git -C "$src" cat-file -e "$lockrev^{commit}" 2>/dev/null \
    && ! git -C "$src" merge-base --is-ancestor "$lockrev" HEAD 2>/dev/null; then
    RESULT="skipped (source is not ahead of $(printf '%s' "$lockrev" | cut -c1-7))"; return 0
  fi

  if [ "$LOCAL" -eq 1 ] && git -C "$ROOT" show-ref -q --verify "refs/heads/$BRANCH"; then
    RESULT="skipped (already committed: $BRANCH)"; return 0
  fi
  if git -C "$ROOT" ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
    if [ "$LOCAL" -eq 0 ]; then
      prs="$(cd "$ROOT" && gh pr list --head "$BRANCH" --state all --json number --jq length 2>&1)" \
        || { RESULT="error (gh pr list failed: $(printf '%s' "$prs" | tail -n 1))"; return 1; }
      if [ "$prs" = 0 ]; then
        [ "$DRY" -eq 1 ] && { RESULT="dry-run"; return 0; }
        out="$(git -C "$ROOT" fetch -q origin "refs/heads/$BRANCH" 2>&1)" || { RESULT="error (git fetch $BRANCH failed: $(lastline "$out"))"; return 1; }
        subj="$(git -C "$ROOT" log -1 --format=%s FETCH_HEAD 2>/dev/null)"; body="$(git -C "$ROOT" log -1 --format=%b FETCH_HEAD 2>/dev/null)"
        [ -n "$subj" ] || { RESULT="error (empty commit title on $BRANCH)"; return 1; }
        create_pr "$base" "$subj" "$body"; return
      fi
    fi
    [ "$LOCAL" -eq 0 ] && [ "$DRY" -eq 1 ] && { RESULT="skipped (already proposed: $BRANCH)"; return 0; }
    EXISTS=1
  fi

  WT="$TMP/wt"
  out="$(git -C "$ROOT" worktree add -q --detach "$WT" "origin/$base" 2>&1)" || { WT=""; RESULT="error (worktree: $(printf '%s' "$out" | head -n 1))"; return 1; }

  vendor="$WT/.claude/hooks/crew/crew-vendor"
  [ -x "$vendor" ] || { RESULT="error (no vendored crew-vendor: run crew-vendor apply from the plugin once)"; return 1; }
  # apply replaces the vendored file with the clone's version: keep running the copy that was committed
  command cp -f "$vendor" "$TMP/crew-vendor" && vendor="$TMP/crew-vendor"
  out="$(rv plan "$WT" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ]; then
    printf '%s\n' "$out"
    clash="$(printf '%s\n' "$out" | awk '/^Files that exist and were not written/ {f=1; next} f && /^  [^ ]/ {sub(/^  /, ""); printf "%s%s", s, $0; s=", "; next} {f=0}')"
    edited="$(printf '%s\n' "$out" | awk '/^Files edited locally/ {f=1; next} f && /^  [^ ]/ {sub(/^  /, ""); printf "%s%s", s, $0; s=", "; next} {f=0}')"
    if [ -n "$clash" ] || [ -n "$edited" ]; then
      blk=""
      [ -n "$clash" ] && blk="clash: $clash"
      [ -n "$edited" ] && blk="${blk:+$blk; }edited: $edited"
      RESULT="blocked ($blk)"
    else
      RESULT="error (crew-vendor plan failed)"
    fi
    return 1
  fi
  if rv check "$WT" >/dev/null 2>&1; then RESULT="up-to-date"; return 0; fi
  if [ "$DRY" -eq 1 ]; then printf '%s\n' "$out"; RESULT="dry-run"; return 0; fi

  allowed="$(printf '%s\n' "$out" | awk '/^(NEW|UPDATE|MODE|DELETE):$/ {f=1; next} f && /^  [^ ]/ {sub(/^  /, ""); print; next} {f=0}')
$LOCK
.claude/settings.json"
  # a settings.json symlinked to a tracked file: the file it points to is part of the plan
  if [ -L "$WT/.claude/settings.json" ]; then
    p="$(perl -MCwd=realpath -e 'print realpath(shift)' "$WT/.claude/settings.json" 2>/dev/null)"; same="$(cd "$WT" && pwd -P)"
    case "$p" in "$same"/*) allowed="$allowed
${p#"$same"/}" ;; esac
  fi
  out="$(rv apply "$WT" 2>&1)" || { printf '%s\n' "$out"; RESULT="error (crew-vendor apply failed)"; return 1; }
  out="$(rv check "$WT" 2>&1)" || { printf '%s\n' "$out"; RESULT="error (crew-vendor check fails after apply)"; return 1; }
  while IFS= read -r -d '' p; do
    p="${p:3}"
    printf '%s\n' "$allowed" | grep -qxF -- "$p" || { RESULT="error (unexpected change: $p)"; return 1; }
  done < <(git -C "$WT" status --porcelain -z --untracked-files=all)
  # -f: a path the repo's .gitignore matches is still part of the plan
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    if [ -e "$WT/$p" ] || git -C "$WT" ls-files --error-unmatch -- "$p" >/dev/null 2>&1; then
      git -C "$WT" add -f -A -- "$p" >/dev/null 2>&1 || { RESULT="error (cannot stage $p)"; return 1; }
      [ ! -e "$WT/$p" ] || git -C "$WT" ls-files --error-unmatch -- "$p" >/dev/null 2>&1 || { RESULT="error (not staged: $p)"; return 1; }
    fi
  done <<END_STAGE
$allowed
END_STAGE
  files="$(git -C "$WT" diff --cached --name-only)"
  [ -n "$files" ] || { RESULT="up-to-date"; return 0; }
  if [ "${GITHUB_ACTIONS:-}" = true ] && printf '%s\n' "$files" | grep -q '^\.github/workflows/'; then
    RESULT="blocked (workflow file changed: run /crew-update locally or use a token with workflow scope)"; return 1
  fi
  oldrev="$(git -C "$WT" show "HEAD:$LOCK" | jq -r '.revision // "unknown"')"
  newrev="$(jq -r '.revision // "unknown"' "$WT/$LOCK")"
  subj="$(git -C "$WT" log -1 --format=%s HEAD -- "$LOCK")"
  scope="$(printf '%s\n' "$subj" | sed -n 's/^[a-z]*(\([^)]*\)).*/\1/p')"
  [ -n "$scope" ] || scope=claude
  subj="chore($scope): update vendored crew workflow"
  body="Files changed:
$(printf '%s\n' "$files" | sed 's/^/- /')

Crew revision: $(printf '%s' "$oldrev" | cut -c1-7) -> $(printf '%s' "$newrev" | cut -c1-7)"
  out="$(git -C "$WT" -c commit.gpgsign=false commit -q -m "$subj" -m "$body" 2>&1)" || { RESULT="error (commit failed: $(lastline "$out"))"; return 1; }
  if [ "${EXISTS:-0}" -eq 1 ]; then
    # the branch of an earlier run blocks unless it was merged since (strictly behind the base) and no longer holds this plan
    out="$(git -C "$WT" fetch -q origin "refs/heads/$BRANCH" 2>&1)" || { RESULT="error (git fetch $BRANCH failed: $(lastline "$out"))"; return 1; }
    same=1
    while IFS= read -r p; do
      [ "$(git -C "$WT" rev-parse -q --verify "FETCH_HEAD:$p" 2>/dev/null)" = "$(git -C "$WT" rev-parse -q --verify "HEAD:$p" 2>/dev/null)" ] || same=0
    done <<END_SAME
$files
END_SAME
    if [ "$same" -eq 1 ] || [ "$(git -C "$WT" rev-parse FETCH_HEAD)" = "$(git -C "$ROOT" rev-parse "origin/$base")" ] \
      || ! git -C "$ROOT" merge-base --is-ancestor "$(git -C "$WT" rev-parse FETCH_HEAD)" "origin/$base"; then
      RESULT="skipped (already proposed: $BRANCH)"; return 0
    fi
    # named after the planned content, so the same plan finds its branch again whatever the base does meanwhile
    same="$(printf '%s\n' "$files" | while IFS= read -r p; do printf '%s %s\n' "$p" "$(git -C "$WT" rev-parse -q --verify "HEAD:$p")"; done | git -C "$WT" hash-object --stdin | cut -c1-7)"
    BRANCH="$BRANCH-$same"
    if [ "$LOCAL" -eq 1 ] && git -C "$ROOT" show-ref -q --verify "refs/heads/$BRANCH"; then RESULT="skipped (already committed: $BRANCH)"; return 0; fi
    if git -C "$ROOT" ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
      RESULT="skipped (already proposed: $BRANCH)"
      [ "$LOCAL" -eq 0 ] || return 0
      prs="$(cd "$ROOT" && gh pr list --head "$BRANCH" --state all --json number --jq length 2>&1)" \
        || { RESULT="error (gh pr list failed: $(lastline "$prs"))"; return 1; }
      [ "$prs" = 0 ] || return 0
      create_pr "$base" "$subj" "$body"; return
    fi
  fi
  if [ "$LOCAL" -eq 1 ]; then
    out="$(git -C "$WT" branch "$BRANCH" 2>&1)" || { RESULT="error (branch $BRANCH: $(printf '%s' "$out" | head -n 1))"; return 1; }
    RESULT="committed $BRANCH"; return 0
  fi
  command -v gh >/dev/null 2>&1 || { RESULT="error (gh is required to open the PR, so nothing was sent to origin; use --local to commit only)"; return 1; }
  out="$(git -C "$WT" push -q origin "HEAD:refs/heads/$BRANCH" 2>&1)" || { RESULT="error (push failed: $(lastline "$out"))"; return 1; }
  create_pr "$base" "$subj" "$body"
}

update; rc=$?
cleanup
echo "crew-update $RESULT"
exit "$rc"
