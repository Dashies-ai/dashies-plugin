#!/usr/bin/env python3
"""Embed a Google Font as base64 @font-face for a self-contained dashboard.

A Dashies dashboard is served under `sandbox allow-scripts` and cannot load a
font over the network. This fetches a font's latin-subset woff2 from Google Fonts
and prints a ready `@font-face` block whose src is a `data:` URI, so the real font
ships inside the HTML with no network call. Verified to render under that CSP.

Usage:
    python3 embed-font.py "<Google Font family>" [weights] [--subset latin|latin-ext]

Examples:
    python3 embed-font.py "Geist" 400,600,700
    python3 embed-font.py "Montserrat" 500,700          # closest free match to a proprietary brand font
    python3 embed-font.py "IBM Plex Sans"               # defaults to weight 400

Paste the printed block into your dashboard <style>, then point the runtime + your
chrome at it:
    :root { --drt-sans: 'Family', ui-sans-serif, system-ui, sans-serif !important; }

Only use fonts you may embed: open-license (OFL/Apache) or Google Fonts families
(Google Fonts are served for use on the open web; their licenses permit web
embedding). Do not use this to redistribute a proprietary font you are not
licensed for - pick the closest free family instead (see brand-book.md).

Notes:
- A latin subset of one weight is ~15-40KB (base64 ~20-55KB). Keep to 2-3 weights.
- For an even smaller file, subset to just the glyphs a dashboard needs with
  fonttools:  pyftsubset font.woff2 --unicodes="U+0030-0039,U+0041-005A,U+0061-007A,U+0020-002F,U+0024,U+0025,U+002C,U+002E" --flavor=woff2
- stdout is the @font-face CSS; a size summary goes to stderr.
"""
import sys
import re
import base64
import urllib.request
import urllib.parse

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
# unicode-range signatures that identify each subset block in the Google CSS
SUBSET_SIGNATURE = {"latin": "U+0000-00FF", "latin-ext": "U+0100-02BA"}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main() -> int:
    args = [a for a in sys.argv[1:] if a]
    if not args:
        print(__doc__)
        return 1
    subset = "latin"
    if "--subset" in args:
        i = args.index("--subset")
        subset = args[i + 1]
        del args[i:i + 2]
    family = args[0]
    weights = args[1] if len(args) > 1 else "400"
    weight_list = ",".join(w.strip() for w in weights.split(",") if w.strip())
    sig = SUBSET_SIGNATURE.get(subset)
    if not sig:
        print(f"error: unknown subset {subset!r} (use latin or latin-ext)", file=sys.stderr)
        return 1

    css_url = (f"https://fonts.googleapis.com/css2?family="
               f"{urllib.parse.quote(family)}:wght@{weight_list.replace(',', ';')}&display=swap")
    try:
        css = fetch(css_url).decode()
    except Exception as e:  # noqa: BLE001
        print(f"error: could not fetch Google Fonts CSS for {family!r}: {e}", file=sys.stderr)
        print("check the family name (exact spelling/case) at fonts.google.com", file=sys.stderr)
        return 1

    blocks = re.findall(r"@font-face\s*\{[^}]*\}", css, re.S)
    out, total = [], 0
    for b in blocks:
        if sig not in b:  # keep only the requested subset
            continue
        wm = re.search(r"font-weight:\s*(\d+)", b)
        um = re.search(r"src:\s*url\((https://[^)]+\.woff2)\)", b)
        if not (wm and um):
            continue
        data = fetch(um.group(1))
        total += len(data)
        b64 = base64.b64encode(data).decode()
        out.append(
            f"@font-face{{font-family:'{family}';font-style:normal;font-weight:{wm.group(1)};"
            f"font-display:swap;src:url(data:font/woff2;base64,{b64}) format('woff2');}}")
        print(f"  weight {wm.group(1)}: woff2 {len(data):,}B -> base64 {len(b64):,} chars",
              file=sys.stderr)

    if not out:
        print(f"error: no {subset} @font-face found for {family!r} weights {weight_list}",
              file=sys.stderr)
        return 1
    print("\n".join(out))
    print(f"embedded {len(out)} weight(s) of {family!r}: {total:,}B woff2 total. "
          f"Set --drt-sans to '{family}'.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
