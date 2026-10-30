# texas-election-page

Future Heist's Texas 2026 early-vote page: the early-vote count with every number traced to its source, our read on the voters who have never voted in a primary, and a workbench for testing assumptions.

**Status: prototype.** Not yet published. Open items:

- Write the publisher statement (marked "Draft · Saul to write" on the page).
- Source the 2024 lean of voters with no primary history before turning on that preset.
- Check the 2022 total (8,095,174, summed from Ryan's voter-file categories) against the official Secretary of State figure.

## Page order

1. Turnout (measured), with the update schedule
2. Where the races stand (our read): a typical Democrat against a typical Republican, then the five statewide races
3. Who hasn't voted in a primary (our read)
4. Scenario workbench
5. How we'd know we're wrong
6. Checking our work: the primary-voter lead, the superseded partial post, the three measures against their thresholds, daily counts
7. Corrections and sources

## Files

| File | What it is |
|---|---|
| `index.html` | The whole page: HTML, CSS and the scenario model, with no build step |

## Data

Every number on the page comes from the analysis repo `saulbanov/election-2026` (private), as of commit `596fb69`. Each sourced number opens a panel naming its source file, the page it came from, the arithmetic and the file's SHA-256 fingerprint from that repo's `MANIFEST.jsonl`.

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
