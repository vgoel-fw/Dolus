# Interface direction

References: Mike (https://app.mikeoss.com/assistant), Vercel, Notion, Ramp, Crosby and Figma. No proprietary assets or layouts were copied.

Structure:

- **Home** (Ramp / Figma file browser): KPI row, three action cards, recent research and corpus tables
- **Research** (Amplitude chart builder): inputs in a sticky left panel, results canvas on the right with tabs for signals & factors, precedent and outcomes. Empty canvas explains what comes back
- **Detail drawer** (Ramp detail sheet / Figma inspector): case and evidence views slide in from the right instead of a centered modal
- **Sidebar** grouped into Workspace, Sources and Insights
- **Logo**: an eye inside a violet-to-magenta tile, for reading intent. `web/favicon.svg` and the inline sidebar mark share it

What we took from them:

- neutral grays with one accent (blue, used for focus, the user's column and semantic-only signals). status colors only where they carry meaning
- thin 1px borders, 8–10px radius, almost no shadow. near-black primary button
- system sans for UI, a serif only for quoted source text so quotes read differently from interface copy, mono for offsets, gaps and rationale lines
- line icons instead of unicode glyphs. no all-caps eyebrows, no arrows on every button, no marketing lines
- 48px sticky top bar, light sidebar, content capped at 1180px
- dark mode follows the OS (`prefers-color-scheme`), with `data-theme` overrides available
- phone width: sidebar becomes an icon row, grids collapse to one column, no horizontal scroll

Everything is plain CSS variables in `web/styles.css`, no build step and no webfont requests. CSP still forbids inline styles, so widths are set from JS via `data-width`.
