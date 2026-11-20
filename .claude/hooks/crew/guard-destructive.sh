#!/usr/bin/env bash
# PreToolUse hook (matcher: Bash). Blocks a small set of commands that are nearly
# always mistakes and hard to undo (exit 2 + stderr reason), and asks the user when a
# push would land on a protected branch, either explicitly (git push origin main,
# HEAD:main) or through the branch upstream (a bare git push).
#
# Philosophy: only block what is (a) nearly always wrong and (b) hard or impossible to
# undo; everything reversible is allowed. A regex over the command string is a safety
# net, not a sandbox: pair it with permissions.deny/ask rules in settings.json.
#
# What counts as "the command being run": the command string is first rewritten (mask below)
# so that text which is only an argument no longer looks like a command. Quoted strings that
# contain whitespace are replaced by "" (commit messages, PR bodies, echo text), quotes around
# a single word are removed (rm -rf "$HOME" is seen as rm -rf $HOME), here-document bodies and
# # comments are dropped. A quoted string is kept as code, so that what it runs is still
# checked, when it contains $( or a backtick, or when the command so far involves a shell,
# ssh, eval, watch, docker, kubectl, an interpreter or a SQL client (bash -c "...", ssh host
# "...", psql -c "..."). Then each ;, & or | separated segment is judged on its own.
# A here-document body is dropped when it feeds something like cat or git commit -F -, and kept
# when the command reading it is one of the same interpreters (psql <<'SQL', bash <<EOF, ssh host <<EOF).
# Commands longer than 4096 characters are matched raw, without masking: the scanner is quadratic,
# and raw matching errs toward blocking (a long commit message that mentions a dangerous command is
# a false positive there).
# Known limits, all deliberate for a regex-level net:
#   - Unquoted prose is still read as a command: echo rm -rf ~ is denied.
#   - Code that is not visible in the string is not seen: scripts run from a file, aliases,
#     variables (rm -rf $DIR), echo "rm -rf ~" | sh.
#   - A quoted string passed to a command that runs it but is not in the list above is masked
#     (for example find -exec sh -c is covered by sh, but make -C x "rm -rf ~" is not).
#   - A false positive remains when such a list word appears earlier in a command that carries a
#     message, for example gh pr create --title "x" docker --body "rm -rf ~".
#   - git -C <dir> is recognized, but the upstream of a bare git push is read in the session cwd,
#     not in <dir>.
#   - git push --all and --mirror are not looked at.
#   - AWS endpoints held in a variable (--endpoint-url $URL, AWS_ENDPOINT_URL=$URL) count as remote, so
#     the delete is denied; a local endpoint set in a file, a profile or a non-exported variable is not
#     seen either, and neither is an export on a later line of a script run from a file.
#   - An export inside a child shell or subshell (bash -c "export ...", ( export ... )) is still read
#     as applying to later segments.
#
# Protected branches: main, master, develop and production by default. A project overrides the
# list with "protectedBranches" in <project>/.claude/crew.json (see crew.schema.json). A missing,
# malformed or empty list, or entries that are not plain branch names, fall back to the default:
# this is a safety net, so a broken config must not switch it off.
#
# PATH: a Desktop-launched session may have a PATH without /opt/homebrew/bin or /usr/local/bin,
# where jq lives on a Mac, and a missing jq blocks every Bash call (the hook cannot check
# the command, so it fails closed). The usual install locations are appended to PATH (after
# the user's own entries). CREW_FALLBACK_PATH replaces that
# list (used by the tests; an empty value appends nothing).
#
# Every pattern has a case in tests/guard-cases.jsonl. After any edit run:
#   hooks/tests/run-all.sh

set -euo pipefail

FALLBACK_PATH="${CREW_FALLBACK_PATH-/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin}"
[[ -z "$FALLBACK_PATH" ]] || PATH="${PATH:+$PATH:}$FALLBACK_PATH"

if ! command -v jq >/dev/null 2>&1; then
  echo "crew guard: jq not found, so every Bash command is blocked until it is on PATH. Install jq outside this session (brew install jq, apt-get install jq) or add it to the image or setup script, then retry." >&2
  exit 2
fi

# One jq call: first line is the cwd (newlines flattened), the rest is the command.
JQ_RC=0
PARSED="$(jq -r '((.cwd // "") | tostring | gsub("\n"; " ")), (.tool_input.command // empty)' 2>/dev/null)" || JQ_RC=$?
if ((JQ_RC != 0)); then
  echo "crew guard: jq failed (exit $JQ_RC), so the command cannot be checked and is blocked." >&2
  exit 2
fi
CWD="${PARSED%%$'\n'*}"
if [[ "$PARSED" == *$'\n'* ]]; then CMD="${PARSED#*$'\n'}"; else CMD=""; fi
[[ -z "$CMD" ]] && exit 0
# A backslash-newline continuation is one command. The mask joins the lines itself (a comment or a
# quoted heredoc line ending in a backslash must not swallow the next line); only a command too long
# to be masked is joined here, so a split delete is seen.
BSNL=$'\\\n'
case "$((${#CMD} > 4096))$CMD" in
  1*\\$'\n'*) CMD="$(printf '%s' "$CMD" | tr '\n' '\001' | sed "s/\\\\$(printf '\001')/ /g" | tr '\001' '\n')" ;;
esac

BRANCHES=(main master develop production)
PROJ="${CLAUDE_PROJECT_DIR:-}"
[[ -d "$PROJ" ]] || PROJ="$(git -C "${CWD:-.}" rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -n "$PROJ" && -f "$PROJ/.claude/crew.json" ]]; then
  CONFIGURED=()
  while IFS= read -r name; do
    if [[ "$name" =~ ^[A-Za-z0-9._/-]+$ ]]; then CONFIGURED+=("$name"); fi
  done < <(jq -r '(.protectedBranches // empty) | if type == "array" then .[] | strings else empty end' "$PROJ/.claude/crew.json" 2>/dev/null || true)
  if [[ ${#CONFIGURED[@]} -gt 0 ]]; then BRANCHES=("${CONFIGURED[@]}"); fi
fi
PROTECTED=""
for name in "${BRANCHES[@]}"; do
  PROTECTED="${PROTECTED:+$PROTECTED|}${name//./\\.}"
done
PROTECTED="($PROTECTED)"
SP='[[:space:]]'

# git global options that may sit between git and the subcommand: -C <dir>, -c k=v, --git-dir=..., --no-pager, -p.
GOPTS="(${SP}+(-[Cc]${SP}+[^[:space:]]+|--(git-dir|work-tree|namespace|exec-path|super-prefix|config-env)(=|${SP}+)[^[:space:]]+|--[a-z][a-z-]*|-[pP]))*"
GBEFORE="(^|[^A-Za-z0-9_.-])git${GOPTS}${SP}+"
GAFTER="git${GOPTS}${SP}+"

deny() {
  echo "guard-destructive blocked: $1" >&2
  echo "command: $CMD" >&2
  echo "If you really mean it, run it outside Claude Code or ask the user to confirm." >&2
  exit 2
}

ask() {
  jq -n --arg reason "$1" \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "ask", permissionDecisionReason: $reason}}'
  exit 0
}

# --- mask: sets MASKED to CMD with argument text neutralized (see the header) ---
RUN_RE=$'^[^\\\'"<#;&|\n]+'
DQ_RE='^"(([^"\\]|\\.)*)"'
SQ_RE="^'([^']*)'"
HD_RE='^<<-?[[:space:]]*["'"'"']?([A-Za-z0-9_]+)'
EXEC_RE='[[:space:]](sh|bash|zsh|dash|ksh|eval|ssh|watch|python3?|node|perl|ruby|docker|kubectl|psql|pgcli|mysql|mariadb|sqlite3|sqlcmd)[[:space:]]'
MASKED=""

mask_quoted() {
  local body="$1" kind="$2" rep
  if [[ "$kind" == dq && ( "$body" == *'$('* || "$body" == *'`'* ) ]]; then
    mask "$body"
    rep="$MASKED"
  elif [[ "$body" != *[[:space:]]* ]]; then
    rep="$body"
  elif [[ " $seg " =~ $EXEC_RE ]]; then
    rep=${body//"$BSNL"/ }
  else
    rep='""'
  fi
  out+="$rep"
  seg+="$rep"
}

mask() {
  local s="$1" n="${#1}" i=0 c rest run body line stripped hd="" hdkeep=false out="" seg=""
  while ((i < n)); do
    rest="${s:i}"
    if [[ "$rest" =~ $RUN_RE ]]; then
      run="${BASH_REMATCH[0]}"
      out+="$run"
      seg+="$run"
      i=$((i + ${#run}))
      continue
    fi
    c="${rest:0:1}"
    case "$c" in
      '\')
        if [[ "${rest:1:1}" == $'\n' ]]; then out+=" "; seg+=" "; else out+="${rest:0:2}"; seg+="${rest:0:2}"; fi
        i=$((i + 2)) ;;
      "'")
        if [[ "$rest" =~ $SQ_RE ]]; then
          body="${BASH_REMATCH[1]}"
          i=$((i + ${#BASH_REMATCH[0]}))
          mask_quoted "$body" sq
        else
          mask_quoted "${rest:1}" sq
          i=$n
        fi ;;
      '"')
        if [[ "$rest" =~ $DQ_RE ]]; then
          body="${BASH_REMATCH[1]}"
          i=$((i + ${#BASH_REMATCH[0]}))
          mask_quoted "$body" dq
        else
          mask_quoted "${rest:1}" dq
          i=$n
        fi ;;
      '<')
        if [[ "${rest:0:2}" == "<<" && "${rest:2:1}" != "<" ]]; then
          if [[ "$rest" =~ $HD_RE ]]; then
            hd="${BASH_REMATCH[1]}"
            hdkeep=false
            if [[ " $seg " =~ $EXEC_RE ]]; then hdkeep=true; fi
          fi
          out+="<<"
          seg+="<<"
          i=$((i + 2))
        else
          out+="<"
          seg+="<"
          i=$((i + 1))
        fi ;;
      '#')
        case "${out: -1}" in
          "" | " " | $'\t' | $'\n' | ";" | "&" | "|" | "(")
            line="${rest%%$'\n'*}"
            i=$((i + ${#line})) ;;
          *)
            out+="#"
            seg+="#"
            i=$((i + 1)) ;;
        esac ;;
      $'\n')
        out+=$'\n'
        seg=""
        i=$((i + 1))
        if [[ -n "$hd" && "$hdkeep" == true ]]; then
          hd=""
        elif [[ -n "$hd" ]]; then
          rest="${s:i}"
          while [[ -n "$rest" ]]; do
            line="${rest%%$'\n'*}"
            if [[ "$rest" == *$'\n'* ]]; then rest="${rest#*$'\n'}"; else rest=""; fi
            stripped="${line#"${line%%[![:space:]]*}"}"
            if [[ "$stripped" == "$hd" ]]; then break; fi
          done
          i=$((n - ${#rest}))
          hd=""
        fi ;;
      *)
        out+="$c"
        seg=""
        i=$((i + 1)) ;;
    esac
  done
  MASKED="$out"
}

# On macOS bash 3.2, [[ =~ ]] and ${var//pat/rep} hang on strings of several KB, so commands over MASK_MAX characters use grep and tr.
MASK_MAX=4096
case "$CMD" in
  *\\* | *\'* | *\"* | *\<* | *\#*)
    if ((${#CMD} > MASK_MAX)); then MASKED="$CMD"; else mask "$CMD"; fi ;;
  *) MASKED="$CMD" ;;
esac

# Match in bash, line by line as grep did, so ^, $ and [^...] classes never span a newline.
# A long string goes to grep instead: bash's regex engine is far slower than grep's on it.
has() {
  local line
  if ((${#MASKED} > MASK_MAX)); then printf '%s' "$MASKED" | grep -qE -- "$1"; return; fi
  if [[ "$MASKED" != *$'\n'* ]]; then [[ "$MASKED" =~ $1 ]]; return; fi
  while IFS= read -r line; do
    if [[ "$line" =~ $1 ]]; then return 0; fi
  done <<< "$MASKED"
  return 1
}
hasi() {
  local rc=0
  if ((${#MASKED} > MASK_MAX)); then printf '%s' "$MASKED" | grep -qiE -- "$1"; return; fi
  shopt -s nocasematch
  has "$1" || rc=$?
  shopt -u nocasematch
  return $rc
}
deny_if() { if has "$2"; then deny "$1"; fi; }
denyi_if() { if hasi "$2"; then deny "$1"; fi; }

# --- destructive filesystem ---
RM_TARGET="(/|~/?|\\\$HOME|\\\$\\{HOME\\}|\\.git)(${SP}|\$|\\*|/\$|[)\`])"
deny_if "chmod 777 on HOME or /"      "chmod${SP}+(-R${SP}+)?0?777${SP}+(/|~/?|\\\$HOME)"

# --- git: history rewrite or deletion on a protected branch ---
# Judge each segment on its own, so a --force or a branch name elsewhere on the line
# (git worktree remove --force, gh pr create --base main) is not read as part of the push.
ASK_MSG=""
# Cloud: irreversible deletes. A segment is exempt only when it targets a local endpoint itself
# (--endpoint-url, or AWS_ENDPOINT_URL[_<SERVICE>]= on the same segment) or an earlier segment
# exported AWS_ENDPOINT_URL[_<SERVICE>]. Global options may sit before and after the service.
# A --endpoint-url flag decides alone; without one the last assignment wins (an unset clears it) and
# AWS_ENDPOINT_URL_<SERVICE> outranks AWS_ENDPOINT_URL.
LOCAL_HOST="https?://(([A-Za-z0-9.-]+\\.)?localhost\\.localstack\\.cloud|localhost|127\\.0\\.0\\.1|0\\.0\\.0\\.0|\\[::1\\]|host\\.docker\\.internal|localstack(-[A-Za-z0-9_-]+)?)([:/]|${SP}|[;&|)]|\$)"
AWS_OPTS="(${SP}+--[^[:space:]]+(${SP}+[^-[:space:]][^[:space:]]*)?)*"
AWS_DELETES=("s3:(rm[^;&|]*--recursive|rb[^;&|]*--force)" "rds:delete-db" "ec2:terminate-instances" "dynamodb:delete-table" "cloudformation:delete-stack")
AWS_EXPORTS=""
# Endpoint variables of a segment as " NAME=value" words (a word "NAME=" is an unset).
env_words() {
  local w ws
  ET=""
  read -ra ws <<< "$1"
  for w in ${ws[@]+"${ws[@]}"}; do
    if [[ "$w" =~ ^AWS_ENDPOINT_URL(_[A-Za-z0-9]+)?= ]]; then ET+=" $w"; fi
  done
}
# The last word for variable $2 in the words $1 wins; EV is its value ("" when unset or absent).
env_value() {
  local w ws
  EV=""
  read -ra ws <<< "$1"
  for w in ${ws[@]+"${ws[@]}"}; do
    if [[ "${w%%=*}" == "$2" ]]; then EV="${w#*=}"; fi
  done
}
# ${//} is quadratic in bash 3.2, so a long string is split by tr.
if ((${#MASKED} > MASK_MAX)); then
  SEGMENTS="$(printf '%s\n' "$MASKED" | tr ';&|' '\n\n\n')"
else
  SEGMENTS="${MASKED//[;&|]/$'\n'}"
fi
while IFS= read -r seg; do
  if [[ "$seg" == *export* && "$seg" =~ ^${SP}*export${SP} ]]; then
    env_words "$seg"
    AWS_EXPORTS+="$ET"
  elif [[ "$seg" == *unset* && "$seg" =~ ^${SP}*unset${SP} ]]; then
    read -ra uw <<< "$seg"
    for w in ${uw[@]+"${uw[@]}"}; do
      if [[ "$w" =~ ^AWS_ENDPOINT_URL(_[A-Za-z0-9]+)?$ ]]; then AWS_EXPORTS+=" $w="; fi
    done
  fi
  case "$seg" in
    *rm* | *push* | *aws*) ;;
    *) continue ;;
  esac
  seg_has() { [[ "$seg" =~ $1 ]]; }
  if seg_has "(^|[^A-Za-z0-9_-])rm(${SP}+(-[A-Za-z]+|--[a-z-]*))+${SP}+${RM_TARGET}"; then
    deny "rm -rf on HOME, /, or .git"
  fi
  for del in "${AWS_DELETES[@]}"; do
    svc="${del%%:*}"
    seg_has "aws${AWS_OPTS}${SP}+${svc}${AWS_OPTS}${SP}+${del#*:}" || continue
    flag_any="(^|${SP})--endpoint-url(${SP}|=|\$)"
    flag_re="(^|${SP})--endpoint-url(${SP}+|=)${LOCAL_HOST}"
    env_words "$seg"
    shopt -s nocasematch
    local_ok=false
    if [[ "$seg" =~ $flag_any ]]; then
      if [[ "$seg" =~ $flag_re ]]; then local_ok=true; fi
    else
      env_value "$AWS_EXPORTS$ET" "AWS_ENDPOINT_URL_${svc}"
      if [[ -z "$EV" ]]; then env_value "$AWS_EXPORTS$ET" AWS_ENDPOINT_URL; fi
      if [[ -n "$EV" && "$EV" =~ ^${LOCAL_HOST} ]]; then local_ok=true; fi
    fi
    shopt -u nocasematch
    [[ "$local_ok" == true ]] || deny "irreversible AWS delete"
  done
  seg_has "${GBEFORE}push(${SP}|\$)" || continue
  [[ "$seg" =~ ${GAFTER}push(${SP}.*)?$ ]] || continue
  ARGS="${BASH_REMATCH[$((${#BASH_REMATCH[@]} - 1))]}"
  args_has() { [[ "$ARGS" =~ $1 ]]; }
  FORCE="(^|${SP})(--force[a-z-]*(=[^ ]*)?|-[a-zA-Z]*f[a-zA-Z]*)(${SP}|\$)"
  PEND="(${SP}|\$|[)\`])"
  ON_PROTECTED="(^|${SP}|[:+])(refs/heads/)?${PROTECTED}${PEND}"
  if args_has "$FORCE" && args_has "$ON_PROTECTED"; then deny "git push --force to a protected branch"; fi
  if args_has "(^|${SP})\\+(refs/heads/|HEAD:)?${PROTECTED}${PEND}"; then deny "git push +<refspec> forces a protected branch"; fi
  if args_has "(--delete|${SP}-d${SP})" && args_has "$ON_PROTECTED"; then deny "git push --delete on a protected branch"; fi
  if args_has "${SP}:${PROTECTED}${PEND}"; then deny "git push :<branch> deletes a protected branch"; fi
  if args_has "$ON_PROTECTED"; then ASK_MSG="This push targets a protected branch. Confirm pushing to it."; fi
done <<< "$SEGMENTS"
deny_if "git reset --hard on a protected remote" "${GBEFORE}reset${SP}+--hard${SP}+(origin|upstream)/${PROTECTED}([^A-Za-z0-9_]|\$)"
deny_if "git branch -D on a protected branch"    "${GBEFORE}branch${SP}+(-D|--delete${SP}+--force|--force${SP}+--delete|-d${SP}+-f|-f${SP}+-d)${SP}+${PROTECTED}([^A-Za-z0-9_]|\$)"
deny_if "git clean -x removes ignored files (.env, build output)" "${GBEFORE}clean[^;&|]*${SP}-[a-zA-Z]*[xX]"

# --- containers: local database volumes ---
deny_if "docker prune of all images or volumes"   "docker${SP}+(system${SP}+prune[^;&|]*(${SP}-[a-zA-Z]*a|--all|--volumes)|volume${SP}+prune)"
deny_if "docker compose down -v deletes volumes"  "docker${SP}+compose${SP}+down[^;&|]*(${SP}-[a-zA-Z]*v|--volumes)"

# --- SQL: only when a SQL client is actually invoked (so commit messages that merely mention it pass) ---
if hasi "(^|[^a-z])(psql|pgcli|mysql|mariadb|sqlite3|sqlcmd)([^a-z]|\$)"; then
  denyi_if "SQL DROP DATABASE/TABLE/SCHEMA" "drop${SP}+(database|table|schema)"
  denyi_if "SQL TRUNCATE"                   "truncate${SP}+(table${SP}+)?[a-z_\"]"
  denyi_if "SQL DELETE without WHERE"       "delete${SP}+from${SP}+[a-z_.\"]+${SP}*(;|\"|'|\$)"
fi

# --- unvetted remote scripts ---
deny_if "piping curl/wget into a shell" "(curl|wget)${SP}+[^|]+\\|${SP}*(sudo${SP}+)?(sh|bash|zsh)(${SP}|\$)"

# --- bare `git push` whose upstream is a protected branch (indirect push to main) ---
if has "(^|[;&|]${SP}*)(env${SP}+)?([A-Za-z_][A-Za-z0-9_]*=[^[:space:];&|]*${SP}+)*${GAFTER}push(${SP}+-[-a-zA-Z=]+)*(${SP}+(origin|upstream))?${SP}*(\$|[;&|])"; then
  UPSTREAM="$(git -C "${CWD:-.}" rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)"
  for name in "${BRANCHES[@]}"; do
    case "$UPSTREAM" in
      */"$name")
        ask "This push goes to $UPSTREAM through the branch upstream. Confirm pushing to a protected branch." ;;
    esac
  done
fi

[[ -z "$ASK_MSG" ]] || ask "$ASK_MSG"
exit 0
