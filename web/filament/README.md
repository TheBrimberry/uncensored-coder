# Filament Build Console — landing page

A redesigned, from-scratch take on the "describe it, ship it" AI app-builder landing
page. Single file, no build step, no dependencies beyond Google Fonts.

**Author:** JAZZYLYFE

## What's in it

- **Workbench hero** — prompt composer on the left, a live build console on the right,
  instead of a centered hero box on a dot grid.
- **Four build targets** (Full stack / Mobile / Website / Extension). Switching a tab
  swaps the placeholder, the seed brief, the stack badges, the example chips, *and*
  replays a target-specific build stream (schema → API → UI → tests → deploy URL).
- **`Build it`** (or `Cmd/Ctrl + Enter` in the composer) replays the stream; example
  chips fill the composer.
- **Pipeline strip** — numbered because it genuinely is a sequence: intent → plan →
  scaffold → verify → ship.
- Capability sections with real artifacts (a diff with its reason, a file tree, a
  ship-gate checklist), a spec table, pricing, FAQ, footer.

## Design tokens

| Role | Light | Dark |
| --- | --- | --- |
| ground | `#E9ECF2` | `#0D1017` |
| surface | `#FFFFFF` | `#151A25` |
| filament amber | `#B8560B` | `#F2913A` |
| signal teal | `#0A6F6A` | `#3FD0C4` |
| pass | `#1B7F46` | `#4BD07E` |

Type: **Bricolage Grotesque** (display) · **Public Sans** (body) ·
**JetBrains Mono** (console, labels, figures).

## Behaviour notes

- Theme-aware across all three viewer states: explicit light, explicit dark, and the
  un-stamped system default. Every colour is a token declared on bare `:root` first.
- `prefers-reduced-motion` skips the streaming animation and paints the finished
  build immediately.
- Responsive to ~360px; the console stops sticking and stacks under the composer
  below 960px.
- All build output is clearly labelled as a sample run — no fabricated customer
  counts, logos, or testimonials.

## Run it

Open `index.html` in a browser. That's the whole thing.
