#!/bin/zsh
# Render og/card.html to the 1200x630 link-preview PNG with headless Chrome.
# Usage: og/render.sh 2026-10-29 [og-dir]   -> <og-dir>/card-2026-10-29.png
# Use a new date in the file name for each update: X, Slack and iMessage cache preview images by URL.
set -e
here="${2:-${0:A:h}}"   # the og/ folder to render in; defaults to this script's folder
stamp="${1:?give the data date, e.g. 2026-10-29}"
out="$here/card-$stamp.png"
profile="$(mktemp -d)"
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars \
  --user-data-dir="$profile" --window-size=1200,630 --virtual-time-budget=8000 \
  --screenshot="$out" "file://$here/card.html" >/dev/null 2>&1
rm -rf "$profile"
echo "wrote $out"
