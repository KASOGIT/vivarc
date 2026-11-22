#!/usr/bin/env bash
# PreToolUse hook (matcher: Write|Edit|MultiEdit). Spec-first gate: before an existing production
# file is edited, at least one test file must already be touched under the same module, either in
# the working tree (modified, staged, untracked) or in a commit ahead of origin/<baseBranch>. When
# that remote ref does not exist but a local branch named <baseBranch> does (a project with no
# remote), the local branch is the comparison base. With neither, the hook does nothing.
#
# The layout comes from one optional file, <project>/.claude/crew.json (schema: crew.schema.json,
# example: crew.example.json). The project is $CLAUDE_PROJECT_DIR, or the git top level of the
# input's cwd when that is unset or not a directory. Without that file, or without a usable
# specFirst block (at least one valid root and one source extension), the hook does nothing at all:
# exit 0, no output, no log. A malformed or unreadable config behaves the same way.
#
# A production edit is a file under a configured root whose extension is in sourceExtensions. The
# module is the first moduleDepth directories below the root; moduleDepth 0 makes the whole root
# one module (a flat source folder). testRoots (optional, per root) lists extra directories,
# relative to the same base as the root, where a test also counts: a sibling test/ or tests/
# folder. A module whose first directory
# matches the root's sharedModulePattern (a cross-cutting layer) accepts a test anywhere under the
# root. Never gated: files matching testPatterns (basename globs), files matching ignoreRegex
# (extended regular expressions tested against /<module>/<rest of path>), and the built-in
# language-neutral ignores: test, fixture and mock directories (fixtures, tests, __tests__,
# __fixtures__, __snapshots__, __mocks__) and *.fixture, *.fixtures, *.e2e-fixture, *.mock, *.stub
# and *.test-utils files of any extension. A Write to a path that does not exist yet is scaffolding:
# allowed in every mode, logged in nudge and shadow mode with new_file true when no test was
# touched, never nudged.
#
# Mode: CREW_POLICY_MODE (env, wins when set and not empty), else specFirst.mode, else nudge.
# Matched case-insensitively:
#   nudge   (default) log would-be blocks, allow the edit, and tell Claude once per session, module
#           and agent (additionalContext, no permissionDecision) that the edit applied with no test
#           touched. Claude then tells the developer in one line and writes the test before any
#           further edit there, or says why the edit is exempt. The text reaches Claude next to the
#           tool result, so it cannot undo the edit that triggered it. The marker file
#           ${TMPDIR:-/tmp}/crew-spec-first-nudge-<uid>-<hash of session_id, root (with its prefix directory), module and agent_id>
#           is created only when nudging; TMPDIR must be absolute. No session_id, no nudge.
#   shadow  log would-be blocks, allow the edit, say nothing
#   enforce exit 2 with a reason on stderr
#   off     do nothing
# Any other value behaves as shadow. Fails open (exit 0, no output, no log) on any error: missing
# jq or git, not a git repo, neither origin/<baseBranch> nor a local <baseBranch>, malformed input
# or config. jq and git are also looked up in /opt/homebrew/bin, /usr/local/bin, /usr/bin and
# /bin after the session PATH, because a Desktop-launched session may lack the first two;
# CREW_FALLBACK_PATH replaces that list (the tests use it; an empty value appends nothing). An unwritable log or
# marker only loses the log line or the nudge. File contents are never logged or printed. Pure
# refactors and logging-only changes cannot be detected here: Claude says they are exempt.
#
# Log: ${CLAUDE_PLUGIN_DATA}/hook-log.jsonl, written only when that variable is set and the
# directory can be created and written, otherwise skipped. One JSON line per would-be block:
#   ts          UTC ISO 8601, e.g. 2026-07-04T09:30:00Z
#   session_id  session id from the hook input, control characters removed (may be empty)
#   tool        tool name from the hook input (Write, Edit, MultiEdit)
#   branch      current branch name, empty on a detached HEAD
#   file        path of the edited file relative to the directory that holds the root
#   context     the module of the file (moduleDepth directories below the root, joined by /;
#               empty when moduleDepth is 0)
#   new_file    true when the file did not exist yet
#   would_block false for new files, true otherwise
#   mode        effective mode, nudge or shadow
#   nudged      true on the line that sent the nudge
#   project     absolute project root (CLAUDE_PROJECT_DIR, or the git top level of cwd)
# Sessions with a would-block, with the files involved:
#   jq -s 'map(select(.would_block)) | group_by(.session_id) | map({branch: .[0].branch, nudged: any(.[]; .nudged), files: (map(.file) | unique)})' "$CLAUDE_PLUGIN_DATA/hook-log.jsonl"
#
# Every behavior has a case in tests/spec-first-cases.jsonl. After any edit run:
#   hooks/tests/run-all.sh

set -euo pipefail
trap 'exit 0' ERR

FALLBACK_PATH="${CREW_FALLBACK_PATH-/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin}"
[[ -z "$FALLBACK_PATH" ]] || PATH="${PATH:+$PATH:}$FALLBACK_PATH"

# No config in a known project dir: stop before forking cat and jq.
if [[ -n "${CLAUDE_PROJECT_DIR:-}" && -d "$CLAUDE_PROJECT_DIR" && ! -f "$CLAUDE_PROJECT_DIR/.claude/crew.json" ]]; then exit 0; fi

command -v jq >/dev/null 2>&1 || exit 0
command -v git >/dev/null 2>&1 || exit 0

INPUT="$(cat)"
IFS=$'\x1f' read -r FILE CWD SID TOOL AGENT <<<"$(printf '%s' "$INPUT" | jq -r '[.tool_input.file_path, .cwd, .session_id, .tool_name, .agent_id] | map((. // "") | tostring | gsub("[\u0000-\u001f]"; "")) | join("\u001f")' 2>/dev/null || true)"
[[ -n "$FILE" ]] || exit 0

PROJ="${CLAUDE_PROJECT_DIR:-}"
[[ -d "$PROJ" ]] || PROJ="$(git -C "${CWD:-$PWD}" rev-parse --show-toplevel 2>/dev/null || true)"
CONF="$PROJ/.claude/crew.json"
[[ -n "$PROJ" && -f "$CONF" && -r "$CONF" ]] || exit 0

CFG_FILTER='
  def clean: tostring | gsub("[\u0000-\u001f]"; "");
  if (type == "object" and (.specFirst | type) == "object" and (.specFirst.roots | type) == "array" and (.specFirst.sourceExtensions | type) == "array") then
    ("S\u001f" + ((.baseBranch // "main") | clean) + "\u001f" + ((.specFirst.mode // "") | clean) + "\u001f" + ((.specFirst.ruleFile // "") | clean)),
    (.specFirst.roots[] | select(type == "object" and (.path | type) == "string") | "R\u001f" + (.path | clean) + "\u001f" + ((.moduleDepth // 1) | clean) + "\u001f" + ((.sharedModulePattern // "") | clean) + "\u001f" + ((.testRoots // []) | if type == "array" then map(strings | clean) | join(" ") else "" end)),
    (.specFirst.sourceExtensions[] | strings | clean | select(length > 1 and startswith(".") and (contains("/") | not)) | "E\u001f" + .),
    ((.specFirst.testPatterns | if type == "array" and length > 0 then . else ["*.spec.*", "*.test.*", "*_test.*", "test_*.*"] end)[] | strings | clean | select(length > 0 and (contains("/") | not)) | "T\u001f" + .),
    ((.specFirst.ignoreRegex | if type == "array" then . else [] end)[] | strings | clean | "I\u001f" + .)
  else empty end'

BASE_BRANCH=main
CFG_MODE=""
RULE=""
ROOTS_PATH=()
ROOTS_DEPTH=()
ROOTS_SHARED=()
ROOTS_TESTROOTS=()
EXTS=()
TESTS=()
IGNORES=()
CFG_OUT="$(jq -r "$CFG_FILTER" "$CONF" 2>/dev/null)" || exit 0
while IFS=$'\x1f' read -r KIND A B C D; do
  case "$KIND" in
    S) BASE_BRANCH="$A"; CFG_MODE="$B"; RULE="$C" ;;
    R)
      RP="$A"
      while [[ "$RP" == ./* ]]; do RP="${RP#./}"; done
      RP="${RP%/}"
      if [[ "$RP" =~ ^[A-Za-z0-9_./-]+$ && "$RP" != . && "/$RP/" != *"/../"* && "$B" =~ ^[0-9]$ ]]; then
        TR=""
        set -f
        for T in $D; do
          while [[ "$T" == ./* ]]; do T="${T#./}"; done
          T="${T%/}"
          if [[ "$T" =~ ^[A-Za-z0-9_./-]+$ && "$T" != . && "/$T/" != *"/../"* ]]; then TR="${TR:+$TR }$T"; fi
        done
        set +f
        ROOTS_PATH+=("$RP")
        ROOTS_DEPTH+=("$B")
        ROOTS_SHARED+=("$C")
        ROOTS_TESTROOTS+=("$TR")
      fi ;;
    E) EXTS+=("$A") ;;
    T) TESTS+=("$A") ;;
    I) IGNORES+=("$A") ;;
  esac
done <<<"$CFG_OUT"
[[ ${#ROOTS_PATH[@]} -gt 0 && ${#EXTS[@]} -gt 0 ]] || exit 0
[[ ${#TESTS[@]} -gt 0 ]] || TESTS=("*.spec.*" "*.test.*" "*_test.*" "test_*.*")
[[ "$BASE_BRANCH" =~ ^[A-Za-z0-9._/-]+$ ]] || exit 0

RAW_MODE="${CREW_POLICY_MODE:-}"
[[ -n "$RAW_MODE" ]] || RAW_MODE="$CFG_MODE"
case "${RAW_MODE:-nudge}" in
  [Nn][Uu][Dd][Gg][Ee]) MODE=nudge ;;
  [Ee][Nn][Ff][Oo][Rr][Cc][Ee]) MODE=enforce ;;
  [Oo][Ff][Ff]) exit 0 ;;
  *) MODE=shadow ;;
esac

ABS="$FILE"
[[ "$ABS" == /* ]] || ABS="${CWD:-$PWD}/$FILE"
if [[ "$ABS" == *//* || "$ABS" == */./* || "$ABS" == */../* || "$ABS" == */. || "$ABS" == */.. ]]; then
  IFS=/ read -ra PARTS <<<"$ABS"
  NSTACK=0
  for P in "${PARTS[@]}"; do
    case "$P" in
      "" | .) ;;
      ..) [[ $NSTACK -eq 0 ]] || NSTACK=$((NSTACK - 1)) ;;
      *) STACK[NSTACK]="$P"; NSTACK=$((NSTACK + 1)) ;;
    esac
  done
  ABS=""
  for ((IDX = 0; IDX < NSTACK; IDX++)); do ABS+="/${STACK[IDX]}"; done
fi

BASE="${ABS##*/}"

EXT_OK=false
for EXT in "${EXTS[@]}"; do
  if [[ "$BASE" == *"$EXT" ]]; then EXT_OK=true; fi
done
[[ "$EXT_OK" == true ]] || exit 0

for PAT in "${TESTS[@]}"; do
  # shellcheck disable=SC2053
  if [[ "$BASE" == $PAT ]]; then exit 0; fi
done

# The file must sit inside the project; its root is the first directory below it that matches a root,
# so a file in another repo or under node_modules is not gated.
# A case-insensitive filesystem (the config also opens under an upper-case name) matches ignoring case.
CI_FS=false
[[ ! -e "${CONF%crew.json}CREW.JSON" ]] || CI_FS=true
[[ "$CI_FS" == false ]] || shopt -s nocasematch
PROJ_P="${PROJ%/}"
# Absolute, resolved common git dir of a directory (git before 2.31 prints it relative).
git_common() {
  local c
  c="$(git -C "$1" rev-parse --git-common-dir 2>/dev/null)" || return 1
  [[ "$c" == /* ]] || c="$(cd -P "$1/$c" 2>/dev/null && pwd)" || return 1
  printf '%s' "$c"
}
if [[ "$ABS" != "$PROJ_P"/* ]]; then
  cd -P "$PROJ" 2>/dev/null || exit 0
  PROJ_P="${PWD%/}"
  PD="${ABS%/*}"
  TAIL="${ABS##*/}"
  while [[ -n "$PD" && ! -d "$PD" ]]; do TAIL="${PD##*/}/$TAIL"; PD="${PD%/*}"; done
  cd -P "${PD:-/}" 2>/dev/null || exit 0
  ABS="${PWD%/}/$TAIL"
  if [[ "$ABS" != "$PROJ_P"/* ]]; then
    # Outside the project folder: only a worktree of the project's own repo counts, and it is its own prefix.
    { read -r WT_TOP; read -r WT_COMMON; } <<<"$(git rev-parse --show-toplevel --git-common-dir 2>/dev/null)"
    [[ -n "$WT_COMMON" ]] || exit 0
    [[ "$WT_COMMON" == /* ]] || WT_COMMON="$(cd -P "$WT_COMMON" 2>/dev/null && pwd)" || exit 0
    [[ "$(git_common "$PROJ_P")" == "$WT_COMMON" ]] || exit 0
    PROJ_P="${WT_TOP%/}"
    [[ "$ABS" == "$PROJ_P"/* ]] || exit 0
  fi
fi
PREL="${ABS:${#PROJ_P}+1}"
[[ "/$PREL" != */node_modules/* ]] || exit 0

# Production edit: a file inside a module directory of a configured root. Of the roots that match,
# the one starting earliest in the path wins (the longest remainder).
BS='\'
MATCHED=false
BEST_SUB=""
IDX=0
while [[ $IDX -lt ${#ROOTS_PATH[@]} ]]; do
  ESC="${ROOTS_PATH[$IDX]//./$BS.}"
  if [[ "${ROOTS_DEPTH[$IDX]}" == 0 ]]; then
    RE="^${ESC}/(.+)\$"
  else
    RE="^${ESC}/(([^/]+/){${ROOTS_DEPTH[$IDX]}})(.+)\$"
  fi
  SUB="$PREL"
  while [[ ! "$SUB" =~ $RE && "$SUB" == */* ]]; do SUB="${SUB#*/}"; done
  if [[ "$SUB" =~ $RE && ( "$MATCHED" == false || ${#SUB} -gt ${#BEST_SUB} ) ]]; then
    BEST_SUB="$SUB"
    RPATH="${ROOTS_PATH[$IDX]}"
    if [[ "${ROOTS_DEPTH[$IDX]}" == 0 ]]; then
      CTX=""
      REST="${BASH_REMATCH[1]}"
    else
      CTX="${BASH_REMATCH[1]%/}"
      REST="${BASH_REMATCH[3]}"
    fi
    SHARED="${ROOTS_SHARED[$IDX]}"
    TESTROOTS="${ROOTS_TESTROOTS[$IDX]}"
    MATCHED=true
  fi
  IDX=$((IDX + 1))
done
[[ "$MATCHED" == true ]] || exit 0
shopt -u nocasematch

# A directory with its own .git between the project and the root is another repo (a worktree of the
# project's repo stays gated).
PFX="${PREL%"$BEST_SUB"}"
ROOT="$PROJ_P/$PFX"
NEST="$PROJ_P"
while [[ -n "$PFX" ]]; do
  NEST="$NEST/${PFX%%/*}"
  PFX="${PFX#*/}"
  if [[ -e "$NEST/.git" ]]; then
    [[ "$(git_common "$NEST")" == "$(git_common "$PROJ_P")" ]] || exit 0
    break
  fi
done
TARGET="/${CTX:+$CTX/}$REST"
BUILTIN_DIR_RE='/(fixtures?|tests?|__tests__|__fixtures__|__snapshots__|__mocks__)/'
BUILTIN_SUFFIX_RE='\.(fixtures?|e2e-fixture|mock|stub|test-utils)\.[A-Za-z0-9]+$'
if [[ "$TARGET" =~ $BUILTIN_DIR_RE || "$TARGET" =~ $BUILTIN_SUFFIX_RE ]]; then exit 0; fi
for IGN in ${IGNORES[@]+"${IGNORES[@]}"}; do
  if [[ "$TARGET" =~ $IGN ]]; then exit 0; fi
done
[[ -z "$CTX" || "$CTX" =~ ^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$ ]] || exit 0

NEW=false
[[ -e "$ABS" ]] || NEW=true
if [[ "$NEW" == true && "$MODE" == enforce ]]; then exit 0; fi

# Test touched: pathspecs stay inside the scope so this is fast in a large tree.
export GIT_OPTIONAL_LOCKS=0
SCOPE="$RPATH${CTX:+/$CTX}"
if [[ -n "$CTX" && -n "$SHARED" && "${CTX%%/*}" =~ $SHARED ]]; then SCOPE="$RPATH"; fi
SPECS=()
for PAT in "${TESTS[@]}"; do
  SPECS+=(":(glob)$SCOPE/**/$PAT")
  for TR in $TESTROOTS; do SPECS+=(":(glob)$TR/**/$PAT"); done
done
g() { git -C "$ROOT" "$@" 2>/dev/null; }

OUT="$(g diff --name-only --relative --diff-filter=ACMR HEAD -- "${SPECS[@]}")"
[[ -z "$OUT" ]] || exit 0
if g rev-parse --verify -q "refs/remotes/origin/$BASE_BRANCH" >/dev/null; then
  BASE_REF="origin/$BASE_BRANCH"
elif g rev-parse --verify -q "refs/heads/$BASE_BRANCH" >/dev/null; then
  BASE_REF="$BASE_BRANCH"
else
  exit 0
fi
OUT="$(g diff --name-only --relative --diff-filter=ACMR "$BASE_REF...HEAD" -- "${SPECS[@]}")"
[[ -z "$OUT" ]] || exit 0
OUT="$(g ls-files --others --exclude-standard -- "${SPECS[@]}")"
[[ -z "$OUT" ]] || exit 0

REL="$RPATH/${CTX:+$CTX/}$REST"

if [[ "$MODE" == enforce ]]; then
  echo "spec-first: no test file (${TESTS[*]}) is modified, added or committed ahead of $BASE_REF under $SCOPE/ yet." >&2
  echo "file: $REL" >&2
  echo "Write a failing spec first and run it red, then edit production code.${RULE:+ See $RULE.}" >&2
  echo "New files and test support files are not gated. Pure refactors, logging-only and generated-file edits are exempt but not detectable here: stop and ask the user, do not touch an unrelated spec." >&2
  exit 2
fi

BRANCH="$(g symbolic-ref --short -q HEAD || true)"

NUDGED=false
if [[ "$MODE" == nudge && "$NEW" == false && -n "$SID" ]]; then
  read -r HASH LEN _ <<<"$(printf '%s\n%s\n%s\n%s' "$SID" "${ROOT#"$PROJ_P"/}$RPATH" "$CTX" "$AGENT" | cksum)"
  MARKER_DIR="${TMPDIR:-/tmp}"
  MARKER="${MARKER_DIR%/}/crew-spec-first-nudge-$UID-$HASH-$LEN"
  if [[ "$MARKER_DIR" == /* && ! -e "$MARKER" ]] && (set -C; : >"$MARKER") 2>/dev/null; then NUDGED=true; fi
fi

if [[ -n "${CLAUDE_PLUGIN_DATA:-}" ]]; then
  {
    mkdir -p "$CLAUDE_PLUGIN_DATA"
    jq -nc --arg sid "$SID" --arg tool "$TOOL" --arg branch "$BRANCH" --arg file "$REL" --arg ctx "$CTX" --arg mode "$MODE" --arg project "$PROJ" --argjson new "$NEW" --argjson nudged "$NUDGED" \
      '{ts: (now | floor | todate), session_id: $sid, tool: $tool, branch: $branch, file: $file, context: $ctx, new_file: $new, would_block: ($new | not), mode: $mode, nudged: $nudged, project: $project}' \
      >>"$CLAUDE_PLUGIN_DATA/hook-log.jsonl"
  } 2>/dev/null || true
fi

[[ "$NUDGED" == true ]] || exit 0
jq -nc --arg msg "This edit applied while no spec has been touched under $SCOPE/ in this task, so the failing spec could not come first. The project rule${RULE:+, $RULE,} is to tell the developer in one line what happened, then write the spec before any further edit here, or say why this edit is exempt (refactor, logging-only, generated file) and continue." \
  '{hookSpecificOutput: {hookEventName: "PreToolUse", additionalContext: $msg}}'
exit 0
