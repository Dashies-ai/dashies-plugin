---
name: dashies-design
description: >-
  Make a Dashies dashboard genuinely beautiful and tailored to a specific
  company's brand, instead of the default blue-on-white template. Reach for this
  WHENEVER you author, publish, or revise a Dashies dashboard and want it to look
  designed, and ALWAYS when the user says a dashboard looks generic / plain /
  boring / "AI-generated" / vibe-coded / "lacks taste", asks to "make it
  beautiful / look good / more polished", asks to brand it or "make it look like
  <a company>" (Stripe, Spotify, Notion, Linear, a bank, a fintech, their own
  employer, etc.), wants company or brand colors, a themed or dark-mode
  dashboard, a real header, or better typography and hierarchy. It infers the
  company (usually the user's own employer - you generally know it), derives a
  tasteful brand system (accent, neutral ramp, type feel, a simple inline mark),
  retints the Dashies runtime so charts, tables, and controls read as the brand
  rather than default blue, and elevates the page chrome (hero-metric hierarchy,
  header identity, considered surfaces and spacing) - all within the
  self-contained-HTML and strict-CSP constraints. Pairs with the `dashies` skill,
  which builds the refreshable dashboard and its data; this skill makes it
  beautiful. Trigger it even if the user never says "design": any time a Dashies
  dashboard could look better or more on-brand, this is the skill.
---

# Designing a beautiful, on-brand Dashies dashboard

A Dashies dashboard published straight from the `dashies` skill is *correct* but
usually *characterless*: default blue on white, every KPI the same weight, a
plain text header, charts in the runtime's default accent. It reads as "a model
made a clean template." This skill turns that into something that looks like a
specific company built it on purpose.

The whole job is two decisions and their execution:

1. **Whose brand is this?** Almost always the user's own company (you usually
   know where they work). Commit to one brand identity and let it flow through
   everything.
2. **Spend that identity with discipline.** Beauty here is not more decoration -
   it is one considered accent, a real neutral ramp, deliberate hierarchy, and a
   header with identity. Tailor the *brand*; keep the *discipline*.

## The mental model: chrome you own, widgets you retint

A Dashies dashboard is one self-contained HTML file with three parts in `<body>`:
your marked-up **chrome**, a JSON **data island**, and the inlined **runtime**.
Understanding who controls what is the key to styling it:

- **The chrome is 100% yours.** The header, KPI cards, layout grid, section
  titles, backgrounds, spacing, and typography are plain HTML + your `<style>`.
  The runtime only *writes numbers into* the slots you mark with `data-dash`; it
  never restyles your page. This is where brand identity lives.
- **The data widgets are runtime-rendered but fully retintable.** Charts, tables,
  filter `<select>`s, and the default KPI card are drawn by the runtime using CSS
  custom properties on `:root` (`--drt-blue`, `--drt-ink`, `--drt-sans`, ...).
  Redefine those tokens and the widgets adopt your brand - no need to hand-roll
  charts. See **Step 2**.

So: **retint the runtime to the brand, then build beautiful chrome around it.**
Do both and the page reads as one designed thing instead of a template with a
custom title.

Two entry points, same technique:

- **Building a new dashboard** (with the `dashies` skill): use that skill for the
  data, cube, and bindings; use this one for the look. Charts stay
  runtime-rendered so the cron can keep refreshing them.
- **Beautifying an existing dashboard**: apply Steps 1-3 to the HTML you already
  have. If it is a static (non-refreshable) dashboard you *may* hand-roll bespoke
  visuals, but retinting the runtime is usually faster and more cohesive.

---

## Step 1 - Identify the company and derive the brand system

**Pick the company first.** Default to the user's own employer - you generally
know it from context, their email domain, the data, or the conversation. If they
name a different company ("make it look like Stripe"), use that. If the company is
genuinely unknown and unguessable, either ask once, or choose a considered
neutral palette (not the default blue) and say which you picked.

From the company, decide four things. `references/brand-book.md` has a lookup
table of ~24 well-known brands (accent, ink, type feel, aesthetic) plus a method
for brands not in the table and a set of CSP-safe system font stacks. Read it
whenever you are unsure of a brand's colors or feel.

1. **Accent** - the single brand color. One hue, used sparingly (see Step 3). For
   many strong brands this is obvious (Spotify green, Stripe indigo, Notion near-
   black + subtle). Get the *actual* brand hex if you know it; approximate
   tastefully if you do not.
2. **Neutral temperature** - warm gray, cool slate, or near-black. This carries
   most of the design. Match it to the accent: warm brands (coral, orange, red)
   want warm neutrals; cool/tech brands want cool slate; premium/fintech/dev-tools
   often want near-black. A mismatched-temperature neutral is a quiet ugliness.
3. **Type** - identify the company's *actual* typeface, then get as close to it as
   the CSP allows. You cannot fetch a font over the network, but you *can* embed
   one as a base64 `@font-face` (Step 1.5). So decide: is the brand's font freely
   obtainable (open-source / on Google Fonts / a file the user has)? If yes, embed
   the real one. If it is proprietary (Stripe's Söhne, Spotify's Circular, and most
   flagship fonts), embed the closest free match instead, or fall back to a
   characterful system stack. brand-book maps brands to their typeface, whether it
   is embeddable, and the best free match. Keep numbers mono tabular for cohesion.
4. **Light or dark, and the logo.** Some brands are dark-first (many dev-tools,
   fintech, media); if the brand reads dark, build dark (Step 2 has a dark
   scaffold), otherwise light. For the mark, use the company's *real logo* inlined
   as SVG (Step 1.5) - it is their own mark on their own dashboard. If you cannot
   get the logo, fall back to a tasteful monogram tile or a wordmark set in the
   brand font. Never leave the header a plain untreated title.

Write these four down before you touch CSS. They are the whole palette.

**Plan in words, then critique, then code.** Before writing any CSS, state the
plan: the 4-6 hex values with their roles (accent, ink, canvas, surface, line),
the type stack, and the *one signature element* the design will be remembered for
(usually the hero). Then read it back against the Step 4 anti-slop list and
revise - it is far cheaper to catch "this is just the default with a new accent"
in the plan than in the rendered page. Only then build. This single pause is what
separates a considered dashboard from a reskinned template.

---

## Step 1.5 - Embed the real logo and font

The dashboard is one self-contained file served under `sandbox allow-scripts`: no
network, no external fonts or images. But **inline SVG and `data:` URIs are fully
allowed** - this is verified to render under that exact CSP with zero violations -
so you can embed the *real* brand assets, not just approximate them.

### The real logo (inline SVG)

Get the company's official logo as **SVG** (its brand/press page, or a vector-logo
source; `simpleicons.org` has a clean single-path mark for most well-known brands).
Paste the `<svg>` straight into the header markup, size it (~20-36px), and recolor
if needed - a single-color mark takes `fill: currentColor` or the brand color and
sits on light or dark; keep a full-color logo's own fills.

Using a company's own logo on that company's own dashboard is legitimate (their
mark, their dashboard). Do not *bundle* third-party logos into a shared template -
fetch/inline per dashboard. If no SVG is available, fall back to the monogram tile
or wordmark in the brand font (brand-book cookbook).

### The real font (base64 `@font-face`)

Embed the font so it needs no network:

```css
@font-face {
  font-family: 'Brand';
  font-weight: 400;                 /* one @font-face per weight you use */
  src: url(data:font/woff2;base64,<...>) format('woff2');
}
:root { --drt-sans: 'Brand', ui-sans-serif, system-ui, sans-serif !important; }
```

The helper `scripts/embed-font.py "<Google Font family>" <weights>` fetches the
latin-subset woff2 from Google Fonts and prints the ready `@font-face` block (a
latin subset is ~20-40KB base64 per weight - keep to 2-3 weights). Set the embedded
family on `--drt-sans` (and your chrome's display font) so chrome and runtime
widgets share it; the runtime keeps its mono stack for figures.

**Only embed a font you may embed:** open-license (OFL/Apache) fonts, Google Fonts,
or a file the user provides. Proprietary brand fonts (Söhne, Circular, Cereal, ...)
are not freely obtainable - use the closest free match instead. brand-book maps
each brand to its typeface, whether it is embeddable, and the best free match.

---

## Step 2 - Retint the runtime to the brand

This is the highest-leverage move and the one most often skipped. The single
biggest "default template" tell is blue charts and controls sitting next to a
"branded" header. Fix it by redefining the runtime's tokens.

**Why `!important`:** the runtime injects its `<style>` last (at boot), so a
plain `:root { --drt-blue: ... }` in your head *loses* the cascade to the
runtime's own `:root`. Marking your token declarations `!important` wins
regardless of order. Two colors are hardcoded in the runtime rather than
tokenized (the area-chart fill and the select focus ring); override those two
classes directly. That is the entire surface - there is nothing else to chase.

Drop this block into your `<style>` and swap the values for your brand (example
values shown are an indigo/near-black fintech feel):

```css
/* ---- Brand retint of the Dashies runtime -----------------------------------
   Redefine the runtime's :root tokens (!important beats its late-injected
   style) so charts, tables, selects and focus rings read as the brand. Then
   override the two hardcoded spots. color-mix ties them to the accent; an
   rgba() literal is a fine fallback on older engines. */
:root {
  /* accent: the one brand colour - chart series, line/bar/area, dots, focus */
  --drt-blue:        #635bff !important;  /* brand primary                    */
  --drt-blue-700:    #4b45d6 !important;  /* darker: bar/line hover           */
  --drt-blue-soft:   #f0efff !important;  /* faint accent wash                */
  /* text ramp: ink is your near-black; keep the greys descending + legible   */
  --drt-ink:         #0a1636 !important;
  --drt-muted:       #45507a !important;
  --drt-subtle:      #6b769c !important;
  --drt-faint:       #9aa2be !important;
  /* surfaces + hairlines: harmonise temperature with the accent              */
  --drt-surface:     #ffffff !important;
  --drt-sunken:      #f7f8fc !important;
  --drt-line:        #e7e9f3 !important;
  --drt-line-strong: #ced2e6 !important;
  --drt-grid:        #eef0f8 !important;
  /* type: a CSP-safe system stack that evokes the brand (no web fonts)        */
  --drt-sans: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif !important;
  --drt-mono: ui-monospace, 'SF Mono', 'JetBrains Mono', Menlo, monospace !important;
}
/* the two hardcoded runtime colours */
.drt-area { fill: color-mix(in srgb, var(--drt-blue) 12%, transparent) !important; }
.drt-select:focus-visible {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--drt-blue) 22%, transparent) !important;
}
```

Match your *chrome* CSS to these same tokens (or just reuse the variables -
`var(--drt-blue)`, `var(--drt-ink)`, ... - so your header and KPI cards share one
palette with the widgets by construction). Tint the neutrals a few percent toward
the accent rather than using pure grays: a canvas of `color-mix(in srgb,
var(--drt-blue) 4%, white)` reads "designed," `#f5f5f5` reads "template." The
example values above are already lightly cool-tinted for the indigo accent.
`references/runtime-theme.md` documents every token, what each one paints, a full
**dark-mode** scaffold, and the cascade gotchas. Read it when you theme.

Two rules that keep a refreshable dashboard valid while you restyle:

- **Do not touch the data island** (`<script id="dashies-data">`) or wrap/move
  it. The refresh cron rewrites it by id; styling lives in `<head>` and your
  markup only.
- **Keep charts runtime-rendered** on refreshable dashboards. Retint them; do not
  replace them with hand-drawn SVG the cron cannot update.

---

## Step 3 - Elevate the chrome

Retinting fixes the color tell. These moves fix the *shape* tells - the things
that make a competent dashboard still feel un-designed. Each is a small change
with a large effect; do them in order.

### 3a. Establish hierarchy - one thing is biggest

The default template makes every KPI identical, so the eye has nowhere to land.
Choose the **one metric that matters most** and make it dominant: larger figure,
more room, often the accent color or a subtle accent-tinted card, with a short
supporting line (a label plus context, e.g. a comparison or a definition). Demote
the rest to a quieter secondary row. A single dominant number is the fastest way
a layout starts to read as "designed."

Spend your boldness in *one* place. Pick a single signature element - almost
always the hero - and let it be large and confident; keep everything else quiet
and supporting. A page where three things all shout reads as noise; a page with
one clear focal point reads as design. The hero figure should be roughly 3x the
size of its label.

> Instead of four equal 28px KPIs in a `repeat(4,1fr)` row, try one hero card
> (spanning two columns, ~40-48px figure) plus a row of smaller supporting KPIs.

### 3b. Give the header an identity

The default header is a plain `<h1>` + subtitle. Add, in restraint:

- A **mark**: the company's real logo inlined as SVG (Step 1.5) paired with the
  wordmark - or, if the logo is unavailable, a monogram tile / short wordmark set
  in the brand font. Inline SVG or styled text only.
- A **brand moment**: a thin accent rule under the header, or a subtle
  accent-tinted band / soft gradient behind the title area. One, not all.
- A tidy **meta line**: title, a real subtitle that says what the dashboard is,
  and the `data-dash="updated-at"` freshness stamp, arranged with clear weight
  contrast (bold title, quiet subtitle).

This is the first impression; spend a little care here and the whole page lifts.

### 3c. Commit to one surface treatment

Pick a single card style and use it everywhere - mixing borders and shadows at
random is the classic slop tell:

- **Flat/precise** (tech, BI): cards on a lightly tinted canvas, hairline border,
  no shadow. Sober and legible.
- **Lifted/product**: cards on white/near-white with one soft shadow, minimal or
  no border. Warmer, more consumer.

Add depth with *one* soft shadow token or a 1px top highlight, never a pile of
drop shadows. Keep radii consistent (one value, e.g. 10-14px). A tinted canvas
(`--drt-sunken`-ish) behind white cards instantly reads as more considered than
white-on-white.

### 3d. Type scale and rhythm

- Use a real scale with big jumps and weight/tracking contrast, not just size:
  e.g. hero ~40-46, section titles ~13 semibold, KPI labels ~11-12 uppercase with
  letter-spacing, body ~13-14. Timid 14/16/18 steps read as a template; a 3x jump
  from label to hero reads as design.
- Think in three type roles: a **display** stack (the characterful one, used with
  restraint on the title/hero), a quiet **body/label** stack, and a **mono** stack
  for every number. Since you cannot load the brand's real font, this split plus
  weight/size contrast is where personality comes from - see brand-book for
  CSP-safe stacks per feel. Keep numbers in mono tabular figures (match the
  runtime) so columns align.
- Space on a consistent 8-based rhythm. Group related cards tightly; separate
  sections with air. Let the hero breathe. Cramped, uniform spacing is a tell.

### 3e. Accent discipline

Spend the accent on: the primary chart series (done by the retint), the hero
figure or a key affordance, links, focus rings, and the header mark. **Not** on
every border, label, or card background. Restraint is what makes the accent read
as intentional rather than decorative. When in doubt, move a color to a neutral.

---

## Step 4 - Anti-slop checklist

Before publishing, scan for the tells that make AI dashboards look generic. Each
line is a thing to *not* do:

- Shipping the runtime's default blue on the charts (retint - Step 2).
- Copying the default `--blue/--ink/--slate` tokens verbatim into your chrome
  (that is literally the template; derive real brand values).
- Every KPI the same size (no hero - Step 3a).
- A plain text-only header with no mark or brand moment (Step 3b).
- Borders *and* shadows mixed at random across cards (pick one - Step 3c).
- Rainbow / multi-color categorical bars (Dashies charts are single-accent by
  design; keep them so).
- Gradient-on-everything, glassmorphism, neon glow, heavy drop-shadows, giant
  20px+ radii, emoji in the header, centered-everything, decorative icons that
  carry no meaning. Precision beats decoration.
- Low-contrast gray-on-gray text (keep `--drt-ink` genuinely dark; check WCAG on
  the accent if you put text on it).
- Mismatched neutral temperature (warm brand + cold slate greys, or vice versa).
- A colored left-border stripe on *every* card "for variety" - reserve a rule for
  one semantic role (e.g. severity) or drop it.
- Container soup: card-inside-card-inside-pill. Keep to two levels of surface
  nesting; use a border or a tonal shift instead of another card.
- Mixed icon sets, or a pulsing "live" dot as decoration. One inline-SVG icon
  style; motion only for real state changes (the runtime already handles its own).
- Generic filler copy ("Welcome to <Product>", "Get started"). Use real, specific
  labels that say what the number or section is.
- Inventing metrics, deltas, or trend arrows the data does not actually contain.

If the dashboard passes this list and commits to one brand, it will look designed.

---

## Constraints (do not break these)

- **Self-contained + strict CSP.** One HTML file. No external fonts, CDN, remote
  images, or network calls - inline CSS/JS/SVG, system font stacks, `data:` URIs
  only. No `localStorage` / cookies (opaque-origin sandbox). The `dashies` skill
  covers this in full; do not regress it while styling.
- **Refreshable dashboards stay refreshable.** Never edit or relocate the
  `<script id="dashies-data">` island; never replace runtime charts with static
  SVG on a refreshable dashboard; never script-replace `<body>` (it clobbers the
  "Powered by Dashies" badge).
- **Sober copy, no em dashes.** Titles and labels stay plain and precise. Use
  ASCII hyphens, never em/en dashes, anywhere in the dashboard. No time estimates
  or hype. Do not describe features the dashboard does not have.
- **Accessibility.** Real contrast, visible focus (the retinted focus ring),
  respect `prefers-reduced-motion` (the runtime already does).

---

## Worked transformation (before -> after)

**Before** (the default template): `:root` copies the runtime tokens verbatim
(`--blue:#2563eb`, slate ramp, Inter/JetBrains); four equal 28px KPIs; a plain
`<h1>Acme Commerce - Revenue Analytics</h1>`; white cards with hairline borders;
charts in default blue. Correct, generic.

**After** (Acme rebuilt as, say, a fintech brand):

1. **Derive**: accent indigo `#635bff`; near-black cool-neutral ramp; geometric
   system stack; light, with a rounded "A" monogram tile in the accent.
2. **Retint**: paste the Step 2 block with those values - charts, the revenue
   area, table headers, and the filter selects all go indigo.
3. **Chrome**: a header with the monogram tile + wordmark + a thin accent rule;
   a hero "Revenue $3.06M" card spanning two columns at 44px with a quiet "last
   90 days" subline; a secondary row of smaller KPIs; all cards flat on a faintly
   tinted canvas with one radius; an 8-based spacing rhythm.
4. **Check**: run Step 4 - single accent, one hero, header identity, one surface
   style, no invented deltas.

Same data, same runtime, same refresh behavior - a dashboard that now looks like
Acme's own team designed it.

---

### Reference files

- `references/brand-book.md` - the company -> brand-system lookup (24 brands),
  the derivation method for brands not listed, warm/cool/near-black neutral ramps,
  CSP-safe system font stacks, **the brand -> real-typeface -> embeddable? ->
  closest-free-match table, and where to source real logos**. **Read it to pick
  colors, type, the real font, and the logo.**
- `scripts/embed-font.py` - fetches a Google Font's latin-subset woff2 and prints
  a ready base64 `@font-face` block to inline (the real-font mechanism, Step 1.5).
- `references/runtime-theme.md` - every `--drt-*` token and what it paints, the
  two hardcoded overrides, a full light + dark retint scaffold, and the cascade
  gotchas. **Read it while theming.**
- `assets/gallery/` - two worked reference dashboards (chrome + retint only):
  `meridian-light.html` (light indigo fintech) and `halo-dark.html` (dark
  near-black + cyan). Read or copy one as a starting point - they show the header
  identity, hero hierarchy, card layout, and the retint block in context. Drop in
  the `dashies` data island + runtime to make them live.
