#!/bin/zsh
# Scheduled update of the Texas early-vote page. Runs every 15 minutes from launchd
# (ops/org.futureheist.election-update.plist) and does nothing outside Oct. 31 - Nov. 4.
#
# 1. Acquire: fetch each Transparency USA snapshot from Oct. 30 through yesterday; file new ones in election-2026.
# 2. Analyze: rebuild election-2026's views; commit and push election-2026 if anything changed.
# 3. Publish: mirror the views into the page, apply the pre-set rules, rebuild; commit and push the page.
#
# The code runs from $RT/code, copied there by ops/deploy.sh and moved only by running it again.
# $RT/election-2026 and $RT/texas-election-page are data clones on main that this script pulls and pushes.
set -u
export PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin
RT=${ELECTION_UPDATE_ROOT:-$HOME/Documents/runtime/election-update}
CODE=$RT/code E=$RT/election-2026 S=$RT/texas-election-page
log() { print -r -- "$(TZ=America/Chicago date '+%Y-%m-%d %H:%M:%S CT') $*"; }

# Auth probe (runs even outside the window): touch $RT/PROBE to test pushes from launchd without changing anything.
if [[ -f $RT/PROBE ]]; then
  for d in $E $S; do git -C $d push --dry-run -q 2>&1 && log "probe: push auth OK in $d" || log "probe: push FAILED in $d"; done
  rm -f $RT/PROBE
fi

today=$(TZ=America/Chicago date +%F)
start=${ELECTION_UPDATE_START:-2026-10-31}
if [[ $today < $start || $today > 2026-11-04 ]]; then log "outside the update window ($start to 2026-11-04); nothing to do"; exit 0; fi
for d in $CODE $E $S; do [[ -d $d ]] || { log "SKIPPED - no checkout at $d; run ops/deploy.sh"; exit 1; }; done
for d in $E $S; do git -C $d pull -q --ff-only || { log "FAILED: git pull --ff-only in $d"; exit 1; }; done

# 1. acquire
d=2026-10-30; yesterday=$(TZ=America/Chicago date -v-1d +%F)
while [[ ! $d > $yesterday ]]; do
  out=$(python3 $CODE/fetch_snapshot.py --repo $E --date $d); rc=$?
  [[ $rc == 0 || $rc == 2 ]] || log "FAILED: fetch $d rc=$rc"
  [[ $out == *'"new": true'* ]] && log "filed: $out"
  d=$(date -j -v+1d -f %F $d +%F)
done

# 2. analyze
python3 $CODE/build_views.py --repo $E >/dev/null || { log "FAILED: build_views"; exit 1; }
if [[ -n $(git -C $E status --porcelain -- general-2026/early-vote) ]]; then
  thru=$(python3 -c "import json,sys; l=json.load(open(sys.argv[1]))['latest']; print(l['through'], l['counties'], 'counties')" $E/general-2026/early-vote/views/latest.json)
  git -C $E add general-2026/early-vote/sources general-2026/early-vote/views \
    && git -C $E commit -q -m "Scheduled: file new Transparency USA snapshot; views through $thru" \
    && git -C $E push -q && log "pushed election-2026 ($thru)" || { log "FAILED: commit/push election-2026"; exit 1; }
fi

# 3. publish
upd=$(python3 $CODE/update.py --election-repo $E --site-repo $S) || { log "FAILED: update.py"; exit 1; }
if [[ -n $(git -C $S status --porcelain -- data og page.html index.html) ]]; then
  git -C $S add data og page.html index.html \
    && git -C $S commit -q -m "Scheduled update: $(print -r -- $upd | tail -1 | cut -c1-120)" \
    && git -C $S push -q && log "pushed texas-election-page: $(print -r -- $upd | tr '\n' ';')" || { log "FAILED: commit/push texas-election-page"; exit 1; }
else
  log "no change"
fi
