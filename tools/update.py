#!/usr/bin/env python3
"""Bring the page up to date from the election-2026 views. Deterministic; no network.

1. Mirror election-2026's views/latest.json and views/series.json into data/, verbatim.
2. Apply the rules set in advance in election-2026's benchmarks.md to data/assumptions.json:
   - once early voting is over (a complete post through Oct. 30), the measured final
     early-vote margin replaces our estimate;
   - from then on, the reliable-voter gap adds 0.4 points if under 150,000 and takes
     0.4 off if over 225,000.
   The lean (leanG, leanN) and the Election Day turnout adjustment (adj_ed) are set by hand.
   Every change to the central read is logged in data/assumptions.json, and the page shows it.
3. Re-render the link-preview card when the numbers changed, and point the page's preview
   tags at it.
4. Rebuild index.html.

    python3 tools/update.py --election-repo ../election-2026

Prints what changed and exits 0; prints "no change" when there is nothing to do.
"""
import argparse, datetime as dt, json, math, re, subprocess, sys
from pathlib import Path
from zoneinfo import ZoneInfo

CT = ZoneInfo('America/Chicago')
HERE = Path(__file__).resolve().parent  # in the pinned runtime, helper scripts sit beside this one
TOTAL_2022 = 8_095_174
FINAL_DAY = '2026-10-30'


def senate(c: dict, latest: dict) -> float:
    """The page's model, in points (positive is Talarico)."""
    g_share = latest['general_only'] / latest['no_primary']
    k = 2 * c['loyal'] / 100 - 1
    lean = g_share * c['leanG'] + (1 - g_share) * c['leanN']
    return 100 * (k * (c['early'] - c['ed']) + c['size'] * 1e6 * lean / 100) / (c['total'] * 1e6) + c.get('adj', 0)


CARD_DESIGN = 'e'  # bump when og/card.template.html changes, so the card gets a new file name
SIGMA = 2.3
RACES = [('Governor', 'Hinojosa', 'Abbott', 2, 0), ('Lt. Governor', 'Goodwin', 'Patrick', -1, 0.75),
         ('Attorney General', 'Johnson', 'Middleton', 1, 0.75), ('Agriculture', 'Tucker', 'Sheets', 0, 1)]
SCENARIO_LEANS = [(-4, None), (5.4, None), (8.5, None), (12, None), (16, 5.0)]


def card_numbers(c: dict, latest: dict) -> tuple[str, str]:
    """The four other races as card list items, and the Senate range across the scenario buttons."""
    t = senate(c, latest)
    items = []
    for name, d, r, adj, drop in RACES:
        m = (t - 0.5) - adj - drop
        who, col = (d, 'dem') if m >= 0 else (r, 'rep')
        items.append(f'<li><span>{name}</span><b style="color:var(--{col})">{who} +{abs(m):.1f}</b></li>')
    ts = [senate({**c, 'leanG': l, 'leanN': l, 'size': z or c['size']}, latest) for l, z in SCENARIO_LEANS]
    return ''.join(items), f'{race(min(ts))} to {race(max(ts))}'


def race(t: float) -> str:
    return ('Talarico +' if t >= 0 else 'Paxton +') + f'{abs(t):.1f}'


def mt(m: int) -> str:
    return ('D +' if m >= 0 else 'R +') + f'{abs(m):,}'


def md(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return ['Jan.', 'Feb.', 'March', 'April', 'May', 'June', 'July', 'Aug.', 'Sept.', 'Oct.', 'Nov.', 'Dec.'][d.month - 1] + f' {d.day}'


def next_update(latest: dict, now: dt.datetime) -> tuple[str, str]:
    if latest['through'] < FINAL_DAY:
        # every report this cycle posted the next day between about 2 and 10 p.m., most after 8
        return 'Sat., Oct. 31, after 6 p.m. CT', '2026-10-31T18:00:00-05:00'
    if now.date() <= dt.date(2026, 11, 1):
        return 'Sun., Nov. 1, after 6 p.m. CT', '2026-11-01T18:00:00-06:00'
    return 'Tue., Nov. 3, through the day', '2026-11-03T12:00:00-06:00'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--election-repo', default=str(Path(__file__).resolve().parents[2] / 'election-2026'))
    ap.add_argument('--site-repo', default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument('--no-card', action='store_true', help='skip the headless-Chrome preview card')
    a = ap.parse_args()
    site, views = Path(a.site_repo).resolve(), Path(a.election_repo).resolve() / 'general-2026' / 'early-vote' / 'views'
    data = site / 'data'; data.mkdir(exist_ok=True)
    now = dt.datetime.now(CT)
    changes = []

    # 1. mirror the views verbatim
    for name in ('latest.json', 'series.json'):
        src = (views / name).read_text()
        dst = data / name
        old = dst.read_text() if dst.exists() else None
        # the views carry a build time; compare without it so a rebuild with no new data is not a change
        strip = lambda t: re.sub(r'"built": "[^"]*"', '', t or '')
        if strip(old) != strip(src):
            dst.write_text(src); changes.append(f'mirrored {name}')
    latest = json.loads((data / 'latest.json').read_text())['latest']
    if not latest:
        print('SKIPPED: no complete snapshot in the views yet'); return 0

    # 2. assumptions and the rules set in advance
    af = data / 'assumptions.json'
    A = json.loads(af.read_text())
    c = A['central']
    before = senate(c, latest)
    notes = []
    final = latest['through'] >= FINAL_DAY and latest['complete']
    if final and (c.get('basis') != 'measured' or c['early'] != latest['primary_margin']):
        notes.append(f"the final early-vote margin, {mt(latest['primary_margin'])} through {md(latest['through'])}, replaced "
                     + (f"our estimate of {mt(c['early'])}" if c.get('basis') != 'measured' else f"the earlier figure of {mt(c['early'])}"))
        c['early'], c['basis'] = latest['primary_margin'], 'measured'
    if final:
        gap = latest['reliable_gap']
        adj_gap = 0.4 if gap < 150_000 else -0.4 if gap > 225_000 else 0.0
        if adj_gap != c.get('adj_gap', 0.0):
            notes.append(f"the reliable-voter gap of {gap:,} " + ('added 0.4 points' if adj_gap > 0 else 'took off 0.4 points' if adj_gap < 0 else 'no longer moves the read'))
            c['adj_gap'] = adj_gap
    c['adj'] = round(c.get('adj_gap', 0.0) + c.get('adj_ed', 0.0), 2)
    after = senate(c, latest)
    if notes:
        text = f"{now.strftime('%b.').replace('Oct.', 'Oct.').replace('Nov.', 'Nov.')} {now.day}: " + '; '.join(notes) + '.'
        text = text[0].upper() + text[1:]
        text += f" Our Senate read moved from {race(before)} to {race(after)}." if f'{before:.1f}' != f'{after:.1f}' else f" Our Senate read stays at {race(after)}."
        A.setdefault('log', []).append({'at': now.isoformat(timespec='minutes'), 'text': text})
        changes.append('central read: ' + text)
    nxt, nxt_iso = next_update(latest, now)
    if (nxt, nxt_iso) != (A.get('next_update'), A.get('next_update_iso')):
        A['next_update'], A['next_update_iso'] = nxt, nxt_iso; changes.append(f'next update: {nxt}')
    # 3. link-preview card and tags (a new card whenever the numbers or the card design change)
    races, rng = card_numbers(c, latest)
    card_name = f"card-{latest['through']}-{latest['counties']}-{CARD_DESIGN}-{'d' if after >= 0 else 'r'}{round(abs(after) * 10)}.png"
    card_missing = not a.no_card and not (site / 'og' / card_name).exists()
    if not changes and not card_missing:
        print('no change'); return 0
    A['page_updated'] = now.isoformat(timespec='minutes')
    af.write_text(json.dumps(A, indent=1) + '\n')

    page = (site / 'page.html').read_text()
    pT = 0.5 * (1 + math.erf(abs(after) / SIGMA / math.sqrt(2)))
    title = "Who wins Texas\u2019s midterm races"
    desc = (f"Future Heist\u2019s live projection from the early vote. Our central read has {race(after)} for the Senate, "
            f"a {round(100 * pT)}% chance; scenarios run from {rng}. Updated as counts arrive, with every number sourced.")
    if card_missing:
        tpl = (site / 'og' / 'card.template.html').read_text()
        html = (tpl.replace('{{THRU}}', md(latest['through']))
                   .replace('{{SENATE}}', race(after)).replace('{{SENATE_COLOR}}', 'var(--dem)' if after >= 0 else 'var(--rep)')
                   .replace('{{CHANCE}}', f"a {round(100 * pT)}% chance of winning")
                   .replace('{{RACES}}', races).replace('{{RANGE}}', rng))
        (site / 'og' / 'card.html').write_text(html)
        render = next(p for p in (HERE / 'render.sh', site / 'og' / 'render.sh') if p.exists())
        subprocess.run(['bash', str(render), card_name[len('card-'):-len('.png')], str(site / 'og')], check=True)
        changes.append(f'rendered og/{card_name}')
    if (site / 'og' / card_name).exists():
        page = re.sub(r'(<meta property="og:image" content="[^"]*/og/)[^"]+(")', rf'\g<1>{card_name}\2', page)
    page = re.sub(r'(<meta property="og:title" content=")[^"]*(")', lambda m: m.group(1) + title + m.group(2), page)
    page = re.sub(r'(<meta property="og:description" content=")[^"]*(")', lambda m: m.group(1) + desc + m.group(2), page)
    page = re.sub(r'(<meta name="description" content=")[^"]*(")', lambda m: m.group(1) + desc + m.group(2), page)
    page = re.sub(r'(<meta property="og:image:alt" content=")[^"]*(")', lambda m: m.group(1) + f"{title}. Our central read has {race(after)} for the Senate, with the other statewide races beside it." + m.group(2), page)
    (site / 'page.html').write_text(page)

    # 4. rebuild
    build = next(p for p in (HERE / 'build.py', site / 'build.py') if p.exists())
    subprocess.run([sys.executable, str(build), '--root', str(site)], check=True)
    for line in changes:
        print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
