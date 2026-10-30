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
import argparse, datetime as dt, json, re, subprocess, sys
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


def race(t: float) -> str:
    return ('Talarico +' if t >= 0 else 'Paxton +') + f'{abs(t):.1f}'


def mt(m: int) -> str:
    return ('D +' if m >= 0 else 'R +') + f'{abs(m):,}'


def md(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return ['Jan.', 'Feb.', 'March', 'April', 'May', 'June', 'July', 'Aug.', 'Sept.', 'Oct.', 'Nov.', 'Dec.'][d.month - 1] + f' {d.day}'


def next_update(latest: dict, now: dt.datetime) -> tuple[str, str]:
    if latest['through'] < FINAL_DAY:
        return 'Sat., Oct. 31, after 11 a.m. CT', '2026-10-31T11:00:00-05:00'
    if now.date() <= dt.date(2026, 11, 1):
        return 'Sun., Nov. 1, after 11 a.m. CT', '2026-11-01T11:00:00-06:00'
    return 'Tue., Nov. 3, through the day', '2026-11-03T12:00:00-06:00'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--election-repo', default=str(Path(__file__).resolve().parents[2] / 'election-2026'))
    ap.add_argument('--site-repo', default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument('--no-card', action='store_true', help='skip the headless-Chrome preview card')
    a = ap.parse_args()
    site, views = Path(a.site_repo), Path(a.election_repo) / 'general-2026' / 'early-vote' / 'views'
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
    if not changes:
        print('no change'); return 0
    A['page_updated'] = now.isoformat(timespec='minutes')
    af.write_text(json.dumps(A, indent=1) + '\n')

    # 3. link-preview card and tags
    page = (site / 'page.html').read_text()
    lead = latest['primary_margin']; party = 'Democratic' if lead >= 0 else 'Republican'
    title = f"{party} primary voters lead Texas's early vote by {abs(lead):,}"
    desc = (f"{latest['votes'] / 1e6:.2f} million early votes through {md(latest['through'])}. At this point in 2022 and 2024, Republicans led. "
            f"Our central read: {race(after)}, a rough model, not a forecast. Every number sourced; test your own assumptions.")
    card_name = f"card-{latest['through']}-{latest['counties']}.png"
    if not a.no_card and not (site / 'og' / card_name).exists():
        tpl = (site / 'og' / 'card.template.html').read_text()
        html = (tpl.replace('{{HEAD}}', f"{party} primary voters lead Texas's early vote by <b style=\"color:var(--{'dem' if lead >= 0 else 'rep'})\">{abs(lead):,}</b>")
                   .replace('{{SUB}}', f"{latest['votes'] / 1e6:.2f} million early votes through {md(latest['through'])}. At this point in 2022 and 2024, Republicans led.")
                   .replace('{{SENATE}}', race(after)).replace('{{SENATE_COLOR}}', 'var(--dem)' if after >= 0 else 'var(--rep)'))
        (site / 'og' / 'card.html').write_text(html)
        render = next(p for p in (HERE / 'render.sh', site / 'og' / 'render.sh') if p.exists())
        subprocess.run(['bash', str(render), f"{latest['through']}-{latest['counties']}", str(site / 'og')], check=True)
        changes.append(f'rendered og/{card_name}')
    if (site / 'og' / card_name).exists():
        page = re.sub(r'(<meta property="og:image" content="[^"]*/og/)[^"]+(")', rf'\g<1>{card_name}\2', page)
    page = re.sub(r'(<meta property="og:title" content=")[^"]*(")', lambda m: m.group(1) + title + m.group(2), page)
    page = re.sub(r'(<meta property="og:description" content=")[^"]*(")', lambda m: m.group(1) + desc + m.group(2), page)
    page = re.sub(r'(<meta name="description" content=")[^"]*(")', lambda m: m.group(1) + desc + m.group(2), page)
    (site / 'page.html').write_text(page)

    # 4. rebuild
    build = next(p for p in (HERE / 'build.py', site / 'build.py') if p.exists())
    subprocess.run([sys.executable, str(build), '--root', str(site)], check=True)
    for line in changes:
        print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
