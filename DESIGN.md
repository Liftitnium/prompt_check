---
name: PromptCheck Dispatch
description: Regression testing for LLM prompts, dressed as a packing slip and carrier label on kraft board.
colors:
  kraft: "#c39a6b"
  kraft-ink: "#2a1c0d"
  label: "#fcfcfb"
  label-2: "#eff0f0"
  ink: "#121110"
  ink-2: "#4a4640"
  ink-3: "#6b665e"
  hair: "#d5d6d5"
  hold: "#e0521f"
  hold-ink: "#a8370d"
  hold-tint: "#fde6db"
  ship: "#1d7a4b"
  ship-tint: "#ddefe3"
  run: "#2d5b8a"
  ship-on-plate: "#3fbf7f"
  plate-rule: "#3a3734"
  plate-caption: "#bdb7ad"
typography:
  stamp:
    fontFamily: "Archivo, Helvetica Neue, Arial, sans-serif"
    fontSize: "clamp(64px, 11vw, 132px)"
    fontWeight: 900
    lineHeight: 0.82
    letterSpacing: "0.02em"
    fontVariation: "\"wdth\" 62"
  display:
    fontFamily: "Archivo, Helvetica Neue, Arial, sans-serif"
    fontSize: "clamp(40px, 6vw, 64px)"
    fontWeight: 900
    lineHeight: 0.92
    letterSpacing: "-0.005em"
    fontVariation: "\"wdth\" 62"
  route:
    fontFamily: "Archivo, Helvetica Neue, Arial, sans-serif"
    fontSize: "40px"
    fontWeight: 900
    lineHeight: 0.9
    fontVariation: "\"wdth\" 62"
  headline:
    fontFamily: "Archivo, Helvetica Neue, Arial, sans-serif"
    fontSize: "26px"
    fontWeight: 900
    lineHeight: 1
    letterSpacing: "0.01em"
    fontVariation: "\"wdth\" 68"
  title:
    fontFamily: "Archivo, Helvetica Neue, Arial, sans-serif"
    fontSize: "18px"
    fontWeight: 800
    lineHeight: 1.3
  body:
    fontFamily: "Archivo, Helvetica Neue, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "\"tnum\" 1"
  small:
    fontFamily: "Archivo, Helvetica Neue, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Archivo, Helvetica Neue, Arial, sans-serif"
    fontSize: "11px"
    fontWeight: 800
    lineHeight: 1.3
    letterSpacing: "0.12em"
    fontVariation: "\"wdth\" 70"
  mono:
    fontFamily: "JetBrains Mono, ui-monospace, Menlo, monospace"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.6
  barcode-caption:
    fontFamily: "JetBrains Mono, ui-monospace, Menlo, monospace"
    fontSize: "9px"
    fontWeight: 400
    letterSpacing: "0.22em"
rounded:
  sheet: "2px"
  chip: "3px"
  field: "4px"
  button: "5px"
  stamp-plate: "10px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "14px"
  lg: "20px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.label}"
    typography: "{typography.body}"
    rounded: "{rounded.button}"
    padding: "9px 14px 8px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.button}"
    padding: "9px 14px 8px"
  button-ghost-hover:
    backgroundColor: "{colors.label-2}"
  button-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.button}"
  button-small:
    padding: "6px 10px 5px"
    typography: "{typography.small}"
  input-text:
    backgroundColor: "#ffffff"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "9px 11px"
  sheet:
    backgroundColor: "{colors.label}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sheet}"
  sheet-foot:
    backgroundColor: "{colors.label-2}"
    padding: "12px 20px"
  field-cell:
    textColor: "{colors.ink}"
    padding: "10px 16px 12px"
  masthead-strip:
    backgroundColor: "{colors.label}"
    textColor: "{colors.ink}"
    height: "56px"
  stamp-ship:
    textColor: "{colors.ship}"
    rounded: "{rounded.field}"
    padding: "6px 10px 5px"
  stamp-hold:
    textColor: "{colors.hold}"
    rounded: "{rounded.field}"
    padding: "6px 10px 5px"
  verdict-plate:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.label}"
  delta-bad:
    backgroundColor: "{colors.hold}"
    textColor: "#ffffff"
    typography: "{typography.mono}"
  chip-kv:
    backgroundColor: "{colors.label-2}"
    typography: "{typography.mono}"
    rounded: "{rounded.chip}"
    padding: "1px 6px"
  meter-track:
    height: "14px"
    rounded: "{rounded.sheet}"
---

# Design System: PromptCheck Dispatch

> This file records the UI's visual system only. The system architecture (requirements, components, ADR references) lives in [docs/DESIGN.md](docs/DESIGN.md).

## Overview

**Creative North Star: "The Dispatch Dock"**

Every prompt version is a parcel on the dock. Its paperwork is a white direct-thermal label laid on brown kraft board: heavy 2px black rules, boxed fields with tiny caps labels, a routing code printed huge, a scannable barcode. The release decision gets stamped onto the paperwork, SHIP in dock green or HOLD in orange, and on the comparison view the stamp lands on a reversed black plate. The interface reads as logistics paperwork rather than a dashboard. There is no sidebar and no KPI card grid; the manifest is a single ruled table.

Density is that of a working document: tabular numerals, ruled rows, caps field labels over bold values. Heavy condensed caps (Archivo at 62 to 70% width) carry identity and hierarchy, plain Archivo carries reading text, and JetBrains Mono carries anything the API or the model produced verbatim (template text, outputs, deltas, raw verdicts). Colour is scarce. Most surfaces are black on white label stock, and the two signal colours each mean one thing.

**Key Characteristics:**
- Kraft board ground (procedural SVG fibre noise, no raster) with white label sheets on top.
- 2px black rules for structure, 1px ink rules inside, 1px hair rules between list rows.
- Condensed heavy caps for titles, routing codes and stamps; 11px wide-tracked caps for every field label.
- Orange is reserved for regressions and HOLD. Green belongs to SHIP and passing checks.
- One reversed black surface per product: the verdict plate.
- One authored motion moment: the verdict stamp lands.

## Colors

The palette is restrained: black ink on label stock over kraft board, plus two signal colours that are never decoration.

### Primary
- **Thermal Ink** (ink): every rule, every primary button, body text, the filled meter bar, the verdict plate. Plain failures (`fail`, `error`, `failed` statuses, error messages) are also ink; failure alone is not a regression.

### Secondary
- **Hold Orange** (hold): the HOLD stamp, the hold-coloured meter fill on a held manifest row, and bad deltas on the verdict plate. Text on label stock uses **Hold Ink** (hold-ink) instead for legibility (regressed tally link, the regressed group heading, its "why" text). **Hold Tint** (hold-tint) is the hover wash on a held manifest row.
- **Dock Green** (ship): the SHIP stamp, `pass` status chips, the fixed tally link, diff additions (on **Ship Tint**, ship-tint). On the black plate green lifts to **Plate Green** (ship-on-plate) so the stamp stays legible.

### Tertiary
- **Conveyor Blue** (run): only for in-flight states, `pending` and `running`. Never for links or actions.

### Neutral
- **Kraft Board** (kraft): the page ground under every sheet, and the scrollbar track.
- **Kraft Ink** (kraft-ink): text printed directly on the board (breadcrumbs).
- **Label Stock** (label): sheet and masthead surface; text colour on the plate.
- **Label Shade** (label-2): table header bands, sheet footers, hover rows, failed-result summaries, code blocks.
- **Ink 2** (ink-2) and **Ink 3** (ink-3): secondary text and field labels; muted and empty values.
- **Hairline** (hair): row dividers inside ledgers and comparison tables, chip borders.
- **Plate Rule** (plate-rule) and **Plate Caption** (plate-caption): dividers and caps labels inside the verdict plate only.

### Named Rules
**The Regression-Only Orange Rule.** Orange means "this got worse than before": HOLD, regressed cases, bad deltas, held rows. A test that simply fails is ink. If nothing regressed, no orange appears on screen.

**The One Plate Rule.** The verdict plate on the comparison view is the only reversed black surface. Everything else is black on label stock. A second black panel would compete with the verdict.

**The Signal Pairing Rule.** Every colour signal also has a non-colour signal: stamps carry the word, status chips carry a shape (filled square, crossed box, hatched box, blinking square) and the status word, and held groups carry the "Regressed" heading.

## Typography

**Display Font:** Archivo variable (wdth 62 to 125), with Helvetica Neue, Arial fallback; self-hosted.
**Body Font:** Archivo at normal width.
**Label/Mono Font:** JetBrains Mono, with ui-monospace, Menlo fallback; self-hosted.

**Character:** One variable family does double duty. Squeezed to 62 to 70% width at weight 800 to 900, it becomes shipping-label caps; at normal width it is a plain grotesque for reading. The mono marks text as "verbatim from the machine".

The scale is 11 / 13 / 15 / 18 / 26 / 40 / 64px, plus the stamp clamp (64 to 132px) and a 9px barcode caption. Body sets tabular numerals globally.

### Hierarchy
- **Stamp** (900, wdth 62, clamp(64px, 11vw, 132px), 0.82): the verdict on the plate only.
- **Display** (900, wdth 62, clamp(40px, 6vw, 64px), 0.92, caps): the prompt name in the parcel header. The large routing code (`v3`) uses the same face at a fixed 64px, dropping to 40px on mobile.
- **Route** (900, wdth 62, 40px, 0.9): routing codes in manifest rows and the `V1 → V2` heading on the plate.
- **Headline** (900, wdth 68, 26px, 1, caps): sheet titles, the masthead wordmark, version numbers in the versions ledger.
- **Title** (800, 18px): prompt names, field values, group headings (caps, wdth 68), empty-state headings.
- **Body** (400, 15px, 1.5): sentences, notes, verdict explanation. Descriptions are capped at 58 to 68ch.
- **Small** (13px): secondary notes, hints, "why" text, nav links (caps, 800, 0.1em).
- **Label** (800, wdth 70, 11px, 0.12em, uppercase, ink-2): every field label, table header, form label and section caption.
- **Mono** (13px, 1.6): templates, outputs, inputs, check arguments, deltas, the raw API verdict.

### Named Rules
**The Squeeze For Identity Rule.** Condensed width (62 to 75%) is for caps: titles, codes, stamps, labels, buttons. Running text is never condensed.

**The Caps Label Rule.** Every value sits under a caps field label (11px, 0.12em). On narrow screens this holds for stacked table cells too: each cell prints its column name above the value.

## Layout

The page is a single column of label sheets, max 1240px wide, padded clamp(16px, 4vw, 40px) at the sides with a generous 120px bottom margin. Sheets stack with a 20px gap. Two sheets may sit side by side in a 1:1 split, which collapses to one column at 900px.

The masthead is a sticky 56px label strip across the full width: wordmark left, nav cells right, each nav cell divided by a 1px rule; the current page is marked with a 5px ink underline inset.

Inside a sheet the rhythm is: head (14px 20px) with a 2px rule below, body (18px 20px), foot (12px 20px) on label shade with a 1px rule above. Field grids auto-fit 140px minimum cells divided by 1px rules. Tables use 14px cell padding in the manifest and 11 to 12px in ledgers.

Responsive behaviour: at 900px the plate stacks, result details go to one column, and the manifest's barcode column is dropped. At 680px tables become stacked records; each cell keeps its caps column label; the parcel's routing block moves under the name; the masthead drops "Dispatch".

## Elevation & Depth

Flat paperwork on a board. Depth is only the contact of paper on cardboard: sheets carry a tight 1px contact shadow tinted kraft-ink, never a floating shadow. Hierarchy otherwise comes from rule weight (2px structure, 1px division, hairline rows) and the single reversed plate.

### Shadow Vocabulary
- **Contact edge** (`box-shadow: 0 1px 2px rgba(42, 28, 13, 0.35)`): every sheet resting on the board.
- **Ticker lift** (`box-shadow: 0 2px 6px rgba(0,0,0,.4)`): the fixed receipt-printer status line, the only element that floats above the page.

### Named Rules
**The Paper On Board Rule.** Sheets touch the board; they don't hover. No sheet gets more than the contact edge.

## Shapes

Corners are nearly square. Sheets are 2px, chips 3px, fields and code blocks 4px, buttons 5px; the plate stamp gets 10px because a rubber stamp has rounded corners. Stamps are bordered in their own colour (2.5px small, 7px on the plate), rotated -4 to -5deg, and broken up with a procedural noise mask so the ink looks pressed. Barcodes are real Code 39 generated from ids, printed as SVG bars with the starred id beneath in spaced mono. The meter is a 14px track with a 1px ink border and tick marks every 10%.

## Components

### Buttons
Heavy condensed caps on ink, stamped rather than glowing.
- **Shape:** gently squared (5px), 2px ink border.
- **Primary:** label text on ink, 15px caps (wdth 72, 800, 0.08em), padding 9px 14px 8px; icons are 15px inline SVG.
- **Hover / Focus:** hover lightens the ink slightly and adds a small drop; active presses down 1px; focus is a 3px ink outline offset 2px.
- **Ghost:** transparent with ink text and the same border; hover fills label shade.
- **Quiet:** borderless ink-2 text for secondary actions such as Cancel.
- **Small:** 13px, 6px 10px 5px, 1.5px border, used in ledger row actions.

### Chips
- **Status chip:** caps word plus a 10px shape glyph drawn in CSS: filled square (pass, completed), crossed box (fail), hatched box (error), blinking filled square (running), hollow box (pending). Pass is green, running and pending are blue, everything else is ink.
- **Key/value chip:** mono 13px on label shade, hairline border, 3px radius; used for variables and inputs.
- **Check chip:** label stock with a 1px ink border; caps check type plus its mono argument.

### Cards / Containers
- **Corner Style:** 2px.
- **Background:** label stock on kraft board.
- **Shadow Strategy:** contact edge only (see Elevation & Depth).
- **Border:** 2px ink all round.
- **Internal Padding:** 14 to 20px; heads and bodies are separated by the 2px rule.

### Inputs / Fields
- **Style:** white fill, 1.5px ink border, 4px radius, 9px 11px padding; textareas switch to 13px mono. Selects use a CSS-drawn chevron.
- **Focus:** 3px ink outline offset 1px.
- **Labels:** caps label above every input.
- **Error:** a 2px ink-bordered box on label shade with a bold caps lead word; errors are ink, not orange.

### Navigation
The masthead strip: wordmark (headline weight, plus a light "Dispatch" at the same size), then nav cells on the right as full-height caps links divided by 1px rules. Hover shades the cell; the current cell gets a 5px inset ink underline. Breadcrumbs print straight on the board in kraft ink caps.

### Manifest table
A ruled table, one row per prompt: route code (40px), name and description, case count, last pass-rate meter, the gate stamp, and a barcode. Held rows get a faint orange wash and an orange meter fill. On mobile each row becomes a stacked record with the route code spanning the left.

### Parcel header
The prompt page opens like a carrier label: display-size name and description on the left; on the right, behind a 2px rule, the routing code at 64px over its barcode. Below it, a boxed field grid.

### Verdict plate
The signature component. A full-bleed ink panel at the top of the comparison: on the left the `V1 → V2` route, the big stamp, a one-sentence reason with the counts in bold, and the raw API verdict in mono beneath (`block` is stamped HOLD, so the original word stays visible); on the right a metrics ledger with mono delta pills (bad deltas in orange, good in deep green, neutral in dark grey). Below the plate, a tally line links to each outcome group, with the regressed group first and in hold ink.

**Motion:** the stamp lands once. It drops from 1.5x scale and a 5px blur with an 11deg tilt, overshoots to 0.96, and settles at -5deg (0.55s, cubic-bezier(0.16, 1, 0.3, 1)); the plate takes a 2px thud as it hits. Only runs when `prefers-reduced-motion: no-preference`.

### Loading and ticker
Loading is a "printing label" strip: a small bordered bar with a feeding ink fill and caps text. Transient messages appear in the ticker, a fixed ink pill at the bottom centre that slides up 12px on entry.

## Do's and Don'ts

### Do:
- **Do** put every new surface on a label sheet on kraft board: label stock, 2px ink border, 2px radius, contact-edge shadow.
- **Do** label every value with an 11px caps field label (wdth 70, 800, 0.12em, ink-2), including stacked table cells on mobile (`data-label`).
- **Do** keep orange for regressions and HOLD only; render plain failures and errors in ink.
- **Do** show the API's own word next to any translated verdict (HOLD with `verdict: "block"` beneath).
- **Do** generate barcodes as real Code 39 from the entity id rather than as decorative stripes.
- **Do** use mono for anything verbatim from the model or API: templates, outputs, inputs, deltas.
- **Do** pair every status colour with a word and a shape.
- **Do** gate any new motion behind `prefers-reduced-motion: no-preference`, and keep the stamp landing as the only authored moment.

### Don't:
- **Don't** add a second reversed black surface; the verdict plate is the only one.
- **Don't** use orange for a failing test, an error, a warning, or emphasis.
- **Don't** build sidebars or KPI card grids; lists are ruled tables on a sheet.
- **Don't** float sheets with large or blurred shadows; the contact edge is the only sheet shadow.
- **Don't** condense running text; condensed width is for caps only.
- **Don't** round sheets beyond 2px or buttons beyond 5px; only the plate stamp gets 10px.
- **Don't** use blue for links or actions; it means "in flight" only.
