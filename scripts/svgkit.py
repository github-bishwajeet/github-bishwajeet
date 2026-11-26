# Tiny SVG kit for the profile cards: design-system tokens, embedded subset fonts, text widths,
# and the sticker shapes (board, card, chip, pill, highlight). Every colour comes from
# scripts/tokens.json, which is a COPY of the BuildinZZ repo's design-system/tokens.json: when the
# design system changes, copy the file again.
import base64, io, json, os
from collections import defaultdict
from xml.sax.saxutils import escape
from fontTools.ttLib import TTFont
from fontTools import subset

HERE = os.path.dirname(os.path.abspath(__file__))
TOK = json.load(open(os.path.join(HERE, "tokens.json"), encoding="utf8"))

FONTS = {  # key: (family, weight, file)
    "f500": ("ZF", 500, "Fredoka-500.ttf"),
    "f600": ("ZF", 600, "Fredoka-600.ttf"),
    "f700": ("ZF", 700, "Fredoka-700.ttf"),
    "m400": ("ZM", 400, "DMMono-400.ttf"),
    "m500": ("ZM", 500, "DMMono-500.ttf"),
}
_tt = {k: TTFont(os.path.join(HERE, "fonts", f)) for k, (_, _, f) in FONTS.items()}


def text_width(s, font, size):
    tt = _tt[font]
    cmap = tt.getBestCmap(); hmtx = tt["hmtx"]; upm = tt["head"].unitsPerEm
    w = 0
    for ch in s:
        g = cmap.get(ord(ch))
        w += hmtx[g][0] if g else upm * 0.55
    return w * size / upm


def wrap(s, font, size, maxw):
    words, lines, cur = s.split(" "), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if text_width(t, font, size) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def _subset_b64(font_key, chars):
    path = os.path.join(HERE, "fonts", FONTS[font_key][2])
    f = TTFont(path, recalcTimestamp=False)   # keep the font's own timestamp: the same input must give the same bytes
    opts = subset.Options(); opts.flavor = "woff2"; opts.layout_features = ["kern", "liga"]
    sub = subset.Subsetter(opts); sub.populate(text="".join(sorted(chars)) + " "); sub.subset(f)
    buf = io.BytesIO(); f.flavor = "woff2"; f.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


def mix(a, b, t):
    """t of colour a over colour b (both #rrggbb), like CSS color-mix."""
    a = [int(a[i:i + 2], 16) for i in (1, 3, 5)]; b = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x * t + y * (1 - t)):02x}" for x, y in zip(a, b))


def img_b64(path, mime=None):
    with open(path, "rb") as f:
        data = f.read()
    mime = mime or {"png": "image/png", "webp": "image/webp", "jpg": "image/jpeg"}[path.rsplit(".", 1)[1]]
    return f"data:{mime};base64," + base64.b64encode(data).decode()


class Svg:
    def __init__(self, w, h, theme, label):
        self.w, self.h, self.theme, self.label = w, h, theme, label
        self.c = TOK["color"][theme]
        self.parts, self.defs, self.css = [], [], []
        self.used = defaultdict(set)
        self._id = 0
        self.min_size = 999      # smallest font size drawn, checked by the tests
        self.overflow = []       # text that runs past the right edge, checked by the tests

    def uid(self, p="i"):
        self._id += 1
        return f"{p}{self._id}"

    def col(self, k):
        return self.c.get(k, k)

    def add(self, s):
        self.parts.append(s)

    def _track(self, s, x, font, size, anchor="start"):
        w = text_width(s, font, size)
        left = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
        if left < -0.5 or left + w > self.w + 0.5:
            self.overflow.append(s)
        self.min_size = min(self.min_size, size)

    def text(self, x, y, s, font="f700", size=16, fill="text", anchor="start", cls="", extra=""):
        self.used[font].update(s)
        self._track(s, x, font, size, anchor)
        fam, wt, _ = FONTS[font]
        c = f' class="{cls}"' if cls else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{fam}" font-weight="{wt}" font-size="{size}" '
                 f'fill="{self.col(fill)}" text-anchor="{anchor}"{c} {extra}>{escape(s)}</text>')
        return text_width(s, font, size)

    def tspans(self, x, y, runs, font="m400", size=15, extra=""):
        """runs: list of (text, fill, font or None); one line of mixed colours."""
        fam, wt, _ = FONTS[font]
        out = []
        self._track("".join(t for t, _, _ in runs), x, font, size)
        for t, fill, f in runs:
            f = f or font
            self.used[f].update(t)
            out.append(f'<tspan font-weight="{FONTS[f][1]}" fill="{self.col(fill)}">{escape(t)}</tspan>')
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{fam}" font-size="{size}" xml:space="preserve" {extra}>{"".join(out)}</text>')

    def rect(self, x, y, w, h, fill="card", r=0, stroke=None, sw=2, extra=""):
        s = f' stroke="{self.col(stroke)}" stroke-width="{sw}"' if stroke else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" fill="{self.col(fill)}"{s} {extra}/>')

    def board(self, x=1, y=1, w=None, h=None, dots=True, stroke=True):
        """Cream sticker board with a faint digital code-matrix rain."""
        w = w or self.w - 2; h = h or self.h - 2
        pid = self.uid("matrix")
        if dots:
            ink = self.col("muted")
            base = 0.10 if self.theme == "light" else 0.09
            # Cascading mono glyphs in columns — denser near the "head" of each stream.
            cols = [
                (6,  "01A7F3",   [0.55, 0.35, 0.22, 0.14, 0.10, 0.07]),
                (18, "C0DE9B",   [0.18, 0.45, 0.30, 0.18, 0.11, 0.07]),
                (30, "7E2F1A",   [0.12, 0.20, 0.50, 0.32, 0.16, 0.09]),
                (42, "B4D801",   [0.08, 0.14, 0.22, 0.48, 0.28, 0.12]),
                (54, "9F3C2E",   [0.10, 0.16, 0.24, 0.18, 0.52, 0.30]),
                (66, "E7A014",   [0.07, 0.12, 0.18, 0.26, 0.20, 0.48]),
            ]
            parts = [f'<pattern id="{pid}" width="78" height="72" patternUnits="userSpaceOnUse">']
            chars = set()
            for cx, stream, opacities in cols:
                for i, (ch, rel) in enumerate(zip(stream, opacities)):
                    chars.add(ch)
                    o = max(0.05, min(0.6, base * 4.2 * rel))
                    gy = 12 + i * 11
                    parts.append(
                        f'<text x="{cx}" y="{gy}" font-family="ZM" font-weight="500" font-size="10" '
                        f'fill="{ink}" text-anchor="middle" opacity="{o:.3f}">{escape(ch)}</text>')
            parts.append("</pattern>")
            self.defs.append("".join(parts))
            self.used["m500"].update(chars)
        self.rect(x, y, w, h, "bg", 18, "line" if stroke else None, 2)
        if dots:
            self.add(f'<rect x="{x + 1}" y="{y + 1}" width="{w - 2}" height="{h - 2}" rx="17" fill="url(#{pid})"/>')
            if stroke:
                # redraw border on top so the matrix fill never covers the ink edge
                self.rect(x, y, w, h, "none", 18, "line", 2)

    def card(self, x, y, w, h, fill="card", r=18, shadow=4, sw=2, rot=0, dashed=False, extra=""):
        g = f'<g transform="rotate({rot} {x + w / 2:.1f} {y + h / 2:.1f})">' if rot else "<g>"
        self.add(g)
        if shadow:
            self.rect(x + shadow, y + shadow, w, h, "line", r)
        d = ' stroke-dasharray="7 5"' if dashed else ""
        self.rect(x, y, w, h, fill, r, "line", sw, d + extra)
        self.add("</g>")

    def chip(self, x, y, label, fill="card", font="m500", size=11, h=20, pad=7, sw=1.5, r=6, shadow=0, tcol="text"):
        w = text_width(label, font, size) + pad * 2
        if shadow:
            self.rect(x + shadow, y + shadow, w, h, "line", r)
        self.rect(x, y, w, h, fill, r, "line", sw)
        self.text(x + w / 2, y + h / 2 + size * 0.36, label, font, size, tcol, "middle")
        return w

    def pill(self, x, y, label, fill="go", tcol=None, size=11):
        tcol = tcol or ("#062b16" if fill == "go" else "text")
        return self.chip(x, y, label, fill, "m500", size, 20, 10, 1.5, 10, 0, tcol)

    def zlogo(self, x, y, s, letter="J"):
        """Letter mark in the design-system sticker style (light colours in both themes)."""
        L = TOK["color"]["light"]
        k = s / 32
        # Approximate centered letter for the 26x26 tile; works for short marks like J / SJ.
        self.add(f'<g transform="translate({x} {y}) scale({k:.3f})"><rect x="4" y="4" width="26" height="26" rx="6" fill="{L["pop"]}"/>'
                 f'<rect x="1.5" y="1.5" width="26" height="26" rx="6" fill="{L["bg"]}" stroke="{L["line"]}" stroke-width="2.5"/>'
                 f'<text x="14.5" y="23" font-family="ZF" font-weight="700" font-size="16" fill="{L["line"]}" text-anchor="middle">{escape(letter)}</text></g>')
        self.used["f700"].update(letter)

    def image(self, x, y, w, h, href, r=0, stroke=True, pixel=False):
        cid = self.uid("clip")
        self.defs.append(f'<clipPath id="{cid}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}"/></clipPath>')
        st = ' style="image-rendering:pixelated"' if pixel else ""
        self.add(f'<image x="{x}" y="{y}" width="{w}" height="{h}" href="{href}" clip-path="url(#{cid})" preserveAspectRatio="xMidYMid slice"{st}/>')
        if stroke:
            self.rect(x, y, w, h, "none", r, "line", 2)

    def render(self):
        faces = []
        for k, chars in self.used.items():
            fam, wt, _ = FONTS[k]
            faces.append(f"@font-face{{font-family:{fam};font-weight:{wt};src:url(data:font/woff2;base64,{_subset_b64(k, chars)}) format('woff2')}}")
        css = "".join(faces) + "".join(self.css)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" '
                f'role="img" aria-label="{escape(self.label)}"><title>{escape(self.label)}</title>'
                f'<defs><style>{css}</style>{"".join(self.defs)}</defs>{"".join(self.parts)}</svg>')

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf8") as f:
            f.write(self.render())
