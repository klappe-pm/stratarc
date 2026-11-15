"""Generate .github/stratarc-banner.svg: a terminal window with text as outlines and a timed animation.

Usage: python3 scripts/make-banner.py [--regular FONT.ttf] [--bold FONT.ttf] [--out PATH]

Text is converted to paths so the banner renders identically in every viewer, with no font
dependency. Requires fontTools and a monospace TrueType font; defaults to DejaVu Sans Mono.
"""

import argparse
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--regular", default="/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
ap.add_argument("--bold", default="/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf")
ap.add_argument("--out", default=str(ROOT / ".github" / "stratarc-banner.svg"))
args = ap.parse_args()

REG = TTFont(args.regular)
BOLD = TTFont(args.bold)

CYCLE = 10.0  # seconds per loop


def glyph_paths(font, text, x, y, size, per_char=False):
    """Return list of (path_d, advance_x) for text at baseline (x, y); one path per run or per char."""
    upem = font["head"].unitsPerEm
    s = size / upem
    cmap = font.getBestCmap()
    gs = font.getGlyphSet()
    hmtx = font["hmtx"]
    out = []
    pen = None
    cx = x
    for ch in text:
        name = cmap.get(ord(ch), ".notdef")
        if per_char or pen is None:
            pen = SVGPathPen(gs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
        tp = TransformPen(pen, (s, 0, 0, -s, cx, y))
        gs[name].draw(tp)
        cx += hmtx[name][0] * s
        if per_char:
            out.append((pen.getCommands(), cx))
            pen = None
    if not per_char:
        out.append((pen.getCommands(), cx))
    return out


def text_width(font, text, size):
    upem = font["head"].unitsPerEm
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    return sum(hmtx[cmap.get(ord(c), ".notdef")][0] for c in text) * size / upem


def pct(t):
    return f"{t / CYCLE * 100:.2f}%"


parts = []
css = []

# ---- static chrome ----
parts.append('<rect x="40" y="28" width="800" height="344" rx="14" fill="url(#bg)" stroke="#23344a" filter="url(#shadow)"/>')
parts.append('<rect x="40" y="28" width="800" height="40" rx="14" fill="#1b2a3d"/>')
parts.append('<rect x="40" y="54" width="800" height="14" fill="#1b2a3d"/>')
parts.append('<circle cx="66" cy="48" r="6.5" fill="#ff5f57"/><circle cx="88" cy="48" r="6.5" fill="#febc2e"/><circle cx="110" cy="48" r="6.5" fill="#28c840"/>')

w = text_width(REG, "stratarc", 13)
(d, _), = glyph_paths(REG, "stratarc", 440 - w / 2, 53, 13)
parts.append(f'<path class="dim" d="{d}"/>')

# ---- prompt line ----
x = 76
(d, x), = glyph_paths(REG, "~/stratarc-source", x, 112, 15)
parts.append(f'<path class="prompt" d="{d}"/>')
(d, x), = glyph_paths(REG, " $ ", x, 112, 15)
parts.append(f'<path class="dim" d="{d}"/>')

# typed command, one path per character with staggered appearance
T_TYPE0 = 0.7
T_STEP = 0.09
cmd = "stratarc sync"
chars = glyph_paths(REG, cmd, x, 112, 15, per_char=True)
cursor_x = x
for i, (d, nx) in enumerate(chars):
    t = T_TYPE0 + i * T_STEP
    parts.append(f'<path class="txt reveal" style="animation-delay:0s" d="{d}" data-t="{t}"/>')
    css.append(f".c{i}{{animation:show{i} {CYCLE}s steps(1) infinite}} @keyframes show{i}{{0%,{pct(t)}{{opacity:0}}{pct(t + 0.001)},100%{{opacity:1}}}}")
    parts[-1] = f'<path class="txt c{i}" d="{d}"/>'
T_TYPED = T_TYPE0 + len(cmd) * T_STEP

# cursor: sits after the prompt, moves with the typing (one rect per position, shown in sequence)
cursor_positions = [cursor_x] + [nx for _, nx in chars]
for i, cx in enumerate(cursor_positions):
    t0 = T_TYPE0 + (i - 1) * T_STEP if i > 0 else 0.0
    t1 = T_TYPE0 + i * T_STEP if i < len(chars) else CYCLE
    parts.append(f'<rect class="cursor k{i}" x="{cx + 3:.1f}" y="100" width="8" height="15"/>')
    if i < len(chars):
        css.append(f".k{i}{{animation:cur{i} {CYCLE}s steps(1) infinite}} @keyframes cur{i}{{0%{{opacity:0}}{pct(t0)}{{opacity:1}}{pct(t1)},100%{{opacity:0}}}}")
    else:
        # final position: visible after typing, and blinking
        css.append(f".k{i}{{animation:cur{i} {CYCLE}s steps(1) infinite, blink 1.1s steps(1) infinite}} @keyframes cur{i}{{0%,{pct(t0)}{{visibility:hidden}}{pct(t0 + 0.001)},100%{{visibility:visible}}}}")

# ---- wordmark and tagline ----
T_WORD = T_TYPED + 0.35
(d, _), = glyph_paths(BOLD, "stratarc", 76, 196, 64)
parts.append(f'<path class="word show-word" d="{d}"/>')
(d, _), = glyph_paths(REG, "one configuration source, rendered into any agent runtime", 76, 228, 15)
parts.append(f'<path class="dim show-word" d="{d}"/>')
css.append(f".show-word{{animation:sw {CYCLE}s steps(1) infinite}} @keyframes sw{{0%,{pct(T_WORD)}{{opacity:0}}{pct(T_WORD + 0.001)},100%{{opacity:1}}}}")

# ---- runtime rows ----
rows = [
    ("claude", "~/.claude", "CLAUDE.md, settings.json, hooks, skills"),
    ("codex", "~/.codex", "AGENTS.md, config.toml, rules, skills"),
    ("gemini", "~/.gemini", "GEMINI.md, settings.json, policies"),
    ("cursor", "~/.cursor", "hooks, hooks.json"),
    ("opencode", "~/.config/opencode", "AGENTS.md, opencode.jsonc, rules"),
]
T_ROW0 = T_WORD + 0.7
T_ROWSTEP = 0.55
for i, (name, target, files) in enumerate(rows):
    y = 272 + i * 22
    t = T_ROW0 + i * T_ROWSTEP
    (d1, _), = glyph_paths(REG, name, 100, y, 14)
    (d2, _), = glyph_paths(REG, target, 220, y, 14)
    (d3, _), = glyph_paths(REG, files, 440, y, 14)
    parts.append(f'<g class="r{i}"><path class="txt" d="{d1}"/><path class="dim" d="{d2}"/><path class="dim" d="{d3}"/></g>')
    # check mark drawn by stroke after the row text lands
    cy = y - 5
    parts.append(f'<path class="ok t{i}" d="M77 {cy} l3.2 3.4 l6.2 -7.2"/>')
    css.append(f".r{i}{{animation:row{i} {CYCLE}s steps(1) infinite}} @keyframes row{i}{{0%,{pct(t)}{{opacity:0}}{pct(t + 0.001)},100%{{opacity:1}}}}")
    css.append(f".t{i}{{animation:tick{i} {CYCLE}s linear infinite}} @keyframes tick{i}{{0%,{pct(t + 0.15)}{{stroke-dashoffset:16}}{pct(t + 0.45)},100%{{stroke-dashoffset:0}}}}")

style = """
.dim{fill:#7c93ad}.txt{fill:#d7e3ee}.prompt{fill:#5aa9ff}.word{fill:#3ddc84}
.cursor{fill:#d7dce6}
.ok{fill:none;stroke:#3ddc84;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:16;stroke-dashoffset:16}
@keyframes blink{50%{opacity:0}}
""" + "\n".join(css)

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="880" height="400" viewBox="0 0 880 400" role="img" aria-label="A terminal window: stratarc sync is typed, the stratarc wordmark appears, and each runtime is checked off">
  <!-- Generated by scripts/make-banner.py. Text is set as outlines of DejaVu Sans Mono (Bitstream Vera license) so it renders identically everywhere. Edit the generator, not these paths. -->
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#162233"/><stop offset="1" stop-color="#0d1520"/></linearGradient>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="18" stdDeviation="18" flood-color="#000" flood-opacity="0.45"/></filter>
    <style>{style}</style>
  </defs>
  {chr(10).join("  " + p for p in parts)}
</svg>
'''
Path(args.out).write_text(svg)
print(f"wrote {args.out}: {len(svg)} bytes; animation settles at {T_ROW0 + len(rows) * T_ROWSTEP:.2f}s of a {CYCLE:.0f}s loop")
