# ContextIQ Design System

Governs every component built for the ContextIQ frontend. Tokens are
implemented in [`app/globals.css`](app/globals.css) (mapped into
shadcn/ui's variable contract and Tailwind utilities); this document
defines how to use them. Components consume **semantic tokens only —
raw hex values never appear in component code.**

Design lineage: ChatGPT / Claude / Linear / Vercel / Notion. Minimal,
elegant, dark, expensive-feeling. No neon, no gradients (skeleton
shimmer excepted), no decorative animation.

---

## 1. Color palette

Dark is the **only** theme (`:root` and `.dark` are identical, the
`dark` class is forced in `layout.tsx` — nothing can flash white).

### Neutrals

| Token | Value | Role |
|---|---|---|
| `--background` | `#0a0a0c` | Canvas — almost black, slightly warm |
| `--card` / `--chat-assistant` | `#141417` | Cards, assistant bubbles |
| `--popover` | `#17171b` | Dialogs, menus — one step above card |
| `--secondary` / `--muted` | `#1a1a1e` | Quiet buttons, muted panels |
| `--accent` | `#1e1e23` | Hover / selected rows |
| `--sidebar` | `#131316` | Sidebar panel |
| `--foreground` | `#e7e7ea` | Primary text — 15.6:1 on canvas |
| `--muted-foreground` | `#8b8b93` | Secondary text — 5.9:1 (AA) |
| `--border` | `white @ 8%` | Hairlines |
| `--input` | `white @ 10%` | Form-control borders |

Elevation on a dark canvas comes from **surface steps + 1px borders,
not shadows** (shadows barely read on near-black). Each nesting level
goes one surface step up; never skip steps, never stack more than
three levels.

### Brand blue — the two-step ramp (do not "simplify")

One hue, two jobs, because no single blue passes WCAG AA in both roles:

| Token | Value | Use for | Contrast |
|---|---|---|---|
| `--ring` (accent) | `#3B82F6` | Text, borders, icons, focus rings ON dark surfaces | 5.4:1 vs canvas ✓ |
| `--primary` | `#1D4ED8` | SOLID fills under white text (primary buttons) | 6.7:1 under white ✓ |

`#3B82F6` under white text is 3.7:1 — an AA failure we already fixed
once in v1.0. Blue is the only brand color; a second accent hue is a
design-review rejection.

## 2. Dark mode

Forced via `class="dark"` on `<html>`. There is no light theme and no
theme toggle — "private, focused tool" is the brand. `prefers-color-scheme`
is deliberately ignored. If a light theme ever ships it is a new
token sheet, not per-component overrides.

## 3. Typography

Geist Sans (already wired via `next/font`; `--font-sans`), Geist Mono
for code, chunk IDs, and numeric badges. Weights: 400 body, 500
labels/buttons, 600 headings, 700–800 hero only.

| Step | Size / line-height | Weight | Use |
|---|---|---|---|
| `display` | 36px / 1.1, tracking −0.02em | 800 | Empty-state hero only |
| `h1` | 24px / 1.2, tracking −0.02em | 700 | Page title (compact header) |
| `h2` | 18px / 1.3, tracking −0.01em | 600 | Dialog titles, section heads |
| `label` | 12px / 1.3, tracking +0.06em, uppercase | 700 | Sidebar section labels |
| `body` | 15px / 1.6 | 400 | Chat messages, paragraphs |
| `small` | 13px / 1.5 | 400–500 | Captions, source rows, footer |
| `mono` | 12–13px | 400 | Chunk IDs, settings values |

Chat text column max-width: **48rem**, centered. Real heading elements
(`h1`–`h3`) for semantics — exactly one `h1` per page.

## 4. Spacing

Tailwind's 4px grid. Semantic conventions:

| Step | px | Convention |
|---|---|---|
| 1 | 4 | Icon-to-label gaps |
| 2 | 8 | Intra-control padding, badge gaps |
| 3 | 12 | Between related controls |
| 4 | 16 | Card padding, message padding |
| 6 | 24 | Between sidebar sections, dialog padding |
| 8 | 32 | Page top/bottom breathing room |
| 12 | 48 | Hero-to-content gap |

Consecutive chat messages: 10px apart (same speaker reads as a
thread); 16px between speaker turns.

## 5. Border radius

Base `--radius: 12px`; shadcn derives the scale.

| Token | ≈px | Use |
|---|---|---|
| `rounded-lg` | 12 | Cards, chat bubbles, dialogs |
| `rounded-md` | 10 | Inputs, source rows |
| `rounded-sm` | 7 | Buttons, badges |
| `rounded-full` | ∞ | Chunk-ID pills, avatars, dots |

Never mix radii on sibling elements of the same kind.

## 6. Cards

`bg-card`, `border border-border`, `rounded-lg`, `p-4`. No shadows
(see elevation note above); a raised/hover state is `bg-accent` or a
`border-chat-user-border`-style accent border — never a shadow bump.
Interactive cards get `transition-colors duration-150`.

## 7. Buttons

shadcn Button variants, mapped:

| Variant | Fill / text | Border | Hover |
|---|---|---|---|
| `default` (primary) | `--primary` / white | none | darken (keeps AA) |
| `secondary` | `--secondary` / `--foreground` | `--border` | `--accent` bg |
| `ghost` | transparent / `--foreground` | none | `--accent` bg |
| `destructive` | `--destructive` / white | none | darken |
| `outline` | transparent / `--foreground` | `--input` | ring-colored border |

Rules: min touch height 40px; one primary button per view region;
icon+label gap 8px (Lucide, 16px icons); `transition-colors 150ms`
only — no scale/translate effects. Focus: 2px `--ring` outline,
2px offset, on **every** interactive element (`focus-visible`).

## 8. Forms & input fields

- Field: `bg-transparent`, `border border-input`, `rounded-md`,
  15px text, placeholder `--muted-foreground`.
- Focus: border becomes `--ring` (plus the standard focus ring).
- Error state: border `--error`, message below in `--error` 13px —
  never color-only; always pair with text.
- Labels: `small` size, weight 500, 6px above the field.
- The chat input is the flagship form control: pinned bottom, card
  surface, `rounded-lg`, send button (primary, icon-only, `Send`
  Lucide icon) inside the field's right edge.

## 9. Dialogs

shadcn Dialog on `--popover` surface, `rounded-lg`, `p-6`, max-width
28rem, overlay `black @ 60%`. Title `h2`, body `small` in
`--muted-foreground`. Destructive confirmations (Clear database):
destructive button right, ghost Cancel left of it. Entrance: fade +
2% scale, 150ms ease-out — Framer Motion, respecting
`prefers-reduced-motion`.

## 10. Sidebar

`--sidebar` surface, 1px right border, fixed 280px (collapses to a
shadcn Sheet drawer under 768px). Anatomy, top to bottom: brand
lockup (34px `--primary` mark with white "C", name 15px/700, tagline
12px muted) → New chat (secondary, full-width) → `label`-style
section heading → Knowledge-base card (uploader dropzone: dashed
`--input` border, `rounded-lg`, hover border `--ring`; file rows:
13px with Lucide `FileText`/`File` icons; capped list + "+N more") →
collapsible Model details (mono values) → footer pinned to bottom
("Built with…", 12px muted). Active/hover rows: `bg-sidebar-accent`.

## 11. Chat bubbles

| | User | Assistant |
|---|---|---|
| Surface | `--chat-user` (blue @ 14%) | `--chat-assistant` |
| Border | `--chat-user-border` (blue @ 28%) | `--border` |
| Alignment | right, max-width 82% (92% mobile) | left, full column width |
| Radius | `rounded-lg` | `rounded-lg` |
| Padding | 12×16px | 16×20px |

Entrance: fade + 4px rise, 200ms ease-out, once (no re-animation on
scroll). Typing indicator: three `--ring`-colored dots, staggered
pulse — one of only two looping animations in the product (the other
is the skeleton shimmer). Below each assistant answer: the sources
expander — collapsed by default, one row per source (filename
truncates with ellipsis · mono chunk-ID pill · similarity % in
`--ring` blue, tabular-nums).

## 12. Status colors

Text tokens pass AA on the canvas; `-soft` variants are 12%-alpha
surfaces for badges/alerts. Always icon + text, never color alone.

| Status | Text token | Ratio | Soft bg | Solid fill |
|---|---|---|---|---|
| Success | `--success` `#34d399` | 9.9:1 | `--success-soft` | `--success-solid` `#059669` |
| Warning | `--warning` `#fbbf24` | 11.5:1 | `--warning-soft` | — (never solid) |
| Error | `--error` `#f87171` | 6.9:1 | `--error-soft` | `--destructive` `#dc2626` |
| Info | `--info` `#60a5fa` | 7.5:1 | `--info-soft` | use primary |

## 13. Loading skeletons

`bg-skeleton` blocks, radius matching the element they stand in for
(text lines: `rounded-sm` at 60–90% width; cards: `rounded-lg`).
Optional `skeleton-shimmer` class adds the 1.6s gradient sweep —
automatically static under `prefers-reduced-motion`. Use skeletons
for **layout-shaped** waits (loading the document list); use the
typing indicator for **generation** waits; use button spinners for
**action** waits (indexing). Never two skeleton styles in one view.

## 14. Motion (summary)

150ms `transition-colors` for all hover/focus; 150–200ms fade+rise
for entrances; the two sanctioned loops (typing dots, skeleton
shimmer); everything gated on `prefers-reduced-motion`. Framer Motion
is the only animation library; if a motion feels "fun", cut it.

---

*Change policy: token values change here and in `globals.css`
together, with contrast ratios re-verified. Components never
introduce colors, radii, or font sizes outside this sheet.*
