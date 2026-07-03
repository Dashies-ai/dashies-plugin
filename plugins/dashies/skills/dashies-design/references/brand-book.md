# Brand book: deriving a design system from a company

Everything you need to turn a company name into the four decisions from Step 1:
**accent, neutral temperature, type feel, light/dark + mark.** Use the lookup
table for known brands, the method for everything else, and the font + mark
cookbooks to execute.

Brand hexes below are best-known approximations. If you know a company's exact
brand color, use it. The goal is a dashboard that reads as *that* company, not a
pixel-perfect trademark reproduction.

---

## The derivation method (for any company)

When you know a company only from general knowledge, reason in this order:

1. **Accent - one hue.** Recall the brand's primary color (the logo, the buttons
   on their site, their marketing). Pick the single most identifying hue. If the
   brand is famously monochrome (Vercel, Uber, Notion), the "accent" is near-black
   and the personality comes from type + restraint, so choose one small secondary
   color for the data series (a quiet blue or the brand's one spot color).
2. **Neutral temperature - warm / cool / near-black.** Look at the accent:
   - Warm accent (red, coral, orange, amber, warm green) -> warm gray / stone
     neutrals (a hint of brown/red in the grays).
   - Cool accent (blue, indigo, teal, cyan, violet) -> cool slate neutrals.
   - Premium / fintech / dev-tools -> near-black ink with either temperature.
   The neutral ramp is ~80% of the pixels, so getting its temperature right
   matters more than the exact accent.
3. **Type feel.** Map the brand's personality to a category, then pick a system
   stack (below) that evokes it - you cannot load their real font under the CSP:
   - Geometric / modern / friendly-tech -> geometric stack.
   - Humanist / approachable / consumer -> humanist stack.
   - Neutral / corporate / enterprise -> grotesk/neutral stack.
   - Editorial / premium / publishing -> serif headlines.
   - Technical / developer / data -> mono-forward.
4. **Light or dark + a mark.** If the brand's own product/site is dark-first (many
   dev-tools, fintech, media, gaming), build dark. Otherwise light. Add one simple
   brand moment: a monogram tile, a wordmark, or a small abstract SVG mark (see the
   mark cookbook). Never a fetched or copied logo.

When the company is **unknown or generic**, do not fall back to the Dashies
default blue. Pick one of the curated palettes below and say which you chose.

---

## Known-brand lookup

| Brand | Accent | Ink (near-black) | Neutral | Type feel | Light/Dark | Aesthetic |
|---|---|---|---|---|---|---|
| Stripe | `#635BFF` | `#0A2540` | cool | geometric-humanist | light | clean, technical, trustworthy |
| Spotify | `#1DB954` | `#191414` | warm-neutral | bold grotesk | dark | energetic, music, bold |
| Airbnb | `#FF5A5F` | `#222222` | warm | humanist rounded | light | friendly, approachable |
| Notion | `#2383E2` (spot) on near-black | `#191919` | cool-neutral | humanist | light | minimal, editorial, calm |
| Linear | `#5E6AD2` | `#08090A` | cool | grotesk (Inter-like) | dark | precise, fast, sharp |
| Vercel | `#000000` (+ one spot blue for series) | `#000000` | pure neutral | grotesk (Geist) | dark | stark, monochrome, technical |
| Netflix | `#E50914` | `#141414` | neutral-dark | bold grotesk | dark | cinematic, bold |
| Shopify | `#008060` | `#1A1A1A` | warm-neutral | humanist | light | commerce, sturdy, friendly |
| Slack | `#4A154B` | `#1D1C1D` | warm | rounded humanist | light | playful-professional |
| Figma | `#0D99FF` | `#1E1E1E` | cool-neutral | grotesk | light | creative, tool, colorful |
| Coinbase | `#0052FF` | `#0A0B0D` | cool | grotesk | light/dark | fintech, trust, clean |
| Robinhood | `#00C805` | `#000000` | neutral-dark | grotesk | dark | bold, modern finance |
| Datadog | `#632CA6` | `#1D1D1D` | cool | grotesk | dark/light | observability, technical |
| Snowflake | `#29B5E8` | `#11567F` | cool | humanist | light | data, cloud, bright |
| Ramp | `#DAFB3C` (warm accent) | `#1C1B17` | near-black | grotesk | dark/light | minimal, near-black + one accent |
| Mercury | `#4D68EB` | `#1F1F30` | cool | grotesk | light | banking for startups, refined |
| Duolingo | `#58CC02` | `#3C3C3C` | warm | rounded | light | playful, friendly |
| Anthropic / Claude | `#D97757` (clay) | `#141413` | warm (cream canvas `#FAF9F5`) | humanist + serif accents | light | warm, thoughtful, human |
| OpenAI | `#10A37F` (or near-black) | `#0D0D0D` | neutral | grotesk | light/dark | clean, research, mono |
| Google | `#4285F4` | `#202124` | cool-neutral | humanist-geometric | light | friendly, multi-color |
| Amazon | `#FF9900` | `#232F3E` | neutral | grotesk (Ember) | light | commerce, utilitarian |
| Microsoft | `#0078D4` | `#201F1E` | neutral | humanist (Segoe) | light | enterprise, clear |
| Salesforce | `#00A1E0` | `#032D60` | cool | humanist | light | cloud, enterprise, friendly |
| Discord | `#5865F2` | `#23272A` | cool | rounded grotesk | dark | playful, community |

Notes on the monochrome brands (Vercel, Uber, Notion): keep the chrome near-black
and quiet, and give the chart series *one* restrained color (a brand spot color or
a muted blue) so the data still reads - a pure-black bar chart is unreadable.

**The dominant pattern, and the safe default.** Fintech and dev-tools brands
cluster hard on **near-black ground + exactly one accent** (Vercel, Uber, Ramp,
Linear, Coinbase, Mercury, Robinhood, Notion, OpenAI). Consumer and creative
brands go **polychrome** (Google, Slack, Figma, Microsoft, Duolingo) - but on a
dense data dashboard, one accent almost always reads more premium than many. So
when a brand is ambiguous or you are unsure, default to **near-black (or a tinted
off-white) ground with a single accent**; it is the hardest look to get wrong.

---

## Curated palettes for unknown / generic companies

Never default to the runtime blue. Pick one of these and commit. Each is
`accent / ink / neutral temperature`.

| Name | Accent | Ink | Neutral | Good for |
|---|---|---|---|---|
| Indigo | `#635BFF` | `#0F1633` | cool | tech, fintech, SaaS |
| Emerald | `#0E9F6E` | `#0B1F17` | warm-neutral | growth, finance, health |
| Teal | `#0D9488` | `#0C1A1A` | cool | data, calm, infra |
| Amber | `#EA580C` | `#1C1410` | warm | commerce, energy, ops |
| Rose | `#F43F5E` | `#1A0F14` | warm | consumer, creative, brand |
| Violet | `#7C3AED` | `#160E2B` | cool | creative, AI, observability |
| Cyan | `#0891B2` | `#0A1A20` | cool | cloud, analytics |
| Graphite | `#111827` + spot `#3B82F6` | `#0B0F19` | near-black | premium, minimal, executive |

---

## Real fonts: embed the brand's typeface

You cannot fetch a font over the network under the CSP, but you *can* embed one as
a base64 `@font-face` `data:` URI (SKILL Step 1.5, verified to render). So prefer
the *real* font when you are allowed to embed it, and fall back only when you are
not. The decision, in order:

1. **The brand's font is open / on Google Fonts / a file the user has** -> embed
   the real one. Run `scripts/embed-font.py "<family>" <weights>` to get the block.
2. **The brand's font is proprietary** (not freely obtainable) -> embed the closest
   free Google Font match from the table below. You may not redistribute a
   proprietary font you are not licensed for.
3. **You want zero embedded bytes** -> use a characterful system stack (next
   section). Lightest, but only an approximation.

Then set the embedded family on the runtime + your chrome:
`:root { --drt-sans: '<Family>', ui-sans-serif, system-ui, sans-serif !important; }`

**Brand -> typeface -> what to embed.** Several brands' fonts are genuinely open
(embed the real one); the rest map to a close free match. Hexes for the closest
match are all on Google Fonts.

| Brand | Its typeface | Embed this (`embed-font.py "<family>"`) |
|---|---|---|
| Vercel | Geist (OFL) | **Geist** - the real font |
| IBM | IBM Plex (OFL) | **IBM Plex Sans** - the real font |
| GitHub | Mona Sans (OFL) | **Mona Sans** - the real font |
| Linear | Inter (open) | **Inter** - the real font |
| Google | Roboto / Product Sans | **Roboto** - the real UI font |
| Slack | Larsseit (was Lato) | **Lato** - the classic Slack font, open |
| Stripe | Söhne (proprietary) | Inter (or Hanken Grotesk) |
| Figma | Inter product UI (open); Whyte display | **Inter** for UI; Space Grotesk for display |
| Coinbase | Coinbase Sans (verify license) | Inter (safe) |
| Uber | Uber Move (proprietary) | Inter (or Archivo) |
| Ramp / Mercury / Datadog | custom grotesk (proprietary) | Inter |
| Shopify | Shopify Sans (proprietary) | Inter |
| Spotify | Circular (proprietary) | Plus Jakarta Sans (or Figtree) |
| Airbnb | Cereal (proprietary) | DM Sans (or Plus Jakarta Sans) |
| Duolingo | Feather / DIN Round (proprietary) | Nunito (or Quicksand) |
| Netflix | Netflix Sans (proprietary) | Archivo (or Roboto) |
| Amazon | Ember (proprietary) | Open Sans (or Source Sans 3) |
| Microsoft | Segoe UI (Windows system) | system-ui, else Open Sans |
| Notion | Inter UI (open) + Lyon serif | **Inter** (real UI); Source Serif 4 for a serif headline |
| Anthropic | Styrene + Tiempos (proprietary) | Inter + Lora (or Source Serif 4) |
| OpenAI | Söhne + Signifier (proprietary) | Inter + a serif |

Match by feel when a brand is not listed: neo-grotesque -> Inter / Hanken Grotesk;
geometric -> Plus Jakarta Sans / DM Sans / Montserrat; rounded -> Nunito / Quicksand;
humanist -> Open Sans / Source Sans 3; serif -> Lora / Source Serif 4 / Newsreader.

## System font stacks (the fallback)

When you cannot embed the real font - it is proprietary, or you want zero embedded
weight - approximate the feel with a *specific, characterful* system stack, not the
generic `system-ui` default (itself a slop tell), and manufacture personality with
weight, size, tracking, and case contrast (the character you would normally buy
with a font, you buy here with the treatment). These stacks use only fonts that
ship on macOS/iOS/Windows/Android, with graceful fallbacks (source:
modernfontstacks.com).

```css
/* Geometric-modern - Stripe, Airbnb, Spotify, Coinbase, modern SaaS */
--display: Avenir, Montserrat, Corbel, 'URW Gothic', 'Century Gothic', system-ui, sans-serif;

/* Neo-grotesque (tight, Swiss) - Linear, Vercel, Uber, Netflix, dev-tools */
--display: 'Helvetica Neue', 'Arial Nova', 'Nimbus Sans', Arial, system-ui, sans-serif;

/* Humanist-friendly - Duolingo, Shopify, Salesforce, Snowflake, consumer */
--display: Seravek, 'Gill Sans Nova', Ubuntu, Calibri, 'DejaVu Sans', system-ui, sans-serif;

/* Classical-humanist (elegant sans) - premium, calm */
--display: Optima, Candara, 'Noto Sans', 'Segoe UI', system-ui, sans-serif;

/* Rounded-friendly - Duolingo, Discord, playful consumer */
--display: ui-rounded, 'Hiragino Maru Gothic ProN', Quicksand, 'Arial Rounded MT Bold', Calibri, system-ui, sans-serif;

/* Industrial / condensed - logistics, sports, bold KPI numerals */
--display: Bahnschrift, 'DIN Alternate', 'Franklin Gothic Medium', 'Nimbus Sans Narrow', sans-serif-condensed, sans-serif;

/* Editorial-serif (transitional) - finance gravitas, reports */
--display: Charter, 'Bitstream Charter', 'Sitka Text', Cambria, Georgia, serif;

/* Editorial-serif (old-style, warm) - Notion-like, human */
--display: 'Iowan Old Style', 'Palatino Linotype', Palatino, Georgia, serif;

/* Body / labels - quiet native default (pairs under any display) */
--body: system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;

/* Mono - every number + technical/dev-tools feel */
--mono: ui-monospace, 'SF Mono', 'Cascadia Code', 'JetBrains Mono', Menlo, Consolas, monospace;
```

**Pairing recipe:** one **display** stack (characterful, used with restraint on
title/hero), the **body** stack for labels and prose, and the **mono** stack for
every number. Keep numbers in mono with `font-variant-numeric: tabular-nums
slashed-zero` so figures align in columns - it matches the runtime and reads as
data software. When you set the runtime's `--drt-sans`, use the display or body
stack; the runtime already uses a mono stack for its figures. Reserve serif for
headlines of editorial/finance brands; keep labels and numbers sans/mono even
then.

---

## Logos and marks (CSP-safe)

A brand mark in the header lifts it from "text" to "identity." **Prefer the
company's real logo, inlined as SVG** (SKILL Step 1.5): get it from the brand's
press/brand page or a vector-logo source (`simpleicons.org` gives a clean
single-path mark for most well-known brands), paste the `<svg>` straight into the
header, size it ~20-36px, and recolor a single-color mark with `fill: currentColor`
or the brand color (keep a full-color logo's own fills). It is the company's own
mark on the company's own dashboard. Do not *bundle* third-party logos into a
shared template - inline per dashboard.

When you cannot get an SVG logo, fall back to one of these type-based marks:

**Monogram tile** - the most reliable. A rounded square with the brand initial(s):

```html
<span class="mark">A</span>
```
```css
.mark {
  display: inline-flex; align-items: center; justify-content: center;
  width: 34px; height: 34px; border-radius: 9px;
  background: var(--accent); color: #fff;
  font: 700 17px/1 var(--sans); letter-spacing: -.02em;
  box-shadow: 0 1px 2px rgba(0,0,0,.12), inset 0 1px 0 rgba(255,255,255,.15);
}
```

**Wordmark** - the company name set tight in the brand type feel, optionally with
a colored dot or the initial in the accent:

```html
<span class="wordmark">Acme<span style="color:var(--accent)">.</span></span>
```
```css
.wordmark { font: 650 18px/1 var(--sans); letter-spacing: -.02em; color: var(--ink); }
```

**Abstract SVG mark** - a simple geometric shape in the accent (a rounded chevron,
a stacked-bars glyph, a ring). Keep it inline, small (~24-34px), and generic:

```html
<svg width="30" height="30" viewBox="0 0 30 30" aria-hidden="true">
  <rect x="3"  y="14" width="6" height="13" rx="2" fill="var(--accent)"/>
  <rect x="12" y="8"  width="6" height="19" rx="2" fill="var(--accent)" opacity=".7"/>
  <rect x="21" y="3"  width="6" height="24" rx="2" fill="var(--accent)" opacity=".45"/>
</svg>
```

Pair the mark with the title and the freshness stamp in the header, with clear
weight contrast (bold title, quiet subtitle). One mark, not three - restraint is
the brand.
