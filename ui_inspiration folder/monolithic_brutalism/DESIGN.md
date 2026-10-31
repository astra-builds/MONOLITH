---
name: Monolithic Brutalism
colors:
  surface: '#131313'
  surface-dim: '#131313'
  surface-bright: '#3a3939'
  surface-container-lowest: '#0e0e0e'
  surface-container-low: '#1c1b1b'
  surface-container: '#201f1f'
  surface-container-high: '#2a2a2a'
  surface-container-highest: '#353534'
  on-surface: '#e5e2e1'
  on-surface-variant: '#c3c9af'
  inverse-surface: '#e5e2e1'
  inverse-on-surface: '#313030'
  outline: '#8d937b'
  outline-variant: '#434935'
  surface-tint: '#a1d811'
  primary: '#ffffff'
  on-primary: '#253600'
  primary-container: '#bcf538'
  on-primary-container: '#506e00'
  inverse-primary: '#4b6700'
  secondary: '#c6c7c1'
  on-secondary: '#2f312d'
  secondary-container: '#4a4c48'
  on-secondary-container: '#bcbcb6'
  tertiary: '#ffffff'
  on-tertiary: '#2f3031'
  tertiary-container: '#e3e2e2'
  on-tertiary-container: '#646464'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#bcf538'
  primary-fixed-dim: '#a1d811'
  on-primary-fixed: '#141f00'
  on-primary-fixed-variant: '#384e00'
  secondary-fixed: '#e3e3dd'
  secondary-fixed-dim: '#c6c7c1'
  on-secondary-fixed: '#1a1c19'
  on-secondary-fixed-variant: '#464743'
  tertiary-fixed: '#e3e2e2'
  tertiary-fixed-dim: '#c7c6c6'
  on-tertiary-fixed: '#1b1c1c'
  on-tertiary-fixed-variant: '#464747'
  background: '#131313'
  on-background: '#e5e2e1'
  surface-variant: '#353534'
typography:
  display-hero:
    fontFamily: Chivo
    fontSize: 80px
    fontWeight: '900'
    lineHeight: 84px
    letterSpacing: -0.04em
  display-hero-mobile:
    fontFamily: Chivo
    fontSize: 44px
    fontWeight: '900'
    lineHeight: 48px
    letterSpacing: -0.03em
  headline-lg:
    fontFamily: Chivo
    fontSize: 48px
    fontWeight: '800'
    lineHeight: 52px
    letterSpacing: -0.03em
  headline-lg-mobile:
    fontFamily: Chivo
    fontSize: 32px
    fontWeight: '800'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Chivo
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-sm:
    fontFamily: Chivo
    fontSize: 20px
    fontWeight: '700'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Space Mono
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Space Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  body-sm:
    fontFamily: Space Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0.01em
  label-code:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-meta:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '700'
    lineHeight: 12px
    letterSpacing: 0.08em
spacing:
  gutter: 0px
  gutter-desktop: 0px
  margin: 1rem
  margin-desktop: 1.5rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 3rem
---

## Brand & Style

The design system embodies an uncompromising computational instrument crafted for polymaths, systems architects, and technical researchers. It rejects modern software trends that rely on simulated tactile materials, soft consumerist radiuses, or obfuscating skeuomorphism. Instead, the interface treats the screen as an architectural drafting board: stark, unyielding, hyper-legible, and rooted in International Typographic Style fused with digital brutalism.

The aesthetic evokes the precision of mainframe instrumentation, physical mid-century industrial terminals, and Swiss editorial manifests. Visual hierarchy is established strictly through scale contrast, hairline architectural dividers, and sudden tactical injections of high-visibility signal color. Interactions do not bounce or simulate rubberized physics; they toggle instantaneously, reinforcing absolute determinism and computational authority.

## Colors

The palette operates on extreme dynamic range against an absolute light sink. It deliberately limits hue complexity to prioritize data legibility and optical velocity.

- **Primary (`#C5FF42` - Acid Lime):** A tactical signal color reserved strictly for focus rings, critical terminal outputs, active state indicators, telemetry pings, and high-priority commands. It must never be diluted with transparency or gradients.
- **Secondary (`#E4E4DE` - Architectural White):** The primary foreground tone for display typography and structural titling, reducing eye fatigue compared to pure `#FFFFFF` while retaining hard contrast against the dark background.
- **Tertiary (`#8E8E8E` - Technical Slate):** Dedicated to technical metadata, tabular column titles, coordinate grids, and inactive state annotations.
- **Neutral (`#101010` - Void Black):** The primary spatial canvas, supported by `#0A0A0A` for recessed sub-layers and `#262626` for structural 1px hairline perimeter bounds.

## Typography

The typographic hierarchy is built on sharp structural contrast: dense, heavyweight, compressed headlines set in Chivo juxtaposed against rigid, monospace technical readouts set in Space Mono and JetBrains Mono.

- **Headlines & Banners:** Rendered in high-density weights of Chivo with tightened tracking to project an authoritative, posterized editorial stance.
- **Monospace Workhorse:** Space Mono governs content, body prose, and operational feeds, enforcing a strict cadence where data and prose share identical tabular alignment.
- **Micro-Labels & Technical Annotations:** JetBrains Mono at 10px uppercase with generous tracking (`0.08em`) defines coordinate tags, system states, memory limits, and hardware metrics.

## Layout & Spacing

The layout model is anchored in an architectural coordinate grid. Panes, docks, and views do not float; they abut directly against one another, separated entirely by hairline structural borders rather than empty gutter channels.

- **Border-Divided Grid:** Columns and panels join seamlessly with 0px gutters, demarcated by continuous `1px solid #262626` dividing axes.
- **Spatial Alignment:** Internal component padding conforms strictly to a 4px/8px incremental cadence. Content must align to the top-left boundary of its enclosing structural quadrant.
- **Responsive Geometry:**
  - **Desktop (>= 1280px):** Multi-pane tiling layout spanning arbitrary 12-column subdivisions, docking technical telemetry panels into fixed 240px–360px vertical rails.
  - **Tablet (768px - 1279px):** Collapses to 2-pane tiled view with top-to-bottom layout stacking.
  - **Mobile (< 768px):** Stacks all grid quadrants into full-bleed modular tiles, retaining explicit edge-to-edge hairline boundaries.

## Elevation & Depth

This design system deliberately excludes drop shadows, ambient blurs, depth-mapping z-axis dropoffs, and translucent frosted materials. Elevation is conveyed strictly through two mechanisms:

1. **Planar Tiering:** Deep layers use `#0A0A0A`, standard interaction panels use `#101010`, and contextual overlays/popovers utilize `#161616`.
2. **Hairline Structural Borders:** Every interface plane is encapsulated by a crisp `1px solid #262626` outline. Active, elevated, or modal panes switch their bounding borders directly to `1px solid #C5FF42`, cutting cleanly through the visual hierarchy with absolute planar prominence.

## Shapes

The geometry of the interface is unyielding: all radii are strictly 0px across all viewports, components, inputs, and system overlays.

Interactive boundaries, dialogue windows, tags, and status indicators preserve hard, mathematical 90-degree right angles. There are no pill buttons, soft corners, or organic cutaways. Every element reads as an exact, engineered slice of display hardware.

## Components

### Buttons & Interactive Triggers
- **Geometry & Border:** Strict rectangular geometry (`border-radius: 0`), bounded by `1px solid #262626`.
- **Typography:** Set in JetBrains Mono, uppercase, `11px`, with `letter-spacing: 0.06em`.
- **Default State:** Canvas `#101010`, foreground text `#E4E4DE`.
- **Hover/Active State:** Immediate inverted visual state: background shifts to `#C5FF42`, text to `#0A0A0A`, with zero transition delay.
- **Destructive/Critical:** Border and text shift to high-contrast monochrome inversion without introducing non-essential hues.

### Input Fields & Terminal Prompts
- **Structure:** Flush box layout with `1px solid #262626` perimeter, inset `space-sm` on vertical and `space-md` on horizontal.
- **Typography:** Space Mono `13px`, rendering with a steady, non-blinking solid `#C5FF42` block cursor.
- **Focus State:** Border changes instantly to `1px solid #C5FF42`. Placeholder text displays in `#8E8E8E` with a leading system chevron (`> `).

### Cards & Content Quadrants
- **Structure:** Cards are termed "Quadrants." They do not float or display drop shadows. They sit flush against adjacent quadrants, demarcated by `1px solid #262626` hairlines.
- **Header Structure:** Every quadrant features an upper telemetry band separated by a horizontal 1px rule, containing an uppercase JetBrains Mono micro-label on the left and an architectural coordinate or status indicator on the right (e.g., `SYS.01 // READY`).

### Lists & Data Tables
- **Grid Lines:** Monospaced data displays over alternating rows without zebra striping; rows are delineated strictly with `1px solid #1C1C1C` horizontal borders.
- **Density:** Compact vertical padding (`space-xs` to `space-sm`) with strict horizontal tabular numbers (`font-variant-numeric: tabular-nums`).
- **Row Focus:** Hovering or navigating via keyboard keys highlights the entire row with a left border marker `2px solid #C5FF42`.

### Checkboxes & Toggle Switches
- **Checkboxes:** 14px by 14px sharp squares (`border: 1px solid #8E8E8E`). When checked, the box fills entirely with `#C5FF42` enclosing a black `#0A0A0A` square core, rather than a curved checkmark glyph.
- **Toggles:** Replaced by binary state segments (`[OFF] [ON]`) bound within a joint rectangular border enclosure, activating the selected state via inverse color fill.

### Telemetry Bars & Badges
- **Badges/Chips:** Rectangular micro-labels with `1px solid #262626`, displaying status data in 10px uppercase monospaced text. Active states prefix a filled `■` block character in `#C5FF42`.
- **System Splitters:** 1px hairline dividers that provide interactive resize handles, highlighting in Acid Lime when dragged.