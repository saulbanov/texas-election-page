# texas-election-page

Future Heist's Texas 2026 early-vote page: the early-vote count with every number traced to its source, our read on the voters who have never voted in a primary, and a workbench for testing assumptions.

**Status: live** at https://saulbanov.github.io/texas-election-page/, with data through Thu., Oct. 29. Open items:

- Source the 2024 lean of voters with no primary history before turning on that preset.
- Check the 2022 total (8,095,174, summed from Ryan's voter-file categories) against the official Secretary of State figure.

## Page order

1. Where the races stand (our read): the Senate race in our central read, then the four other statewide races
2. Who has voted early, by the party primary they last voted in, against 2022 and 2024 at the same point; update schedule
3. Who hasn't voted in a primary (our read)
4. What could happen: the 2022 lean, our central read and the 2018 lean side by side
5. Scenario workbench
6. How we'd know we're wrong
7. Checking our work: the primary-voter lead, the superseded partial post, the three measures against their thresholds, daily counts
8. Corrections, who publishes this, and sources

## Files

| File | What it is |
|---|---|
| `page.html` | The page source: HTML, CSS and the scenario model. Edit this one. |
| `build.py` | Wraps `page.html` in a full HTML document (doctype, charset, viewport) and writes `index.html`. Run `python3 build.py` after every edit. |
| `og/card.html`, `og/render.sh` | The link-preview card. After each data update, edit the card's numbers and run `og/render.sh <data date>`, then point `og:image` in `page.html` at the new PNG. Platforms cache preview images by URL, so each update needs a new file name. |
| `index.html` | What GitHub Pages serves at https://saulbanov.github.io/texas-election-page/. Generated; don't edit by hand. |

`page.html` has no doctype or `<head>` because the Claude artifact host adds them when it publishes the private preview. GitHub Pages serves files as they are, so without `build.py` phones would lay the page out at desktop width.

## Data

Every number on the page comes from the analysis repo [`saulbanov/election-2026`](https://github.com/saulbanov/election-2026) (public since Oct. 30), as of commit `596fb69`. Each sourced number opens a panel naming its source file, the page it came from, the arithmetic and the file's SHA-256 fingerprint from that repo's `MANIFEST.jsonl`.

The page shows aggregate counts only, never individual voter records.

## The model

The workbench uses the same rough model as `election-2026/general-2026/early-vote/benchmarks.md`:

```
Senate margin (pts) = 100 × [ (2·loyalty − 1)·(early margin − Election Day reserve)
                              + general-only voters × their lean
                              + no-history voters × their lean ] ÷ total votes
Other races = (Senate − 0.5) − candidate adjustment − drop-off − ticket-splitting shift
```

Central case: leans of D +8.5, 4.0M voters with no primary history split 80/20, an early margin of D +30,000, an Election Day reserve of R +200,000, 95% loyalty and 10M votes. That gives Talarico +1.9. It is a rough model, not a forecast.

## How it updates

The numbers come from three files in `data/`, which the page fetches fresh on every load (and `build.py` also inlines as a fallback):

| File | Written by | What it holds |
|---|---|---|
| `data/latest.json`, `data/series.json` | `tools/update.py`, copied verbatim from `election-2026`'s `general-2026/early-vote/views/` | Every parsed Transparency USA snapshot, each naming its source PDF and SHA-256 |
| `data/assumptions.json` | `tools/update.py` for the rules below; Saul by hand for the rest | The central read's inputs and a dated log of every change to it |

**What changes on its own,** by the rules committed in advance in `election-2026/general-2026/early-vote/benchmarks.md`:
- once a complete post (240+ counties) through Oct. 30 exists, the measured final early-vote margin replaces our estimate;
- from then on, a reliable-voter gap under 150,000 adds 0.4 points to the Senate read, and one over 225,000 takes 0.4 off.

**What changes only by hand:** the lean of voters with no primary history (`leanG`, `leanN`) and the Election Day turnout adjustment (`adj_ed`: +0.5 if the marker counties run light, −0.7 if heavy). Edit `data/assumptions.json`, add a line to its `log`, run `python3 tools/update.py`, commit and push.

**The schedule.** `ops/run-update.sh` runs every 15 minutes from launchd, Oct. 31 to Nov. 4. Each run fetches every snapshot from Oct. 30 through yesterday (`election-2026/tools/fetch_snapshot.py`), files new ones, rebuilds the views (`build_views.py`), pushes `election-2026`, then runs `tools/update.py` and pushes this repo. It runs from a pinned copy of the code in `~/Documents/runtime/election-update/code`, which only `ops/deploy.sh` moves; the log is `~/Library/Logs/election-update.log`. To test push access from launchd without changing anything: `touch ~/Documents/runtime/election-update/PROBE`.

