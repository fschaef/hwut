#!/usr/bin/env python3
"""RETURN: None. Render a tmux 'capture-pane -e' dump as a terminal-window PNG.
usage: render.py IN.ans OUT.png TITLE   (env PW_CHROMIUM: path of a chromium)"""
import os
import html, re, sys
from playwright.sync_api import sync_playwright

BASE = ["#1e1e1e","#cd3131","#0dbc79","#e5e510","#2472c8","#bc3fbc","#11a8cd","#e5e5e5",
        "#666666","#f14c4c","#23d18b","#f5f543","#3b8eea","#d670d6","#29b8db","#ffffff"]
def c256(n):
    if n < 16: return BASE[n]
    if n < 232:
        n -= 16; r, g, b = n // 36, (n // 6) % 6, n % 6
        f = lambda v: 0 if v == 0 else 55 + 40 * v
        return "#%02x%02x%02x" % (f(r), f(g), f(b))
    v = 8 + 10 * (n - 232); return "#%02x%02x%02x" % (v, v, v)
FG0, BG0 = "#d4d4d4", "#1e1e1e"

def to_html(text):
    fg = bg = None; bold = dim = rev = ul = False
    out = []; pos = 0
    for m in re.finditer(r"\x1b\[([0-9;]*)m|\x1b\[[0-9;?]*[A-Za-z]", text):
        out.append(("t", text[pos:m.start()], (fg, bg, bold, dim, rev, ul))); pos = m.end()
        if not m.group(0).endswith("m"): continue
        a = [int(x) if x else 0 for x in (m.group(1) or "0").split(";")]; i = 0
        while i < len(a):
            n = a[i]
            if n == 0: fg = bg = None; bold = dim = rev = ul = False
            elif n == 1: bold = True
            elif n == 2: dim = True
            elif n == 4: ul = True
            elif n == 7: rev = True
            elif n == 22: bold = dim = False
            elif n == 24: ul = False
            elif n == 27: rev = False
            elif 30 <= n <= 37: fg = BASE[n - 30]
            elif 90 <= n <= 97: fg = BASE[n - 90 + 8]
            elif n == 39: fg = None
            elif 40 <= n <= 47: bg = BASE[n - 40]
            elif 100 <= n <= 107: bg = BASE[n - 100 + 8]
            elif n == 49: bg = None
            elif n in (38, 48):
                if a[i + 1] == 5: col = c256(a[i + 2]); i += 2
                else: col = "#%02x%02x%02x" % tuple(a[i + 2:i + 5]); i += 4
                if n == 38: fg = col
                else: bg = col
            i += 1
    out.append(("t", text[pos:], (fg, bg, bold, dim, rev, ul)))
    parts = []
    for _, t, (f, b, bo, di, re_, u) in out:
        if not t: continue
        f2, b2 = (f or FG0), (b or BG0)
        if re_: f2, b2 = b2, f2
        st = "color:%s;background:%s;" % (f2, b2)
        if bo: st += "font-weight:bold;"
        if di: st += "opacity:.6;"
        if u: st += "text-decoration:underline;"
        parts.append('<span style="%s">%s</span>' % (st, html.escape(t)))
    return "".join(parts)

src, dst, title = sys.argv[1:4]
text = open(src).read().rstrip("\n")
lines = text.split("\n")
while lines and not re.sub(r"\x1b\[[0-9;]*m", "", lines[-1]).strip(): lines.pop()
body = to_html("\n".join(lines))
page = f"""<html><body style="margin:0;background:#fff">
<div id=w style="display:inline-block;margin:18px;border-radius:9px;overflow:hidden;
 box-shadow:0 4px 18px rgba(0,0,0,.35);background:{BG0}">
<div style="background:#3a3a3a;color:#bbb;font:13px sans-serif;padding:8px 12px">
<span style="color:#ff5f56">&#9679;</span> <span style="color:#ffbd2e">&#9679;</span>
<span style="color:#27c93f">&#9679;</span>&nbsp;&nbsp;{html.escape(title)}</div>
<pre style="margin:0;padding:12px 14px;color:{FG0};background:{BG0};
 font:15px/1.25 'DejaVu Sans Mono',monospace">{body}</pre></div></body></html>"""
with sync_playwright() as p:
    exe = os.environ.get('PW_CHROMIUM')
    b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    pg = b.new_page(device_scale_factor=2, viewport={"width": 1400, "height": 900})
    pg.set_content(page); pg.locator("#w").screenshot(path=dst); b.close()
