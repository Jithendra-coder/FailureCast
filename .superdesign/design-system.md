# FailureCast design system

## Product and visual direction
A desktop-first reliability operations workspace for maintenance engineers. Keep it precise, quiet, and credible: cool neutral canvas, deep navy frame, crisp type, and restrained blue/teal state colors. Data must be legible at a glance. The app is a research demonstration using historical/simulated data; never style a forecast as a guarantee or imply live equipment control.

## Existing implementation tokens
The current stylesheet is the source of truth for existing values; the complete file is in .superdesign/init/theme.md.

- Canvas: #f5f7f9; surfaces: #fff; deep sidebar: #111c2c.
- Main text: #172435; supporting text uses slate/blue-gray; separators and chart grids are light gray.
- Primary actions and model series use blue around #477de3; healthy/live uses teal-green around #30b99b; watch uses amber; critical uses red.
- Body font: DM Sans; display/headings: Manrope.
- Card treatment: white, thin cool-gray border, 8–12px radius, low-opacity shadow.
- Navigation is a fixed dark left sidebar on desktop and an off-canvas drawer on mobile. Main content uses a light neutral background with responsive card grids.
- Responsive breakpoints: 1150px, 900px, 700px, 390px.

## Frontend libraries
- React 18 + TypeScript + Vite.
- Lucide React icons; Recharts for operational time-series.
- Custom global CSS; no component library or Tailwind configuration.

## Safety and copy conventions
- Label simulated/historical telemetry explicitly.
- Distinguish observed sensor data from model estimates.
- Always label RUL as estimated and avoid calibrated-confidence claims unless calibrated.
- Show that alerts require review and do not control equipment.
