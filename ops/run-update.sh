#!/bin/zsh
# Scheduled fetch (and, optionally, update) for the Texas early-vote page. launchd wakes it every 3 minutes
# (ops/org.futureheist.election-update.plist); it fetches snapshots at most every 15 minutes and does nothing
# outside Oct. 31 - Nov. 4. Election-night results reading is added here once built.
#
# 1. Acquire: fetch each Transparency USA snapshot from Oct. 30 through yesterday; file new ones in election-2026.
#    Also fetch the Secretary of State's county turnout files (Friday's early vote, Election Day) through BrowserOS.
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
  gh auth status -h github.com >/dev/null 2>&1 && log "probe: gh auth OK (can start the publisher)" || log "probe: gh auth FAILED"
  rm -f $RT/PROBE
fi

today=$(TZ=America/Chicago date +%F)
start=${ELECTION_UPDATE_START:-2026-10-31}
if [[ $today < $start || $today > 2026-11-04 ]]; then log "outside the update window ($start to 2026-11-04); nothing to do"; exit 0; fi
for d in $CODE $E $S; do [[ -d $d ]] || { log "SKIPPED - no checkout at $d; run ops/deploy.sh"; exit 1; }; done
for d in $E $S; do git -C $d pull -q --ff-only || { log "FAILED: git pull --ff-only in $d"; exit 1; }; done

# 1. acquire, at most every 15 minutes
stamp=$RT/.last-snapshot-run
if [[ -f $stamp && $(( $(date +%s) - $(stat -f %m $stamp) )) -lt 840 ]]; then exit 0; fi
touch $stamp
d=2026-10-30; yesterday=$(TZ=America/Chicago date -v-1d +%F)
while [[ ! $d > $yesterday ]]; do
  out=$(python3 $CODE/fetch_snapshot.py --repo $E --date $d); rc=$?
  [[ $rc == 0 || $rc == 2 ]] || log "FAILED: fetch $d rc=$rc"
  [[ $out == *'"new": true'* ]] && log "filed: $out"
  d=$(date -j -v+1d -f %F $d +%F)
done
# the state's turnout app, read through BrowserOS (it must be running with its MCP server on)
out=$(python3 $CODE/fetch_sos_turnout.py --repo $E); rc=$?
case $rc in
  0) print -r -- "$out" | grep -q '"new": true' && log "filed SOS turnout: $(print -r -- "$out" | grep '"new": true' | tr '\n' ' ')" ;;
  3) log "SKIPPED SOS turnout - BrowserOS is not running at 127.0.0.1:9010; open BrowserOS" ;;
  4) log "SKIPPED SOS turnout - the turnout app shows a check in BrowserOS; clear it there: $out" ;;
  *) log "FAILED: fetch_sos_turnout rc=$rc $out" ;;
esac

# 2. analyze
python3 $CODE/build_views.py --repo $E >/dev/null || { log "FAILED: build_views"; exit 1; }
if [[ -n $(git -C $E status --porcelain -- general-2026/early-vote turnout) ]]; then
  thru=$(python3 -c "import json,sys; l=json.load(open(sys.argv[1]))['latest']; print(l['through'], l['counties'], 'counties')" $E/general-2026/early-vote/views/latest.json)
  git -C $E add general-2026/early-vote/sources general-2026/early-vote/views turnout \
    && git -C $E commit -q -m "Scheduled: file new snapshot or SOS turnout; views through $thru" \
    && git -C $E push -q && log "pushed election-2026 ($thru)" || { log "FAILED: commit/push election-2026"; exit 1; }
  # GitHub runs the scheduled publisher only every few hours, so start it now that there is new data
  if [[ ${ELECTION_UPDATE_FETCH_ONLY:-0} == 1 ]]; then
    gh workflow run update.yml -R saulbanov/texas-election-page >/dev/null 2>&1 \
      && log "started the GitHub publisher" || log "FAILED: gh workflow run update.yml (the page waits for GitHub's own schedule)"
  fi
fi

# 3. publish (skipped when GitHub Actions publishes the page; the plist sets ELECTION_UPDATE_FETCH_ONLY=1)
if [[ ${ELECTION_UPDATE_FETCH_ONLY:-0} == 1 ]]; then log "fetch-only run done"; exit 0; fi
upd=$(python3 $CODE/update.py --election-repo $E --site-repo $S) || { log "FAILED: update.py"; exit 1; }
if [[ -n $(git -C $S status --porcelain -- data og page.html index.html version.json live) ]]; then
  git -C $S add data og page.html index.html version.json live \
    && git -C $S commit -q -m "Scheduled update: $(print -r -- $upd | tail -1 | cut -c1-120)" \
    && git -C $S push -q && log "pushed texas-election-page: $(print -r -- $upd | tr '\n' ';')" || { log "FAILED: commit/push texas-election-page"; exit 1; }
else
  log "no change"
fi
