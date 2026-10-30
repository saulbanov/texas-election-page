#!/usr/bin/env bash
# Render og/card.html to the 1200x630 link-preview PNG with headless Chrome (macOS or Linux).
# Usage: og/render.sh 2026-10-29 [og-dir]   -> <og-dir>/card-2026-10-29.png
# Use a new name for each update: X, Slack and iMessage cache preview images by URL.
set -euo pipefail
here="${2:-$(cd "$(dirname "$0")" && pwd)}"   # the og/ folder to render in; defaults to this script's folder
stamp="${1:?give the data date, e.g. 2026-10-29}"
out="$here/card-$stamp.png"
chrome="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
[[ -x "$chrome" ]] || chrome="$(command -v google-chrome || command -v google-chrome-stable || command -v chromium || command -v chromium-browser)"
profile="$(mktemp -d)"
"$chrome" --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
  --user-data-dir="$profile" --window-size=1200,630 --virtual-time-budget=8000 \
  --screenshot="$out" "file://$here/card.html" >/dev/null 2>&1
rm -rf "$profile"
echo "wrote $out"
