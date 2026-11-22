#!/usr/bin/env bash
# PreToolUse hook (matcher: Bash). Blocks a small set of commands that are nearly
# always mistakes and hard to undo (exit 2 + stderr reason), and asks the user when a
# push would land on a protected branch, either explicitly (git push origin main,
# HEAD:main, a lone HEAD as the current branch) or through the branch upstream (a bare git push).
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
# Commands longer than 4096 characters are matched raw, without masking (only their quote characters are
# deleted): bash 3.2 is too slow on them, and raw matching errs toward blocking (a long commit message
# that mentions a dangerous command is a false positive there). A here-string is consumed whole, a <<
# inside (( )) is not a here-document, and a here-document with no terminator line stays code. The
# terminator is the delimiter word after shell quote removal (<<'\EOF' ends on a line \EOF); a word that
# holds $, a backtick or ( is not trusted, so the body stays code. The SQL checks of a long command read
# it raw, so a quote that ends a DELETE is still there.
# git clean with -x or -X (in any option bundle) is denied, whatever else is on the line: -n and --dry-run
# do not exempt it, and docker compose down with -v or --volumes is also matched line by line, as a second
# net for a & that the segment split cuts inside a quoted word. chmod 777 is judged on every chmod in a segment and on every target of each, not only
# the first: it is denied when a target starts with /, ~, $HOME or ${HOME}, so /tmp/build/out and
# ~/project/dist are denied too; a relative target (dist/*, *.sh, ../build) passes.
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
# "confirmProtectedPush": false in the same file drops only the confirm prompts for a push to a
# protected branch (an explicit one and a bare git push through the upstream). Force pushes, +refspec,
# --delete and :branch on a protected branch stay denied, and a push with a force option or --mirror keeps
# the prompt. Any value other than false keeps the prompt.
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
MASK_MAX=4096
case "$((${#CMD} > MASK_MAX))$CMD" in
  1*\\$'\n'*) CMD="$(printf '%s' "$CMD" | tr '\n' '\001' | sed "s/\\\\$(printf '\001')/ /g" | tr '\001' '\n')" ;;
esac

BRANCHES=(main master develop production)
CONFIRM_PUSH=true
PROJ="${CLAUDE_PROJECT_DIR:-}"
[[ -d "$PROJ" ]] || PROJ="$(git -C "${CWD:-.}" rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -n "$PROJ" && -f "$PROJ/.claude/crew.json" ]]; then
  CONFIGURED=()
  while IFS= read -r name; do
    if [[ "$name" =~ ^[A-Za-z0-9._/-]+$ ]]; then CONFIGURED+=("$name"); fi
  done < <(jq -r '(.protectedBranches // empty) | if type == "array" then .[] | strings else empty end' "$PROJ/.claude/crew.json" 2>/dev/null || true)
  if [[ ${#CONFIGURED[@]} -gt 0 ]]; then BRANCHES=("${CONFIGURED[@]}"); fi
  if [[ "$(jq -r 'if .confirmProtectedPush == false then "false" else "true" end' "$PROJ/.claude/crew.json" 2>/dev/null || true)" == false ]]; then CONFIRM_PUSH=false; fi
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
MASK_STOP=$'[\\\\\'"<#;&|\n]'
DQ_RE='^"(([^"\\]|\\.)*)"'
SQ_RE="^'([^']*)'"
HD_RE="^<<(-?)${SP}*((\\\\.|'[^']*'|\"[^\"]*\"|[^][:space:];&|<>()'\"\\\\])+)"
SQL_CLIENTS='psql|pgcli|mysql|mariadb|sqlite3|sqlcmd'
EXEC_NAMES="sh|bash|zsh|dash|ksh|eval|ssh|watch|python3?|node|perl|ruby|docker|kubectl|${SQL_CLIENTS}"
# The name is a command word: bare, or a path that starts at / ./ ../ or ~/ (so --repo acme/docker is not one).
EXEC_RE="[[:space:](\`](${EXEC_NAMES})[[:space:]]|[[:space:](\`](/|\\./|\\.\\./|~/)([^[:space:]]*/)?(${EXEC_NAMES})[[:space:]]"
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

# Shell quote removal on a here-document delimiter word: HDW is the line that ends the body. A backslash
# outside quotes keeps the next character, single quotes keep everything, and in double quotes a backslash
# is removed only before $, a backtick, " or a backslash.
hd_unquote() {
  local LC_ALL=C w="$1" c n i=0 q=""
  HDW=""
  while ((i < ${#w})); do
    c="${w:i:1}"
    if [[ "$q" == s ]]; then
      if [[ "$c" == "'" ]]; then q=""; else HDW+="$c"; fi
    elif [[ "$c" == "'" && -z "$q" ]]; then q=s
    elif [[ "$c" == '"' ]]; then if [[ -z "$q" ]]; then q=d; else q=""; fi
    elif [[ "$c" == '\' ]]; then
      n="${w:i+1:1}"
      if [[ -z "$q" || "$n" == [\$\`\"\\] ]]; then i=$((i + 1)); HDW+="$n"; else HDW+="$c"; fi
    else HDW+="$c"
    fi
    i=$((i + 1))
  done
}

# One pass: rest holds the unread tail and shrinks as tokens are consumed, so no step re-slices the whole string.
# LC_ALL=C makes bash scan bytes: in a UTF-8 locale the slicing below is far from linear.
mask() {
  local LC_ALL=C
  local rest="$1" run body line stripped hd="" hddash=false hdkeep=false out="" seg="" tail arith word found
  while [[ -n "$rest" ]]; do
    run="${rest%%$MASK_STOP*}"
    if [[ -n "$run" ]]; then
      out+="$run"
      seg+="$run"
      rest="${rest:${#run}}"
      continue
    fi
    case "${rest:0:1}" in
      '\')
        if [[ "${rest:1:1}" == $'\n' ]]; then out+=" "; seg+=" "; else out+="${rest:0:2}"; seg+="${rest:0:2}"; fi
        rest="${rest:2}" ;;
      "'")
        if [[ "$rest" =~ $SQ_RE ]]; then
          body="${BASH_REMATCH[1]}"
          rest="${rest:${#BASH_REMATCH[0]}}"
          mask_quoted "$body" sq
        else
          mask_quoted "${rest:1}" sq
          rest=""
        fi ;;
      '"')
        if [[ "$rest" =~ $DQ_RE ]]; then
          body="${BASH_REMATCH[1]}"
          rest="${rest:${#BASH_REMATCH[0]}}"
          mask_quoted "$body" dq
        else
          mask_quoted "${rest:1}" dq
          rest=""
        fi ;;
      '<')
        if [[ "${rest:0:3}" == "<<<" ]]; then
          out+="<<<"
          seg+="<<<"
          rest="${rest:3}"
        elif [[ "${rest:0:2}" == "<<" ]]; then
          arith="${seg#*((}"
          if [[ "$seg" == *"(("* ]]; then
            tail="${arith//[^(]/}"
            arith="${arith//[^)]/}"
            if ((2 + ${#tail} - ${#arith} > 0)); then arith=open; else arith=""; fi
          else
            arith=""
          fi
          if [[ -z "$arith" && "$rest" =~ $HD_RE ]]; then
            word="${BASH_REMATCH[2]}"
            hddash=false
            if [[ -n "${BASH_REMATCH[1]}" ]]; then hddash=true; fi
            hdkeep=false
            if [[ "$word" == *[\$\`]* || "${rest:${#BASH_REMATCH[0]}:1}" == "(" ]]; then hdkeep=true; fi
            hd_unquote "$word"
            hd="$HDW"
            if [[ " $seg " =~ $EXEC_RE ]]; then hdkeep=true; fi
            line="${rest%%$'\n'*}"
            if [[ "$line" == *"|"* && " ${line#*|} " =~ $EXEC_RE ]]; then hdkeep=true; fi
          fi
          out+="<<"
          seg+="<<"
          rest="${rest:2}"
        else
          out+="<"
          seg+="<"
          rest="${rest:1}"
        fi ;;
      '#')
        case "${out: -1}" in
          "" | " " | $'\t' | $'\n' | ";" | "&" | "|" | "(")
            line="${rest%%$'\n'*}"
            rest="${rest:${#line}}" ;;
          *)
            out+="#"
            seg+="#"
            rest="${rest:1}" ;;
        esac ;;
      $'\n')
        out+=$'\n'
        seg=""
        rest="${rest:1}"
        if [[ -n "$hd" && "$hdkeep" == true ]]; then
          hd=""
        elif [[ -n "$hd" ]]; then
          tail="$rest"
          found=""
          while [[ -n "$rest" ]]; do
            line="${rest%%$'\n'*}"
            if [[ "$rest" == *$'\n'* ]]; then rest="${rest#*$'\n'}"; else rest=""; fi
            stripped="$line"
            if [[ "$hddash" == true ]]; then stripped="${line#"${line%%[!$'\t']*}"}"; fi
            if [[ "$stripped" == "$hd" ]]; then found=yes; break; fi
          done
          [[ -n "$found" ]] || rest="$tail"
          hd=""
        fi ;;
      *)
        out+="${rest:0:1}"
        seg=""
        rest="${rest:1}" ;;
    esac
  done
  MASKED="$out"
}

# On macOS bash 3.2, [[ =~ ]] and ${var//pat/rep} hang on strings of several KB, so commands over MASK_MAX characters use grep and tr.
case "$CMD" in
  *\\* | *\'* | *\"* | *\<* | *\#*)
    if ((${#CMD} > MASK_MAX)); then MASKED="$(printf '%s' "$CMD" | tr -d "'\"")"$'\n'"$CMD"; else mask "$CMD"; fi ;;
  *) MASKED="$CMD" ;;
esac

# Match in bash, line by line as grep did, so ^, $ and [^...] classes never span a newline.
# A long string goes to grep instead: bash's regex engine is far slower than grep's on it.
has() {
  local line
  if ((${#MASKED} > MASK_MAX)); then grep -qE -- "$1" <<<"$MASKED"; return; fi
  if [[ "$MASKED" != *$'\n'* ]]; then [[ "$MASKED" =~ $1 ]]; return; fi
  while IFS= read -r line; do
    if [[ "$line" =~ $1 ]]; then return 0; fi
  done <<< "$MASKED"
  return 1
}
hasi() {
  local rc=0
  if ((${#MASKED} > MASK_MAX)); then grep -qiE -- "$1" <<<"$MASKED"; return; fi
  shopt -s nocasematch
  has "$1" || rc=$?
  shopt -u nocasematch
  return $rc
}
deny_if() { if has "$2"; then deny "$1"; fi; }
denyi_if() { if hasi "$2"; then deny "$1"; fi; }

# --- destructive filesystem ---
PATH_END="(${SP}|\$|\\*|/\\*?(${SP}|\$|[)\`])|[)\`])"
RM_TARGET="(\\./)*(/|~/?|\\\$HOME|\\\$\\{HOME\\}|\\.git)${PATH_END}"

# chmod 777 is judged on every target. A target is unsafe when it starts with /, ~, $HOME or ${HOME}.
chmod_target_unsafe() {
  case "$1" in
    /* | "~"* | '$HOME'* | '${HOME}'*) return 0 ;;
  esac
  return 1
}
# Succeeds when the chmod arguments $1 set mode 777 and any target is unsafe; redirections are skipped.
chmod_777_unsafe() {
  local w ws skip=false moded=false
  read -ra ws <<< "$1"
  for w in ${ws[@]+"${ws[@]}"}; do
    w="${w//[)\`]/}"
    [[ -n "$w" ]] || continue
    if $skip; then skip=false; continue; fi
    if [[ "$w" =~ ^[0-9]*(\>\>?|\<)(.*)$ ]]; then
      [[ -n "${BASH_REMATCH[2]}" ]] || skip=true
      continue
    fi
    [[ "$w" != -* ]] || continue
    if ! $moded; then
      moded=true
      [[ "$w" =~ ^0?777$ ]] || return 1
      continue
    fi
    if chmod_target_unsafe "$w"; then return 0; fi
  done
  return 1
}
# Succeeds when any chmod word of the segment $1 starts an invocation that chmod_777_unsafe denies (a
# chmod after an assignment or sudo, FOO=chmod sudo chmod 777 /etc, is a second one).
chmod_any_unsafe() {
  local rest="$1" start="^[[:space:])\`]"
  while [[ "$rest" == *chmod* ]]; do
    rest="${rest#*chmod}"
    if [[ -z "$rest" || "$rest" =~ $start ]] && chmod_777_unsafe "$rest"; then return 0; fi
  done
  return 1
}

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
# ${//} is quadratic in bash 3.2 (about 0.3 s at 1.7 KB), so a string over 256 characters is split by tr.
if ((${#MASKED} > 256)); then
  SEGMENTS="$(printf '%s\n' "$MASKED" | tr ';&|' '\n\n\n')"
else
  SEGMENTS="${MASKED//[;&|]/$'\n'}"
fi
# A segment may start with a keyword, sudo (and its options), env or assignments before git.
PUSH_LEAD="^${SP}*((if|then|do|else|elif|while|until|!|[{]|env|[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*|sudo(${SP}+(-[ugphCDRTUrt]${SP}+[^[:space:]]+|-[^[:space:]]+))*)${SP}+)*"
PUSH_END='([[:space:])`].*)?$'
BARE_PUSH=false
BARE_STRONG=false
# Succeeds when the push arguments $1 name no refspec: options, then at most origin or upstream; redirections are skipped.
bare_push() {
  local w ws skip=false remote=false
  read -ra ws <<< "$1"
  for w in ${ws[@]+"${ws[@]}"}; do
    w="${w//[)\`]/}"
    [[ -n "$w" ]] || continue
    if $skip; then skip=false; continue; fi
    if [[ "$w" =~ ^[0-9]*(\>\>?|\<)(.*)$ ]]; then
      [[ -n "${BASH_REMATCH[2]}" ]] || skip=true
      continue
    fi
    if [[ "$w" =~ ^-[-a-zA-Z=]+$ ]]; then
      if $remote; then return 1; fi
      continue
    fi
    if ! $remote && [[ "$w" =~ ^(origin|upstream)$ ]]; then remote=true; continue; fi
    return 1
  done
  return 0
}
COMPOSE_RE="docker(${SP}+|-)compose(${SP}|\$|[)\`])(.*)\$"
# Succeeds when the compose arguments $1 are a down with -v or --volumes among its own options. The
# subcommand is the first word that names one, after the global options and the values of those that take one.
compose_down_volumes() {
  local w ws skip=false sub=""
  read -ra ws <<< "${1//[<>]/ }"
  for w in ${ws[@]+"${ws[@]}"}; do
    w="${w//[)\`]/}"
    if $skip; then skip=false; continue; fi
    if [[ -z "$sub" ]]; then
      case "$w" in
        -f | --file | -p | --project-name | --project-directory | --profile | --env-file | --ansi | --parallel | --progress | -H | --host | --context) skip=true ;;
        down) sub=down ;;
        attach | build | commit | config | cp | create | events | exec | export | images | kill | logs | ls | pause | port | ps | publish | pull | push | restart | rm | run | scale | start | stats | stop | top | unpause | up | version | wait | watch) return 1 ;;
      esac
    else
      [[ "$w" == --volumes || "$w" == --volumes=* || "$w" =~ ^-[a-zA-Z]*v ]] && return 0
    fi
  done
  return 1
}
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
  if [[ "$seg" == *compose* && "$seg" =~ $COMPOSE_RE ]] && compose_down_volumes "${BASH_REMATCH[$((${#BASH_REMATCH[@]} - 1))]}"; then
    deny "docker compose down -v deletes volumes"
  fi
  case "$seg" in
    *rm* | *push* | *aws* | *clean* | *chmod*) ;;
    *) continue ;;
  esac
  seg_has() { [[ "$seg" =~ $1 ]]; }
  if [[ "$seg" == *chmod* ]] && chmod_any_unsafe "$seg"; then
    deny "chmod 777 on HOME, / or an absolute path"
  fi
  if [[ "$seg" == *clean* ]] && seg_has "${GBEFORE}clean[^;&|]*${SP}-[a-zA-Z]*[xX]"; then
    deny "git clean -x removes ignored files (.env, build output)"
  fi
  if seg_has "(^|[^A-Za-z0-9_-])rm${SP}+(-[A-Za-z]+|--[a-z-]*)(${SP}+[^[:space:]]+)*${SP}+${RM_TARGET}"; then
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
  seg_has "${GBEFORE}push(${SP}|\$|[)\`])" || continue
  [[ "$seg" =~ ${GAFTER}push${PUSH_END} ]] || continue
  ARGS="${BASH_REMATCH[$((${#BASH_REMATCH[@]} - 1))]}"
  if [[ "$seg" =~ ${PUSH_LEAD}([A-Za-z_][A-Za-z0-9_]*=)?[\$\(]*${SP}*([^[:space:]]*/)?${GAFTER}push${PUSH_END} ]] && bare_push "${BASH_REMATCH[$((${#BASH_REMATCH[@]} - 1))]}"; then BARE_PUSH=true; fi
  HEAD_RE='^(.*[[:space:]+])HEAD(([[:space:])`<>].*)?)$'
  if [[ "$ARGS" =~ $HEAD_RE ]]; then
    CUR="$(git -C "${CWD:-.}" symbolic-ref --short -q HEAD 2>/dev/null || true)"
    [[ -z "$CUR" ]] || ARGS="${BASH_REMATCH[1]}$CUR${BASH_REMATCH[2]}"
  fi
  args_has() { [[ "$ARGS" =~ $1 ]]; }
  STRONG=false
  if args_has "(^|${SP})(--force[a-z-]*(=[^ ]*)?|-[a-zA-Z]*f[a-zA-Z]*|--mirror)(${SP}|\$|[)\`<>])"; then STRONG=true; fi
  if $STRONG && [[ "$BARE_PUSH" == true ]]; then BARE_STRONG=true; fi
  FORCE="(^|${SP})(--force[a-z-]*(=[^ ]*)?|-[a-zA-Z]*f[a-zA-Z]*)(${SP}|\$)"
  PEND="(${SP}|\$|[)\`<>])"
  ON_PROTECTED="(^|${SP}|[:+])(refs/heads/)?${PROTECTED}${PEND}"
  if args_has "$FORCE" && args_has "$ON_PROTECTED"; then deny "git push --force to a protected branch"; fi
  if args_has "(^|${SP})\\+([^[:space:]:]+:)?(refs/heads/)?${PROTECTED}${PEND}"; then deny "git push +<refspec> forces a protected branch"; fi
  if args_has "(--delete|${SP}-d${SP})" && args_has "$ON_PROTECTED"; then deny "git push --delete on a protected branch"; fi
  if args_has "${SP}:${PROTECTED}${PEND}"; then deny "git push :<branch> deletes a protected branch"; fi
  if [[ "$CONFIRM_PUSH" == true || "$STRONG" == true ]] && args_has "$ON_PROTECTED"; then ASK_MSG="This push targets a protected branch. Confirm pushing to it."; fi
done <<< "$SEGMENTS"
# Second net: main's line-level patterns, for text the segment split cuts (a & inside a quoted or escaped word).
deny_if "git clean -x removes ignored files (.env, build output)" "${GBEFORE}clean[^;&|]*${SP}-[a-zA-Z]*[xX]"
deny_if "docker compose down -v deletes volumes" "docker${SP}+compose${SP}+down[^;&|]*(${SP}-[a-zA-Z]*v|--volumes)"
deny_if "git reset --hard on a protected remote" "${GBEFORE}reset${SP}+--hard${SP}+(origin|upstream)/${PROTECTED}([^A-Za-z0-9_-]|\$)"
deny_if "git branch -D on a protected branch"    "${GBEFORE}branch${SP}+(-D|--delete${SP}+--force|--force${SP}+--delete|-d${SP}+-f|-f${SP}+-d)${SP}+([^[:space:];&|]+[[:blank:]]+)*${PROTECTED}([^A-Za-z0-9_-]|\$)"

# --- containers: local database volumes ---
deny_if "docker prune of all images or volumes"   "docker${SP}+(system${SP}+prune[^;&|]*(${SP}-[a-zA-Z]*a|--all|--volumes)|volume${SP}+prune)"

# --- SQL: only when a SQL client is actually invoked (so commit messages that merely mention it pass) ---
# A command too long to be masked is checked raw here: its quote characters end the DELETE pattern.
MASKED_KEPT="$MASKED"
if ((${#CMD} > MASK_MAX)); then MASKED="$CMD"; fi
if hasi "(^|[^a-z])(${SQL_CLIENTS})([^a-z]|\$)"; then
  denyi_if "SQL DROP DATABASE/TABLE/SCHEMA" "drop${SP}+(database|table|schema)"
  denyi_if "SQL TRUNCATE"                   "truncate${SP}+(table${SP}+)?[a-z_\"]"
  denyi_if "SQL DELETE without WHERE"       "delete${SP}+from${SP}+[a-z_.\"]+${SP}*(;|\"|'|\$)"
fi
MASKED="$MASKED_KEPT"

# --- unvetted remote scripts ---
PIPED="$MASKED"
if [[ "$MASKED" == *"|"$'\n'* ]]; then
  PIPED="$(printf '%s' "$MASKED" | tr '\n' '\001' | sed "s/|$(printf '\001')/| /g" | tr '\001' '\n')"
fi
MASKED="$PIPED"
deny_if "piping curl/wget into a shell" "(curl|wget)${SP}+[^|]+\\|${SP}*(sudo(${SP}+-[^[:space:]]+)*${SP}+)?([^[:space:]]*/)?(sh|bash|zsh)(${SP}|\$|[)\`])"

# --- bare `git push` whose upstream is a protected branch (indirect push to main) ---
if $BARE_PUSH && [[ "$CONFIRM_PUSH" == true || "$BARE_STRONG" == true ]]; then
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
