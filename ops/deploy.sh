#!/bin/zsh
# Deploy (or redeploy) the scheduled updater. Run by hand; this is the only thing that moves the pinned code.
#
#   ops/deploy.sh            copy the code at the two repos' current HEADs into the runtime, clone data repos if missing
#   ops/deploy.sh --install  also install and load the launchd job
#
# Pinned code: ~/Documents/runtime/election-update/code (plain copies, with DEPLOYED naming their commits).
# Data clones:  ~/Documents/runtime/election-update/{election-2026,texas-election-page}, on main.
# Log:          ~/Library/Logs/election-update.log
set -eu
SITE=${0:A:h:h}
ELECTION=${ELECTION_REPO:-${SITE:h}/election-2026}
RT=$HOME/Documents/runtime/election-update
mkdir -p $RT/code
for r in election-2026 texas-election-page; do
  [[ -d $RT/$r/.git ]] || git clone -q https://github.com/saulbanov/$r.git $RT/$r
done
# copy from committed HEAD, not the working tree, so what runs is what is on GitHub
git -C $ELECTION show HEAD:tools/fetch_snapshot.py > $RT/code/fetch_snapshot.py
git -C $ELECTION show HEAD:tools/build_views.py   > $RT/code/build_views.py
git -C $ELECTION show HEAD:tools/fetch_sos_results.py > $RT/code/fetch_sos_results.py
git -C $ELECTION show HEAD:tools/fetch_sos_turnout.py > $RT/code/fetch_sos_turnout.py
git -C $ELECTION show HEAD:tools/build_results_view.py > $RT/code/build_results_view.py
git -C $SITE show HEAD:tools/update.py           > $RT/code/update.py
git -C $SITE show HEAD:build.py                  > $RT/code/build.py
git -C $SITE show HEAD:og/render.sh              > $RT/code/render.sh
git -C $SITE show HEAD:ops/run-update.sh         > $RT/code/run-update.sh
chmod +x $RT/code/*.sh
print -r -- "election-2026 $(git -C $ELECTION rev-parse --short HEAD)  texas-election-page $(git -C $SITE rev-parse --short HEAD)  deployed $(date '+%Y-%m-%d %H:%M')" > $RT/code/DEPLOYED
cat $RT/code/DEPLOYED

if [[ ${1:-} == --install ]]; then
  plist=$HOME/Library/LaunchAgents/org.futureheist.election-update.plist
  sed "s#__RT__#$RT#g; s#__HOME__#$HOME#g" $SITE/ops/org.futureheist.election-update.plist > $plist
  launchctl bootout gui/$(id -u)/org.futureheist.election-update 2>/dev/null || true
  launchctl bootstrap gui/$(id -u) $plist
  print "loaded org.futureheist.election-update (every 15 min; log ~/Library/Logs/election-update.log)"
fi
