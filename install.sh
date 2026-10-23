#!/bin/bash
# Vivarc: one-line install, update and repair for macOS.
#
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KASOGIT/vivarc/main/install.sh)"
#
# It downloads the latest Vivarc release into ~/.vivarc/app and runs its installer. Running it again updates
# Vivarc and re-applies it after a Vivaldi update. Extra arguments go to `vivarc.py install` (for example --no-peek).
set -e

REPO="KASOGIT/vivarc"
DEST="$HOME/.vivarc/app"

say() { printf '%s\n' "$*"; }
fail() { printf 'error: %s\n' "$*" >&2; exit 1; }

[ "$(uname)" = "Darwin" ] || fail "Vivarc is for macOS."
[ "$(id -u)" != "0" ] || fail "Do not use sudo. Run this command as yourself; if macOS blocks it, the installer will guide you."

if ! xcode-select -p >/dev/null 2>&1; then
  say "Vivarc needs Python, which comes with Apple's free command line developer tools."
  say "A window is about to appear: click Install, wait for it to finish (a few minutes), then run this command again."
  xcode-select --install >/dev/null 2>&1 || true
  exit 1
fi
PYTHON=/usr/bin/python3
[ -x "$PYTHON" ] || fail "python3 was not found at $PYTHON."

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

URL="${VIVARC_TARBALL_URL:-}"
if [ -z "$URL" ]; then
  say "Looking for the latest Vivarc release..."
  TAG="$(curl -fsSLI -o /dev/null -w '%{url_effective}' "https://github.com/$REPO/releases/latest" | sed 's#.*/##')"
  case "$TAG" in v[0-9]*) ;; *) fail "Could not find the latest release. Check your internet connection." ;; esac
  say "Downloading Vivarc $TAG..."
  URL="https://github.com/$REPO/archive/refs/tags/$TAG.tar.gz"
fi
curl -fsSL "$URL" -o "$TMP/vivarc.tar.gz" || fail "Download failed. Check your internet connection."
mkdir "$TMP/src"
tar -xzf "$TMP/vivarc.tar.gz" -C "$TMP/src" --strip-components=1
[ -f "$TMP/src/vivarc.py" ] || fail "The download does not look like Vivarc."

mkdir -p "$HOME/.vivarc"
rm -rf "$DEST"
mv "$TMP/src" "$DEST"

exec "$PYTHON" "$DEST/vivarc.py" install "$@"
