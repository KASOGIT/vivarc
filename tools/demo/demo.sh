#!/bin/sh
# Records the README demo in a throwaway Vivaldi profile (macOS). Vivarc must already be applied to Vivaldi
# (./vivarc.py apply). Your own profiles are never touched: the demo runs a second Vivaldi with its own --user-data-dir.
#
#   tools/demo/demo.sh setup     fresh profile: Vivarc shortcuts, English UI, spaces, pins and tabs
#   tools/demo/demo.sh launch    start the demo Vivaldi again (after a reboot or `stop`)
#   tools/demo/demo.sh reset     back to the storyboard's start state
#   tools/demo/demo.sh rehearse  reset, then play the storyboard without filming
#   tools/demo/demo.sh record    reset, then film the storyboard (hands off the mouse and keyboard meanwhile)
#   tools/demo/demo.sh encode    take.mov -> demo.gif (1280 px, 15 fps) and demo.mp4 (Retina)
#   tools/demo/demo.sh stop | clean
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
DIR=${DEMO_DIR:-$HOME/.cache/vivarc-demo}
PROFILE=$DIR/profile
PORT=${DEMO_PORT:-9335}
export DEMO_PORT=$PORT DEMO_INPUT=$DIR/input
X=100 Y=80 W=1280 H=800

pid() { pgrep -f "MacOS/Vivaldi --user-data-dir=$PROFILE" || true; }
cdp() { node "$HERE/cdp.mjs" "$@"; }

launch() {
  [ -n "$(pid)" ] && return
  open -n -a Vivaldi --args --user-data-dir="$PROFILE" --remote-debugging-port="$PORT" --no-first-run --lang=en-US \
    --window-size=$W,$H --window-position=$X,$Y
  i=0
  until curl -s "localhost:$PORT/json/list" | grep -q /window.html; do
    i=$((i + 1)); [ $i -gt 30 ] && { echo "demo Vivaldi did not start" >&2; exit 1; }
    sleep 1
  done
  sleep 3
}

stop() {
  p=$(pid); [ -z "$p" ] && return
  kill -TERM "$p"
  while kill -0 "$p" 2>/dev/null; do sleep 0.5; done
}

front() {
  osascript -e "tell application \"System Events\" to set frontmost of (first process whose unix id is $(pid)) to true"
  sleep 0.5
}

build_input() {
  [ "$DIR/input" -nt "$HERE/input.swift" ] || swiftc -O "$HERE/input.swift" -o "$DIR/input"
}

play() {
  build_input
  cdp @"$HERE/reset.js" >/dev/null
  sleep 3
  front
  # An empty spot of the sidebar: the first click only focuses the window, so a right-click would be lost.
  "$DIR/input" "click $((X + 162)) $((Y + 640)) 300; wait 800"
}

case "$1" in
  setup)
    stop; command rm -r -f "$PROFILE"; mkdir -p "$DIR"
    launch; stop
    # Vivarc's shortcuts (what the installer writes), an English UI, and the sidebar pinned open.
    python3 - "$REPO" "$PROFILE" <<'EOF'
import json, os, sys
sys.path.insert(0, sys.argv[1]); sys.argv = sys.argv[:1] + sys.argv[2:]
import vivarc
profile = sys.argv[1]
path = os.path.join(profile, "Default", "Preferences")
prefs, _ = vivarc.patch_preferences(vivarc.read_json(path), vivarc.default_actions(vivarc.resources_dir(vivarc.DEFAULT_APP)))
prefs.setdefault("intl", {})["app_locale"] = "en-US"
prefs.setdefault("vivaldi", {}).setdefault("auto_hide", {})["tab_bar"] = False
vivarc.write_json(path, prefs)
EOF
    launch
    cdp @"$HERE/seed.js"
    node "$HERE/warmup.mjs"
    cdp @"$HERE/reset.js"
    echo "Ready. First take: $0 rehearse"
    ;;
  launch) launch ;;
  reset) cdp @"$HERE/reset.js" ;;
  rehearse) play; node "$HERE/take.mjs" ;;
  record)
    play
    command rm -f "$DIR/take.mov"
    screencapture -x -C -V "${2:-55}" -R$X,$Y,$W,$H "$DIR/take.mov" &
    sleep 1
    node "$HERE/take.mjs"
    wait
    echo "Recorded $DIR/take.mov. Trim the end with DEMO_LENGTH=<seconds> $0 encode"
    ;;
  encode)
    t=${DEMO_LENGTH:+-t $DEMO_LENGTH}
    # One palette for the whole clip with diff_mode: per-frame palettes look marginally better but weigh ~200 MB.
    ffmpeg -v error -y $t -i "$DIR/take.mov" -filter_complex \
      "fps=15,scale=1280:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle" \
      "$DIR/demo.gif"
    ffmpeg -v error -y $t -i "$DIR/take.mov" -vf "scale=2560:-2" -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p \
      -movflags +faststart -an "$DIR/demo.mp4"
    ls -lh "$DIR/demo.gif" "$DIR/demo.mp4"
    echo "README GIF: cp $DIR/demo.gif $REPO/docs/demo.gif"
    ;;
  stop) stop ;;
  clean) stop; command rm -r -f "$DIR" ;;
  *) sed -n '2,13p' "$0"; exit 1 ;;
esac
