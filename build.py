#!/usr/bin/env python3
"""Build index.html (served by GitHub Pages) from page.html (the source).

page.html is written the way the Claude artifact host expects: no doctype,
no <html>/<head>/<body>, because that host wraps it at publish time. GitHub
Pages serves files as they are, so this adds the same wrapper here: a doctype
(without it browsers render in quirks mode), the charset and viewport tags
(without the viewport tag phones lay the page out at desktop width), and the
host's small reset. Run it after every edit to page.html:

    python3 build.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPLIT = '<div class="wrap">'

RESET = (
    ':root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);'
    'padding-bottom:env(safe-area-inset-bottom,0px)}'
    'body{margin:0;font:14px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif}'
    'img{max-width:100%}[hidden]{display:none!important}'
)


def main() -> None:
    src = (ROOT / 'page.html').read_text(encoding='utf-8')
    if SPLIT not in src:
        raise SystemExit(f'page.html has no {SPLIT!r}; cannot tell head from body')
    head, body = src.split(SPLIT, 1)
    out = (
        '<!doctype html>\n<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        f'<style>{RESET}</style>\n'
        f'{head.rstrip()}\n</head>\n<body>\n{SPLIT}{body.rstrip()}\n</body>\n</html>\n'
    )
    (ROOT / 'index.html').write_text(out, encoding='utf-8')
    print(f'wrote index.html ({len(out):,} bytes) from page.html')


if __name__ == '__main__':
    main()
