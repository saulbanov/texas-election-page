#!/usr/bin/env python3
"""Build index.html (served by GitHub Pages) from page.html (the source).

page.html is written the way the Claude artifact host expects: no doctype,
no <html>/<head>/<body>, because that host wraps it at publish time. GitHub
Pages serves files as they are, so this adds the same wrapper here: a doctype
(without it browsers render in quirks mode), the charset and viewport tags
(without the viewport tag phones lay the page out at desktop width), and the
host's small reset. Run it after every edit to page.html.

GitHub Pages tells browsers to keep a page for 10 minutes, so a phone can show
an old copy after an update. Each build therefore writes version.json with a
hash of the page, and the page carries the same hash: on load it fetches
version.json uncached and, if the hash differs, reloads at ?v=<new hash>,
a URL the browser has not cached.



    python3 build.py
"""
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent  # overridden by --root
SPLIT = '<div class="wrap">'

RESET = (
    ':root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);'
    'padding-bottom:env(safe-area-inset-bottom,0px)}'
    'body{margin:0;font:14px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif}'
    'img{max-width:100%}[hidden]{display:none!important}'
)


def main() -> None:
    global ROOT
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('--root', default=str(ROOT), help='the texas-election-page checkout to build')
    ROOT = Path(ap.parse_args().root)
    src = (ROOT / 'page.html').read_text(encoding='utf-8')
    if SPLIT not in src:
        raise SystemExit(f'page.html has no {SPLIT!r}; cannot tell head from body')
    head, body = src.split(SPLIT, 1)
    # Inline the data files as a fallback; the page fetches them fresh on load.
    data = {}
    for name in ('latest', 'series', 'assumptions', 'seats'):
        f = ROOT / 'data' / f'{name}.json'
        if not f.exists():
            raise SystemExit(f'missing data/{name}.json; run tools/update.py first')
        data[name] = json.loads(f.read_text(encoding='utf-8'))
    blob = json.dumps(data, separators=(',', ':')).replace('</', '<\\/')
    i = body.rindex('<script>')
    body = body[:i] + f'<script id="ledger-data" type="application/json">{blob}</script>\n' + body[i:]
    page = f'{head.rstrip()}\n</head>\n<body>\n{SPLIT}{body.rstrip()}\n</body>\n</html>\n'
    build = hashlib.sha256(page.encode('utf-8')).hexdigest()[:12]
    fresh = ("<script>(function(){var b='%s';fetch('version.json',{cache:'no-store'}).then(function(r){return r.json()})"
             ".then(function(v){var u=new URL(location.href);if(v.build&&v.build!==b&&u.searchParams.get('v')!==v.build)"
             "{u.searchParams.set('v',v.build);location.replace(u.href)}}).catch(function(){})})()</script>" % build)
    out = (
        '<!doctype html>\n<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        f'<style>{RESET}</style>\n{fresh}\n'
        f'{page}'
    )
    (ROOT / 'index.html').write_text(out, encoding='utf-8')
    (ROOT / 'version.json').write_text(json.dumps({'build': build}) + '\n', encoding='utf-8')
    print(f'wrote index.html ({len(out):,} bytes) from page.html')


if __name__ == '__main__':
    main()
